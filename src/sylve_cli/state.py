"""Shared CLI state and common Typer option annotations."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer

from sylve_cli.client import SylveClient, SylveError
from sylve_cli.config import load_config
from sylve_cli.formatter import OutputFormat


def confirm_destructive(prompt: str, *, yes: bool) -> None:
    """Ask before a destructive action, unless *yes* or stdin cannot answer.

    A non-interactive stdin (pipe, CI) must not be treated as consent: it
    aborts with a hint to pass ``--yes`` instead of silently proceeding.
    """
    if yes:
        return
    if not sys.stdin.isatty():
        raise SylveError(f"{prompt} Aborted: stdin is not a terminal; pass --yes to skip.")
    typer.confirm(prompt, abort=True)


@dataclass
class CLIState:
    """Global options populated by the root Typer callback."""

    config_path: Path | None = None
    context_name: str | None = None
    node: str | None = None
    insecure: bool = False
    timeout: float = 30.0

    def get_client(self, node_override: str | None = None) -> SylveClient:
        """Create an authenticated client for the active context.

        Args:
            node_override: Optional node hostname or UUID for this client.

        Returns:
            SylveClient: Configured API client. Use it as a context manager.

        Raises:
            RuntimeError: If no usable context or environment credentials exist.

        Example:
            >>> with state.get_client() as client:
            ...     client.get("/cluster")
        """
        cfg = load_config(self.config_path)
        _, ctx = cfg.get_active_context(self.context_name)
        if self.insecure:
            ctx.verify_ssl = False
        effective_node = node_override or self.node
        return SylveClient(ctx, node_override=effective_node, timeout=self.timeout)


# Reusable Typer option annotations
FormatOption = Annotated[
    OutputFormat,
    typer.Option(
        "-f",
        "--format",
        help="Output format (table, json, yaml, value, csv).",
        case_sensitive=False,
    ),
]

ColumnsOption = Annotated[
    list[str] | None,
    typer.Option(
        "-c",
        "--column",
        help="Specify the column(s) to include in output (repeatable).",
    ),
]

SortColumnOption = Annotated[
    str | None,
    typer.Option(
        "--sort-column",
        help="Sort output by the specified column name.",
    ),
]

LongOption = Annotated[
    bool,
    typer.Option(
        "--long",
        help="Show the full set of columns, including lower-priority details.",
    ),
]

NodeOption = Annotated[
    str | None,
    typer.Option(
        "-n",
        "--node",
        help="Target cluster node hostname or UUID. List commands query all nodes unless given; other commands use the connected node.",
    ),
]

WaitOption = Annotated[
    bool,
    typer.Option(
        "-w",
        "--wait/--no-wait",
        help="Wait for asynchronous task completion.",
    ),
]

YesOption = Annotated[
    bool,
    typer.Option("-y", "--yes", help="Skip confirmation prompt."),
]

FilterOption = Annotated[
    list[str] | None,
    typer.Option(
        "--filter",
        help="Filter rows by COLUMN=VALUE (substring, repeatable) or by bare text.",
    ),
]

LimitOption = Annotated[
    int | None,
    typer.Option("--limit", "-l", min=1, help="Show at most this many rows after filtering."),
]
