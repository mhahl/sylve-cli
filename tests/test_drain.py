"""Tests for cluster node maintenance drain planning and execution."""

from __future__ import annotations

import httpx

from sylve_cli.commands.node import build_node_drain_plan
from tests.test_client_and_routing import _make_mock_client


def test_build_drain_plan_with_ha_and_standalone_guests() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/cluster/nodes":
            return httpx.Response(
                200,
                json={
                    "status": "success",
                    "data": [
                        {
                            "nodeUUID": "uuid-1",
                            "hostname": "node1.lan",
                            "status": "online",
                            "cpuUsage": 50.0,
                            "memoryUsage": 60.0,
                            "guestIDs": [101, 102, 201],
                        },
                        {
                            "nodeUUID": "uuid-2",
                            "hostname": "node2.lan",
                            "status": "online",
                            "cpuUsage": 10.0,
                            "memoryUsage": 20.0,
                            "guestIDs": [],
                        },
                        {
                            "nodeUUID": "uuid-3",
                            "hostname": "node3.lan",
                            "status": "online",
                            "cpuUsage": 75.0,
                            "memoryUsage": 80.0,
                            "guestIDs": [301],
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
                            "vms": [
                                {"rid": 101, "name": "ha-db-vm", "state": 1},
                                {"rid": 102, "name": "standalone-web-vm", "state": 1},
                            ],
                            "jails": [
                                {"ctId": 201, "name": "app-jail", "state": "ACTIVE"},
                            ],
                        },
                        {"nodeUUID": "uuid-2", "hostname": "node2.lan", "vms": [], "jails": []},
                        {"nodeUUID": "uuid-3", "hostname": "node3.lan", "vms": [], "jails": []},
                    ],
                },
            )
        if path == "/api/cluster/replication/policies":
            return httpx.Response(
                200,
                json={
                    "status": "success",
                    "data": [
                        {
                            "id": 7,
                            "name": "ha-db-policy",
                            "enabled": True,
                            "guestType": "vm",
                            "guestId": 101,
                            "activeNodeId": "uuid-1",
                            "targets": [
                                {"nodeId": "uuid-3", "weight": 100, "ready": True},
                            ],
                        }
                    ],
                },
            )
        if path == "/api/cluster/backups/jobs":
            return httpx.Response(
                200,
                json={
                    "status": "success",
                    "data": [
                        {"id": 3, "name": "nightly-zroot", "runnerNodeId": "uuid-1"},
                    ],
                },
            )
        if path == "/api/tasks/migration/validate":
            return httpx.Response(
                200,
                json={"status": "success", "data": {"valid": True}},
            )
        return httpx.Response(404, json={"status": "error", "error": "not_found"})

    client = _make_mock_client(handler)
    src_uuid, src_host, plan, pinned_jobs = build_node_drain_plan(
        client, source_node="node1.lan"
    )

    assert src_uuid == "uuid-1"
    assert src_host == "node1.lan"
    assert len(pinned_jobs) == 1
    assert len(plan) == 3

    # VM 101 is HA-protected -> ha-failover to node3.lan (policy target)
    item_ha = next(p for p in plan if p.guest_id == 101)
    assert item_ha.action == "ha-failover"
    assert item_ha.policy_id == 7
    assert item_ha.target_node == "node3.lan"

    # VM 102 & Jail 201 are standalone -> migrated to least-loaded node2.lan
    item_vm = next(p for p in plan if p.guest_id == 102)
    assert item_vm.action == "migrate"
    assert item_vm.target_node == "node2.lan"

    item_jail = next(p for p in plan if p.guest_id == 201)
    assert item_jail.action == "migrate"
    assert item_jail.target_node == "node2.lan"


def test_build_drain_plan_stop_only_and_fallback_stop() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/cluster/nodes":
            return httpx.Response(
                200,
                json={
                    "status": "success",
                    "data": [
                        {"nodeUUID": "uuid-1", "hostname": "node1.lan", "status": "online"},
                        {"nodeUUID": "uuid-2", "hostname": "node2.lan", "status": "online"},
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
                            "vms": [{"rid": 105, "name": "local-pci-vm", "state": 1}],
                            "jails": [{"ctId": 205, "name": "stopped-jail", "state": "INACTIVE"}],
                        }
                    ],
                },
            )
        if path in ("/api/cluster/replication/policies", "/api/cluster/backups/jobs"):
            return httpx.Response(200, json={"status": "success", "data": []})
        if path == "/api/tasks/migration/validate":
            return httpx.Response(
                400,
                json={"status": "error", "error": "pci_passthrough_attached", "message": "PCI passthrough prevents migration"},
            )
        return httpx.Response(404)

    client = _make_mock_client(handler)

    # Without fallback_stop, failed migration preflight marks guest as 'blocked'
    _, _, plan_blocked, _ = build_node_drain_plan(client, source_node="node1.lan", fallback_stop=False)
    assert plan_blocked[0].action == "blocked"
    assert "PCI passthrough" in plan_blocked[0].reason

    # With fallback_stop=True, running VM falls back to 'shutdown' and stopped jail is 'skip'
    _, _, plan_fb, _ = build_node_drain_plan(client, source_node="node1.lan", fallback_stop=True)
    assert plan_fb[0].action == "shutdown"
    assert plan_fb[1].action == "skip"

    # With stop_only=True
    _, _, plan_stop, _ = build_node_drain_plan(client, source_node="node1.lan", stop_only=True)
    assert plan_stop[0].action == "shutdown"
    assert plan_stop[1].action == "skip"
