"""Fixtures for live tests against a real Sylve system."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from sylve_cli.client import SylveClient, SylveError
from sylve_cli.config import ContextConfig, normalize_server_url
from sylve_cli.main import app
from tests.live.openapi import OpenAPISpec

ROOT = Path(__file__).resolve().parents[2]


def _truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


@pytest.fixture(scope="session")
def live_settings() -> dict[str, str]:
    """Return live connection settings or skip the live suite."""
    if not _truthy("SYLVE_LIVE"):
        pytest.skip("live tests are disabled; set SYLVE_LIVE=1")
    server = os.environ.get("SYLVE_SERVER", "")
    token = os.environ.get("SYLVE_TOKEN", "")
    if not server or not token:
        pytest.skip("live tests need SYLVE_SERVER and SYLVE_TOKEN")
    return {
        "server": server,
        "token": token,
        "node": os.environ.get("SYLVE_NODE", ""),
        "insecure": os.environ.get("SYLVE_INSECURE", ""),
    }


@pytest.fixture(scope="session")
def openapi_spec() -> OpenAPISpec:
    """Load the swagger document used for response validation."""
    path = Path(os.environ.get("SYLVE_SWAGGER", ROOT / "docs" / "swagger.json")).expanduser()
    if not path.exists():
        pytest.skip(f"OpenAPI spec not found: {path}")
    return OpenAPISpec(path)


@pytest.fixture(scope="session")
def validate_api_calls(openapi_spec: OpenAPISpec) -> Any:
    """Validate every response made through SylveClient during the test session."""
    monkeypatch = pytest.MonkeyPatch()
    original = SylveClient.request

    def wrapped(self: SylveClient, method: str, path: str, *args: Any, **kwargs: Any) -> Any:
        result = original(self, method, path, *args, **kwargs)
        openapi_spec.validate(method, path, result)
        return result

    monkeypatch.setattr(SylveClient, "request", wrapped)
    try:
        yield
    finally:
        monkeypatch.undo()


@pytest.fixture(scope="session")
def live_client(
    live_settings: dict[str, str],
    validate_api_calls: Any,
) -> SylveClient:
    """Return a direct client for the live target."""
    context = ContextConfig(
        server=normalize_server_url(live_settings["server"]),
        token=live_settings["token"],
        verify_ssl=not _truthy("SYLVE_INSECURE"),
        default_node=live_settings["node"] or None,
    )
    client = SylveClient(context, node_override=live_settings["node"] or None)
    if client.context.is_token_expired():
        pytest.fail("SYLVE_TOKEN is expired")
    try:
        yield client
    finally:
        client.close()


def _first(items: Any) -> dict[str, Any] | None:
    if isinstance(items, list) and items and isinstance(items[0], dict):
        return items[0]
    return None


def _safe_get(client: SylveClient, path: str) -> Any:
    try:
        return client.get(path)
    except SylveError:
        return []


@pytest.fixture(scope="session")
def live_state(live_client: SylveClient) -> dict[str, Any]:
    """Collect optional IDs and names used by read-only live commands."""
    nodes = _safe_get(live_client, "/cluster/nodes")
    vms = _safe_get(live_client, "/vm/simple")
    jails = _safe_get(live_client, "/jail/simple")
    vm_templates = _safe_get(live_client, "/vm/templates")
    jail_templates = _safe_get(live_client, "/jail/templates")
    pools = _safe_get(live_client, "/zfs/pools")
    switches = _safe_get(live_client, "/network/switch")
    downloads = _safe_get(live_client, "/utilities/downloads")
    targets = _safe_get(live_client, "/cluster/backups/targets")
    jobs = _safe_get(live_client, "/cluster/backups/jobs")
    tasks = _safe_get(live_client, "/tasks/lifecycle/recent")
    users = _safe_get(live_client, "/auth/users")
    notes = _safe_get(live_client, "/cluster/notes")

    node = _first(nodes)
    vm = _first(vms)
    jail = _first(jails)
    vm_template = _first(vm_templates)
    jail_template = _first(jail_templates)
    pool = _first(pools)
    download = _first(downloads)
    target = _first(targets)
    job = _first(jobs)
    task = _first(tasks)
    user = _first(users)
    note = _first(notes)

    switch_name = None
    if isinstance(switches, dict):
        for group in ("standard", "manual"):
            for item in switches.get(group) or []:
                if isinstance(item, dict) and item.get("name"):
                    switch_name = item["name"]
                    break
            if switch_name:
                break

    return {
        "node": node.get("hostname") if node else None,
        "vm": vm.get("rid") if vm else None,
        "jail": jail.get("ctId") if jail else None,
        "vm_template": vm_template.get("id") if vm_template else None,
        "jail_template": jail_template.get("id") if jail_template else None,
        "pool": pool.get("name") if pool else None,
        "switch": switch_name,
        "download": (download.get("uuid") or download.get("id")) if download else None,
        "backup_target": target.get("id") if target else None,
        "backup_job": job.get("id") if job else None,
        "task": task.get("id") if task else None,
        "user": user.get("id") if user else None,
        "note": note.get("id") if note else None,
    }


@pytest.fixture()
def run_cli(live_settings: dict[str, str]) -> Any:
    """Return a CLI runner bound to the live environment."""
    runner = CliRunner()
    env = {
        "SYLVE_CONFIG": "/dev/null",
        "SYLVE_SERVER": live_settings["server"],
        "SYLVE_TOKEN": live_settings["token"],
        "SYLVE_NODE": live_settings["node"],
        "SYLVE_INSECURE": live_settings["insecure"],
        "COLUMNS": "120",
    }

    def run(args: list[str]) -> Any:
        return runner.invoke(app, args, env=env)

    return run


@pytest.fixture()
def mutate_target(live_settings: dict[str, str]) -> dict[str, str]:
    """Return an explicit node/pool for mutating tests, or skip.

    Mutating tests only run when SYLVE_LIVE_MUTATE=1 and a target node plus
    pool are supplied, so they can never touch production by accident.
    """
    if not _truthy("SYLVE_LIVE_MUTATE"):
        pytest.skip("live mutation disabled; set SYLVE_LIVE_MUTATE=1")
    node = os.environ.get("SYLVE_NODE", "").strip()
    pool = os.environ.get("SYLVE_LIVE_POOL", "").strip()
    if not node or not pool:
        pytest.skip("live mutation needs SYLVE_NODE and SYLVE_LIVE_POOL")
    return {"node": node, "pool": pool}


@pytest.fixture()
def migrate_target(live_settings: dict[str, str], mutate_target: dict[str, str]) -> dict[str, str]:
    """Return a node *other than* the create/run node, for migration tests.

    Requires an explicit SYLVE_LIVE_MIGRATE_TARGET so a migration can never run
    against an accidentally-chosen node.
    """
    target = os.environ.get("SYLVE_LIVE_MIGRATE_TARGET", "").strip()
    if not target:
        pytest.skip("live migration needs SYLVE_LIVE_MIGRATE_TARGET")
    if target == mutate_target["node"]:
        pytest.skip("SYLVE_LIVE_MIGRATE_TARGET must differ from SYLVE_NODE")
    return {"node": target}


@pytest.fixture()
def jail_target(mutate_target: dict[str, str]) -> dict[str, str]:
    """Return node/pool/bootstrap/switch for jail mutation tests, or skip.

    Jails need an existing pkgbase bootstrap on their create node, so this is a
    separate, explicit opt-in from VM mutation.
    """
    node = os.environ.get("SYLVE_LIVE_JAIL_NODE", "").strip()
    bootstrap = os.environ.get("SYLVE_LIVE_JAIL_BOOTSTRAP", "").strip()
    switch = os.environ.get("SYLVE_LIVE_JAIL_SWITCH", "").strip()
    if not (node and bootstrap and switch):
        pytest.skip("jail mutation needs SYLVE_LIVE_JAIL_NODE, _BOOTSTRAP, _SWITCH")
    return {
        "node": node,
        "pool": os.environ.get("SYLVE_LIVE_JAIL_POOL") or mutate_target["pool"],
        "bootstrap": bootstrap,
        "switch": switch,
    }
