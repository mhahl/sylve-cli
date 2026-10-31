"""ZFS pools, datasets, snapshots, scrub schedules, and periodic snapshot commands."""

from __future__ import annotations

from typing import Annotated, Any

import typer

from sylve_cli.client import ResourceNotFoundError
from sylve_cli.formatter import (
    ColumnSpec,
    OutputFormat,
    format_bytes,
    format_percent,
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
    confirm_destructive,
)

zfs_app = typer.Typer(
    name="zfs",
    help="Query and manage ZFS storage pools, datasets, volumes, scrubs, and snapshots.",
    no_args_is_help=True,
    rich_markup_mode=None,
)

pool_app = typer.Typer(
    name="pool",
    help="Query and manage ZFS storage pools.",
    no_args_is_help=True,
    rich_markup_mode=None,
)
dataset_app = typer.Typer(
    name="dataset",
    help="Query and manage ZFS filesystems and volumes.",
    no_args_is_help=True,
    rich_markup_mode=None,
)
snapshot_app = typer.Typer(
    name="snapshot",
    help="Query and manage ZFS dataset snapshots.",
    no_args_is_help=True,
    rich_markup_mode=None,
)
periodic_app = typer.Typer(
    name="periodic",
    help="Manage periodic ZFS snapshot schedules.",
    no_args_is_help=True,
    rich_markup_mode=None,
)

zfs_app.add_typer(pool_app, name="pool")
zfs_app.add_typer(dataset_app, name="dataset")
zfs_app.add_typer(snapshot_app, name="snapshot")
zfs_app.add_typer(periodic_app, name="periodic")


def _resolve_pool_guid(client: Any, pool_ident: str, node: str | None) -> tuple[str, str]:
    """Resolve a pool name or GUID into (pool_guid, node_hostname)."""
    ident = pool_ident.strip()
    results = client.fan_out_get("/zfs/pools", node=node)
    for host, pools in results:
        if isinstance(pools, list):
            for p in pools:
                if not isinstance(p, dict):
                    continue
                guid = str(p.get("pool_guid") or p.get("guid") or "")
                name = str(p.get("name") or "")
                if ident.lower() in (guid.lower(), name.lower()):
                    return guid, host
    if ident.isdigit():
        return ident, client.resolve_node_hostname(node) or ""
    raise ResourceNotFoundError(f"ZFS pool '{pool_ident}' not found.")


def _resolve_dataset_guid(
    client: Any,
    dataset_ident: str,
    dtype: str | None = None,
    node: str | None = None,
) -> tuple[str, str]:
    """Resolve a ZFS dataset or snapshot name or GUID into (guid, node_hostname)."""
    ident = dataset_ident.strip()
    params = {"type": dtype} if dtype else None
    results = client.fan_out_get("/zfs/datasets", params=params, node=node)
    for host, datasets in results:
        if isinstance(datasets, list):
            for ds in datasets:
                if not isinstance(ds, dict):
                    continue
                guid = str(ds.get("guid") or "")
                name = str(ds.get("name") or "")
                if ident.lower() in (guid.lower(), name.lower()):
                    return guid, host
    return ident, client.resolve_node_hostname(node) or ""


# ------------------------------------------------------------------
# ZFS Pools
# ------------------------------------------------------------------
@pool_app.command("list")
def pool_list(
    ctx: typer.Context,
    all_pools: Annotated[
        bool,
        typer.Option("--all", "-a", help="Include pools not marked usable in Sylve settings."),
    ] = False,
    node: NodeOption = None,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
    sort_column: SortColumnOption = None,
    long: LongOption = False,
    filters: FilterOption = None,
    limit: LimitOption = None,
) -> None:
    """List ZFS storage pools across cluster nodes."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        results = client.fan_out_get(
            "/zfs/pools",
            params={"all": all_pools} if all_pools else None,
            node=node,
        )

    rows: list[dict[str, Any]] = []
    for host, data in results:
        if isinstance(data, list):
            for p in data:
                if not isinstance(p, dict):
                    continue
                row = dict(p)
                row["node"] = host
                rows.append(row)

    spec = [
        ColumnSpec("Name", "name"),
        ColumnSpec("Node", "node"),
        ColumnSpec("State", "state"),
        ColumnSpec("Size", "size", formatter=format_bytes, justify="right"),
        ColumnSpec("Free", "free", formatter=format_bytes, justify="right"),
        ColumnSpec("Frag%", "fragmentation", formatter=format_percent, justify="right"),
    ]
    if long:
        spec = [
            ColumnSpec("Name", "name"),
            ColumnSpec("GUID", "pool_guid"),
            ColumnSpec("Node", "node"),
            ColumnSpec("State", "state"),
            ColumnSpec("Size", "size", formatter=format_bytes, justify="right"),
            ColumnSpec("Allocated", "allocated", formatter=format_bytes, justify="right"),
            ColumnSpec("Free", "free", formatter=format_bytes, justify="right"),
            ColumnSpec("Frag%", "fragmentation", formatter=format_percent, justify="right"),
            ColumnSpec("Dedup", "dedup_ratio", justify="right"),
        ]
    print_list(
        rows,
        spec,
        fmt=fmt,
        selected_columns=columns,
        sort_column=sort_column,
        title="ZFS Storage Pools",
        filters=filters,
        limit=limit,
    )


@pool_app.command("status")
@pool_app.command("show")
def pool_status(
    ctx: typer.Context,
    pool: Annotated[str, typer.Argument(help="ZFS pool name or GUID.")],
    node: NodeOption = None,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
) -> None:
    """Show detailed vdev topology, health, and scrub status of a ZFS pool."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        guid, host = _resolve_pool_guid(client, pool, node=node)
        data = client.get(f"/zfs/pools/{guid}/status", node=host or None) or {}
    if isinstance(data, dict):
        data["node"] = host
        print_dict(
            data, fmt=fmt, selected_columns=columns, title=f"ZFS Pool Status: {pool} ({host})"
        )


@pool_app.command("scrub")
def pool_scrub(
    ctx: typer.Context,
    pool: Annotated[str, typer.Argument(help="ZFS pool name or GUID to scrub.")],
    node: NodeOption = None,
    fmt: FormatOption = OutputFormat.table,
) -> None:
    """Start a ZFS scrub on a storage pool."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        guid, host = _resolve_pool_guid(client, pool, node=node)
        client.post(f"/zfs/pools/{guid}/scrub", node=host or None)
    print_result(
        {"pool": pool, "node": host or "local", "action": "scrub"},
        fmt,
        f"Started scrub on ZFS pool '{pool}' ({host or 'local'}).",
    )


# ------------------------------------------------------------------
# ZFS Datasets
# ------------------------------------------------------------------
@dataset_app.command("list")
def dataset_list(
    ctx: typer.Context,
    dataset_type: Annotated[
        str | None,
        typer.Option("--type", "-t", help="Filter by type: FILESYSTEM, VOLUME, SNAPSHOT, ALL."),
    ] = None,
    node: NodeOption = None,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
    sort_column: SortColumnOption = None,
    long: LongOption = False,
    filters: FilterOption = None,
    limit: LimitOption = None,
) -> None:
    """List ZFS datasets across cluster nodes."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        params = {"type": dataset_type.upper()} if dataset_type else None
        results = client.fan_out_get("/zfs/datasets", params=params, node=node)

    rows: list[dict[str, Any]] = []
    for host, data in results:
        if isinstance(data, list):
            for ds in data:
                if not isinstance(ds, dict):
                    continue
                row = dict(ds)
                row["node"] = host
                rows.append(row)

    spec = [
        ColumnSpec("Name", "name"),
        ColumnSpec("Node", "node"),
        ColumnSpec("Type", "type"),
        ColumnSpec("Used", "used", formatter=format_bytes, justify="right"),
        ColumnSpec("Avail", "available", formatter=format_bytes, justify="right"),
        ColumnSpec("Mountpoint", "mountpoint"),
    ]
    if long:
        spec = [
            ColumnSpec("Name", "name"),
            ColumnSpec("GUID", "guid"),
            ColumnSpec("Node", "node"),
            ColumnSpec("Pool", "pool"),
            ColumnSpec("Type", "type"),
            ColumnSpec("Used", "used", formatter=format_bytes, justify="right"),
            ColumnSpec("Avail", "available", formatter=format_bytes, justify="right"),
            ColumnSpec("Refer", "referenced", formatter=format_bytes, justify="right"),
            ColumnSpec("Mountpoint", "mountpoint"),
        ]
    print_list(
        rows,
        spec,
        fmt=fmt,
        selected_columns=columns,
        sort_column=sort_column,
        title="ZFS Datasets",
        filters=filters,
        limit=limit,
    )


@dataset_app.command("create-fs")
def dataset_create_fs(
    ctx: typer.Context,
    parent: Annotated[
        str, typer.Option("--parent", "-p", help="Parent dataset path (e.g. zroot).")
    ],
    name: Annotated[str, typer.Option("--name", help="New filesystem name.")],
    node: NodeOption = None,
    fmt: FormatOption = OutputFormat.table,
) -> None:
    """Create a new ZFS filesystem dataset."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        client.post(
            "/zfs/datasets/filesystem",
            json_body={"parent": parent, "name": name, "properties": {}},
            node=node,
        )
    print_result(
        {"name": f"{parent}/{name}", "type": "filesystem"},
        fmt,
        f"Created ZFS filesystem '{parent}/{name}'.",
    )


@dataset_app.command("create-vol")
def dataset_create_vol(
    ctx: typer.Context,
    parent: Annotated[
        str, typer.Option("--parent", "-p", help="Parent dataset path (e.g. zroot).")
    ],
    name: Annotated[str, typer.Option("--name", help="New ZFS volume name.")],
    size: Annotated[str, typer.Option("--size", "-s", help="Volume size (e.g. 10G).")],
    node: NodeOption = None,
    fmt: FormatOption = OutputFormat.table,
) -> None:
    """Create a new ZFS volume (zvol)."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        client.post(
            "/zfs/datasets/volume",
            json_body={"parent": parent, "name": name, "properties": {"volsize": size}},
            node=node,
        )
    print_result(
        {"name": f"{parent}/{name}", "type": "volume", "size": size},
        fmt,
        f"Created ZFS volume '{parent}/{name}' ({size}).",
    )


@dataset_app.command("delete")
def dataset_delete(
    ctx: typer.Context,
    dataset: Annotated[str, typer.Argument(help="Dataset name or GUID.")],
    dtype: Annotated[
        str,
        typer.Option("--type", "-t", help="Dataset type: 'filesystem' or 'volume'."),
    ] = "filesystem",
    yes: Annotated[bool, typer.Option("-y", "--yes", help="Skip confirmation prompt.")] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Print what would be deleted without deleting it."),
    ] = False,
    node: NodeOption = None,
    fmt: FormatOption = OutputFormat.table,
) -> None:
    """Delete a ZFS filesystem or volume."""
    norm_type = dtype.strip().lower()
    if norm_type not in ("filesystem", "volume"):
        raise typer.BadParameter("Dataset type must be 'filesystem' or 'volume'.")
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        guid, host = _resolve_dataset_guid(client, dataset, node=node)
        if dry_run:
            print_result(
                {
                    "action": "delete-dataset",
                    "dataset": dataset,
                    "type": norm_type,
                    "guid": guid,
                    "node": host or "local",
                },
                fmt,
                f"Dry run: would delete ZFS {norm_type} '{dataset}'.",
            )
            return
        confirm_destructive(
            f"Delete ZFS {norm_type} '{dataset}' ({guid}) on {host or 'local'}?", yes=yes
        )
        client.delete(f"/zfs/datasets/{norm_type}/{guid}", node=host or None)
    print_result(
        {"dataset": dataset, "type": norm_type, "deleted": True},
        fmt,
        f"Deleted ZFS {norm_type} '{dataset}'.",
    )


# ------------------------------------------------------------------
# ZFS Snapshots
# ------------------------------------------------------------------
@snapshot_app.command("list")
def snapshot_list(
    ctx: typer.Context,
    node: NodeOption = None,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
    sort_column: SortColumnOption = None,
) -> None:
    """List ZFS dataset snapshots across cluster nodes."""
    dataset_list(
        ctx=ctx,
        dataset_type="SNAPSHOT",
        node=node,
        fmt=fmt,
        columns=columns,
        sort_column=sort_column,
    )


@snapshot_app.command("create")
def snapshot_create(
    ctx: typer.Context,
    dataset: Annotated[str, typer.Argument(help="Target dataset name or GUID.")],
    name: Annotated[str, typer.Option("--name", "-m", help="Snapshot name (after @).")],
    recursive: Annotated[
        bool,
        typer.Option("-r", "--recursive/--no-recursive", help="Create snapshot recursively."),
    ] = False,
    node: NodeOption = None,
    fmt: FormatOption = OutputFormat.table,
) -> None:
    """Create a ZFS snapshot of a dataset."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        guid, host = _resolve_dataset_guid(client, dataset, node=node)
        client.post(
            "/zfs/datasets/snapshot",
            json_body={"guid": guid, "name": name, "recursive": recursive},
            node=host or None,
        )
    print_result(
        {"snapshot": f"{dataset}@{name}"}, fmt, f"Created ZFS snapshot '{dataset}@{name}'."
    )


@snapshot_app.command("rollback")
def snapshot_rollback(
    ctx: typer.Context,
    snapshot: Annotated[str, typer.Argument(help="Snapshot name (dataset@snap) or GUID.")],
    destroy_more_recent: Annotated[
        bool,
        typer.Option("--destroy-more-recent", help="Destroy newer snapshots during rollback."),
    ] = False,
    yes: Annotated[bool, typer.Option("-y", "--yes", help="Skip confirmation prompt.")] = False,
    node: NodeOption = None,
    fmt: FormatOption = OutputFormat.table,
) -> None:
    """Roll back to a ZFS snapshot."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        guid, host = _resolve_dataset_guid(client, snapshot, dtype="SNAPSHOT", node=node)
        confirm_destructive(f"Roll back to snapshot '{snapshot}' ({guid})?", yes=yes)
        client.post(
            f"/zfs/datasets/snapshot/{guid}/rollback",
            json_body={"destroyMoreRecent": destroy_more_recent},
            node=host or None,
        )
    print_result(
        {"snapshot": snapshot, "rolledBack": True}, fmt, f"Rolled back to snapshot '{snapshot}'."
    )


@snapshot_app.command("delete")
def snapshot_delete(
    ctx: typer.Context,
    snapshot: Annotated[str, typer.Argument(help="Snapshot name (dataset@snap) or GUID.")],
    recursive: Annotated[
        bool,
        typer.Option(
            "-r", "--recursive/--no-recursive", help="Delete child snapshots recursively."
        ),
    ] = False,
    yes: Annotated[bool, typer.Option("-y", "--yes", help="Skip confirmation prompt.")] = False,
    node: NodeOption = None,
    fmt: FormatOption = OutputFormat.table,
) -> None:
    """Delete a ZFS snapshot."""
    state: CLIState = ctx.obj
    confirm_destructive(f"Delete ZFS snapshot '{snapshot}'?", yes=yes)
    with state.get_client(node_override=node) as client:
        guid, host = _resolve_dataset_guid(client, snapshot, dtype="SNAPSHOT", node=node)
        client.delete(
            f"/zfs/datasets/snapshot/{guid}",
            params={"recursive": recursive},
            node=host or None,
        )
    print_result(
        {"snapshot": snapshot, "deleted": True}, fmt, f"Deleted ZFS snapshot '{snapshot}'."
    )


# ------------------------------------------------------------------
# Periodic Snapshot Jobs
# ------------------------------------------------------------------
@periodic_app.command("list")
def periodic_list(
    ctx: typer.Context,
    node: NodeOption = None,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
    long: LongOption = False,
) -> None:
    """List periodic ZFS snapshot schedules."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        results = client.fan_out_get("/zfs/datasets/snapshot/periodic", node=node)
    rows: list[dict[str, Any]] = []
    for host, data in results:
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    r = dict(item)
                    r["node"] = host
                    rows.append(r)
    spec = [
        ColumnSpec("ID", "id", justify="right"),
        ColumnSpec("Node", "node"),
        ColumnSpec("Prefix", "prefix"),
        ColumnSpec("Cron", "cronExpr"),
        ColumnSpec("Keep Last", "keepLast", justify="right"),
        ColumnSpec("Last Run", "lastRunAt", formatter=format_timestamp),
    ]
    if long:
        spec = [
            ColumnSpec("ID", "id", justify="right"),
            ColumnSpec("Node", "node"),
            ColumnSpec("Pool", "pool"),
            ColumnSpec("GUID", "guid"),
            ColumnSpec("Prefix", "prefix"),
            ColumnSpec("Cron", "cronExpr"),
            ColumnSpec("Recursive", "recursive"),
            ColumnSpec("Keep Last", "keepLast", justify="right"),
            ColumnSpec("Last Run", "lastRunAt", formatter=format_timestamp),
            ColumnSpec("Next Run", "nextRunAt", formatter=format_timestamp),
        ]
    print_list(rows, spec, fmt=fmt, selected_columns=columns, title="Periodic ZFS Snapshot Jobs")
