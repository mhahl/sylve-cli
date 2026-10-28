"""Unit tests for configuration, JWT parsing, and context resolution."""

from __future__ import annotations

import base64
import json
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sylve_cli.config import (
    ContextConfig,
    SylveConfig,
    decode_jwt_payload,
    extract_token_expiry,
    get_default_config_path,
    load_config,
    normalize_server_url,
    parse_iso_datetime,
    save_config,
)


def make_jwt(expires_at: datetime, username: str = "admin") -> str:
    """Build an unsigned JWT for tests."""
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').decode().rstrip("=")
    payload = (
        base64.urlsafe_b64encode(
            json.dumps({"sub": username, "exp": int(expires_at.timestamp())}).encode()
        )
        .decode()
        .rstrip("=")
    )
    return f"{header}.{payload}.signature"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("", {}),
        ("not-a-jwt", {}),
        ("a.b", {}),
        ("a.%%%.c", {}),
    ],
)
def test_decode_jwt_payload_edge_cases(value: str, expected: dict[str, object]) -> None:
    assert decode_jwt_payload(value) == expected


def test_decode_jwt_payload_reads_claims() -> None:
    token = make_jwt(datetime(2026, 1, 1, tzinfo=timezone.utc), "operator")
    assert decode_jwt_payload(token)["sub"] == "operator"


def test_extract_token_expiry() -> None:
    expiry = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    assert extract_token_expiry(make_jwt(expiry)) == "2026-05-01T12:00:00Z"
    assert extract_token_expiry("invalid") is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-01-01T00:00:00Z", datetime(2026, 1, 1, tzinfo=timezone.utc)),
        ("2026-01-01T00:00:00", datetime(2026, 1, 1, tzinfo=timezone.utc)),
        ("invalid", None),
        (None, None),
    ],
)
def test_parse_iso_datetime(value: str | None, expected: datetime | None) -> None:
    assert parse_iso_datetime(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("sylve.example.test", "https://sylve.example.test"),
        ("https://sylve.example.test/", "https://sylve.example.test"),
        ("https://sylve.example.test/api", "https://sylve.example.test"),
        ("https://sylve.example.test/api/", "https://sylve.example.test"),
    ],
)
def test_normalize_server_url(value: str, expected: str) -> None:
    assert normalize_server_url(value) == expected


def test_normalize_server_url_rejects_empty() -> None:
    with pytest.raises(ValueError):
        normalize_server_url("  ")


def test_context_token_lifecycle() -> None:
    future = datetime.now(timezone.utc) + timedelta(hours=2)
    ctx = ContextConfig(server="https://example.test", token=make_jwt(future))
    assert ctx.is_token_expired() is False
    assert ctx.get_expiry_datetime() is not None
    assert ctx.remaining_seconds() is not None
    assert "h" in ctx.format_remaining()


def test_context_expired_and_missing_token() -> None:
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    expired = ContextConfig(server="https://example.test", token=make_jwt(past))
    assert expired.is_token_expired() is True
    assert expired.format_remaining().startswith("expired")

    missing = ContextConfig(server="https://example.test")
    assert missing.is_token_expired() is True
    assert missing.format_remaining() == "unknown"


def test_config_roundtrip_and_permissions(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    config = SylveConfig(
        current_context="prod",
        contexts={
            "prod": ContextConfig(
                server="https://sylve.example.test",
                username="admin",
                token="token",
                default_node="node1.example.test",
            )
        },
    )
    saved = save_config(config, path)
    assert saved == path
    assert stat.S_IMODE(path.stat().st_mode) == 0o600

    loaded = load_config(path)
    assert loaded.current_context == "prod"
    assert loaded.contexts["prod"].server == "https://sylve.example.test"
    assert loaded.contexts["prod"].default_node == "node1.example.test"


def test_load_config_missing_or_invalid(tmp_path: Path) -> None:
    assert load_config(tmp_path / "missing.yaml").contexts == {}

    invalid = tmp_path / "invalid.yaml"
    invalid.write_text("contexts: [\n", encoding="utf-8")
    with pytest.raises(RuntimeError):
        load_config(invalid)


def test_get_active_context_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SYLVE_SERVER", "sylve.example.test")
    monkeypatch.setenv("SYLVE_TOKEN", make_jwt(datetime.now(timezone.utc) + timedelta(hours=1)))
    monkeypatch.setenv("SYLVE_NODE", "node2.example.test")
    monkeypatch.setenv("SYLVE_INSECURE", "true")

    name, context = SylveConfig().get_active_context()
    assert name == "env"
    assert context.server == "https://sylve.example.test"
    assert context.default_node == "node2.example.test"
    assert context.verify_ssl is False


def test_get_active_context_requires_login() -> None:
    with pytest.raises(RuntimeError):
        SylveConfig().get_active_context()


def test_get_active_context_unknown_name() -> None:
    config = SylveConfig(
        contexts={"prod": ContextConfig(server="https://example.test")},
    )
    with pytest.raises(RuntimeError):
        config.get_active_context("missing")


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ({}, Path.home() / ".config" / "sylve" / "config.yaml"),
        ({"XDG_CONFIG_HOME": "/tmp/xdg"}, Path("/tmp/xdg/sylve/config.yaml")),
        ({"SYLVE_CONFIG": "~/sylve.yaml"}, Path.home() / "sylve.yaml"),
    ],
)
def test_get_default_config_path(
    env: dict[str, str], expected: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for key in ("SYLVE_CONFIG", "XDG_CONFIG_HOME"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    assert get_default_config_path() == expected
