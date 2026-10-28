"""Downloader and ISO/disk-image management commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import typer

from sylve_cli.client import ResourceNotFoundError
from sylve_cli.formatter import (
    ColumnSpec,
    OutputFormat,
    console,
    format_bytes,
    format_percent,
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

download_app = typer.Typer(
    name="download",
    help="Query, start, upload, and manage ISO/image downloads across cluster nodes.",
    no_args_is_help=True,
    rich_markup_mode=None,
)


@download_app.command("list")
def download_list(
    ctx: typer.Context,
    node: NodeOption = None,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
    sort_column: SortColumnOption = None,
    long: LongOption = False,
) -> None:
    """List downloads across all cluster nodes (or a specific node with --node)."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        results = client.fan_out_get("/utilities/downloads", node=node)

    rows: list[dict[str, Any]] = []
    for host, data in results:
        if isinstance(data, list):
            for dl in data:
                if not isinstance(dl, dict):
                    continue
                row = dict(dl)
                row["node"] = host
                rows.append(row)

    spec = [
        ColumnSpec("ID", "id", justify="right"),
        ColumnSpec("Name", "name"),
        ColumnSpec("Node", "node"),
        ColumnSpec("Size", "size", formatter=format_bytes, justify="right"),
        ColumnSpec("Progress", "progress", formatter=format_percent, justify="right"),
        ColumnSpec("Status", "status"),
    ]
    if long:
        spec = [
            ColumnSpec("ID", "id", justify="right"),
            ColumnSpec("UUID", "uuid"),
            ColumnSpec("Name", "name"),
            ColumnSpec("Node", "node"),
            ColumnSpec("Type", "type"),
            ColumnSpec("Usage Type", "uType"),
            ColumnSpec("Pool", "storagePool"),
            ColumnSpec("Size", "size", formatter=format_bytes, justify="right"),
            ColumnSpec("Progress", "progress", formatter=format_percent, justify="right"),
            ColumnSpec("Status", "status"),
        ]
    print_list(
        rows,
        spec,
        fmt=fmt,
        selected_columns=columns,
        sort_column=sort_column,
        title="Downloads",
    )


@download_app.command("show")
def download_show(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="Download ID, UUID, or filename.")],
    node: NodeOption = None,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
) -> None:
    """Display full metadata for a download."""
    state: CLIState = ctx.obj
    ident = identifier.strip().lower()
    with state.get_client(node_override=node) as client:
        results = client.fan_out_get("/utilities/downloads", node=node)

    for host, data in results:
        if isinstance(data, list):
            for dl in data:
                if not isinstance(dl, dict):
                    continue
                if (
                    str(dl.get("id") or "").lower() == ident
                    or str(dl.get("uuid") or "").lower() == ident
                    or str(dl.get("name") or "").lower() == ident
                ):
                    out = dict(dl)
                    out["node"] = host
                    print_dict(
                        out,
                        fmt=fmt,
                        selected_columns=columns,
                        title=f"Download {dl.get('name')} ({host})",
                    )
                    return

    raise ResourceNotFoundError(f"Download '{identifier}' not found.")


@download_app.command("create", hidden=True)
@download_app.command("start")
def download_create(
    ctx: typer.Context,
    url: Annotated[
        str, typer.Argument(help="HTTP(S) URL, magnet URI, or server local path to download.")
    ],
    filename: Annotated[
        str | None,
        typer.Option("--filename", "-O", help="Override target filename."),
    ] = None,
    download_type: Annotated[
        str,
        typer.Option(
            "--type",
            "-t",
            help="Download usage type: 'uncategorized', 'cloud-init', 'base-rootfs'.",
        ),
    ] = "uncategorized",
    storage_pool: Annotated[
        str | None,
        typer.Option(
            "--pool", "-p", help="ZFS storage pool name (uses the server default if omitted)."
        ),
    ] = None,
    auto_extract: Annotated[
        bool,
        typer.Option("--extract/--no-extract", help="Automatically extract compressed archives."),
    ] = True,
    auto_raw: Annotated[
        bool,
        typer.Option(
            "--raw-convert/--no-raw-convert", help="Automatically convert disk images to RAW."
        ),
    ] = False,
    ignore_tls: Annotated[
        bool,
        typer.Option("--ignore-tls", help="Ignore TLS verification on the remote download URL."),
    ] = False,
    node: NodeOption = None,
) -> None:
    """Start a new download on the target node."""
    state: CLIState = ctx.obj
    payload: dict[str, Any] = {
        "url": url,
        "downloadType": download_type,
        "automaticExtraction": auto_extract,
        "automaticRawConversion": auto_raw,
        "ignoreTLS": ignore_tls,
    }
    if filename:
        payload["filename"] = filename
    if storage_pool:
        payload["storagePool"] = storage_pool

    with state.get_client(node_override=node) as client:
        data = client.post("/utilities/downloads", json_body=payload, node=node)
    if isinstance(data, dict) and data.get("uuid"):
        console.print(
            f"[green]Queued download[/green] [bold]{data.get('name') or url}[/bold] (UUID: {data.get('uuid')})."
        )
    else:
        console.print(f"[green]Queued download from '{url}'.[/green]")


@download_app.command("upload")
def download_upload(
    ctx: typer.Context,
    file_path: Annotated[
        Path, typer.Argument(exists=True, readable=True, help="Local file to upload.")
    ],
    download_type: Annotated[
        str,
        typer.Option(
            "--type",
            "-t",
            help="Download usage type: 'uncategorized', 'cloud-init', 'base-rootfs'.",
        ),
    ] = "uncategorized",
    storage_pool: Annotated[
        str | None,
        typer.Option("--pool", "-p", help="Target ZFS storage pool."),
    ] = None,
    auto_extract: Annotated[
        bool,
        typer.Option("--extract/--no-extract", help="Automatically extract compressed archives."),
    ] = True,
    auto_raw: Annotated[
        bool,
        typer.Option(
            "--raw-convert/--no-raw-convert", help="Automatically convert disk images to RAW."
        ),
    ] = False,
    node: NodeOption = None,
) -> None:
    """Upload a local ISO or image file to a node's downloader storage."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        params = {"storagePool": storage_pool} if storage_pool else None
        with file_path.open("rb") as fh:
            receipt = client.post(
                "/utilities/downloader-uploads",
                params=params,
                files={"filepond": (file_path.name, fh, "application/octet-stream")},
                node=node,
            )
        upload_id = receipt.get("uploadId") if isinstance(receipt, dict) else str(receipt or "")
        if not upload_id:
            raise RuntimeError("Server did not return an uploadId during staging.")
        result = client.post(
            f"/utilities/downloader-uploads/{upload_id}/complete",
            json_body={
                "downloadType": download_type,
                "automaticExtraction": auto_extract,
                "automaticRawConversion": auto_raw,
            },
            node=node,
        )
    dl_uuid = result.get("uuid") if isinstance(result, dict) else ""
    console.print(
        f"[green]Uploaded '{file_path.name}' successfully[/green]"
        + (f" (UUID: {dl_uuid})." if dl_uuid else ".")
    )


@download_app.command("delete")
def download_delete(
    ctx: typer.Context,
    ids: Annotated[list[int], typer.Argument(help="One or more download IDs to delete.")],
    node: NodeOption = None,
) -> None:
    """Delete one or more downloads by ID."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        if len(ids) == 1:
            client.delete(f"/utilities/downloads/{ids[0]}", node=node)
            console.print(f"[green]Deleted download #{ids[0]}.[/green]")
        else:
            client.post("/utilities/downloads/bulk-delete", json_body={"ids": ids}, node=node)
            console.print(f"[green]Deleted {len(ids)} downloads.[/green]")


@download_app.command("signed-url")
def download_signed_url(
    ctx: typer.Context,
    parent_uuid: Annotated[str, typer.Option("--uuid", "-u", help="Download UUID.")],
    name: Annotated[str, typer.Option("--name", "-f", help="Filename within the download.")],
    node: NodeOption = None,
    fmt: FormatOption = OutputFormat.table,
) -> None:
    """Create a 2-hour signed capability URL for a completed download file."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        data = client.post(
            "/utilities/downloads/signed-url",
            json_body={"parentUUID": parent_uuid, "name": name},
            node=node,
        )
    if isinstance(data, dict):
        print_dict(data, fmt=fmt, title="Signed Download URL")
    else:
        console.print(str(data))


@download_app.command("storage")
def download_storage(
    ctx: typer.Context,
    node: NodeOption = None,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
) -> None:
    """List available download storage pools and default paths."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        storage = client.get("/utilities/downloads/storage", node=node) or []
        paths = client.get("/utilities/downloads/paths", node=node) or {}

    if isinstance(paths, dict) and fmt == OutputFormat.table:
        print_dict(paths, fmt=fmt, title="Default Download Paths")

    if isinstance(storage, list):
        spec = [
            ColumnSpec("Name", "name"),
            ColumnSpec("Pool", "pool"),
            ColumnSpec("Path", "path"),
            ColumnSpec("Free", "free", formatter=format_bytes, justify="right"),
        ]
        print_list(
            storage, spec, fmt=fmt, selected_columns=columns, title="Download Storage Targets"
        )
