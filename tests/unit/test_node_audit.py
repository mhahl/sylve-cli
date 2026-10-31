"""Unit tests for node audit-log path extraction."""

from __future__ import annotations

import pytest

from sylve_cli.commands.node import _audit_request_path


@pytest.mark.parametrize(
    ("action", "expected"),
    [
        (
            '{"body":{"targetNodeUuid":"u1"},"method":"POST",'
            '"path":"/api/vm/902/migrations","response":{}}',
            "/api/vm/902/migrations",
        ),
        ("not json at all", "-"),
        (None, "-"),
        ('{"method":"GET"}', "-"),
    ],
)
def test_audit_request_path(action: str | None, expected: str) -> None:
    assert _audit_request_path(action) == expected
