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
        if path == "/api/vm/101" and request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "status": "success",
                    "data": {
                        "rid": 101,
                        "name": "web",
                        "ram": 4 * 1024**3,
                        "storages": [
                            {
                                "id": 1,
                                "name": "boot",
                                "type": "zvol",
                                "pool": "zroot",
                                "size": 40 * 1024**3,
                                "emulation": "virtio-blk",
                            }
                        ],
                        "networks": [
                            {
                                "id": 1,
                                "emulation": "virtio",
                                "mac": "02:00:00:aa:bb:cc",
                                "standardSwitch": {"name": "vm-public"},
                            }
                        ],
                        "snapshots": [{"id": 7, "name": "pre-upgrade"}],
                        "cloudInitData": "#cloud-config\npackages:\n  - vim\n",
                        "cloudInitMetaData": "instance-id: web\n",
                        "cloudInitNetworkConfig": "",
                    },
                },
            )
        if path == "/api/jail/201" and request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "status": "success",
                    "data": {
                        "ctId": 201,
                        "name": "app",
                        "memory": 2 * 1024**3,
                        "storages": [{"id": 1, "name": "root", "pool": "zroot", "isBase": True}],
                        "networks": [
                            {
                                "id": 1,
                                "name": "vnet0",
                                "dhcp": True,
                                "standardSwitch": {"name": "vm-public"},
                            }
                        ],
                        "snapshots": [{"id": 3, "name": "clean"}],
                        "jailHooks": [
                            {"phase": "prestart", "enabled": True, "script": "/bin/true"},
                            {"phase": "poststop", "enabled": False, "script": ""},
                        ],
                        "fstab": "/data /mnt nullfs ro 0 0\n/logs /var/log nullfs rw 0 0\n",
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


def test_vm_show_summarizes_by_default_and_pretty_prints_with_long(cli_env: Path) -> None:
    short = runner.invoke(app, ["vm", "show", "101"])
    assert short.exit_code == 0, short.stdout
    assert "4.0 GiB" in short.stdout
    assert "#1 boot (zvol on zroot, 40.0 GiB, virtio-blk)" in short.stdout
    assert "#1 virtio on vm-public (02:00:00:aa:bb:cc)" in short.stdout
    assert "1 (latest: pre-upgrade)" in short.stdout
    assert "user-data (3 lines), meta-data (1 lines)" in short.stdout
    assert "#cloud-config" not in short.stdout

    detailed = runner.invoke(app, ["vm", "show", "101", "--long"])
    assert detailed.exit_code == 0, detailed.stdout
    assert '"emulation": "virtio-blk"' in detailed.stdout
    assert "#cloud-config\n" in detailed.stdout
    assert "  - vim" in detailed.stdout

    jail_short = runner.invoke(app, ["jail", "show", "201"])
    assert jail_short.exit_code == 0, jail_short.stdout
    assert "2.0 GiB" in jail_short.stdout
    assert "#1 root (pool zroot, base)" in jail_short.stdout
    assert "#1 vnet0 on vm-public (dhcp)" in jail_short.stdout
    assert "1 (latest: clean)" in jail_short.stdout
    assert "prestart" in jail_short.stdout
    assert "2 lines (use --long)" in jail_short.stdout

    jail_long = runner.invoke(app, ["jail", "show", "201", "--long"])
    assert jail_long.exit_code == 0, jail_long.stdout
    assert '"isBase": true' in jail_long.stdout
    assert "/data /mnt nullfs ro 0 0\n" in jail_long.stdout
    assert "/logs /var/log nullfs rw 0 0" in jail_long.stdout


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


def test_generic_set_replaces_inline_json() -> None:
    result = runner.invoke(
        app,
        [
            "system",
            "tunable",
            "set",
            "--property",
            "name=kern.maxfiles",
            "--property",
            "value=200000",
            "--dry-run",
            "-f",
            "json",
        ],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["method"] == "PUT"
    assert payload["path"] == "/system/tunables"
    # 'value' is a string in BODY_SCHEMAS, so numeric strings stay strings.
    assert payload["body"] == {"name": "kern.maxfiles", "value": "200000"}


def test_generic_set_merges_over_data() -> None:
    result = runner.invoke(
        app,
        [
            "vm",
            "hardware",
            "cpu",
            "101",
            "--data",
            '{"cpuSockets": 1}',
            "--property",
            "cpuCores=4",
            "--dry-run",
            "-f",
            "json",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout)["body"] == {"cpuSockets": 1, "cpuCores": 4}


def test_generic_set_openstack_lists_and_objects() -> None:
    switch = runner.invoke(
        app,
        [
            "network",
            "switch",
            "set-standard",
            "1",
            "--property",
            "private=false",
            "--property",
            "addresses4=cidr=10.0.0.1/24,objectId=0",
            "--property",
            "addresses4=cidr=10.0.1.1/24,objectId=0",
            "--dry-run",
            "-f",
            "json",
        ],
    )
    assert switch.exit_code == 0, switch.stdout
    assert json.loads(switch.stdout)["body"] == {
        "private": False,
        "addresses4": [
            {"cidr": "10.0.0.1/24", "objectId": 0},
            {"cidr": "10.0.1.1/24", "objectId": 0},
        ],
    }

    pci = runner.invoke(
        app,
        [
            "vm",
            "hardware",
            "pci",
            "101",
            "--property",
            "pciDevices=1,2",
            "--property",
            "pciDevices=3",
            "--dry-run",
            "-f",
            "json",
        ],
    )
    assert pci.exit_code == 0, pci.stdout
    assert json.loads(pci.stdout)["body"] == {"pciDevices": [1, 2, 3]}


def test_generic_help_lists_settable_fields(cli_env: Path) -> None:
    """--help must show the settable body fields so users never guess keys."""
    cpu = runner.invoke(app, ["vm", "hardware", "cpu", "--help"])
    assert cpu.exit_code == 0
    assert "Settable body fields (--property):" in cpu.stdout
    flat = " ".join(cpu.stdout.split())
    assert "cpuCores (integer, required)" in flat
    # Required fields sort first; nested array of objects renders with [] and indented children.
    assert cpu.stdout.index("cpuCores") < cpu.stdout.index("cpuPinning[]")
    assert "cores (array of integer, required)" in flat

    tunable = runner.invoke(app, ["system", "tunable", "set", "--help"])
    assert tunable.exit_code == 0
    flat = " ".join(tunable.stdout.split())
    assert "name (string, required)" in flat
    assert "value (string, required)" in flat

    # Reads advertise query parameters instead of body fields or --data/--property.
    tunables = runner.invoke(app, ["system", "tunable", "list", "--help"])
    assert tunables.exit_code == 0
    assert "Query parameters (--param):" in tunables.stdout
    assert "Settable body fields" not in tunables.stdout
    assert "--property" not in tunables.stdout
    assert "--data" not in tunables.stdout


def test_generic_bare_command_shows_help(cli_env: Path) -> None:
    """A generic command with nothing supplied prints help, like bare groups."""
    bare = runner.invoke(app, ["vm", "hardware", "cpu"])
    assert bare.exit_code == 0
    assert "Usage:" in bare.stdout
    assert "Settable body fields" in bare.stdout

    # Bare body-requiring commands without path placeholders also print help.
    bare_tunable = runner.invoke(app, ["system", "tunable", "set"])
    assert bare_tunable.exit_code == 0
    assert "Usage:" in bare_tunable.stdout
    assert "Settable body fields" in bare_tunable.stdout

    # Options but no path argument is a usage error, not an API failure.
    partial = runner.invoke(app, ["vm", "hardware", "cpu", "--property", "cpuCores=4"])
    assert partial.exit_code == 2

    # Read commands without path placeholders still execute when bare.
    listed = runner.invoke(app, ["system", "pci-list", "-f", "json"])
    assert listed.exit_code == 0
    assert json.loads(listed.stdout)[0]["bus"] == 1


def test_generic_set_rejects_bad_input() -> None:
    missing_equals = runner.invoke(
        app, ["vm", "hardware", "cpu", "101", "--property", "oops", "--dry-run", "-f", "json"]
    )
    assert missing_equals.exit_code == 1

    non_object = runner.invoke(
        app,
        ["vm", "hardware", "cpu", "101", "--data", "[1, 2]", "--property", "a=1", "--dry-run"],
    )
    assert non_object.exit_code == 1


def test_every_leaf_command_renders_help() -> None:
    """Every registered command must render help (catches wiring mistakes)."""
    from click import Context
    from typer.main import get_command

    root = get_command(app)
    leafs: list[tuple[tuple[str, ...], object]] = []

    def walk(command: object, prefix: tuple[str, ...]) -> None:
        children = getattr(command, "commands", None)
        if children:
            for name, child in children.items():
                if getattr(child, "hidden", False):
                    continue
                walk(child, (*prefix, name))
        else:
            leafs.append((prefix, command))

    walk(root, ())
    assert len(leafs) > 300
    for path, command in leafs:
        if path[0] == "server":
            continue
        text = command.get_help(Context(command))  # type: ignore[union-attr]
        assert "Usage:" in text, f"help output missing Usage for: {' '.join(path)}"


def test_power_and_snapshot_machine_output_is_pure_json(cli_env: Path) -> None:
    """Machine output must parse as JSON with no prose lines mixed in."""
    cases = (
        ["vm", "start", "web", "-f", "json"],
        ["jail", "start", "app", "-f", "json"],
        ["vm", "snapshot", "create", "web", "--name", "s1", "-f", "json"],
        ["jail", "snapshot", "create", "app", "--name", "s1", "-f", "json"],
        ["vm", "rename", "web", "web2", "-f", "json"],
        ["jail", "rename", "app", "app2", "-f", "json"],
        ["vm", "template", "capture", "web", "--name", "t1", "-f", "json"],
        ["backup", "job", "restore", "3", "--snapshot", "snap1", "-f", "json"],
    )
    for args in cases:
        result = runner.invoke(app, args)
        assert result.exit_code == 0, (args, result.stdout)
        json.loads(result.stdout)


def test_generic_read_selection(cli_env: Path) -> None:
    projected = runner.invoke(app, ["system", "pci-list", "-c", "bus", "-f", "json"])
    assert projected.exit_code == 0
    assert json.loads(projected.stdout) == [{"bus": 1}]

    filtered = runner.invoke(app, ["system", "pci-list", "--filter", "bus=9", "-f", "json"])
    assert filtered.exit_code == 0
    assert json.loads(filtered.stdout) == []


def test_login_password_has_no_short_flag() -> None:
    out = runner.invoke(app, ["login", "--help"]).stdout
    assert "--password" in out
    assert "-p," not in out


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

    destructive = runner.invoke(app, ["system", "note", "delete", "--help"])
    assert destructive.exit_code == 0
    assert "--yes" in destructive.stdout


def test_note_show_commands(cli_env: Path) -> None:
    show = runner.invoke(app, ["cluster", "note", "show", "1", "-f", "json"])
    assert show.exit_code == 0
    assert json.loads(show.stdout)["content"] == "Disk replacement 22:00"

    missing = runner.invoke(app, ["cluster", "note", "show", "9", "-f", "json"])
    assert missing.exit_code == 1

    host = runner.invoke(app, ["system", "note", "show", "1", "-f", "json"])
    assert host.exit_code == 0
    assert json.loads(host.stdout)["title"] == "Maintenance"

    host_missing = runner.invoke(app, ["system", "note", "show", "9", "-f", "json"])
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


def test_console_frame_timeout_breaks_instead_of_hanging() -> None:
    import socket as socket_mod

    from sylve_cli.console_ws import _enable_keepalive, decode_server_frame

    class _StalledSock:
        def recv(self, n: int) -> bytes:
            raise TimeoutError("timed out")

    # A stalled connection surfaces as a catchable timeout (the attach loop
    # turns it into "back to select"), not an eternal block...
    with pytest.raises(socket_mod.timeout):
        decode_server_frame(_StalledSock(), bytearray())

    # ...and bytes of a partial frame already read are preserved for resume.
    buf = bytearray(b"\x82")
    with pytest.raises(socket_mod.timeout):
        decode_server_frame(_StalledSock(), buf)
    assert buf == bytearray(b"\x82")

    # Keepalive setup is best-effort and must never raise on odd platforms.
    seen: list[tuple[int, int, int]] = []

    class _OptSock:
        def setsockopt(self, level: int, opt: int, value: int) -> None:
            seen.append((level, opt, value))

    _enable_keepalive(_OptSock())
    assert any(opt == socket_mod.SO_KEEPALIVE for _, opt, _ in seen)


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
    assert "options serial-console" in str(err_409)

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


def test_container_and_directory_services_dry_run(cli_env: Path) -> None:
    """New container, directory-services, L3, and scrub-schedule commands build typed payloads."""
    cases = (
        (
            [
                "container",
                "create",
                "--property",
                "name=web",
                "--property",
                "ocId=301",
                "--property",
                "pool=zroot",
            ],
            "POST",
            "/container",
            {"name": "web", "ocId": 301, "pool": "zroot"},
        ),
        (
            ["container", "start", "301"],
            "POST",
            "/container/301/actions/start",
            None,
        ),
        (
            ["directory-services", "ad", "config", "set", "--property", "domain=example.test"],
            "PUT",
            "/directory-services/active-directory",
            {"domain": "example.test"},
        ),
        (
            [
                "network",
                "interface",
                "l3-set",
                "em0",
                "--property",
                "addresses=address=10.0.0.10/24",
            ],
            "PUT",
            "/network/interface/em0/l3",
            {"addresses": [{"address": "10.0.0.10/24"}]},
        ),
        (
            [
                "zfs",
                "pool",
                "scrub-schedule-create",
                "--property",
                "poolGuid=g1",
                "--property",
                "cronExpr=0 2 * * 0",
            ],
            "POST",
            "/zfs/pools/scrub/schedules",
            {"poolGuid": "g1", "cronExpr": "0 2 * * 0"},
        ),
    )
    for args, method, path, body in cases:
        res = runner.invoke(app, [*args, "--dry-run", "-f", "json"])
        assert res.exit_code == 0, (args, res.stdout)
        payload = json.loads(res.stdout)
        assert payload["method"] == method
        assert payload["path"] == path
        assert payload["body"] == body
