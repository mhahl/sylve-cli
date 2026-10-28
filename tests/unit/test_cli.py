"""Functional CLI tests with a mocked HTTP boundary."""

from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
import pytest
from typer.testing import CliRunner

from sylve_cli.config import ContextConfig, SylveConfig, save_config
from sylve_cli.main import app

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
