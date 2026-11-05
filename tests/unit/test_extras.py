"""Unit tests for the generic extras.py request/format helpers.

These cover the shared logic behind the table-driven command registration: body
and query-param parsing, path-template substitution, and result formatting.
"""

from __future__ import annotations

import json

import pytest
import yaml

from sylve_cli.client import SylveError
from sylve_cli.commands.extras import (
    _merge_body,
    _parse_data,
    _parse_params,
    _parse_set,
    _path_for,
    _print_result,
)
from sylve_cli.formatter import OutputFormat


# ---------------------------------------------------------------------------
# Request body parsing: raw YAML, @FILE reading, and error paths.
# ---------------------------------------------------------------------------
def test_parse_data_accepts_yaml_and_json(tmp_path) -> None:
    assert _parse_data(None) is None
    assert _parse_data("") is None
    assert _parse_data("name: web") == {"name": "web"}
    assert _parse_data('{"a": 1}') == {"a": 1}


def test_parse_data_reads_file(tmp_path) -> None:
    body = tmp_path / "body.yaml"
    body.write_text("name: web\ncores: 2\n", encoding="utf-8")
    assert _parse_data(f"@{body}") == {"name": "web", "cores": 2}


def test_parse_data_errors_on_missing_file_and_bad_yaml(tmp_path) -> None:
    with pytest.raises(SylveError, match="Could not read request body"):
        _parse_data(f"@{tmp_path}/missing.yaml")
    with pytest.raises(SylveError, match="Invalid request body"):
        _parse_data("name: [unclosed")


# ---------------------------------------------------------------------------
# Query parameter parsing: KEY=VALUE coercion and malformed rejection.
# ---------------------------------------------------------------------------
def test_parse_params_coerces_yaml_scalars() -> None:
    assert _parse_params(None) is None
    assert _parse_params(["limit=10", "action=pass"]) == {"limit": 10, "action": "pass"}


def test_parse_params_falls_back_to_raw_string_on_bad_yaml() -> None:
    # A value that is not valid YAML must be kept verbatim, not dropped.
    assert _parse_params(["note=hello world"]) == {"note": "hello world"}


def test_parse_params_rejects_missing_equals() -> None:
    with pytest.raises(SylveError, match="KEY=VALUE"):
        _parse_params(["nokey"])


# ---------------------------------------------------------------------------
# --property parsing: YAML coercion, dotted nesting, and body merging.
# ---------------------------------------------------------------------------
def test_parse_set_coerces_scalars_and_nests_dotted_keys() -> None:
    assert _parse_set(None) == {}
    assert _parse_set([]) == {}
    assert _parse_set(["cores=4", "dhcp=true"]) == {"cores": 4, "dhcp": True}
    assert _parse_set(["vlanPolicy.mode=tagged"]) == {"vlanPolicy": {"mode": "tagged"}}
    # Later entries win; unquoted values fall back to raw strings when not YAML.
    assert _parse_set(["a=1", "a=2"]) == {"a": 2}
    assert _parse_set(["note=hello world"]) == {"note": "hello world"}


def test_parse_set_schema_preserves_strings_and_builds_lists(capsys) -> None:
    schema = (
        ("name", "string", True, ()),
        ("value", "string", True, ()),
        ("ids", "array of integer", False, ()),
        (
            "guest",
            "object",
            False,
            (("enabled", "boolean", False, ()), ("writeable", "boolean", False, ())),
        ),
        (
            "addresses4",
            "array of object",
            False,
            (("cidr", "string", False, ()), ("objectId", "integer", False, ())),
        ),
        (
            "hooks",
            "object",
            False,
            (
                (
                    "prestart",
                    "object",
                    False,
                    (("enabled", "boolean", False, ()), ("script", "string", False, ())),
                ),
            ),
        ),
    )
    parsed = _parse_set(
        [
            "name=yes",
            "value=200000",
            "ids=1,2",
            "ids=3",
            "guest=enabled=true,writeable=false",
            "addresses4=cidr=10.0.0.1/24,objectId=0",
            "addresses4=cidr=10.0.1.1/24,objectId=0",
            "hooks.prestart.script=true",
            "typo=1",
        ],
        schema_fields=schema,
        label="PUT /test",
    )
    assert parsed == {
        "name": "yes",
        "value": "200000",
        "ids": [1, 2, 3],
        "guest": {"enabled": True, "writeable": False},
        "addresses4": [
            {"cidr": "10.0.0.1/24", "objectId": 0},
            {"cidr": "10.0.1.1/24", "objectId": 0},
        ],
        "hooks": {"prestart": {"script": "true"}},
        "typo": 1,
    }
    assert "unknown field 'typo'" in capsys.readouterr().err


def test_parse_set_rejects_bad_format() -> None:
    with pytest.raises(SylveError, match="KEY=VALUE"):
        _parse_set(["nokey"])
    with pytest.raises(SylveError, match="KEY=VALUE"):
        _parse_set([".a=1"])
    with pytest.raises(SylveError, match="KEY=VALUE"):
        _parse_set(["a..b=1"])
    with pytest.raises(SylveError, match="Invalid --property list"):
        _parse_set(["ids=[1, 2"], schema_fields=(("ids", "array of integer", False, ()),))


def test_merge_body_combines_data_and_set() -> None:
    assert _merge_body(None, None) is None
    assert _merge_body(None, ["cores=4"]) == {"cores": 4}
    assert _merge_body('{"cores": 2}', None) == {"cores": 2}
    assert _merge_body('{"a": 1, "nested": {"x": 1, "y": 2}}', ["b=3", "nested.x=9"]) == {
        "a": 1,
        "b": 3,
        "nested": {"x": 9, "y": 2},
    }


def test_merge_body_rejects_set_without_object_body() -> None:
    with pytest.raises(SylveError, match="JSON object body"):
        _merge_body("[1, 2]", ["a=1"])


# ---------------------------------------------------------------------------
# Path template substitution: placeholder count must match arguments.
# ---------------------------------------------------------------------------
def test_path_for_substitutes_placeholders_in_order() -> None:
    assert _path_for("/vm/{rid}/storage/{sid}", ["10", "20"]) == "/vm/10/storage/20"
    assert _path_for("/jail", None) == "/jail"


def test_path_for_rejects_argument_count_mismatch() -> None:
    with pytest.raises(SylveError, match="path argument"):
        _path_for("/vm/{rid}/storage/{sid}", ["10"])


# ---------------------------------------------------------------------------
# Result formatting: structured formats are serializable round-trips.
# ---------------------------------------------------------------------------
def test_print_result_json_and_yaml_round_trip(capsys) -> None:
    data = {"id": 1, "name": "web"}
    _print_result(data, OutputFormat.json, "ok")
    assert json.loads(capsys.readouterr().out) == data

    _print_result(data, OutputFormat.yaml, "ok")
    assert yaml.safe_load(capsys.readouterr().out) == data


def test_print_result_value_matches_print_dict(capsys) -> None:
    # A dict prints one value per line, the same as print_dict -f value.
    _print_result({"a": 1, "b": 2}, OutputFormat.value, "ok")
    assert capsys.readouterr().out.splitlines() == ["1", "2"]

    # A list of rows keeps one row per line.
    _print_result([{"x": 1, "y": 2}], OutputFormat.value, "ok")
    assert capsys.readouterr().out.splitlines() == ["1 2"]


def test_print_result_empty_prints_ok(capsys) -> None:
    _print_result(None, OutputFormat.table, "ok")
    assert "OK" in capsys.readouterr().out
