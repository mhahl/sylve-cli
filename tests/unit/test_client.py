"""Unit tests for the HTTP client boundary and routing behaviour."""

from __future__ import annotations

import base64
import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import pytest

from sylve_cli.client import (
    ResourceNotFoundError,
    SylveAPIError,
    SylveClient,
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


def make_context() -> ContextConfig:
    """Return a context with a valid token."""
    expiry = datetime.now(timezone.utc) + timedelta(hours=1)
    return ContextConfig(
        server="https://sylve.example.test",
        token=make_jwt(expiry),
        verify_ssl=False,
    )


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


def test_request_sends_auth_and_unwraps_envelope() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/vm/1"
        assert request.headers["Authorization"].startswith("Bearer ")
        return httpx.Response(
            200,
            json={"status": "success", "data": {"rid": 1, "name": "web"}},
        )

    with client_with(handler) as client:
        assert client.get("/vm/1") == {"rid": 1, "name": "web"}


def test_request_maps_api_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            json={
                "status": "error",
                "message": "vm_not_found",
                "error": "vm 9 does not exist",
                "data": {"rid": 9},
            },
        )

    with client_with(handler) as client:
        with pytest.raises(SylveAPIError) as exc_info:
            client.get("/vm/9")
    assert exc_info.value.status_code == 404
    assert "vm_not_found" in str(exc_info.value)
    assert exc_info.value.data == {"rid": 9}


def test_node_resolution_and_header() -> None:
    nodes = [
        {"nodeUUID": "uuid-1", "hostname": "node1.lan"},
        {"nodeUUID": "uuid-2", "hostname": "node2.lan"},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/cluster/nodes":
            return httpx.Response(200, json={"status": "success", "data": nodes})
        assert request.headers["X-Current-Hostname"] == "node2.lan"
        return httpx.Response(200, json={"status": "success", "data": {"ok": True}})

    with client_with(handler) as client:
        assert client.resolve_node_hostname("uuid-2") == "node2.lan"
        assert client.resolve_node_hostname("unknown") == "unknown"
        assert client.get("/test", node="uuid-2") == {"ok": True}


def test_fan_out_get_uses_each_online_node() -> None:
    nodes = [
        {"nodeUUID": "uuid-1", "hostname": "node1.lan", "status": "online"},
        {"nodeUUID": "uuid-2", "hostname": "node2.lan", "status": "online"},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/cluster/nodes":
            return httpx.Response(200, json={"status": "success", "data": nodes})
        host = request.headers["X-Current-Hostname"]
        return httpx.Response(200, json={"status": "success", "data": [{"node": host}]})

    with client_with(handler) as client:
        results = client.fan_out_get("/vm/simple")
    assert [host for host, _ in results] == ["node1.lan", "node2.lan"]
    assert [data[0]["node"] for _, data in results] == ["node1.lan", "node2.lan"]


def test_resolve_vm_by_name_and_numeric() -> None:
    resources = [
        {
            "hostname": "node1.lan",
            "vms": [{"rid": 101, "name": "web"}],
            "jails": [],
        }
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/cluster/nodes":
            return httpx.Response(
                200,
                json={
                    "status": "success",
                    "data": [{"nodeUUID": "u1", "hostname": "node1.lan", "status": "online"}],
                },
            )
        return httpx.Response(200, json={"status": "success", "data": resources})

    with client_with(handler) as client:
        assert client.resolve_vm("web")[:2] == (101, "node1.lan")
        assert client.resolve_vm("101")[:2] == (101, "node1.lan")


def test_resolve_vm_not_found() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/cluster/nodes":
            return httpx.Response(200, json={"status": "success", "data": []})
        return httpx.Response(200, json={"status": "success", "data": []})

    with client_with(handler) as client:
        with pytest.raises(ResourceNotFoundError):
            client.resolve_vm("missing")


def test_download_file_and_stream_lines(tmp_path) -> None:
    seen_sse_token: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/file":
            return httpx.Response(200, content=b"payload")
        if request.url.path == "/api/auth/sse-tokens":
            return httpx.Response(
                200,
                json={"status": "success", "data": {"token": "sse-tok-123", "expiresIn": 600}},
            )
        seen_sse_token.append(request.url.params.get("sse_token"))
        return httpx.Response(
            200,
            content=b"event: update\ndata: {}\n",
            headers={"Content-Type": "text/event-stream"},
        )

    with client_with(handler) as client:
        target = client.download_file("/file", tmp_path / "out.bin")
        assert target.read_bytes() == b"payload"
        assert list(client.stream_lines("/events/stream")) == ["event: update", "data: {}"]
        assert seen_sse_token == ["sse-tok-123"]


def test_login_updates_context() -> None:
    new_token = make_jwt(datetime.now(timezone.utc) + timedelta(days=1))

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/auth/login"
        return httpx.Response(
            200,
            json={
                "status": "success",
                "data": {"token": new_token, "hostname": "node1.lan", "nodeId": "u1"},
            },
        )

    with client_with(handler) as client:
        ctx = client.login("admin", "secret", remember=False)
    assert ctx.token == new_token
    assert ctx.hostname == "node1.lan"


def test_enrich_template_metadata_merges_detail() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/vm/templates/7"
        return httpx.Response(
            200,
            json={
                "status": "success",
                "data": {
                    "id": 7,
                    "name": "debian-13",
                    "sourceVmName": "web-01",
                    "createdAt": "2026-10-28T14:13:24.369790382+11:00",
                    "pool": "zroot",
                },
            },
        )

    with client_with(handler) as client:
        item: dict[str, Any] = {"id": 7, "name": "debian-13"}
        client.enrich_template_metadata(item, "/vm/templates/7", None)
    assert item["createdAt"].startswith("2026-10-28")
    assert item["pool"] == "zroot"


def test_enrich_template_metadata_tolerates_missing_or_errored_detail() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if len(calls) == 1:
            return httpx.Response(404, json={"status": "error", "message": "not_found"})
        return httpx.Response(
            200,
            json={"status": "success", "data": {"id": 9, "name": "x"}},
        )

    with client_with(handler) as client:
        gone: dict[str, Any] = {"id": 8}
        client.enrich_template_metadata(gone, "/vm/templates/8", None)
        assert "createdAt" not in gone
        assert "pool" not in gone

        no_date: dict[str, Any] = {"id": 9, "createdAt": "placeholder"}
        client.enrich_template_metadata(no_date, "/vm/templates/9", None)
        assert no_date["createdAt"] == "placeholder"
