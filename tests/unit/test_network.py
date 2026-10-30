"""CLI tests for network interface commands, especially phantom-endpoint handling."""

from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
import pytest
from typer.testing import CliRunner

from sylve_cli.config import ContextConfig, SylveConfig, save_config
from sylve_cli.main import app

runner = CliRunner()


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


@pytest.fixture()
def html_l3_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, dict[str, Any]]:
    """CLI context whose /network/interface/l3 returns an HTML page."""
    config_path = tmp_path / "config.yaml"
    save_config(
        SylveConfig(
            current_context="test",
            contexts={
                "test": ContextConfig(
                    server="https://sylve.example.test",
                    token=make_jwt(datetime.now(timezone.utc) + timedelta(hours=1)),
                    verify_ssl=False,
                )
            },
        ),
        config_path,
    )
    monkeypatch.setenv("SYLVE_CONFIG", str(config_path))
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.setdefault("path", request.url.path)
        return httpx.Response(
            200,
            content=b"<!doctype html><html><body>svelte shell</body></html>",
            headers={"Content-Type": "text/html"},
        )

    original_init = httpx.Client.__init__

    def patched_init(self: Any, *args: Any, **kwargs: Any) -> None:
        kwargs["transport"] = httpx.MockTransport(handler)
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.Client, "__init__", patched_init)
    return config_path, seen


def test_interface_l3_html_returns_clean_error(html_l3_config: tuple[Path, dict[str, Any]]) -> None:
    """A phantom endpoint returning HTML must error cleanly, not print HTML."""
    result = runner.invoke(app, ["network", "interface", "l3", "-f", "json"])
    assert result.exit_code == 1
    assert result.exception is not None
    assert "not implemented" in str(result.exception)
    assert "<html" not in result.stdout
