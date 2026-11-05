"""Additional command groups backed by the Sylve v0.3.1 HTTP API.

The commands here accept request bodies through ``--data`` (a JSON/YAML blob
or ``@FILE``) with per-field ``--property KEY=VALUE`` overrides, plus query
parameters through ``--param``. That keeps the CLI thin: the API remains the
source of truth for request shapes, and new fields do not need a new flag.
"""

# shortcut: generic --data/--param commands avoid per-endpoint flag boilerplate.
# Add typed flags when a command becomes common enough to deserve them.

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Annotated, Any

import typer
import yaml

from sylve_cli.body_schemas import BODY_SCHEMAS
from sylve_cli.client import ResourceNotFoundError, SylveError
from sylve_cli.commands.backup import backup_event_app, job_app, target_app
from sylve_cli.commands.cluster import cluster_app, cluster_note_app
from sylve_cli.commands.download import download_app
from sylve_cli.commands.jail import jail_app, jail_bootstrap_app, jail_template_app
from sylve_cli.commands.network import (
    dhcp_app,
    dhcp_lease_app,
    dhcp_range_app,
    firewall_advanced_app,
    firewall_nat_app,
    firewall_traffic_app,
    iface_app,
    network_app,
    object_app,
    route_app,
    switch_app,
    wg_client_app,
    wg_peer_app,
    wg_server_app,
)
from sylve_cli.commands.node import node_app
from sylve_cli.commands.replication import policy_app
from sylve_cli.commands.task import task_app
from sylve_cli.commands.vm import vm_app, vm_template_app
from sylve_cli.commands.zfs import dataset_app, periodic_app, pool_app, zfs_app
from sylve_cli.console_ws import attach_console
from sylve_cli.formatter import (
    ColumnSpec,
    OutputFormat,
    console,
    err_console,
    print_dict,
    print_list,
    print_result,
)
from sylve_cli.state import (
    CLIState,
    ColumnsOption,
    FilterOption,
    FormatOption,
    LimitOption,
    LongOption,
    NodeOption,
    SortColumnOption,
    confirm_destructive,
)

system_app = typer.Typer(
    name="system",
    help="Manage host disks, SMART tests, PCI passthrough, files, certificates, and settings.",
    no_args_is_help=True,
    rich_markup_mode=None,
)
samba_app = typer.Typer(
    name="samba",
    help="Manage Samba configuration and shares.",
    no_args_is_help=True,
    rich_markup_mode=None,
)
iscsi_app = typer.Typer(
    name="iscsi",
    help="Manage iSCSI targets, initiators, LUNs, and portals.",
    no_args_is_help=True,
    rich_markup_mode=None,
)
ddns_app = typer.Typer(
    name="ddns",
    help="Manage dynamic DNS entries.",
    no_args_is_help=True,
    rich_markup_mode=None,
)
mdns_app = typer.Typer(
    name="mdns",
    help="Manage mDNS configuration and records.",
    no_args_is_help=True,
    rich_markup_mode=None,
)
notifications_app = typer.Typer(
    name="notifications",
    help="Manage notification transports, rules, and active notifications.",
    no_args_is_help=True,
    rich_markup_mode=None,
)
user_app = typer.Typer(
    name="user",
    help="Manage local, PAM, and imported Unix users.",
    no_args_is_help=True,
    rich_markup_mode=None,
)
group_app = typer.Typer(
    name="group",
    help="Manage authentication groups and membership.",
    no_args_is_help=True,
    rich_markup_mode=None,
)
auth_app = typer.Typer(
    name="auth",
    help="Authentication configuration, passkeys, and SSE tokens.",
    no_args_is_help=True,
    rich_markup_mode=None,
)
cloud_init_app = typer.Typer(
    name="cloud-init",
    help="Manage reusable cloud-init templates.",
    no_args_is_help=True,
    rich_markup_mode=None,
)
container_app = typer.Typer(
    name="container",
    help="Manage OCI/Podman containers, images, networks, registries, and catalog apps.",
    no_args_is_help=True,
    rich_markup_mode=None,
)
directory_services_app = typer.Typer(
    name="directory-services",
    help="Manage Active Directory, Kerberos realms, keytabs, and principals.",
    no_args_is_help=True,
    rich_markup_mode=None,
)


def _subapp(parent: typer.Typer, name: str, help_text: str) -> typer.Typer:
    sub = typer.Typer(name=name, help=help_text, no_args_is_help=True, rich_markup_mode=None)
    parent.add_typer(sub, name=name)
    return sub


vm_hardware_app = _subapp(vm_app, "hardware", "Configure VM CPU, RAM, PCI, and VNC hardware.")
vm_network_app = _subapp(vm_app, "network", "Attach, detach, and configure VM networks.")
vm_storage_app = _subapp(vm_app, "storage", "Attach, configure, and delete VM storage.")
vm_options_app = _subapp(vm_app, "options", "Configure VM boot, clock, cloud-init, and options.")

jail_hardware_app = _subapp(jail_app, "hardware", "Configure Jail CPU, RAM, and resource limits.")
jail_network_app = _subapp(jail_app, "network", "Attach, detach, and configure Jail networks.")
jail_options_app = _subapp(jail_app, "options", "Configure Jail fstab, DevFS, hooks, and options.")

system_note_app = _subapp(system_app, "note", "Manage host notes.")
system_disk_app = _subapp(
    system_app, "disk", "List disks and manage GPT partitions and SMART tests."
)
system_ppt_app = _subapp(system_app, "ppt", "Manage PCI passthrough (PPT) devices.")
system_tunable_app = _subapp(system_app, "tunable", "List and set sysctl tunables.")
system_file_app = _subapp(system_app, "file", "Browse, upload, download, and manage host files.")
system_cert_app = _subapp(system_app, "cert", "Manage TLS certificates.")

samba_share_app = _subapp(samba_app, "share", "Manage Samba shares.")
iscsi_initiator_app = _subapp(iscsi_app, "initiator", "Manage iSCSI initiators.")
iscsi_target_app = _subapp(iscsi_app, "target", "Manage iSCSI targets, portals, and LUNs.")
mdns_record_app = _subapp(mdns_app, "record", "Manage mDNS records.")
notifications_rule_app = _subapp(notifications_app, "rule", "Manage notification rules.")
notifications_transport_app = _subapp(
    notifications_app, "transport", "Manage notification transports."
)
user_passkey_app = _subapp(user_app, "passkey", "List and delete user passkeys.")
auth_passkey_app = _subapp(
    auth_app, "passkey", "Run WebAuthn passkey login and registration flows."
)
cloud_init_template_app = _subapp(
    cloud_init_app, "template", "Manage reusable cloud-init templates."
)
container_image_app = _subapp(container_app, "image", "Manage container images on a ZFS pool.")
container_network_app = _subapp(container_app, "network", "Manage container networks.")
container_registry_app = _subapp(
    container_app, "registry", "Manage container registry credentials."
)
container_catalog_app = _subapp(
    container_app, "catalog", "Browse and render container catalog applications."
)
ds_ad_app = _subapp(
    directory_services_app, "ad", "Manage Active Directory configuration and domain membership."
)
ds_kerberos_app = _subapp(
    directory_services_app, "kerberos", "Manage Kerberos settings, realms, and keytabs."
)

# Singleton configuration groups: `config show` reads, `config set` updates.
network_config_app = _subapp(network_app, "config", "Show or update network-wide configuration.")
dhcp_config_app = _subapp(dhcp_app, "config", "Show or update DHCP service configuration.")
samba_config_app = _subapp(samba_app, "config", "Show or update global Samba configuration.")
iscsi_config_app = _subapp(iscsi_app, "config", "Show or update iSCSI global configuration.")
mdns_config_app = _subapp(mdns_app, "config", "Show or update mDNS daemon configuration.")
ds_ad_config_app = _subapp(ds_ad_app, "config", "Show or update Active Directory configuration.")
ds_kerberos_config_app = _subapp(ds_kerberos_app, "config", "Show or update Kerberos defaults.")

_PUBLIC_PATHS = {
    "/auth/login/config",
    "/auth/passkeys/login/begin",
    "/auth/passkeys/login/finish",
    "/basic/initialize",
}


def _parse_data(value: str | None) -> Any:
    if value is None or not value.strip():
        return None
    if value.startswith("@"):
        path = Path(value[1:]).expanduser()
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise SylveError(f"Could not read request body '{path}': {exc}") from exc
    else:
        text = value
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise SylveError(f"Invalid request body: {exc}") from exc


def _parse_params(values: list[str] | None) -> dict[str, Any] | None:
    if not values:
        return None
    result: dict[str, Any] = {}
    for item in values:
        if "=" not in item:
            raise SylveError("--param must use KEY=VALUE format.")
        key, value = item.split("=", 1)
        try:
            result[key] = yaml.safe_load(value)
        except yaml.YAMLError:
            result[key] = value
    return result


def _split_csv_items(text: str) -> list[str]:
    """Split on top-level commas, respecting quotes and bracket/brace nesting."""
    items: list[str] = []
    buf: list[str] = []
    depth = 0
    quote: str | None = None
    for ch in text:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
        elif ch in ('"', "'"):
            quote = ch
            buf.append(ch)
        elif ch in ("[", "{"):
            depth += 1
            buf.append(ch)
        elif ch in ("]", "}"):
            depth = max(0, depth - 1)
            buf.append(ch)
        elif ch == "," and depth == 0:
            items.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    if buf or text.endswith(","):
        items.append("".join(buf).strip())
    return [item for item in items if item != ""]


def _coerce_scalar(raw: str, field_type: str | None) -> Any:
    """Coerce a raw string according to its BODY_SCHEMAS type."""
    if field_type == "string":
        if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ('"', "'"):
            try:
                loaded = yaml.safe_load(raw)
                if isinstance(loaded, str):
                    return loaded
            except yaml.YAMLError:
                pass
        return raw
    try:
        return yaml.safe_load(raw)
    except yaml.YAMLError:
        return raw


def _parse_kv_object(raw: str, children_map: dict[str, str]) -> dict[str, Any]:
    """Parse OpenStack-style ``k1=v1,k2=v2`` into a dict using child schema types."""
    obj: dict[str, Any] = {}
    for pair in _split_csv_items(raw):
        if "=" not in pair:
            raise SylveError(f"--property object entry '{pair}' must use KEY=VALUE format.")
        sub_k, sub_v = pair.split("=", 1)
        sub_k = sub_k.strip()
        if not sub_k:
            raise SylveError("--property must use KEY=VALUE format with a non-empty key.")
        sub_type = children_map.get(sub_k)
        if sub_type is None and "**" in children_map:
            sub_type = children_map["**"]
        if sub_type and sub_type.startswith("array of ") and not sub_v.lstrip().startswith("["):
            elem_type = sub_type.removeprefix("array of ")
            obj[sub_k] = [_coerce_scalar(x, elem_type) for x in _split_csv_items(sub_v)]
        else:
            obj[sub_k] = _coerce_scalar(sub_v, sub_type)
    return obj


def _parse_bracketed_list(raw: str, elem_type: str | None = None) -> list[Any]:
    """Parse a bracketed ``[...]`` value and verify it is a list."""
    try:
        parsed = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise SylveError(f"Invalid --property list '{raw}': {exc}") from exc
    if not isinstance(parsed, list):
        raise SylveError(f"--property list value '{raw}' must be a YAML/JSON list.")
    if elem_type == "string":
        return [str(x) for x in parsed]
    return parsed


def _lookup_schema(fields: tuple[Any, ...], parts: list[str]) -> tuple[str | None, dict[str, str]]:
    """Walk ``BODY_SCHEMAS`` tuples along ``parts`` to return ``(type, child_types)``."""
    current = fields
    field_type: str | None = None
    children_map: dict[str, str] = {}
    for part in parts:
        matched = None
        for entry in current or ():
            if isinstance(entry, (list, tuple)) and len(entry) == 4 and entry[0] == part:
                matched = entry
                break
        if matched is None:
            # Fall back to additionalProperties sentinel ("**") if present
            for entry in current or ():
                if isinstance(entry, (list, tuple)) and len(entry) >= 4 and entry[0] == "**":
                    field_type = entry[1]
                    current = entry[3] if len(entry) > 3 else ()
                    children_map = {
                        c[0]: c[1]
                        for c in (current or ())
                        if isinstance(c, (list, tuple)) and len(c) >= 2
                    }
                    break
            else:
                return None, {}
            continue
        _, field_type, _req, current = matched
        children_map = {
            c[0]: c[1] for c in (current or ()) if isinstance(c, (list, tuple)) and len(c) >= 2
        }
    return field_type, children_map


def _parse_set(
    values: list[str] | None,
    schema_fields: tuple[Any, ...] = (),
    label: str = "",
) -> dict[str, Any]:
    """Parse ``--property KEY=VALUE`` overrides into a (possibly nested) dict.

    Dotted keys address nested objects (``vlanPolicy.mode=tagged``),
    OpenStack-style repeatable ``k1=v1,k2=v2`` builds ``array of object``
    or nested ``object`` fields, and ``BODY_SCHEMAS`` types preserve
    ``string`` fields while coercing numbers, booleans, and lists.
    """
    top_names = [
        entry[0] for entry in schema_fields if isinstance(entry, (list, tuple)) and len(entry) == 4
    ]
    result: dict[str, Any] = {}
    warned: set[str] = set()
    for item in values or []:
        if "=" not in item:
            raise SylveError("--property must use KEY=VALUE format.")
        key, value = item.split("=", 1)
        raw_parts = [part.strip() for part in key.split(".")]
        if not key.strip() or any(not part or part == "[]" for part in raw_parts):
            raise SylveError("--property must use KEY=VALUE format with a non-empty key.")
        explicit_list = raw_parts[-1].endswith("[]")
        parts = [part[:-2] if part.endswith("[]") else part for part in raw_parts]
        top = parts[0]
        if top_names and top not in top_names and top not in warned:
            warned.add(top)
            target_label = f" for {label}" if label else ""
            err_console.print(
                f"warning: unknown field '{top}'{target_label} (expected: {', '.join(top_names)})",
                style="yellow",
                markup=False,
            )

        leaf_type, children_map = _lookup_schema(schema_fields, parts)
        if len(parts) == 1:
            stripped = value.lstrip()
            if leaf_type == "array of object" or (
                explicit_list and "=" in value and not stripped.startswith("[")
            ):
                if stripped.startswith("["):
                    result[top] = _parse_bracketed_list(value)
                else:
                    existing_list = result.get(top)
                    if not isinstance(existing_list, list):
                        existing_list = []
                        result[top] = existing_list
                    if stripped.startswith("{"):
                        existing_list.append(_coerce_scalar(value, None))
                    else:
                        existing_list.append(_parse_kv_object(value, children_map))
                continue
            if (leaf_type and leaf_type.startswith("array of ")) or explicit_list:
                elem_type = (
                    leaf_type.removeprefix("array of ")
                    if (leaf_type and leaf_type.startswith("array of "))
                    else None
                )
                if stripped.startswith("["):
                    result[top] = _parse_bracketed_list(value, elem_type)
                else:
                    existing_list = result.get(top)
                    if not isinstance(existing_list, list):
                        existing_list = []
                        result[top] = existing_list
                    for elem in _split_csv_items(value):
                        existing_list.append(_coerce_scalar(elem, elem_type))
                continue
            if leaf_type == "object" and "=" in value and not stripped.startswith("{"):
                existing_obj = result.get(top)
                if not isinstance(existing_obj, dict):
                    existing_obj = {}
                    result[top] = existing_obj
                existing_obj.update(_parse_kv_object(value, children_map))
                continue

        target = result
        for part in parts[:-1]:
            existing = target.get(part)
            if not isinstance(existing, dict):
                existing = {}
                target[part] = existing
            target = existing

        last = parts[-1]
        if leaf_type and leaf_type.startswith("array of "):
            elem_type = leaf_type.removeprefix("array of ")
            if value.lstrip().startswith("["):
                target[last] = _parse_bracketed_list(value, elem_type)
            else:
                existing_list = target.get(last)
                if not isinstance(existing_list, list):
                    existing_list = []
                    target[last] = existing_list
                for elem in _split_csv_items(value):
                    existing_list.append(_coerce_scalar(elem, elem_type))
        else:
            target[last] = _coerce_scalar(value, leaf_type)
    return result


def _merge_body(
    data: str | None,
    set_values: list[str] | None,
    schema_fields: tuple[Any, ...] = (),
    label: str = "",
) -> Any:
    """Combine ``--data`` with ``--property`` overrides.

    ``--property`` wins field by field; nested dicts merge instead of replacing.
    ``--property`` needs a JSON object body to merge into.
    """

    def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                _deep_merge(base[key], value)
            else:
                base[key] = value
        return base

    base = _parse_data(data)
    overrides = _parse_set(set_values, schema_fields=schema_fields, label=label)
    if not overrides:
        return base
    if base is None:
        return overrides
    if not isinstance(base, dict):
        raise SylveError("--property needs a JSON object body; use --data '{\"key\": ...}' first.")
    return _deep_merge(base, overrides)


def _print_result(
    data: Any,
    fmt: OutputFormat,
    title: str | None = None,
    selected: list[str] | None = None,
    sort_column: str | None = None,
    filters: list[str] | None = None,
    limit: int | None = None,
    long: bool = False,
) -> None:
    if data in (None, {}, []):
        if fmt == OutputFormat.json:
            print_dict({}, fmt=fmt) if isinstance(data, dict) else print_list([], [], fmt=fmt)
        elif fmt == OutputFormat.yaml:
            print_dict({}, fmt=fmt) if isinstance(data, dict) else print_list([], [], fmt=fmt)
        elif fmt != OutputFormat.value:
            console.print("OK", style="green", markup=False)
        return
    if isinstance(data, list) and all(isinstance(row, dict) for row in data):
        columns = [ColumnSpec(str(key), str(key)) for key in data[0]]
        print_list(
            data,
            columns,
            fmt=fmt,
            title=title,
            selected_columns=selected,
            sort_column=sort_column,
            filters=filters,
            limit=limit,
        )
    elif isinstance(data, dict):
        print_dict(data, fmt=fmt, title=title, selected_columns=selected, long=long)
    else:
        print_result(data, fmt)


def _render_field_lines(fields: object, indent: str) -> list[str]:
    """Render ``(name, type, required, children)`` fields as one line each."""
    lines: list[str] = []
    if not isinstance(fields, (list, tuple)):
        return lines
    for field in fields:
        if not isinstance(field, (list, tuple)) or len(field) != 4:
            continue
        name, field_type, required, children = field
        marker = ", required" if required else ""
        if name == "**":
            display_name = "<any key>"
        elif field_type == "array of object":
            display_name = f"{name}[]"
        else:
            display_name = name
        if isinstance(children, (list, tuple)) and children:
            lines.append(f"{indent}{display_name} ({field_type}{marker}):")
            lines.extend(_render_field_lines(children, indent + "  "))
        else:
            lines.append(f"{indent}{display_name} ({field_type}{marker})")
    return lines


def _schema_epilog(method: str, path: str) -> str | None:
    """Build the ``--help`` appendix listing settable fields.

    Generic commands take free-form ``--property`` keys, so the schema is the
    only in-terminal discovery. Shapes come from the checked-in
    ``body_schemas`` module (built from ``docs/swagger.json``), never from
    the network, so ``--help`` stays offline-fast. Required fields sort
    first; nested objects render indented one level down.
    """
    entry = BODY_SCHEMAS.get((method, path))
    if not entry:
        return None
    sections: list[str] = []
    body = entry.get("body")
    if body:
        sections.append("Settable body fields (--property):")
        sections.extend(_render_field_lines(body, "  "))
    query = entry.get("query")
    if query:
        if sections:
            sections.append("")
        sections.append("Query parameters (--param):")
        sections.extend(_render_field_lines(query, "  "))
    if not sections:
        return None
    # \b keeps the field list preformatted instead of rewrapped.
    return "\b\n" + "\n".join(sections)


def _path_for(template: str, args: list[str] | None) -> str:
    args = args or []
    placeholders = re.findall(r"\{[^}]+\}", template)
    if len(args) != len(placeholders):
        raise SylveError(
            f"This command expects {len(placeholders)} path argument(s), "
            f"got {len(args)}: {template}."
        )
    values = iter(args)
    return re.sub(r"\{[^}]+\}", lambda _: next(values), template)


def _execute_generic(
    ctx: typer.Context,
    method: str,
    path: str,
    args: list[str] | None,
    data: str | None,
    param: list[str] | None,
    yes: bool,
    node: str | None,
    fmt: OutputFormat,
    title: str,
    set_values: list[str] | None = None,
    dry_run: bool = False,
    selected: list[str] | None = None,
    sort_column: str | None = None,
    filters: list[str] | None = None,
    limit: int | None = None,
    long: bool = False,
) -> None:
    """Run one generic API request and print the result."""
    schema_entry = BODY_SCHEMAS.get((method, path), {})
    body_schema: tuple[Any, ...] = schema_entry.get("body") or ()
    try:
        target_path = _path_for(path, args)
    except SylveError as exc:
        # Wrong path-argument count with no body or parameters either: the
        # user is exploring, so show this command's help like a bare command
        # group does. Anything else supplied means a real (broken) invocation,
        # reported as a usage error (exit 2) with the command's usage.
        # ctx.fail() raises the UsageError class of this app's click copy, so
        # the error is rendered (not dumped as a traceback) on every runner.
        if (
            not data
            and not set_values
            and not param
            and not selected
            and not sort_column
            and not filters
            and not limit
        ):
            typer.echo(ctx.get_help())
            raise typer.Exit(0)
        ctx.fail(str(exc))
    if (
        not args
        and (body_schema or method == "PUT")
        and not data
        and not set_values
        and not param
        and not dry_run
    ):
        typer.echo(ctx.get_help())
        raise typer.Exit(0)
    state: CLIState = ctx.obj
    body = _merge_body(data, set_values, schema_fields=body_schema, label=f"{method} {path}")
    params = _parse_params(param)
    if dry_run:
        _print_result(
            {"method": method, "path": target_path, "params": params, "body": body},
            fmt,
            f"Dry run: {method} {target_path}",
            long=True,
        )
        return
    destructive = method == "DELETE" or "delete" in path.lower()
    if destructive:
        # A non-interactive stdin must not count as consent; the helper aborts
        # with a "--yes" hint instead of deleting silently.
        confirm_destructive(f"Send {method} {target_path}?", yes=yes)
    with state.get_client(node_override=node) as client:
        result = client.request(
            method,
            target_path,
            params=params,
            json_body=body,
            node=node,
            require_auth=path not in _PUBLIC_PATHS,
        )
    if isinstance(result, str) and result.lstrip().lower().startswith(("<!doctype html", "<html")):
        raise SylveError(
            f"{method} {target_path} returned a non-JSON body; "
            "this endpoint is not implemented on the target server."
        )
    _print_result(result, fmt, title, selected, sort_column, filters, limit, long=long)


PathArgs = Annotated[list[str] | None, typer.Argument(help="Path arguments in URL order.")]
DataOption = Annotated[
    str | None,
    typer.Option(
        "--data",
        "-d",
        help="Base JSON or YAML request body, or @FILE to read it from disk.",
    ),
]
SetOption = Annotated[
    list[str] | None,
    typer.Option(
        "--property",
        "-s",
        help="Set a body field KEY=VALUE (repeatable; dotted keys nest; "
        "repeat or comma-separate for lists). Overrides --data.",
    ),
]
ParamOption = Annotated[
    list[str] | None,
    typer.Option("--param", "-p", help="Query parameter KEY=VALUE (repeatable)."),
]
DryRunOption = Annotated[
    bool,
    typer.Option("--dry-run", help="Print the request without sending it."),
]
YesPromptOption = Annotated[
    bool,
    typer.Option("-y", "--yes", help="Skip confirmation prompt."),
]


def _add(
    app: typer.Typer,
    name: str,
    method: str,
    path: str,
    description: str,
    args_help: str = "",
    *,
    binary: bool = False,
    upload: bool = False,
) -> None:
    title = description.split(".")[0]
    help_text = description if not args_help else f"{description} Arguments: {args_help}."
    epilog = _schema_epilog(method, path)
    destructive = method == "DELETE" or "delete" in path.lower()
    has_body = method in ("POST", "PUT", "PATCH") or bool(
        BODY_SCHEMAS.get((method, path), {}).get("body")
    )

    if binary:

        def command(
            ctx: typer.Context,
            args: PathArgs = None,
            param: ParamOption = None,
            output: Annotated[Path, typer.Option("--output", "-o")] = ...,  # type: ignore[assignment]
            node: NodeOption = None,
        ) -> None:
            state: CLIState = ctx.obj
            with state.get_client(node_override=node) as client:
                target = client.download_file(
                    _path_for(path, args), output, params=_parse_params(param), node=node
                )
            console.print(f"Saved to {target}", style="green", markup=False)

    elif upload:

        def command(  # type: ignore[misc]
            ctx: typer.Context,
            args: PathArgs = None,
            file: Annotated[
                Path,
                typer.Option(
                    "--file",
                    exists=True,
                    dir_okay=False,
                    readable=True,
                    help="Local file to upload.",
                ),
            ] = ...,  # type: ignore[assignment]
            param: ParamOption = None,
            node: NodeOption = None,
            fmt: FormatOption = OutputFormat.table,
        ) -> None:
            state: CLIState = ctx.obj
            with state.get_client(node_override=node) as client, file.open("rb") as handle:
                result = client.post(
                    _path_for(path, args),
                    params=_parse_params(param),
                    files={"filepond": (file.name, handle, "application/octet-stream")},
                    node=node,
                )
            _print_result(result, fmt, title)

    elif destructive and not has_body:

        def command(  # type: ignore[misc]
            ctx: typer.Context,
            args: PathArgs = None,
            param: ParamOption = None,
            yes: YesPromptOption = False,
            dry_run: DryRunOption = False,
            node: NodeOption = None,
            fmt: FormatOption = OutputFormat.table,
        ) -> None:
            _execute_generic(
                ctx, method, path, args, None, param, yes, node, fmt, title, None, dry_run
            )

    elif destructive:

        def command(  # type: ignore[misc]
            ctx: typer.Context,
            args: PathArgs = None,
            data: DataOption = None,
            set_value: SetOption = None,
            param: ParamOption = None,
            yes: YesPromptOption = False,
            dry_run: DryRunOption = False,
            node: NodeOption = None,
            fmt: FormatOption = OutputFormat.table,
        ) -> None:
            _execute_generic(
                ctx, method, path, args, data, param, yes, node, fmt, title, set_value, dry_run
            )

    elif method == "GET":

        def command(  # type: ignore[misc]
            ctx: typer.Context,
            args: PathArgs = None,
            param: ParamOption = None,
            long: LongOption = False,
            dry_run: DryRunOption = False,
            node: NodeOption = None,
            fmt: FormatOption = OutputFormat.table,
            columns: ColumnsOption = None,
            sort_column: SortColumnOption = None,
            filters: FilterOption = None,
            limit: LimitOption = None,
        ) -> None:
            _execute_generic(
                ctx,
                method,
                path,
                args,
                None,
                param,
                False,
                node,
                fmt,
                title,
                None,
                dry_run,
                columns,
                sort_column,
                filters,
                limit,
                long=long,
            )

    else:

        def command(  # type: ignore[misc]
            ctx: typer.Context,
            args: PathArgs = None,
            data: DataOption = None,
            set_value: SetOption = None,
            param: ParamOption = None,
            dry_run: DryRunOption = False,
            node: NodeOption = None,
            fmt: FormatOption = OutputFormat.table,
        ) -> None:
            _execute_generic(
                ctx, method, path, args, data, param, False, node, fmt, title, set_value, dry_run
            )

    command.__name__ = f"{app.info.name}_{name}".replace("-", "_")
    command.__doc__ = help_text
    app.command(name, help=help_text, epilog=epilog)(command)


# ---------------------------------------------------------------------------
# VM configuration
# ---------------------------------------------------------------------------
for spec in [  # type: ignore[assignment]
    (
        vm_template_app,
        "show",
        "GET",
        "/vm/templates/{templateId}",
        "Show a VM template.",
        "templateId",
    ),
    (vm_app, "description", "PATCH", "/vm/{rid}/description", "Update a VM description.", "rid"),
    (vm_app, "domain", "GET", "/vm/{rid}/domain", "Show the libvirt domain XML.", "rid"),
    (vm_app, "stats", "GET", "/vm/{rid}/stats", "Show current VM statistics.", "rid"),
    (
        vm_app,
        "stats-step",
        "GET",
        "/vm/{rid}/stats/{step}",
        "Show VM statistics for a step.",
        "rid step",
    ),
    (
        vm_hardware_app,
        "cpu",
        "PUT",
        "/vm/{rid}/hardware/cpu",
        "Replace VM CPU configuration.",
        "rid",
    ),
    (
        vm_hardware_app,
        "ram",
        "PUT",
        "/vm/{rid}/hardware/ram",
        "Replace VM RAM configuration.",
        "rid",
    ),
    (
        vm_hardware_app,
        "pci",
        "PUT",
        "/vm/{rid}/hardware/pci-devices",
        "Replace VM PCI passthrough devices.",
        "rid",
    ),
    (
        vm_hardware_app,
        "vnc",
        "PUT",
        "/vm/{rid}/hardware/vnc",
        "Replace VM VNC configuration.",
        "rid",
    ),
    (vm_network_app, "attach", "POST", "/vm/{rid}/networks", "Attach a network to a VM.", "rid"),
    (
        vm_network_app,
        "detach",
        "DELETE",
        "/vm/{rid}/networks/{networkId}",
        "Detach a VM network.",
        "rid networkId",
    ),
    (
        vm_network_app,
        "set",
        "PATCH",
        "/vm/{rid}/networks/{networkId}",
        "Update a VM network.",
        "rid networkId",
    ),
    (vm_storage_app, "attach", "POST", "/vm/{rid}/storage", "Attach storage to a VM.", "rid"),
    (
        vm_storage_app,
        "from-image",
        "POST",
        "/vm/{rid}/storage/from-image",
        "Create VM storage from an image.",
        "rid",
    ),
    (
        vm_storage_app,
        "set",
        "PATCH",
        "/vm/{rid}/storage/{storageId}",
        "Update VM storage.",
        "rid storageId",
    ),
    (
        vm_storage_app,
        "delete",
        "DELETE",
        "/vm/{rid}/storage/{storageId}",
        "Delete VM storage.",
        "rid storageId",
    ),
    (
        vm_options_app,
        "boot-order",
        "PUT",
        "/vm/{rid}/options/boot-order",
        "Replace VM autostart configuration.",
        "rid",
    ),
    (
        vm_options_app,
        "boot-rom",
        "PUT",
        "/vm/{rid}/options/boot-rom",
        "Replace VM boot ROM configuration.",
        "rid",
    ),
    (
        vm_options_app,
        "clock",
        "PUT",
        "/vm/{rid}/options/clock",
        "Replace VM clock configuration.",
        "rid",
    ),
    (
        vm_options_app,
        "cloud-init",
        "PUT",
        "/vm/{rid}/options/cloud-init",
        "Replace VM cloud-init configuration.",
        "rid",
    ),
    (
        vm_options_app,
        "extra-bhyve",
        "PUT",
        "/vm/{rid}/options/extra-bhyve-options",
        "Replace extra bhyve options.",
        "rid",
    ),
    (
        vm_options_app,
        "ignore-umsrs",
        "PUT",
        "/vm/{rid}/options/ignore-umsrs",
        "Replace unknown-MSR handling.",
        "rid",
    ),
    (
        vm_options_app,
        "qemu-guest-agent",
        "PUT",
        "/vm/{rid}/options/qemu-guest-agent",
        "Replace QEMU guest-agent configuration.",
        "rid",
    ),
    (
        vm_options_app,
        "serial-console",
        "PUT",
        "/vm/{rid}/options/serial-console",
        "Replace serial-console configuration.",
        "rid",
    ),
    (
        vm_options_app,
        "shutdown-wait-time",
        "PUT",
        "/vm/{rid}/options/shutdown-wait-time",
        "Replace shutdown wait time.",
        "rid",
    ),
    (
        vm_options_app,
        "tpm",
        "PUT",
        "/vm/{rid}/options/tpm",
        "Replace TPM emulation configuration.",
        "rid",
    ),
    (
        vm_options_app,
        "wol",
        "PUT",
        "/vm/{rid}/options/wol",
        "Replace Wake-on-LAN configuration.",
        "rid",
    ),
    (
        vm_app,
        "registration-purge",
        "DELETE",
        "/vm/{rid}/registration",
        "Purge an orphaned VM registration.",
        "rid",
    ),
    (
        vm_app,
        "domain-reinitialize",
        "POST",
        "/vm/{rid}/domain/reinitialize",
        "Reinitialize a VM libvirt domain.",
        "rid",
    ),
]:
    _add(*spec)

# ---------------------------------------------------------------------------
# Jail configuration
# ---------------------------------------------------------------------------
for spec in [  # type: ignore[assignment]
    (
        jail_app,
        "description",
        "PATCH",
        "/jail/{ctid}/description",
        "Update a Jail description.",
        "ctid",
    ),
    (
        jail_hardware_app,
        "cpu",
        "PUT",
        "/jail/{ctid}/hardware/cpu",
        "Update a Jail CPU limit.",
        "ctid",
    ),
    (
        jail_hardware_app,
        "ram",
        "PUT",
        "/jail/{ctid}/hardware/ram",
        "Update a Jail RAM limit.",
        "ctid",
    ),
    (
        jail_hardware_app,
        "resource-limits",
        "PUT",
        "/jail/{ctid}/hardware/resource-limits",
        "Set Jail resource limits.",
        "ctid",
    ),
    (
        jail_network_app,
        "inheritance",
        "PUT",
        "/jail/{ctid}/network/inheritance",
        "Set Jail network inheritance.",
        "ctid",
    ),
    (
        jail_network_app,
        "attach",
        "POST",
        "/jail/{ctid}/networks",
        "Attach a network to a Jail.",
        "ctid",
    ),
    (
        jail_network_app,
        "detach",
        "DELETE",
        "/jail/{ctid}/networks/{networkId}",
        "Detach a Jail network.",
        "ctid networkId",
    ),
    (
        jail_network_app,
        "set",
        "PATCH",
        "/jail/{ctid}/networks/{networkId}",
        "Update a Jail network.",
        "ctid networkId",
    ),
    (
        jail_options_app,
        "additional",
        "PUT",
        "/jail/{ctid}/options/additional-options",
        "Replace additional jail.conf options.",
        "ctid",
    ),
    (
        jail_options_app,
        "allowed",
        "PUT",
        "/jail/{ctid}/options/allowed-options",
        "Replace allowed jail options.",
        "ctid",
    ),
    (
        jail_options_app,
        "boot-order",
        "PUT",
        "/jail/{ctid}/options/boot-order",
        "Replace Jail autostart configuration.",
        "ctid",
    ),
    (
        jail_options_app,
        "devfs-rules",
        "PUT",
        "/jail/{ctid}/options/devfs-rules",
        "Replace Jail DevFS rules.",
        "ctid",
    ),
    (
        jail_options_app,
        "execution-timeout",
        "PUT",
        "/jail/{ctid}/options/execution-timeout",
        "Replace Jail execution timeout.",
        "ctid",
    ),
    (
        jail_options_app,
        "fstab",
        "PUT",
        "/jail/{ctid}/options/fstab",
        "Replace Jail fstab configuration.",
        "ctid",
    ),
    (
        jail_options_app,
        "lifecycle-hooks",
        "PUT",
        "/jail/{ctid}/options/lifecycle-hooks",
        "Replace Jail lifecycle hooks.",
        "ctid",
    ),
    (
        jail_options_app,
        "metadata",
        "PUT",
        "/jail/{ctid}/options/metadata",
        "Replace Jail metadata.",
        "ctid",
    ),
    (
        jail_options_app,
        "resolv-conf",
        "PUT",
        "/jail/{ctid}/options/resolv-conf",
        "Replace Jail resolv.conf configuration.",
        "ctid",
    ),
    (
        jail_options_app,
        "wol",
        "PUT",
        "/jail/{ctid}/options/wol",
        "Replace Jail Wake-on-LAN configuration.",
        "ctid",
    ),
    (
        jail_app,
        "root-mountpoint",
        "GET",
        "/jail/{ctid}/root-mountpoint",
        "Resolve a Jail root mountpoint.",
        "ctid",
    ),
    (jail_app, "state", "GET", "/jail/{ctid}/state", "Show Jail state.", "ctid"),
    (jail_app, "stats", "GET", "/jail/{ctid}/stats", "Show Jail statistics.", "ctid"),
    (
        jail_template_app,
        "show",
        "GET",
        "/jail/templates/{templateId}",
        "Show a Jail template.",
        "templateId",
    ),
    (
        jail_template_app,
        "delete",
        "DELETE",
        "/jail/templates/{templateId}",
        "Delete a Jail template.",
        "templateId",
    ),
    (
        jail_template_app,
        "capture",
        "POST",
        "/jail/{ctid}/templates",
        "Capture a Jail as a template.",
        "ctid",
    ),
    (
        jail_template_app,
        "deploy",
        "POST",
        "/jail/templates/{templateId}/jails",
        "Create Jails from a template.",
        "templateId",
    ),
    (
        jail_bootstrap_app,
        "delete",
        "DELETE",
        "/jail/bootstraps/{name}",
        "Delete a pkgbase Jail bootstrap.",
        "name",
    ),
    (
        jail_app,
        "stats-step",
        "GET",
        "/jail/{ctid}/stats/{step}",
        "Show Jail statistics for a step.",
        "ctid step",
    ),
    (
        jail_app,
        "validate",
        "POST",
        "/jail/validate",
        "Validate a Jail creation request.",
    ),
    (
        jail_app,
        "zfs-sources",
        "GET",
        "/jail/zfs-sources",
        "List existing Jail root datasets.",
    ),
]:
    _add(*spec)

# ---------------------------------------------------------------------------
# Network config, interface L3, DHCP, firewall, network-object, route, WireGuard
# ---------------------------------------------------------------------------
for spec in [  # type: ignore[assignment]
    (
        network_config_app,
        "show",
        "GET",
        "/network/global-config",
        "Show network-wide configuration.",
    ),
    (
        network_config_app,
        "set",
        "PUT",
        "/network/global-config",
        "Update network-wide configuration.",
    ),
    (
        iface_app,
        "l3-pending",
        "GET",
        "/network/interface/l3/pending",
        "List pending host interface L3 operations.",
    ),
    (
        iface_app,
        "l3-set",
        "PUT",
        "/network/interface/{name}/l3",
        "Stage a host interface L3 configuration change.",
        "name",
    ),
    (
        iface_app,
        "l3-delete",
        "DELETE",
        "/network/interface/{name}/l3",
        "Stage deletion of host interface L3 configuration.",
        "name",
    ),
    (
        iface_app,
        "l3-reapply",
        "POST",
        "/network/interface/{name}/l3/reapply",
        "Reapply host interface L3 configuration.",
        "name",
    ),
    (
        iface_app,
        "l3-confirm",
        "POST",
        "/network/host-ip/pending/{id}/confirm",
        "Confirm a pending host interface L3 operation.",
        "id",
    ),
    (
        iface_app,
        "l3-revert",
        "POST",
        "/network/host-ip/pending/{id}/revert",
        "Revert a pending host interface L3 operation.",
        "id",
    ),
    (dhcp_config_app, "show", "GET", "/network/dhcp/config", "Show DHCP service configuration."),
    (dhcp_config_app, "set", "PUT", "/network/dhcp/config", "Update DHCP service configuration."),
    (dhcp_range_app, "create", "POST", "/network/dhcp/range", "Create a DHCP range."),
    (dhcp_range_app, "set", "PUT", "/network/dhcp/range/{id}", "Update a DHCP range.", "id"),
    (dhcp_range_app, "delete", "DELETE", "/network/dhcp/range/{id}", "Delete a DHCP range.", "id"),
    (dhcp_lease_app, "create", "POST", "/network/dhcp/lease", "Create a static DHCP lease."),
    (
        dhcp_lease_app,
        "set",
        "PUT",
        "/network/dhcp/lease/{id}",
        "Update a static DHCP lease.",
        "id",
    ),
    (
        dhcp_lease_app,
        "delete",
        "DELETE",
        "/network/dhcp/lease/{id}",
        "Delete a static DHCP lease.",
        "id",
    ),
    (
        dhcp_lease_app,
        "delete-dynamic",
        "DELETE",
        "/network/dhcp/lease/dynamic",
        "Delete a dynamic DHCP lease.",
    ),
    (
        firewall_advanced_app,
        "show",
        "GET",
        "/network/firewall/advanced",
        "Show advanced firewall settings.",
    ),
    (
        firewall_advanced_app,
        "set",
        "PUT",
        "/network/firewall/advanced",
        "Update advanced firewall settings.",
    ),
    (
        firewall_advanced_app,
        "preview",
        "POST",
        "/network/firewall/advanced/preview",
        "Preview rendered firewall configuration.",
    ),
    (
        firewall_advanced_app,
        "rendered",
        "GET",
        "/network/firewall/advanced/rendered",
        "Show rendered firewall configuration.",
    ),
    (
        firewall_traffic_app,
        "create",
        "POST",
        "/network/firewall/traffic",
        "Create a firewall traffic rule.",
    ),
    (
        firewall_traffic_app,
        "set",
        "PUT",
        "/network/firewall/traffic/{id}",
        "Update a firewall traffic rule.",
        "id",
    ),
    (
        firewall_traffic_app,
        "delete",
        "DELETE",
        "/network/firewall/traffic/{id}",
        "Delete a firewall traffic rule.",
        "id",
    ),
    (
        firewall_traffic_app,
        "bulk-delete",
        "DELETE",
        "/network/firewall/traffic",
        "Bulk-delete firewall traffic rules.",
    ),
    (
        firewall_traffic_app,
        "reorder",
        "PUT",
        "/network/firewall/traffic/reorder",
        "Reorder firewall traffic rules.",
    ),
    (
        firewall_traffic_app,
        "counters",
        "GET",
        "/network/firewall/traffic/counters",
        "Show firewall traffic rule counters.",
    ),
    (
        firewall_nat_app,
        "create",
        "POST",
        "/network/firewall/nat",
        "Create a firewall NAT rule.",
    ),
    (
        firewall_nat_app,
        "set",
        "PUT",
        "/network/firewall/nat/{id}",
        "Update a firewall NAT rule.",
        "id",
    ),
    (
        firewall_nat_app,
        "delete",
        "DELETE",
        "/network/firewall/nat/{id}",
        "Delete a firewall NAT rule.",
        "id",
    ),
    (
        firewall_nat_app,
        "bulk-delete",
        "DELETE",
        "/network/firewall/nat",
        "Bulk-delete firewall NAT rules.",
    ),
    (
        firewall_nat_app,
        "reorder",
        "PUT",
        "/network/firewall/nat/reorder",
        "Reorder firewall NAT rules.",
    ),
    (
        firewall_nat_app,
        "counters",
        "GET",
        "/network/firewall/nat/counters",
        "Show firewall NAT rule counters.",
    ),
    (
        firewall_nat_app,
        "route-suggestions",
        "GET",
        "/network/firewall/nat/{id}/route-suggestions",
        "Suggest routes for a NAT rule.",
        "id",
    ),
    (
        wg_server_app,
        "init",
        "POST",
        "/network/wireguard/server",
        "Initialize the WireGuard server.",
    ),
    (wg_server_app, "set", "PUT", "/network/wireguard/server", "Update the WireGuard server."),
    (
        wg_server_app,
        "delete",
        "DELETE",
        "/network/wireguard/server",
        "Deinitialize the WireGuard server.",
    ),
    (wg_server_app, "state", "PATCH", "/network/wireguard/server", "Set WireGuard server state."),
    (
        wg_peer_app,
        "add",
        "POST",
        "/network/wireguard/server/peer",
        "Add a WireGuard server peer.",
    ),
    (
        wg_peer_app,
        "set",
        "PUT",
        "/network/wireguard/server/peer/{peerId}",
        "Update a WireGuard peer.",
        "peerId",
    ),
    (
        wg_peer_app,
        "remove",
        "DELETE",
        "/network/wireguard/server/peer/{peerId}",
        "Remove a WireGuard peer.",
        "peerId",
    ),
    (
        wg_peer_app,
        "state",
        "PATCH",
        "/network/wireguard/server/peer/{peerId}",
        "Set WireGuard peer state.",
        "peerId",
    ),
    (
        wg_client_app,
        "create",
        "POST",
        "/network/wireguard/clients",
        "Create a WireGuard client.",
    ),
    (
        wg_client_app,
        "set",
        "PUT",
        "/network/wireguard/clients/{clientId}",
        "Update a WireGuard client.",
        "clientId",
    ),
    (
        wg_client_app,
        "delete",
        "DELETE",
        "/network/wireguard/clients/{clientId}",
        "Delete a WireGuard client.",
        "clientId",
    ),
    (
        wg_client_app,
        "state",
        "PATCH",
        "/network/wireguard/clients/{clientId}",
        "Set WireGuard client state.",
        "clientId",
    ),
    (route_app, "create", "POST", "/network/route", "Create a static route."),
    (route_app, "set", "PUT", "/network/route/{id}", "Update a static route.", "id"),
    (
        switch_app,
        "set-standard",
        "PUT",
        "/network/switch/standard/{id}",
        "Update a standard switch.",
        "id",
    ),
    (object_app, "set", "PUT", "/network/object/{id}", "Update a network object.", "id"),
    (object_app, "bulk-delete", "DELETE", "/network/object", "Bulk-delete network objects."),
]:
    _add(*spec)


# shortcut: WebSocket consoles, VNC, and node terminal are not wrapped here;
# use the web UI or a websocket client until interactive terminal plumbing is
# actually needed.


# ---------------------------------------------------------------------------
# Node history and task lookup
# ---------------------------------------------------------------------------
for spec in [  # type: ignore[assignment]
    (node_app, "cpu-history", "GET", "/info/cpu/historical", "Show historical CPU data."),
    (node_app, "ram-history", "GET", "/info/ram/historical", "Show historical RAM data."),
    (node_app, "swap-history", "GET", "/info/swap/historical", "Show historical swap data."),
    (
        node_app,
        "network-history",
        "GET",
        "/info/network-interfaces/historical",
        "Show historical network data.",
    ),
    (node_app, "summary-history", "GET", "/info/summary/history", "Show node summary history."),
    (
        node_app,
        "summary-delta",
        "GET",
        "/info/summary/history/delta",
        "Show node summary history deltas.",
    ),
    (
        task_app,
        "active",
        "GET",
        "/tasks/lifecycle/active/{guestType}/{guestId}",
        "Show the active task for a guest.",
        "guestType guestId",
    ),
]:
    _add(*spec)


# ---------------------------------------------------------------------------
# ZFS depth
# ---------------------------------------------------------------------------
for spec in [  # type: ignore[assignment]
    (pool_app, "create", "POST", "/zfs/pools", "Create a ZFS pool."),
    (pool_app, "disks-usage", "GET", "/zfs/pools/disks-usage", "Show disk usage."),
    (
        pool_app,
        "scrub-schedules",
        "GET",
        "/zfs/pools/scrub/schedules",
        "List ZFS scrub schedules.",
    ),
    (
        pool_app,
        "scrub-schedule-create",
        "POST",
        "/zfs/pools/scrub/schedules",
        "Create a ZFS scrub schedule.",
    ),
    (
        pool_app,
        "scrub-schedule-set",
        "PUT",
        "/zfs/pools/scrub/schedules/{id}",
        "Update a ZFS scrub schedule.",
        "id",
    ),
    (
        pool_app,
        "scrub-schedule-delete",
        "DELETE",
        "/zfs/pools/scrub/schedules/{id}",
        "Delete a ZFS scrub schedule.",
        "id",
    ),
    (
        dataset_app,
        "bulk-delete",
        "DELETE",
        "/zfs/datasets",
        "Bulk-delete ZFS datasets.",
    ),
    (dataset_app, "paginated", "GET", "/zfs/datasets/paginated", "List paginated ZFS datasets."),
    (
        periodic_app,
        "create",
        "POST",
        "/zfs/datasets/snapshot/periodic",
        "Create a periodic snapshot job.",
    ),
    (
        periodic_app,
        "set",
        "PATCH",
        "/zfs/datasets/snapshot/periodic/{id}",
        "Update a periodic snapshot job.",
        "id",
    ),
    (
        periodic_app,
        "delete",
        "DELETE",
        "/zfs/datasets/snapshot/periodic/{id}",
        "Delete a periodic snapshot job.",
        "id",
    ),
    (
        periodic_app,
        "bulk-delete",
        "DELETE",
        "/zfs/datasets/snapshot/periodic",
        "Bulk-delete periodic snapshot jobs.",
    ),
    (
        zfs_app,
        "dashboard-snapshot",
        "GET",
        "/zfs/dashboard/snapshot",
        "Show the current ZFS dashboard snapshot.",
    ),
    (zfs_app, "dashboard-history", "GET", "/zfs/dashboard/history", "Show ZFS dashboard history."),
    (
        zfs_app,
        "dashboard-delta",
        "GET",
        "/zfs/dashboard/history/delta",
        "Show ZFS dashboard history deltas.",
    ),
]:
    _add(*spec)


# ---------------------------------------------------------------------------
# Backup depth
# ---------------------------------------------------------------------------
for spec in [  # type: ignore[assignment]
    (target_app, "create", "POST", "/cluster/backups/targets", "Create a backup target."),
    (target_app, "set", "PUT", "/cluster/backups/targets/{id}", "Update a backup target.", "id"),
    (
        target_app,
        "readiness",
        "GET",
        "/cluster/backups/targets/{id}/readiness",
        "Show backup target readiness.",
        "id",
    ),
    (
        target_app,
        "running-jobs",
        "GET",
        "/cluster/backups/targets/{id}/running-jobs",
        "List running jobs for a target.",
        "id",
    ),
    (
        target_app,
        "dataset-snapshots",
        "GET",
        "/cluster/backups/targets/{id}/datasets/snapshots",
        "List target dataset snapshots.",
        "id",
    ),
    (
        target_app,
        "vm-metadata",
        "GET",
        "/cluster/backups/targets/{id}/datasets/vm-metadata",
        "Show target VM metadata.",
        "id",
    ),
    (
        target_app,
        "jail-metadata",
        "GET",
        "/cluster/backups/targets/{id}/datasets/jail-metadata",
        "Show target Jail metadata.",
        "id",
    ),
    (
        target_app,
        "restore",
        "POST",
        "/cluster/backups/targets/{id}/restore",
        "Restore a target dataset.",
        "id",
    ),
    (job_app, "create", "POST", "/cluster/backups/jobs", "Create a backup job."),
    (job_app, "set", "PUT", "/cluster/backups/jobs/{id}", "Update a backup job.", "id"),
    (
        backup_event_app,
        "remote-list",
        "GET",
        "/cluster/backups/events/remote",
        "List remote backup events with pagination.",
    ),
    (
        policy_app,
        "set",
        "PUT",
        "/cluster/replication/policies/{id}",
        "Update a replication policy.",
        "id",
    ),
]:
    _add(*spec)


# ---------------------------------------------------------------------------
# Cluster depth
# ---------------------------------------------------------------------------
for spec in [  # type: ignore[assignment]
    (cluster_app, "accept-join", "POST", "/cluster/accept-join", "Accept a pending cluster join."),
    (cluster_note_app, "set", "PUT", "/cluster/notes/{id}", "Update a cluster note.", "id"),
    (
        cluster_note_app,
        "bulk-delete",
        "POST",
        "/cluster/notes/bulk-delete",
        "Bulk-delete cluster notes.",
    ),
]:
    _add(*spec)


# ---------------------------------------------------------------------------
# Downloads
# ---------------------------------------------------------------------------
for spec in [  # type: ignore[assignment]
    (
        download_app,
        "set",
        "PATCH",
        "/utilities/downloads/{id}",
        "Update download metadata.",
        "id",
    ),
    (
        download_app,
        "utype",
        "GET",
        "/utilities/downloads/utype",
        "List completed download choices.",
    ),
    (
        download_app,
        "detect-filename",
        "POST",
        "/utilities/downloads/detect-filename",
        "Detect a remote filename from a URL.",
    ),
    (
        download_app,
        "abort-upload",
        "DELETE",
        "/utilities/downloader-uploads/{id}",
        "Abort a staged upload.",
        "id",
    ),
]:
    _add(*spec)

_add(
    download_app,
    "file",
    "GET",
    "/utilities/downloads/{uuid}",
    "Download a completed file using signed capability params.",
    args_help="uuid",
    binary=True,
)
_add(
    download_app,
    "file-with-name",
    "GET",
    "/utilities/downloads/{uuid}/{filename}",
    "Download a completed file by UUID and filename using signed capability params.",
    args_help="uuid filename",
    binary=True,
)


# ---------------------------------------------------------------------------
# System
# ---------------------------------------------------------------------------
for spec in [  # type: ignore[assignment]
    (system_app, "init", "POST", "/basic/initialize", "Initialize Sylve."),
    (
        system_app,
        "basic-settings",
        "GET",
        "/basic/settings",
        "Show basic Sylve settings from /basic/settings.",
    ),
    (
        system_app,
        "settings",
        "GET",
        "/system/basic-settings",
        "Show system basic settings from /system/basic-settings.",
    ),
    (
        system_app,
        "settings-pools",
        "PUT",
        "/system/basic-settings/pools",
        "Replace usable ZFS pools.",
    ),
    (
        system_app,
        "service",
        "PATCH",
        "/system/basic-settings/services/{service}",
        "Set a service state.",
        "service",
    ),
    (system_note_app, "list", "GET", "/info/notes", "List host notes."),
    (system_note_app, "create", "POST", "/info/notes", "Create a host note."),
    (system_note_app, "set", "PUT", "/info/notes/{id}", "Update a host note.", "id"),
    (system_note_app, "delete", "DELETE", "/info/notes/{id}", "Delete a host note.", "id"),
    (system_note_app, "bulk-delete", "DELETE", "/info/notes", "Bulk-delete host notes."),
    (system_disk_app, "list", "GET", "/disk", "List disk devices."),
    (
        system_disk_app,
        "partition-delete",
        "DELETE",
        "/disk/partitions/{partition}",
        "Delete a partition.",
        "partition",
    ),
    (
        system_disk_app,
        "gpt-init",
        "POST",
        "/disk/{device}/partition-table",
        "Initialize a GPT partition table.",
        "device",
    ),
    (
        system_disk_app,
        "gpt-clear",
        "DELETE",
        "/disk/{device}/partition-table",
        "Clear a disk partition table.",
        "device",
    ),
    (
        system_disk_app,
        "partition-create",
        "POST",
        "/disk/{device}/partitions",
        "Create disk partitions.",
        "device",
    ),
    (
        system_disk_app,
        "smart-info",
        "GET",
        "/disk/smart/self-test",
        "Show SMART self-test information.",
    ),
    (system_disk_app, "smart-start", "POST", "/disk/smart/self-test", "Start a SMART self-test."),
    (
        system_disk_app,
        "smart-abort",
        "POST",
        "/disk/smart/self-test/abort",
        "Abort a SMART self-test.",
    ),
    (
        system_disk_app,
        "smart-schedules",
        "GET",
        "/disk/smart/self-test/schedules",
        "List SMART test schedules.",
    ),
    (
        system_disk_app,
        "smart-schedule-create",
        "POST",
        "/disk/smart/self-test/schedules",
        "Create a SMART test schedule.",
    ),
    (
        system_disk_app,
        "smart-schedule-set",
        "PUT",
        "/disk/smart/self-test/schedules/{id}",
        "Update a SMART test schedule.",
        "id",
    ),
    (
        system_disk_app,
        "smart-schedule-delete",
        "DELETE",
        "/disk/smart/self-test/schedules/{id}",
        "Delete a SMART test schedule.",
        "id",
    ),
    (system_app, "pci-list", "GET", "/system/pci-devices", "List PCI devices."),
    (system_ppt_app, "list", "GET", "/system/ppt-devices", "List managed PCI passthrough devices."),
    (system_ppt_app, "enable", "POST", "/system/ppt-devices", "Enable PCI passthrough."),
    (
        system_ppt_app,
        "import",
        "POST",
        "/system/ppt-devices/import",
        "Import a PCI passthrough device.",
    ),
    (system_ppt_app, "prepare", "POST", "/system/ppt-devices/prepare", "Prepare PCI passthrough."),
    (
        system_ppt_app,
        "disable",
        "DELETE",
        "/system/ppt-devices/{id}",
        "Disable PCI passthrough.",
        "id",
    ),
    (system_tunable_app, "list", "GET", "/system/tunables/remote", "List sysctl tunables."),
    (system_tunable_app, "set", "PUT", "/system/tunables", "Set a sysctl tunable."),
    (system_file_app, "list", "GET", "/system/file-explorer", "Browse files and folders."),
    (system_file_app, "create", "POST", "/system/file-explorer", "Create a file or folder."),
    (
        system_file_app,
        "copy-move",
        "POST",
        "/system/file-explorer/copy-or-move-batch",
        "Copy or move files.",
    ),
    (
        system_file_app,
        "delete",
        "POST",
        "/system/file-explorer/delete",
        "Delete files or folders.",
    ),
    (
        system_file_app,
        "rename",
        "POST",
        "/system/file-explorer/rename",
        "Rename a file or folder.",
    ),
    (
        system_file_app,
        "upload-revert",
        "DELETE",
        "/system/file-explorer/upload",
        "Revert an uploaded file.",
    ),
    (system_cert_app, "list", "GET", "/certificates", "List TLS certificates."),
    (system_cert_app, "create", "POST", "/certificates", "Create a TLS certificate."),
    (
        system_cert_app,
        "domain-check",
        "GET",
        "/certificates/domain-check",
        "Check certificate domain resolution.",
    ),
    (
        system_cert_app,
        "set",
        "PATCH",
        "/certificates/{id}",
        "Update a TLS certificate.",
        "id",
    ),
    (
        system_cert_app,
        "delete",
        "DELETE",
        "/certificates/{id}",
        "Delete a TLS certificate.",
        "id",
    ),
    (
        system_cert_app,
        "activate",
        "POST",
        "/certificates/{id}/activate",
        "Schedule certificate activation.",
        "id",
    ),
    (
        system_cert_app,
        "activate-cancel",
        "DELETE",
        "/certificates/{id}/activate",
        "Cancel certificate activation.",
        "id",
    ),
    (
        system_cert_app,
        "renew",
        "POST",
        "/certificates/{id}/renew",
        "Renew a TLS certificate.",
        "id",
    ),
    (
        system_cert_app,
        "retry",
        "POST",
        "/certificates/{id}/retry",
        "Retry certificate issuance.",
        "id",
    ),
    (system_app, "health-basic", "GET", "/health/basic", "Run a basic health check."),
    (system_app, "health-http", "GET", "/health/http", "Run an HTTP health check."),
]:
    _add(*spec)


@system_note_app.command("show")
def system_notes_show(
    ctx: typer.Context,
    note_id: Annotated[str, typer.Argument(help="Host note ID to display.")],
    node: NodeOption = None,
    fmt: FormatOption = OutputFormat.table,
    columns: ColumnsOption = None,
) -> None:
    """Display full details of a host note."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        notes = client.get("/info/notes", node=node) or []
    if isinstance(notes, list):
        for note in notes:
            if isinstance(note, dict) and str(note.get("id")) == note_id:
                print_dict(note, fmt=fmt, selected_columns=columns, title=f"Host Note {note_id}")
                return
    raise ResourceNotFoundError(f"Host note '{note_id}' not found.")


_add(
    system_file_app,
    "upload",
    "POST",
    "/system/file-explorer/upload",
    "Upload a file. Use --param path=/destination.",
    upload=True,
)
_add(
    system_file_app,
    "download",
    "GET",
    "/system/file-explorer/download",
    "Download a file. Use --param id=/absolute/path.",
    binary=True,
)
_add(
    system_cert_app,
    "archive",
    "GET",
    "/certificates/{id}/archive",
    "Download a certificate archive.",
    args_help="id",
    binary=True,
)


@system_app.command("events")
def system_events(
    ctx: typer.Context,
    lines: Annotated[
        int | None,
        typer.Option(
            "--lines",
            "-l",
            min=1,
            help="Stop after printing N non-empty event lines.",
        ),
    ] = None,
    reconnect: Annotated[
        bool,
        typer.Option(
            "--reconnect/--no-reconnect",
            help="Re-mint sse_token and reconnect if the event stream drops.",
        ),
    ] = True,
    param: Annotated[
        list[str] | None,
        typer.Option("--param", "-p", help="Query parameter KEY=VALUE (repeatable)."),
    ] = None,
    node: NodeOption = None,
) -> None:
    """Stream server-sent events using a short-lived sse_token capability."""
    state: CLIState = ctx.obj
    parsed_params = _parse_params(param) or {}
    explicit_token = parsed_params.get("sse_token")
    printed = 0
    with state.get_client(node_override=node) as client:
        while True:
            req_params = dict(parsed_params)
            if not explicit_token:
                req_params.pop("sse_token", None)
            try:
                for line in client.stream_lines("/events/stream", params=req_params, node=node):
                    console.print(line, markup=False)
                    if line.strip():
                        printed += 1
                        if lines is not None and printed >= lines:
                            return
                if not reconnect or lines is not None:
                    return
                time.sleep(1.5)
            except KeyboardInterrupt:
                return


@system_app.command("terminal")
def system_terminal(
    ctx: typer.Context,
    kill_on_exit: Annotated[
        bool,
        typer.Option(
            "--kill-on-exit/--keep-alive",
            help="Send a kill control frame to close the host shell on detach.",
        ),
    ] = True,
    node: NodeOption = None,
) -> None:
    """Attach to an interactive host shell on the target node over WebSocket."""
    state: CLIState = ctx.obj
    with state.get_client(node_override=node) as client:
        attach_console(
            client,
            "/info/terminal",
            node=node,
            takeover=False,
            kill_on_exit=kill_on_exit,
            banner="Attached to host terminal",
        )


# ---------------------------------------------------------------------------
# Samba
# ---------------------------------------------------------------------------
for spec in [  # type: ignore[assignment]
    (samba_config_app, "show", "GET", "/samba/config", "Show global Samba configuration."),
    (samba_config_app, "set", "PUT", "/samba/config", "Update global Samba configuration."),
    (samba_share_app, "list", "GET", "/samba/shares", "List Samba shares."),
    (samba_share_app, "create", "POST", "/samba/shares", "Create a Samba share."),
    (samba_share_app, "set", "PUT", "/samba/shares/{id}", "Update a Samba share.", "id"),
    (samba_share_app, "delete", "DELETE", "/samba/shares/{id}", "Delete a Samba share.", "id"),
    (
        samba_share_app,
        "enable",
        "PUT",
        "/samba/shares/{id}/enabled",
        "Enable or disable a Samba share.",
        "id",
    ),
    (samba_app, "audit-logs", "GET", "/samba/audit-logs", "Show Samba audit logs."),
]:
    _add(*spec)


# ---------------------------------------------------------------------------
# iSCSI
# ---------------------------------------------------------------------------
for spec in [  # type: ignore[assignment]
    (iscsi_config_app, "show", "GET", "/iscsi/config", "Show iSCSI global configuration."),
    (iscsi_config_app, "set", "PUT", "/iscsi/config", "Update iSCSI global configuration."),
    (iscsi_initiator_app, "list", "GET", "/iscsi/initiators", "List iSCSI initiators."),
    (iscsi_initiator_app, "create", "POST", "/iscsi/initiators", "Create an iSCSI initiator."),
    (
        iscsi_initiator_app,
        "set",
        "PUT",
        "/iscsi/initiators/{id}",
        "Update an iSCSI initiator.",
        "id",
    ),
    (
        iscsi_initiator_app,
        "delete",
        "DELETE",
        "/iscsi/initiators/{id}",
        "Delete an iSCSI initiator.",
        "id",
    ),
    (
        iscsi_initiator_app,
        "connect",
        "POST",
        "/iscsi/initiators/{id}/connect",
        "Connect an iSCSI initiator.",
        "id",
    ),
    (iscsi_app, "status", "GET", "/iscsi/status", "Show iSCSI initiator status."),
    (iscsi_app, "sessions", "GET", "/iscsi/target-sessions", "List iSCSI target sessions."),
    (iscsi_target_app, "list", "GET", "/iscsi/targets", "List iSCSI targets."),
    (iscsi_target_app, "create", "POST", "/iscsi/targets", "Create an iSCSI target."),
    (
        iscsi_target_app,
        "set",
        "PUT",
        "/iscsi/targets/{targetId}",
        "Update an iSCSI target.",
        "targetId",
    ),
    (
        iscsi_target_app,
        "delete",
        "DELETE",
        "/iscsi/targets/{targetId}",
        "Delete an iSCSI target.",
        "targetId",
    ),
    (
        iscsi_target_app,
        "lun-add",
        "POST",
        "/iscsi/targets/{targetId}/luns",
        "Add a target LUN.",
        "targetId",
    ),
    (
        iscsi_target_app,
        "lun-remove",
        "DELETE",
        "/iscsi/targets/{targetId}/luns/{lunId}",
        "Remove a target LUN.",
        "targetId lunId",
    ),
    (
        iscsi_target_app,
        "portal-add",
        "POST",
        "/iscsi/targets/{targetId}/portals",
        "Add a target portal.",
        "targetId",
    ),
    (
        iscsi_target_app,
        "portal-remove",
        "DELETE",
        "/iscsi/targets/{targetId}/portals/{portalId}",
        "Remove a target portal.",
        "targetId portalId",
    ),
]:
    _add(*spec)


# ---------------------------------------------------------------------------
# DDNS and mDNS
# ---------------------------------------------------------------------------
for spec in [  # type: ignore[assignment]
    (ddns_app, "list", "GET", "/dynamic-dns/entries", "List dynamic DNS entries."),
    (ddns_app, "create", "POST", "/dynamic-dns/entries", "Create a dynamic DNS entry."),
    (ddns_app, "set", "PUT", "/dynamic-dns/entries/{id}", "Update a dynamic DNS entry.", "id"),
    (
        ddns_app,
        "delete",
        "DELETE",
        "/dynamic-dns/entries/{id}",
        "Delete a dynamic DNS entry.",
        "id",
    ),
    (
        ddns_app,
        "sync",
        "POST",
        "/dynamic-dns/entries/{id}/sync",
        "Synchronize a dynamic DNS entry.",
        "id",
    ),
    (mdns_config_app, "show", "GET", "/mdns/config", "Show mDNS daemon configuration."),
    (mdns_config_app, "set", "PUT", "/mdns/config", "Update mDNS daemon configuration."),
    (mdns_record_app, "list", "GET", "/mdns/records", "List mDNS records."),
    (mdns_record_app, "create", "POST", "/mdns/records", "Create an mDNS record."),
    (mdns_record_app, "set", "PUT", "/mdns/records/{id}", "Update an mDNS record.", "id"),
    (mdns_record_app, "delete", "DELETE", "/mdns/records/{id}", "Delete an mDNS record.", "id"),
]:
    _add(*spec)


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------
for spec in [  # type: ignore[assignment]
    (notifications_app, "list", "GET", "/notifications", "List notifications."),
    (notifications_app, "count", "GET", "/notifications/count", "Count active notifications."),
    (
        notifications_app,
        "dismiss-all",
        "POST",
        "/notifications/dismiss-all",
        "Dismiss all notifications.",
    ),
    (
        notifications_app,
        "dismiss",
        "POST",
        "/notifications/{id}/dismiss",
        "Dismiss a notification.",
        "id",
    ),
    (notifications_rule_app, "list", "GET", "/notifications/rules", "List notification rules."),
    (
        notifications_rule_app,
        "set-all",
        "PUT",
        "/notifications/rules",
        "Update notification rules.",
    ),
    (
        notifications_rule_app,
        "create",
        "POST",
        "/notifications/rules",
        "Create a notification rule.",
    ),
    (
        notifications_rule_app,
        "set",
        "PUT",
        "/notifications/rules/{id}",
        "Update a notification rule.",
        "id",
    ),
    (
        notifications_rule_app,
        "delete",
        "DELETE",
        "/notifications/rules/{id}",
        "Delete a notification rule.",
        "id",
    ),
    (
        notifications_rule_app,
        "bulk-delete",
        "POST",
        "/notifications/rules/bulk-delete",
        "Bulk-delete notification rules.",
    ),
    (
        notifications_rule_app,
        "bulk-set",
        "POST",
        "/notifications/rules/bulk-update",
        "Bulk-update notification rules.",
    ),
    (
        notifications_rule_app,
        "test",
        "POST",
        "/notifications/rules/test",
        "Test a notification rule.",
    ),
    (
        notifications_transport_app,
        "list",
        "GET",
        "/notifications/transports",
        "List notification transports.",
    ),
    (
        notifications_transport_app,
        "create",
        "POST",
        "/notifications/transports",
        "Create a notification transport.",
    ),
    (
        notifications_transport_app,
        "set",
        "PUT",
        "/notifications/transports/{id}",
        "Update a notification transport.",
        "id",
    ),
    (
        notifications_transport_app,
        "delete",
        "DELETE",
        "/notifications/transports/{id}",
        "Delete a notification transport.",
        "id",
    ),
    (
        notifications_transport_app,
        "test",
        "POST",
        "/notifications/transports/{id}/test",
        "Test a notification transport.",
        "id",
    ),
]:
    _add(*spec)


# ---------------------------------------------------------------------------
# Users, groups, and auth
# ---------------------------------------------------------------------------
for spec in [  # type: ignore[assignment]
    (user_app, "list", "GET", "/auth/users", "List users."),
    (user_app, "create", "POST", "/auth/users", "Create a local user."),
    (
        user_app,
        "capabilities",
        "GET",
        "/auth/users/capabilities",
        "Show user-management capabilities.",
    ),
    (user_app, "import", "POST", "/auth/users/import", "Import a Unix user."),
    (user_app, "importable", "GET", "/auth/users/importable", "List importable Unix users."),
    (user_app, "pam-create", "POST", "/auth/users/pam", "Create a PAM user."),
    (user_app, "next-uid", "GET", "/auth/users/uid/next", "Show the next Unix UID."),
    (user_app, "set", "PUT", "/auth/users/{userId}", "Update a user.", "userId"),
    (user_app, "delete", "DELETE", "/auth/users/{userId}", "Delete a user.", "userId"),
    (
        user_passkey_app,
        "list",
        "GET",
        "/auth/users/{userId}/passkeys",
        "List user passkeys.",
        "userId",
    ),
    (
        user_passkey_app,
        "delete",
        "DELETE",
        "/auth/users/{userId}/passkeys/{credentialId}",
        "Delete a user passkey.",
        "userId credentialId",
    ),
    (group_app, "list", "GET", "/auth/groups", "List groups."),
    (group_app, "create", "POST", "/auth/groups", "Create a group."),
    (group_app, "delete", "DELETE", "/auth/groups/{groupId}", "Delete a group.", "groupId"),
    (
        group_app,
        "members",
        "PUT",
        "/auth/groups/{groupId}/members",
        "Replace group members.",
        "groupId",
    ),
    (auth_app, "login-config", "GET", "/auth/login/config", "Show login configuration."),
    (auth_app, "preferences", "GET", "/auth/preferences", "Show user preferences."),
    (auth_app, "sse-token", "POST", "/auth/sse-tokens", "Create an SSE token."),
    (
        auth_passkey_app,
        "login-begin",
        "POST",
        "/auth/passkeys/login/begin",
        "Begin passkey login.",
    ),
    (
        auth_passkey_app,
        "login-finish",
        "POST",
        "/auth/passkeys/login/finish",
        "Finish passkey login.",
    ),
    (
        auth_passkey_app,
        "register-begin",
        "POST",
        "/auth/passkeys/register/begin",
        "Begin passkey registration.",
    ),
    (
        auth_passkey_app,
        "register-finish",
        "POST",
        "/auth/passkeys/register/finish",
        "Finish passkey registration.",
    ),
    (
        cloud_init_template_app,
        "list",
        "GET",
        "/utilities/cloud-init/templates",
        "List cloud-init templates.",
    ),
    (
        cloud_init_template_app,
        "create",
        "POST",
        "/utilities/cloud-init/templates",
        "Create a cloud-init template.",
    ),
    (
        cloud_init_template_app,
        "set",
        "PUT",
        "/utilities/cloud-init/templates/{templateId}",
        "Update a cloud-init template.",
        "templateId",
    ),
    (
        cloud_init_template_app,
        "delete",
        "DELETE",
        "/utilities/cloud-init/templates/{templateId}",
        "Delete a cloud-init template.",
        "templateId",
    ),
]:
    _add(*spec)


# ---------------------------------------------------------------------------
# Containers (OCI / Podman)
# ---------------------------------------------------------------------------
for spec in [  # type: ignore[assignment]
    (container_app, "list", "GET", "/container", "List containers."),
    (container_app, "create", "POST", "/container", "Create a container."),
    (container_app, "show", "GET", "/container/{ocid}", "Show a container.", "ocid"),
    (container_app, "set", "PUT", "/container/{ocid}", "Update a container.", "ocid"),
    (container_app, "delete", "DELETE", "/container/{ocid}", "Delete a container.", "ocid"),
    (
        container_app,
        "start",
        "POST",
        "/container/{ocid}/actions/start",
        "Start a container.",
        "ocid",
    ),
    (
        container_app,
        "stop",
        "POST",
        "/container/{ocid}/actions/stop",
        "Stop a container.",
        "ocid",
    ),
    (
        container_app,
        "restart",
        "POST",
        "/container/{ocid}/actions/restart",
        "Restart a container.",
        "ocid",
    ),
    (
        container_app,
        "kill",
        "POST",
        "/container/{ocid}/actions/kill",
        "Kill a container.",
        "ocid",
    ),
    (
        container_app,
        "image-info",
        "GET",
        "/container/{ocid}/image",
        "Show container image metadata.",
        "ocid",
    ),
    (container_app, "logs", "GET", "/container/{ocid}/logs", "Show container logs.", "ocid"),
    (
        container_app,
        "options",
        "PATCH",
        "/container/{ocid}/options",
        "Update container boot and web options.",
        "ocid",
    ),
    (
        container_app,
        "stats",
        "GET",
        "/container/{ocid}/stats",
        "Show current container statistics.",
        "ocid",
    ),
    (
        container_app,
        "stats-step",
        "GET",
        "/container/{ocid}/stats/{step}",
        "Show container statistics for a step.",
        "ocid step",
    ),
    (container_app, "ports", "GET", "/container/ports", "List used host ports."),
    (container_app, "stack", "POST", "/container/stack", "Create a catalog app stack."),
    (
        container_image_app,
        "list",
        "GET",
        "/container/images/{pool}",
        "List container images on a pool.",
        "pool",
    ),
    (
        container_image_app,
        "pull",
        "POST",
        "/container/images/{pool}/pull",
        "Pull a container image to a pool.",
        "pool",
    ),
    (
        container_image_app,
        "prune",
        "POST",
        "/container/images/{pool}/prune",
        "Remove unused container images from a pool.",
        "pool",
    ),
    (
        container_image_app,
        "delete",
        "DELETE",
        "/container/images/{pool}/{id}",
        "Remove a container image from a pool.",
        "pool id",
    ),
    (container_network_app, "list", "GET", "/container/networks", "List container networks."),
    (container_network_app, "create", "POST", "/container/networks", "Create a container network."),
    (
        container_network_app,
        "delete",
        "DELETE",
        "/container/networks/{id}",
        "Delete a container network.",
        "id",
    ),
    (
        container_registry_app,
        "list",
        "GET",
        "/container/registry-credentials",
        "List container registry credentials.",
    ),
    (
        container_registry_app,
        "set",
        "PUT",
        "/container/registry-credentials",
        "Save a container registry credential.",
    ),
    (
        container_registry_app,
        "delete",
        "DELETE",
        "/container/registry-credentials/{id}",
        "Delete a container registry credential.",
        "id",
    ),
    (container_catalog_app, "list", "GET", "/container/catalog", "List catalog applications."),
    (
        container_catalog_app,
        "show",
        "GET",
        "/container/catalog/{source}/{id}",
        "Show catalog application settings.",
        "source id",
    ),
    (
        container_catalog_app,
        "render",
        "POST",
        "/container/catalog/{source}/{id}/render",
        "Render a catalog application plan.",
        "source id",
    ),
]:
    _add(*spec)

_add(
    container_catalog_app,
    "source-icon",
    "GET",
    "/container/catalog/{source}/icon",
    "Download a catalog source logo.",
    args_help="source",
    binary=True,
)
_add(
    container_catalog_app,
    "icon",
    "GET",
    "/container/catalog/{source}/{id}/icon",
    "Download a catalog application icon.",
    args_help="source id",
    binary=True,
)


@container_app.command("console")
def container_console(
    ctx: typer.Context,
    ocid: Annotated[int, typer.Argument(help="Container OCID.")],
    shell: Annotated[
        str | None,
        typer.Option("--shell", help="Shell executable inside the container."),
    ] = None,
    node: NodeOption = None,
) -> None:
    """Attach to a running container's interactive console over WebSocket."""
    state: CLIState = ctx.obj
    extra_params: dict[str, Any] | None = {"shell": shell} if shell else None
    with state.get_client(node_override=node) as client:
        attach_console(
            client,
            f"/container/{ocid}/console",
            node=node,
            extra_params=extra_params,
            takeover=False,
            banner=f"Attached to container {ocid} console",
        )


# ---------------------------------------------------------------------------
# Directory services (Active Directory and Kerberos)
# ---------------------------------------------------------------------------
for spec in [  # type: ignore[assignment]
    (
        directory_services_app,
        "principals",
        "GET",
        "/directory-services/principals",
        "Search Active Directory user or group principals.",
    ),
    (
        ds_ad_config_app,
        "show",
        "GET",
        "/directory-services/active-directory",
        "Show Active Directory configuration.",
    ),
    (
        ds_ad_config_app,
        "set",
        "PUT",
        "/directory-services/active-directory",
        "Update Active Directory configuration.",
    ),
    (
        ds_ad_app,
        "status",
        "GET",
        "/directory-services/active-directory/status",
        "Show cached Active Directory status.",
    ),
    (
        ds_ad_app,
        "check",
        "POST",
        "/directory-services/active-directory/check",
        "Check Active Directory trust and Winbind health.",
    ),
    (
        ds_ad_app,
        "enable",
        "PUT",
        "/directory-services/active-directory/enabled",
        "Enable or disable Active Directory.",
    ),
    (
        ds_ad_app,
        "join",
        "POST",
        "/directory-services/active-directory/join",
        "Join the configured Active Directory domain.",
    ),
    (
        ds_ad_app,
        "leave",
        "POST",
        "/directory-services/active-directory/leave",
        "Leave the Active Directory domain.",
    ),
    (
        ds_kerberos_config_app,
        "show",
        "GET",
        "/directory-services/kerberos/settings",
        "Show Kerberos defaults.",
    ),
    (
        ds_kerberos_config_app,
        "set",
        "PUT",
        "/directory-services/kerberos/settings",
        "Update Kerberos defaults.",
    ),
    (
        ds_kerberos_app,
        "realm-list",
        "GET",
        "/directory-services/kerberos/realms",
        "List Kerberos realms.",
    ),
    (
        ds_kerberos_app,
        "realm-create",
        "POST",
        "/directory-services/kerberos/realms",
        "Create a Kerberos realm.",
    ),
    (
        ds_kerberos_app,
        "realm-discover",
        "POST",
        "/directory-services/kerberos/realms/discover",
        "Discover Kerberos servers via DNS SRV records.",
    ),
    (
        ds_kerberos_app,
        "realm-set",
        "PUT",
        "/directory-services/kerberos/realms/{id}",
        "Update a Kerberos realm.",
        "id",
    ),
    (
        ds_kerberos_app,
        "realm-delete",
        "DELETE",
        "/directory-services/kerberos/realms/{id}",
        "Delete a Kerberos realm.",
        "id",
    ),
    (
        ds_kerberos_app,
        "keytab-list",
        "GET",
        "/directory-services/kerberos/keytabs",
        "List Kerberos keytabs.",
    ),
    (
        ds_kerberos_app,
        "keytab-create",
        "POST",
        "/directory-services/kerberos/keytabs",
        "Upload a Kerberos keytab.",
    ),
    (
        ds_kerberos_app,
        "keytab-set",
        "PUT",
        "/directory-services/kerberos/keytabs/{id}",
        "Update a Kerberos keytab.",
        "id",
    ),
    (
        ds_kerberos_app,
        "keytab-delete",
        "DELETE",
        "/directory-services/kerberos/keytabs/{id}",
        "Delete a Kerberos keytab.",
        "id",
    ),
]:
    _add(*spec)
