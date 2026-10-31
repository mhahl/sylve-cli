"""FreeBSD Jail management commands."""

from __future__ import annotations

from typing import Annotated, Any

import typer

from sylve_cli.client import SylveClient, SylveError
from sylve_cli.console_ws import attach_console
from sylve_cli.formatter import (
    ColumnSpec,
    OutputFormat,
    console,
    format_bytes,
    format_timestamp,
    print_dict,
    print_list,
    print_result,
)
from sylve_cli.state import (
    CLIState,
    ColumnsOption,
    FilterOption,
    FormatOption,
    LimitOption,
    LongOption,
    NodeOption,
    SortColumnOption,
    WaitOption,
    YesOption,
    confirm_destructive,
)
from sylve_cli.tasks import wait_for_lifecycle_task

jail_app = typer.Typer(
    name="jail",
    help="Query, start, stop, restart, migrate, snapshot, and manage FreeBSD Jails.",
    no_args_is_help=True,
    rich_markup_mode=None,
)

jail_snapshot_app = typer.Typer(
    name="snapshot",
    help="Manage ZFS snapshots for a FreeBSD jail.",
    no_args_is_help=True,
    rich_markup_mode=None,
)
jail_bootstrap_app = typer.Typer(
    name="bootstrap",
    help="Manage pkgbase FreeBSD jail bootstraps.",
    no_args_is_help=True,
    rich_markup_mode=None,
)
jail_template_app = typer.Typer(
    name="template",
    help="Manage jail templates.",
    no_args_is_help=True,
    rich_markup_mode=None,
)

jail_app.add_typer(jail_snapshot_app, name="snapshot")
jail_app.add_typer(jail_bootstrap_app, name="bootstrap")
jail_app.add_typer(jail_template_app, name="template")


def _run_jail_action(
    client: SylveClient,
    action: str,
    jails: list[str],
    node: str | None,
    wait: bool,
) -> None:
    for ident in jails:
        ctid, host, _ = client.resolve_jail(ident, node=node)
        resp = client.post(f"/jail/{ctid}/actions/{action}", node=host or None)
        task_id = resp.get("taskId") if isinstance(resp, dict) else None
        outcome = resp.get("outcome") if isinstance(resp, dict) else "queued"
        if wait and task_id:
            wait_for_lifecycle_task(client, int(task_id), node=host or None)
            console.print(
                f"[green]Jail {ctid}[/green] ({host or 'local'}): [bold]{action}[/bold] completed."
            )
        else:
            task_note = f" (task #{task_id})" if task_id else ""
            console.print(
                f"[cyan]Jail {ctid}[/cyan] ({host or 'local'}): [bold]{action}[/bold] {outcome}{task_note}."
            )


@jail_app.command("list")
def jail_list(
    ctx: typer.Context,
    node: NodeOption = None,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
    sort_column: SortColumnOption = None,
    long: LongOption = False,
    filters: FilterOption = None,
    limit: LimitOption = None,
) -> None:
    """List jails across all cluster nodes (or a specific node with --node)."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        rows: list[dict[str, Any]] = []
        target_host = client.resolve_node_hostname(node)
        for node_res in client.get_cluster_resources():
            host = str(node_res.get("hostname") or "")
            if target_host and host.lower() != target_host.lower():
                continue
            for jail in node_res.get("jails") or []:
                if not isinstance(jail, dict):
                    continue
                rows.append(
                    {
                        "ctId": jail.get("ctId"),
                        "name": jail.get("name"),
                        "state": str(jail.get("state") or "UNKNOWN").upper(),
                        "type": jail.get("type") or "freebsd",
                        "node": host,
                        "cores": jail.get("cores") or "-",
                        "memory": jail.get("memory"),
                        "resourceLimits": bool(jail.get("resourceLimits")),
                    }
                )

    spec = [
        ColumnSpec("CTID", "ctId", justify="right"),
        ColumnSpec("Name", "name"),
        ColumnSpec("State", "state"),
        ColumnSpec("Type", "type"),
        ColumnSpec("Node", "node"),
        ColumnSpec("Cores", "cores", justify="right"),
        ColumnSpec("Memory", "memory", formatter=format_bytes, justify="right"),
    ]
    if long:
        spec.append(ColumnSpec("Limits", "resourceLimits"))
    print_list(
        rows,
        spec,
        fmt=fmt,
        selected_columns=columns,
        sort_column=sort_column,
        title="FreeBSD Jails",
        filters=filters,
        limit=limit,
    )


@jail_app.command("show")
def jail_show(
    ctx: typer.Context,
    jail: Annotated[str, typer.Argument(help="Jail CTID or name.")],
    node: NodeOption = None,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
) -> None:
    """Display full configuration and status of a jail."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        ctid, host, summary = client.resolve_jail(jail, node=node)
        data = client.get(f"/jail/{ctid}", node=host or None)
        if not isinstance(data, dict):
            raise SylveError(
                f"Unexpected response showing Jail {ctid}. "
                "Re-run with -f json to inspect the response, or report it with your server version."
            )
        data["state"] = summary.get("state") or data.get("state") or "UNKNOWN"
        data["node"] = host or client.context.hostname or "local"

    print_dict(
        data,
        fmt=fmt,
        selected_columns=columns,
        title=f"Jail {data.get('name')} (CTID {ctid} on {data.get('node')})",
    )


@jail_app.command("start")
def jail_start(
    ctx: typer.Context,
    jails: Annotated[list[str], typer.Argument(help="One or more Jail CTIDs or names to start.")],
    node: NodeOption = None,
    wait: WaitOption = False,
) -> None:
    """Start one or more jails."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        _run_jail_action(client, "start", jails, node=node, wait=wait)


@jail_app.command("stop")
def jail_stop(
    ctx: typer.Context,
    jails: Annotated[list[str], typer.Argument(help="One or more Jail CTIDs or names to stop.")],
    node: NodeOption = None,
    wait: WaitOption = False,
) -> None:
    """Stop one or more jails."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        _run_jail_action(client, "stop", jails, node=node, wait=wait)


@jail_app.command("restart")
def jail_restart(
    ctx: typer.Context,
    jails: Annotated[list[str], typer.Argument(help="One or more Jail CTIDs or names to restart.")],
    node: NodeOption = None,
    wait: WaitOption = False,
) -> None:
    """Restart one or more jails."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        _run_jail_action(client, "restart", jails, node=node, wait=wait)


@jail_app.command("migrate")
def jail_migrate(
    ctx: typer.Context,
    jail: Annotated[str, typer.Argument(help="Jail CTID or name to migrate.")],
    target: Annotated[
        str, typer.Option("--target", "-t", help="Target cluster node hostname or UUID.")
    ],
    validate_only: Annotated[
        bool,
        typer.Option(
            "--validate-only", "--dry-run", help="Only run migration preflight validation."
        ),
    ] = False,
    node: NodeOption = None,
    wait: WaitOption = True,
) -> None:
    """Validate and migrate a jail to another cluster node."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        ctid, source_host, _ = client.resolve_jail(jail, node=node)
        target_uuid, target_host = client.resolve_node_uuid(target)

        val_res = client.get(
            "/tasks/migration/validate",
            params={
                "guestType": "jail",
                "guestId": ctid,
                "targetNodeUuid": target_uuid,
            },
            node=source_host or None,
        )
        if validate_only:
            if isinstance(val_res, dict):
                print_dict(val_res, title=f"Jail {ctid} Migration Preflight -> {target_host}")
            else:
                console.print(
                    f"[green]Migration preflight passed for Jail {ctid} -> {target_host}.[/green]"
                )
            return

        resp = client.post(
            f"/jail/{ctid}/migrations",
            json_body={"targetNodeUuid": target_uuid},
            node=source_host or None,
        )
        task_id = resp.get("taskId") if isinstance(resp, dict) else None
        if wait and task_id:
            wait_for_lifecycle_task(client, int(task_id), node=source_host or None)
            console.print(
                f"[green]Jail {ctid} successfully migrated from {source_host} to {target_host}.[/green]"
            )
        else:
            console.print(
                f"[cyan]Queued migration of Jail {ctid} -> {target_host} (task #{task_id}).[/cyan]"
            )


@jail_app.command("delete")
def jail_delete(
    ctx: typer.Context,
    jail: Annotated[str, typer.Argument(help="Jail CTID or name to delete.")],
    delete_rootfs: Annotated[
        bool,
        typer.Option("--delete-rootfs/--keep-rootfs", help="Delete the jail's root ZFS dataset."),
    ] = True,
    delete_macs: Annotated[
        bool,
        typer.Option("--delete-macs/--keep-macs", help="Delete unused MAC objects."),
    ] = True,
    yes: Annotated[bool, typer.Option("-y", "--yes", help="Skip confirmation prompt.")] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Print what would be deleted without deleting it."),
    ] = False,
    node: NodeOption = None,
    fmt: FormatOption = OutputFormat.table,
) -> None:
    """Delete a jail by CTID or name."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        ctid, host, summary = client.resolve_jail(jail, node=node)
        plan = {
            "action": "delete-jail",
            "ctid": ctid,
            "name": summary.get("name"),
            "node": host or "local",
            "deleteRootfs": delete_rootfs,
            "deleteMacs": delete_macs,
        }
        if dry_run:
            print_result(plan, fmt, f"Dry run: would delete Jail {ctid} ({host or 'local'}).")
            return
        confirm_destructive(f"Delete Jail {ctid} on node '{host or 'local'}'?", yes=yes)
        client.delete(
            f"/jail/{ctid}",
            params={"deleterootfs": delete_rootfs, "deletemacs": delete_macs},
            node=host or None,
        )
    print_result(
        {"deleted": True, "ctid": ctid, "node": host or "local"},
        fmt,
        f"Deleted Jail {ctid} ({host or 'local'}).",
    )


@jail_app.command("logs")
def jail_logs(
    ctx: typer.Context,
    jail: Annotated[str, typer.Argument(help="Jail CTID or name.")],
    node: NodeOption = None,
) -> None:
    """Show console logs for a jail."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        ctid, host, _ = client.resolve_jail(jail, node=node)
        data = client.get(f"/jail/{ctid}/logs", node=host or None)
    if isinstance(data, dict):
        console.print(str(data.get("logs") or ""))
    else:
        console.print(str(data or ""))


@jail_app.command("console")
def jail_console(
    ctx: typer.Context,
    jail: Annotated[str, typer.Argument(help="Jail CTID or name.")],
    node: NodeOption = None,
) -> None:
    """Attach to a running jail's interactive console over WebSocket."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        ctid, host, summary = client.resolve_jail(jail, node=node)
        name = summary.get("name") or ctid
        attach_console(
            client,
            f"/jail/{ctid}/console",
            node=host or node,
            takeover=False,
            banner=f"Attached to Jail {name} ({ctid}) console",
        )


@jail_app.command("guest-info")
def jail_guest_info(
    ctx: typer.Context,
    jail: Annotated[str, typer.Argument(help="Jail CTID or name.")],
    node: NodeOption = None,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
) -> None:
    """Retrieve live OS and network interface information from a running jail."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        ctid, host, _ = client.resolve_jail(jail, node=node)
        data = client.get(f"/jail/{ctid}/guest-info", node=host or None) or {}
    if isinstance(data, dict):
        print_dict(data, fmt=fmt, selected_columns=columns, title=f"Jail {ctid} Guest Info")
    else:
        console.print(str(data))


@jail_app.command("rename")
def jail_rename(
    ctx: typer.Context,
    jail: Annotated[str, typer.Argument(help="Jail CTID or current name.")],
    new_name: Annotated[str, typer.Argument(help="New jail name.")],
    node: NodeOption = None,
) -> None:
    """Rename a jail."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        ctid, host, _ = client.resolve_jail(jail, node=node)
        client.patch(f"/jail/{ctid}/name", json_body={"name": new_name}, node=host or None)
    console.print(f"[green]Renamed Jail {ctid} to '{new_name}'.[/green]")


@jail_snapshot_app.command("list")
def jail_snapshot_list(
    ctx: typer.Context,
    jail: Annotated[str, typer.Argument(help="Jail CTID or name.")],
    node: NodeOption = None,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
    long: LongOption = False,
) -> None:
    """List ZFS snapshots for a jail."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        ctid, host, _ = client.resolve_jail(jail, node=node)
        snaps = client.get(f"/jail/{ctid}/snapshots", node=host or None) or []
    spec = [
        ColumnSpec("ID", "id", justify="right"),
        ColumnSpec("Snapshot", "snapshotName"),
        ColumnSpec("Created At", "createdAt", formatter=format_timestamp),
    ]
    if long:
        spec = [
            ColumnSpec("ID", "id", justify="right"),
            ColumnSpec("Name", "name"),
            ColumnSpec("Snapshot", "snapshotName"),
            ColumnSpec("Root Dataset", "rootDataset"),
            ColumnSpec("Description", "description"),
            ColumnSpec("Created At", "createdAt", formatter=format_timestamp),
        ]
    print_list(
        snaps if isinstance(snaps, list) else [],
        spec,
        fmt=fmt,
        selected_columns=columns,
        title=f"Jail {ctid} Snapshots ({host or 'local'})",
    )


@jail_snapshot_app.command("create")
def jail_snapshot_create(
    ctx: typer.Context,
    jail: Annotated[str, typer.Argument(help="Jail CTID or name.")],
    name: Annotated[str, typer.Option("--name", "-m", help="Snapshot name.")],
    description: Annotated[
        str, typer.Option("--description", "-d", help="Snapshot description.")
    ] = "",
    node: NodeOption = None,
) -> None:
    """Create a ZFS snapshot for a jail."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        ctid, host, _ = client.resolve_jail(jail, node=node)
        client.post(
            f"/jail/{ctid}/snapshots",
            json_body={"name": name, "description": description},
            node=host or None,
        )
    console.print(f"[green]Created snapshot '{name}' for Jail {ctid}.[/green]")


@jail_snapshot_app.command("rollback")
def jail_snapshot_rollback(
    ctx: typer.Context,
    jail: Annotated[str, typer.Argument(help="Jail CTID or name.")],
    snapshot_id: Annotated[int, typer.Argument(help="Snapshot ID to roll back to.")],
    yes: Annotated[bool, typer.Option("-y", "--yes", help="Skip confirmation prompt.")] = False,
    node: NodeOption = None,
) -> None:
    """Roll back a jail to a selected snapshot."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        ctid, host, _ = client.resolve_jail(jail, node=node)
        confirm_destructive(
            f"Roll back Jail {ctid} to snapshot #{snapshot_id}? Newer ZFS snapshots will be destroyed.",
            yes=yes,
        )
        client.post(f"/jail/{ctid}/snapshots/{snapshot_id}/rollback", node=host or None)
    console.print(f"[green]Rolled back Jail {ctid} to snapshot #{snapshot_id}.[/green]")


@jail_snapshot_app.command("delete")
def jail_snapshot_delete(
    ctx: typer.Context,
    jail: Annotated[str, typer.Argument(help="Jail CTID or name.")],
    snapshot_id: Annotated[int, typer.Argument(help="Snapshot ID to delete.")],
    yes: YesOption = False,
    node: NodeOption = None,
) -> None:
    """Delete a jail snapshot."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        ctid, host, _ = client.resolve_jail(jail, node=node)
        confirm_destructive(f"Delete snapshot #{snapshot_id} for Jail {ctid}?", yes=yes)
        client.delete(f"/jail/{ctid}/snapshots/{snapshot_id}", node=host or None)
    console.print(f"[green]Deleted snapshot #{snapshot_id} for Jail {ctid}.[/green]")


@jail_bootstrap_app.command("list")
def jail_bootstrap_list(
    ctx: typer.Context,
    pool: Annotated[str, typer.Option("--pool", "-p", help="ZFS pool name to query.")],
    node: NodeOption = None,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
) -> None:
    """List pkgbase jail bootstraps on a ZFS pool."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        results = client.fan_out_get("/jail/bootstraps", params={"pool": pool}, node=node)
    rows: list[dict[str, Any]] = []
    for host, data in results:
        if isinstance(data, list):
            for entry in data:
                if isinstance(entry, dict):
                    r = dict(entry)
                    r.setdefault("node", host)
                    rows.append(r)
    spec = [
        ColumnSpec("Name", "name"),
        ColumnSpec("Pool", "pool"),
        ColumnSpec("Version", "version"),
        ColumnSpec("Type", "type"),
        ColumnSpec("Status", "status"),
        ColumnSpec("Node", "node"),
    ]
    print_list(
        rows, spec, fmt=fmt, selected_columns=columns, title=f"Jail Bootstraps (Pool: {pool})"
    )


@jail_bootstrap_app.command("create")
def jail_bootstrap_create(
    ctx: typer.Context,
    pool: Annotated[str, typer.Option("--pool", "-p", help="ZFS pool name.")],
    major: Annotated[int, typer.Option("--major", help="FreeBSD major version (e.g. 14 or 15).")],
    minor: Annotated[int, typer.Option("--minor", help="FreeBSD minor version (e.g. 2).")] = 0,
    btype: Annotated[
        str, typer.Option("--type", help="Bootstrap type (e.g. base, minimal).")
    ] = "base",
    node: NodeOption = None,
) -> None:
    """Queue a pkgbase jail bootstrap on a ZFS pool."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        client.post(
            "/jail/bootstraps",
            json_body={"pool": pool, "major": major, "minor": minor, "type": btype},
            node=node,
        )
    console.print(
        f"[green]Queued jail bootstrap ({major}.{minor} {btype}) on pool '{pool}'.[/green]"
    )


@jail_template_app.command("list")
def jail_template_list(
    ctx: typer.Context,
    node: NodeOption = None,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
) -> None:
    """List jail templates across the cluster."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        results = client.fan_out_get("/jail/templates", node=node)
        rows: list[dict[str, Any]] = []
        for host, data in results:
            if isinstance(data, list):
                for t in data:
                    if not isinstance(t, dict):
                        continue
                    row = dict(t)
                    row.setdefault("node", host)
                    # The simple list omits detail metadata; fetch it per template.
                    client.enrich_template_metadata(row, f"/jail/templates/{row.get('id')}", host)
                    rows.append(row)
    spec = [
        ColumnSpec("ID", "id", justify="right"),
        ColumnSpec("Name", "name"),
        ColumnSpec("Source Jail", "sourceJailName"),
        ColumnSpec("Pool", "pool"),
        ColumnSpec("Node", "node"),
        ColumnSpec("Created At", "createdAt", formatter=format_timestamp),
    ]
    print_list(rows, spec, fmt=fmt, selected_columns=columns, title="Jail Templates")
