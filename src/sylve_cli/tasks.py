"""Asynchronous task and event polling helpers for Sylve lifecycle, migration, and Zelta tasks."""

from __future__ import annotations

import time
from typing import Any

from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from sylve_cli.client import SylveClient, SylveError
from sylve_cli.formatter import err_console, format_bytes

TERMINAL_TASK_STATUSES = {
    "success",
    "completed",
    "failed",
    "error",
    "cancelled",
    "canceled",
    "aborted",
    "interrupted",
}
FAILURE_TASK_STATUSES = {"failed", "error", "cancelled", "canceled", "aborted", "interrupted"}


def get_lifecycle_task(
    client: SylveClient,
    task_id: int,
    node: str | None = None,
) -> dict[str, Any] | None:
    """Fetch a lifecycle task by ID.

    Older server builds do not serve ``GET /tasks/lifecycle/{id}``; the web
    UI's catch-all answers with HTML. Fall back to the active/recent lists,
    which carry the same task records.

    Args:
        client: Sylve API client.
        task_id: Lifecycle task ID.
        node: Node to route the request to.

    Returns:
        dict[str, Any] | None: The task record, or ``None`` if it is not found.
    """
    data = client.get(f"/tasks/lifecycle/{task_id}", node=node)
    if isinstance(data, dict) and data.get("id") is not None:
        return data

    for path, params in (
        ("/tasks/lifecycle/active", None),
        ("/tasks/lifecycle/recent", {"limit": 100}),
    ):
        data = client.get(path, node=node, params=params)
        if isinstance(data, list):
            for task in data:
                if isinstance(task, dict) and str(task.get("id")) == str(task_id):
                    return task
    return None


def wait_for_lifecycle_task(
    client: SylveClient,
    task_id: int,
    node: str | None = None,
    timeout: float = 600.0,
    poll_interval: float = 1.5,
    quiet: bool = False,
) -> dict[str, Any]:
    """Poll a lifecycle task until it reaches a terminal status.

    Args:
        client: Sylve API client.
        task_id: Lifecycle task ID.
        node: Node to route the request to.
        timeout: Maximum wait in seconds.
        poll_interval: Seconds between polls.
        quiet: Suppress the progress spinner.

    Returns:
        dict[str, Any]: Terminal task record.

    Raises:
        SylveError: If the task fails, is cancelled, or times out.

    Example:
        >>> wait_for_lifecycle_task(client, 42, timeout=30)
    """
    deadline = time.monotonic() + timeout
    last_task: dict[str, Any] = {"id": task_id, "status": "queued"}

    if quiet:
        while time.monotonic() < deadline:
            data = get_lifecycle_task(client, task_id, node=node)
            if data is None:
                raise SylveError(f"Lifecycle task #{task_id} not found.")
            last_task = data
            status = str(data.get("status") or "").strip().lower()
            if status in TERMINAL_TASK_STATUSES:
                if status in FAILURE_TASK_STATUSES:
                    err_detail = data.get("error") or data.get("message") or status
                    raise SylveError(f"Task #{task_id} {status}: {err_detail}")
                return data
            time.sleep(poll_interval)
        raise SylveError(f"Timed out waiting for lifecycle task #{task_id} after {int(timeout)}s.")

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        TimeElapsedColumn(),
        console=err_console,
        transient=True,
    ) as progress:
        ptask = progress.add_task(f"Waiting for task #{task_id}...", total=None)
        while time.monotonic() < deadline:
            data = get_lifecycle_task(client, task_id, node=node)
            if data is None:
                raise SylveError(f"Lifecycle task #{task_id} not found.")
            last_task = data
            status = str(data.get("status") or "").strip().lower()
            action = str(data.get("action") or "task")
            gtype = str(data.get("guestType") or "")
            gid = data.get("guestId") or ""
            msg = str(data.get("message") or status)
            progress.update(
                ptask,
                description=f"Task #{task_id} ({gtype} {gid} {action}): {msg}",
            )
            if status in TERMINAL_TASK_STATUSES:
                if status in FAILURE_TASK_STATUSES:
                    err_detail = data.get("error") or data.get("message") or status
                    raise SylveError(f"Task #{task_id} {status}: {err_detail}")
                return data
            time.sleep(poll_interval)

    raise SylveError(
        f"Timed out waiting for lifecycle task #{task_id} after {int(timeout)}s "
        f"(last status: {last_task.get('status')})."
    )


def wait_for_replication_event(
    client: SylveClient,
    event_id: int,
    node_id: str | None = None,
    timeout: float = 1800.0,
    poll_interval: float = 2.0,
) -> dict[str, Any]:
    """Poll a replication event until it reaches a terminal status.

    Args:
        client: Sylve API client.
        event_id: Replication event ID.
        node_id: Optional node ID filter.
        timeout: Maximum wait in seconds.
        poll_interval: Seconds between polls.

    Returns:
        dict[str, Any]: Terminal replication event.

    Raises:
        SylveError: If the event fails or times out.

    Example:
        >>> wait_for_replication_event(client, 7, timeout=60)
    """
    deadline = time.monotonic() + timeout
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(),
        TextColumn("{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=err_console,
        transient=True,
    ) as progress:
        ptask = progress.add_task(f"Replication event #{event_id}", total=100.0)
        while time.monotonic() < deadline:
            params = {"nodeId": node_id} if node_id else None
            data = client.get(f"/cluster/replication/events/{event_id}/progress", params=params)
            if isinstance(data, dict):
                event_value = data.get("event")
                ev = event_value if isinstance(event_value, dict) else data
                pct = float(data.get("progressPercent") or 0.0)
                status = str(ev.get("status") or "").strip().lower()
                moved = data.get("movedBytes")
                total = data.get("totalBytes")
                transfer = (
                    f" ({format_bytes(moved)} / {format_bytes(total)})"
                    if moved is not None and total
                    else ""
                )
                progress.update(
                    ptask,
                    completed=min(100.0, max(0.0, pct)),
                    description=f"Replication event #{event_id} [{status}]{transfer}",
                )
                if status in TERMINAL_TASK_STATUSES:
                    if status in FAILURE_TASK_STATUSES:
                        err_detail = ev.get("error") or ev.get("message") or status
                        raise SylveError(f"Replication event #{event_id} {status}: {err_detail}")
                    return ev
            time.sleep(poll_interval)

    raise SylveError(f"Timed out waiting for replication event #{event_id}.")


def wait_for_backup_event(
    client: SylveClient,
    event_id: int,
    node_id: str | None = None,
    timeout: float = 3600.0,
    poll_interval: float = 2.0,
) -> dict[str, Any]:
    """Poll a backup event until it reaches a terminal status.

    Args:
        client: Sylve API client.
        event_id: Backup event ID.
        node_id: Optional node ID filter.
        timeout: Maximum wait in seconds.
        poll_interval: Seconds between polls.

    Returns:
        dict[str, Any]: Terminal backup event.

    Raises:
        SylveError: If the event fails or times out.

    Example:
        >>> wait_for_backup_event(client, 8, timeout=60)
    """
    deadline = time.monotonic() + timeout
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(),
        TextColumn("{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=err_console,
        transient=True,
    ) as progress:
        ptask = progress.add_task(f"Backup event #{event_id}", total=100.0)
        while time.monotonic() < deadline:
            params = {"nodeId": node_id} if node_id else None
            data = client.get(f"/cluster/backups/events/{event_id}/progress", params=params)
            if isinstance(data, dict):
                event_value = data.get("event")
                ev = event_value if isinstance(event_value, dict) else data
                pct = float(data.get("progressPercent") or 0.0)
                phase = str(data.get("phase") or ev.get("status") or "")
                status = str(ev.get("status") or "").strip().lower()
                moved = data.get("movedBytes")
                total = data.get("totalBytes")
                dataset = str(data.get("progressDataset") or "").strip()
                transfer = (
                    f" ({format_bytes(moved)} / {format_bytes(total)})"
                    if moved is not None and total
                    else ""
                )
                ds_label = f" {dataset}" if dataset else ""
                progress.update(
                    ptask,
                    completed=min(100.0, max(0.0, pct)),
                    description=f"Backup event #{event_id} [{phase}]{ds_label}{transfer}",
                )
                if status in TERMINAL_TASK_STATUSES:
                    if status in FAILURE_TASK_STATUSES:
                        err_detail = ev.get("error") or status
                        raise SylveError(f"Backup event #{event_id} {status}: {err_detail}")
                    return ev
            time.sleep(poll_interval)

    raise SylveError(f"Timed out waiting for backup event #{event_id}.")
