"""Unit tests for formatters, filtering, sorting, and output modes."""

from __future__ import annotations

import csv
import io
import json

import pytest
import yaml
from rich.text import Text

from sylve_cli.formatter import (
    ColumnSpec,
    FormatterError,
    OutputFormat,
    apply_row_filters,
    configure_table,
    filter_columns,
    format_bytes,
    format_percent,
    format_vm_state,
    print_dict,
    print_list,
    state_text,
)


@pytest.fixture(autouse=True)
def reset_table_options() -> None:
    configure_table()
    yield
    configure_table()


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, "NOSTATE"),
        (1, "RUNNING"),
        (5, "SHUTOFF"),
        (99, "UNKNOWN(99)"),
        ("5", "SHUTOFF"),
        ("running", "RUNNING"),
        ("", "UNKNOWN"),
        (None, "UNKNOWN"),
    ],
)
def test_format_vm_state(value: object, expected: str) -> None:
    assert format_vm_state(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "-"),
        ("", "-"),
        (0, "0 B"),
        (512, "512 B"),
        (1024, "1.0 KiB"),
        (1536, "1.5 KiB"),
        (1024**3, "1.0 GiB"),
        (-1, "-1"),
        ("invalid", "invalid"),
    ],
)
def test_format_bytes(value: object, expected: str) -> None:
    assert format_bytes(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, "-"), ("", "-"), (42.567, "42.6%"), ("bad", "bad")],
)
def test_format_percent(value: object, expected: str) -> None:
    assert format_percent(value) == expected


def test_state_text_styles_known_and_unknown() -> None:
    assert isinstance(state_text("RUNNING"), Text)
    assert state_text("RUNNING").style == "green"
    assert state_text("UNKNOWN(9)").style == "red"


@pytest.mark.parametrize(
    ("selected", "expected"),
    [
        (["RID"], ["RID"]),
        (["rid"], ["RID"]),
        (["name,State"], ["Name", "State"]),
        (["state", "rid"], ["State", "RID"]),
    ],
)
def test_filter_columns(selected: list[str], expected: list[str]) -> None:
    columns = [
        ColumnSpec("RID", "rid"),
        ColumnSpec("Name", "name"),
        ColumnSpec("State", "state"),
    ]
    assert [column.header for column in filter_columns(columns, selected)] == expected


def test_filter_columns_unknown_raises() -> None:
    columns = [ColumnSpec("RID", "rid")]
    with pytest.raises(FormatterError, match="Unknown column"):
        filter_columns(columns, ["nope"])


def test_print_list_json_projects_and_sorts(capsys: pytest.CaptureFixture[str]) -> None:
    rows = [
        {"rid": 2, "name": "beta", "state": 5},
        {"rid": 1, "name": "alpha", "state": 1},
    ]
    columns = [
        ColumnSpec("RID", "rid"),
        ColumnSpec("Name", "name"),
        ColumnSpec("State", "state", formatter=format_vm_state),
    ]
    print_list(
        rows,
        columns,
        fmt=OutputFormat.json,
        selected_columns=["rid", "name"],
        sort_column="RID",
    )
    output = json.loads(capsys.readouterr().out)
    assert output == [
        {"rid": 1, "name": "alpha"},
        {"rid": 2, "name": "beta"},
    ]


def test_print_list_yaml_csv_value(capsys: pytest.CaptureFixture[str]) -> None:
    rows = [{"rid": 2, "name": "beta"}, {"rid": 10, "name": "alpha"}]
    columns = [ColumnSpec("RID", "rid"), ColumnSpec("Name", "name")]

    print_list(rows, columns, fmt=OutputFormat.yaml, sort_column="rid")
    assert yaml.safe_load(capsys.readouterr().out) == [
        {"rid": 2, "name": "beta"},
        {"rid": 10, "name": "alpha"},
    ]

    print_list(rows, columns, fmt=OutputFormat.csv, sort_column="rid")
    parsed = list(csv.reader(io.StringIO(capsys.readouterr().out)))
    assert parsed == [["RID", "Name"], ["2", "beta"], ["10", "alpha"]]

    print_list(rows, columns, fmt=OutputFormat.value, sort_column="rid")
    assert capsys.readouterr().out.splitlines() == ["2 beta", "10 alpha"]


def test_print_list_table_is_aligned_and_bounded(capsys: pytest.CaptureFixture[str]) -> None:
    rows = [{"rid": 1, "name": "alpha"}, {"rid": 200, "name": "beta"}]
    columns = [ColumnSpec("RID", "rid", justify="right"), ColumnSpec("Name", "name")]
    configure_table(max_width=60)
    print_list(rows, columns, fmt=OutputFormat.table, title="Items")
    lines = capsys.readouterr().out.splitlines()
    content = [line for line in lines if line.strip() and line.strip() != "Items"]
    assert content
    assert not any("|" in line or line.lstrip().startswith("+") for line in lines)
    assert max(len(line) for line in content) <= 60
    assert all(line == line.rstrip() for line in lines)

    # No borders: alignment is vertical, so the Name column starts at the same
    # index on the header and every row.
    def name_column(line: str) -> int:
        for needle in ("Name", "alpha", "beta"):
            if needle in line:
                return line.index(needle)
        return -1

    assert len({name_column(line) for line in content}) == 1


def test_print_list_empty_and_no_columns(capsys: pytest.CaptureFixture[str]) -> None:
    print_list([], [ColumnSpec("RID", "rid")], title="Virtual Machines")
    assert "No virtual machines found." in capsys.readouterr().out

    configure_table()
    print_list([{"x": 1}], [], fmt=OutputFormat.table)
    assert "No columns selected." in capsys.readouterr().out


def test_print_list_unknown_sort_column(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(FormatterError, match="Unknown sort column"):
        print_list(
            [{"name": "alpha"}],
            [ColumnSpec("Name", "name")],
            sort_column="missing",
        )
    assert capsys.readouterr().out == ""


def test_none_and_nested_values(capsys: pytest.CaptureFixture[str]) -> None:
    rows = [{"name": None, "meta": {"b": 2, "a": 1}, "tags": ["x", "y"]}]
    columns = [
        ColumnSpec("Name", "name"),
        ColumnSpec("Meta", "meta"),
        ColumnSpec("Tags", "tags"),
    ]
    print_list(rows, columns, fmt=OutputFormat.json)
    parsed = json.loads(capsys.readouterr().out)
    assert parsed[0]["name"] is None
    assert parsed[0]["meta"] == {"b": 2, "a": 1}
    assert parsed[0]["tags"] == ["x", "y"]


def test_csv_formula_injection(capsys: pytest.CaptureFixture[str]) -> None:
    rows = [{"name": "=cmd", "note": "+note", "size": "-1"}]
    columns = [
        ColumnSpec("Name", "name"),
        ColumnSpec("Note", "note"),
        ColumnSpec("Size", "size"),
    ]
    print_list(rows, columns, fmt=OutputFormat.csv)
    parsed = list(csv.reader(io.StringIO(capsys.readouterr().out)))
    assert parsed[1] == ["'=cmd", "'+note", "-1"]


def test_print_dict_formats_and_selection(capsys: pytest.CaptureFixture[str]) -> None:
    data = {"name": "node1", "status": "online", "cores": 16}

    print_dict(data, fmt=OutputFormat.json, selected_columns=["status", "name"])
    assert list(json.loads(capsys.readouterr().out)) == ["status", "name"]

    print_dict(data, fmt=OutputFormat.yaml)
    assert yaml.safe_load(capsys.readouterr().out) == data

    print_dict(data, fmt=OutputFormat.value, selected_columns=["name", "cores"])
    assert capsys.readouterr().out.splitlines() == ["node1", "16"]

    print_dict(data, fmt=OutputFormat.csv, selected_columns=["name", "status"])
    assert list(csv.reader(io.StringIO(capsys.readouterr().out))) == [
        ["Field", "Value"],
        ["name", "node1"],
        ["status", "online"],
    ]


def test_print_dict_unknown_field(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(FormatterError, match="Unknown field"):
        print_dict({"name": "node1"}, selected_columns=["missing"])
    assert capsys.readouterr().out == ""


def test_table_truncation_and_no_truncate(capsys: pytest.CaptureFixture[str]) -> None:
    name = "web-vm-with-a-very-long-name-that-does-not-fit"
    rows = [{"name": name}]
    columns = [ColumnSpec("Name", "name")]

    configure_table(max_width=30)
    print_list(rows, columns)
    truncated = capsys.readouterr().out
    assert "…" in truncated

    configure_table(max_width=70, no_truncate=True)
    print_list(rows, columns)
    wrapped = capsys.readouterr().out
    assert name in wrapped
    assert "…" not in wrapped


def test_apply_row_filters_by_column_text_and_limit() -> None:
    rows = [
        {"name": "web-01", "state": "RUNNING"},
        {"name": "web-02", "state": "SHUTOFF"},
        {"name": "db-01", "state": "RUNNING"},
    ]
    # COLUMN=VALUE is a case-insensitive substring match on that column only.
    assert [r["name"] for r in apply_row_filters(rows, ["state=running"])] == [
        "web-01",
        "db-01",
    ]
    # A bare term matches any field.
    assert [r["name"] for r in apply_row_filters(rows, ["db"])] == ["db-01"]
    # Multiple filters combine with AND; limit caps the result.
    assert apply_row_filters(rows, ["state=RUNNING", "web"], limit=1) == [rows[0]]
    # An unknown column filters everything out rather than silently passing.
    assert apply_row_filters(rows, ["nope=x"]) == []
