"""Output formatting for tables, JSON, YAML, values, and CSV using Rich."""

from __future__ import annotations

import csv
import io
import json
import re
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Literal

import yaml
from rich import box
from rich.cells import cell_len
from rich.console import Console
from rich.table import Table
from rich.text import Text

console = Console()
err_console = Console(stderr=True)

TABLE_BOX = box.Box(
    "+-++\n| ||\n+-++\n| ||\n+-++\n+-++\n| ||\n+-++\n",
    ascii=True,
)


class FormatterError(ValueError):
    """Raised when a requested output column or field is invalid."""


class OutputFormat(str, Enum):
    """Supported output formats."""

    table = "table"
    json = "json"
    yaml = "yaml"
    value = "value"
    csv = "csv"


@dataclass(frozen=True)
class ColumnSpec:
    """Defines a table/output column mapping from a dict/object.

    ``no_wrap`` and ``overflow`` control how a cell that is wider than the
    available table width is displayed.  Tables default to a single line per
    row with an ellipsis; ``--no-truncate`` switches every column to wrapping.
    """

    header: str
    key: str
    formatter: Callable[[Any], str] | None = None
    justify: Literal["default", "left", "center", "right", "full"] = "left"
    state: bool = False
    min_width: int | None = None
    max_width: int | None = None
    no_wrap: bool = True
    overflow: Literal["fold", "crop", "ellipsis", "ignore"] = "ellipsis"


@dataclass
class TableOptions:
    """Process-wide table display settings for the current invocation."""

    max_width: int | None = None
    no_truncate: bool = False


_table_options = TableOptions()


def configure_table(*, max_width: int | None = None, no_truncate: bool = False) -> None:
    """Configure table formatting for the current invocation.

    Args:
        max_width: Maximum table width in terminal columns.
        no_truncate: Wrap cells instead of truncating them.

    Returns:
        None.

    Example:
        >>> configure_table(max_width=80)
    """
    _table_options.max_width = max_width
    _table_options.no_truncate = no_truncate


# Libvirt DomainState integer mapping (from swagger spec libvirt.DomainState)
LIBVIRT_DOMAIN_STATES: dict[int, str] = {
    0: "NOSTATE",
    1: "RUNNING",
    2: "BLOCKED",
    3: "PAUSED",
    4: "SHUTDOWN",
    5: "SHUTOFF",
    6: "CRASHED",
    7: "PMSUSPENDED",
}

STATE_HEADERS: frozenset[str] = frozenset(
    {"state", "status", "health", "ready", "enabled", "leader"}
)

STATE_STYLES: dict[str, str] = {
    "RUNNING": "green",
    "ONLINE": "green",
    "ACTIVE": "green",
    "SUCCESS": "green",
    "COMPLETED": "green",
    "READY": "green",
    "HEALTHY": "green",
    "TRUE": "green",
    "ENABLED": "green",
    "UP": "green",
    "PASS": "green",
    "LEADER": "green",
    "PRESENT": "green",
    "SHUTOFF": "dim",
    "STOPPED": "dim",
    "INACTIVE": "dim",
    "FALSE": "dim",
    "DISABLED": "dim",
    "OFFLINE": "red",
    "FAILED": "red",
    "ERROR": "red",
    "FAULTED": "red",
    "CRASHED": "red",
    "DEGRADED": "red",
    "QUEUED": "yellow",
    "PENDING": "yellow",
    "PAUSED": "yellow",
    "SHUTDOWN": "yellow",
    "MIGRATING": "yellow",
    "DRAINING": "yellow",
    "REBOOTING": "yellow",
    "STAGING": "yellow",
}

_NUMERIC_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")
_CSV_FORMULA_PREFIXES = frozenset("=+-@\t\r")
_TRAILING_WHITESPACE_RE = re.compile(r"[ \t]+(?P<ansi>(?:\x1b\[[0-9;]*m)*)$")


def format_vm_state(value: Any) -> str:
    """Convert a libvirt domain state into a display string.

    Args:
        value: Integer, numeric string, or textual state.

    Returns:
        str: Uppercase state name, or ``UNKNOWN(...)``.

    Example:
        >>> format_vm_state(1)
        'RUNNING'
    """
    if isinstance(value, int):
        return LIBVIRT_DOMAIN_STATES.get(value, f"UNKNOWN({value})")
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            return LIBVIRT_DOMAIN_STATES.get(int(stripped), stripped.upper())
        return stripped.upper() if stripped else "UNKNOWN"
    return "UNKNOWN"


def format_timestamp(value: Any) -> str:
    """Render an RFC 3339 timestamp at a fixed width.

    Args:
        value: Timestamp string, number, or empty value.

    Returns:
        str: ``2026-10-28 14:13:24 +1100``, the raw value if it is not RFC 3339,
        or ``-`` for empty.

    Example:
        >>> format_timestamp("2026-10-28T14:13:24.369790382+11:00")
        '2026-10-28 14:13:24 +1100'
    """
    if value is None or value == "":
        return "-"
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return text
    return parsed.strftime("%Y-%m-%d %H:%M:%S %z").rstrip()


def format_bytes(num_bytes: Any) -> str:
    """Format a byte count into IEC units.

    Args:
        num_bytes: Byte count as a number or numeric string.

    Returns:
        str: Human-readable value such as ``1.5 GiB``, or ``-`` for empty.

    Example:
        >>> format_bytes(1024 ** 3)
        '1.0 GiB'
    """
    if num_bytes is None or num_bytes == "":
        return "-"
    try:
        val = float(num_bytes)
    except (ValueError, TypeError):
        return str(num_bytes)
    if val < 0:
        return str(num_bytes)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB", "PiB"):
        if abs(val) < 1024.0 or unit == "PiB":
            if unit == "B":
                return f"{int(val)} {unit}"
            return f"{val:.1f} {unit}"
        val /= 1024.0
    return f"{val:.1f} PiB"


def format_percent(val: Any) -> str:
    """Format a percentage value.

    Args:
        val: Number or numeric string.

    Returns:
        str: Value with one decimal and ``%``, or ``-`` for empty.

    Example:
        >>> format_percent(42.56)
        '42.6%'
    """
    if val is None or val == "":
        return "-"
    try:
        fval = float(val)
    except (ValueError, TypeError):
        return str(val)
    return f"{fval:.1f}%"


def state_text(value: str) -> Text:
    """Return styled text for a state value.

    Args:
        value: State label such as ``RUNNING``.

    Returns:
        Text: Rich text with a color style; markup is not interpreted.

    Example:
        >>> state_text("RUNNING").style
        'green'
    """
    upper = value.strip().upper()
    if upper.startswith("UNKNOWN"):
        style = "red"
    else:
        style = STATE_STYLES.get(upper, "")
    return Text(value, style=style)


def _extract_value(row: dict[str, Any], key: str) -> Any:
    """Extract a possibly dotted key from a dictionary."""
    if key in row:
        return row[key]
    cur: Any = row
    for part in key.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _stringify_cell(val: Any) -> str:
    """Convert a cell value to a clean string."""
    if val is None:
        return ""
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, dict):
        return json.dumps(val, separators=(",", ":"), default=str)
    if isinstance(val, (list, tuple)):
        if all(not isinstance(item, (dict, list, tuple)) for item in val):
            return ", ".join(str(item) for item in val)
        return json.dumps(val, separators=(",", ":"), default=str)
    return str(val)


def _normalize_cell(value: str) -> str:
    """Keep table rows on one line and avoid tab-induced width errors."""
    return value.replace("\r\n", " ").replace("\r", " ").replace("\n", " ").replace("\t", "    ")


def _display_cell(col: ColumnSpec, raw_value: Any) -> str:
    if col.formatter is not None:
        value = col.formatter(raw_value)
    else:
        value = _stringify_cell(raw_value)
    if raw_value is None and value == "":
        return "-"
    return _normalize_cell(str(value))


def _render_rows(
    items: Sequence[dict[str, Any]],
    columns: Sequence[ColumnSpec],
) -> list[list[str]]:
    rows: list[list[str]] = []
    for item in items:
        row: list[str] = []
        for col in columns:
            raw_value = _extract_value(item, col.key)
            if col.formatter is not None:
                value = col.formatter(raw_value)
            else:
                value = _stringify_cell(raw_value)
            row.append(_normalize_cell(str(value)) if value is not None else "")
        rows.append(row)
    return rows


def _csv_safe(value: str) -> str:
    """Prevent spreadsheet formula execution without altering numeric cells."""
    if value and value[0] in _CSV_FORMULA_PREFIXES and not _NUMERIC_RE.match(value):
        return "'" + value
    return value


def _split_columns(selected: Sequence[str] | None) -> list[str]:
    if not selected:
        return []
    result: list[str] = []
    for item in selected:
        for part in item.split(","):
            part = part.strip()
            if part:
                result.append(part)
    return result


def _valid_column_names(columns: Sequence[ColumnSpec]) -> str:
    return ", ".join(col.header for col in columns)


def filter_columns(
    columns: Sequence[ColumnSpec],
    selected: Sequence[str] | None,
) -> list[ColumnSpec]:
    """Filter and order columns from ``--column`` values.

    Args:
        columns: Available column definitions.
        selected: Header/key names, or comma-separated names.

    Returns:
        list[ColumnSpec]: Columns in the requested order.

    Raises:
        FormatterError: If a requested column is unknown.

    Example:
        >>> [c.header for c in filter_columns([ColumnSpec("RID", "rid")], ["rid"])]
        ['RID']
    """
    requested = _split_columns(selected)
    if not requested:
        return list(columns)

    by_lookup: dict[str, ColumnSpec] = {}
    for col in columns:
        by_lookup[col.header.casefold()] = col
        by_lookup[col.key.casefold()] = col

    resolved: list[ColumnSpec] = []
    unknown: list[str] = []
    for request in requested:
        match = by_lookup.get(request.casefold())
        if match is None:
            unknown.append(request)
        else:
            resolved.append(match)

    if unknown:
        raise FormatterError(
            f"Unknown column(s): {', '.join(unknown)}. "
            f"Valid columns: {_valid_column_names(columns)}."
        )
    return resolved


def _sort_key(value: Any) -> tuple[int, Any]:
    """Sort numbers numerically, text case-insensitively, and None values last."""
    if value is None:
        return (2, 0.0)
    if isinstance(value, bool):
        return (0, float(value))
    if isinstance(value, (int, float)):
        return (0, float(value))
    text = str(value).strip()
    if _NUMERIC_RE.match(text):
        return (0, float(text))
    return (1, text.casefold())


def _resolve_sort_key(columns: Sequence[ColumnSpec], sort_column: str) -> str | None:
    requested = sort_column.strip().casefold()
    for col in columns:
        if col.header.casefold() == requested or col.key.casefold() == requested:
            return col.key
    return None


def _cell_width(value: str) -> int:
    return max((cell_len(line) for line in value.splitlines()), default=0)


def _available_content_width(column_count: int) -> int:
    max_width = _table_options.max_width
    if max_width is None:
        max_width = console.width
    if max_width <= 0:
        return 0
    # One leading/trailing space per column plus a border per column edge.
    return max(column_count, max_width - (column_count * 3 + 1))


def _fit_widths(
    columns: Sequence[ColumnSpec],
    rendered_rows: Sequence[Sequence[str]],
) -> Sequence[int | None]:
    if _table_options.no_truncate:
        return [None] * len(columns)

    available = _available_content_width(len(columns))
    if available <= 0:
        return [None] * len(columns)

    header_widths = [max(1, _cell_width(col.header)) for col in columns]
    natural_widths: list[int] = []
    for index, col in enumerate(columns):
        content_width = max(
            (_cell_width(row[index]) for row in rendered_rows),
            default=0,
        )
        natural_widths.append(max(header_widths[index], content_width))

    minimums = [
        max(
            1,
            col.min_width
            if col.min_width is not None
            else max(header_widths[index], min(natural_widths[index], 12)),
        )
        for index, col in enumerate(columns)
    ]
    desired: list[int] = []
    for index, col in enumerate(columns):
        value = max(minimums[index], natural_widths[index])
        if col.max_width is not None:
            value = min(value, max(minimums[index], col.max_width))
        desired.append(value)

    if sum(desired) <= available:
        return desired

    if sum(minimums) > available:
        total = sum(minimums)
        widths = [max(1, int(available * width / total)) for width in minimums]
        remaining = available - sum(widths)
        for index in sorted(range(len(widths)), key=lambda i: widths[i], reverse=True):
            if remaining <= 0:
                break
            widths[index] += 1
            remaining -= 1
        return widths

    extra = available - sum(minimums)
    growth = [max(0, desired[index] - minimums[index]) for index in range(len(columns))]
    total_growth = sum(growth)
    if total_growth <= 0:
        return minimums

    widths = [
        minimums[index] + int(extra * growth[index] / total_growth) for index in range(len(columns))
    ]
    remaining = available - sum(widths)
    for index in sorted(
        range(len(widths)),
        key=lambda i: desired[i] - widths[i],
        reverse=True,
    ):
        if remaining <= 0:
            break
        widths[index] += 1
        remaining -= 1
    return widths


def _rstrip_line(line: str) -> str:
    """Strip trailing spaces while preserving any ANSI reset suffix."""
    while True:
        match = _TRAILING_WHITESPACE_RE.search(line)
        if match is None:
            return line
        line = line[: match.start()] + (match.group("ansi") or "")


def _rstrip_output(text: str) -> str:
    """Remove trailing whitespace from every rendered output line."""
    return "".join(f"{_rstrip_line(line)}\n" for line in text.splitlines())


def _print_table(table: Table) -> None:
    # Rich pads centred titles to the table width with trailing spaces.  Rendering
    # through a buffer lets us drop that padding so every line ends at the same
    # column and the final border cannot wrap on terminals of exactly that width.
    previous_width = console.width
    try:
        if _table_options.max_width is not None:
            console.width = _table_options.max_width
        with console.capture() as capture:
            console.print(table)
    finally:
        console.width = previous_width

    console.file.write(_rstrip_output(capture.get()))
    console.file.flush()


def _add_table_columns(
    table: Table,
    columns: Sequence[ColumnSpec],
    widths: Sequence[int | None],
) -> None:
    no_truncate = _table_options.no_truncate
    for col, width in zip(columns, widths):
        table.add_column(
            Text(col.header),
            justify=col.justify,
            no_wrap=False if no_truncate else col.no_wrap,
            overflow="fold" if no_truncate else col.overflow,
            max_width=None if no_truncate else width,
        )


def print_list(
    rows: Sequence[dict[str, Any]],
    columns: Sequence[ColumnSpec],
    fmt: OutputFormat = OutputFormat.table,
    selected_columns: Sequence[str] | None = None,
    sort_column: str | None = None,
    title: str | None = None,
    empty_message: str | None = None,
) -> None:
    """Render records in the selected output format.

    Args:
        rows: Records to display.
        columns: Column definitions and formatters.
        fmt: Output format.
        selected_columns: Optional subset/order of columns.
        sort_column: Header or key to sort by.
        title: Table title or empty-state label.
        empty_message: Message used when *rows* is empty.

    Raises:
        FormatterError: If a column or sort key is unknown.

    Example:
        >>> print_list([{"rid": 1}], [ColumnSpec("RID", "rid")], fmt=OutputFormat.json)
    """
    items = list(rows)
    selected = _split_columns(selected_columns)
    active_cols = filter_columns(columns, selected)

    if sort_column:
        sort_key = _resolve_sort_key(columns, sort_column)
        if sort_key is None:
            if not items or not any(
                _extract_value(item, sort_column) is not None for item in items
            ):
                raise FormatterError(
                    f"Unknown sort column: {sort_column}. "
                    f"Valid columns: {_valid_column_names(columns)}."
                )
            sort_key = sort_column
        items.sort(key=lambda item: _sort_key(_extract_value(item, sort_key)))

    if fmt == OutputFormat.json:
        if selected:
            projected = [
                {col.key: _extract_value(row, col.key) for col in active_cols} for row in items
            ]
            sys.stdout.write(json.dumps(projected, indent=2, default=str) + "\n")
        else:
            sys.stdout.write(json.dumps(items, indent=2, default=str) + "\n")
        return

    if fmt == OutputFormat.yaml:
        if selected:
            projected = [
                {col.key: _extract_value(row, col.key) for col in active_cols} for row in items
            ]
            sys.stdout.write(yaml.safe_dump(projected, sort_keys=False))
        else:
            sys.stdout.write(yaml.safe_dump(items, sort_keys=False))
        return

    if fmt == OutputFormat.table and not items:
        if empty_message:
            message = empty_message
        elif title:
            message = f"No {title.lower()} found."
        else:
            message = "No records found."
        console.print(Text(message, style="dim"))
        return

    rendered_rows = _render_rows(items, active_cols)

    if fmt == OutputFormat.value:
        for row in rendered_rows:
            sys.stdout.write(" ".join(row) + "\n")
        return

    if fmt == OutputFormat.csv:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([col.header for col in active_cols])
        for row in rendered_rows:
            writer.writerow([_csv_safe(value) for value in row])
        sys.stdout.write(buf.getvalue())
        return

    if not active_cols:
        console.print(Text("No columns selected.", style="dim"))
        return

    table_rows = [
        [_display_cell(col, _extract_value(item, col.key)) for col in active_cols] for item in items
    ]
    widths = _fit_widths(active_cols, table_rows)

    table = Table(
        title=Text(title) if title else None,
        show_header=True,
        header_style="bold",
        box=TABLE_BOX,
    )
    _add_table_columns(table, active_cols, widths)

    for row in table_rows:
        styled_row = [
            state_text(value)
            if active_cols[index].state or active_cols[index].header.casefold() in STATE_HEADERS
            else Text(value)
            for index, value in enumerate(row)
        ]
        table.add_row(*styled_row)

    _print_table(table)


def _lookup_dict_key(data: dict[str, Any], requested: str) -> tuple[str, Any]:
    if requested in data:
        return requested, data[requested]
    folded = requested.casefold()
    for key, value in data.items():
        if key.casefold() == folded:
            return key, value
    if "." not in requested:
        raise KeyError(requested)

    current: Any = data
    for part in requested.split("."):
        if not isinstance(current, dict):
            raise KeyError(requested)
        match = next((key for key in current if key.casefold() == part.casefold()), None)
        if match is None:
            raise KeyError(requested)
        current = current[match]
    return requested, current


def _project_dict(data: dict[str, Any], selected: Sequence[str]) -> dict[str, Any]:
    if not selected:
        return dict(data)
    projected: dict[str, Any] = {}
    for request in selected:
        try:
            key, value = _lookup_dict_key(data, request)
        except KeyError:
            raise FormatterError(
                f"Unknown field: {request}. Valid fields: {', '.join(str(k) for k in data)}."
            ) from None
        projected[key] = value
    return projected


def _format_dict_value(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, (dict, list, tuple)):
        if value and all(not isinstance(item, (dict, list, tuple)) for item in value):
            return _normalize_cell(_stringify_cell(value))
        if value:
            return json.dumps(value, separators=(",", ":"), default=str)
        return _stringify_cell(value)
    return _normalize_cell(_stringify_cell(value))


def print_dict(
    data: dict[str, Any],
    fmt: OutputFormat = OutputFormat.table,
    selected_columns: Sequence[str] | None = None,
    title: str | None = None,
) -> None:
    """Render one resource dictionary.

    Args:
        data: Resource fields.
        fmt: Output format.
        selected_columns: Optional field subset/order.
        title: Table title.

    Raises:
        FormatterError: If a requested field is unknown.

    Example:
        >>> print_dict({"name": "node1"}, fmt=OutputFormat.json)
    """
    filtered = _project_dict(data, _split_columns(selected_columns))

    if fmt == OutputFormat.json:
        sys.stdout.write(json.dumps(filtered, indent=2, default=str) + "\n")
        return

    if fmt == OutputFormat.yaml:
        sys.stdout.write(yaml.safe_dump(filtered, sort_keys=False))
        return

    if fmt == OutputFormat.value:
        for value in filtered.values():
            sys.stdout.write(_stringify_cell(value) + "\n")
        return

    if fmt == OutputFormat.csv:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["Field", "Value"])
        for key, value in filtered.items():
            writer.writerow([_csv_safe(str(key)), _csv_safe(_stringify_cell(value))])
        sys.stdout.write(buf.getvalue())
        return

    table = Table(
        title=Text(title) if title else None,
        show_header=True,
        header_style="bold",
        box=TABLE_BOX,
    )
    table.add_column(Text("Field"), style="bold")
    table.add_column(Text("Value"), overflow="fold")

    for key, value in filtered.items():
        cell = _format_dict_value(value)
        key_name = str(key).casefold()
        value_text = (
            state_text(cell)
            if key_name in STATE_HEADERS or key_name.endswith(("_state", "_status"))
            else Text(cell)
        )
        table.add_row(Text(str(key), style="bold"), value_text)

    _print_table(table)
