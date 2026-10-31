"""Additional command groups backed by the Sylve v0.3.1 HTTP API.

The commands here intentionally accept JSON/YAML bodies through ``--data`` and
query parameters through ``--param``.  That keeps the CLI thin: the API remains
the source of truth for request shapes, and new fields do not need a new flag.
"""

# shortcut: generic --data/--param commands avoid per-endpoint flag boilerplate.
# Add typed flags when a command becomes common enough to deserve them.

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Annotated, Any

import typer
import yaml

from sylve_cli.client import ResourceNotFoundError, SylveError
from sylve_cli.commands.backup import backup_event_app, job_app, target_app
from sylve_cli.commands.cluster import cluster_app, cluster_note_app
from sylve_cli.commands.download import download_app
from sylve_cli.commands.jail import jail_app
from sylve_cli.commands.network import (
    dhcp_app,
    firewall_app,
    object_app,
    route_app,
    switch_app,
    wg_app,
)
from sylve_cli.commands.node import node_app
from sylve_cli.commands.replication import policy_app
from sylve_cli.commands.task import task_app
from sylve_cli.commands.vm import vm_app
from sylve_cli.commands.zfs import dataset_app, periodic_app, pool_app, zfs_app
from sylve_cli.console_ws import attach_console
from sylve_cli.formatter import (
    ColumnSpec,
    OutputFormat,
    console,
    print_dict,
    print_list,
    print_result,
)
from sylve_cli.state import CLIState, ColumnsOption, FormatOption, NodeOption, confirm_destructive

system_app = typer.Typer(
    name="system",
    help="Manage host disks, SMART tests, PCI passthrough, files, certificates, and settings.",
    no_args_is_help=True,
    rich_markup_mode=None,
)
samba_app = typer.Typer(
    name="samba",
    help="Manage Samba configuration and shares.",
    no_args_is_help=True,
    rich_markup_mode=None,
)
iscsi_app = typer.Typer(
    name="iscsi",
    help="Manage iSCSI targets, initiators, LUNs, and portals.",
    no_args_is_help=True,
    rich_markup_mode=None,
)
ddns_app = typer.Typer(
    name="ddns",
    help="Manage dynamic DNS entries.",
    no_args_is_help=True,
    rich_markup_mode=None,
)
mdns_app = typer.Typer(
    name="mdns",
    help="Manage mDNS configuration and records.",
    no_args_is_help=True,
    rich_markup_mode=None,
)
notifications_app = typer.Typer(
    name="notifications",
    help="Manage notification transports, rules, and active notifications.",
    no_args_is_help=True,
    rich_markup_mode=None,
)
user_app = typer.Typer(
    name="user",
    help="Manage local, PAM, and imported Unix users.",
    no_args_is_help=True,
    rich_markup_mode=None,
)
group_app = typer.Typer(
    name="group",
    help="Manage authentication groups and membership.",
    no_args_is_help=True,
    rich_markup_mode=None,
)
auth_app = typer.Typer(
    name="auth",
    help="Authentication configuration, passkeys, and SSE tokens.",
    no_args_is_help=True,
    rich_markup_mode=None,
)
cloud_init_app = typer.Typer(
    name="cloud-init",
    help="Manage reusable cloud-init templates.",
    no_args_is_help=True,
    rich_markup_mode=None,
)

_PUBLIC_PATHS = {
    "/auth/login/config",
    "/auth/passkeys/login/begin",
    "/auth/passkeys/login/finish",
    "/basic/initialize",
    "/health/basic",
    "/health/http",
}


def _parse_data(value: str | None) -> Any:
    if value is None or not value.strip():
        return None
    if value.startswith("@"):
        path = Path(value[1:]).expanduser()
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise SylveError(f"Could not read request body '{path}': {exc}") from exc
    else:
        text = value
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise SylveError(f"Invalid request body: {exc}") from exc


def _parse_params(values: list[str] | None) -> dict[str, Any] | None:
    if not values:
        return None
    result: dict[str, Any] = {}
    for item in values:
        if "=" not in item:
            raise SylveError("--param must use KEY=VALUE format.")
        key, value = item.split("=", 1)
        try:
            result[key] = yaml.safe_load(value)
        except yaml.YAMLError:
            result[key] = value
    return result


def _print_result(data: Any, fmt: OutputFormat, title: str | None = None) -> None:
    if data in (None, {}, []):
        if fmt not in (OutputFormat.json, OutputFormat.yaml, OutputFormat.value):
            console.print("OK", style="green", markup=False)
        return
    if isinstance(data, list) and all(isinstance(row, dict) for row in data):
        columns = [ColumnSpec(str(key), str(key)) for key in data[0]]
        print_list(data, columns, fmt=fmt, title=title)
    elif isinstance(data, dict):
        print_dict(data, fmt=fmt, title=title)
    else:
        print_result(data, fmt)


def _path_for(template: str, args: list[str] | None) -> str:
    args = args or []
    placeholders = re.findall(r"\{[^}]+\}", template)
    if len(args) != len(placeholders):
        raise SylveError(
            f"This command expects {len(placeholders)} path argument(s), "
            f"got {len(args)}: {template}."
        )
    values = iter(args)
    return re.sub(r"\{[^}]+\}", lambda _: next(values), template)


def _execute_generic(
    ctx: typer.Context,
    method: str,
    path: str,
    args: list[str] | None,
    data: str | None,
    param: list[str] | None,
    yes: bool,
    node: str | None,
    fmt: OutputFormat,
    title: str,
) -> None:
    """Run one generic API request and print the result."""
    state: CLIState = ctx.obj
    target_path = _path_for(path, args)
    destructive = method == "DELETE" or "delete" in path.lower()
    if destructive:
        # A non-interactive stdin must not count as consent; the helper aborts
        # with a "--yes" hint instead of deleting silently.
        confirm_destructive(f"Send {method} {target_path}?", yes=yes)
    with state.get_client(node_override=node) as client:
        result = client.request(
            method,
            target_path,
            params=_parse_params(param),
            json_body=_parse_data(data),
            node=node,
            require_auth=path not in _PUBLIC_PATHS,
        )
    _print_result(result, fmt, title)


def _add(
    app: typer.Typer,
    name: str,
    method: str,
    path: str,
    description: str,
    args_help: str = "",
    *,
    binary: bool = False,
    upload: bool = False,
) -> None:
    title = description.split(".")[0]
    help_text = description if not args_help else f"{description} Arguments: {args_help}."
    destructive = method == "DELETE" or "delete" in path.lower()

    if binary:

        def command(
            ctx: typer.Context,
            args: Annotated[
                list[str] | None, typer.Argument(help="Path arguments in URL order.")
            ] = None,
            param: Annotated[
                list[str] | None,
                typer.Option("--param", "-p", help="Query parameter KEY=VALUE (repeatable)."),
            ] = None,
            output: Annotated[Path, typer.Option("--output", "-o")] = ...,  # type: ignore[assignment]
            node: NodeOption = None,
        ) -> None:
            state: CLIState = ctx.obj
            with state.get_client(node_override=node) as client:
                target = client.download_file(
                    _path_for(path, args), output, params=_parse_params(param), node=node
                )
            console.print(f"Saved to {target}", style="green", markup=False)

    elif upload:

        def command(  # type: ignore[misc]
            ctx: typer.Context,
            args: Annotated[
                list[str] | None, typer.Argument(help="Path arguments in URL order.")
            ] = None,
            file: Annotated[
                Path,
                typer.Option(
                    "--file",
                    exists=True,
                    dir_okay=False,
                    readable=True,
                    help="Local file to upload.",
                ),
            ] = ...,  # type: ignore[assignment]
            param: Annotated[
                list[str] | None,
                typer.Option("--param", "-p", help="Query parameter KEY=VALUE (repeatable)."),
            ] = None,
            node: NodeOption = None,
            fmt: FormatOption = OutputFormat.table,
        ) -> None:
            state: CLIState = ctx.obj
            with state.get_client(node_override=node) as client, file.open("rb") as handle:
                result = client.post(
                    _path_for(path, args),
                    params=_parse_params(param),
                    files={"filepond": (file.name, handle, "application/octet-stream")},
                    node=node,
                )
            _print_result(result, fmt, title)

    elif destructive:

        def command(  # type: ignore[misc]
            ctx: typer.Context,
            args: Annotated[
                list[str] | None, typer.Argument(help="Path arguments in URL order.")
            ] = None,
            data: Annotated[
                str | None,
                typer.Option(
                    "--data",
                    "-d",
                    help="Raw JSON or YAML request body, or @FILE to read it from disk.",
                ),
            ] = None,
            param: Annotated[
                list[str] | None,
                typer.Option("--param", "-p", help="Query parameter KEY=VALUE (repeatable)."),
            ] = None,
            yes: Annotated[
                bool,
                typer.Option("-y", "--yes", help="Skip confirmation prompt."),
            ] = False,
            node: NodeOption = None,
            fmt: FormatOption = OutputFormat.table,
        ) -> None:
            _execute_generic(ctx, method, path, args, data, param, yes, node, fmt, title)

    else:

        def command(  # type: ignore[misc]
            ctx: typer.Context,
            args: Annotated[
                list[str] | None, typer.Argument(help="Path arguments in URL order.")
            ] = None,
            data: Annotated[
                str | None,
                typer.Option(
                    "--data",
                    "-d",
                    help="Raw JSON or YAML request body, or @FILE to read it from disk.",
                ),
            ] = None,
            param: Annotated[
                list[str] | None,
                typer.Option("--param", "-p", help="Query parameter KEY=VALUE (repeatable)."),
            ] = None,
            node: NodeOption = None,
            fmt: FormatOption = OutputFormat.table,
        ) -> None:
            _execute_generic(ctx, method, path, args, data, param, False, node, fmt, title)

    command.__name__ = f"{app.info.name}_{name}".replace("-", "_")
    command.__doc__ = help_text
    app.command(name, help=help_text)(command)


# ---------------------------------------------------------------------------
# VM configuration
# ---------------------------------------------------------------------------
for spec in [  # type: ignore[assignment]
    (
        vm_app,
        "template-show",
        "GET",
        "/vm/templates/{templateId}",
        "Show a VM template.",
        "templateId",
    ),
    (vm_app, "description", "PATCH", "/vm/{rid}/description", "Update a VM description.", "rid"),
    (vm_app, "domain", "GET", "/vm/{rid}/domain", "Show the libvirt domain XML.", "rid"),
    (vm_app, "stats", "GET", "/vm/{rid}/stats", "Show current VM statistics.", "rid"),
    (
        vm_app,
        "stats-step",
        "GET",
        "/vm/{rid}/stats/{step}",
        "Show VM statistics for a step.",
        "rid step",
    ),
    (
        vm_app,
        "hardware-cpu",
        "PUT",
        "/vm/{rid}/hardware/cpu",
        "Replace VM CPU configuration.",
        "rid",
    ),
    (
        vm_app,
        "hardware-ram",
        "PUT",
        "/vm/{rid}/hardware/ram",
        "Replace VM RAM configuration.",
        "rid",
    ),
    (
        vm_app,
        "hardware-pci",
        "PUT",
        "/vm/{rid}/hardware/pci-devices",
        "Replace VM PCI passthrough devices.",
        "rid",
    ),
    (
        vm_app,
        "hardware-vnc",
        "PUT",
        "/vm/{rid}/hardware/vnc",
        "Replace VM VNC configuration.",
        "rid",
    ),
    (vm_app, "network-attach", "POST", "/vm/{rid}/networks", "Attach a network to a VM.", "rid"),
    (
        vm_app,
        "network-detach",
        "DELETE",
        "/vm/{rid}/networks/{networkId}",
        "Detach a VM network.",
        "rid networkId",
    ),
    (
        vm_app,
        "network-update",
        "PATCH",
        "/vm/{rid}/networks/{networkId}",
        "Update a VM network.",
        "rid networkId",
    ),
    (vm_app, "storage-attach", "POST", "/vm/{rid}/storage", "Attach storage to a VM.", "rid"),
    (
        vm_app,
        "storage-from-image",
        "POST",
        "/vm/{rid}/storage/from-image",
        "Create VM storage from an image.",
        "rid",
    ),
    (
        vm_app,
        "storage-update",
        "PATCH",
        "/vm/{rid}/storage/{storageId}",
        "Update VM storage.",
        "rid storageId",
    ),
    (
        vm_app,
        "storage-delete",
        "DELETE",
        "/vm/{rid}/storage/{storageId}",
        "Delete VM storage.",
        "rid storageId",
    ),
    (
        vm_app,
        "options-boot-order",
        "PUT",
        "/vm/{rid}/options/boot-order",
        "Replace VM autostart configuration.",
        "rid",
    ),
    (
        vm_app,
        "options-boot-rom",
        "PUT",
        "/vm/{rid}/options/boot-rom",
        "Replace VM boot ROM configuration.",
        "rid",
    ),
    (
        vm_app,
        "options-clock",
        "PUT",
        "/vm/{rid}/options/clock",
        "Replace VM clock configuration.",
        "rid",
    ),
    (
        vm_app,
        "options-cloud-init",
        "PUT",
        "/vm/{rid}/options/cloud-init",
        "Replace VM cloud-init configuration.",
        "rid",
    ),
    (
        vm_app,
        "options-extra-bhyve",
        "PUT",
        "/vm/{rid}/options/extra-bhyve-options",
        "Replace extra bhyve options.",
        "rid",
    ),
    (
        vm_app,
        "options-ignore-umsrs",
        "PUT",
        "/vm/{rid}/options/ignore-umsrs",
        "Replace unknown-MSR handling.",
        "rid",
    ),
    (
        vm_app,
        "options-qemu-guest-agent",
        "PUT",
        "/vm/{rid}/options/qemu-guest-agent",
        "Replace QEMU guest-agent configuration.",
        "rid",
    ),
    (
        vm_app,
        "options-serial-console",
        "PUT",
        "/vm/{rid}/options/serial-console",
        "Replace serial-console configuration.",
        "rid",
    ),
    (
        vm_app,
        "options-shutdown-wait-time",
        "PUT",
        "/vm/{rid}/options/shutdown-wait-time",
        "Replace shutdown wait time.",
        "rid",
    ),
    (
        vm_app,
        "options-tpm",
        "PUT",
        "/vm/{rid}/options/tpm",
        "Replace TPM emulation configuration.",
        "rid",
    ),
    (
        vm_app,
        "options-wol",
        "PUT",
        "/vm/{rid}/options/wol",
        "Replace Wake-on-LAN configuration.",
        "rid",
    ),
    (
        vm_app,
        "registration-purge",
        "DELETE",
        "/vm/{rid}/registration",
        "Purge an orphaned VM registration.",
        "rid",
    ),
]:
    _add(*spec)

# ---------------------------------------------------------------------------
# Jail configuration
# ---------------------------------------------------------------------------
for spec in [  # type: ignore[assignment]
    (jail_app, "create", "POST", "/jail", "Create a Jail."),
    (
        jail_app,
        "description",
        "PATCH",
        "/jail/{ctid}/description",
        "Update a Jail description.",
        "ctid",
    ),
    (
        jail_app,
        "hardware-cpu",
        "PUT",
        "/jail/{ctid}/hardware/cpu",
        "Update a Jail CPU limit.",
        "ctid",
    ),
    (
        jail_app,
        "hardware-ram",
        "PUT",
        "/jail/{ctid}/hardware/ram",
        "Update a Jail RAM limit.",
        "ctid",
    ),
    (
        jail_app,
        "hardware-resource-limits",
        "PUT",
        "/jail/{ctid}/hardware/resource-limits",
        "Set Jail resource limits.",
        "ctid",
    ),
    (
        jail_app,
        "network-inheritance",
        "PUT",
        "/jail/{ctid}/network/inheritance",
        "Set Jail network inheritance.",
        "ctid",
    ),
    (
        jail_app,
        "network-attach",
        "POST",
        "/jail/{ctid}/networks",
        "Attach a network to a Jail.",
        "ctid",
    ),
    (
        jail_app,
        "network-detach",
        "DELETE",
        "/jail/{ctid}/networks/{networkId}",
        "Detach a Jail network.",
        "ctid networkId",
    ),
    (
        jail_app,
        "network-update",
        "PATCH",
        "/jail/{ctid}/networks/{networkId}",
        "Update a Jail network.",
        "ctid networkId",
    ),
    (
        jail_app,
        "options-additional",
        "PUT",
        "/jail/{ctid}/options/additional-options",
        "Replace additional jail.conf options.",
        "ctid",
    ),
    (
        jail_app,
        "options-allowed",
        "PUT",
        "/jail/{ctid}/options/allowed-options",
        "Replace allowed jail options.",
        "ctid",
    ),
    (
        jail_app,
        "options-boot-order",
        "PUT",
        "/jail/{ctid}/options/boot-order",
        "Replace Jail autostart configuration.",
        "ctid",
    ),
    (
        jail_app,
        "options-devfs-rules",
        "PUT",
        "/jail/{ctid}/options/devfs-rules",
        "Replace Jail DevFS rules.",
        "ctid",
    ),
    (
        jail_app,
        "options-execution-timeout",
        "PUT",
        "/jail/{ctid}/options/execution-timeout",
        "Replace Jail execution timeout.",
        "ctid",
    ),
    (
        jail_app,
        "options-fstab",
        "PUT",
        "/jail/{ctid}/options/fstab",
        "Replace Jail fstab configuration.",
        "ctid",
    ),
    (
        jail_app,
        "options-lifecycle-hooks",
        "PUT",
        "/jail/{ctid}/options/lifecycle-hooks",
        "Replace Jail lifecycle hooks.",
        "ctid",
    ),
    (
        jail_app,
        "options-metadata",
        "PUT",
        "/jail/{ctid}/options/metadata",
        "Replace Jail metadata.",
        "ctid",
    ),
    (
        jail_app,
        "options-resolv-conf",
        "PUT",
        "/jail/{ctid}/options/resolv-conf",
        "Replace Jail resolv.conf configuration.",
        "ctid",
    ),
    (
        jail_app,
        "options-wol",
        "PUT",
        "/jail/{ctid}/options/wol",
        "Replace Jail Wake-on-LAN configuration.",
        "ctid",
    ),
    (
        jail_app,
        "root-mountpoint",
        "GET",
        "/jail/{ctid}/root-mountpoint",
        "Resolve a Jail root mountpoint.",
        "ctid",
    ),
    (jail_app, "state", "GET", "/jail/{ctid}/state", "Show Jail state.", "ctid"),
    (jail_app, "stats", "GET", "/jail/{ctid}/stats", "Show Jail statistics.", "ctid"),
    (
        jail_app,
        "template-show",
        "GET",
        "/jail/templates/{templateId}",
        "Show a Jail template.",
        "templateId",
    ),
    (
        jail_app,
        "template-delete",
        "DELETE",
        "/jail/templates/{templateId}",
        "Delete a Jail template.",
        "templateId",
    ),
    (
        jail_app,
        "template-capture",
        "POST",
        "/jail/{ctid}/templates",
        "Capture a Jail as a template.",
        "ctid",
    ),
    (
        jail_app,
        "template-deploy",
        "POST",
        "/jail/templates/{templateId}/jails",
        "Create Jails from a template.",
        "templateId",
    ),
    (
        jail_app,
        "bootstrap-delete",
        "DELETE",
        "/jail/bootstraps/{name}",
        "Delete a pkgbase Jail bootstrap.",
        "name",
    ),
]:
    _add(*spec)

# ---------------------------------------------------------------------------
# Network writes
# ---------------------------------------------------------------------------
for spec in [  # type: ignore[assignment]
    (dhcp_app, "config-update", "PUT", "/network/dhcp/config", "Update DHCP configuration."),
    (dhcp_app, "range-create", "POST", "/network/dhcp/range", "Create a DHCP range."),
    (dhcp_app, "range-update", "PUT", "/network/dhcp/range/{id}", "Update a DHCP range.", "id"),
    (dhcp_app, "range-delete", "DELETE", "/network/dhcp/range/{id}", "Delete a DHCP range.", "id"),
    (dhcp_app, "lease-create", "POST", "/network/dhcp/lease", "Create a static DHCP lease."),
    (
        dhcp_app,
        "lease-update",
        "PUT",
        "/network/dhcp/lease/{id}",
        "Update a static DHCP lease.",
        "id",
    ),
    (
        dhcp_app,
        "lease-delete",
        "DELETE",
        "/network/dhcp/lease/{id}",
        "Delete a static DHCP lease.",
        "id",
    ),
    (
        dhcp_app,
        "lease-delete-dynamic",
        "DELETE",
        "/network/dhcp/lease/dynamic",
        "Delete a dynamic DHCP lease.",
    ),
    (
        firewall_app,
        "advanced-show",
        "GET",
        "/network/firewall/advanced",
        "Show advanced firewall settings.",
    ),
    (
        firewall_app,
        "advanced-update",
        "PUT",
        "/network/firewall/advanced",
        "Update advanced firewall settings.",
    ),
    (
        firewall_app,
        "advanced-preview",
        "POST",
        "/network/firewall/advanced/preview",
        "Preview rendered firewall configuration.",
    ),
    (
        firewall_app,
        "advanced-rendered",
        "GET",
        "/network/firewall/advanced/rendered",
        "Show rendered firewall configuration.",
    ),
    (
        firewall_app,
        "traffic-create",
        "POST",
        "/network/firewall/traffic",
        "Create a firewall traffic rule.",
    ),
    (
        firewall_app,
        "traffic-update",
        "PUT",
        "/network/firewall/traffic/{id}",
        "Update a firewall traffic rule.",
        "id",
    ),
    (
        firewall_app,
        "traffic-delete",
        "DELETE",
        "/network/firewall/traffic/{id}",
        "Delete a firewall traffic rule.",
        "id",
    ),
    (
        firewall_app,
        "traffic-bulk-delete",
        "DELETE",
        "/network/firewall/traffic",
        "Bulk-delete firewall traffic rules.",
    ),
    (
        firewall_app,
        "traffic-reorder",
        "PUT",
        "/network/firewall/traffic/reorder",
        "Reorder firewall traffic rules.",
    ),
    (
        firewall_app,
        "traffic-counters",
        "GET",
        "/network/firewall/traffic/counters",
        "Show firewall traffic rule counters.",
    ),
    (firewall_app, "nat-create", "POST", "/network/firewall/nat", "Create a firewall NAT rule."),
    (
        firewall_app,
        "nat-update",
        "PUT",
        "/network/firewall/nat/{id}",
        "Update a firewall NAT rule.",
        "id",
    ),
    (
        firewall_app,
        "nat-delete",
        "DELETE",
        "/network/firewall/nat/{id}",
        "Delete a firewall NAT rule.",
        "id",
    ),
    (
        firewall_app,
        "nat-bulk-delete",
        "DELETE",
        "/network/firewall/nat",
        "Bulk-delete firewall NAT rules.",
    ),
    (
        firewall_app,
        "nat-reorder",
        "PUT",
        "/network/firewall/nat/reorder",
        "Reorder firewall NAT rules.",
    ),
    (
        firewall_app,
        "nat-counters",
        "GET",
        "/network/firewall/nat/counters",
        "Show firewall NAT rule counters.",
    ),
    (
        firewall_app,
        "nat-route-suggestions",
        "GET",
        "/network/firewall/nat/{id}/route-suggestions",
        "Suggest routes for a NAT rule.",
        "id",
    ),
    (
        wg_app,
        "server-init",
        "POST",
        "/network/wireguard/server",
        "Initialize the WireGuard server.",
    ),
    (wg_app, "server-update", "PUT", "/network/wireguard/server", "Update the WireGuard server."),
    (
        wg_app,
        "server-delete",
        "DELETE",
        "/network/wireguard/server",
        "Deinitialize the WireGuard server.",
    ),
    (wg_app, "server-state", "PATCH", "/network/wireguard/server", "Set WireGuard server state."),
    (wg_app, "peer-add", "POST", "/network/wireguard/server/peer", "Add a WireGuard server peer."),
    (
        wg_app,
        "peer-update",
        "PUT",
        "/network/wireguard/server/peer/{peerId}",
        "Update a WireGuard peer.",
        "peerId",
    ),
    (
        wg_app,
        "peer-remove",
        "DELETE",
        "/network/wireguard/server/peer/{peerId}",
        "Remove a WireGuard peer.",
        "peerId",
    ),
    (
        wg_app,
        "peer-state",
        "PATCH",
        "/network/wireguard/server/peer/{peerId}",
        "Set WireGuard peer state.",
        "peerId",
    ),
    (wg_app, "client-create", "POST", "/network/wireguard/clients", "Create a WireGuard client."),
    (
        wg_app,
        "client-update",
        "PUT",
        "/network/wireguard/clients/{clientId}",
        "Update a WireGuard client.",
        "clientId",
    ),
    (
        wg_app,
        "client-delete",
        "DELETE",
        "/network/wireguard/clients/{clientId}",
        "Delete a WireGuard client.",
        "clientId",
    ),
    (
        wg_app,
        "client-state",
        "PATCH",
        "/network/wireguard/clients/{clientId}",
        "Set WireGuard client state.",
        "clientId",
    ),
    (route_app, "create", "POST", "/network/route", "Create a static route."),
    (route_app, "update", "PUT", "/network/route/{id}", "Update a static route.", "id"),
    (
        switch_app,
        "update-standard",
        "PUT",
        "/network/switch/standard/{id}",
        "Update a standard switch.",
        "id",
    ),
    (object_app, "update", "PUT", "/network/object/{id}", "Update a network object.", "id"),
    (object_app, "bulk-delete", "DELETE", "/network/object", "Bulk-delete network objects."),
]:
    _add(*spec)


# shortcut: WebSocket consoles, VNC, and node terminal are not wrapped here;
# use the web UI or a websocket client until interactive terminal plumbing is
# actually needed.


# ---------------------------------------------------------------------------
# Node history and task lookup
# ---------------------------------------------------------------------------
for spec in [  # type: ignore[assignment]
    (node_app, "cpu-history", "GET", "/info/cpu/historical", "Show historical CPU data."),
    (node_app, "ram-history", "GET", "/info/ram/historical", "Show historical RAM data."),
    (node_app, "swap-history", "GET", "/info/swap/historical", "Show historical swap data."),
    (
        node_app,
        "network-history",
        "GET",
        "/info/network-interfaces/historical",
        "Show historical network data.",
    ),
    (node_app, "summary-history", "GET", "/info/summary/history", "Show node summary history."),
    (
        node_app,
        "summary-delta",
        "GET",
        "/info/summary/history/delta",
        "Show node summary history deltas.",
    ),
    (
        task_app,
        "active",
        "GET",
        "/tasks/lifecycle/active/{guestType}/{guestId}",
        "Show the active task for a guest.",
        "guestType guestId",
    ),
]:
    _add(*spec)


# ---------------------------------------------------------------------------
# ZFS depth
# ---------------------------------------------------------------------------
for spec in [  # type: ignore[assignment]
    (pool_app, "create", "POST", "/zfs/pools", "Create a ZFS pool."),
    (pool_app, "delete", "DELETE", "/zfs/pools/{guid}", "Delete a ZFS pool.", "guid"),
    (pool_app, "edit", "PATCH", "/zfs/pools/{guid}", "Edit a ZFS pool.", "guid"),
    (pool_app, "detach", "POST", "/zfs/pools/{guid}/detach", "Detach a pool device.", "guid"),
    (
        pool_app,
        "replace-device",
        "POST",
        "/zfs/pools/{guid}/replace-device",
        "Replace a pool device.",
        "guid",
    ),
    (pool_app, "disks-usage", "GET", "/zfs/pools/disks-usage", "Show disk usage."),
    (
        dataset_app,
        "edit",
        "PATCH",
        "/zfs/datasets/filesystem/{guid}",
        "Edit a ZFS filesystem.",
        "guid",
    ),
    (dataset_app, "bulk-delete", "DELETE", "/zfs/datasets", "Bulk-delete ZFS datasets."),
    (dataset_app, "paginated", "GET", "/zfs/datasets/paginated", "List paginated ZFS datasets."),
    (
        dataset_app,
        "volume-edit",
        "PATCH",
        "/zfs/datasets/volume/{guid}",
        "Edit a ZFS volume.",
        "guid",
    ),
    (
        dataset_app,
        "volume-flash",
        "POST",
        "/zfs/datasets/volume/{guid}/flash",
        "Flash a ZFS volume.",
        "guid",
    ),
    (
        periodic_app,
        "create",
        "POST",
        "/zfs/datasets/snapshot/periodic",
        "Create a periodic snapshot job.",
    ),
    (
        periodic_app,
        "update",
        "PATCH",
        "/zfs/datasets/snapshot/periodic/{id}",
        "Update a periodic snapshot job.",
        "id",
    ),
    (
        periodic_app,
        "delete",
        "DELETE",
        "/zfs/datasets/snapshot/periodic/{id}",
        "Delete a periodic snapshot job.",
        "id",
    ),
    (
        zfs_app,
        "dashboard-snapshot",
        "GET",
        "/zfs/dashboard/snapshot",
        "Show the current ZFS dashboard snapshot.",
    ),
    (zfs_app, "dashboard-history", "GET", "/zfs/dashboard/history", "Show ZFS dashboard history."),
    (
        zfs_app,
        "dashboard-delta",
        "GET",
        "/zfs/dashboard/history/delta",
        "Show ZFS dashboard history deltas.",
    ),
]:
    _add(*spec)


# ---------------------------------------------------------------------------
# Backup depth
# ---------------------------------------------------------------------------
for spec in [  # type: ignore[assignment]
    (target_app, "create", "POST", "/cluster/backups/targets", "Create a backup target."),
    (target_app, "update", "PUT", "/cluster/backups/targets/{id}", "Update a backup target.", "id"),
    (
        target_app,
        "running-jobs",
        "GET",
        "/cluster/backups/targets/{id}/running-jobs",
        "List running jobs for a target.",
        "id",
    ),
    (
        target_app,
        "dataset-snapshots",
        "GET",
        "/cluster/backups/targets/{id}/datasets/snapshots",
        "List target dataset snapshots.",
        "id",
    ),
    (
        target_app,
        "vm-metadata",
        "GET",
        "/cluster/backups/targets/{id}/datasets/vm-metadata",
        "Show target VM metadata.",
        "id",
    ),
    (
        target_app,
        "jail-metadata",
        "GET",
        "/cluster/backups/targets/{id}/datasets/jail-metadata",
        "Show target Jail metadata.",
        "id",
    ),
    (
        target_app,
        "restore",
        "POST",
        "/cluster/backups/targets/{id}/restore",
        "Restore a target dataset.",
        "id",
    ),
    (job_app, "create", "POST", "/cluster/backups/jobs", "Create a backup job."),
    (job_app, "update", "PUT", "/cluster/backups/jobs/{id}", "Update a backup job.", "id"),
    (
        backup_event_app,
        "remote-list",
        "GET",
        "/cluster/backups/events/remote",
        "List remote backup events with pagination.",
    ),
    (
        policy_app,
        "update",
        "PUT",
        "/cluster/replication/policies/{id}",
        "Update a replication policy.",
        "id",
    ),
]:
    _add(*spec)


# ---------------------------------------------------------------------------
# Cluster depth
# ---------------------------------------------------------------------------
for spec in [  # type: ignore[assignment]
    (cluster_app, "accept-join", "POST", "/cluster/accept-join", "Accept a pending cluster join."),
    (cluster_note_app, "update", "PUT", "/cluster/notes/{id}", "Update a cluster note.", "id"),
    (
        cluster_note_app,
        "bulk-delete",
        "POST",
        "/cluster/notes/bulk-delete",
        "Bulk-delete cluster notes.",
    ),
]:
    _add(*spec)


# ---------------------------------------------------------------------------
# Downloads
# ---------------------------------------------------------------------------
for spec in [  # type: ignore[assignment]
    (
        download_app,
        "update",
        "PATCH",
        "/utilities/downloads/{id}",
        "Update download metadata.",
        "id",
    ),
    (
        download_app,
        "utype",
        "GET",
        "/utilities/downloads/utype",
        "List completed download choices.",
    ),
    (
        download_app,
        "abort-upload",
        "DELETE",
        "/utilities/downloader-uploads/{id}",
        "Abort a staged upload.",
        "id",
    ),
]:
    _add(*spec)

_add(
    download_app,
    "file",
    "GET",
    "/utilities/downloads/{uuid}",
    "Download a completed file using signed capability params.",
    args_help="uuid",
    binary=True,
)
_add(
    download_app,
    "file-with-name",
    "GET",
    "/utilities/downloads/{uuid}/{filename}",
    "Download a completed file by UUID and filename using signed capability params.",
    args_help="uuid filename",
    binary=True,
)


# ---------------------------------------------------------------------------
# System
# ---------------------------------------------------------------------------
for spec in [  # type: ignore[assignment]
    (system_app, "init", "POST", "/basic/initialize", "Initialize Sylve."),
    (
        system_app,
        "basic-settings",
        "GET",
        "/basic/settings",
        "Show basic Sylve settings from /basic/settings.",
    ),
    (
        system_app,
        "settings",
        "GET",
        "/system/basic-settings",
        "Show system basic settings from /system/basic-settings.",
    ),
    (
        system_app,
        "settings-pools",
        "PUT",
        "/system/basic-settings/pools",
        "Replace usable ZFS pools.",
    ),
    (
        system_app,
        "service",
        "PATCH",
        "/system/basic-settings/services/{service}",
        "Set a service state.",
        "service",
    ),
    (system_app, "notes-list", "GET", "/info/notes", "List host notes."),
    (system_app, "notes-create", "POST", "/info/notes", "Create a host note."),
    (system_app, "notes-update", "PUT", "/info/notes/{id}", "Update a host note.", "id"),
    (system_app, "notes-delete", "DELETE", "/info/notes/{id}", "Delete a host note.", "id"),
    (system_app, "notes-bulk-delete", "DELETE", "/info/notes", "Bulk-delete host notes."),
    (system_app, "disk-list", "GET", "/disk", "List disk devices."),
    (
        system_app,
        "disk-partition-delete",
        "DELETE",
        "/disk/partitions/{partition}",
        "Delete a partition.",
        "partition",
    ),
    (
        system_app,
        "disk-gpt-init",
        "POST",
        "/disk/{device}/partition-table",
        "Initialize a GPT partition table.",
        "device",
    ),
    (
        system_app,
        "disk-gpt-clear",
        "DELETE",
        "/disk/{device}/partition-table",
        "Clear a disk partition table.",
        "device",
    ),
    (
        system_app,
        "disk-partition-create",
        "POST",
        "/disk/{device}/partitions",
        "Create disk partitions.",
        "device",
    ),
    (
        system_app,
        "disk-smart-info",
        "GET",
        "/disk/smart/self-test",
        "Show SMART self-test information.",
    ),
    (system_app, "disk-smart-start", "POST", "/disk/smart/self-test", "Start a SMART self-test."),
    (
        system_app,
        "disk-smart-abort",
        "POST",
        "/disk/smart/self-test/abort",
        "Abort a SMART self-test.",
    ),
    (
        system_app,
        "disk-smart-schedules",
        "GET",
        "/disk/smart/self-test/schedules",
        "List SMART test schedules.",
    ),
    (
        system_app,
        "disk-smart-schedule-create",
        "POST",
        "/disk/smart/self-test/schedules",
        "Create a SMART test schedule.",
    ),
    (
        system_app,
        "disk-smart-schedule-update",
        "PUT",
        "/disk/smart/self-test/schedules/{id}",
        "Update a SMART test schedule.",
        "id",
    ),
    (
        system_app,
        "disk-smart-schedule-delete",
        "DELETE",
        "/disk/smart/self-test/schedules/{id}",
        "Delete a SMART test schedule.",
        "id",
    ),
    (system_app, "pci-list", "GET", "/system/pci-devices", "List PCI devices."),
    (system_app, "ppt-list", "GET", "/system/ppt-devices", "List managed PCI passthrough devices."),
    (system_app, "ppt-enable", "POST", "/system/ppt-devices", "Enable PCI passthrough."),
    (
        system_app,
        "ppt-import",
        "POST",
        "/system/ppt-devices/import",
        "Import a PCI passthrough device.",
    ),
    (system_app, "ppt-prepare", "POST", "/system/ppt-devices/prepare", "Prepare PCI passthrough."),
    (
        system_app,
        "ppt-disable",
        "DELETE",
        "/system/ppt-devices/{id}",
        "Disable PCI passthrough.",
        "id",
    ),
    (system_app, "tunables", "GET", "/system/tunables/remote", "List sysctl tunables."),
    (system_app, "tunable-set", "PUT", "/system/tunables", "Set a sysctl tunable."),
    (system_app, "file-list", "GET", "/system/file-explorer", "Browse files and folders."),
    (system_app, "file-create", "POST", "/system/file-explorer", "Create a file or folder."),
    (
        system_app,
        "file-copy-move",
        "POST",
        "/system/file-explorer/copy-or-move-batch",
        "Copy or move files.",
    ),
    (system_app, "file-delete", "POST", "/system/file-explorer/delete", "Delete files or folders."),
    (system_app, "file-rename", "POST", "/system/file-explorer/rename", "Rename a file or folder."),
    (
        system_app,
        "file-upload-revert",
        "DELETE",
        "/system/file-explorer/upload",
        "Revert an uploaded file.",
    ),
    (system_app, "cert-list", "GET", "/certificates", "List TLS certificates."),
    (system_app, "cert-create", "POST", "/certificates", "Create a TLS certificate."),
    (
        system_app,
        "cert-domain-check",
        "GET",
        "/certificates/domain-check",
        "Check certificate domain resolution.",
    ),
    (system_app, "cert-update", "PATCH", "/certificates/{id}", "Update a TLS certificate.", "id"),
    (system_app, "cert-delete", "DELETE", "/certificates/{id}", "Delete a TLS certificate.", "id"),
    (
        system_app,
        "cert-activate",
        "POST",
        "/certificates/{id}/activate",
        "Schedule certificate activation.",
        "id",
    ),
    (
        system_app,
        "cert-activate-cancel",
        "DELETE",
        "/certificates/{id}/activate",
        "Cancel certificate activation.",
        "id",
    ),
    (
        system_app,
        "cert-renew",
        "POST",
        "/certificates/{id}/renew",
        "Renew a TLS certificate.",
        "id",
    ),
    (
        system_app,
        "cert-retry",
        "POST",
        "/certificates/{id}/retry",
        "Retry certificate issuance.",
        "id",
    ),
    (system_app, "health-basic", "GET", "/health/basic", "Run a basic health check."),
    (system_app, "health-http", "GET", "/health/http", "Run an HTTP health check."),
]:
    _add(*spec)


@system_app.command("notes-show")
def system_notes_show(
    ctx: typer.Context,
    note_id: Annotated[str, typer.Argument(help="Host note ID to display.")],
    node: NodeOption = None,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
) -> None:
    """Display full details of a host note."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        notes = client.get("/info/notes", node=node) or []
    if isinstance(notes, list):
        for note in notes:
            if isinstance(note, dict) and str(note.get("id")) == note_id:
                print_dict(note, fmt=fmt, selected_columns=columns, title=f"Host Note {note_id}")
                return
    raise ResourceNotFoundError(f"Host note '{note_id}' not found.")


_add(
    system_app,
    "file-upload",
    "POST",
    "/system/file-explorer/upload",
    "Upload a file. Use --param path=/destination.",
    upload=True,
)
_add(
    system_app,
    "file-download",
    "GET",
    "/system/file-explorer/download",
    "Download a file. Use --param id=/absolute/path.",
    binary=True,
)
_add(
    system_app,
    "cert-archive",
    "GET",
    "/certificates/{id}/archive",
    "Download a certificate archive.",
    args_help="id",
    binary=True,
)


@system_app.command("events")
def system_events(
    ctx: typer.Context,
    lines: Annotated[
        int | None,
        typer.Option(
            "--lines",
            "-l",
            min=1,
            help="Stop after printing N non-empty event lines.",
        ),
    ] = None,
    reconnect: Annotated[
        bool,
        typer.Option(
            "--reconnect/--no-reconnect",
            help="Re-mint sse_token and reconnect if the event stream drops.",
        ),
    ] = True,
    param: Annotated[
        list[str] | None,
        typer.Option("--param", "-p", help="Query parameter KEY=VALUE (repeatable)."),
    ] = None,
    node: NodeOption = None,
) -> None:
    """Stream server-sent events using a short-lived sse_token capability."""
    state: CLIState = ctx.obj
    parsed_params = _parse_params(param) or {}
    explicit_token = parsed_params.get("sse_token")
    printed = 0
    with state.get_client(node_override=node) as client:
        while True:
            req_params = dict(parsed_params)
            if not explicit_token:
                req_params.pop("sse_token", None)
            try:
                for line in client.stream_lines("/events/stream", params=req_params, node=node):
                    console.print(line, markup=False)
                    if line.strip():
                        printed += 1
                        if lines is not None and printed >= lines:
                            return
                if not reconnect or lines is not None:
                    return
                time.sleep(1.5)
            except KeyboardInterrupt:
                return


@system_app.command("terminal")
def system_terminal(
    ctx: typer.Context,
    kill_on_exit: Annotated[
        bool,
        typer.Option(
            "--kill-on-exit/--keep-alive",
            help="Send a kill control frame to close the host shell on detach.",
        ),
    ] = True,
    node: NodeOption = None,
) -> None:
    """Attach to an interactive host shell on the target node over WebSocket."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        attach_console(
            client,
            "/info/terminal",
            node=node,
            takeover=False,
            kill_on_exit=kill_on_exit,
            banner="Attached to host terminal",
        )


# ---------------------------------------------------------------------------
# Samba
# ---------------------------------------------------------------------------
for spec in [  # type: ignore[assignment]
    (samba_app, "config", "GET", "/samba/config", "Show Samba global configuration."),
    (samba_app, "config-set", "PUT", "/samba/config", "Update Samba global configuration."),
    (samba_app, "shares", "GET", "/samba/shares", "List Samba shares."),
    (samba_app, "share-create", "POST", "/samba/shares", "Create a Samba share."),
    (samba_app, "share-update", "PUT", "/samba/shares/{id}", "Update a Samba share.", "id"),
    (samba_app, "share-delete", "DELETE", "/samba/shares/{id}", "Delete a Samba share.", "id"),
    (
        samba_app,
        "share-enable",
        "PUT",
        "/samba/shares/{id}/enabled",
        "Enable or disable a Samba share.",
        "id",
    ),
    (samba_app, "audit-logs", "GET", "/samba/audit-logs", "Show Samba audit logs."),
]:
    _add(*spec)


# ---------------------------------------------------------------------------
# iSCSI
# ---------------------------------------------------------------------------
for spec in [  # type: ignore[assignment]
    (iscsi_app, "initiators", "GET", "/iscsi/initiators", "List iSCSI initiators."),
    (iscsi_app, "initiator-create", "POST", "/iscsi/initiators", "Create an iSCSI initiator."),
    (
        iscsi_app,
        "initiator-update",
        "PUT",
        "/iscsi/initiators/{id}",
        "Update an iSCSI initiator.",
        "id",
    ),
    (
        iscsi_app,
        "initiator-delete",
        "DELETE",
        "/iscsi/initiators/{id}",
        "Delete an iSCSI initiator.",
        "id",
    ),
    (
        iscsi_app,
        "initiator-connect",
        "POST",
        "/iscsi/initiators/{id}/connect",
        "Connect an iSCSI initiator.",
        "id",
    ),
    (iscsi_app, "status", "GET", "/iscsi/status", "Show iSCSI initiator status."),
    (iscsi_app, "sessions", "GET", "/iscsi/target-sessions", "List iSCSI target sessions."),
    (iscsi_app, "targets", "GET", "/iscsi/targets", "List iSCSI targets."),
    (iscsi_app, "target-create", "POST", "/iscsi/targets", "Create an iSCSI target."),
    (
        iscsi_app,
        "target-update",
        "PUT",
        "/iscsi/targets/{targetId}",
        "Update an iSCSI target.",
        "targetId",
    ),
    (
        iscsi_app,
        "target-delete",
        "DELETE",
        "/iscsi/targets/{targetId}",
        "Delete an iSCSI target.",
        "targetId",
    ),
    (
        iscsi_app,
        "lun-add",
        "POST",
        "/iscsi/targets/{targetId}/luns",
        "Add a target LUN.",
        "targetId",
    ),
    (
        iscsi_app,
        "lun-remove",
        "DELETE",
        "/iscsi/targets/{targetId}/luns/{lunId}",
        "Remove a target LUN.",
        "targetId lunId",
    ),
    (
        iscsi_app,
        "portal-add",
        "POST",
        "/iscsi/targets/{targetId}/portals",
        "Add a target portal.",
        "targetId",
    ),
    (
        iscsi_app,
        "portal-remove",
        "DELETE",
        "/iscsi/targets/{targetId}/portals/{portalId}",
        "Remove a target portal.",
        "targetId portalId",
    ),
]:
    _add(*spec)


# ---------------------------------------------------------------------------
# DDNS and mDNS
# ---------------------------------------------------------------------------
for spec in [  # type: ignore[assignment]
    (ddns_app, "list", "GET", "/dynamic-dns/entries", "List dynamic DNS entries."),
    (ddns_app, "create", "POST", "/dynamic-dns/entries", "Create a dynamic DNS entry."),
    (ddns_app, "update", "PUT", "/dynamic-dns/entries/{id}", "Update a dynamic DNS entry.", "id"),
    (
        ddns_app,
        "delete",
        "DELETE",
        "/dynamic-dns/entries/{id}",
        "Delete a dynamic DNS entry.",
        "id",
    ),
    (
        ddns_app,
        "sync",
        "POST",
        "/dynamic-dns/entries/{id}/sync",
        "Synchronize a dynamic DNS entry.",
        "id",
    ),
    (mdns_app, "config", "GET", "/mdns/config", "Show mDNS settings."),
    (mdns_app, "config-set", "PUT", "/mdns/config", "Update mDNS settings."),
    (mdns_app, "records", "GET", "/mdns/records", "List mDNS records."),
    (mdns_app, "record-create", "POST", "/mdns/records", "Create an mDNS record."),
    (mdns_app, "record-update", "PUT", "/mdns/records/{id}", "Update an mDNS record.", "id"),
    (mdns_app, "record-delete", "DELETE", "/mdns/records/{id}", "Delete an mDNS record.", "id"),
]:
    _add(*spec)


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------
for spec in [  # type: ignore[assignment]
    (notifications_app, "list", "GET", "/notifications", "List notifications."),
    (notifications_app, "count", "GET", "/notifications/count", "Count active notifications."),
    (
        notifications_app,
        "dismiss-all",
        "POST",
        "/notifications/dismiss-all",
        "Dismiss all notifications.",
    ),
    (
        notifications_app,
        "dismiss",
        "POST",
        "/notifications/{id}/dismiss",
        "Dismiss a notification.",
        "id",
    ),
    (notifications_app, "rules", "GET", "/notifications/rules", "List notification rules."),
    (
        notifications_app,
        "rules-update",
        "PUT",
        "/notifications/rules",
        "Update notification rules.",
    ),
    (
        notifications_app,
        "rule-create",
        "POST",
        "/notifications/rules",
        "Create a notification rule.",
    ),
    (
        notifications_app,
        "rule-update",
        "PUT",
        "/notifications/rules/{id}",
        "Update a notification rule.",
        "id",
    ),
    (
        notifications_app,
        "rule-delete",
        "DELETE",
        "/notifications/rules/{id}",
        "Delete a notification rule.",
        "id",
    ),
    (
        notifications_app,
        "rules-bulk-delete",
        "POST",
        "/notifications/rules/bulk-delete",
        "Bulk-delete notification rules.",
    ),
    (
        notifications_app,
        "rules-bulk-update",
        "POST",
        "/notifications/rules/bulk-update",
        "Bulk-update notification rules.",
    ),
    (
        notifications_app,
        "rule-test",
        "POST",
        "/notifications/rules/test",
        "Test a notification rule.",
    ),
    (
        notifications_app,
        "transports",
        "GET",
        "/notifications/transports",
        "List notification transports.",
    ),
    (
        notifications_app,
        "transport-create",
        "POST",
        "/notifications/transports",
        "Create a notification transport.",
    ),
    (
        notifications_app,
        "transport-update",
        "PUT",
        "/notifications/transports/{id}",
        "Update a notification transport.",
        "id",
    ),
    (
        notifications_app,
        "transport-delete",
        "DELETE",
        "/notifications/transports/{id}",
        "Delete a notification transport.",
        "id",
    ),
    (
        notifications_app,
        "transport-test",
        "POST",
        "/notifications/transports/{id}/test",
        "Test a notification transport.",
        "id",
    ),
]:
    _add(*spec)


# ---------------------------------------------------------------------------
# Users, groups, and auth
# ---------------------------------------------------------------------------
for spec in [  # type: ignore[assignment]
    (user_app, "list", "GET", "/auth/users", "List users."),
    (user_app, "create", "POST", "/auth/users", "Create a local user."),
    (
        user_app,
        "capabilities",
        "GET",
        "/auth/users/capabilities",
        "Show user-management capabilities.",
    ),
    (user_app, "import", "POST", "/auth/users/import", "Import a Unix user."),
    (user_app, "importable", "GET", "/auth/users/importable", "List importable Unix users."),
    (user_app, "pam-create", "POST", "/auth/users/pam", "Create a PAM user."),
    (user_app, "next-uid", "GET", "/auth/users/uid/next", "Show the next Unix UID."),
    (user_app, "update", "PUT", "/auth/users/{userId}", "Update a user.", "userId"),
    (user_app, "delete", "DELETE", "/auth/users/{userId}", "Delete a user.", "userId"),
    (user_app, "passkeys", "GET", "/auth/users/{userId}/passkeys", "List user passkeys.", "userId"),
    (
        user_app,
        "passkey-delete",
        "DELETE",
        "/auth/users/{userId}/passkeys/{credentialId}",
        "Delete a user passkey.",
        "userId credentialId",
    ),
    (group_app, "list", "GET", "/auth/groups", "List groups."),
    (group_app, "create", "POST", "/auth/groups", "Create a group."),
    (group_app, "delete", "DELETE", "/auth/groups/{groupId}", "Delete a group.", "groupId"),
    (
        group_app,
        "members",
        "PUT",
        "/auth/groups/{groupId}/members",
        "Replace group members.",
        "groupId",
    ),
    (auth_app, "login-config", "GET", "/auth/login/config", "Show login configuration."),
    (auth_app, "sse-token", "POST", "/auth/sse-tokens", "Create an SSE token."),
    (auth_app, "passkey-login-begin", "POST", "/auth/passkeys/login/begin", "Begin passkey login."),
    (
        auth_app,
        "passkey-login-finish",
        "POST",
        "/auth/passkeys/login/finish",
        "Finish passkey login.",
    ),
    (
        auth_app,
        "passkey-register-begin",
        "POST",
        "/auth/passkeys/register/begin",
        "Begin passkey registration.",
    ),
    (
        auth_app,
        "passkey-register-finish",
        "POST",
        "/auth/passkeys/register/finish",
        "Finish passkey registration.",
    ),
    (
        cloud_init_app,
        "templates",
        "GET",
        "/utilities/cloud-init/templates",
        "List cloud-init templates.",
    ),
    (
        cloud_init_app,
        "template-create",
        "POST",
        "/utilities/cloud-init/templates",
        "Create a cloud-init template.",
    ),
    (
        cloud_init_app,
        "template-update",
        "PUT",
        "/utilities/cloud-init/templates/{templateId}",
        "Update a cloud-init template.",
        "templateId",
    ),
    (
        cloud_init_app,
        "template-delete",
        "DELETE",
        "/utilities/cloud-init/templates/{templateId}",
        "Delete a cloud-init template.",
        "templateId",
    ),
]:
    _add(*spec)
