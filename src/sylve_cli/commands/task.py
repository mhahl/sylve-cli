"""Guest lifecycle and migration task inspection and cancellation commands."""

from __future__ import annotations

from typing import Annotated, Any

import typer

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
from sylve_cli.tasks import wait_for_lifecycle_task

task_app = typer.Typer(
    name="task",
    help="Query active/recent guest lifecycle tasks, wait for completion, or cancel migrations.",
    no_args_is_help=True,
    rich_markup_mode=None,
)


@task_app.command("list")
def task_list(
    ctx: typer.Context,
    active_only: Annotated[
        bool,
        typer.Option("--active/--recent", help="Show only active (queued/running) tasks or recent tasks."),
    ] = False,
    guest_type: Annotated[
        str | None,
        typer.Option("--guest-type", help="Filter by guest type ('vm' or 'jail')."),
    ] = None,
    guest_id: Annotated[
        int | None,
        typer.Option("--guest-id", help="Filter by VM RID or Jail CTID."),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", "-l", help="Maximum recent tasks per node."),
    ] = 25,
    node: NodeOption = None,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
    sort_column: SortColumnOption = None,
    long: LongOption = False,
) -> None:
    """List active or recent guest lifecycle tasks across cluster nodes."""
    state: CLIState = ctx.obj
    endpoint = "/tasks/lifecycle/active" if active_only else "/tasks/lifecycle/recent"
    params: dict[str, Any] = {"guestType": guest_type, "guestId": guest_id}
    if not active_only:
        params["limit"] = limit

    with state.get_client(node_override=node) as client:
        results = client.fan_out_get(endpoint, params=params, node=node)

    rows: list[dict[str, Any]] = []
    for host, data in results:
        if isinstance(data, list):
            for t in data:
                if isinstance(t, dict):
                    row = dict(t)
                    row["node"] = host
                    rows.append(row)

    spec = [
        ColumnSpec("ID", "id", justify="right"),
        ColumnSpec("Node", "node"),
        ColumnSpec("Guest Type", "guestType"),
        ColumnSpec("Guest ID", "guestId", justify="right"),
        ColumnSpec("Action", "action"),
        ColumnSpec("Status", "status"),
        ColumnSpec("Created At", "createdAt"),
    ]
    if long:
        spec.extend(
            [
                ColumnSpec("Requested By", "requestedBy"),
                ColumnSpec("Message", "message"),
                ColumnSpec("Error", "error"),
            ]
        )
    print_list(
        rows,
        spec,
        fmt=fmt,
        selected_columns=columns,
        sort_column=sort_column,
        title="Active Lifecycle Tasks" if active_only else "Recent Lifecycle Tasks",
    )


@task_app.command("show")
def task_show(
    ctx: typer.Context,
    task_id: Annotated[int, typer.Argument(help="Lifecycle task ID.")],
    node: NodeOption = None,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
) -> None:
    """Display full details of a lifecycle task by ID."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        data = client.get(f"/tasks/lifecycle/{task_id}", node=node) or {}
    if isinstance(data, dict):
        print_dict(data, fmt=fmt, selected_columns=columns, title=f"Lifecycle Task #{task_id}")


@task_app.command("wait")
def task_wait(
    ctx: typer.Context,
    task_id: Annotated[int, typer.Argument(help="Lifecycle task ID to wait for.")],
    timeout: Annotated[float, typer.Option("--timeout", help="Timeout in seconds.")] = 600.0,
    node: NodeOption = None,
    fmt: FormatOption = OutputFormat.table,
) -> None:
    """Wait until a queued or running lifecycle task completes."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        result = wait_for_lifecycle_task(client, task_id, node=node, timeout=timeout)
    print_dict(result, fmt=fmt, title=f"Completed Task #{task_id}")


@task_app.command("cancel-migration")
def task_cancel_migration(
    ctx: typer.Context,
    task_id: Annotated[int, typer.Argument(help="Migration task ID to cancel.")],
    node: NodeOption = None,
) -> None:
    """Request cancellation of a queued or pre-cutover guest migration task."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        client.post(f"/tasks/migration/{task_id}/cancel", node=node)
    console.print(f"[yellow]Requested cancellation of migration task #{task_id}.[/yellow]")
