"""Unit tests for node drain planning."""

from __future__ import annotations

from typing import Any

import pytest

from sylve_cli.client import SylveError
from sylve_cli.commands.node import build_node_drain_plan


class StubClient:
    """Client stub with just enough behaviour for drain planning."""

    def __init__(
        self,
        *,
        policies: list[dict[str, Any]] | None = None,
        validation: dict[str, Any] | None = None,
        jobs: list[dict[str, Any]] | None = None,
    ) -> None:
        self.policies = policies or []
        self.validation = validation if validation is not None else {"valid": True}
        self.jobs = jobs or []
        self.nodes = [
            {
                "nodeUUID": "u1",
                "hostname": "node1.lan",
                "status": "online",
                "cpuUsage": 10,
                "memoryUsage": 10,
                "guestIDs": [101, 201],
            },
            {
                "nodeUUID": "u2",
                "hostname": "node2.lan",
                "status": "online",
                "cpuUsage": 20,
                "memoryUsage": 20,
                "guestIDs": [],
            },
        ]
        self.resources = [
            {
                "hostname": "node1.lan",
                "vms": [{"rid": 101, "name": "web", "state": 1}],
                "jails": [{"ctId": 201, "name": "app", "state": "STOPPED"}],
            }
        ]

    def resolve_node_uuid(self, node: str) -> tuple[str, str]:
        """Resolve one of the stub nodes."""
        mapping = {"node1.lan": ("u1", "node1.lan"), "node2.lan": ("u2", "node2.lan")}
        if node not in mapping:
            raise SylveError(f"unknown node {node}")
        return mapping[node]

    def get_cluster_nodes(self, refresh: bool = False) -> list[dict[str, Any]]:
        """Return the stub cluster nodes."""
        return self.nodes

    def get_cluster_resources(self, refresh: bool = False) -> list[dict[str, Any]]:
        """Return the stub resources."""
        return self.resources

    def get(self, path: str, **_kwargs: Any) -> Any:
        """Return canned policy, job, or validation data."""
        if path == "/cluster/replication/policies":
            return self.policies
        if path == "/cluster/backups/jobs":
            return self.jobs
        if path == "/tasks/migration/validate":
            return self.validation
        raise AssertionError(f"unexpected path {path}")


def test_drain_plan_migrates_standalone_guest() -> None:
    client = StubClient()
    _, host, plan, jobs = build_node_drain_plan(client, "node1.lan")
    assert host == "node1.lan"
    assert jobs == []
    assert plan[0].guest_type == "vm"
    assert plan[0].action == "migrate"
    assert plan[0].target_node == "node2.lan"


def test_drain_plan_uses_ha_failover() -> None:
    client = StubClient(
        policies=[
            {
                "id": 7,
                "enabled": True,
                "guestType": "vm",
                "guestId": 101,
                "sourceNodeId": "u1",
                "targets": [{"nodeId": "u2", "ready": True, "weight": 100}],
            }
        ]
    )
    _, _, plan, _ = build_node_drain_plan(client, "node1.lan")
    assert plan[0].action == "ha-failover"
    assert plan[0].policy_id == 7
    assert plan[0].target_node == "node2.lan"


def test_drain_plan_falls_back_to_stop_when_validation_fails() -> None:
    client = StubClient(validation={"valid": False, "reason": "PCI passthrough"})
    _, _, plan, _ = build_node_drain_plan(client, "node1.lan", fallback_stop=True)
    assert plan[0].action == "shutdown"
    assert "PCI passthrough" in plan[0].reason


def test_drain_plan_blocks_without_fallback() -> None:
    client = StubClient(validation={"valid": False, "reason": "PCI passthrough"})
    _, _, plan, _ = build_node_drain_plan(client, "node1.lan", fallback_stop=False)
    assert plan[0].action == "blocked"
    assert "PCI passthrough" in plan[0].reason


def test_drain_plan_stop_only() -> None:
    client = StubClient()
    _, _, plan, _ = build_node_drain_plan(client, "node1.lan", stop_only=True)
    actions = {item.guest_id: item.action for item in plan}
    assert actions[101] == "shutdown"
    assert actions[201] == "skip"


def test_drain_plan_blocks_when_no_target_exists() -> None:
    client = StubClient()
    client.nodes = [node for node in client.nodes if node["hostname"] == "node1.lan"]
    _, _, plan, _ = build_node_drain_plan(client, "node1.lan")
    assert plan[0].action == "blocked"


def test_drain_plan_rejects_same_target() -> None:
    client = StubClient()
    with pytest.raises(SylveError, match="same as the source"):
        build_node_drain_plan(client, "node1.lan", target_node="node1.lan")
