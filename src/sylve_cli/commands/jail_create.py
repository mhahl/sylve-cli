"""Create FreeBSD jails from typed flags or a YAML/JSON file.

This mirrors ``vm create``: flags and ``--file`` build the request, sizes like
``2G`` are parsed to bytes, names are resolved against the server, and
``--dry-run`` prints the payload without creating anything. ``--property KEY=VALUE``
covers the remaining API fields (for example ``hooks``) without raw JSON.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Annotated, Any

import typer
import yaml

from sylve_cli.client import SylveAPIError, SylveClient, SylveError
from sylve_cli.commands.vm_create import (
    _as_bool,
    _as_int,
    _load_config,
    _next_guest_id,
    _parse_size,
    _resolve_host,
    _resolve_mac_id,
    _resolve_pool,
    _resolve_switch,
)
from sylve_cli.formatter import OutputFormat, console, format_bytes, print_result
from sylve_cli.state import CLIState, FormatOption, NodeOption, WaitOption
from sylve_cli.tasks import wait_for_lifecycle_task

_JAIL_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]+$")
_JAIL_TYPES = {"freebsd", "linux"}
_ZFS_SOURCE_MODES = {"copy", "rename"}

_API_KEYS = {
    "name",
    "ctId",
    "pool",
    "type",
    "bootstrapName",
    "base",
    "cores",
    "memory",
    "resourceLimits",
    "description",
    "hostname",
    "switchName",
    "dhcp",
    "slaac",
    "inheritIPv4",
    "inheritIPv6",
    "ipv4Raw",
    "ipv4GwRaw",
    "ipv6Raw",
    "ipv6GwRaw",
    "macRaw",
    "mac",
    "devfsRuleset",
    "fstab",
    "resolvConf",
    "additionalOptions",
    "allowedOptions",
    "metadataEnv",
    "metadataMeta",
    "cleanEnvironment",
    "startAtBoot",
    "startOrder",
}

_ALIASES = {
    "ctid": "ctId",
    "ct_id": "ctId",
    "bootstrap": "bootstrapName",
    "bootstrap_name": "bootstrapName",
    "resource_limits": "resourceLimits",
    "switch": "switchName",
    "switch_name": "switchName",
    "ipv4": "ipv4Raw",
    "ipv4_gw": "ipv4GwRaw",
    "ipv4gw": "ipv4GwRaw",
    "ipv6": "ipv6Raw",
    "ipv6_gw": "ipv6GwRaw",
    "ipv6gw": "ipv6GwRaw",
    "mac_object": "mac",
    "mac_id": "mac",
    "inherit_ipv4": "inheritIPv4",
    "inherit_ipv6": "inheritIPv6",
    "devfs_ruleset": "devfsRuleset",
    "resolv_conf": "resolvConf",
    "additional_options": "additionalOptions",
    "allowed_options": "allowedOptions",
    "metadata_env": "metadataEnv",
    "metadata_meta": "metadataMeta",
    "clean_environment": "cleanEnvironment",
    "start_at_boot": "startAtBoot",
    "start_order": "startOrder",
    "ram": "memory",
}


def _config_to_payload(cfg: dict[str, Any]) -> dict[str, Any]:
    """Flatten a file config with flat keys and grouped sections."""
    payload: dict[str, Any] = {}
    for key in _API_KEYS:
        if key in cfg and cfg[key] is not None:
            payload[key] = cfg[key]
    for source, target in _ALIASES.items():
        if source in cfg and cfg[source] is not None and target not in payload:
            payload[target] = cfg[source]

    cpu = cfg.get("cpu")
    if isinstance(cpu, dict):
        if "cores" in cpu:
            payload["cores"] = cpu["cores"]
        if "memory" in cpu:
            payload["memory"] = cpu["memory"]

    network = cfg.get("network")
    if isinstance(network, dict):
        for source, target in {
            "switch": "switchName",
            "switch_name": "switchName",
            "dhcp": "dhcp",
            "slaac": "slaac",
            "inherit_ipv4": "inheritIPv4",
            "inherit_ipv6": "inheritIPv6",
            "ipv4": "ipv4Raw",
            "ipv4_gw": "ipv4GwRaw",
            "ipv6": "ipv6Raw",
            "ipv6_gw": "ipv6GwRaw",
            "mac": "macRaw",
            "mac_object": "mac",
            "mac_id": "mac",
            "hostname": "hostname",
        }.items():
            if source in network and network[source] is not None:
                payload[target] = network[source]

    boot = cfg.get("boot")
    if isinstance(boot, dict):
        if "start_at_boot" in boot:
            payload["startAtBoot"] = boot["start_at_boot"]
        if "start_order" in boot:
            payload["startOrder"] = boot["start_order"]

    options = cfg.get("options")
    if isinstance(options, dict):
        for source, target in {
            "devfs_ruleset": "devfsRuleset",
            "fstab": "fstab",
            "resolv_conf": "resolvConf",
            "additional_options": "additionalOptions",
            "allowed_options": "allowedOptions",
            "metadata_env": "metadataEnv",
            "metadata_meta": "metadataMeta",
            "clean_environment": "cleanEnvironment",
            "resource_limits": "resourceLimits",
            "description": "description",
        }.items():
            if source in options and options[source] is not None:
                payload[target] = options[source]

    for group_key, target_key in (("zfs_source", "zfsSource"), ("zfsSource", "zfsSource")):
        group = cfg.get(group_key)
        if isinstance(group, dict) and target_key not in payload:
            payload[target_key] = dict(group)
    for group_key, target_key in (("vlan_policy", "vlanPolicy"), ("vlanPolicy", "vlanPolicy")):
        group = cfg.get(group_key)
        if isinstance(group, dict) and target_key not in payload:
            payload[target_key] = dict(group)
    hooks = cfg.get("hooks")
    if isinstance(hooks, dict) and "hooks" not in payload:
        payload["hooks"] = dict(hooks)
    return payload


def _apply_set_overrides(payload: dict[str, Any], values: list[str] | None) -> None:
    """Deep-merge ``--property KEY=VALUE`` overrides so exotic fields need no JSON."""
    from sylve_cli.commands.extras import _parse_set

    def _merge(target: dict[str, Any], overrides: dict[str, Any]) -> None:
        for key, value in overrides.items():
            if isinstance(value, dict) and isinstance(target.get(key), dict):
                _merge(target[key], value)
            else:
                target[key] = value

    _merge(payload, _parse_set(values))


def _installed_bootstraps(client: SylveClient, host: str, pool: str) -> tuple[list[str], bool]:
    """Return ``(installed_names, has_catalog_entries)`` for ``pool`` on ``host``."""
    try:
        entries = client.get("/jail/bootstraps", params={"pool": pool}, node=host)
    except SylveError:
        return [], False
    if not isinstance(entries, list):
        return [], False
    installed = [
        str(entry["name"])
        for entry in entries
        if isinstance(entry, dict) and entry.get("name") and entry.get("exists", True) is not False
    ]
    return installed, bool(entries)


def _resolve_bootstrap(client: SylveClient, host: str, pool: str, requested: Any) -> str:
    """Resolve a bootstrap name against the pool's installed bootstraps."""
    wanted = str(requested).strip()
    names, _ = _installed_bootstraps(client, host, pool)
    for name in names:
        if name.lower() == wanted.lower():
            return name
    available = ", ".join(names) if names else "none"
    raise SylveError(
        f"Jail bootstrap '{requested}' not found in pool '{pool}' on '{host}'. "
        f"Available: {available}."
    )


def _normalize_payload(client: SylveClient, host: str, payload: dict[str, Any]) -> dict[str, Any]:
    name = str(payload.get("name") or "").strip()
    if not name:
        raise SylveError("Jail name is required. Pass it as NAME or --name.")
    if not _JAIL_NAME_RE.fullmatch(name):
        raise SylveError("Jail names may contain only letters, numbers, '-' and '_'.")
    payload["name"] = name

    ctid = payload.get("ctId", payload.get("ctid"))
    if ctid in (None, "", 0, "0"):
        ctid = _next_guest_id(client)
    ctid = _as_int(ctid, "CTID")
    if not 1 <= ctid <= 9999:
        raise SylveError("CTID must be between 1 and 9999.")
    payload["ctId"] = ctid
    payload.pop("ctid", None)

    jail_type = str(payload.get("type") or "freebsd").strip().lower()
    if jail_type not in _JAIL_TYPES:
        raise SylveError("--type must be 'freebsd' or 'linux'.")
    payload["type"] = jail_type

    pool_name, _ = _resolve_pool(client, host, payload.get("pool"))
    payload["pool"] = pool_name

    if payload.get("base") is not None and not str(payload["base"]).strip():
        payload.pop("base", None)

    if payload.get("bootstrapName") not in (None, ""):
        payload["bootstrapName"] = _resolve_bootstrap(
            client, host, pool_name, payload["bootstrapName"]
        )
    else:
        payload.pop("bootstrapName", None)
        if not payload.get("base") and not payload.get("zfsSource"):
            installed, has_catalog = _installed_bootstraps(client, host, pool_name)
            if len(installed) == 1:
                payload["bootstrapName"] = installed[0]
            elif len(installed) > 1:
                raise SylveError(
                    f"Pool '{pool_name}' on '{host}' has multiple installed bootstraps "
                    f"({', '.join(installed)}). Pass --bootstrap NAME."
                )
            elif has_catalog:
                raise SylveError(
                    f"No jail bootstrap is installed in pool '{pool_name}' on '{host}'. "
                    f"Run 'sylve jail bootstrap create --pool {pool_name} --major 15 --minor 1' "
                    "or pass --base / --zfs-source-dataset."
                )

    if payload.get("cores") not in (None, ""):
        cores = _as_int(payload["cores"], "cores")
        if cores < 0:
            raise SylveError("cores must be 0 or greater.")
        payload["cores"] = cores
    else:
        payload.pop("cores", None)

    if payload.get("memory") not in (None, ""):
        raw_memory = payload["memory"]
        if isinstance(raw_memory, (int, float)) and int(raw_memory) == 0:
            payload["memory"] = 0
        elif isinstance(raw_memory, str) and raw_memory.strip() == "0":
            payload["memory"] = 0
        else:
            payload["memory"] = _parse_size(raw_memory, "memory")
    else:
        payload.pop("memory", None)

    for key in (
        "resourceLimits",
        "dhcp",
        "slaac",
        "inheritIPv4",
        "inheritIPv6",
        "cleanEnvironment",
        "startAtBoot",
    ):
        if payload.get(key) is not None:
            payload[key] = _as_bool(payload[key], key)

    description = str(payload.get("description") or "")
    if len(description) > 1024:
        raise SylveError("Description must be 1024 characters or fewer.")
    if description:
        payload["description"] = description
    else:
        payload.pop("description", None)

    if payload.get("hostname") is not None:
        hostname = str(payload["hostname"]).strip()
        if hostname:
            payload["hostname"] = hostname
        else:
            payload.pop("hostname", None)

    switch_name = payload.get("switchName")
    if switch_name is None or str(switch_name).strip().lower() in ("", "none"):
        payload.pop("switchName", None)
    else:
        payload["switchName"] = _resolve_switch(client, host, switch_name)

    if payload.get("mac") not in (None, "") and payload.get("macRaw") not in (None, ""):
        raise SylveError("Pass either --mac or --mac-object, not both.")
    if payload.get("mac") not in (None, ""):
        mac_id = _resolve_mac_id(client, host, payload["mac"])
        if mac_id is not None:
            payload["mac"] = mac_id
        else:
            payload.pop("mac", None)
    for key in ("ipv4Raw", "ipv4GwRaw", "ipv6Raw", "ipv6GwRaw", "macRaw"):
        if payload.get(key) is not None and not str(payload[key]).strip():
            payload.pop(key, None)

    vlan = payload.get("vlanPolicy")
    if vlan is not None and not isinstance(vlan, dict):
        raise SylveError("vlanPolicy must be an object.")
    if isinstance(vlan, dict):
        if vlan.get("untaggedVlan") not in (None, ""):
            vlan["untaggedVlan"] = _as_int(vlan["untaggedVlan"], "untaggedVlan")
        tagged = vlan.get("taggedVlans")
        if isinstance(tagged, str):
            tagged = [item.strip() for item in tagged.split(",") if item.strip()]
        if isinstance(tagged, list):
            vlan["taggedVlans"] = [_as_int(item, "taggedVlans") for item in tagged]
        if not vlan:
            payload.pop("vlanPolicy", None)

    if payload.get("startOrder") not in (None, ""):
        start_order = _as_int(payload["startOrder"], "startOrder")
        if start_order < 0:
            raise SylveError("startOrder must be 0 or greater.")
        payload["startOrder"] = start_order
    else:
        payload.pop("startOrder", None)

    zfs_source = payload.get("zfsSource")
    if zfs_source is not None and not isinstance(zfs_source, dict):
        raise SylveError("zfsSource must be an object.")
    if isinstance(zfs_source, dict):
        mode = str(zfs_source.get("mode") or "").strip().lower()
        if mode:
            if mode not in _ZFS_SOURCE_MODES:
                raise SylveError("--zfs-source-mode must be 'copy' or 'rename'.")
            zfs_source["mode"] = mode
        if not zfs_source:
            payload.pop("zfsSource", None)

    allowed = payload.get("allowedOptions")
    if isinstance(allowed, str):
        allowed = [item.strip() for item in allowed.split(",") if item.strip()]
    if isinstance(allowed, list):
        payload["allowedOptions"] = [str(item) for item in allowed if str(item).strip()]
    elif allowed is not None:
        raise SylveError("allowedOptions must be a list of strings.")

    for key in (
        "additionalOptions",
        "devfsRuleset",
        "fstab",
        "resolvConf",
        "metadataEnv",
        "metadataMeta",
    ):
        if payload.get(key) is not None and not str(payload[key]).strip():
            payload.pop(key, None)

    return {key: value for key, value in payload.items() if value is not None}


def _friendly_create_error(exc: SylveAPIError) -> str:
    combined = f"{exc.error_code} {str(exc)}".lower()
    mappings = (
        ("ctid_or_name_already_in_use", "CTID or jail name is already in use."),
        ("jail_name_already_in_use", "Jail name is already in use."),
        ("guest_id_already_in_use", "CTID is already used by another guest."),
        ("pool_not_found", "The selected storage pool was not found."),
        ("bootstrap_not_found", "The selected bootstrap was not found."),
        (
            "download_uuid_or_bootstrap_name_required",
            "A jail requires --bootstrap NAME, --base DOWNLOAD, or --zfs-source-dataset.",
        ),
        ("switch_not_found", "The selected network switch was not found."),
        ("invalid_ctid_range", "The jail CTID range is invalid."),
    )
    for code, message in mappings:
        if code in combined:
            return message
    return str(exc) or "Jail creation failed."


def _print_payload(payload: dict[str, Any], fmt: OutputFormat) -> None:
    if fmt == OutputFormat.yaml:
        sys.stdout.write(yaml.safe_dump(payload, sort_keys=False))
    elif fmt == OutputFormat.value:
        sys.stdout.write(json.dumps(payload, separators=(",", ":")) + "\n")
    else:
        sys.stdout.write(json.dumps(payload, indent=2) + "\n")


def _confirm(plan: list[str], title: str, yes: bool, fmt: OutputFormat) -> None:
    if yes or not sys.stdin.isatty() or fmt != OutputFormat.table:
        return
    console.print(title, style="bold")
    for line in plan:
        console.print(f"  {line}", markup=False)
    typer.confirm("Create the jail with this configuration?", abort=True)


def register_jail_create_commands(app: typer.Typer) -> None:
    @app.command("create")
    def jail_create(
        ctx: typer.Context,
        name: Annotated[
            str | None,
            typer.Argument(help="Name for the new jail. Omit to use the config default."),
        ] = None,
        name_option: Annotated[
            str | None,
            typer.Option("--name", help="Jail name (overrides the positional argument)."),
        ] = None,
        node: NodeOption = None,
        ctid: Annotated[
            int | None,
            typer.Option("--ctid", help="Jail CTID (1-9999). Defaults to the next free guest ID."),
        ] = None,
        pool: Annotated[
            str | None,
            typer.Option("--pool", "-p", help="ZFS pool for the jail root dataset."),
        ] = None,
        jail_type: Annotated[
            str | None,
            typer.Option("--type", "-t", help="Jail type: freebsd or linux."),
        ] = None,
        bootstrap: Annotated[
            str | None,
            typer.Option("--bootstrap", help="pkgbase bootstrap name (e.g. 15-1-Base)."),
        ] = None,
        base: Annotated[
            str | None,
            typer.Option("--base", help="Base release for the jail."),
        ] = None,
        cores: Annotated[
            int | None,
            typer.Option("--cores", help="CPU core limit."),
        ] = None,
        memory: Annotated[
            str | None,
            typer.Option("--memory", help="Memory limit, e.g. 2G or 512M."),
        ] = None,
        resource_limits: Annotated[
            bool | None,
            typer.Option("--resource-limits/--no-resource-limits", help="Enforce rctl limits."),
        ] = None,
        description: Annotated[
            str | None,
            typer.Option("--description", "-d", help="Jail description."),
        ] = None,
        hostname: Annotated[
            str | None,
            typer.Option("--hostname", help="Hostname inside the jail (defaults to the name)."),
        ] = None,
        switch: Annotated[
            str | None,
            typer.Option("--switch", help="Network switch name, or 'none'."),
        ] = None,
        dhcp: Annotated[
            bool | None,
            typer.Option("--dhcp/--no-dhcp", help="Configure addresses via DHCP."),
        ] = None,
        slaac: Annotated[
            bool | None,
            typer.Option("--slaac/--no-slaac", help="Configure IPv6 via SLAAC."),
        ] = None,
        inherit_ipv4: Annotated[
            bool | None,
            typer.Option("--inherit-ipv4/--no-inherit-ipv4", help="Inherit host IPv4."),
        ] = None,
        inherit_ipv6: Annotated[
            bool | None,
            typer.Option("--inherit-ipv6/--no-inherit-ipv6", help="Inherit host IPv6."),
        ] = None,
        ipv4: Annotated[
            str | None,
            typer.Option("--ipv4", help="Static IPv4 address, e.g. 10.0.10.21/24."),
        ] = None,
        ipv4_gw: Annotated[
            str | None,
            typer.Option("--ipv4-gw", help="IPv4 gateway."),
        ] = None,
        ipv6: Annotated[
            str | None,
            typer.Option("--ipv6", help="Static IPv6 address."),
        ] = None,
        ipv6_gw: Annotated[
            str | None,
            typer.Option("--ipv6-gw", help="IPv6 gateway."),
        ] = None,
        mac: Annotated[
            str | None,
            typer.Option("--mac", help="Static MAC address."),
        ] = None,
        mac_object: Annotated[
            str | None,
            typer.Option("--mac-object", help="Existing MAC object name or ID."),
        ] = None,
        vlan_mode: Annotated[
            str | None,
            typer.Option("--vlan-mode", help="VLAN policy mode for filtered switches."),
        ] = None,
        vlan_untagged: Annotated[
            int | None,
            typer.Option("--vlan-untagged", help="Untagged VLAN ID."),
        ] = None,
        vlan_tagged: Annotated[
            list[int] | None,
            typer.Option("--vlan-tagged", help="Tagged VLAN ID (repeatable)."),
        ] = None,
        start_at_boot: Annotated[
            bool | None,
            typer.Option("--start-at-boot/--no-start-at-boot"),
        ] = None,
        start_order: Annotated[
            int | None,
            typer.Option("--start-order", help="Autostart order."),
        ] = None,
        devfs_ruleset: Annotated[
            str | None,
            typer.Option("--devfs-ruleset", help="DevFS ruleset."),
        ] = None,
        fstab: Annotated[
            str | None,
            typer.Option("--fstab", help="fstab configuration."),
        ] = None,
        resolv_conf: Annotated[
            str | None,
            typer.Option("--resolv-conf", help="resolv.conf configuration."),
        ] = None,
        additional_options: Annotated[
            str | None,
            typer.Option("--additional-options", help="Additional jail.conf options."),
        ] = None,
        allowed_option: Annotated[
            list[str] | None,
            typer.Option("--allowed-option", help="Allowed jail option (repeatable)."),
        ] = None,
        metadata_env: Annotated[
            str | None,
            typer.Option("--metadata-env", help="Metadata environment."),
        ] = None,
        metadata_meta: Annotated[
            str | None,
            typer.Option("--metadata-meta", help="Metadata document."),
        ] = None,
        clean_environment: Annotated[
            bool | None,
            typer.Option("--clean-environment/--no-clean-environment"),
        ] = None,
        zfs_source_dataset: Annotated[
            str | None,
            typer.Option("--zfs-source-dataset", help="Clone from an existing ZFS dataset."),
        ] = None,
        zfs_source_guid: Annotated[
            str | None,
            typer.Option("--zfs-source-guid", help="Clone from a dataset GUID."),
        ] = None,
        zfs_source_mode: Annotated[
            str | None,
            typer.Option("--zfs-source-mode", help="Clone mode: copy or rename."),
        ] = None,
        config_file: Annotated[
            Path | None,
            typer.Option(
                "--file",
                exists=True,
                dir_okay=False,
                readable=True,
                help="YAML or JSON create configuration. Flags override file values.",
            ),
        ] = None,
        set_value: Annotated[
            list[str] | None,
            typer.Option(
                "--property",
                "-s",
                help="Set any other API field KEY=VALUE (repeatable, dotted keys nest).",
            ),
        ] = None,
        start: Annotated[
            bool,
            typer.Option("--start", help="Start the jail after creation."),
        ] = False,
        wait: WaitOption = True,
        dry_run: Annotated[
            bool,
            typer.Option("--dry-run", help="Print the API request without creating anything."),
        ] = False,
        yes: Annotated[
            bool,
            typer.Option("-y", "--yes", help="Skip confirmation."),
        ] = False,
        fmt: FormatOption = OutputFormat.table,
    ) -> None:
        """Create a FreeBSD jail from flags or a YAML/JSON file."""
        state: CLIState = ctx.obj
        cfg = _load_config(config_file) if config_file else {}
        if name_option is not None:
            name = name_option
        cfg_node = cfg.get("node") or cfg.get("host")
        if node is None and cfg_node is not None and str(cfg_node).strip():
            node = str(cfg_node).strip()

        with state.get_client(node_override=node) as client:
            host = _resolve_host(client, node)
            payload = _config_to_payload(cfg)
            if name is not None:
                payload["name"] = name
            if ctid is not None:
                payload["ctId"] = ctid
            if pool is not None:
                payload["pool"] = pool
            if jail_type is not None:
                payload["type"] = jail_type
            if bootstrap is not None:
                payload["bootstrapName"] = bootstrap
            if base is not None:
                payload["base"] = base
            if cores is not None:
                payload["cores"] = cores
            if memory is not None:
                payload["memory"] = memory
            if resource_limits is not None:
                payload["resourceLimits"] = resource_limits
            if description is not None:
                payload["description"] = description
            if hostname is not None:
                payload["hostname"] = hostname
            if switch is not None:
                payload["switchName"] = switch
            if dhcp is not None:
                payload["dhcp"] = dhcp
            if slaac is not None:
                payload["slaac"] = slaac
            if inherit_ipv4 is not None:
                payload["inheritIPv4"] = inherit_ipv4
            if inherit_ipv6 is not None:
                payload["inheritIPv6"] = inherit_ipv6
            if ipv4 is not None:
                payload["ipv4Raw"] = ipv4
            if ipv4_gw is not None:
                payload["ipv4GwRaw"] = ipv4_gw
            if ipv6 is not None:
                payload["ipv6Raw"] = ipv6
            if ipv6_gw is not None:
                payload["ipv6GwRaw"] = ipv6_gw
            if mac is not None:
                payload["macRaw"] = mac
            if mac_object is not None:
                payload["mac"] = mac_object
            if start_at_boot is not None:
                payload["startAtBoot"] = start_at_boot
            if start_order is not None:
                payload["startOrder"] = start_order
            if devfs_ruleset is not None:
                payload["devfsRuleset"] = devfs_ruleset
            if fstab is not None:
                payload["fstab"] = fstab
            if resolv_conf is not None:
                payload["resolvConf"] = resolv_conf
            if additional_options is not None:
                payload["additionalOptions"] = additional_options
            if allowed_option is not None:
                payload["allowedOptions"] = list(allowed_option)
            if metadata_env is not None:
                payload["metadataEnv"] = metadata_env
            if metadata_meta is not None:
                payload["metadataMeta"] = metadata_meta
            if clean_environment is not None:
                payload["cleanEnvironment"] = clean_environment
            zfs_source: dict[str, Any] = (
                dict(payload["zfsSource"]) if isinstance(payload.get("zfsSource"), dict) else {}
            )
            if zfs_source_dataset is not None:
                zfs_source["dataset"] = zfs_source_dataset
            if zfs_source_guid is not None:
                zfs_source["guid"] = zfs_source_guid
            if zfs_source_mode is not None:
                zfs_source["mode"] = zfs_source_mode
            if zfs_source:
                payload["zfsSource"] = zfs_source
            vlan: dict[str, Any] = (
                dict(payload["vlanPolicy"]) if isinstance(payload.get("vlanPolicy"), dict) else {}
            )
            if vlan_mode is not None:
                vlan["mode"] = vlan_mode
            if vlan_untagged is not None:
                vlan["untaggedVlan"] = vlan_untagged
            if vlan_tagged is not None:
                vlan["taggedVlans"] = list(vlan_tagged)
            if vlan:
                payload["vlanPolicy"] = vlan
            _apply_set_overrides(payload, set_value)

            request = _normalize_payload(client, host, payload)

            if dry_run:
                _print_payload(request, fmt)
                return

            plan = [
                f"Node: {host}",
                f"Name: {request['name']}",
                f"CTID: {request['ctId']}",
                f"Type: {request['type']}",
                f"Pool: {request['pool']}",
            ]
            if request.get("bootstrapName"):
                plan.append(f"Bootstrap: {request['bootstrapName']}")
            if request.get("cores") is not None:
                plan.append(f"Cores: {request['cores']}")
            if request.get("memory") is not None:
                plan.append(f"Memory: {format_bytes(request['memory'])}")
            plan.append(f"Network: {request.get('switchName') or 'none'}")
            plan.append(f"Start after create: {'yes' if start else 'no'}")
            _confirm(plan, "Jail creation plan", yes, fmt)

            try:
                response = client.post("/jail", json_body=request, node=host)
            except SylveAPIError as exc:
                raise SylveError(_friendly_create_error(exc)) from exc
            created = response if isinstance(response, dict) else {}
            created_ctid = int(created.get("ctId") or request["ctId"])
            created_name = str(created.get("name") or request["name"])
            result: dict[str, Any] = {
                "ctId": created_ctid,
                "name": created_name,
                "node": host,
            }
            if start:
                try:
                    start_resp = client.post(f"/jail/{created_ctid}/actions/start", node=host)
                except SylveAPIError as exc:
                    raise SylveError(
                        f"Jail {created_ctid} was created but could not be started: {exc}"
                    ) from exc
                task_id = start_resp.get("taskId") if isinstance(start_resp, dict) else None
                if wait and task_id:
                    wait_for_lifecycle_task(client, int(task_id), node=host)
                    message = f"Created and started Jail {created_name} ({created_ctid}) on {host}."
                else:
                    message = (
                        f"Created Jail {created_name} ({created_ctid}) on {host}; start queued."
                    )
                result["started"] = True
            else:
                message = f"Created Jail {created_name} ({created_ctid}) on {host}."
            print_result(result, fmt=fmt, message=message)
