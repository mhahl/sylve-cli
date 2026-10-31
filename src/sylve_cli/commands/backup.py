"""Cluster backup targets, scheduled backup jobs, snapshots, and restore commands."""

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
from sylve_cli.tasks import wait_for_backup_event

backup_app = typer.Typer(
    name="backup",
    help="Manage cluster backup targets, scheduled jobs, snapshots, restores, and events.",
    no_args_is_help=True,
    rich_markup_mode=None,
)

target_app = typer.Typer(
    name="target",
    help="Manage cluster backup targets.",
    no_args_is_help=True,
    rich_markup_mode=None,
)
job_app = typer.Typer(
    name="job", help="Manage scheduled backup jobs.", no_args_is_help=True, rich_markup_mode=None
)
backup_event_app = typer.Typer(
    name="event",
    help="Query backup events and live progress.",
    no_args_is_help=True,
    rich_markup_mode=None,
)

backup_app.add_typer(target_app, name="target")
backup_app.add_typer(job_app, name="job")
backup_app.add_typer(backup_event_app, name="event")


# ------------------------------------------------------------------
# Backup Targets
# ------------------------------------------------------------------
@target_app.command("list")
def target_list(
    ctx: typer.Context,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
    sort_column: SortColumnOption = None,
    long: LongOption = False,
    filters: FilterOption = None,
    limit: LimitOption = None,
) -> None:
    """List cluster backup targets."""
    state: CLIState = ctx.obj
    with state.get_client() as client:
        targets = client.get("/cluster/backups/targets") or []
    spec = [
        ColumnSpec("ID", "id", justify="right"),
        ColumnSpec("Name", "name"),
        ColumnSpec("SSH Host", "sshHost"),
        ColumnSpec("Enabled", "enabled"),
    ]
    if long:
        spec = [
            ColumnSpec("ID", "id", justify="right"),
            ColumnSpec("Name", "name"),
            ColumnSpec("SSH Host", "sshHost"),
            ColumnSpec("Port", "sshPort", justify="right"),
            ColumnSpec("Backup Root", "backupRoot"),
            ColumnSpec("Enabled", "enabled"),
            ColumnSpec("Description", "description"),
        ]
    print_list(
        targets if isinstance(targets, list) else [],
        spec,
        fmt=fmt,
        selected_columns=columns,
        sort_column=sort_column,
        title="Backup Targets",
        filters=filters,
        limit=limit,
    )


@target_app.command("show")
def target_show(
    ctx: typer.Context,
    target_id: Annotated[int, typer.Argument(help="Backup target ID.")],
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
) -> None:
    """Display full details and per-node readiness for a backup target."""
    state: CLIState = ctx.obj
    with state.get_client() as client:
        targets = client.get("/cluster/backups/targets") or []
    if isinstance(targets, list):
        for t in targets:
            if isinstance(t, dict) and int(t.get("id") or 0) == target_id:
                print_dict(
                    t, fmt=fmt, selected_columns=columns, title=f"Backup Target #{target_id}"
                )
                return
    raise ResourceNotFoundError(f"Backup target #{target_id} not found.")


@target_app.command("datasets")
def target_datasets(
    ctx: typer.Context,
    target_id: Annotated[int, typer.Argument(help="Backup target ID.")],
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
    long: LongOption = False,
) -> None:
    """List restorable datasets on a backup target."""
    state: CLIState = ctx.obj
    with state.get_client() as client:
        datasets = client.get(f"/cluster/backups/targets/{target_id}/datasets") or []
    spec = [
        ColumnSpec("Dataset", "name"),
        ColumnSpec("Kind", "kind"),
        ColumnSpec("Snapshots", "snapshotCount", justify="right"),
        ColumnSpec("Encrypted", "encrypted"),
    ]
    if long:
        spec = [
            ColumnSpec("Dataset", "name"),
            ColumnSpec("Kind", "kind"),
            ColumnSpec("Lineage", "lineage"),
            ColumnSpec("VM RID", "vmRid", justify="right"),
            ColumnSpec("Jail CTID", "jailCtId", justify="right"),
            ColumnSpec("Snapshots", "snapshotCount", justify="right"),
            ColumnSpec("Encrypted", "encrypted"),
        ]
    print_list(
        datasets if isinstance(datasets, list) else [],
        spec,
        fmt=fmt,
        selected_columns=columns,
        title=f"Backup Target #{target_id} Datasets",
    )


@target_app.command("validate")
def target_validate(
    ctx: typer.Context,
    target_id: Annotated[int, typer.Argument(help="Backup target ID.")],
    fmt: FormatOption = OutputFormat.table,
) -> None:
    """Validate connectivity and readiness for a backup target."""
    state: CLIState = ctx.obj
    with state.get_client() as client:
        client.post(f"/cluster/backups/targets/{target_id}/validate")
    print_result(
        {"id": target_id, "valid": True}, fmt, f"Backup target #{target_id} validated successfully."
    )


@target_app.command("delete")
def target_delete(
    ctx: typer.Context,
    target_id: Annotated[int, typer.Argument(help="Backup target ID.")],
    yes: Annotated[bool, typer.Option("-y", "--yes", help="Skip confirmation prompt.")] = False,
    fmt: FormatOption = OutputFormat.table,
) -> None:
    """Delete a disabled backup target."""
    confirm_destructive(f"Delete backup target #{target_id}?", yes=yes)
    state: CLIState = ctx.obj
    with state.get_client() as client:
        client.delete(f"/cluster/backups/targets/{target_id}")
    print_result({"id": target_id, "deleted": True}, fmt, f"Deleted backup target #{target_id}.")


# ------------------------------------------------------------------
# Backup Jobs
# ------------------------------------------------------------------
@job_app.command("list")
def job_list(
    ctx: typer.Context,
    target_id: Annotated[
        int | None, typer.Option("--target-id", help="Filter by backup target ID.")
    ] = None,
    guest_type: Annotated[
        str | None, typer.Option("--guest-type", help="Filter by guest type (vm or jail).")
    ] = None,
    guest_id: Annotated[int | None, typer.Option("--guest-id", help="Filter by guest ID.")] = None,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
    sort_column: SortColumnOption = None,
    long: LongOption = False,
    filters: FilterOption = None,
    limit: LimitOption = None,
) -> None:
    """List scheduled backup jobs."""
    state: CLIState = ctx.obj
    with state.get_client() as client:
        jobs = (
            client.get(
                "/cluster/backups/jobs",
                params={"targetId": target_id, "guestType": guest_type, "guestId": guest_id},
            )
            or []
        )
    spec = [
        ColumnSpec("ID", "id", justify="right"),
        ColumnSpec("Name", "name"),
        ColumnSpec("Mode", "mode"),
        ColumnSpec("Last Status", "lastStatus"),
        ColumnSpec("Last Run", "lastRunAt", formatter=format_timestamp),
        ColumnSpec("Enabled", "enabled"),
    ]
    if long:
        spec = [
            ColumnSpec("ID", "id", justify="right"),
            ColumnSpec("Name", "name"),
            ColumnSpec("Mode", "mode"),
            ColumnSpec("Source", "friendlySrc"),
            ColumnSpec("Target ID", "targetId", justify="right"),
            ColumnSpec("Runner Node", "runnerNodeId"),
            ColumnSpec("Cron", "cronExpr"),
            ColumnSpec("Last Status", "lastStatus"),
            ColumnSpec("Last Run", "lastRunAt", formatter=format_timestamp),
            ColumnSpec("Enabled", "enabled"),
        ]
    print_list(
        jobs if isinstance(jobs, list) else [],
        spec,
        fmt=fmt,
        selected_columns=columns,
        sort_column=sort_column,
        title="Backup Jobs",
        filters=filters,
        limit=limit,
    )


@job_app.command("run")
def job_run(
    ctx: typer.Context,
    job_id: Annotated[int, typer.Argument(help="Backup job ID to run immediately.")],
    fmt: FormatOption = OutputFormat.table,
) -> None:
    """Queue an immediate run of a backup job."""
    state: CLIState = ctx.obj
    with state.get_client() as client:
        client.post(f"/cluster/backups/jobs/{job_id}/run")
    print_result(
        {"id": job_id, "status": "queued"}, fmt, f"Queued immediate run for backup job #{job_id}."
    )


@job_app.command("snapshots")
def job_snapshots(
    ctx: typer.Context,
    job_id: Annotated[int, typer.Argument(help="Backup job ID.")],
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max snapshots to return.")] = 100,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
    long: LongOption = False,
) -> None:
    """List restorable snapshots produced by a backup job."""
    state: CLIState = ctx.obj
    with state.get_client() as client:
        page: dict[str, Any] = (
            client.get(f"/cluster/backups/jobs/{job_id}/snapshots", params={"limit": limit}) or {}
        )
    items = [item for item in page.get("items") or [] if isinstance(item, dict)]
    spec = [
        ColumnSpec("Snapshot", "shortName"),
        ColumnSpec("Used", "used", justify="right"),
        ColumnSpec("Created At", "creation", formatter=format_timestamp),
    ]
    if long:
        spec = [
            ColumnSpec("Snapshot", "shortName"),
            ColumnSpec("Full Name", "name"),
            ColumnSpec("Lineage", "lineage"),
            ColumnSpec("Used", "used", justify="right"),
            ColumnSpec("Refer", "refer", justify="right"),
            ColumnSpec("Committed", "committed"),
            ColumnSpec("Created At", "creation", formatter=format_timestamp),
        ]
    print_list(
        items, spec, fmt=fmt, selected_columns=columns, title=f"Backup Job #{job_id} Snapshots"
    )


@job_app.command("restore")
def job_restore(
    ctx: typer.Context,
    job_id: Annotated[int, typer.Argument(help="Backup job ID.")],
    snapshot: Annotated[str, typer.Option("--snapshot", "-s", help="Snapshot name to restore.")],
    encryption_key: Annotated[
        str | None, typer.Option("--encryption-key", help="Decryption key if encrypted.")
    ] = None,
) -> None:
    """Queue restoration of a snapshot from a backup job."""
    state: CLIState = ctx.obj
    body: dict[str, Any] = {"snapshot": snapshot}
    if encryption_key:
        body["encryptionKey"] = encryption_key
    with state.get_client() as client:
        client.post(f"/cluster/backups/jobs/{job_id}/restore", json_body=body)
    console.print(
        f"[green]Queued restore of snapshot '{snapshot}' from backup job #{job_id}.[/green]"
    )


@job_app.command("delete")
def job_delete(
    ctx: typer.Context,
    job_id: Annotated[int, typer.Argument(help="Backup job ID to delete.")],
    yes: Annotated[bool, typer.Option("-y", "--yes", help="Skip confirmation prompt.")] = False,
    fmt: FormatOption = OutputFormat.table,
) -> None:
    """Delete a backup job."""
    confirm_destructive(f"Delete backup job #{job_id}?", yes=yes)
    state: CLIState = ctx.obj
    with state.get_client() as client:
        client.delete(f"/cluster/backups/jobs/{job_id}")
    print_result({"id": job_id, "deleted": True}, fmt, f"Deleted backup job #{job_id}.")


# ------------------------------------------------------------------
# Backup Events
# ------------------------------------------------------------------
@backup_event_app.command("list")
def backup_event_list(
    ctx: typer.Context,
    job_id: Annotated[int | None, typer.Option("--job-id", help="Filter by backup job ID.")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Maximum events.")] = 50,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
    long: LongOption = False,
) -> None:
    """List recent backup events."""
    state: CLIState = ctx.obj
    with state.get_client() as client:
        events = (
            client.get(
                "/cluster/backups/events",
                params={"jobId": job_id, "limit": limit},
            )
            or []
        )
    spec = [
        ColumnSpec("ID", "id", justify="right"),
        ColumnSpec("Job ID", "jobId", justify="right"),
        ColumnSpec("Status", "status"),
        ColumnSpec("Started At", "startedAt", formatter=format_timestamp),
        ColumnSpec("Completed At", "completedAt", formatter=format_timestamp),
    ]
    if long:
        spec = [
            ColumnSpec("ID", "id", justify="right"),
            ColumnSpec("Job ID", "jobId", justify="right"),
            ColumnSpec("Mode", "mode"),
            ColumnSpec("Source Dataset", "sourceDataset"),
            ColumnSpec("Target Endpoint", "targetEndpoint"),
            ColumnSpec("Status", "status"),
            ColumnSpec("Started At", "startedAt", formatter=format_timestamp),
            ColumnSpec("Completed At", "completedAt", formatter=format_timestamp),
        ]
    print_list(
        events if isinstance(events, list) else [],
        spec,
        fmt=fmt,
        selected_columns=columns,
        title="Backup Events",
    )


@backup_event_app.command("show")
def backup_event_show(
    ctx: typer.Context,
    event_id: Annotated[int, typer.Argument(help="Backup event ID.")],
    wait: WaitOption = False,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
) -> None:
    """Show details (or follow live progress with --wait) of a backup event."""
    state: CLIState = ctx.obj
    with state.get_client() as client:
        if wait:
            data = wait_for_backup_event(client, event_id)
        else:
            data = client.get(f"/cluster/backups/events/{event_id}") or {}
    if isinstance(data, dict):
        print_dict(data, fmt=fmt, selected_columns=columns, title=f"Backup Event #{event_id}")
