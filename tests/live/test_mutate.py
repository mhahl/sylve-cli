"""Opt-in live mutation tests: create, verify, and delete throwaway resources.

These only run with SYLVE_LIVE_MUTATE=1 plus an explicit SYLVE_NODE and
SYLVE_LIVE_POOL, and every resource is deleted in fixture teardown even when a
check fails. Resources are always named zclitest-* so existing objects are
never touched.
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Iterator
from typing import Any

import pytest

pytestmark = pytest.mark.live_mutate

PREFIX = "zclitest-"


def _json(result: Any) -> Any:
    assert result.exit_code == 0, (
        f"command failed: stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    return json.loads(result.stdout)


def _find_vm(run_cli: Any, name: str, nodes: list[str] | None = None) -> dict[str, Any] | None:
    """Find a VM by name, checking the given nodes (or cluster-wide) explicitly.

    Cluster-wide `vm list` can miss VMs on other nodes when /cluster/resources
    falls back to a single-node result, so check each online node directly.
    """
    candidates = nodes or [None]  # empty/None -> cluster-wide call
    for node in candidates:
        args = (
            ["vm", "list", "-f", "json"]
            if node is None
            else ["vm", "list", "-n", node, "-f", "json"]
        )
        try:
            data = _json(run_cli(args))
        except AssertionError:
            continue
        for vm in data:
            if isinstance(vm, dict) and vm.get("name") == name:
                return vm
    return None


def _online_nodes(run_cli: Any) -> list[str]:
    """Return all cluster node hostnames, used to locate a migrated VM."""
    try:
        data = _json(run_cli(["node", "list", "-f", "json"]))
    except AssertionError:
        return []
    return [
        str(n.get("hostname") or n.get("node") or "").strip()
        for n in data
        if isinstance(n, dict) and (n.get("hostname") or n.get("node"))
    ]


def _find_vm_with_retry(
    run_cli: Any, name: str, nodes: list[str] | None = None, tries: int = 6
) -> dict[str, Any] | None:
    """Poll for the VM, checking the given nodes (or cluster-wide); migration is eventually consistent."""
    vm = None
    for _ in range(tries):
        vm = _find_vm(run_cli, name, nodes=nodes)
        if vm is not None:
            return vm
        time.sleep(2)
    return None


def _delete_vm(run_cli: Any, name: str, node: str, nodes: list[str] | None = None) -> list[Any]:
    """Stop and delete a VM, returning failing result objects (empty when clean)."""
    failures: list[Any] = []
    run_cli(["vm", "stop", name, "-n", node])
    for _ in range(6):
        stopped = _find_vm(run_cli, name, nodes=nodes)
        if stopped is None:
            return failures  # already gone
        # don't delete a still-RUNNING VM too eagerly; stop is async
        if str(stopped.get("state", "")).upper() in ("SHUTOFF", "STOPPED", "INACTIVE", "-"):
            break
        time.sleep(2)
    result = run_cli(
        [
            "vm",
            "delete",
            name,
            "-n",
            node,
            "-y",
            "--delete-volumes",
            "--delete-raw-disks",
            "--delete-macs",
        ]
    )
    if result.exit_code != 0:
        failures.append(result)
    for _ in range(6):
        if _find_vm(run_cli, name, nodes=nodes) is None:
            return failures
        time.sleep(2)
    failures.append(run_cli(["vm", "list", "-f", "json"]))
    return failures


@pytest.fixture()
def throwaway_vm(mutate_target: dict[str, str], run_cli: Any) -> Iterator[dict[str, Any]]:
    """Create a small VM and delete it (with volumes) on teardown."""
    name = f"{PREFIX}vm-{uuid.uuid4().hex[:8]}"
    created = _json(
        run_cli(
            [
                "vm",
                "create",
                name,
                "-n",
                mutate_target["node"],
                "--pool",
                mutate_target["pool"],
                "--disk-size",
                "1G",
                "--memory",
                "256M",
                "--cpu",
                "1",
                "--no-vnc",
                "--yes",
                "-f",
                "json",
            ]
        )
    )
    try:
        yield {"name": name, "rid": created.get("rid"), **mutate_target}
    finally:
        # A migrated VM can land on any cluster node; search them all.
        nodes = _online_nodes(run_cli) or [mutate_target["node"]]
        vm = _find_vm_with_retry(run_cli, name, nodes=nodes)
        node = (vm.get("node") if vm else None) or mutate_target["node"]
        cleanup_failures = _delete_vm(run_cli, name, node, nodes=nodes)
        # Never allow a silently-orphaned VM to stay behind on a live cluster.
        assert not cleanup_failures, (
            f"failed to clean up {name}: {[r.stdout + r.stderr for r in cleanup_failures]}"
        )


def test_guest_lifecycle_migrates_to_another_node(
    throwaway_vm: dict[str, Any], migrate_target: dict[str, str], run_cli: Any
) -> None:
    """A running VM moved with vm migrate ends up on the target node."""
    name = throwaway_vm["name"]
    source = throwaway_vm["node"]
    target = migrate_target["node"]
    nodes = [source, target]

    result = run_cli(["vm", "start", name, "-n", source, "-w"])
    assert result.exit_code == 0, (result.stdout, result.stderr)

    # Validate preflight, which must allow the migration.
    check = run_cli(["vm", "migrate", name, "-t", target, "-n", source, "--validate-only"])
    assert check.exit_code == 0, (check.stdout, check.stderr)

    result = run_cli(["vm", "migrate", name, "-t", target, "-n", source, "-w"])
    assert result.exit_code == 0, (result.stdout, result.stderr)

    vm = _find_vm_with_retry(run_cli, name, nodes=nodes)
    assert vm is not None, "VM missing after migration"
    assert str(vm.get("node", "")).lower() == target.lower(), (
        f"VM did not land on target {target}; got {vm.get('node')}"
    )


def test_created_vm_is_visible_with_its_requested_name(
    throwaway_vm: dict[str, Any], run_cli: Any
) -> None:
    """A created VM must appear in the list under its name and requested RID."""
    vm = _find_vm(run_cli, throwaway_vm["name"])
    assert vm is not None, "created VM not visible in vm list"
    assert vm.get("name") == throwaway_vm["name"]
    assert str(vm.get("rid")) == str(throwaway_vm["rid"])


def test_created_vm_can_snapshot_and_be_deleted(throwaway_vm: dict[str, Any], run_cli: Any) -> None:
    """A created VM accepts a snapshot that then disappears when deleted."""
    name = throwaway_vm["name"]
    node = throwaway_vm["node"]
    snap = f"{PREFIX}snap"

    _apply = run_cli(["vm", "snapshot", "create", name, "-m", snap, "-n", node])
    assert _apply.exit_code == 0, (_apply.stdout, _apply.stderr)
    listed = _json(run_cli(["vm", "snapshot", "list", name, "-n", node, "-f", "json"]))
    assert any(snap in json.dumps(item) for item in listed), "snapshot not listed after create"

    snap_id = None
    for item in listed:
        if snap in json.dumps(item):
            snap_id = item.get("id") or item.get("name")
            break
    assert snap_id is not None, "snapshot has no id/name to delete"

    _apply = run_cli(["vm", "snapshot", "delete", name, str(snap_id), "-n", node])
    assert _apply.exit_code == 0, (_apply.stdout, _apply.stderr)
    remaining = _json(run_cli(["vm", "snapshot", "list", name, "-n", node, "-f", "json"]))
    assert not any(snap in json.dumps(item) for item in remaining), "snapshot survived delete"


def test_vm_lifecycle_survives_start_and_stop(throwaway_vm: dict[str, Any], run_cli: Any) -> None:
    """A diskless VM starts to RUNNING and stops without error."""
    name = throwaway_vm["name"]
    node = throwaway_vm["node"]

    result = run_cli(["vm", "start", name, "-n", node, "-w"])
    assert result.exit_code == 0, (result.stdout, result.stderr)
    vm = _find_vm(run_cli, name)
    assert vm is not None
    assert str(vm.get("state")).upper() == "RUNNING"

    result = run_cli(["vm", "stop", name, "-n", node])
    assert result.exit_code == 0, (result.stdout, result.stderr)
