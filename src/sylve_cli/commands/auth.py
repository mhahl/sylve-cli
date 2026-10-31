"""Authentication (login, logout, whoami) and context management commands."""

from __future__ import annotations

from typing import Annotated, Any
from urllib.parse import urlparse

import typer
import yaml

from sylve_cli.client import ResourceNotFoundError, SylveClient, SylveError
from sylve_cli.config import (
    ContextConfig,
    decode_jwt_payload,
    extract_token_expiry,
    get_default_config_path,
    load_config,
    normalize_server_url,
    save_config,
)
from sylve_cli.formatter import (
    ColumnSpec,
    OutputFormat,
    console,
    print_dict,
    print_list,
)
from sylve_cli.state import CLIState, ColumnsOption, FormatOption

config_app = typer.Typer(
    name="config",
    help="Manage Sylve CLI configuration contexts.",
    no_args_is_help=True,
    rich_markup_mode=None,
)


def _derive_context_name(server_url: str, username: str) -> str:
    parsed = urlparse(server_url)
    host = parsed.hostname or server_url
    return f"{username}@{host}" if username else host


def login_command(
    ctx: typer.Context,
    server: Annotated[
        str | None,
        typer.Argument(
            help="Sylve server URL (e.g. https://sylve.lan:8181). Uses active context URL if omitted."
        ),
    ] = None,
    username: Annotated[
        str | None,
        typer.Option("-u", "--username", help="Username for authentication."),
    ] = None,
    password: Annotated[
        str | None,
        typer.Option("-p", "--password", help="Password for authentication."),
    ] = None,
    token: Annotated[
        str | None,
        typer.Option("--token", help="Authenticate directly using an existing Bearer JWT token."),
    ] = None,
    auth_type: Annotated[
        str,
        typer.Option("--auth-type", help="Authentication realm: 'sylve' or 'pam'."),
    ] = "sylve",
    remember: Annotated[
        bool,
        typer.Option("--remember/--no-remember", help="Request a 7-day token instead of 24-hour."),
    ] = True,
    insecure: Annotated[
        bool,
        typer.Option(
            "-k",
            "--insecure-skip-tls-verify",
            help="Skip TLS certificate verification.",
        ),
    ] = False,
    ca_cert: Annotated[
        str | None,
        typer.Option("--ca-cert", help="Path to custom CA certificate bundle."),
    ] = None,
    context_name: Annotated[
        str | None,
        typer.Option("--context-name", help="Context name to save in config."),
    ] = None,
    default_node: Annotated[
        str | None,
        typer.Option("--default-node", help="Default cluster node hostname for this context."),
    ] = None,
) -> None:
    """Log in to a Sylve server or cluster and save the session token until it expires."""
    state: CLIState = ctx.obj
    cfg = load_config(state.config_path)

    existing_ctx: ContextConfig | None = None
    if cfg.current_context and cfg.current_context in cfg.contexts:
        existing_ctx = cfg.contexts[cfg.current_context]

    raw_server = server or (existing_ctx.server if existing_ctx else None)
    if not raw_server:
        raw_server = typer.prompt("Server URL (e.g. https://sylve.lan:8181)")
    norm_server = normalize_server_url(str(raw_server))

    verify_ssl = not (insecure or state.insecure)

    if token:
        claims = decode_jwt_payload(token).get("custom_claims") or {}
        resolved_user = username or str(claims.get("username") or "token-user")
        resolved_auth = str(claims.get("auth_type") or auth_type)
        temp_ctx = ContextConfig(
            server=norm_server,
            username=resolved_user,
            auth_type=resolved_auth,
            token=token.strip(),
            expires_at=extract_token_expiry(token.strip()),
            verify_ssl=verify_ssl,
            ca_cert=ca_cert,
            default_node=default_node,
        )
        with SylveClient(temp_ctx, timeout=state.timeout) as client:
            try:
                node_info = client.get("/info/node")
                if isinstance(node_info, dict) and node_info.get("hostname"):
                    temp_ctx.hostname = str(node_info["hostname"])
            except SylveError:
                pass
        updated_ctx = temp_ctx
    else:
        resolved_user = str(username or (existing_ctx.username if existing_ctx else "")).strip()
        if not resolved_user:
            resolved_user = typer.prompt("Username")
        resolved_pass = str(password or "").strip()
        if not resolved_pass:
            resolved_pass = typer.prompt("Password", hide_input=True)

        temp_ctx = ContextConfig(
            server=norm_server,
            username=resolved_user,
            auth_type=auth_type.strip().lower(),
            verify_ssl=verify_ssl,
            ca_cert=ca_cert,
            default_node=default_node,
        )
        with SylveClient(temp_ctx, timeout=state.timeout) as client:
            updated_ctx = client.login(
                username=resolved_user,
                password=resolved_pass,
                auth_type=auth_type.strip().lower(),
                remember=remember,
            )

    target_ctx_name = (
        context_name
        or state.context_name
        or _derive_context_name(norm_server, updated_ctx.username)
    )
    cfg.contexts[target_ctx_name] = updated_ctx
    cfg.current_context = target_ctx_name
    saved_path = save_config(cfg, state.config_path)

    console.print(
        f"[green]Login successful![/green] Logged into [bold]{norm_server}[/bold] "
        f"as [bold]{updated_ctx.username}[/bold] ({updated_ctx.auth_type})."
    )
    if updated_ctx.hostname:
        console.print(
            f"Connected node: [cyan]{updated_ctx.hostname}[/cyan] ({updated_ctx.node_id or 'local'})"
        )
    if updated_ctx.expires_at:
        console.print(
            f"Session token valid until [bold]{updated_ctx.expires_at}[/bold] "
            f"({updated_ctx.format_remaining()} remaining)."
        )
    console.print(f"Context [bold]{target_ctx_name}[/bold] saved to {saved_path}.")


def logout_command(ctx: typer.Context) -> None:
    """Revoke the current JWT session token and clear it from the configuration file."""
    state: CLIState = ctx.obj
    cfg = load_config(state.config_path)
    ctx_name, active_ctx = cfg.get_active_context(state.context_name)

    with SylveClient(active_ctx, timeout=state.timeout) as client:
        client.logout()

    if ctx_name in cfg.contexts:
        cfg.contexts[ctx_name].token = ""
        cfg.contexts[ctx_name].expires_at = None
        save_config(cfg, state.config_path)

    console.print(
        f"[green]Logged out[/green] of context [bold]{ctx_name}[/bold] ({active_ctx.server})."
    )


def whoami_command(
    ctx: typer.Context,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
) -> None:
    """Display current user identity, active context, server endpoint, and token expiration."""
    state: CLIState = ctx.obj
    cfg = load_config(state.config_path)
    ctx_name, active_ctx = cfg.get_active_context(state.context_name)

    payload = decode_jwt_payload(active_ctx.token)
    custom: dict[str, Any] = (
        payload["custom_claims"] if isinstance(payload.get("custom_claims"), dict) else {}
    )

    info: dict[str, object] = {
        "context": ctx_name,
        "server": active_ctx.server,
        "username": active_ctx.username or custom.get("username") or "",
        "user_id": custom.get("user_id") or custom.get("userId") or "",
        "auth_type": active_ctx.auth_type or custom.get("auth_type") or "",
        "hostname": active_ctx.hostname,
        "node_id": active_ctx.node_id,
        "default_node": active_ctx.default_node or "(all/origin)",
        "verify_ssl": active_ctx.verify_ssl,
        "expires_at": active_ctx.expires_at or extract_token_expiry(active_ctx.token) or "unknown",
        "token_status": "EXPIRED"
        if active_ctx.is_token_expired()
        else f"VALID ({active_ctx.format_remaining()} remaining)",
    }

    if fmt == OutputFormat.value and not columns:
        console.print(str(info["username"]))
        return

    print_dict(info, fmt=fmt, selected_columns=columns, title="Current Session")


@config_app.command("view")
def config_view(
    ctx: typer.Context,
    redact: Annotated[
        bool,
        typer.Option("--redact/--show-token", help="Redact bearer tokens in output."),
    ] = True,
    fmt: FormatOption = OutputFormat.yaml,
) -> None:
    """Display the current CLI configuration."""
    state: CLIState = ctx.obj
    cfg = load_config(state.config_path)
    data: dict[str, Any] = {
        "config_file": str(state.config_path or get_default_config_path()),
        "current_context": cfg.current_context,
        "contexts": {},
    }
    for name, c in cfg.contexts.items():
        tok = c.token
        if redact and tok:
            tok = f"{tok[:10]}...REDACTED" if len(tok) > 12 else "REDACTED"
        data["contexts"][name] = {
            "server": c.server,
            "username": c.username,
            "auth_type": c.auth_type,
            "hostname": c.hostname,
            "node_id": c.node_id,
            "default_node": c.default_node,
            "verify_ssl": c.verify_ssl,
            "ca_cert": c.ca_cert,
            "expires_at": c.expires_at,
            "token": tok,
        }
    print_dict(data, fmt=fmt, title="Sylve CLI Configuration")


@config_app.command("get-contexts")
def config_get_contexts(
    ctx: typer.Context,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
) -> None:
    """List all saved login contexts."""
    state: CLIState = ctx.obj
    cfg = load_config(state.config_path)
    rows = []
    for name, c in cfg.contexts.items():
        rows.append(
            {
                "current": "*" if name == cfg.current_context else "",
                "name": name,
                "server": c.server,
                "username": c.username,
                "auth_type": c.auth_type,
                "hostname": c.hostname,
                "default_node": c.default_node or "",
                "status": "EXPIRED" if c.is_token_expired() else f"ACTIVE ({c.format_remaining()})",
            }
        )
    spec = [
        ColumnSpec("Current", "current", justify="center"),
        ColumnSpec("Name", "name"),
        ColumnSpec("Server", "server"),
        ColumnSpec("Username", "username"),
        ColumnSpec("Auth", "auth_type"),
        ColumnSpec("Node", "hostname"),
        ColumnSpec("Default Node", "default_node"),
        ColumnSpec("Status", "status"),
    ]
    print_list(rows, spec, fmt=fmt, selected_columns=columns, title="Contexts")


@config_app.command("use-context")
def config_use_context(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Context name to activate.")],
) -> None:
    """Switch the active CLI context."""
    state: CLIState = ctx.obj
    cfg = load_config(state.config_path)
    if name not in cfg.contexts:
        raise ResourceNotFoundError(
            f"Context '{name}' does not exist. Available: {', '.join(cfg.contexts.keys())}"
        )
    cfg.current_context = name
    save_config(cfg, state.config_path)
    console.print(f"Switched to context [bold cyan]{name}[/bold cyan].")


@config_app.command("set-node")
def config_set_node(
    ctx: typer.Context,
    node: Annotated[
        str | None,
        typer.Argument(help="Default node hostname (or 'all' / empty to clear)."),
    ] = None,
) -> None:
    """Set or clear the default target cluster node for the active context."""
    state: CLIState = ctx.obj
    cfg = load_config(state.config_path)
    ctx_name, _ = cfg.get_active_context(state.context_name)
    if ctx_name not in cfg.contexts:
        raise ResourceNotFoundError(f"Context '{ctx_name}' is not persisted in config file.")
    cleaned = None if not node or node.strip().lower() in ("all", "none", "-") else node.strip()
    cfg.contexts[ctx_name].default_node = cleaned
    save_config(cfg, state.config_path)
    if cleaned:
        console.print(
            f"Default node for context [bold]{ctx_name}[/bold] set to [cyan]{cleaned}[/cyan]."
        )
    else:
        console.print(
            f"Cleared default node for context [bold]{ctx_name}[/bold] (operating cluster-wide)."
        )


@config_app.command("validate")
def config_validate(ctx: typer.Context) -> None:
    """Check the configuration file for parse errors and unusable contexts."""
    state: CLIState = ctx.obj
    path = state.config_path or get_default_config_path()
    problems: list[str] = []

    if not path.exists():
        console.print(f"[yellow]No configuration file at {path}.[/yellow]")
        raise SystemExit(1)

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        raise RuntimeError(f"Failed to parse configuration file {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise RuntimeError(f"{path} does not contain a YAML mapping.")

    raw_contexts = raw.get("contexts") or {}
    if not isinstance(raw_contexts, dict):
        raise RuntimeError("The 'contexts' key must be a mapping of name to context.")
    for name, cdata in raw_contexts.items():
        if not isinstance(cdata, dict) or not cdata.get("server"):
            # load_config silently drops these, so surface them here instead.
            problems.append(f"context '{name}': missing 'server' key (ignored by the CLI)")
    current = str(raw.get("current_context") or "")
    if current and current not in raw_contexts:
        problems.append(f"current_context '{current}' does not exist in 'contexts'")

    cfg = load_config(state.config_path)
    for name, c in cfg.contexts.items():
        if c.is_token_expired():
            problems.append(f"context '{name}': token expired (run 'sylve login')")
        if not c.token:
            problems.append(f"context '{name}': no token (run 'sylve login')")

    for problem in problems:
        console.print(f"[yellow]warning:[/yellow] {problem}")
    console.print(f"Checked {len(cfg.contexts)} context(s) in {path}.")
    if problems:
        raise SystemExit(1)
    console.print("[green]Configuration is valid.[/green]")


@config_app.command("delete-context")
def config_delete_context(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Context name to remove.")],
) -> None:
    """Delete a saved context from the configuration file."""
    state: CLIState = ctx.obj
    cfg = load_config(state.config_path)
    if name not in cfg.contexts:
        raise ResourceNotFoundError(f"Context '{name}' not found.")
    del cfg.contexts[name]
    if cfg.current_context == name:
        cfg.current_context = next(iter(cfg.contexts.keys()), "")
    save_config(cfg, state.config_path)
    console.print(f"Deleted context [bold]{name}[/bold].")
