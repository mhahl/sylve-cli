"""Unit tests for the live-test Swagger response validator."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.live.openapi import OpenAPISpec

SPEC_PATH = Path(__file__).resolve().parents[2] / "docs" / "swagger.json"


@pytest.fixture(scope="module")
def spec() -> OpenAPISpec:
    """Load the bundled Swagger document."""
    return OpenAPISpec(SPEC_PATH)


def test_accepts_matching_response(spec: OpenAPISpec) -> None:
    spec.validate(
        "GET",
        "/cluster/nodes",
        [{"nodeUUID": "u1", "hostname": "node1.lan", "status": "online"}],
    )


def test_rejects_wrong_shape(spec: OpenAPISpec) -> None:
    """A plain string where structured data is expected means a non-JSON body."""
    with pytest.raises(AssertionError, match="non-JSON body"):
        spec.validate("GET", "/cluster/nodes", "not-a-list")


def test_rejects_unknown_endpoint(spec: OpenAPISpec) -> None:
    with pytest.raises(AssertionError, match="not present"):
        spec.validate("GET", "/not/a/real/path", {})
