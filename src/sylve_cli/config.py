"""Configuration and session token management for sylve-cli."""

from __future__ import annotations

import base64
import json
import os
import stat
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


def get_default_config_path() -> Path:
    """Return the default configuration file path.

    Returns:
        Path: ``$SYLVE_CONFIG``, ``$XDG_CONFIG_HOME/sylve/config.yaml``, or
        ``~/.config/sylve/config.yaml``.

    Example:
        >>> get_default_config_path().name
        'config.yaml'
    """
    env_path = os.environ.get("SYLVE_CONFIG")
    if env_path:
        return Path(env_path).expanduser()
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".config"
    return base / "sylve" / "config.yaml"


def decode_jwt_payload(token: str) -> dict[str, Any]:
    """Decode a JWT payload without verifying its signature.

    Args:
        token: Compact JWT string.

    Returns:
        dict[str, Any]: Decoded claims, or an empty dict when malformed.

    Example:
        >>> decode_jwt_payload("header.payload.signature")
        {}
    """
    if not token or "." not in token:
        return {}
    parts = token.split(".")
    if len(parts) < 2:
        return {}
    payload_b64 = parts[1]
    padding = "=" * ((4 - len(payload_b64) % 4) % 4)
    try:
        raw = base64.urlsafe_b64decode(payload_b64 + padding)
        data = json.loads(raw.decode("utf-8"))
        return data if isinstance(data, dict) else {}
    except (ValueError, UnicodeDecodeError):
        return {}


def extract_token_expiry(token: str) -> str | None:
    """Extract the JWT ``exp`` claim as an ISO-8601 UTC timestamp.

    Args:
        token: Compact JWT string.

    Returns:
        str | None: Timestamp such as ``2026-01-01T00:00:00Z``, or None.

    Example:
        >>> extract_token_expiry("") is None
        True
    """
    payload = decode_jwt_payload(token)
    exp = payload.get("exp")
    if isinstance(exp, (int, float)) and exp > 0:
        dt = datetime.fromtimestamp(exp, tz=timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")
    return None


def parse_iso_datetime(value: str | None) -> datetime | None:
    """Parse an ISO-8601 timestamp into an aware UTC datetime.

    Args:
        value: Timestamp text, with or without a trailing ``Z``.

    Returns:
        datetime | None: UTC datetime, or None when parsing fails.

    Example:
        >>> parse_iso_datetime("2026-01-01T00:00:00Z")
        datetime.datetime(2026, 1, 1, 0, 0, tzinfo=datetime.timezone.utc)
    """
    if not value:
        return None
    try:
        normalized = value.strip()
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def normalize_server_url(server: str) -> str:
    """Normalize a Sylve server URL.

    Args:
        server: Hostname or URL, with or without a scheme or ``/api`` suffix.

    Returns:
        str: URL with an ``http`` or ``https`` scheme and no trailing slash.

    Raises:
        ValueError: If *server* is empty.

    Example:
        >>> normalize_server_url("sylve.example.test/api/")
        'https://sylve.example.test'
    """
    s = server.strip()
    if not s:
        raise ValueError("Server URL cannot be empty")
    if not s.startswith(("http://", "https://")):
        s = f"https://{s}"
    s = s.rstrip("/")
    s = s.removesuffix("/api")
    return s


@dataclass
class ContextConfig:
    """Represents a single Sylve server/cluster login context."""

    server: str
    username: str = ""
    auth_type: str = "sylve"
    node_id: str = ""
    hostname: str = ""
    token: str = ""
    expires_at: str | None = None
    verify_ssl: bool = True
    ca_cert: str | None = None
    default_node: str | None = None

    def get_expiry_datetime(self) -> datetime | None:
        """Return the token expiry from config or the decoded JWT.

        Returns:
            datetime | None: Aware UTC expiry, or None when unknown.

        Example:
            >>> ContextConfig("https://example.test").get_expiry_datetime() is None
            True
        """
        dt = parse_iso_datetime(self.expires_at)
        if dt is not None:
            return dt
        if self.token:
            return parse_iso_datetime(extract_token_expiry(self.token))
        return None

    def is_token_expired(self, skew_seconds: int = 0) -> bool:
        """Return whether the token is missing or expired.

        Args:
            skew_seconds: Treat tokens expiring within this many seconds as stale.

        Returns:
            bool: True when no token exists or its expiry has passed.

        Example:
            >>> ContextConfig("https://example.test").is_token_expired()
            True
        """
        if not self.token:
            return True
        exp = self.get_expiry_datetime()
        if exp is None:
            return False
        now = datetime.now(timezone.utc)
        return (exp.timestamp() - now.timestamp()) <= skew_seconds

    def remaining_seconds(self) -> float | None:
        """Return remaining token lifetime in seconds.

        Returns:
            float | None: Seconds until expiry, or None when unknown.

        Example:
            >>> ContextConfig("https://example.test").remaining_seconds() is None
            True
        """
        exp = self.get_expiry_datetime()
        if exp is None:
            return None
        now = datetime.now(timezone.utc)
        return exp.timestamp() - now.timestamp()

    def format_remaining(self) -> str:
        """Return a human-readable token lifetime.

        Returns:
            str: Compact duration such as ``2h 5m``, ``expired (...)``, or
            ``unknown``.

        Example:
            >>> ContextConfig("https://example.test").format_remaining()
            'unknown'
        """
        rem = self.remaining_seconds()
        if rem is None:
            return "unknown"
        if rem <= 0:
            exp = self.get_expiry_datetime()
            exp_str = exp.strftime("%Y-%m-%d %H:%M:%S UTC") if exp else "unknown"
            return f"expired ({exp_str})"
        total_sec = int(rem)
        days, r = divmod(total_sec, 86400)
        hours, r = divmod(r, 3600)
        minutes, seconds = divmod(r, 60)
        parts: list[str] = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        if not parts:
            parts.append(f"{seconds}s")
        return " ".join(parts)


@dataclass
class SylveConfig:
    """Top-level CLI configuration holding named contexts and active context."""

    current_context: str = ""
    contexts: dict[str, ContextConfig] = field(default_factory=dict)

    def get_active_context(self, context_override: str | None = None) -> tuple[str, ContextConfig]:
        """Resolve the active context.

        Args:
            context_override: Context name that takes precedence over config
                and ``$SYLVE_CONTEXT``.

        Returns:
            tuple[str, ContextConfig]: Context name and resolved settings.

        Raises:
            RuntimeError: If no context is configured and no environment
                credentials are present.

        Example:
            >>> config = SylveConfig(
            ...     contexts={"prod": ContextConfig("https://example.test")}
            ... )
            >>> config.get_active_context("prod")[0]
            'prod'
        """
        ctx_name = context_override or os.environ.get("SYLVE_CONTEXT") or self.current_context
        if not ctx_name or ctx_name not in self.contexts:
            # Allow pure environment-driven usage if SYLVE_SERVER and SYLVE_TOKEN are set
            env_server = os.environ.get("SYLVE_SERVER")
            env_token = os.environ.get("SYLVE_TOKEN")
            if env_server and env_token:
                verify_ssl = os.environ.get("SYLVE_INSECURE", "").lower() not in (
                    "1",
                    "true",
                    "yes",
                )
                return "env", ContextConfig(
                    server=normalize_server_url(env_server),
                    token=env_token,
                    expires_at=extract_token_expiry(env_token),
                    verify_ssl=verify_ssl,
                    default_node=os.environ.get("SYLVE_NODE"),
                )
            if not self.contexts:
                raise RuntimeError(
                    "Not logged in to any Sylve server. Run 'sylve login <server-url>' first."
                )
            if ctx_name and ctx_name not in self.contexts:
                raise RuntimeError(
                    f"Context '{ctx_name}' not found in configuration. "
                    f"Available contexts: {', '.join(sorted(self.contexts.keys()))}"
                )
            ctx_name = next(iter(self.contexts.keys()))

        ctx = self.contexts[ctx_name]
        # Apply environment variable overrides if present
        env_server = os.environ.get("SYLVE_SERVER")
        env_token = os.environ.get("SYLVE_TOKEN")
        env_node = os.environ.get("SYLVE_NODE")
        env_insecure = os.environ.get("SYLVE_INSECURE")

        resolved = ContextConfig(
            server=normalize_server_url(env_server) if env_server else ctx.server,
            username=ctx.username,
            auth_type=ctx.auth_type,
            node_id=ctx.node_id,
            hostname=ctx.hostname,
            token=env_token if env_token else ctx.token,
            expires_at=extract_token_expiry(env_token) if env_token else ctx.expires_at,
            verify_ssl=(
                False
                if (env_insecure and env_insecure.lower() in ("1", "true", "yes"))
                else ctx.verify_ssl
            ),
            ca_cert=ctx.ca_cert,
            default_node=env_node if env_node else ctx.default_node,
        )
        return ctx_name, resolved


def load_config(path: Path | None = None) -> SylveConfig:
    """Load configuration from disk.

    Args:
        path: Config path. Defaults to :func:`get_default_config_path`.

    Returns:
        SylveConfig: Parsed configuration, or an empty config if absent.

    Raises:
        RuntimeError: If the file exists but cannot be parsed.

    Example:
        >>> load_config(Path("/missing.yaml")).contexts
        {}
    """
    cfg_path = path or get_default_config_path()
    if not cfg_path.exists():
        return SylveConfig()
    try:
        raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        raise RuntimeError(f"Failed to parse configuration file {cfg_path}: {exc}") from exc

    if not isinstance(raw, dict):
        return SylveConfig()

    current_context = str(raw.get("current_context") or "")
    raw_contexts = raw.get("contexts") or {}
    contexts: dict[str, ContextConfig] = {}

    if isinstance(raw_contexts, dict):
        for name, cdata in raw_contexts.items():
            if not isinstance(cdata, dict) or not cdata.get("server"):
                continue
            contexts[str(name)] = ContextConfig(
                server=normalize_server_url(str(cdata.get("server", ""))),
                username=str(cdata.get("username") or ""),
                auth_type=str(cdata.get("auth_type") or "sylve"),
                node_id=str(cdata.get("node_id") or ""),
                hostname=str(cdata.get("hostname") or ""),
                token=str(cdata.get("token") or ""),
                expires_at=cdata.get("expires_at"),
                verify_ssl=bool(cdata.get("verify_ssl", True)),
                ca_cert=cdata.get("ca_cert"),
                default_node=cdata.get("default_node"),
            )

    return SylveConfig(current_context=current_context, contexts=contexts)


def save_config(config: SylveConfig, path: Path | None = None) -> Path:
    """Persist configuration with mode 0600.

    Args:
        config: Configuration object to serialize.
        path: Destination path. Defaults to :func:`get_default_config_path`.

    Returns:
        Path: The file that was written.

    Example:
        >>> save_config(SylveConfig(), Path("/tmp/sylve.yaml")).name
        'sylve.yaml'
    """
    cfg_path = path or get_default_config_path()
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(cfg_path.parent, stat.S_IRWXU)
    except OSError:
        pass

    payload = {
        "current_context": config.current_context,
        "contexts": {name: asdict(ctx) for name, ctx in config.contexts.items()},
    }
    serialized = yaml.safe_dump(payload, sort_keys=False)

    # Write with restrictive permissions (0600) since it holds the bearer token
    fd = os.open(
        str(cfg_path),
        os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
        stat.S_IRUSR | stat.S_IWUSR,
    )
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(serialized)
    try:
        os.chmod(cfg_path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
    return cfg_path
