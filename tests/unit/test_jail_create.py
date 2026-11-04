"""Unit tests for typed jail creation.

These mirror the vm_create tests: file-config mapping is pure, payload
normalization resolves against a stub client, and ``--dry-run`` proves the
full CLI path without touching a server.
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
import pytest
from typer.testing import CliRunner

from sylve_cli.client import SylveError
from sylve_cli.commands.jail_create import (
    _apply_set_overrides,
    _config_to_payload,
    _normalize_payload,
)
from sylve_cli.config import ContextConfig, SylveConfig, save_config
from sylve_cli.main import app

runner = CliRunner()


class StubClient:
    """Client stub returning canned responses for the jail resolvers."""

    def __init__(self, **data: Any) -> None:
        self.data = data

    def resolve_node_hostname(self, node: str | None) -> str | None:
        return node

    def get_online_nodes(self, refresh: bool = False) -> list[dict[str, Any]]:
        return self.data.get("online_nodes", [])

    def get_cluster_nodes(self, refresh: bool = False) -> list[dict[str, Any]]:
        return self.data.get("cluster_nodes", [])

    def get_cluster_resources(self, refresh: bool = False) -> list[dict[str, Any]]:
        return self.data.get("cluster_resources", [])

    def get(self, path: str, **kwargs: Any) -> Any:
        if path == "/zfs/pools":
            return self.data.get("pools", [])
        if path == "/network/switch":
            return self.data.get("switches", {})
        if path == "/jail/bootstraps":
            return self.data.get("bootstraps", [])
        if path == "/network/object":
            return self.data.get("objects", [])
        raise AssertionError(f"unexpected path {path}")


def make_client(**data: Any) -> StubClient:
    return StubClient(**data)


def base_client(**overrides: Any) -> StubClient:
    data: dict[str, Any] = {
        "cluster_nodes": [{"guestIDs": [101]}],
        "pools": [{"name": "zroot"}],
        "switches": {"standard": [{"name": "vm-switch"}], "manual": []},
        "bootstraps": [{"name": "15-1-Base"}],
        "objects": [],
    }
    data.update(overrides)
    return make_client(**data)


# ---------------------------------------------------------------------------
# Config mapping: flat keys, snake_case aliases, and grouped sections.
# ---------------------------------------------------------------------------
def test_config_to_payload_accepts_flat_and_grouped_keys() -> None:
    cfg = {
        "name": "dns-03",
        "ctid": 203,
        "pool": "zroot",
        "memory": "2G",
        "cpu": {"cores": 2},
        "network": {"switch": "vm-switch", "dhcp": True},
        "boot": {"start_at_boot": True, "start_order": 5},
        "options": {"description": "resolver", "resource_limits": True},
    }
    payload = _config_to_payload(cfg)
    assert payload["name"] == "dns-03"
    assert payload["ctId"] == 203
    assert payload["cores"] == 2
    assert payload["memory"] == "2G"
    assert payload["switchName"] == "vm-switch"
    assert payload["dhcp"] is True
    assert payload["startAtBoot"] is True
    assert payload["startOrder"] == 5
    assert payload["description"] == "resolver"
    assert payload["resourceLimits"] is True


def test_apply_set_overrides_nests_dotted_keys() -> None:
    payload: dict[str, Any] = {"cores": 2}
    _apply_set_overrides(payload, ["memory=2147483648", "hooks.prestart.enabled=true"])
    assert payload == {"cores": 2, "memory": 2147483648, "hooks": {"prestart": {"enabled": True}}}
    with pytest.raises(SylveError, match="KEY=VALUE"):
        _apply_set_overrides(payload, ["nokey"])


# ---------------------------------------------------------------------------
# Normalization: sizes, defaults, resolution, and rejection of bad input.
# ---------------------------------------------------------------------------
def test_normalize_builds_minimal_payload_with_defaults() -> None:
    request = _normalize_payload(base_client(), "node1.lan", {"name": "dns-03", "pool": "zroot"})
    assert request["name"] == "dns-03"
    assert request["type"] == "freebsd"
    assert request["pool"] == "zroot"
    assert request["ctId"] == 102
    assert request["bootstrapName"] == "15-1-Base"
    assert "memory" not in request
    assert "switchName" not in request


def test_normalize_autoselects_only_installed_bootstrap() -> None:
    client = base_client(
        bootstraps=[
            {"name": "15-0-Base", "exists": False},
            {"name": "15-1-Base", "exists": True, "status": "completed"},
        ]
    )
    request = _normalize_payload(client, "node1.lan", {"name": "dns-03", "pool": "zroot"})
    assert request["bootstrapName"] == "15-1-Base"

    # Uninstalled bootstrap is rejected even if present in the catalog.
    with pytest.raises(SylveError, match="Available: 15-1-Base"):
        _normalize_payload(
            client, "node1.lan", {"name": "dns-03", "pool": "zroot", "bootstrapName": "15-0-Base"}
        )


def test_normalize_parses_sizes_and_resolves_names() -> None:
    request = _normalize_payload(
        base_client(),
        "node1.lan",
        {
            "name": "dns-03",
            "pool": "zroot",
            "memory": "2G",
            "cores": 2,
            "bootstrapName": "15-1-base",
            "switchName": "VM-SWITCH",
        },
    )
    assert request["memory"] == 2 * 1024**3
    assert request["cores"] == 2
    assert request["bootstrapName"] == "15-1-Base"
    assert request["switchName"] == "vm-switch"


def test_normalize_rejects_bad_input() -> None:
    client = base_client()
    with pytest.raises(SylveError, match="required"):
        _normalize_payload(client, "node1.lan", {"pool": "zroot"})
    with pytest.raises(SylveError, match="letters, numbers"):
        _normalize_payload(client, "node1.lan", {"name": "bad name!", "pool": "zroot"})
    with pytest.raises(SylveError, match="CTID"):
        _normalize_payload(client, "node1.lan", {"name": "ok", "pool": "zroot", "ctId": 10000})
    with pytest.raises(SylveError, match="freebsd.*linux"):
        _normalize_payload(client, "node1.lan", {"name": "ok", "pool": "zroot", "type": "windows"})
    with pytest.raises(SylveError, match="either --mac or --mac-object"):
        _normalize_payload(
            client,
            "node1.lan",
            {"name": "ok", "pool": "zroot", "macRaw": "aa:bb:cc:dd:ee:ff", "mac": "m1"},
        )
    with pytest.raises(SylveError, match="bootstrap"):
        _normalize_payload(
            client,
            "node1.lan",
            {"name": "ok", "pool": "zroot", "bootstrapName": "nope"},
        )


# ---------------------------------------------------------------------------
# CLI: --dry-run proves the whole path without a server write.
# ---------------------------------------------------------------------------
def _make_token() -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').decode().rstrip("=")
    payload = (
        base64.urlsafe_b64encode(
            json.dumps(
                {
                    "sub": "admin",
                    "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
                }
            ).encode()
        )
        .decode()
        .rstrip("=")
    )
    return f"{header}.{payload}.sig"


@pytest.fixture()
def jail_cli_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Temporary context plus a mock API serving pools, switches, and bootstraps."""
    config_path = tmp_path / "config.yaml"
    save_config(
        SylveConfig(
            current_context="test",
            contexts={
                "test": ContextConfig(
                    server="https://sylve.example.test",
                    username="admin",
                    token=_make_token(),
                    hostname="node1.lan",
                    verify_ssl=False,
                )
            },
        ),
        config_path,
    )
    monkeypatch.setenv("SYLVE_CONFIG", str(config_path))

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/cluster/nodes":
            return httpx.Response(
                200,
                json={
                    "status": "success",
                    "data": [
                        {
                            "nodeUUID": "u1",
                            "hostname": "node1.lan",
                            "status": "online",
                            "guestIDs": [101],
                        }
                    ],
                },
            )
        if path == "/api/cluster/resources":
            return httpx.Response(200, json={"status": "success", "data": []})
        if path == "/api/zfs/pools":
            return httpx.Response(200, json={"status": "success", "data": [{"name": "zroot"}]})
        if path == "/api/network/switch":
            return httpx.Response(
                200,
                json={
                    "status": "success",
                    "data": {"standard": [{"name": "vm-switch"}], "manual": []},
                },
            )
        if path == "/api/jail/bootstraps":
            return httpx.Response(200, json={"status": "success", "data": [{"name": "15-1-Base"}]})
        if path == "/api/network/object":
            return httpx.Response(200, json={"status": "success", "data": []})
        return httpx.Response(200, json={"status": "success", "data": {}})

    original_init = httpx.Client.__init__

    def patched_init(self: Any, *args: Any, **kwargs: Any) -> None:
        kwargs["transport"] = httpx.MockTransport(handler)
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.Client, "__init__", patched_init)
    return config_path


def test_jail_create_dry_run_from_flags(jail_cli_env: Path) -> None:
    result = runner.invoke(
        app,
        [
            "jail",
            "create",
            "dns-03",
            "--pool",
            "zroot",
            "--cores",
            "2",
            "--memory",
            "2G",
            "--switch",
            "vm-switch",
            "--dhcp",
            "--dry-run",
            "-f",
            "json",
        ],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["name"] == "dns-03"
    assert payload["pool"] == "zroot"
    assert payload["cores"] == 2
    assert payload["memory"] == 2 * 1024**3
    assert payload["switchName"] == "vm-switch"
    assert payload["dhcp"] is True


def test_jail_create_file_and_flags_merge(jail_cli_env: Path, tmp_path: Path) -> None:
    cfg_file = tmp_path / "jail.yaml"
    cfg_file.write_text(
        "name: dns-03\npool: zroot\ntype: freebsd\n"
        "cpu:\n  cores: 2\n  memory: 2G\n"
        "network:\n  switch: vm-switch\n",
        encoding="utf-8",
    )
    result = runner.invoke(
        app,
        ["jail", "create", "--file", str(cfg_file), "--memory", "4G", "--dry-run", "-f", "json"],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["cores"] == 2
    assert payload["memory"] == 4 * 1024**3
    assert payload["switchName"] == "vm-switch"


def test_jail_create_rejects_invalid_type(jail_cli_env: Path) -> None:
    result = runner.invoke(app, ["jail", "create", "ok", "--pool", "zroot", "--type", "windows"])
    assert result.exit_code == 1
