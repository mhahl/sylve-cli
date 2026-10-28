"""Live command coverage and OpenAPI contract checks."""

from __future__ import annotations

import json
from typing import Any

import pytest
from click import Context
from typer.main import get_command

from sylve_cli.main import app

pytestmark = pytest.mark.live

READ_CASES: list[tuple[tuple[str, ...], tuple[str, ...]]] = [
    (("whoami", "-f", "json"), ()),
    (("config", "view", "-f", "json"), ()),
    (("config", "get-contexts", "-f", "json"), ()),
    (("cluster", "show", "-f", "json"), ()),
    (("cluster", "resources", "-f", "json"), ()),
    (("cluster", "note", "list", "-f", "json"), ()),
    (("cluster", "note", "show", "$note", "-f", "json"), ("note",)),
    (("node", "list", "-f", "json"), ()),
    (("node", "drain", "$node", "--dry-run", "-f", "json"), ("node",)),
    (("node", "show", "-f", "json"), ()),
    (("node", "audit-logs", "-f", "json"), ()),
    (("node", "cpu-history", "-f", "json"), ()),
    (("node", "ram-history", "-f", "json"), ()),
    (("node", "swap-history", "-f", "json"), ()),
    (("node", "network-history", "-f", "json"), ()),
    (("node", "summary-history", "-f", "json"), ()),
    (("node", "summary-delta", "-f", "json"), ()),
    (("vm", "list", "-f", "json"), ()),
    (("vm", "show", "$vm", "-f", "json"), ("vm",)),
    (("vm", "stats", "$vm", "-f", "json"), ("vm",)),
    (("vm", "domain", "$vm", "-f", "json"), ("vm",)),
    (("vm", "snapshot", "list", "$vm", "-f", "json"), ("vm",)),
    (("vm", "template", "list", "-f", "json"), ()),
    (("vm", "template-show", "$vm_template", "-f", "json"), ("vm_template",)),
    (("jail", "list", "-f", "json"), ()),
    (("jail", "show", "$jail", "-f", "json"), ("jail",)),
    (("jail", "state", "$jail", "-f", "json"), ("jail",)),
    (("jail", "stats", "$jail", "-f", "json"), ("jail",)),
    (("jail", "root-mountpoint", "$jail", "-f", "json"), ("jail",)),
    (("jail", "snapshot", "list", "$jail", "-f", "json"), ("jail",)),
    (("jail", "template", "list", "-f", "json"), ()),
    (("jail", "template-show", "$jail_template", "-f", "json"), ("jail_template",)),
    (("jail", "bootstrap", "list", "--pool", "$pool", "-f", "json"), ("pool",)),
    (("network", "interface", "list", "-f", "json"), ()),
    (("network", "interface", "l3", "-f", "json"), ()),
    (("network", "switch", "list", "-f", "json"), ()),
    (("network", "route", "list", "-f", "json"), ()),
    (("network", "dhcp", "config", "-f", "json"), ()),
    (("network", "dhcp", "range-list", "-f", "json"), ()),
    (("network", "dhcp", "lease-list", "-f", "json"), ()),
    (("network", "firewall", "traffic-list", "-f", "json"), ()),
    (("network", "firewall", "nat-list", "-f", "json"), ()),
    (("network", "object", "list", "-f", "json"), ()),
    (("network", "wireguard", "status", "-f", "json"), ()),
    (("network", "wireguard", "client-list", "-f", "json"), ()),
    (("download", "list", "-f", "json"), ()),
    (("download", "show", "$download", "-f", "json"), ("download",)),
    (("download", "storage", "-f", "json"), ()),
    (("download", "utype", "-f", "json"), ()),
    (("replication", "policy", "list", "-f", "json"), ()),
    (("replication", "event", "list", "-f", "json"), ()),
    (("backup", "target", "list", "-f", "json"), ()),
    (("backup", "target", "show", "$backup_target", "-f", "json"), ("backup_target",)),
    (("backup", "target", "datasets", "$backup_target", "-f", "json"), ("backup_target",)),
    (("backup", "target", "running-jobs", "$backup_target", "-f", "json"), ("backup_target",)),
    (("backup", "job", "list", "-f", "json"), ()),
    (("backup", "job", "snapshots", "$backup_job", "-f", "json"), ("backup_job",)),
    (("backup", "event", "list", "-f", "json"), ()),
    (("backup", "event", "remote-list", "-f", "json"), ()),
    (("zfs", "pool", "list", "-f", "json"), ()),
    (("zfs", "pool", "status", "$pool", "-f", "json"), ("pool",)),
    (("zfs", "pool", "disks-usage", "-f", "json"), ()),
    (("zfs", "dataset", "list", "-f", "json"), ()),
    (("zfs", "dataset", "paginated", "-f", "json"), ()),
    (("zfs", "snapshot", "list", "-f", "json"), ()),
    (("zfs", "periodic", "list", "-f", "json"), ()),
    (("zfs", "dashboard-snapshot", "-f", "json"), ()),
    (("zfs", "dashboard-history", "-f", "json"), ()),
    (("zfs", "dashboard-delta", "-f", "json"), ()),
    (("task", "list", "-f", "json"), ()),
    (("task", "show", "$task", "-f", "json"), ("task",)),
    (("system", "settings", "-f", "json"), ()),
    (("system", "basic-settings", "-f", "json"), ()),
    (("system", "notes-list", "-f", "json"), ()),
    (("system", "disk-list", "-f", "json"), ()),
    (("system", "pci-list", "-f", "json"), ()),
    (("system", "ppt-list", "-f", "json"), ()),
    (("system", "tunables", "-f", "json"), ()),
    (("system", "file-list", "--param", "id=/", "-f", "json"), ()),
    (("system", "cert-list", "-f", "json"), ()),
    (("system", "health-basic", "-f", "json"), ()),
    (("system", "health-http", "-f", "json"), ()),
    (("samba", "config", "-f", "json"), ()),
    (("samba", "shares", "-f", "json"), ()),
    (("samba", "audit-logs", "-f", "json"), ()),
    (("iscsi", "targets", "-f", "json"), ()),
    (("iscsi", "initiators", "-f", "json"), ()),
    (("iscsi", "status", "-f", "json"), ()),
    (("iscsi", "sessions", "-f", "json"), ()),
    (("ddns", "list", "-f", "json"), ()),
    (("mdns", "config", "-f", "json"), ()),
    (("mdns", "records", "-f", "json"), ()),
    (("notifications", "list", "-f", "json"), ()),
    (("notifications", "count", "-f", "json"), ()),
    (("notifications", "rules", "-f", "json"), ()),
    (("notifications", "transports", "-f", "json"), ()),
    (("user", "list", "-f", "json"), ()),
    (("user", "capabilities", "-f", "json"), ()),
    (("user", "importable", "-f", "json"), ()),
    (("user", "next-uid", "-f", "json"), ()),
    (("user", "passkeys", "$user", "-f", "json"), ("user",)),
    (("group", "list", "-f", "json"), ()),
    (("auth", "login-config", "-f", "json"), ()),
    (("cloud-init", "templates", "-f", "json"), ()),
    (
        ("vm", "create", "live-check", "--pool", "$pool", "--no-vnc", "--dry-run", "-f", "json"),
        ("pool",),
    ),
]


def _leaf_commands() -> list[tuple[tuple[str, ...], Any]]:
    root = get_command(app)
    result: list[tuple[tuple[str, ...], Any]] = []

    def walk(command: Any, prefix: tuple[str, ...]) -> None:
        children = getattr(command, "commands", None)
        if children:
            for name, child in children.items():
                walk(child, (*prefix, name))
        else:
            result.append((prefix, command))

    walk(root, ())
    return sorted(result, key=lambda item: item[0])


@pytest.mark.parametrize(
    ("path", "command"),
    _leaf_commands(),
    ids=lambda value: " ".join(value) if isinstance(value, tuple) else "",
)
def test_every_command_has_help(path: tuple[str, ...], command: Any) -> None:
    """Every registered leaf command must render help."""
    text = command.get_help(Context(command))
    assert "Usage:" in text, f"help output missing Usage for: {' '.join(path)}"


def _resolve(args: tuple[str, ...], state: dict[str, Any]) -> tuple[list[str], list[str]]:
    resolved: list[str] = []
    missing: list[str] = []
    for arg in args:
        if arg.startswith("$"):
            key = arg[1:]
            value = state.get(key)
            if value is None:
                missing.append(key)
            else:
                resolved.append(str(value))
        else:
            resolved.append(arg)
    return resolved, missing


@pytest.mark.parametrize(
    ("case", "needs"),
    READ_CASES,
    ids=lambda case: " ".join(case) if isinstance(case, tuple) else "",
)
def test_read_only_command_against_live(
    case: tuple[str, ...],
    needs: tuple[str, ...],
    live_state: dict[str, Any],
    run_cli: Any,
) -> None:
    """Run a read-only command and check its structured output."""
    args, missing = _resolve(case, live_state)
    if missing:
        pytest.skip(f"live system has no {'/'.join(missing)}")
    result = run_cli(args)
    assert result.exit_code == 0, (
        f"command failed: {' '.join(args)}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    if "-f" in args and "json" in args:
        try:
            json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            pytest.fail(
                f"command did not return JSON: {' '.join(args)}\n"
                f"stdout:\n{result.stdout}\n"
                f"error: {exc}"
            )
