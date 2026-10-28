"""Network management commands: interfaces, switches, routes, DHCP, firewall, objects, WireGuard."""

from __future__ import annotations

import json
import sys
import time
from typing import Annotated, Any

import typer
import yaml

from sylve_cli.formatter import (
    ColumnSpec,
    OutputFormat,
    console,
    print_dict,
    print_list,
)
from sylve_cli.state import (
    CLIState,
    ColumnsOption,
    FormatOption,
    LongOption,
    NodeOption,
    SortColumnOption,
)

network_app = typer.Typer(
    name="network",
    help="Query and manage network interfaces, switches, routes, DHCP, firewall, and WireGuard.",
    no_args_is_help=True,
    rich_markup_mode=None,
)

iface_app = typer.Typer(
    name="interface",
    help="Query host network interfaces and L3 addresses.",
    no_args_is_help=True,
    rich_markup_mode=None,
)
switch_app = typer.Typer(
    name="switch",
    help="Query and manage standard and manual network switches.",
    no_args_is_help=True,
    rich_markup_mode=None,
)
route_app = typer.Typer(
    name="route",
    help="Query and manage static routes.",
    no_args_is_help=True,
    rich_markup_mode=None,
)
dhcp_app = typer.Typer(
    name="dhcp",
    help="Query and manage DHCP configuration, ranges, and leases.",
    no_args_is_help=True,
    rich_markup_mode=None,
)
firewall_app = typer.Typer(
    name="firewall",
    help="Query PF firewall traffic rules, NAT rules, counters, and live logs.",
    no_args_is_help=True,
    rich_markup_mode=None,
)
object_app = typer.Typer(
    name="object",
    help="Query and manage network/firewall alias objects.",
    no_args_is_help=True,
    rich_markup_mode=None,
)
wg_app = typer.Typer(
    name="wireguard",
    help="Query WireGuard VPN server, peers, and outbound clients.",
    no_args_is_help=True,
    rich_markup_mode=None,
)

network_app.add_typer(iface_app, name="interface")
network_app.add_typer(switch_app, name="switch")
network_app.add_typer(route_app, name="route")
network_app.add_typer(dhcp_app, name="dhcp")
network_app.add_typer(firewall_app, name="firewall")
network_app.add_typer(object_app, name="object")
network_app.add_typer(wg_app, name="wireguard")


def _format_ip_list(ips: Any) -> str:
    if not isinstance(ips, list):
        return ""
    out: list[str] = []
    for item in ips:
        if isinstance(item, dict):
            ip = item.get("ip") or item.get("address") or ""
            netmask = item.get("netmask") or item.get("prefixLength") or ""
            if ip:
                out.append(f"{ip}/{netmask}" if netmask else str(ip))
        elif item:
            out.append(str(item))
    return ", ".join(out)


# ------------------------------------------------------------------
# Interfaces
# ------------------------------------------------------------------
@iface_app.command("list")
def iface_list(
    ctx: typer.Context,
    node: NodeOption = None,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
    sort_column: SortColumnOption = None,
    long: LongOption = False,
) -> None:
    """List physical and virtual network interfaces across cluster nodes."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        results = client.fan_out_get("/network/interface", node=node)

    rows: list[dict[str, Any]] = []
    for host, data in results:
        if isinstance(data, list):
            for iface in data:
                if not isinstance(iface, dict):
                    continue
                rows.append(
                    {
                        "name": iface.get("name"),
                        "node": host,
                        "model": iface.get("model") or iface.get("driver") or "",
                        "mac": iface.get("ether") or iface.get("hwaddr") or "",
                        "mtu": iface.get("mtu"),
                        "ipv4": _format_ip_list(iface.get("ipv4")),
                        "ipv6": _format_ip_list(iface.get("ipv6")),
                        "groups": ", ".join(iface.get("groups") or []),
                        "description": iface.get("description") or "",
                    }
                )

    spec = [
        ColumnSpec("Name", "name"),
        ColumnSpec("Node", "node"),
        ColumnSpec("IPv4", "ipv4"),
        ColumnSpec("IPv6", "ipv6"),
        ColumnSpec("Description", "description"),
    ]
    if long:
        spec = [
            ColumnSpec("Name", "name"),
            ColumnSpec("Node", "node"),
            ColumnSpec("MAC", "mac"),
            ColumnSpec("MTU", "mtu", justify="right"),
            ColumnSpec("IPv4", "ipv4"),
            ColumnSpec("IPv6", "ipv6"),
            ColumnSpec("Groups", "groups"),
            ColumnSpec("Description", "description"),
        ]
    print_list(
        rows,
        spec,
        fmt=fmt,
        selected_columns=columns,
        sort_column=sort_column,
        title="Network Interfaces",
    )


@iface_app.command("l3")
def iface_l3(
    ctx: typer.Context,
    node: NodeOption = None,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
) -> None:
    """List managed host interface Layer-3 IP configurations."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        data = client.get("/network/interface/l3", node=node) or {}
    if (
        isinstance(data, dict)
        and isinstance(data.get("entries"), list)
        and fmt == OutputFormat.table
    ):
        spec = [
            ColumnSpec("Interface", "name"),
            ColumnSpec("DHCP", "dhcp"),
            ColumnSpec("SLAAC", "slaac"),
            ColumnSpec("MTU", "mtu", justify="right"),
            ColumnSpec("Revision", "revision", justify="right"),
        ]
        print_list(
            data["entries"], spec, fmt=fmt, selected_columns=columns, title="Host L3 Interfaces"
        )
    elif isinstance(data, dict):
        print_dict(data, fmt=fmt, selected_columns=columns, title="Host L3 Configuration")
    else:
        console.print(str(data))


# ------------------------------------------------------------------
# Switches
# ------------------------------------------------------------------
@switch_app.command("list")
def switch_list(
    ctx: typer.Context,
    node: NodeOption = None,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
    sort_column: SortColumnOption = None,
    long: LongOption = False,
) -> None:
    """List standard and manual network switches across the cluster."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        results = client.fan_out_get("/network/switch", node=node)

    rows: list[dict[str, Any]] = []
    for host, data in results:
        if not isinstance(data, dict):
            continue
        for sw in data.get("standard") or []:
            if not isinstance(sw, dict):
                continue
            ports = [
                str(p.get("name") if isinstance(p, dict) else p) for p in (sw.get("ports") or [])
            ]
            rows.append(
                {
                    "id": sw.get("id"),
                    "name": sw.get("name"),
                    "type": "standard",
                    "bridge": sw.get("bridgeName") or "",
                    "node": host,
                    "vlan": sw.get("vlan") or sw.get("defaultAccessVlan") or "-",
                    "vlan_filtering": bool(sw.get("vlanFiltering")),
                    "address": sw.get("address") or ("DHCP" if sw.get("dhcp") else "-"),
                    "ports": ", ".join(ports),
                    "private": bool(sw.get("private")),
                }
            )
        for msw in data.get("manual") or []:
            if not isinstance(msw, dict):
                continue
            rows.append(
                {
                    "id": msw.get("id"),
                    "name": msw.get("name"),
                    "type": "manual",
                    "bridge": msw.get("bridge") or "",
                    "node": host,
                    "vlan": msw.get("defaultAccessVlan") or "-",
                    "vlan_filtering": bool(msw.get("vlanFiltering")),
                    "address": "-",
                    "ports": "-",
                    "private": False,
                }
            )

    spec = [
        ColumnSpec("ID", "id", justify="right"),
        ColumnSpec("Name", "name"),
        ColumnSpec("Type", "type"),
        ColumnSpec("Node", "node"),
        ColumnSpec("VLAN", "vlan", justify="right"),
        ColumnSpec("Private", "private"),
    ]
    if long:
        spec = [
            ColumnSpec("ID", "id", justify="right"),
            ColumnSpec("Name", "name"),
            ColumnSpec("Type", "type"),
            ColumnSpec("Bridge", "bridge"),
            ColumnSpec("Node", "node"),
            ColumnSpec("VLAN", "vlan", justify="right"),
            ColumnSpec("VLAN Filter", "vlan_filtering"),
            ColumnSpec("Address", "address"),
            ColumnSpec("Ports", "ports"),
            ColumnSpec("Private", "private"),
        ]
    print_list(
        rows,
        spec,
        fmt=fmt,
        selected_columns=columns,
        sort_column=sort_column,
        title="Network Switches",
    )


@switch_app.command("create-standard")
def switch_create_standard(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", help="Switch name.")],
    ports: Annotated[
        list[str] | None,
        typer.Option("--port", "-p", help="Bridge member port interface(s) (repeatable)."),
    ] = None,
    private: Annotated[
        bool,
        typer.Option("--private/--public", help="Whether switch is private (host-only)."),
    ] = False,
    dhcp: Annotated[
        bool,
        typer.Option("--dhcp/--no-dhcp", help="Enable DHCP on the switch."),
    ] = False,
    mtu: Annotated[int, typer.Option("--mtu", help="Switch MTU.")] = 1500,
    vlan: Annotated[int, typer.Option("--vlan", help="VLAN tag.")] = 0,
    vlan_filtering: Annotated[
        bool,
        typer.Option(
            "--vlan-filtering/--no-vlan-filtering", help="Enable FreeBSD bridge VLAN filtering."
        ),
    ] = False,
    default_access_vlan: Annotated[
        int,
        typer.Option(
            "--default-access-vlan", help="Default access VLAN when VLAN filtering is enabled."
        ),
    ] = 0,
    node: NodeOption = None,
) -> None:
    """Create a managed standard network switch on a node."""
    state: CLIState = ctx.obj
    payload: dict[str, Any] = {
        "name": name,
        "private": private,
        "dhcp": dhcp,
        "mtu": mtu,
        "ports": ports or [],
        "vlan": vlan,
        "vlanFiltering": vlan_filtering,
        "defaultAccessVlan": default_access_vlan,
    }
    with state.get_client(node_override=node) as client:
        client.post("/network/switch/standard", json_body=payload, node=node)
    console.print(f"[green]Created standard switch '{name}'.[/green]")


@switch_app.command("create-manual")
def switch_create_manual(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", help="Manual switch name.")],
    bridge: Annotated[
        str, typer.Option("--bridge", help="Existing host bridge interface (e.g. bridge0).")
    ],
    node: NodeOption = None,
) -> None:
    """Register an existing host bridge as a manual switch."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        client.post(
            "/network/switch/manual",
            json_body={"name": name, "bridge": bridge},
            node=node,
        )
    console.print(f"[green]Created manual switch '{name}' on bridge '{bridge}'.[/green]")


@switch_app.command("delete")
def switch_delete(
    ctx: typer.Context,
    switch_id: Annotated[int, typer.Argument(help="Switch ID to delete.")],
    switch_type: Annotated[
        str,
        typer.Option("--type", "-t", help="Switch type: 'standard' or 'manual'."),
    ] = "standard",
    node: NodeOption = None,
) -> None:
    """Delete a standard or manual network switch by ID."""
    stype = switch_type.strip().lower()
    if stype not in ("standard", "manual"):
        raise typer.BadParameter("Switch type must be 'standard' or 'manual'.")
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        client.delete(f"/network/switch/{stype}/{switch_id}", node=node)
    console.print(f"[green]Deleted {stype} switch #{switch_id}.[/green]")


@switch_app.command("sync")
def switch_sync(
    ctx: typer.Context,
    node: NodeOption = None,
) -> None:
    """Re-apply and reconcile stored switch network configuration on a node."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        target = client.resolve_node_hostname(node) or client.context.hostname or "connected node"
        client.post("/network/switch/sync", node=node)
    console.print(f"[green]Synchronized switch configuration on {target}.[/green]")


# ------------------------------------------------------------------
# Static Routes
# ------------------------------------------------------------------
@route_app.command("list")
def route_list(
    ctx: typer.Context,
    node: NodeOption = None,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
    long: LongOption = False,
) -> None:
    """List static routes across nodes."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        results = client.fan_out_get("/network/route", node=node)
    rows: list[dict[str, Any]] = []
    for host, data in results:
        if isinstance(data, list):
            for r in data:
                if isinstance(r, dict):
                    item = dict(r)
                    item.setdefault("node", host)
                    rows.append(item)
    spec = [
        ColumnSpec("ID", "id", justify="right"),
        ColumnSpec("Name", "name"),
        ColumnSpec("Node", "node"),
        ColumnSpec("Destination", "destinationRaw"),
        ColumnSpec("Gateway / NextHop", "gatewayRaw"),
        ColumnSpec("Enabled", "enabled"),
    ]
    if long:
        spec = [
            ColumnSpec("ID", "id", justify="right"),
            ColumnSpec("Name", "name"),
            ColumnSpec("Node", "node"),
            ColumnSpec("Family", "family"),
            ColumnSpec("Type", "destinationType"),
            ColumnSpec("Destination", "destinationRaw"),
            ColumnSpec("Gateway / NextHop", "gatewayRaw"),
            ColumnSpec("Interface", "interface"),
            ColumnSpec("Enabled", "enabled"),
        ]
    print_list(rows, spec, fmt=fmt, selected_columns=columns, title="Static Routes")


@route_app.command("delete")
def route_delete(
    ctx: typer.Context,
    route_id: Annotated[int, typer.Argument(help="Static route ID to delete.")],
    node: NodeOption = None,
) -> None:
    """Delete a static route by ID."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        client.delete(f"/network/route/{route_id}", node=node)
    console.print(f"[green]Deleted static route #{route_id}.[/green]")


# ------------------------------------------------------------------
# DHCP
# ------------------------------------------------------------------
@dhcp_app.command("config")
def dhcp_config(
    ctx: typer.Context,
    node: NodeOption = None,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
) -> None:
    """Show DHCP service configuration."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        data = client.get("/network/dhcp/config", node=node) or {}
    if isinstance(data, dict):
        print_dict(data, fmt=fmt, selected_columns=columns, title="DHCP Configuration")


@dhcp_app.command("range-list")
def dhcp_range_list(
    ctx: typer.Context,
    node: NodeOption = None,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
) -> None:
    """List configured DHCP address ranges."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        results = client.fan_out_get("/network/dhcp/range", node=node)
    rows: list[dict[str, Any]] = []
    for host, data in results:
        if isinstance(data, list):
            for r in data:
                if isinstance(r, dict):
                    item = dict(r)
                    item.setdefault("node", host)
                    rows.append(item)
    spec = [
        ColumnSpec("ID", "id", justify="right"),
        ColumnSpec("Node", "node"),
        ColumnSpec("Type", "type"),
        ColumnSpec("Start IP", "startIp"),
        ColumnSpec("End IP", "endIp"),
        ColumnSpec("Expiry (s)", "expiry", justify="right"),
        ColumnSpec("SLAAC", "slaac"),
    ]
    print_list(rows, spec, fmt=fmt, selected_columns=columns, title="DHCP Ranges")


@dhcp_app.command("lease-list")
def dhcp_lease_list(
    ctx: typer.Context,
    node: NodeOption = None,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
) -> None:
    """List active and static DHCP leases."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        data = client.get("/network/dhcp/lease", node=node) or {}
    if isinstance(data, list):
        spec = [
            ColumnSpec("ID", "id", justify="right"),
            ColumnSpec("Hostname", "hostname"),
            ColumnSpec("IP", "ip"),
            ColumnSpec("MAC", "mac"),
            ColumnSpec("Expiry", "expiry"),
        ]
        print_list(data, spec, fmt=fmt, selected_columns=columns, title="DHCP Leases")
    elif isinstance(data, dict):
        print_dict(data, fmt=fmt, selected_columns=columns, title="DHCP Leases")


# ------------------------------------------------------------------
# Firewall
# ------------------------------------------------------------------
@firewall_app.command("traffic-list")
def firewall_traffic_list(
    ctx: typer.Context,
    node: NodeOption = None,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
    long: LongOption = False,
) -> None:
    """List PF firewall traffic rules in evaluation order."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        results = client.fan_out_get("/network/firewall/traffic", node=node)
    rows: list[dict[str, Any]] = []
    for host, data in results:
        if isinstance(data, list):
            for r in data:
                if isinstance(r, dict):
                    item = dict(r)
                    item.setdefault("node", host)
                    rows.append(item)
    spec = [
        ColumnSpec("ID", "id", justify="right"),
        ColumnSpec("Priority", "priority", justify="right"),
        ColumnSpec("Node", "node"),
        ColumnSpec("Name", "name"),
        ColumnSpec("Action", "action"),
        ColumnSpec("Source", "sourceRaw"),
        ColumnSpec("Dest", "destRaw"),
        ColumnSpec("Enabled", "enabled"),
    ]
    if long:
        spec = [
            ColumnSpec("ID", "id", justify="right"),
            ColumnSpec("Priority", "priority", justify="right"),
            ColumnSpec("Node", "node"),
            ColumnSpec("Name", "name"),
            ColumnSpec("Action", "action"),
            ColumnSpec("Dir", "direction"),
            ColumnSpec("Proto", "protocol"),
            ColumnSpec("Source", "sourceRaw"),
            ColumnSpec("Dest", "destRaw"),
            ColumnSpec("Dst Ports", "dstPortsRaw"),
            ColumnSpec("Enabled", "enabled"),
        ]
    print_list(rows, spec, fmt=fmt, selected_columns=columns, title="Firewall Traffic Rules")


@firewall_app.command("nat-list")
def firewall_nat_list(
    ctx: typer.Context,
    node: NodeOption = None,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
    long: LongOption = False,
) -> None:
    """List PF firewall NAT rules in evaluation order."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        results = client.fan_out_get("/network/firewall/nat", node=node)
    rows: list[dict[str, Any]] = []
    for host, data in results:
        if isinstance(data, list):
            for r in data:
                if isinstance(r, dict):
                    item = dict(r)
                    item.setdefault("node", host)
                    rows.append(item)
    spec = [
        ColumnSpec("ID", "id", justify="right"),
        ColumnSpec("Priority", "priority", justify="right"),
        ColumnSpec("Node", "node"),
        ColumnSpec("Name", "name"),
        ColumnSpec("NAT Type", "natType"),
        ColumnSpec("Source", "sourceRaw"),
        ColumnSpec("Dest", "destRaw"),
        ColumnSpec("Enabled", "enabled"),
    ]
    if long:
        spec = [
            ColumnSpec("ID", "id", justify="right"),
            ColumnSpec("Priority", "priority", justify="right"),
            ColumnSpec("Node", "node"),
            ColumnSpec("Name", "name"),
            ColumnSpec("NAT Type", "natType"),
            ColumnSpec("Proto", "protocol"),
            ColumnSpec("Source", "sourceRaw"),
            ColumnSpec("Dest", "destRaw"),
            ColumnSpec("Enabled", "enabled"),
        ]
    print_list(rows, spec, fmt=fmt, selected_columns=columns, title="Firewall NAT Rules")


@firewall_app.command("logs")
def firewall_logs(
    ctx: typer.Context,
    limit: Annotated[
        int, typer.Option("--limit", "-l", help="Maximum log entries per poll (1-2000).")
    ] = 50,
    cursor: Annotated[
        int | None,
        typer.Option(
            "--cursor",
            help="Return hits after this cursor (0 starts at the current live stream position).",
        ),
    ] = None,
    follow: Annotated[
        bool,
        typer.Option("--follow", "-F", help="Poll continuously for new firewall hits."),
    ] = False,
    interval: Annotated[
        float,
        typer.Option("--interval", help="Polling interval in seconds when --follow is set."),
    ] = 1.5,
    rule_type: Annotated[
        str | None,
        typer.Option("--rule-type", help="Filter by rule type ('traffic' or 'nat')."),
    ] = None,
    rule_id: Annotated[
        int | None,
        typer.Option("--rule-id", help="Filter by rule ID."),
    ] = None,
    action: Annotated[
        str | None,
        typer.Option("--action", help="Filter by PF action (pass, block, scrub, nat, binat, rdr)."),
    ] = None,
    direction: Annotated[
        str | None,
        typer.Option("--direction", help="Filter by packet direction ('in' or 'out')."),
    ] = None,
    interface: Annotated[
        str | None, typer.Option("--interface", "-i", help="Filter by interface.")
    ] = None,
    query: Annotated[
        str | None,
        typer.Option("--query", "-q", help="Search rule name, ID, and raw log text."),
    ] = None,
    node: NodeOption = None,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
) -> None:
    """Fetch or follow live firewall rule hit logs."""
    state: CLIState = ctx.obj
    spec = [
        ColumnSpec("Time", "timestamp"),
        ColumnSpec("Action", "action"),
        ColumnSpec("Dir", "direction"),
        ColumnSpec("Interface", "interface"),
        ColumnSpec("Proto", "protocol"),
        ColumnSpec("Source", "src"),
        ColumnSpec("Destination", "dst"),
        ColumnSpec("Rule ID", "ruleId", justify="right"),
    ]

    def _extract(data: Any) -> tuple[list[dict[str, Any]], int | None]:
        raw_items: list[Any] = (
            data["items"]
            if isinstance(data, dict) and isinstance(data.get("items"), list)
            else (data if isinstance(data, list) else [])
        )
        rows = [item for item in raw_items if isinstance(item, dict)]
        next_cur: int | None = None
        if isinstance(data, dict) and data.get("nextCursor") is not None:
            next_cur = int(data["nextCursor"])
        elif rows and rows[-1].get("cursor") is not None:
            next_cur = int(rows[-1]["cursor"])
        return rows, next_cur

    base_params: dict[str, Any] = {
        "limit": limit,
        "ruleType": rule_type,
        "ruleId": rule_id,
        "action": action,
        "direction": direction,
        "interface": interface,
        "query": query,
    }

    with state.get_client(node_override=node) as client:
        if not follow:
            params = dict(base_params)
            if cursor is not None:
                params["cursor"] = cursor
            data = client.get("/network/firewall/logs/live", params=params, node=node)
            items, _ = _extract(data)
            print_list(items, spec, fmt=fmt, selected_columns=columns, title="Firewall Live Logs")
            return

        cur = 0 if cursor is None else cursor
        try:
            while True:
                params = dict(base_params, cursor=cur)
                data = client.get("/network/firewall/logs/live", params=params, node=node)
                items, next_cur = _extract(data)
                if next_cur is not None:
                    cur = next_cur
                if items:
                    if fmt == OutputFormat.json:
                        for row in items:
                            sys.stdout.write(json.dumps(row, default=str) + "\n")
                        sys.stdout.flush()
                    elif fmt == OutputFormat.yaml:
                        sys.stdout.write(yaml.safe_dump(items, sort_keys=False))
                        sys.stdout.flush()
                    elif fmt in (OutputFormat.value, OutputFormat.csv):
                        print_list(items, spec, fmt=fmt, selected_columns=columns)
                    else:
                        for row in items:
                            raw = row.get("rawLine")
                            if raw:
                                console.print(str(raw), markup=False)
                            else:
                                line = " ".join(
                                    str(row.get(k) or "-")
                                    for k in (
                                        "timestamp",
                                        "action",
                                        "direction",
                                        "interface",
                                        "ruleType",
                                        "ruleName",
                                        "ruleId",
                                    )
                                )
                                console.print(line, markup=False)
                time.sleep(max(0.2, interval))
        except KeyboardInterrupt:
            return


# ------------------------------------------------------------------
# Network Objects
# ------------------------------------------------------------------
@object_app.command("list")
def object_list(
    ctx: typer.Context,
    node: NodeOption = None,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
) -> None:
    """List configured network objects (IP/MAC/Port aliases)."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        results = client.fan_out_get("/network/object", node=node)
    rows: list[dict[str, Any]] = []
    for host, data in results:
        if isinstance(data, list):
            for obj in data:
                if isinstance(obj, dict):
                    vals = [
                        str(v.get("value") if isinstance(v, dict) else v)
                        for v in (obj.get("entries") or obj.get("values") or [])
                    ]
                    rows.append(
                        {
                            "id": obj.get("id"),
                            "name": obj.get("name"),
                            "type": obj.get("type"),
                            "values": ", ".join(vals),
                            "used": bool(obj.get("isUsed")),
                            "node": host,
                        }
                    )
    spec = [
        ColumnSpec("ID", "id", justify="right"),
        ColumnSpec("Name", "name"),
        ColumnSpec("Type", "type"),
        ColumnSpec("Values", "values"),
        ColumnSpec("In Use", "used"),
        ColumnSpec("Node", "node"),
    ]
    print_list(rows, spec, fmt=fmt, selected_columns=columns, title="Network Objects")


@object_app.command("create")
def object_create(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", help="Network object name.")],
    obj_type: Annotated[
        str, typer.Option("--type", "-t", help="Object type (e.g. Host, Network, Port, Mac).")
    ],
    values: Annotated[
        list[str], typer.Option("--value", "-v", help="Object value(s) (repeatable).")
    ],
    node: NodeOption = None,
) -> None:
    """Create a network object."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        client.post(
            "/network/object",
            json_body={"name": name, "type": obj_type, "values": values},
            node=node,
        )
    console.print(f"[green]Created network object '{name}' ({obj_type}).[/green]")


@object_app.command("delete")
def object_delete(
    ctx: typer.Context,
    object_id: Annotated[int, typer.Argument(help="Network object ID.")],
    node: NodeOption = None,
) -> None:
    """Delete a network object by ID."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        client.delete(f"/network/object/{object_id}", node=node)
    console.print(f"[green]Deleted network object #{object_id}.[/green]")


# ------------------------------------------------------------------
# WireGuard
# ------------------------------------------------------------------
@wg_app.command("status")
def wg_status(
    ctx: typer.Context,
    node: NodeOption = None,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
) -> None:
    """Show WireGuard server configuration and runtime status."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        data = client.get("/network/wireguard/server", node=node) or {}
    if isinstance(data, dict):
        print_dict(data, fmt=fmt, selected_columns=columns, title="WireGuard Server")


@wg_app.command("client-list")
def wg_client_list(
    ctx: typer.Context,
    node: NodeOption = None,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
) -> None:
    """List outbound WireGuard clients."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        results = client.fan_out_get("/network/wireguard/clients", node=node)
    rows: list[dict[str, Any]] = []
    for host, data in results:
        if isinstance(data, list):
            for c in data:
                if isinstance(c, dict):
                    item = dict(c)
                    item.setdefault("node", host)
                    rows.append(item)
    spec = [
        ColumnSpec("ID", "id", justify="right"),
        ColumnSpec("Name", "name"),
        ColumnSpec("Node", "node"),
        ColumnSpec("Endpoint", "endpoint"),
        ColumnSpec("Enabled", "enabled"),
    ]
    print_list(rows, spec, fmt=fmt, selected_columns=columns, title="WireGuard Clients")
