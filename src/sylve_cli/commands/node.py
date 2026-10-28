"""Cluster node management, telemetry, and node maintenance drain commands."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Annotated, Any

import typer

from sylve_cli.client import SylveClient, SylveError
from sylve_cli.formatter import (
    ColumnSpec,
    OutputFormat,
    console,
    err_console,
    format_bytes,
    format_percent,
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
    SortColumnOption,
    WaitOption,
)
from sylve_cli.tasks import wait_for_lifecycle_task

node_app = typer.Typer(
    name="node",
    help="Query and manage cluster nodes, maintenance draining, services, and host state.",
    no_args_is_help=True,
    rich_markup_mode=None,
)


@dataclass
class DrainPlanItem:
    """Single workload action in a node maintenance drain plan."""

    guest_type: str
    guest_id: int
    name: str
    current_state: str
    action: str  # ha-failover | migrate | shutdown | stop | skip | blocked
    source_node: str
    target_node: str
    target_node_uuid: str
    policy_id: int | None = None
    reason: str = "ok"
    result: str = "pending"
    task_id: int | None = None


def _select_least_loaded_node(
    candidates: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Pick the online candidate node with the lowest combined memory and CPU usage."""
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda n: (
            float(n.get("memoryUsage") or 0.0) * 0.7 + float(n.get("cpuUsage") or 0.0) * 0.3,
            len(n.get("guestIDs") or []),
        ),
    )


def build_node_drain_plan(
    client: SylveClient,
    source_node: str,
    target_node: str | None = None,
    stop_only: bool = False,
    fallback_stop: bool = False,
    include_stopped: bool = True,
) -> tuple[str, str, list[DrainPlanItem], list[dict[str, Any]]]:
    """Build and validate a maintenance drain plan for all guests on `source_node`."""
    source_uuid, source_host = client.resolve_node_uuid(source_node)
    all_nodes = client.get_cluster_nodes(refresh=True)

    candidate_nodes = [
        n
        for n in all_nodes
        if str(n.get("hostname") or "").lower() != source_host.lower()
        and str(n.get("status") or "online").lower() == "online"
    ]

    explicit_target_uuid = ""
    explicit_target_host = ""
    if target_node and not stop_only:
        explicit_target_uuid, explicit_target_host = client.resolve_node_uuid(target_node)
        if explicit_target_host.lower() == source_host.lower():
            raise SylveError("Target node for drain cannot be the same as the source node.")

    node_uuid_to_host = {
        str(n.get("nodeUUID") or n.get("nodeUuid") or ""): str(n.get("hostname") or "")
        for n in all_nodes
    }

    # Fetch guests on source node
    resources = client.get_cluster_resources(refresh=True)
    source_vms: list[dict[str, Any]] = []
    source_jails: list[dict[str, Any]] = []
    for entry in resources:
        if str(entry.get("hostname") or "").lower() == source_host.lower():
            source_vms = [v for v in (entry.get("vms") or []) if isinstance(v, dict)]
            source_jails = [j for j in (entry.get("jails") or []) if isinstance(j, dict)]
            break

    # Fetch replication policies to identify HA-protected guests
    policies_by_guest: dict[tuple[str, int], dict[str, Any]] = {}
    try:
        raw_policies = client.get("/cluster/replication/policies") or []
        if isinstance(raw_policies, list):
            for pol in raw_policies:
                if not isinstance(pol, dict) or not pol.get("enabled", True):
                    continue
                active_node = str(pol.get("activeNodeId") or pol.get("sourceNodeId") or "")
                gtype = str(pol.get("guestType") or "").lower()
                gid = int(pol.get("guestId") or 0)
                if active_node.lower() == source_uuid.lower() and gtype and gid > 0:
                    policies_by_guest[(gtype, gid)] = pol
    except SylveError:
        pass

    # Check backup jobs assigned to this runner node
    pinned_backup_jobs: list[dict[str, Any]] = []
    try:
        raw_jobs = client.get("/cluster/backups/jobs") or []
        if isinstance(raw_jobs, list):
            for job in raw_jobs:
                if (
                    isinstance(job, dict)
                    and str(job.get("runnerNodeId") or "").lower() == source_uuid.lower()
                ):
                    pinned_backup_jobs.append(job)
    except SylveError:
        pass

    plan: list[DrainPlanItem] = []

    guests: list[tuple[str, int, str, str]] = []
    for vm in source_vms:
        rid = int(vm.get("rid") or 0)
        name = str(vm.get("name") or f"vm-{rid}")
        state_str = format_vm_state(vm.get("state"))
        guests.append(("vm", rid, name, state_str))

    for jail in source_jails:
        ctid = int(jail.get("ctId") or 0)
        name = str(jail.get("name") or f"jail-{ctid}")
        state_str = str(jail.get("state") or "UNKNOWN").upper()
        guests.append(("jail", ctid, name, state_str))

    for gtype, gid, name, state_str in guests:
        is_running = state_str in ("RUNNING", "ACTIVE", "PAUSED", "BLOCKED")

        if stop_only:
            if is_running:
                act = "shutdown" if gtype == "vm" else "stop"
                plan.append(
                    DrainPlanItem(
                        guest_type=gtype,
                        guest_id=gid,
                        name=name,
                        current_state=state_str,
                        action=act,
                        source_node=source_host,
                        target_node="-",
                        target_node_uuid="",
                        reason="stop-only requested",
                    )
                )
            else:
                plan.append(
                    DrainPlanItem(
                        guest_type=gtype,
                        guest_id=gid,
                        name=name,
                        current_state=state_str,
                        action="skip",
                        source_node=source_host,
                        target_node="-",
                        target_node_uuid="",
                        reason="already stopped",
                        result="skipped",
                    )
                )
            continue

        if not include_stopped and not is_running:
            plan.append(
                DrainPlanItem(
                    guest_type=gtype,
                    guest_id=gid,
                    name=name,
                    current_state=state_str,
                    action="skip",
                    source_node=source_host,
                    target_node="-",
                    target_node_uuid="",
                    reason="stopped (--running-only)",
                    result="skipped",
                )
            )
            continue

        # 1. Check if guest is managed by an active HA Replication Policy
        pol = policies_by_guest.get((gtype, gid))
        if pol is not None:
            pol_id = int(pol.get("id") or 0)
            targets = [t for t in (pol.get("targets") or []) if isinstance(t, dict)]
            chosen_target_uuid = ""
            if explicit_target_uuid:
                for t in targets:
                    if str(t.get("nodeId") or "").lower() == explicit_target_uuid.lower():
                        chosen_target_uuid = str(t.get("nodeId"))
                        break
            if not chosen_target_uuid and targets:
                ready_targets = [t for t in targets if t.get("ready")]
                pool_targets = ready_targets if ready_targets else targets
                pool_targets.sort(key=lambda t: int(t.get("weight") or 0), reverse=True)
                chosen_target_uuid = str(pool_targets[0].get("nodeId") or "")

            chosen_host = node_uuid_to_host.get(chosen_target_uuid, chosen_target_uuid or "-")
            if chosen_target_uuid:
                plan.append(
                    DrainPlanItem(
                        guest_type=gtype,
                        guest_id=gid,
                        name=name,
                        current_state=state_str,
                        action="ha-failover",
                        source_node=source_host,
                        target_node=chosen_host,
                        target_node_uuid=chosen_target_uuid,
                        policy_id=pol_id,
                        reason=f"replication policy #{pol_id}",
                    )
                )
            else:
                plan.append(
                    DrainPlanItem(
                        guest_type=gtype,
                        guest_id=gid,
                        name=name,
                        current_state=state_str,
                        action="blocked",
                        source_node=source_host,
                        target_node="-",
                        target_node_uuid="",
                        policy_id=pol_id,
                        reason=f"policy #{pol_id} has no matching failover target",
                    )
                )
            continue

        # 2. Standalone guest migration
        dest_uuid = explicit_target_uuid
        dest_host = explicit_target_host
        if not dest_uuid:
            best = _select_least_loaded_node(candidate_nodes)
            if best:
                dest_uuid = str(best.get("nodeUUID") or best.get("nodeUuid") or "")
                dest_host = str(best.get("hostname") or "")

        if not dest_uuid:
            if fallback_stop:
                act = ("shutdown" if gtype == "vm" else "stop") if is_running else "skip"
                plan.append(
                    DrainPlanItem(
                        guest_type=gtype,
                        guest_id=gid,
                        name=name,
                        current_state=state_str,
                        action=act,
                        source_node=source_host,
                        target_node="-",
                        target_node_uuid="",
                        reason="no online target node; fallback to stop",
                    )
                )
            else:
                plan.append(
                    DrainPlanItem(
                        guest_type=gtype,
                        guest_id=gid,
                        name=name,
                        current_state=state_str,
                        action="blocked",
                        source_node=source_host,
                        target_node="-",
                        target_node_uuid="",
                        reason="no online target node available in cluster",
                    )
                )
            continue

        # Validate migration preflight on source node
        validation_ok = True
        validation_reason = "preflight ok"
        try:
            val_res = client.get(
                "/tasks/migration/validate",
                params={
                    "guestType": gtype,
                    "guestId": gid,
                    "targetNodeUuid": dest_uuid,
                },
                node=source_host,
            )
            if isinstance(val_res, dict) and (
                val_res.get("valid") is False or val_res.get("canMigrate") is False
            ):
                validation_ok = False
                validation_reason = str(
                    val_res.get("reason")
                    or val_res.get("error")
                    or val_res.get("message")
                    or "migration validation failed"
                )
        except SylveError as exc:
            validation_ok = False
            validation_reason = str(exc)

        if validation_ok:
            plan.append(
                DrainPlanItem(
                    guest_type=gtype,
                    guest_id=gid,
                    name=name,
                    current_state=state_str,
                    action="migrate",
                    source_node=source_host,
                    target_node=dest_host,
                    target_node_uuid=dest_uuid,
                    reason=validation_reason,
                )
            )
        elif fallback_stop:
            act = ("shutdown" if gtype == "vm" else "stop") if is_running else "skip"
            plan.append(
                DrainPlanItem(
                    guest_type=gtype,
                    guest_id=gid,
                    name=name,
                    current_state=state_str,
                    action=act,
                    source_node=source_host,
                    target_node="-",
                    target_node_uuid="",
                    reason=f"fallback stop ({validation_reason})",
                )
            )
        else:
            plan.append(
                DrainPlanItem(
                    guest_type=gtype,
                    guest_id=gid,
                    name=name,
                    current_state=state_str,
                    action="blocked",
                    source_node=source_host,
                    target_node=dest_host,
                    target_node_uuid=dest_uuid,
                    reason=validation_reason,
                )
            )

    return source_uuid, source_host, plan, pinned_backup_jobs


@node_app.command("list")
def node_list(
    ctx: typer.Context,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
    sort_column: SortColumnOption = None,
    long: LongOption = False,
) -> None:
    """List all nodes in the cluster with CPU, memory, disk usage, and guest count."""
    state: CLIState = ctx.obj
    with state.get_client() as client:
        nodes = client.get_cluster_nodes(refresh=True)

    spec = [
        ColumnSpec("Hostname", "hostname"),
        ColumnSpec("Status", "status"),
        ColumnSpec("CPU%", "cpuUsage", formatter=format_percent, justify="right"),
        ColumnSpec("RAM%", "memoryUsage", formatter=format_percent, justify="right"),
        ColumnSpec("Disk%", "diskUsage", formatter=format_percent, justify="right"),
        ColumnSpec("Guests", "guestIDs", formatter=lambda g: str(len(g or [])), justify="right"),
        ColumnSpec("Version", "sylveVersion"),
    ]
    if long:
        spec = [
            ColumnSpec("Hostname", "hostname"),
            ColumnSpec("Node UUID", "nodeUUID"),
            ColumnSpec("Status", "status"),
            ColumnSpec("API", "api"),
            ColumnSpec("Cores", "cpu", justify="right"),
            ColumnSpec("CPU%", "cpuUsage", formatter=format_percent, justify="right"),
            ColumnSpec("Memory", "memory", formatter=format_bytes, justify="right"),
            ColumnSpec("RAM%", "memoryUsage", formatter=format_percent, justify="right"),
            ColumnSpec("Disk", "disk", formatter=format_bytes, justify="right"),
            ColumnSpec("Disk%", "diskUsage", formatter=format_percent, justify="right"),
            ColumnSpec(
                "Guests", "guestIDs", formatter=lambda g: str(len(g or [])), justify="right"
            ),
            ColumnSpec("Version", "sylveVersion"),
        ]
    print_list(
        nodes,
        spec,
        fmt=fmt,
        selected_columns=columns,
        sort_column=sort_column,
        title="Cluster Nodes",
    )


@node_app.command("show")
def node_show(
    ctx: typer.Context,
    node: Annotated[
        str | None,
        typer.Argument(help="Node hostname or UUID (defaults to current/connected node)."),
    ] = None,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
) -> None:
    """Show detailed system, CPU, RAM, swap, and cluster telemetry for a node."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        target_host = client.resolve_node_hostname(node)
        node_info = client.get("/info/node", node=target_host) or {}
        basic_info: dict[str, Any] = {}
        cpu_info: dict[str, Any] = {}
        ram_info: dict[str, Any] = {}
        swap_info: dict[str, Any] = {}
        try:
            basic_info = client.get("/info/basic", node=target_host) or {}
        except SylveError:
            pass
        try:
            cpu_info = client.get("/info/cpu", node=target_host) or {}
        except SylveError:
            pass
        try:
            ram_info = client.get("/info/ram", node=target_host) or {}
        except SylveError:
            pass
        try:
            swap_info = client.get("/info/swap", node=target_host) or {}
        except SylveError:
            pass

    combined: dict[str, Any] = {}
    if isinstance(basic_info, dict):
        combined.update(basic_info)
    if isinstance(node_info, dict):
        combined.update(node_info)
    if isinstance(cpu_info, dict) and cpu_info:
        combined["cpu_details"] = cpu_info
    if isinstance(ram_info, dict) and ram_info:
        combined["ram_details"] = ram_info
    if isinstance(swap_info, dict) and swap_info:
        combined["swap_details"] = swap_info

    print_dict(
        combined,
        fmt=fmt,
        selected_columns=columns,
        title=f"Node Details: {combined.get('hostname') or target_host or 'local'}",
    )


@node_app.command("drain")
def node_drain(
    ctx: typer.Context,
    node: Annotated[
        str, typer.Argument(help="Hostname or UUID of the node to drain for maintenance.")
    ],
    target_node: Annotated[
        str | None,
        typer.Option(
            "--target-node",
            "-t",
            help="Explicit destination node hostname or UUID (auto-selects least-loaded node if omitted).",
        ),
    ] = None,
    stop_only: Annotated[
        bool,
        typer.Option(
            "--stop-only",
            help="Gracefully shut down all VMs and Jails on the node instead of migrating them.",
        ),
    ] = False,
    fallback_stop: Annotated[
        bool,
        typer.Option(
            "--fallback-stop",
            help="Gracefully stop guests that cannot be migrated instead of blocking the drain.",
        ),
    ] = False,
    running_only: Annotated[
        bool,
        typer.Option(
            "--running-only",
            help="Only migrate/failover guests that are currently running; leave stopped guests on the node.",
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Validate migrations and show the drain plan without executing any changes.",
        ),
    ] = False,
    ignore_errors: Annotated[
        bool,
        typer.Option(
            "--ignore-errors",
            help="Continue draining actionable guests even if some guests fail preflight or execution.",
        ),
    ] = False,
    wait: WaitOption = True,
    yes: Annotated[
        bool,
        typer.Option("-y", "--yes", help="Skip interactive confirmation prompt."),
    ] = False,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
) -> None:
    """Drain a cluster node for maintenance by failing over HA policies and migrating/stopping VMs and Jails."""
    state: CLIState = ctx.obj
    with state.get_client() as client:
        source_uuid, source_host, plan, pinned_jobs = build_node_drain_plan(
            client,
            source_node=node,
            target_node=target_node,
            stop_only=stop_only,
            fallback_stop=fallback_stop,
            include_stopped=not running_only,
        )

        plan_cols = [
            ColumnSpec("Type", "guest_type"),
            ColumnSpec("ID", "guest_id", justify="right"),
            ColumnSpec("Name", "name"),
            ColumnSpec("State", "current_state"),
            ColumnSpec("Action", "action"),
            ColumnSpec("Source", "source_node"),
            ColumnSpec("Target", "target_node"),
            ColumnSpec("Preflight / Reason", "reason"),
            ColumnSpec("Result", "result"),
        ]

        if not plan:
            if fmt in (OutputFormat.json, OutputFormat.yaml):
                print_list([], plan_cols, fmt=fmt, selected_columns=columns)
            else:
                console.print(
                    f"[green]Node '{source_host}' ({source_uuid}) has no guests to drain.[/green]"
                )
            return

        if dry_run:
            print_list(
                [asdict(p) for p in plan],
                plan_cols,
                fmt=fmt,
                selected_columns=columns,
                title=f"Drain Plan (DRY RUN) for {source_host}",
            )
            if pinned_jobs and fmt == OutputFormat.table:
                err_console.print(
                    f"[yellow]Notice:[/yellow] {len(pinned_jobs)} backup job(s) are pinned to run on "
                    f"{source_host}: {', '.join(str(j.get('name')) for j in pinned_jobs)}"
                )
            return

        blocked = [p for p in plan if p.action == "blocked"]
        if blocked and not ignore_errors:
            print_list(
                [asdict(p) for p in plan],
                plan_cols,
                fmt=fmt,
                selected_columns=columns,
                title=f"Drain Plan Blocked for {source_host}",
            )
            raise SylveError(
                f"{len(blocked)} guest(s) failed migration preflight on '{source_host}'. "
                "Use '--fallback-stop' to shut down non-migratable guests, '--stop-only', or '--ignore-errors'."
            )

        actionable = [p for p in plan if p.action not in ("skip", "blocked")]
        if not actionable:
            print_list(
                [asdict(p) for p in plan],
                plan_cols,
                fmt=fmt,
                selected_columns=columns,
                title=f"Drain Plan for {source_host}",
            )
            console.print(f"[green]Node '{source_host}' has no guests to drain.[/green]")
            return

        if fmt == OutputFormat.table:
            print_list(
                [asdict(p) for p in plan],
                plan_cols,
                fmt=fmt,
                selected_columns=columns,
                title=f"Planned Drain Operations for {source_host}",
            )

        if not yes:
            noun = "guest" if len(actionable) == 1 else "guests"
            typer.confirm(
                f"Drain {len(actionable)} {noun} from node '{source_host}'?",
                abort=True,
            )

        failures = 0
        for item in plan:
            if item.action in ("skip", "blocked"):
                continue

            try:
                if item.action == "ha-failover" and item.policy_id:
                    client.post(
                        f"/cluster/replication/policies/{item.policy_id}/failover",
                        json_body={
                            "targetNodeId": item.target_node_uuid,
                            "mode": "safe",
                            "movePinnedSource": True,
                            "confirmDataLoss": False,
                        },
                    )
                    item.result = "failover-queued"

                elif item.action == "migrate":
                    endpoint = (
                        f"/vm/{item.guest_id}/migrations"
                        if item.guest_type == "vm"
                        else f"/jail/{item.guest_id}/migrations"
                    )
                    resp = client.post(
                        endpoint,
                        json_body={"targetNodeUuid": item.target_node_uuid},
                        node=source_host,
                    )
                    task_id = resp.get("taskId") if isinstance(resp, dict) else None
                    item.task_id = int(task_id) if task_id else None
                    if wait and item.task_id:
                        wait_for_lifecycle_task(client, item.task_id, node=source_host)
                        item.result = "migrated"
                    else:
                        item.result = f"queued (task #{item.task_id})" if item.task_id else "queued"

                elif item.action in ("shutdown", "stop"):
                    endpoint = (
                        f"/vm/{item.guest_id}/actions/{item.action}"
                        if item.guest_type == "vm"
                        else f"/jail/{item.guest_id}/actions/{item.action}"
                    )
                    resp = client.post(endpoint, node=source_host)
                    task_id = resp.get("taskId") if isinstance(resp, dict) else None
                    item.task_id = int(task_id) if task_id else None
                    if wait and item.task_id:
                        wait_for_lifecycle_task(client, item.task_id, node=source_host)
                        item.result = "stopped"
                    else:
                        item.result = (
                            f"queued (task #{item.task_id})" if item.task_id else "stopped"
                        )

            except SylveError as exc:
                failures += 1
                item.result = f"failed: {exc}"
                if not ignore_errors:
                    print_list(
                        [asdict(p) for p in plan],
                        plan_cols,
                        fmt=fmt,
                        selected_columns=columns,
                        title=f"Drain Interrupted on {source_host}",
                    )
                    raise

        print_list(
            [asdict(p) for p in plan],
            plan_cols,
            fmt=fmt,
            selected_columns=columns,
            title=f"Drain Summary for {source_host}",
        )
        if pinned_jobs and fmt == OutputFormat.table:
            err_console.print(
                f"[yellow]Notice:[/yellow] {len(pinned_jobs)} scheduled backup job(s) still reference "
                f"runner node {source_host}: {', '.join(str(j.get('name')) for j in pinned_jobs)}"
            )
        if failures:
            raise SylveError(f"Node drain completed with {failures} error(s).")
        if fmt == OutputFormat.table:
            console.print(
                f"[bold green]Node '{source_host}' drained successfully and is ready for maintenance.[/bold green]"
            )


@node_app.command("reboot")
def node_reboot(
    ctx: typer.Context,
    node: Annotated[
        str | None,
        typer.Argument(help="Node hostname or UUID to reboot (defaults to current node)."),
    ] = None,
    yes: Annotated[
        bool,
        typer.Option("-y", "--yes", help="Skip confirmation prompt."),
    ] = False,
) -> None:
    """Initiate a system reboot on a node."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        target = client.resolve_node_hostname(node) or client.context.hostname or "current node"
        if not yes:
            typer.confirm(f"Reboot node '{target}'?", abort=True)
        client.post("/basic/system/reboot", node=target)
    console.print(f"[yellow]Reboot initiated for node '{target}'.[/yellow]")


@node_app.command("remove")
def node_remove(
    ctx: typer.Context,
    node: Annotated[str, typer.Argument(help="Node hostname or UUID to remove from the cluster.")],
    retain_guests: Annotated[
        bool,
        typer.Option(
            "--retain-guests/--no-retain-guests", help="Keep the node's VM and jail registrations."
        ),
    ] = True,
    force: Annotated[
        bool,
        typer.Option("--force", help="Force remove an offline, externally fenced peer."),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option("-y", "--yes", help="Skip confirmation prompt."),
    ] = False,
) -> None:
    """Remove a peer node from the cluster."""
    state: CLIState = ctx.obj
    with state.get_client() as client:
        node_uuid, host = client.resolve_node_uuid(node)
        if not yes:
            typer.confirm(f"Remove node '{host}' ({node_uuid}) from the cluster?", abort=True)
        if force:
            client.post(
                "/cluster/remove-node/force",
                json_body={"nodeId": node_uuid, "targetExternallyFenced": True},
            )
        else:
            client.post(
                "/cluster/remove-node",
                json_body={"nodeId": node_uuid, "retainGuests": retain_guests},
            )
    console.print(f"[green]Removed node '{host}' ({node_uuid}) from the cluster.[/green]")


@node_app.command("audit-logs")
def node_audit_logs(
    ctx: typer.Context,
    node: Annotated[
        str | None,
        typer.Option("-n", "--node", help="Target node hostname or UUID."),
    ] = None,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
) -> None:
    """Show recent audit records from a node (or all nodes)."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        results = client.fan_out_get("/info/audit-records", node=node)

    rows: list[dict[str, Any]] = []
    for host, data in results:
        if isinstance(data, list):
            for entry in data:
                if isinstance(entry, dict):
                    row = dict(entry)
                    row.setdefault("node", host)
                    rows.append(row)

    spec = [
        ColumnSpec("ID", "id", justify="right"),
        ColumnSpec("Node", "node"),
        ColumnSpec("User", "username"),
        ColumnSpec("Action", "action"),
        ColumnSpec("Path", "path"),
        ColumnSpec("Status", "status"),
        ColumnSpec("Created At", "createdAt", formatter=format_timestamp),
    ]
    print_list(rows, spec, fmt=fmt, selected_columns=columns, title="Node Audit Records")
