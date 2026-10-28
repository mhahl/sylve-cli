"""Tests for output formatting (table, json, yaml, value, csv)."""

from __future__ import annotations

import csv
import io
import json

import pytest
import yaml

from sylve_cli.formatter import (
    ColumnSpec,
    OutputFormat,
    configure_table,
    format_bytes,
    format_percent,
    format_vm_state,
    print_dict,
    print_list,
)


@pytest.fixture(autouse=True)
def _reset_table_options() -> None:
    configure_table()
    yield
    configure_table()


def test_format_helpers() -> None:
    assert format_vm_state(1) == "RUNNING"
    assert format_vm_state(5) == "SHUTOFF"
    assert format_vm_state("running") == "RUNNING"
    assert format_bytes(1024 * 1024 * 1024) == "1.0 GiB"
    assert format_bytes(512) == "512 B"
    assert format_percent(42.56) == "42.6%"


def test_print_list_formats(capsys: pytest.CaptureFixture[str]) -> None:
    rows = [
        {"rid": 102, "name": "db-vm", "state": 1, "node": "node2"},
        {"rid": 101, "name": "web-vm", "state": 5, "node": "node1"},
    ]
    cols = [
        ColumnSpec("RID", "rid"),
        ColumnSpec("Name", "name"),
        ColumnSpec("State", "state", formatter=format_vm_state),
        ColumnSpec("Node", "node"),
    ]

    # JSON with column selection & sorting
    print_list(
        rows,
        cols,
        fmt=OutputFormat.json,
        selected_columns=["RID", "Name"],
        sort_column="RID",
    )
    out_json = json.loads(capsys.readouterr().out)
    assert out_json == [
        {"rid": 101, "name": "web-vm"},
        {"rid": 102, "name": "db-vm"},
    ]

    # Value format
    print_list(
        rows,
        cols,
        fmt=OutputFormat.value,
        selected_columns=["RID", "State"],
        sort_column="RID",
    )
    out_val = capsys.readouterr().out.strip().splitlines()
    assert out_val == ["101 SHUTOFF", "102 RUNNING"]

    # CSV format
    print_list(rows, cols, fmt=OutputFormat.csv, sort_column="RID")
    out_csv = capsys.readouterr().out.strip().splitlines()
    assert out_csv[0] == "RID,Name,State,Node"
    assert out_csv[1] == "101,web-vm,SHUTOFF,node1"

    # Default ASCII table format (+---+---+ and |   |)
    print_list(rows, cols, fmt=OutputFormat.table, sort_column="RID")
    out_tbl = capsys.readouterr().out
    assert "+-----+--------+---------+-------+" in out_tbl
    assert "| 101 | web-vm |" in out_tbl


def test_print_dict_yaml(capsys: pytest.CaptureFixture[str]) -> None:
    data = {"hostname": "node1.lan", "status": "online", "cores": 16}
    print_dict(data, fmt=OutputFormat.yaml, selected_columns=["hostname", "status"])
    parsed = yaml.safe_load(capsys.readouterr().out)
    assert parsed == {"hostname": "node1.lan", "status": "online"}


def test_rich_markup_is_treated_as_literal_data(capsys: pytest.CaptureFixture[str]) -> None:
    rows = [{"rid": 1, "name": "[red]prod[/red]"}]
    cols = [ColumnSpec("RID", "rid"), ColumnSpec("Name", "name")]

    print_list(rows, cols, title="[bold]VMs[/bold]")
    out = capsys.readouterr().out
    assert "[red]prod[/red]" in out
    assert "[bold]VMs[/bold]" in out

    print_dict({"name": "[red]prod[/red]"}, title="[bold]VM[/bold]")
    out = capsys.readouterr().out
    assert "[red]prod[/red]" in out
    assert "[bold]VM[/bold]" in out


def test_numeric_sort(capsys: pytest.CaptureFixture[str]) -> None:
    rows = [{"rid": 2}, {"rid": 10}, {"rid": 1}]
    cols = [ColumnSpec("RID", "rid")]
    print_list(rows, cols, fmt=OutputFormat.value, sort_column="RID")
    assert capsys.readouterr().out.splitlines() == ["1", "2", "10"]


def test_unknown_column_is_rejected(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(ValueError, match="Unknown column"):
        print_list(
            [{"rid": 1, "name": "web"}],
            [ColumnSpec("RID", "rid"), ColumnSpec("Name", "name")],
            selected_columns=["nmae"],
        )
    assert capsys.readouterr().out == ""


def test_comma_separated_columns(capsys: pytest.CaptureFixture[str]) -> None:
    rows = [{"rid": 1, "name": "web", "state": "RUNNING"}]
    cols = [
        ColumnSpec("RID", "rid"),
        ColumnSpec("Name", "name"),
        ColumnSpec("State", "state"),
    ]
    print_list(rows, cols, fmt=OutputFormat.value, selected_columns=["rid,name"])
    assert capsys.readouterr().out.strip() == "1 web"


def test_empty_table_message(capsys: pytest.CaptureFixture[str]) -> None:
    print_list([], [ColumnSpec("RID", "rid")], title="Virtual Machines")
    assert "No virtual machines found." in capsys.readouterr().out


def test_none_values_render_as_dash_in_tables(capsys: pytest.CaptureFixture[str]) -> None:
    print_list([{"name": None}], [ColumnSpec("Name", "name")])
    assert "| - " in capsys.readouterr().out


def test_csv_formula_injection_is_neutralized(capsys: pytest.CaptureFixture[str]) -> None:
    rows = [{"name": "=cmd", "note": "+note", "size": "-1"}]
    cols = [
        ColumnSpec("Name", "name"),
        ColumnSpec("Note", "note"),
        ColumnSpec("Size", "size"),
    ]
    print_list(rows, cols, fmt=OutputFormat.csv)
    parsed = list(csv.reader(io.StringIO(capsys.readouterr().out)))
    assert parsed[1] == ["'=cmd", "'+note", "-1"]


def test_print_dict_preserves_selected_order(capsys: pytest.CaptureFixture[str]) -> None:
    print_dict(
        {"hostname": "node1.lan", "status": "online"},
        fmt=OutputFormat.json,
        selected_columns=["status", "hostname"],
    )
    assert list(json.loads(capsys.readouterr().out)) == ["status", "hostname"]


def test_print_dict_compacts_nested_values(capsys: pytest.CaptureFixture[str]) -> None:
    print_dict({"network": {"bridge": "vm0", "vlan": 10}})
    out = capsys.readouterr().out
    assert '{"bridge":"vm0","vlan":10}' in out
    assert out.count('"bridge"') == 1


def test_table_truncation_and_no_truncate(capsys: pytest.CaptureFixture[str]) -> None:
    name = "web-vm-with-a-very-long-name-that-does-not-fit"
    rows = [{"name": name}]
    cols = [ColumnSpec("Name", "name")]

    configure_table(max_width=30)
    print_list(rows, cols)
    truncated = capsys.readouterr().out
    assert "…" in truncated
    assert name not in truncated

    configure_table(max_width=70, no_truncate=True)
    print_list(rows, cols)
    wrapped = capsys.readouterr().out
    assert name in wrapped
    assert "…" not in wrapped
