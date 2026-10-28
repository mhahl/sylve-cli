"""Tests for SylveClient multi-node routing (X-Current-Hostname), fan-out, and guest resolution."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import pytest

from sylve_cli.client import (
    ResourceNotFoundError,
    SessionExpiredError,
    SylveAPIError,
    SylveClient,
)
from sylve_cli.config import ContextConfig, extract_token_expiry
from tests.test_config import make_test_jwt


def _make_mock_client(handler: Any, expired: bool = False) -> SylveClient:
    delta = timedelta(minutes=-5) if expired else timedelta(hours=24)
    tok = make_test_jwt(datetime.now(timezone.utc) + delta)
    ctx = ContextConfig(
        server="https://sylve.lan:8181",
        username="admin",
        auth_type="sylve",
        node_id="uuid-node-1",
        hostname="node1.lan",
        token=tok,
        expires_at=extract_token_expiry(tok),
    )
    client = SylveClient(ctx)
    client._http = httpx.Client(
        base_url="https://sylve.lan:8181/api",
        transport=httpx.MockTransport(handler),
    )
    return client


def test_expired_token_blocked_before_http() -> None:
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, json={"status": "success", "data": {}})

    client = _make_mock_client(handler, expired=True)
    with pytest.raises(SessionExpiredError, match="expired"):
        client.get("/cluster")
    assert not called


def test_x_current_hostname_and_guest_resolution() -> None:
    seen_headers: list[tuple[str, str | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        host_hdr = request.headers.get("X-Current-Hostname")
        seen_headers.append((path, host_hdr))

        if path == "/api/cluster/nodes":
            return httpx.Response(
                200,
                json={
                    "status": "success",
                    "data": [
                        {"nodeUUID": "uuid-node-1", "hostname": "node1.lan", "status": "online"},
                        {"nodeUUID": "uuid-node-2", "hostname": "node2.lan", "status": "online"},
                    ],
                },
            )
        if path == "/api/cluster/resources":
            return httpx.Response(
                200,
                json={
                    "status": "success",
                    "data": [
                        {
                            "nodeUUID": "uuid-node-1",
                            "hostname": "node1.lan",
                            "vms": [{"rid": 101, "name": "web-01", "state": 1}],
                            "jails": [{"ctId": 201, "name": "dns-01", "state": "ACTIVE"}],
                        },
                        {
                            "nodeUUID": "uuid-node-2",
                            "hostname": "node2.lan",
                            "vms": [{"rid": 102, "name": "db-01", "state": 5}],
                            "jails": [{"ctId": 202, "name": "cache-01", "state": "INACTIVE"}],
                        },
                    ],
                },
            )
        if path == "/api/vm/102/actions/start":
            assert host_hdr == "node2.lan"
            return httpx.Response(
                200,
                json={
                    "status": "success",
                    "data": {"rid": 102, "action": "start", "outcome": "queued", "taskId": 99},
                },
            )
        if path == "/api/utilities/downloads":
            return httpx.Response(
                200,
                json={
                    "status": "success",
                    "data": [{"id": 1, "name": f"iso-on-{host_hdr}", "status": "completed"}],
                },
            )
        return httpx.Response(404, json={"status": "error", "error": "not_found", "message": "not_found"})

    client = _make_mock_client(handler)

    # Resolve VM by name on node2.lan
    rid, host, _ = client.resolve_vm("db-01")
    assert rid == 102
    assert host == "node2.lan"

    # Resolve Jail by CTID on node1.lan
    ctid, jhost, _ = client.resolve_jail(201)
    assert ctid == 201
    assert jhost == "node1.lan"

    # Resolve node UUID to hostname when issuing node-scoped request
    resp = client.post("/vm/102/actions/start", node="uuid-node-2")
    assert resp["taskId"] == 99

    # Fan-out GET across all online nodes
    fan = client.fan_out_get("/utilities/downloads")
    assert len(fan) == 2
    assert fan[0][0] == "node1.lan"
    assert fan[1][0] == "node2.lan"

    with pytest.raises(ResourceNotFoundError):
        client.resolve_vm("nonexistent-vm")

    with pytest.raises(SylveAPIError):
        client.get("/does-not-exist")
