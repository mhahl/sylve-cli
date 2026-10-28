"""Tests for JWT decoding, token expiration, and ~/.config/sylve/config.yaml persistence."""

from __future__ import annotations

import base64
import json
import os
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sylve_cli.config import (
    ContextConfig,
    SylveConfig,
    decode_jwt_payload,
    extract_token_expiry,
    load_config,
    normalize_server_url,
    save_config,
)


def make_test_jwt(exp_dt: datetime, username: str = "admin", auth_type: str = "sylve") -> str:
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode().rstrip("=")
    payload = base64.urlsafe_b64encode(
        json.dumps(
            {
                "exp": int(exp_dt.timestamp()),
                "jti": "test-uuid",
                "custom_claims": {
                    "user_id": 1,
                    "username": username,
                    "auth_type": auth_type,
                },
            }
        ).encode()
    ).decode().rstrip("=")
    return f"{header}.{payload}.signature"


def test_decode_jwt_and_expiry() -> None:
    future = datetime.now(timezone.utc) + timedelta(hours=24)
    token = make_test_jwt(future, username="operator", auth_type="pam")

    payload = decode_jwt_payload(token)
    assert payload["custom_claims"]["username"] == "operator"
    assert payload["custom_claims"]["auth_type"] == "pam"

    exp_iso = extract_token_expiry(token)
    assert exp_iso is not None
    assert exp_iso.endswith("Z")

    ctx = ContextConfig(server="https://sylve.lan:8181", token=token, expires_at=exp_iso)
    assert not ctx.is_token_expired()
    assert ctx.remaining_seconds() is not None and ctx.remaining_seconds() > 3600
    assert "h" in ctx.format_remaining() or "d" in ctx.format_remaining()


def test_expired_token_detection() -> None:
    past = datetime.now(timezone.utc) - timedelta(minutes=10)
    token = make_test_jwt(past)
    ctx = ContextConfig(
        server="https://sylve.lan:8181",
        token=token,
        expires_at=extract_token_expiry(token),
    )
    assert ctx.is_token_expired()
    assert "expired" in ctx.format_remaining()


def test_save_and_load_config_permissions(tmp_path: Path) -> None:
    cfg_file = tmp_path / "sylve" / "config.yaml"
    future = datetime.now(timezone.utc) + timedelta(days=7)
    token = make_test_jwt(future)

    cfg = SylveConfig(
        current_context="prod",
        contexts={
            "prod": ContextConfig(
                server="sylve.lan:8181",
                username="admin",
                auth_type="sylve",
                node_id="node-1",
                hostname="node1.lan",
                token=token,
                expires_at=extract_token_expiry(token),
                verify_ssl=False,
            )
        },
    )
    save_config(cfg, cfg_file)
    assert cfg_file.exists()

    mode = stat.S_IMODE(os.stat(cfg_file).st_mode)
    assert mode == 0o600

    loaded = load_config(cfg_file)
    assert loaded.current_context == "prod"
    name, active = loaded.get_active_context()
    assert name == "prod"
    assert active.server == "https://sylve.lan:8181"
    assert active.username == "admin"
    assert active.hostname == "node1.lan"
    assert not active.verify_ssl
    assert not active.is_token_expired()


def test_normalize_server_url() -> None:
    assert normalize_server_url("sylve.lan:8181") == "https://sylve.lan:8181"
    assert normalize_server_url("https://sylve.lan:8181/api/") == "https://sylve.lan:8181"
    assert normalize_server_url("http://10.0.0.5:8181/") == "http://10.0.0.5:8181"
    with pytest.raises(ValueError):
        normalize_server_url("   ")
