"""End-to-end CLI command tests using Typer CliRunner and mocked Sylve API responses."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
import pytest
from typer.testing import CliRunner

from sylve_cli.config import ContextConfig, SylveConfig, extract_token_expiry, save_config
from sylve_cli.main import app
from tests.test_config import make_test_jwt

runner = CliRunner()


@pytest.fixture()
def configured_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    cfg_path = tmp_path / "config.yaml"
    tok = make_test_jwt(datetime.now(timezone.utc) + timedelta(hours=12), username="admin")
    cfg = SylveConfig(
        current_context="test-cluster",
        contexts={
            "test-cluster": ContextConfig(
                server="https://sylve.lan:8181",
                username="admin",
                auth_type="sylve",
                node_id="uuid-1",
                hostname="node1.lan",
                token=tok,
                expires_at=extract_token_expiry(tok),
                verify_ssl=False,
            )
        },
    )
    save_config(cfg, cfg_path)
    monkeypatch.setenv("SYLVE_CONFIG", str(cfg_path))

    def mock_handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        method = request.method

        if path == "/api/auth/login" and method == "POST":
            new_tok = make_test_jwt(datetime.now(timezone.utc) + timedelta(days=7), username="admin")
            return httpx.Response(
                200,
                json={
                    "status": "success",
                    "data": {
                        "token": new_tok,
                        "hostname": "node1.lan",
                        "nodeId": "uuid-1",
                    },
                },
            )
        if path == "/api/auth/logout" and method == "POST":
            return httpx.Response(200, json={"status": "success", "data": None})

        if path == "/api/cluster":
            return httpx.Response(
                200,
                json={
                    "status": "success",
                    "data": {
                        "cluster": {"enabled": True, "raftIP": "10.0.0.1", "raftPort": 7000},
                        "nodeId": "uuid-1",
                        "leaderId": "uuid-1",
                        "leaderAddress": "10.0.0.1:7000",
                        "partial": False,
                        "nodes": [
                            {"id": "uuid-1", "address": "10.0.0.1:7000", "isLeader": True, "suffrage": "Voter", "guestIDs": [101, 201]},
                            {"id": "uuid-2", "address": "10.0.0.2:7000", "isLeader": False, "suffrage": "Voter", "guestIDs": [102]},
                        ],
                    },
                },
            )
        if path == "/api/cluster/nodes":
            return httpx.Response(
                200,
                json={
                    "status": "success",
                    "data": [
                        {
                            "nodeUUID": "uuid-1",
                            "hostname": "node1.lan",
                            "api": "10.0.0.1:8181",
                            "status": "online",
                            "cpu": 16,
                            "cpuUsage": 12.5,
                            "memory": 34359738368,
                            "memoryUsage": 35.0,
                            "disk": 1099511627776,
                            "diskUsage": 22.0,
                            "guestIDs": [101, 201],
                            "sylveVersion": "0.3.1",
                        },
                        {
                            "nodeUUID": "uuid-2",
                            "hostname": "node2.lan",
                            "api": "10.0.0.2:8181",
                            "status": "online",
                            "cpu": 16,
                            "cpuUsage": 8.0,
                            "memory": 34359738368,
                            "memoryUsage": 18.0,
                            "disk": 1099511627776,
                            "diskUsage": 15.0,
                            "guestIDs": [102],
                            "sylveVersion": "0.3.1",
                        },
                    ],
                },
            )
        if path == "/api/cluster/resources":
            return httpx.Response(
                200,
                json={
                    "status": "success",
                    "data": [
                        {
                            "nodeUUID": "uuid-1",
                            "hostname": "node1.lan",
                            "vms": [{"rid": 101, "name": "freebsd-vm", "state": 1, "vncPort": 5901}],
                            "jails": [{"ctId": 201, "name": "nginx-jail", "state": "ACTIVE", "type": "freebsd", "cores": 2, "memory": 2147483648}],
                        },
                        {
                            "nodeUUID": "uuid-2",
                            "hostname": "node2.lan",
                            "vms": [{"rid": 102, "name": "postgres-vm", "state": 5, "vncPort": 5902}],
                            "jails": [],
                        },
                    ],
                },
            )
        if path.startswith("/api/vm/") and "/actions/" in path:
            return httpx.Response(
                200,
                json={"status": "success", "data": {"rid": 101, "action": "start", "outcome": "queued", "taskId": 55}},
            )
        if path == "/api/vm/101/migrations":
            return httpx.Response(
                200,
                json={"status": "success", "data": {"guestId": 101, "outcome": "queued", "taskId": 77}},
            )
        if path.startswith("/api/tasks/lifecycle/"):
            return httpx.Response(
                200,
                json={"status": "success", "data": {"id": 55, "status": "completed", "action": "start", "guestType": "vm", "guestId": 101}},
            )
        if path == "/api/tasks/migration/validate":
            return httpx.Response(
                200,
                json={"status": "success", "data": {"valid": True}},
            )
        if path.startswith("/api/jail/") and "/actions/" in path:
            return httpx.Response(
                200,
                json={"status": "success", "data": {"ctId": 201, "action": "stop", "outcome": "queued", "taskId": 56}},
            )
        if path == "/api/jail/201/migrations":
            return httpx.Response(
                200,
                json={"status": "success", "data": {"guestId": 201, "outcome": "queued", "taskId": 78}},
            )
        if path == "/api/network/switch":
            return httpx.Response(
                200,
                json={
                    "status": "success",
                    "data": {
                        "standard": [{"id": 1, "name": "wan0", "bridgeName": "vm-wan0", "vlan": 0, "vlanFiltering": False, "dhcp": True, "ports": [{"name": "em0"}]}],
                        "manual": [],
                    },
                },
            )
        if path == "/api/utilities/downloads":
            return httpx.Response(
                200,
                json={
                    "status": "success",
                    "data": [
                        {
                            "id": 1,
                            "uuid": "dl-uuid-1",
                            "name": "FreeBSD-14.2-RELEASE-amd64.iso",
                            "type": "http",
                            "uType": "uncategorized",
                            "storagePool": "zroot",
                            "size": 1073741824,
                            "progress": 100,
                            "status": "completed",
                        }
                    ],
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
                            "pool_guid": "123456789",
                            "state": "ONLINE",
                            "size": 107374182400,
                            "allocated": 21474836480,
                            "free": 85899345920,
                            "fragmentation": 4.0,
                            "dedup_ratio": 1.0,
                        }
                    ],
                },
            )
        if path in ("/api/cluster/replication/policies", "/api/cluster/backups/jobs", "/api/cluster/backups/targets"):
            return httpx.Response(200, json={"status": "success", "data": []})
        return httpx.Response(200, json={"status": "success", "data": {}})

    orig_init = httpx.Client.__init__

    def patched_init(self: Any, *args: Any, **kwargs: Any) -> None:
        kwargs["transport"] = httpx.MockTransport(mock_handler)
        orig_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.Client, "__init__", patched_init)
    return cfg_path


def test_cli_whoami_and_config(configured_env: Path) -> None:
    res = runner.invoke(app, ["whoami", "-f", "json"])
    assert res.exit_code == 0
    data = json.loads(res.stdout)
    assert data["username"] == "admin"
    assert data["context"] == "test-cluster"
    assert "VALID" in data["token_status"]

    res_ctx = runner.invoke(app, ["config", "get-contexts", "-f", "json"])
    assert res_ctx.exit_code == 0
    ctxs = json.loads(res_ctx.stdout)
    assert len(ctxs) == 1
    assert ctxs[0]["name"] == "test-cluster"


def test_cli_cluster_and_nodes(configured_env: Path) -> None:
    res_cluster = runner.invoke(app, ["cluster", "show", "-f", "json"])
    assert res_cluster.exit_code == 0
    cdata = json.loads(res_cluster.stdout)
    assert cdata["enabled"] is True
    assert cdata["nodes_online"] == "2/2"

    res_nodes = runner.invoke(app, ["node", "list", "-f", "json"])
    assert res_nodes.exit_code == 0
    ndata = json.loads(res_nodes.stdout)
    assert len(ndata) == 2
    assert {n["hostname"] for n in ndata} == {"node1.lan", "node2.lan"}

    res_compact = runner.invoke(app, ["node", "list"])
    assert res_compact.exit_code == 0
    assert "Node UUID" not in res_compact.stdout

    res_long = runner.invoke(app, ["--max-width", "200", "node", "list", "--long"])
    assert res_long.exit_code == 0
    assert "Node UUID" in res_long.stdout

    res_width = runner.invoke(app, ["--max-width", "60", "node", "list"])
    assert res_width.exit_code == 0
    assert "Hostname" in res_width.stdout


def test_cli_vm_and_jail_operations(configured_env: Path) -> None:
    res_vms = runner.invoke(app, ["vm", "list", "-f", "json"])
    assert res_vms.exit_code == 0
    vms = json.loads(res_vms.stdout)
    assert len(vms) == 2
    assert vms[0]["name"] == "freebsd-vm"
    assert vms[0]["state"] == "RUNNING"

    # Test the legacy 'server' alias as well
    res_srv = runner.invoke(app, ["server", "list", "-f", "value", "-c", "rid", "-c", "name"])
    assert res_srv.exit_code == 0
    assert "101 freebsd-vm" in res_srv.stdout

    # Start VM by name with --wait
    res_start = runner.invoke(app, ["vm", "start", "postgres-vm", "--wait"])
    assert res_start.exit_code == 0
    assert "start completed" in res_start.stdout

    # List and stop Jail
    res_jails = runner.invoke(app, ["jail", "list", "-f", "json"])
    assert res_jails.exit_code == 0
    jails = json.loads(res_jails.stdout)
    assert len(jails) == 1
    assert jails[0]["ctId"] == 201

    res_jstop = runner.invoke(app, ["jail", "stop", "nginx-jail", "--wait"])
    assert res_jstop.exit_code == 0
    assert "stop completed" in res_jstop.stdout


def test_cli_node_drain_execution(configured_env: Path) -> None:
    res_dry = runner.invoke(app, ["node", "drain", "node1.lan", "--dry-run", "-f", "json"])
    assert res_dry.exit_code == 0
    plan = json.loads(res_dry.stdout)
    assert len(plan) == 2
    assert all(p["action"] == "migrate" for p in plan)
    assert all(p["target_node"] == "node2.lan" for p in plan)

    res_exec = runner.invoke(app, ["node", "drain", "node1.lan", "--yes", "-f", "json"])
    assert res_exec.exit_code == 0
    executed = json.loads(res_exec.stdout)
    assert all(p["result"] == "migrated" for p in executed)


def test_cli_network_download_and_zfs(configured_env: Path) -> None:
    res_sw = runner.invoke(app, ["network", "switch", "list", "-f", "json"])
    assert res_sw.exit_code == 0
    switches = json.loads(res_sw.stdout)
    assert len(switches) == 2  # fanned out across 2 online nodes

    res_dl = runner.invoke(app, ["download", "list", "-f", "json"])
    assert res_dl.exit_code == 0
    dls = json.loads(res_dl.stdout)
    assert len(dls) == 2

    res_zfs = runner.invoke(app, ["zfs", "pool", "list", "-f", "json"])
    assert res_zfs.exit_code == 0
    pools = json.loads(res_zfs.stdout)
    assert len(pools) == 2
    assert pools[0]["name"] == "zroot"


def test_cli_login_and_logout(configured_env: Path) -> None:
    res_login = runner.invoke(
        app,
        ["login", "https://sylve.lan:8181", "-u", "admin", "-p", "secret123", "-k"],
    )
    assert res_login.exit_code == 0
    assert "Login successful!" in res_login.stdout

    res_logout = runner.invoke(app, ["logout"])
    assert res_logout.exit_code == 0
    assert "Logged out" in res_logout.stdout
