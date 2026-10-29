"""Bhyve Virtual Machine (vm / server) management commands."""

from __future__ import annotations

from typing import Annotated, Any

import typer

from sylve_cli.client import SylveClient, SylveError
from sylve_cli.commands.vm_create import register_vm_create_commands
from sylve_cli.console_ws import attach_console
from sylve_cli.formatter import (
    ColumnSpec,
    OutputFormat,
    console,
    format_bytes,
    format_timestamp,
    format_vm_state,
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
    WaitOption,
)
from sylve_cli.tasks import wait_for_lifecycle_task
from sylve_cli.vnc_proxy import serve_vnc

vm_app = typer.Typer(
    name="vm",
    help="Query, start, stop, migrate, snapshot, and manage Bhyve virtual machines.",
    no_args_is_help=True,
    rich_markup_mode=None,
)

vm_snapshot_app = typer.Typer(
    name="snapshot",
    help="Manage crash-consistent ZFS snapshots for a virtual machine.",
    no_args_is_help=True,
    rich_markup_mode=None,
)
vm_template_app = typer.Typer(
    name="template",
    help="Manage VM templates and deploy VMs from templates.",
    no_args_is_help=True,
    rich_markup_mode=None,
)

vm_app.add_typer(vm_snapshot_app, name="snapshot")
vm_app.add_typer(vm_template_app, name="template")
register_vm_create_commands(vm_app)


def _run_vm_action(
    client: SylveClient,
    action: str,
    vms: list[str],
    node: str | None,
    wait: bool,
) -> None:
    for ident in vms:
        rid, host, _ = client.resolve_vm(ident, node=node)
        resp = client.post(f"/vm/{rid}/actions/{action}", node=host or None)
        task_id = resp.get("taskId") if isinstance(resp, dict) else None
        outcome = resp.get("outcome") if isinstance(resp, dict) else "queued"
        if wait and task_id:
            wait_for_lifecycle_task(client, int(task_id), node=host or None)
            console.print(
                f"[green]VM {rid}[/green] ({host or 'local'}): [bold]{action}[/bold] completed."
            )
        else:
            task_note = f" (task #{task_id})" if task_id else ""
            console.print(
                f"[cyan]VM {rid}[/cyan] ({host or 'local'}): [bold]{action}[/bold] {outcome}{task_note}."
            )


@vm_app.command("list")
def vm_list(
    ctx: typer.Context,
    node: NodeOption = None,
    detailed: Annotated[
        bool,
        typer.Option("--long", "-l", help="Fetch full VM details (CPU/RAM/Boot) from each node."),
    ] = False,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
    sort_column: SortColumnOption = None,
) -> None:
    """List virtual machines across all cluster nodes (or a specific node with --node)."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        rows: list[dict[str, Any]] = []
        target_host = client.resolve_node_hostname(node)

        if detailed:
            fan_results = client.fan_out_get("/vm", node=target_host)
            for host, data in fan_results:
                if isinstance(data, list):
                    for vm in data:
                        if not isinstance(vm, dict):
                            continue
                        vcpus = (
                            int(vm.get("cpuSockets") or 1)
                            * int(vm.get("cpuCores") or 1)
                            * int(vm.get("cpuThreads") or 1)
                        )
                        rows.append(
                            {
                                "rid": vm.get("rid"),
                                "name": vm.get("name"),
                                "state": format_vm_state(vm.get("state")),
                                "node": host,
                                "vcpus": vcpus,
                                "ram": vm.get("ram"),
                                "vnc_port": vm.get("vncPort") if vm.get("vncEnabled") else "-",
                                "autostart": bool(vm.get("startAtBoot")),
                                "description": vm.get("description") or "",
                            }
                        )
            spec = [
                ColumnSpec("RID", "rid", justify="right"),
                ColumnSpec("Name", "name"),
                ColumnSpec("State", "state"),
                ColumnSpec("Node", "node"),
                ColumnSpec("vCPUs", "vcpus", justify="right"),
                ColumnSpec("Memory", "ram", formatter=format_bytes, justify="right"),
                ColumnSpec("VNC Port", "vnc_port", justify="right"),
                ColumnSpec("Autostart", "autostart"),
                ColumnSpec("Description", "description"),
            ]
        else:
            for node_res in client.get_cluster_resources():
                host = str(node_res.get("hostname") or "")
                if target_host and host.lower() != target_host.lower():
                    continue
                for vm in node_res.get("vms") or []:
                    if not isinstance(vm, dict):
                        continue
                    rows.append(
                        {
                            "rid": vm.get("rid"),
                            "name": vm.get("name"),
                            "state": format_vm_state(vm.get("state")),
                            "node": host,
                            "vnc_port": vm.get("vncPort") or "-",
                        }
                    )
            spec = [
                ColumnSpec("RID", "rid", justify="right"),
                ColumnSpec("Name", "name"),
                ColumnSpec("State", "state"),
                ColumnSpec("Node", "node"),
                ColumnSpec("VNC Port", "vnc_port", justify="right"),
            ]

    print_list(
        rows,
        spec,
        fmt=fmt,
        selected_columns=columns,
        sort_column=sort_column,
        title="Virtual Machines",
    )


@vm_app.command("show")
def vm_show(
    ctx: typer.Context,
    vm: Annotated[str, typer.Argument(help="VM RID or name.")],
    node: NodeOption = None,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
) -> None:
    """Display full details of a virtual machine."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        rid, host, summary = client.resolve_vm(vm, node=node)
        data = client.get(f"/vm/{rid}", node=host or None)
        if not isinstance(data, dict):
            raise SylveError(f"Unexpected response for VM {rid}.")
        if "state" in summary:
            # The detail endpoint returns the stored row; only the cluster
            # summary carries the live libvirt state.
            data["state"] = summary["state"]
        data["state_name"] = format_vm_state(data.get("state"))
        data["node"] = host or client.context.hostname or "local"
        selected = {
            part.strip().casefold() for column in (columns or []) for part in column.split(",")
        }
        if (
            fmt in (OutputFormat.table, OutputFormat.csv, OutputFormat.value)
            and "state" not in selected
        ):
            data.pop("state", None)

    print_dict(
        data,
        fmt=fmt,
        selected_columns=columns,
        title=f"Virtual Machine {data.get('name')} (RID {rid} on {data.get('node')})",
    )


@vm_app.command("start")
def vm_start(
    ctx: typer.Context,
    vms: Annotated[list[str], typer.Argument(help="One or more VM RIDs or names to start.")],
    node: NodeOption = None,
    wait: WaitOption = False,
) -> None:
    """Start one or more virtual machines."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        _run_vm_action(client, "start", vms, node=node, wait=wait)


@vm_app.command("stop")
def vm_stop(
    ctx: typer.Context,
    vms: Annotated[list[str], typer.Argument(help="One or more VM RIDs or names to force-stop.")],
    node: NodeOption = None,
    wait: WaitOption = False,
) -> None:
    """Force-stop (power off) one or more virtual machines."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        _run_vm_action(client, "stop", vms, node=node, wait=wait)


@vm_app.command("shutdown")
def vm_shutdown(
    ctx: typer.Context,
    vms: Annotated[
        list[str], typer.Argument(help="One or more VM RIDs or names to gracefully shut down.")
    ],
    node: NodeOption = None,
    wait: WaitOption = False,
) -> None:
    """Gracefully shut down one or more virtual machines via ACPI."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        _run_vm_action(client, "shutdown", vms, node=node, wait=wait)


@vm_app.command("reboot")
def vm_reboot(
    ctx: typer.Context,
    vms: Annotated[list[str], typer.Argument(help="One or more VM RIDs or names to reboot.")],
    node: NodeOption = None,
    wait: WaitOption = False,
) -> None:
    """Reboot one or more virtual machines."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        _run_vm_action(client, "reboot", vms, node=node, wait=wait)


@vm_app.command("migrate")
def vm_migrate(
    ctx: typer.Context,
    vm: Annotated[str, typer.Argument(help="VM RID or name to migrate.")],
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
    """Validate and migrate a virtual machine to another cluster node."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        rid, source_host, _ = client.resolve_vm(vm, node=node)
        target_uuid, target_host = client.resolve_node_uuid(target)

        val_res = client.get(
            "/tasks/migration/validate",
            params={
                "guestType": "vm",
                "guestId": rid,
                "targetNodeUuid": target_uuid,
            },
            node=source_host or None,
        )
        if validate_only:
            if isinstance(val_res, dict):
                print_dict(val_res, title=f"VM {rid} Migration Preflight -> {target_host}")
            else:
                console.print(
                    f"[green]Migration preflight passed for VM {rid} -> {target_host}.[/green]"
                )
            return

        resp = client.post(
            f"/vm/{rid}/migrations",
            json_body={"targetNodeUuid": target_uuid},
            node=source_host or None,
        )
        task_id = resp.get("taskId") if isinstance(resp, dict) else None
        if wait and task_id:
            wait_for_lifecycle_task(client, int(task_id), node=source_host or None)
            console.print(
                f"[green]VM {rid} successfully migrated from {source_host} to {target_host}.[/green]"
            )
        else:
            console.print(
                f"[cyan]Queued migration of VM {rid} -> {target_host} (task #{task_id}).[/cyan]"
            )


@vm_app.command("delete")
def vm_delete(
    ctx: typer.Context,
    vm: Annotated[str, typer.Argument(help="VM RID or name to delete.")],
    delete_volumes: Annotated[
        bool,
        typer.Option("--delete-volumes/--keep-volumes", help="Delete attached ZFS volumes."),
    ] = True,
    delete_raw_disks: Annotated[
        bool,
        typer.Option(
            "--delete-raw-disks/--keep-raw-disks", help="Delete attached RAW disk images."
        ),
    ] = True,
    delete_macs: Annotated[
        bool,
        typer.Option("--delete-macs/--keep-macs", help="Delete associated MAC address objects."),
    ] = True,
    force: Annotated[
        bool,
        typer.Option("--force", help="Force best-effort removal."),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option("-y", "--yes", help="Skip confirmation prompt."),
    ] = False,
    node: NodeOption = None,
) -> None:
    """Delete a virtual machine."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        rid, host, _ = client.resolve_vm(vm, node=node)
        if not yes:
            typer.confirm(f"Delete VM {rid} on node '{host or 'local'}'?", abort=True)
        client.delete(
            f"/vm/{rid}",
            params={
                "deletevolumes": delete_volumes,
                "deleterawdisks": delete_raw_disks,
                "deletemacs": delete_macs,
                "force": force,
            },
            node=host or None,
        )
    console.print(f"[green]Deleted VM {rid} ({host or 'local'}).[/green]")


@vm_app.command("logs")
def vm_logs(
    ctx: typer.Context,
    vm: Annotated[str, typer.Argument(help="VM RID or name.")],
    node: NodeOption = None,
) -> None:
    """Retrieve console logs for a virtual machine."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        rid, host, _ = client.resolve_vm(vm, node=node)
        data = client.get(f"/vm/{rid}/logs", node=host or None)
    if isinstance(data, dict):
        console.print(str(data.get("logs") or ""))
    else:
        console.print(str(data or ""))


@vm_app.command("console")
def vm_console(
    ctx: typer.Context,
    vm: Annotated[str, typer.Argument(help="VM RID or name.")],
    baudrate: Annotated[
        int,
        typer.Option("--baudrate", "-b", help="Serial baud rate."),
    ] = 115200,
    takeover: Annotated[
        bool,
        typer.Option(
            "--takeover/--observe",
            help="Request input control of the serial console, or attach read-only.",
        ),
    ] = True,
    node: NodeOption = None,
) -> None:
    """Attach to a running VM's interactive serial console over WebSocket."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        rid, host, summary = client.resolve_vm(vm, node=node)
        name = summary.get("name") or rid
        attach_console(
            client,
            f"/vm/{rid}/console",
            node=host or node,
            extra_params={"baudrate": baudrate},
            takeover=takeover,
            banner=f"Attached to VM {name} ({rid}) serial console",
        )


@vm_app.command("vnc")
def vm_vnc(
    ctx: typer.Context,
    vm: Annotated[str, typer.Argument(help="VM RID or name.")],
    overtake: Annotated[
        bool,
        typer.Option(
            "--overtake/--no-overtake",
            help="Take over an existing VNC session instead of refusing to connect.",
        ),
    ] = False,
    viewer: Annotated[
        str | None,
        typer.Option(
            "--viewer",
            help="Viewer command template; {host}, {port} and {url} are substituted.",
        ),
    ] = None,
    local_port: Annotated[
        int,
        typer.Option(
            "--local-port",
            min=0,
            max=65535,
            help="Loopback port for the bridge (0 picks a free port).",
        ),
    ] = 0,
    print_only: Annotated[
        bool,
        typer.Option("--print-only", help="Print the local VNC address without opening a viewer."),
    ] = False,
    node: NodeOption = None,
) -> None:
    """Open a running VM's graphical console in a local VNC viewer."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        rid, host, summary = client.resolve_vm(vm, node=node)
        name = summary.get("name") or rid
        serve_vnc(
            client,
            rid,
            node=host or node,
            overtake=overtake,
            local_port=local_port,
            viewer=viewer,
            print_only=print_only,
            name=str(name),
            state=summary.get("state"),
        )


@vm_app.command("guest-agent")
def vm_guest_agent(
    ctx: typer.Context,
    vm: Annotated[str, typer.Argument(help="VM RID or name.")],
    node: NodeOption = None,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
) -> None:
    """Retrieve OS and live network information from the QEMU Guest Agent of a running VM."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        rid, host, _ = client.resolve_vm(vm, node=node)
        data = client.get(f"/vm/{rid}/guest-agent", node=host or None) or {}
    if isinstance(data, dict):
        print_dict(data, fmt=fmt, selected_columns=columns, title=f"VM {rid} Guest Agent Info")
    else:
        console.print(str(data))


@vm_app.command("rename")
def vm_rename(
    ctx: typer.Context,
    vm: Annotated[str, typer.Argument(help="VM RID or current name.")],
    new_name: Annotated[str, typer.Argument(help="New VM name.")],
    node: NodeOption = None,
) -> None:
    """Rename a virtual machine."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        rid, host, _ = client.resolve_vm(vm, node=node)
        client.patch(f"/vm/{rid}/name", json_body={"name": new_name}, node=host or None)
    console.print(f"[green]Renamed VM {rid} to '{new_name}'.[/green]")


@vm_snapshot_app.command("list")
def vm_snapshot_list(
    ctx: typer.Context,
    vm: Annotated[str, typer.Argument(help="VM RID or name.")],
    node: NodeOption = None,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
    long: LongOption = False,
) -> None:
    """List ZFS snapshots for a virtual machine."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        rid, host, _ = client.resolve_vm(vm, node=node)
        snaps = client.get(f"/vm/{rid}/snapshots", node=host or None) or []
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
            ColumnSpec("Description", "description"),
            ColumnSpec("Created At", "createdAt", formatter=format_timestamp),
        ]
    print_list(
        snaps if isinstance(snaps, list) else [],
        spec,
        fmt=fmt,
        selected_columns=columns,
        title=f"VM {rid} Snapshots ({host or 'local'})",
    )


@vm_snapshot_app.command("create")
def vm_snapshot_create(
    ctx: typer.Context,
    vm: Annotated[str, typer.Argument(help="VM RID or name.")],
    name: Annotated[str, typer.Option("--name", "-m", help="Snapshot name.")],
    description: Annotated[
        str, typer.Option("--description", "-d", help="Snapshot description.")
    ] = "",
    node: NodeOption = None,
) -> None:
    """Create a crash-consistent ZFS snapshot for a virtual machine."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        rid, host, _ = client.resolve_vm(vm, node=node)
        client.post(
            f"/vm/{rid}/snapshots",
            json_body={"name": name, "description": description},
            node=host or None,
        )
    console.print(f"[green]Created snapshot '{name}' for VM {rid}.[/green]")


@vm_snapshot_app.command("rollback")
def vm_snapshot_rollback(
    ctx: typer.Context,
    vm: Annotated[str, typer.Argument(help="VM RID or name.")],
    snapshot_id: Annotated[int, typer.Argument(help="Snapshot ID to roll back to.")],
    yes: Annotated[bool, typer.Option("-y", "--yes", help="Skip confirmation prompt.")] = False,
    node: NodeOption = None,
) -> None:
    """Roll back a virtual machine to a recorded snapshot."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        rid, host, _ = client.resolve_vm(vm, node=node)
        if not yes:
            typer.confirm(
                f"Roll back VM {rid} to snapshot #{snapshot_id}? Newer ZFS snapshots will be destroyed.",
                abort=True,
            )
        client.post(f"/vm/{rid}/snapshots/{snapshot_id}/rollback", node=host or None)
    console.print(f"[green]Rolled back VM {rid} to snapshot #{snapshot_id}.[/green]")


@vm_snapshot_app.command("delete")
def vm_snapshot_delete(
    ctx: typer.Context,
    vm: Annotated[str, typer.Argument(help="VM RID or name.")],
    snapshot_id: Annotated[int, typer.Argument(help="Snapshot ID to delete.")],
    node: NodeOption = None,
) -> None:
    """Delete a virtual machine snapshot."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        rid, host, _ = client.resolve_vm(vm, node=node)
        client.delete(f"/vm/{rid}/snapshots/{snapshot_id}", node=host or None)
    console.print(f"[green]Deleted snapshot #{snapshot_id} for VM {rid}.[/green]")


@vm_template_app.command("list")
def vm_template_list(
    ctx: typer.Context,
    node: NodeOption = None,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
) -> None:
    """List VM templates across the cluster (or on a specific node)."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        results = client.fan_out_get("/vm/templates", node=node)
    rows: list[dict[str, Any]] = []
    for host, data in results:
        if isinstance(data, list):
            for t in data:
                if isinstance(t, dict):
                    row = dict(t)
                    row.setdefault("node", host)
                    rows.append(row)
    spec = [
        ColumnSpec("ID", "id", justify="right"),
        ColumnSpec("Name", "name"),
        ColumnSpec("Source VM", "sourceVmName"),
        ColumnSpec("Node", "node"),
        ColumnSpec("Created At", "createdAt", formatter=format_timestamp),
    ]
    print_list(rows, spec, fmt=fmt, selected_columns=columns, title="VM Templates")


@vm_template_app.command("capture")
def vm_template_capture(
    ctx: typer.Context,
    vm: Annotated[str, typer.Argument(help="Shut-off source VM RID or name.")],
    name: Annotated[str, typer.Option("--name", help="Template name.")],
    node: NodeOption = None,
    wait: WaitOption = True,
) -> None:
    """Capture a shut-off VM as a reusable template."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        rid, host, _ = client.resolve_vm(vm, node=node)
        resp = client.post(
            f"/vm/{rid}/templates",
            json_body={"name": name},
            node=host or None,
        )
        task_id = resp.get("taskId") if isinstance(resp, dict) else None
        if wait and task_id:
            wait_for_lifecycle_task(client, int(task_id), node=host or None)
        console.print(f"[green]Captured VM {rid} as template '{name}'.[/green]")


@vm_template_app.command("delete")
def vm_template_delete(
    ctx: typer.Context,
    template_id: Annotated[int, typer.Argument(help="VM template ID.")],
    node: NodeOption = None,
) -> None:
    """Delete a VM template by ID."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        client.delete(f"/vm/templates/{template_id}", node=node)
    console.print(f"[green]Deleted VM template #{template_id}.[/green]")
