"""Unit tests for client error contracts and cluster/guest invariants.

These target behavior that the existing client tests do not cover: the
auth-failure contract, response-parse error handling, dependency-failure
handling, and the multi-node ambiguity/fallback invariants.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from sylve_cli.client import (
    ResourceNotFoundError,
    SessionExpiredError,
    SylveAPIError,
    SylveClient,
    SylveError,
)
from sylve_cli.config import ContextConfig


def make_jwt(expires_at: datetime) -> str:
    """Build an unsigned JWT for tests."""
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').decode().rstrip("=")
    payload = (
        base64.urlsafe_b64encode(
            json.dumps({"sub": "admin", "exp": int(expires_at.timestamp())}).encode()
        )
        .decode()
        .rstrip("=")
    )
    return f"{header}.{payload}.sig"


def make_context(**overrides: object) -> ContextConfig:
    """Return a context with a token valid for one hour unless overridden."""
    defaults: dict[str, object] = {
        "server": "https://sylve.example.test",
        "token": make_jwt(datetime.now(timezone.utc) + timedelta(hours=1)),
        "verify_ssl": False,
    }
    defaults.update(overrides)
    return ContextConfig(**defaults)


@contextmanager
def client_with(handler: Callable[[httpx.Request], httpx.Response]) -> Iterator[SylveClient]:
    """Create a client backed by an httpx mock transport."""
    client = SylveClient(make_context())
    client.close()
    client._http = httpx.Client(
        base_url=client._base_url,
        transport=httpx.MockTransport(handler),
    )
    try:
        yield client
    finally:
        client.close()


@contextmanager
def client_with_context(
    context: ContextConfig,
    handler: Callable[[httpx.Request], httpx.Response],
) -> Iterator[SylveClient]:
    """Create a mock-transport client for an explicit context."""
    client = SylveClient(context)
    client.close()
    client._http = httpx.Client(
        base_url=client._base_url,
        transport=httpx.MockTransport(handler),
    )
    try:
        yield client
    finally:
        client.close()


# ---------------------------------------------------------------------------
# Auth contract: missing vs expired tokens are both rejected before any I/O.
# ---------------------------------------------------------------------------
def test_request_with_no_token_raises_session_expired() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request should be sent without a token")

    with client_with_context(make_context(token=""), handler) as client:
        with pytest.raises(SessionExpiredError, match="No authentication token"):
            client.get("/vm/1")


def test_request_with_expired_token_raises_session_expired() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request should be sent with an expired token")

    expired = make_context(token=make_jwt(datetime.now(timezone.utc) - timedelta(minutes=5)))
    with client_with_context(expired, handler) as client:
        with pytest.raises(SessionExpiredError, match="token expired"):
            client.get("/vm/1")


def test_request_with_require_auth_false_sends_no_bearer() -> None:
    """Unauthenticated requests (login) must not carry an Authorization header."""
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("Authorization", ""))
        return httpx.Response(200, json={"status": "success", "data": {"token": "t"}})

    with client_with(handler) as client:
        client.request("POST", "/auth/login", json_body={}, require_auth=False)
    assert seen == [""]


# ---------------------------------------------------------------------------
# Response-parse contract: a non-JSON error body is surfaced as an API error.
# ---------------------------------------------------------------------------
def test_non_json_error_body_raises_api_error() -> None:
    """Older servers may answer errors with an HTML page; that must still raise."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            content=b"<html><body>Not Found</body></html>",
            headers={"Content-Type": "text/html"},
        )

    with client_with(handler) as client:
        with pytest.raises(SylveAPIError) as exc_info:
            client.get("/vm/9")
    assert exc_info.value.status_code == 404
    # The HTML shell must never be echoed as the error text.
    assert "<html" not in str(exc_info.value)
    assert "HTTP 404" in str(exc_info.value)
    assert "endpoint not implemented" in str(exc_info.value)


# ---------------------------------------------------------------------------
# login contract: a success status without a token is a hard failure, and the
# context is not mutated on failure.
# ---------------------------------------------------------------------------
def test_login_rejects_response_without_token() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "success", "data": {"hostname": "n1"}})

    # A context with no token, so a failed login must not install a session.
    with client_with_context(make_context(token=""), handler) as client:
        with pytest.raises(SylveError, match="did not contain a valid token"):
            client.login("admin", "secret")
    assert client.context.token == ""


# ---------------------------------------------------------------------------
# logout contract: revocation failure must be swallowed, not propagated.
# ---------------------------------------------------------------------------
def test_logout_swallows_revocation_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"status": "error", "message": "boom"})

    with client_with(handler) as client:
        # Must not raise even though the server rejects the revocation.
        client.logout()


# ---------------------------------------------------------------------------
# Online-node invariant: with no online node, every node is treated as a target.
# ---------------------------------------------------------------------------
def test_get_online_nodes_falls_back_to_all_when_none_online() -> None:
    nodes = [
        {"nodeUUID": "u1", "hostname": "node1.lan", "status": "offline"},
        {"nodeUUID": "u2", "hostname": "node2.lan", "status": "draining"},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "success", "data": nodes})

    with client_with(handler) as client:
        online = client.get_online_nodes()
    assert [n["hostname"] for n in online] == ["node1.lan", "node2.lan"]


# ---------------------------------------------------------------------------
# Guest-resolution invariants: a name that matches several guests is ambiguous
# and must be rejected rather than silently returning one.
# ---------------------------------------------------------------------------
def test_resolve_vm_ambiguous_name_raises() -> None:
    resources = [
        {"hostname": "node1.lan", "vms": [{"rid": 101, "name": "web"}], "jails": []},
        {"hostname": "node2.lan", "vms": [{"rid": 202, "name": "web"}], "jails": []},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/cluster/nodes":
            return httpx.Response(
                200,
                json={"status": "success", "data": [{"nodeUUID": "u", "hostname": "node1.lan"}]},
            )
        return httpx.Response(200, json={"status": "success", "data": resources})

    with client_with(handler) as client:
        with pytest.raises(SylveError, match="Multiple VMs match"):
            client.resolve_vm("web")


# ---------------------------------------------------------------------------
# Node-resolution contract: an unknown node for uuid resolution is a hard
# error naming the node, distinct from the lenient hostname resolver.
# ---------------------------------------------------------------------------
def test_resolve_node_uuid_not_found_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "success", "data": []})

    with client_with(handler) as client:
        with pytest.raises(ResourceNotFoundError, match="missing-node"):
            client.resolve_node_uuid("missing-node")


# ---------------------------------------------------------------------------
# Cluster-discovery invariant: when /cluster/nodes is unavailable the client
# falls back to /info/node rather than returning an empty list.
# ---------------------------------------------------------------------------
def test_get_cluster_nodes_falls_back_to_info_node() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/cluster/nodes":
            return httpx.Response(500, json={"status": "error", "message": "boom"})
        assert request.url.path == "/api/info/node"
        return httpx.Response(
            200,
            json={
                "status": "success",
                "data": {
                    "hostname": "standalone.lan",
                    "logicalCores": 4,
                    "ramTotal": 8589934592,
                },
            },
        )

    with client_with(handler) as client:
        nodes = client.get_cluster_nodes()
    assert len(nodes) == 1
    assert nodes[0]["hostname"] == "standalone.lan"
