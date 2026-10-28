"""Main entry point for the Sylve CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from sylve_cli import __version__
from sylve_cli.client import SylveError
from sylve_cli.commands.auth import config_app, login_command, logout_command, whoami_command
from sylve_cli.commands.backup import backup_app
from sylve_cli.commands.cluster import cluster_app
from sylve_cli.commands.download import download_app
from sylve_cli.commands.extras import (
    auth_app,
    cloud_init_app,
    ddns_app,
    group_app,
    iscsi_app,
    mdns_app,
    notifications_app,
    samba_app,
    system_app,
    user_app,
)
from sylve_cli.commands.jail import jail_app
from sylve_cli.commands.network import network_app
from sylve_cli.commands.node import node_app
from sylve_cli.commands.replication import replication_app
from sylve_cli.commands.task import task_app
from sylve_cli.commands.vm import vm_app
from sylve_cli.commands.zfs import zfs_app
from sylve_cli.formatter import FormatterError, configure_table, err_console
from sylve_cli.state import CLIState

app = typer.Typer(
    name="sylve",
    help=(
        "CLI for Sylve FreeBSD clusters: query and manage VMs, Jails, "
        "Networks, ZFS, Downloads, Backups, HA Replication, and Node Draining."
    ),
    no_args_is_help=True,
    rich_markup_mode=None,
    context_settings={"help_option_names": ["-h", "--help"]},
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"sylve-cli {__version__}")
        raise typer.Exit()


@app.callback()
def main_callback(
    ctx: typer.Context,
    config: Annotated[
        Path | None,
        typer.Option(
            "--config",
            envvar="SYLVE_CONFIG",
            help="Path to Sylve CLI config file (defaults to ~/.config/sylve/config.yaml).",
        ),
    ] = None,
    context: Annotated[
        str | None,
        typer.Option(
            "--context",
            envvar="SYLVE_CONTEXT",
            help="Named configuration context to use.",
        ),
    ] = None,
    node: Annotated[
        str | None,
        typer.Option(
            "-n",
            "--node",
            envvar="SYLVE_NODE",
            help="Target cluster node hostname or UUID.",
        ),
    ] = None,
    insecure: Annotated[
        bool,
        typer.Option(
            "-k",
            "--insecure",
            envvar="SYLVE_INSECURE",
            help="Skip TLS certificate verification.",
        ),
    ] = False,
    timeout: Annotated[
        float,
        typer.Option(
            "--timeout",
            help="HTTP request timeout in seconds.",
        ),
    ] = 30.0,
    max_width: Annotated[
        int | None,
        typer.Option(
            "--max-width",
            min=1,
            help="Maximum table width in columns (default: terminal width).",
        ),
    ] = None,
    no_truncate: Annotated[
        bool,
        typer.Option(
            "--no-truncate",
            help="Wrap long table cells instead of truncating them.",
        ),
    ] = False,
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            "-V",
            callback=_version_callback,
            is_eager=True,
            help="Show sylve-cli version and exit.",
        ),
    ] = None,
) -> None:
    """Global options for Sylve CLI."""
    configure_table(max_width=max_width, no_truncate=no_truncate)
    ctx.obj = CLIState(
        config_path=config,
        context_name=context,
        node=node,
        insecure=insecure,
        timeout=timeout,
    )


# Top-level authentication & session commands
app.command("login")(login_command)
app.command("logout")(logout_command)
app.command("whoami")(whoami_command)
app.add_typer(config_app, name="config")

# Resource noun command groups
app.add_typer(cluster_app, name="cluster")
app.add_typer(node_app, name="node")
app.add_typer(vm_app, name="vm")
app.add_typer(vm_app, name="server", hidden=True)
app.add_typer(jail_app, name="jail")
app.add_typer(network_app, name="network")
app.add_typer(download_app, name="download")
app.add_typer(replication_app, name="replication")
app.add_typer(backup_app, name="backup")
app.add_typer(zfs_app, name="zfs")
app.add_typer(task_app, name="task")
app.add_typer(system_app, name="system")
app.add_typer(samba_app, name="samba")
app.add_typer(iscsi_app, name="iscsi")
app.add_typer(ddns_app, name="ddns")
app.add_typer(mdns_app, name="mdns")
app.add_typer(notifications_app, name="notifications")
app.add_typer(user_app, name="user")
app.add_typer(group_app, name="group")
app.add_typer(auth_app, name="auth")
app.add_typer(cloud_init_app, name="cloud-init")


def run() -> None:
    """Console script entry point with clean error reporting."""
    try:
        app()
    except (FormatterError, SylveError) as exc:
        err_console.print(f"[bold red]Error:[/bold red] {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    run()
