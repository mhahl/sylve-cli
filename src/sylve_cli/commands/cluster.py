"""Cluster status, Raft consensus, resources, notes, and enrollment commands."""

from __future__ import annotations

from typing import Annotated, Any

import typer

from sylve_cli.formatter import (
    ColumnSpec,
    OutputFormat,
    console,
    format_percent,
    format_vm_state,
    print_dict,
    print_list,
)
from sylve_cli.state import CLIState, ColumnsOption, FormatOption, LongOption, SortColumnOption

cluster_app = typer.Typer(
    name="cluster",
    help="Query and manage cluster status, Raft consensus, resources, and notes.",
    no_args_is_help=True,
    rich_markup_mode=None,
)

cluster_note_app = typer.Typer(
    name="note",
    help="Manage cluster-wide notes.",
    no_args_is_help=True,
    rich_markup_mode=None,
)
cluster_app.add_typer(cluster_note_app, name="note")


@cluster_app.command("show")
@cluster_app.command("status")
def cluster_show(
    ctx: typer.Context,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
    long: LongOption = False,
) -> None:
    """Show cluster status, Raft leader, quorum members, and node health summary."""
    state: CLIState = ctx.obj
    with state.get_client() as client:
        details = client.get("/cluster") or {}
        nodes = client.get_cluster_nodes()

    cluster_cfg = details.get("cluster") if isinstance(details.get("cluster"), dict) else {}
    raft_nodes = details.get("nodes") if isinstance(details.get("nodes"), list) else []

    online_count = sum(
        1 for n in nodes if str(n.get("status") or "").lower() == "online"
    )
    total_guests = sum(len(n.get("guestIDs") or []) for n in nodes)

    summary: dict[str, Any] = {
        "enabled": bool(cluster_cfg.get("enabled", False)),
        "node_id": details.get("nodeId") or "",
        "leader_id": details.get("leaderId") or "",
        "leader_address": details.get("leaderAddress") or "",
        "raft_ip": cluster_cfg.get("raftIP") or "",
        "raft_port": cluster_cfg.get("raftPort") or "",
        "partial": bool(details.get("partial", False)),
        "nodes_online": f"{online_count}/{len(nodes)}",
        "total_guests": total_guests,
        "raft_members": raft_nodes,
        "nodes": nodes,
    }

    if fmt in (OutputFormat.json, OutputFormat.yaml):
        print_dict(summary, fmt=fmt, selected_columns=columns)
        return

    top_info = {k: v for k, v in summary.items() if k not in ("raft_members", "nodes")}
    print_dict(top_info, fmt=fmt, selected_columns=columns, title="Cluster Status")

    if raft_nodes and fmt == OutputFormat.table:
        raft_cols = [
            ColumnSpec("Raft Node ID", "id"),
            ColumnSpec("Address", "address"),
            ColumnSpec("Leader", "isLeader"),
            ColumnSpec("Suffrage", "suffrage"),
            ColumnSpec("Guests", "guestIDs", formatter=lambda g: str(len(g or []))),
        ]
        print_list(raft_nodes, raft_cols, fmt=fmt, title="Raft Consensus Members")

    if nodes and fmt == OutputFormat.table:
        node_cols = [
            ColumnSpec("Hostname", "hostname"),
            ColumnSpec("Status", "status"),
            ColumnSpec("CPU%", "cpuUsage", formatter=format_percent, justify="right"),
            ColumnSpec("RAM%", "memoryUsage", formatter=format_percent, justify="right"),
            ColumnSpec("Disk%", "diskUsage", formatter=format_percent, justify="right"),
            ColumnSpec("Guests", "guestIDs", formatter=lambda g: str(len(g or [])), justify="right"),
            ColumnSpec("Version", "sylveVersion"),
        ]
        if long:
            node_cols = [
                ColumnSpec("Hostname", "hostname"),
                ColumnSpec("Node UUID", "nodeUUID"),
                ColumnSpec("Status", "status"),
                ColumnSpec("API", "api"),
                ColumnSpec("CPU%", "cpuUsage", formatter=format_percent, justify="right"),
                ColumnSpec("RAM%", "memoryUsage", formatter=format_percent, justify="right"),
                ColumnSpec("Disk%", "diskUsage", formatter=format_percent, justify="right"),
                ColumnSpec("Guests", "guestIDs", formatter=lambda g: str(len(g or [])), justify="right"),
                ColumnSpec("Version", "sylveVersion"),
            ]
        print_list(nodes, node_cols, fmt=fmt, title="Cluster Nodes")


@cluster_app.command("resources")
def cluster_resources(
    ctx: typer.Context,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
    sort_column: SortColumnOption = None,
    long: LongOption = False,
) -> None:
    """List all guests (VMs & Jails) and templates across all cluster nodes."""
    state: CLIState = ctx.obj
    with state.get_client() as client:
        res_list = client.get_cluster_resources()

    rows: list[dict[str, Any]] = []
    for node_entry in res_list:
        host = str(node_entry.get("hostname") or "")
        uuid = str(node_entry.get("nodeUUID") or "")
        for vm in node_entry.get("vms") or []:
            rows.append(
                {
                    "id": vm.get("rid"),
                    "name": vm.get("name"),
                    "type": "vm",
                    "state": format_vm_state(vm.get("state")),
                    "node": host,
                    "node_uuid": uuid,
                }
            )
        for jail in node_entry.get("jails") or []:
            rows.append(
                {
                    "id": jail.get("ctId"),
                    "name": jail.get("name"),
                    "type": f"jail ({jail.get('type') or 'freebsd'})",
                    "state": str(jail.get("state") or "").upper(),
                    "node": host,
                    "node_uuid": uuid,
                }
            )
        for vmt in node_entry.get("vmTemplates") or []:
            rows.append(
                {
                    "id": vmt.get("id"),
                    "name": vmt.get("name"),
                    "type": "vm-template",
                    "state": "TEMPLATE",
                    "node": host,
                    "node_uuid": uuid,
                }
            )
        for jt in node_entry.get("jailTemplates") or []:
            rows.append(
                {
                    "id": jt.get("id"),
                    "name": jt.get("name"),
                    "type": "jail-template",
                    "state": "TEMPLATE",
                    "node": host,
                    "node_uuid": uuid,
                }
            )

    spec = [
        ColumnSpec("ID", "id", justify="right"),
        ColumnSpec("Name", "name"),
        ColumnSpec("Type", "type"),
        ColumnSpec("State", "state"),
        ColumnSpec("Node", "node"),
    ]
    if long:
        spec.append(ColumnSpec("Node UUID", "node_uuid"))
    print_list(
        rows,
        spec,
        fmt=fmt,
        selected_columns=columns,
        sort_column=sort_column,
        title="Cluster Resources",
    )


@cluster_app.command("resync")
def cluster_resync(
    ctx: typer.Context,
    fmt: FormatOption = OutputFormat.table,
) -> None:
    """Audit all Raft members and resynchronize divergent follower nodes."""
    state: CLIState = ctx.obj
    with state.get_client() as client:
        data = client.post("/cluster/resync-state")

    if isinstance(data, dict):
        members = data.get("members") if isinstance(data.get("members"), list) else []
        if fmt == OutputFormat.table and members:
            print_dict(
                {
                    "leaderNodeId": data.get("leaderNodeId"),
                    "referenceAppliedIndex": data.get("referenceAppliedIndex"),
                    "referenceDigest": data.get("referenceDigest"),
                },
                fmt=fmt,
                title="Cluster State Resync Summary",
            )
            cols = [
                ColumnSpec("Node ID", "nodeId"),
                ColumnSpec("Address", "address"),
                ColumnSpec("Suffrage", "suffrage"),
                ColumnSpec("Applied Index", "appliedIndex", justify="right"),
                ColumnSpec("Status", "status"),
                ColumnSpec("Digest", "digest"),
                ColumnSpec("Error", "error"),
            ]
            print_list(members, cols, fmt=fmt, title="Member Resync Results")
            return
        print_dict(data, fmt=fmt, title="Cluster Resync Result")
    else:
        console.print("[green]Cluster state resync completed.[/green]")


@cluster_app.command("create")
def cluster_create(
    ctx: typer.Context,
    ip: Annotated[str, typer.Option("--ip", help="Bootstrap Raft IP address for this node.")],
) -> None:
    """Initialize a new Sylve cluster on the current node."""
    state: CLIState = ctx.obj
    with state.get_client() as client:
        client.post("/cluster", json_body={"ip": ip})
    console.print(f"[green]Cluster created[/green] with bootstrap IP [bold]{ip}[/bold].")


@cluster_app.command("join-key")
def cluster_join_key(
    ctx: typer.Context,
    fmt: FormatOption = OutputFormat.table,
) -> None:
    """Reveal the cluster join key for enrolling additional nodes."""
    state: CLIState = ctx.obj
    with state.get_client() as client:
        data = client.get("/cluster/join-key")
    if isinstance(data, dict):
        print_dict(data, fmt=fmt, title="Cluster Join Key")
    else:
        console.print(str(data))


@cluster_app.command("join")
def cluster_join(
    ctx: typer.Context,
    leader_ip: Annotated[str, typer.Option("--leader-ip", help="IP address of the cluster leader.")],
    node_ip: Annotated[str, typer.Option("--node-ip", help="Raft IP address of this joining node.")],
    node_id: Annotated[str, typer.Option("--node-id", help="Node UUID of this joining node.")],
    cluster_key: Annotated[str, typer.Option("--cluster-key", help="Cluster join key.")],
) -> None:
    """Join this node to an existing Sylve cluster."""
    state: CLIState = ctx.obj
    with state.get_client() as client:
        client.post(
            "/cluster/join",
            json_body={
                "leaderIp": leader_ip,
                "nodeIp": node_ip,
                "nodeId": node_id,
                "clusterKey": cluster_key,
            },
        )
    console.print(f"[green]Node joined cluster via leader {leader_ip}.[/green]")


@cluster_app.command("leave")
def cluster_leave(
    ctx: typer.Context,
    retain_guests: Annotated[
        bool,
        typer.Option("--retain-guests/--no-retain-guests", help="Keep local VM and jail registrations."),
    ] = True,
    force: Annotated[
        bool,
        typer.Option("--force", help="Force local cluster reset without contacting Raft."),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option("-y", "--yes", help="Skip confirmation prompt."),
    ] = False,
) -> None:
    """Remove the current node from the cluster and clear its cluster state."""
    if not yes:
        typer.confirm("Are you sure you want this node to leave the cluster?", abort=True)
    state: CLIState = ctx.obj
    with state.get_client() as client:
        if force:
            client.delete(
                "/cluster/reset-node/force",
                json_body={"acknowledgeMembershipRepair": True, "nodeExternallyFenced": True},
            )
        else:
            client.delete("/cluster/reset-node", json_body={"retainGuests": retain_guests})
    console.print("[green]Node has left the cluster.[/green]")


@cluster_note_app.command("list")
def cluster_note_list(
    ctx: typer.Context,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
    long: LongOption = False,
) -> None:
    """List all cluster notes."""
    state: CLIState = ctx.obj
    with state.get_client() as client:
        notes = client.get("/cluster/notes") or []
    spec = [
        ColumnSpec("ID", "id", justify="right"),
        ColumnSpec("Title", "title"),
        ColumnSpec("Updated At", "updatedAt"),
    ]
    if long:
        spec.insert(2, ColumnSpec("Content", "content"))
    print_list(notes if isinstance(notes, list) else [], spec, fmt=fmt, selected_columns=columns, title="Cluster Notes")


@cluster_note_app.command("create")
def cluster_note_create(
    ctx: typer.Context,
    title: Annotated[str, typer.Option("--title", "-t", help="Note title (3-128 chars).")],
    content: Annotated[str, typer.Option("--content", "-m", help="Note body content.")],
) -> None:
    """Create a new cluster note."""
    state: CLIState = ctx.obj
    with state.get_client() as client:
        client.post("/cluster/notes", json_body={"title": title, "content": content})
    console.print(f"[green]Created cluster note '{title}'.[/green]")


@cluster_note_app.command("delete")
def cluster_note_delete(
    ctx: typer.Context,
    note_id: Annotated[int, typer.Argument(help="Cluster note ID to delete.")],
) -> None:
    """Delete a cluster note by ID."""
    state: CLIState = ctx.obj
    with state.get_client() as client:
        client.delete(f"/cluster/notes/{note_id}")
    console.print(f"[green]Deleted cluster note #{note_id}.[/green]")
