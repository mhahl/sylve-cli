"""Cluster HA Replication policies, failovers, and replication events commands."""

from __future__ import annotations

from typing import Annotated, Any

import typer

from sylve_cli.client import ResourceNotFoundError
from sylve_cli.formatter import (
    ColumnSpec,
    OutputFormat,
    console,
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
    SortColumnOption,
    WaitOption,
    confirm_destructive,
)
from sylve_cli.tasks import wait_for_replication_event

replication_app = typer.Typer(
    name="replication",
    help="Manage cluster HA replication policies, manual runs, failovers, and events.",
    no_args_is_help=True,
    rich_markup_mode=None,
)

policy_app = typer.Typer(
    name="policy",
    help="Manage cluster replication policies.",
    no_args_is_help=True,
    rich_markup_mode=None,
)
event_app = typer.Typer(
    name="event",
    help="Query replication events and live progress.",
    no_args_is_help=True,
    rich_markup_mode=None,
)

replication_app.add_typer(policy_app, name="policy")
replication_app.add_typer(event_app, name="event")


@policy_app.command("list")
def policy_list(
    ctx: typer.Context,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
    sort_column: SortColumnOption = None,
    long: LongOption = False,
    filters: FilterOption = None,
    limit: LimitOption = None,
) -> None:
    """List cluster replication policies and their current HA state."""
    state: CLIState = ctx.obj
    with state.get_client() as client:
        policies = client.get("/cluster/replication/policies") or []

    rows: list[dict[str, Any]] = []
    if isinstance(policies, list):
        for p in policies:
            if not isinstance(p, dict):
                continue
            targets = [
                f"{t.get('nodeId')}(w={t.get('weight', 100)},{'ready' if t.get('ready') else 'not-ready'})"
                for t in (p.get("targets") or [])
                if isinstance(t, dict)
            ]
            row = dict(p)
            row["targets_summary"] = ", ".join(targets)
            rows.append(row)

    spec = [
        ColumnSpec("ID", "id", justify="right"),
        ColumnSpec("Name", "name"),
        ColumnSpec("Guest Type", "guestType"),
        ColumnSpec("Guest ID", "guestId", justify="right"),
        ColumnSpec("Active Node", "activeNodeId"),
        ColumnSpec("Last Status", "lastStatus"),
        ColumnSpec("Enabled", "enabled"),
    ]
    if long:
        spec = [
            ColumnSpec("ID", "id", justify="right"),
            ColumnSpec("Name", "name"),
            ColumnSpec("Guest Type", "guestType"),
            ColumnSpec("Guest ID", "guestId", justify="right"),
            ColumnSpec("Active Node", "activeNodeId"),
            ColumnSpec("Targets", "targets_summary"),
            ColumnSpec("Cron", "cronExpr"),
            ColumnSpec("HA Eligible", "haEligible"),
            ColumnSpec("Last Status", "lastStatus"),
            ColumnSpec("Enabled", "enabled"),
        ]
    print_list(
        rows,
        spec,
        fmt=fmt,
        selected_columns=columns,
        sort_column=sort_column,
        title="Replication Policies",
        filters=filters,
        limit=limit,
    )


@policy_app.command("show")
def policy_show(
    ctx: typer.Context,
    policy_id: Annotated[int, typer.Argument(help="Replication policy ID.")],
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
) -> None:
    """Display full details of a replication policy."""
    state: CLIState = ctx.obj
    with state.get_client() as client:
        policies = client.get("/cluster/replication/policies") or []
    if isinstance(policies, list):
        for p in policies:
            if isinstance(p, dict) and int(p.get("id") or 0) == policy_id:
                print_dict(
                    p, fmt=fmt, selected_columns=columns, title=f"Replication Policy #{policy_id}"
                )
                return
    raise ResourceNotFoundError(f"Replication policy #{policy_id} not found.")


@policy_app.command("create")
def policy_create(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", help="Policy name.")],
    guest_type: Annotated[str, typer.Option("--guest-type", help="Guest type: 'vm' or 'jail'.")],
    guest_id: Annotated[int, typer.Option("--guest-id", help="VM RID or Jail CTID.")],
    targets: Annotated[
        list[str],
        typer.Option(
            "--target",
            "-t",
            help="Target node hostname/UUID (optionally 'node:weight', repeatable).",
        ),
    ],
    cron: Annotated[str, typer.Option("--cron", help="Cron schedule expression.")] = "*/15 * * * *",
    failover_mode: Annotated[
        str, typer.Option("--failover-mode", help="Failover mode (manual or auto).")
    ] = "manual",
    enabled: Annotated[bool, typer.Option("--enabled/--disabled", help="Enable policy.")] = True,
) -> None:
    """Create a cluster replication policy for a VM or jail."""
    state: CLIState = ctx.obj
    with state.get_client() as client:
        target_reqs: list[dict[str, Any]] = []
        for raw_t in targets:
            if ":" in raw_t:
                n_part, w_part = raw_t.rsplit(":", 1)
                weight = int(w_part)
            else:
                n_part, weight = raw_t, 100
            uuid, _ = client.resolve_node_uuid(n_part)
            target_reqs.append({"nodeId": uuid, "weight": weight})

        client.post(
            "/cluster/replication/policies",
            json_body={
                "name": name,
                "guestType": guest_type.strip().lower(),
                "guestId": guest_id,
                "targets": target_reqs,
                "cronExpr": cron,
                "failoverMode": failover_mode,
                "enabled": enabled,
            },
        )
    console.print(
        f"[green]Created replication policy '{name}' for {guest_type} {guest_id}.[/green]"
    )


@policy_app.command("run")
def policy_run(
    ctx: typer.Context,
    policy_id: Annotated[int, typer.Argument(help="Replication policy ID to run now.")],
    fmt: FormatOption = OutputFormat.table,
) -> None:
    """Queue an immediate replication run for a policy."""
    state: CLIState = ctx.obj
    with state.get_client() as client:
        client.post(f"/cluster/replication/policies/{policy_id}/run")
    print_result(
        {"id": policy_id, "status": "queued"},
        fmt,
        f"Queued immediate run for replication policy #{policy_id}.",
    )


@policy_app.command("failover")
def policy_failover(
    ctx: typer.Context,
    policy_id: Annotated[int, typer.Argument(help="Replication policy ID to fail over.")],
    target_node: Annotated[
        str | None,
        typer.Option(
            "--target", "-t", help="Target node hostname or UUID (auto-selected if omitted)."
        ),
    ] = None,
    mode: Annotated[
        str,
        typer.Option("--mode", help="Failover mode: 'safe' or 'force'."),
    ] = "safe",
    move_pinned_source: Annotated[
        bool,
        typer.Option(
            "--move-pinned-source/--keep-pinned-source",
            help="Update pinned source node to new owner.",
        ),
    ] = True,
    confirm_data_loss: Annotated[
        bool,
        typer.Option(
            "--confirm-data-loss", help="Acknowledge potential data loss for forced failover."
        ),
    ] = False,
    fmt: FormatOption = OutputFormat.table,
) -> None:
    """Queue a safe or forced HA failover for a replication policy."""
    state: CLIState = ctx.obj
    with state.get_client() as client:
        target_uuid = ""
        if target_node:
            target_uuid, _ = client.resolve_node_uuid(target_node)
        body: dict[str, Any] = {
            "mode": mode,
            "movePinnedSource": move_pinned_source,
            "confirmDataLoss": confirm_data_loss,
        }
        if target_uuid:
            body["targetNodeId"] = target_uuid
        client.post(f"/cluster/replication/policies/{policy_id}/failover", json_body=body)
    print_result(
        {"id": policy_id, "mode": mode, "status": "queued"},
        fmt,
        f"Queued {mode} failover for replication policy #{policy_id}.",
    )


@policy_app.command("delete")
def policy_delete(
    ctx: typer.Context,
    policy_id: Annotated[int, typer.Argument(help="Replication policy ID to delete.")],
    yes: Annotated[bool, typer.Option("-y", "--yes", help="Skip confirmation prompt.")] = False,
    fmt: FormatOption = OutputFormat.table,
) -> None:
    """Delete a replication policy."""
    confirm_destructive(f"Delete replication policy #{policy_id}?", yes=yes)
    state: CLIState = ctx.obj
    with state.get_client() as client:
        client.delete(f"/cluster/replication/policies/{policy_id}")
    print_result(
        {"id": policy_id, "deleted": True}, fmt, f"Deleted replication policy #{policy_id}."
    )


@event_app.command("list")
def event_list(
    ctx: typer.Context,
    policy_id: Annotated[
        int | None, typer.Option("--policy-id", help="Filter by policy ID.")
    ] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Maximum events to return.")] = 50,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
    long: LongOption = False,
) -> None:
    """List recent replication events."""
    state: CLIState = ctx.obj
    with state.get_client() as client:
        events = (
            client.get(
                "/cluster/replication/events",
                params={"policyId": policy_id, "limit": limit},
            )
            or []
        )
    spec = [
        ColumnSpec("ID", "id", justify="right"),
        ColumnSpec("Policy ID", "policyId", justify="right"),
        ColumnSpec("Event Type", "eventType"),
        ColumnSpec("Guest", "guestType"),
        ColumnSpec("Status", "status"),
        ColumnSpec("Started At", "startedAt", formatter=format_timestamp),
    ]
    if long:
        spec = [
            ColumnSpec("ID", "id", justify="right"),
            ColumnSpec("Policy ID", "policyId", justify="right"),
            ColumnSpec("Event Type", "eventType"),
            ColumnSpec("Guest", "guestType"),
            ColumnSpec("Guest ID", "guestId", justify="right"),
            ColumnSpec("Source Node", "sourceNodeId"),
            ColumnSpec("Target Node", "targetNodeId"),
            ColumnSpec("Status", "status"),
            ColumnSpec("Started At", "startedAt", formatter=format_timestamp),
            ColumnSpec("Completed At", "completedAt", formatter=format_timestamp),
        ]
    print_list(
        events if isinstance(events, list) else [],
        spec,
        fmt=fmt,
        selected_columns=columns,
        title="Replication Events",
    )


@event_app.command("show")
def event_show(
    ctx: typer.Context,
    event_id: Annotated[int, typer.Argument(help="Replication event ID.")],
    wait: WaitOption = False,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
) -> None:
    """Show details (or follow live progress with --wait) of a replication event."""
    state: CLIState = ctx.obj
    with state.get_client() as client:
        if wait:
            data = wait_for_replication_event(client, event_id)
        else:
            data = client.get(f"/cluster/replication/events/{event_id}") or {}
    if isinstance(data, dict):
        print_dict(data, fmt=fmt, selected_columns=columns, title=f"Replication Event #{event_id}")
