"""Opt-in live mutation tests for Jails: create, start, stop, migrate, delete.

Jails need an existing pkgbase bootstrap and a network switch, so this is a
separate opt-in from VM mutation. Every jail is named zclitest-* and deleted in
fixture teardown (with --delete-rootfs) even when a check fails. Because a jail
can migrate to another node, cleanup searches every online node.
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


def _find_jail(run_cli: Any, name: str, nodes: list[str] | None = None) -> dict[str, Any] | None:
    """Find a jail by name.

    Cluster-wide `jail list` can miss jails on other nodes when aggregation
    falls back to a single node, so default to scanning every online node.
    """
    for node in nodes or _online_nodes(run_cli) or [None]:
        args = (
            ["jail", "list", "-f", "json"]
            if node is None
            else ["jail", "list", "-n", node, "-f", "json"]
        )
        try:
            data = _json(run_cli(args))
        except AssertionError:
            continue
        for jail in data:
            if isinstance(jail, dict) and jail.get("name") == name:
                return jail
    return None


def _online_nodes(run_cli: Any) -> list[str]:
    """Return all cluster node hostnames, used to locate a migrated jail."""
    try:
        data = _json(run_cli(["node", "list", "-f", "json"]))
    except AssertionError:
        return []
    return [
        str(n.get("hostname") or n.get("node") or "").strip()
        for n in data
        if isinstance(n, dict) and (n.get("hostname") or n.get("node"))
    ]


def _find_jail_with_retry(
    run_cli: Any, name: str, nodes: list[str] | None = None, tries: int = 6
) -> dict[str, Any] | None:
    jail = None
    for _ in range(tries):
        jail = _find_jail(run_cli, name, nodes=nodes)
        if jail is not None:
            return jail
        time.sleep(2)
    return None


def _delete_jail(run_cli: Any, name: str, node: str, nodes: list[str] | None = None) -> list[Any]:
    """Stop and delete a jail (with its rootfs), returning failures (empty when clean)."""
    failures: list[Any] = []
    run_cli(["jail", "stop", name, "-n", node])
    result = run_cli(["jail", "delete", name, "-n", node, "-y", "--delete-rootfs", "--delete-macs"])
    if result.exit_code != 0:
        failures.append(result)
    for _ in range(6):
        if _find_jail(run_cli, name, nodes=nodes) is None:
            return failures
        time.sleep(2)
    failures.append(run_cli(["jail", "list", "-f", "json"]))
    return failures


@pytest.fixture()
def throwaway_jail(jail_target: dict[str, str], run_cli: Any) -> Iterator[dict[str, Any]]:
    """Create a bootable jail and delete it (with rootfs) on teardown."""
    name = f"{PREFIX}jail-{uuid.uuid4().hex[:8]}"
    # A high, random CTID keeps clear of existing guests (e.g. test-jail = 100).
    ctid = 8000 + uuid.uuid4().int % 1000
    body = {
        "name": name,
        "ctId": ctid,
        "pool": jail_target["pool"],
        "type": "freebsd",
        "bootstrapName": jail_target["bootstrap"],
        "switchName": jail_target["switch"],
        "dhcp": True,
    }
    created = _json(
        run_cli(
            ["jail", "create", "--node", jail_target["node"], "-d", json.dumps(body), "-f", "json"]
        )
    )
    try:
        yield {"name": name, "ctId": created.get("ctId", ctid), **jail_target}
    finally:
        nodes = _online_nodes(run_cli) or [jail_target["node"]]
        jail = _find_jail_with_retry(run_cli, name, nodes=nodes)
        node = (jail.get("node") if jail else None) or jail_target["node"]
        cleanup_failures = _delete_jail(run_cli, name, node, nodes=nodes)
        assert not cleanup_failures, (
            f"failed to clean up {name}: {[r.stdout + r.stderr for r in cleanup_failures]}"
        )


def test_created_jail_is_visible_with_its_requested_name(
    throwaway_jail: dict[str, Any], run_cli: Any
) -> None:
    """A created jail must appear in the list under its name and CTID."""
    jail = _find_jail(run_cli, throwaway_jail["name"])
    assert jail is not None, "created jail not visible in jail list"
    assert jail.get("name") == throwaway_jail["name"]
    assert str(jail.get("ctId")) == str(throwaway_jail["ctId"])


def test_jail_starts_and_stops(throwaway_jail: dict[str, Any], run_cli: Any) -> None:
    """A bootable jail reaches ACTIVE on start and stops cleanly."""
    name = throwaway_jail["name"]
    node = throwaway_jail["node"]

    result = run_cli(["jail", "start", name, "-n", node, "-w"])
    assert result.exit_code == 0, (result.stdout, result.stderr)
    jail = _find_jail(run_cli, name)
    assert jail is not None
    assert str(jail.get("state")).upper() == "ACTIVE"

    result = run_cli(["jail", "stop", name, "-n", node])
    assert result.exit_code == 0, (result.stdout, result.stderr)


def test_jail_migrates_to_another_node(
    throwaway_jail: dict[str, Any], migrate_target: dict[str, str], run_cli: Any
) -> None:
    """A running jail moved with jail migrate ends up on the target node."""
    name = throwaway_jail["name"]
    source = throwaway_jail["node"]
    target = migrate_target["node"]
    nodes = [source, target]

    result = run_cli(["jail", "start", name, "-n", source, "-w"])
    assert result.exit_code == 0, (result.stdout, result.stderr)

    check = run_cli(["jail", "migrate", name, "-t", target, "-n", source, "--validate-only"])
    assert check.exit_code == 0, (check.stdout, check.stderr)

    result = run_cli(["jail", "migrate", name, "-t", target, "-n", source, "-w"])
    assert result.exit_code == 0, (result.stdout, result.stderr)

    jail = _find_jail_with_retry(run_cli, name, nodes=nodes)
    assert jail is not None, "jail missing after migration"
    assert str(jail.get("node", "")).lower() == target.lower(), (
        f"jail did not land on target {target}; got {jail.get('node')}"
    )
