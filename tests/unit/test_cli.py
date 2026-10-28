"""Functional CLI tests with a mocked HTTP boundary."""

from __future__ import annotations

import base64
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
import pytest
from typer.testing import CliRunner

from sylve_cli.config import ContextConfig, SylveConfig, save_config
from sylve_cli.main import app, run

runner = CliRunner()


def make_jwt(expires_at: datetime) -> str:
    """Build an unsigned JWT for tests."""
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').decode().rstrip("=")
    payload = (
        base64.urlsafe_b64encode(
            json.dumps({"sub": "admin", "exp": int(expires_at.timestamp())}).encode()
        )
        .decode()
        .rstrip("=")
    )
    return f"{header}.{payload}.sig"


@pytest.fixture()
def cli_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Configure a temporary CLI context and a mock Sylve API."""
    token = make_jwt(datetime.now(timezone.utc) + timedelta(hours=1))
    config_path = tmp_path / "config.yaml"
    save_config(
        SylveConfig(
            current_context="test",
            contexts={
                "test": ContextConfig(
                    server="https://sylve.example.test",
                    username="admin",
                    token=token,
                    hostname="node1.lan",
                    verify_ssl=False,
                )
            },
        ),
        config_path,
    )
    monkeypatch.setenv("SYLVE_CONFIG", str(config_path))

    nodes = [
        {
            "nodeUUID": "u1",
            "hostname": "node1.lan",
            "status": "online",
            "guestIDs": [101],
        }
    ]
    resources = [
        {
            "hostname": "node1.lan",
            "vms": [{"rid": 101, "name": "web", "state": 1}],
            "jails": [{"ctId": 201, "name": "app", "state": "ACTIVE"}],
        }
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/cluster/nodes":
            return httpx.Response(200, json={"status": "success", "data": nodes})
        if path == "/api/cluster/resources":
            return httpx.Response(200, json={"status": "success", "data": resources})
        if path == "/api/cluster":
            return httpx.Response(
                200,
                json={
                    "status": "success",
                    "data": {
                        "cluster": {"enabled": True, "raftIP": "10.0.0.1", "raftPort": 7000},
                        "nodeId": "u1",
                        "leaderId": "u1",
                        "leaderAddress": "10.0.0.1:7000",
                        "partial": False,
                        "nodes": [],
                    },
                },
            )
        if path == "/api/zfs/pools":
            return httpx.Response(
                200,
                json={
                    "status": "success",
                    "data": [
                        {
                            "name": "zroot",
                            "pool_guid": "g1",
                            "state": "ONLINE",
                            "size": 107374182400,
                            "free": 107374182400,
                        }
                    ],
                },
            )
        if path == "/api/system/pci-devices":
            return httpx.Response(
                200,
                json={
                    "status": "success",
                    "data": [{"domain": 0, "bus": 1, "device": 2, "function": 0}],
                },
            )
        if path in ("/api/vm/simple", "/api/jail/simple"):
            return httpx.Response(200, json={"status": "success", "data": []})
        if path in ("/api/cluster/notes", "/api/info/notes"):
            return httpx.Response(
                200,
                json={
                    "status": "success",
                    "data": [
                        {
                            "id": 1,
                            "title": "Maintenance",
                            "content": "Disk replacement 22:00",
                            "updatedAt": "2026-10-28T20:00:00Z",
                        }
                    ],
                },
            )
        if path == "/api/auth/sse-tokens":
            return httpx.Response(
                200,
                json={"status": "success", "data": {"token": "sse-tok", "expiresIn": 600}},
            )
        if path == "/api/events/stream":
            assert request.url.params.get("sse_token") == "sse-tok"
            return httpx.Response(
                200,
                content=b'event: ping\ndata: {"ok":true}\n\n',
                headers={"Content-Type": "text/event-stream"},
            )
        if path == "/api/network/firewall/logs/live":
            cur = int(request.url.params.get("cursor") or 0)
            return httpx.Response(
                200,
                json={
                    "status": "success",
                    "data": {
                        "items": [
                            {
                                "cursor": cur + 1,
                                "timestamp": "2026-10-29T00:00:00Z",
                                "action": request.url.params.get("action") or "block",
                                "direction": "in",
                                "interface": "em0",
                                "ruleId": 7,
                                "rawLine": "block in on em0",
                            }
                        ],
                        "nextCursor": cur + 1,
                        "sourceStatus": "ok",
                    },
                },
            )
        if path == "/api/vm/999":
            return httpx.Response(
                404,
                json={
                    "status": "error",
                    "message": "vm_not_found",
                    "error": "vm 999 does not exist",
                },
            )
        return httpx.Response(200, json={"status": "success", "data": {}})

    original_init = httpx.Client.__init__

    def patched_init(self: Any, *args: Any, **kwargs: Any) -> None:
        kwargs["transport"] = httpx.MockTransport(handler)
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.Client, "__init__", patched_init)
    return config_path


def test_version_and_help() -> None:
    version = runner.invoke(app, ["--version"])
    assert version.exit_code == 0
    assert version.stdout.startswith("sylve-cli ")
    assert runner.invoke(app, ["--help"]).exit_code == 0


def test_config_commands(cli_env: Path) -> None:
    view = runner.invoke(app, ["config", "view", "-f", "json"])
    assert view.exit_code == 0
    assert json.loads(view.stdout)["current_context"] == "test"

    contexts = runner.invoke(app, ["config", "get-contexts", "-f", "json"])
    assert contexts.exit_code == 0
    assert [item["name"] for item in json.loads(contexts.stdout)] == ["test"]

    use = runner.invoke(app, ["config", "use-context", "test"])
    assert use.exit_code == 0

    set_node = runner.invoke(app, ["config", "set-node", "node1.lan"])
    assert set_node.exit_code == 0

    delete = runner.invoke(app, ["config", "delete-context", "test"])
    assert delete.exit_code == 0


def test_jail_list_structured_output(cli_env: Path) -> None:
    result = runner.invoke(app, ["jail", "list", "-f", "json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data[0]["ctId"] == 201
    assert data[0]["name"] == "app"


def test_vm_create_dry_run_parses_options(cli_env: Path) -> None:
    result = runner.invoke(
        app,
        [
            "vm",
            "create",
            "web-02",
            "--rid",
            "102",
            "--memory",
            "2G",
            "--disk-size",
            "20G",
            "--pool",
            "zroot",
            "--no-vnc",
            "--dry-run",
            "-f",
            "json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["name"] == "web-02"
    assert payload["rid"] == 102
    assert payload["ram"] == 2 * 1024**3
    assert payload["storageSize"] == 20 * 1024**3
    assert payload["vncEnabled"] is False


def test_dynamic_system_command(cli_env: Path) -> None:
    result = runner.invoke(app, ["system", "pci-list", "-f", "json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data[0]["bus"] == 1


def test_api_and_formatter_errors_exit_nonzero(cli_env: Path) -> None:
    missing = runner.invoke(app, ["vm", "show", "999", "-f", "json"])
    assert missing.exit_code == 1

    bad_column = runner.invoke(app, ["jail", "list", "-c", "nope"])
    assert bad_column.exit_code == 1


def test_run_without_login_prints_clean_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """No configured session must print a one-line error, not a traceback."""
    monkeypatch.setenv("SYLVE_CONFIG", str(tmp_path / "missing.yaml"))
    for var in ("SYLVE_SERVER", "SYLVE_TOKEN", "SYLVE_CONTEXT"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(sys, "argv", ["sylve", "whoami"])
    with pytest.raises(SystemExit) as exc_info:
        run()
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "Not logged in" in captured.err
    assert "Traceback" not in captured.err


def test_yes_flag_only_on_destructive_generic_commands(cli_env: Path) -> None:
    readonly = runner.invoke(app, ["task", "active", "--help"])
    assert readonly.exit_code == 0
    assert "--yes" not in readonly.stdout

    destructive = runner.invoke(app, ["system", "notes-delete", "--help"])
    assert destructive.exit_code == 0
    assert "--yes" in destructive.stdout


def test_note_show_commands(cli_env: Path) -> None:
    show = runner.invoke(app, ["cluster", "note", "show", "1", "-f", "json"])
    assert show.exit_code == 0
    assert json.loads(show.stdout)["content"] == "Disk replacement 22:00"

    missing = runner.invoke(app, ["cluster", "note", "show", "9", "-f", "json"])
    assert missing.exit_code == 1

    host = runner.invoke(app, ["system", "notes-show", "1", "-f", "json"])
    assert host.exit_code == 0
    assert json.loads(host.stdout)["title"] == "Maintenance"

    host_missing = runner.invoke(app, ["system", "notes-show", "9", "-f", "json"])
    assert host_missing.exit_code == 1


def test_sse_events_and_firewall_logs_cursor(cli_env: Path) -> None:
    events = runner.invoke(app, ["system", "events", "--lines", "2", "--no-reconnect"])
    assert events.exit_code == 0
    assert "event: ping" in events.stdout

    fw = runner.invoke(
        app,
        [
            "network",
            "firewall",
            "logs",
            "--cursor",
            "5",
            "--action",
            "pass",
            "--rule-type",
            "traffic",
            "-f",
            "json",
        ],
    )
    assert fw.exit_code == 0
    items = json.loads(fw.stdout)
    assert items[0]["cursor"] == 6
    assert items[0]["action"] == "pass"


def test_console_ws_auth_and_protocol() -> None:
    import hashlib

    from sylve_cli.console_ws import (
        build_resize_frame,
        build_ws_auth_hex,
        decode_server_frame,
        encode_client_frame,
        format_console_http_error,
        scan_detach_escape,
    )

    hex_auth = build_ws_auth_hex("jwt-token", "node1.lan")
    decoded = json.loads(bytes.fromhex(hex_auth).decode("utf-8"))
    assert decoded == {
        "hash": hashlib.sha256(b"jwt-token").hexdigest(),
        "hostname": "node1.lan",
    }

    err_409 = format_console_http_error(
        409,
        b'{"status":"error","message":"vm_serial_console_disabled","error":"disabled"}',
        "/vm/101/console",
    )
    assert "options-serial-console" in str(err_409)

    err_401 = format_console_http_error(401, b"", "/info/terminal")
    assert "sylve login" in str(err_401)

    fwd, at_bol, detach, pending = scan_detach_escape(b"hello\r~.", True)
    assert fwd == b"hello\r"
    assert not at_bol
    assert detach is True

    fwd2, at_bol2, detach2, pending2 = scan_detach_escape(b"~~abc\n", True)
    assert fwd2 == b"~abc\n"
    assert at_bol2 is True
    assert detach2 is False
    assert pending2 == b""

    # Server frame round-trip (unmasked binary frame from server)
    class _FakeSock:
        def __init__(self, data: bytes) -> None:
            self._buf = bytearray(data)

        def recv(self, n: int) -> bytes:
            out = bytes(self._buf[:n])
            del self._buf[:n]
            return out

    sock = _FakeSock(b"\x82\x05hello")
    frame = decode_server_frame(sock, bytearray())
    assert frame == (2, b"hello")
    assert len(encode_client_frame(b"\x00ls\n")) == 2 + 4 + 4
    assert len(build_resize_frame(80, 24)) > 10
