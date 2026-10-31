"""Create Bhyve virtual machines from scratch or from a VM template."""

from __future__ import annotations

import ipaddress
import json
import re
import secrets
import string
import sys
from pathlib import Path
from typing import Annotated, Any

import typer
import yaml

from sylve_cli.client import SylveAPIError, SylveClient, SylveError
from sylve_cli.formatter import OutputFormat, console, format_bytes, print_result
from sylve_cli.state import CLIState, FormatOption, NodeOption
from sylve_cli.tasks import wait_for_lifecycle_task

_VM_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]+$")
_SIZE_RE = re.compile(r"^\s*(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>[a-zA-Z]*)\s*$")
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

_STORAGE_TYPES = {"raw", "zvol", "image", "filesystem", "none"}
_STORAGE_EMULATIONS = {"virtio-blk", "virtio-9p", "ahci-hd", "ahci-cd", "nvme"}
_BOOT_ROMS = {"uefi", "uboot", "none"}
_TIME_OFFSETS = {"utc", "localtime"}

_SIZE_UNITS = {
    "": 1,
    "b": 1,
    "byte": 1,
    "bytes": 1,
    "k": 1024,
    "kb": 1024,
    "kib": 1024,
    "m": 1024**2,
    "mb": 1024**2,
    "mib": 1024**2,
    "g": 1024**3,
    "gb": 1024**3,
    "gib": 1024**3,
    "t": 1024**4,
    "tb": 1024**4,
    "tib": 1024**4,
    "p": 1024**5,
    "pb": 1024**5,
    "pib": 1024**5,
}

_SCRATCH_API_KEYS = {
    "name",
    "rid",
    "description",
    "cpuSockets",
    "cpuCores",
    "cpuThreads",
    "ram",
    "tpmEmulation",
    "serial",
    "vncEnabled",
    "vncBind",
    "vncPort",
    "vncPassword",
    "vncResolution",
    "vncWait",
    "startAtBoot",
    "startOrder",
    "timeOffset",
    "apic",
    "acpi",
    "cloudInit",
    "cloudInitData",
    "cloudInitMetaData",
    "cloudInitNetworkConfig",
    "bootRom",
    "extraBhyveOptions",
    "ignoreUMSR",
    "qemuGuestAgent",
    "storageType",
    "storagePool",
    "storageSize",
    "storageEmulationType",
    "iso",
    "switchName",
    "switchEmulationType",
    "macId",
    "pciDevices",
    "cpuPinning",
}

_SCRATCH_ALIASES = {
    "cores": "cpuCores",
    "cpu": "cpuCores",
    "sockets": "cpuSockets",
    "threads": "cpuThreads",
    "memory": "ram",
    "tpm": "tpmEmulation",
    "ignore_umsr": "ignoreUMSR",
    "ignore_umsrs": "ignoreUMSR",
    "qemu_guest_agent": "qemuGuestAgent",
    "start_at_boot": "startAtBoot",
    "start_order": "startOrder",
    "time_offset": "timeOffset",
    "boot_rom": "bootRom",
    "extra_bhyve_options": "extraBhyveOptions",
    "pci_devices": "pciDevices",
    "storage_type": "storageType",
    "storage_pool": "storagePool",
    "pool": "storagePool",
    "disk_size": "storageSize",
    "storage_size": "storageSize",
    "storage_emulation": "storageEmulationType",
    "switch": "switchName",
    "switch_emulation": "switchEmulationType",
    "mac": "macId",
    "mac_object": "macId",
    "mac_id": "macId",
    "vnc_enabled": "vncEnabled",
    "vnc_bind": "vncBind",
    "vnc_port": "vncPort",
    "vnc_password": "vncPassword",
    "vnc_resolution": "vncResolution",
    "vnc_wait": "vncWait",
    "cloud_init": "cloudInit",
    "cloud_init_data": "cloudInitData",
    "cloud_init_meta_data": "cloudInitMetaData",
    "cloud_init_network_config": "cloudInitNetworkConfig",
    "user_data": "cloudInitData",
    "meta_data": "cloudInitMetaData",
    "network_config": "cloudInitNetworkConfig",
}

_TEMPLATE_ALIASES = {
    "template_id": "template",
    "templateId": "template",
    "start_rid": "startRid",
    "startRid": "startRid",
    "name_prefix": "namePrefix",
    "namePrefix": "namePrefix",
    "storage_pools": "storagePools",
    "storagePools": "storagePools",
    "rewrite_cloud_init_identity": "rewriteCloudInitIdentity",
    "rewriteCloudInitIdentity": "rewriteCloudInitIdentity",
    "cloud_init_prefix": "cloudInitPrefix",
    "cloudInitPrefix": "cloudInitPrefix",
}


def _parse_size(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise SylveError(f"Invalid {field}: {value!r}. Use a size like 2G or 512M.")
    if isinstance(value, (int, float)):
        size = int(value)
    else:
        text = str(value).strip()
        match = _SIZE_RE.match(text)
        if match is None:
            raise SylveError(f"Invalid {field}: '{value}'. Use a size like 2G or 512M.")
        number = float(match.group("value"))
        unit = match.group("unit").lower()
        if unit not in _SIZE_UNITS:
            raise SylveError(f"Invalid {field} unit '{unit}'. Use B, K, M, G, or T.")
        size = int(number * _SIZE_UNITS[unit])
    if size <= 0:
        raise SylveError(f"{field} must be greater than zero.")
    return size


def _as_int(value: Any, field: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise SylveError(f"Invalid {field}: {value!r}.") from exc


def _as_bool(value: Any, field: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    raise SylveError(f"Invalid {field}: {value!r}.")


def _load_config(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SylveError(f"Could not read config file '{path}': {exc}") from exc

    try:
        if path.suffix.lower() == ".json":
            data = json.loads(text)
        else:
            data = yaml.safe_load(text)
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        raise SylveError(f"Could not parse config file '{path}': {exc}") from exc

    if not isinstance(data, dict):
        raise SylveError(f"Config file '{path}' must contain a YAML/JSON object.")
    return data


def _read_text_value(value: Any, field: str) -> str:
    if value is None:
        return ""
    text = str(value)
    candidate = Path(text).expanduser()
    looks_like_path = text.startswith((".", "/", "~")) or text.lower().endswith((".yaml", ".yml"))
    if "\n" not in text and candidate.is_file():
        try:
            return candidate.read_text(encoding="utf-8")
        except OSError as exc:
            raise SylveError(f"Could not read {field} from '{candidate}': {exc}") from exc
    if looks_like_path and "\n" not in text:
        raise SylveError(f"{field} file '{candidate}' does not exist.")
    return text


def _validate_yaml(text: str, field: str) -> None:
    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise SylveError(f"{field} is not valid YAML: {exc}") from exc
    if parsed is None:
        raise SylveError(f"{field} is empty.")


def _config_to_scratch_payload(cfg: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}

    for key in _SCRATCH_API_KEYS:
        if key in cfg and cfg[key] is not None:
            payload[key] = cfg[key]

    for source, target in _SCRATCH_ALIASES.items():
        if source in cfg and cfg[source] is not None and target not in payload:
            payload[target] = cfg[source]

    cpu = cfg.get("cpu")
    if not isinstance(cpu, dict):
        cpu = cfg.get("hardware") if isinstance(cfg.get("hardware"), dict) else {}
    if isinstance(cpu, dict):
        if "sockets" in cpu:
            payload["cpuSockets"] = cpu["sockets"]
        if "cores" in cpu:
            payload["cpuCores"] = cpu["cores"]
        if "threads" in cpu:
            payload["cpuThreads"] = cpu["threads"]
        if "memory" in cpu:
            payload["ram"] = cpu["memory"]

    storage = cfg.get("storage")
    if isinstance(storage, dict):
        for source, target in {
            "type": "storageType",
            "pool": "storagePool",
            "size": "storageSize",
            "disk_size": "storageSize",
            "emulation": "storageEmulationType",
            "iso": "iso",
        }.items():
            if source in storage and storage[source] is not None:
                payload[target] = storage[source]

    network = cfg.get("network")
    if isinstance(network, dict):
        for source, target in {
            "switch": "switchName",
            "switch_name": "switchName",
            "emulation": "switchEmulationType",
            "switch_emulation": "switchEmulationType",
            "mac": "macId",
            "mac_object": "macId",
            "mac_id": "macId",
        }.items():
            if source in network and network[source] is not None:
                payload[target] = network[source]

    vnc = cfg.get("vnc")
    if isinstance(vnc, dict):
        for source, target in {
            "enabled": "vncEnabled",
            "bind": "vncBind",
            "port": "vncPort",
            "password": "vncPassword",
            "resolution": "vncResolution",
            "wait": "vncWait",
        }.items():
            if source in vnc and vnc[source] is not None:
                payload[target] = vnc[source]

    cloud_init = cfg.get("cloud_init")
    if not isinstance(cloud_init, dict) and isinstance(cfg.get("cloudInit"), dict):
        cloud_init = cfg["cloudInit"]
    if isinstance(cloud_init, dict):
        if "enabled" in cloud_init:
            payload["cloudInit"] = cloud_init["enabled"]
        for source, target in {
            "user_data": "cloudInitData",
            "userdata": "cloudInitData",
            "userData": "cloudInitData",
            "meta_data": "cloudInitMetaData",
            "metadata": "cloudInitMetaData",
            "metaData": "cloudInitMetaData",
            "network_config": "cloudInitNetworkConfig",
            "networkconfig": "cloudInitNetworkConfig",
            "networkConfig": "cloudInitNetworkConfig",
        }.items():
            if source in cloud_init and cloud_init[source] is not None:
                payload[target] = cloud_init[source]

    boot = cfg.get("boot")
    if isinstance(boot, dict):
        for source, target in {
            "rom": "bootRom",
            "boot_rom": "bootRom",
            "start_at_boot": "startAtBoot",
            "start_order": "startOrder",
        }.items():
            if source in boot and boot[source] is not None:
                payload[target] = boot[source]

    options = cfg.get("options")
    if isinstance(options, dict):
        for source, target in {
            "serial": "serial",
            "tpm": "tpmEmulation",
            "tpm_emulation": "tpmEmulation",
            "qemu_guest_agent": "qemuGuestAgent",
            "ignore_umsr": "ignoreUMSR",
            "ignore_umsrs": "ignoreUMSR",
            "apic": "apic",
            "acpi": "acpi",
            "time_offset": "timeOffset",
            "extra_bhyve_options": "extraBhyveOptions",
            "pci_devices": "pciDevices",
            "cpu_pinning": "cpuPinning",
        }.items():
            if source in options and options[source] is not None:
                payload[target] = options[source]

    return _coerce_scratch_values(payload)


def _coerce_scratch_values(payload: dict[str, Any]) -> dict[str, Any]:
    for key in ("ram", "storageSize"):
        if key in payload:
            payload[key] = _parse_size(payload[key], "memory" if key == "ram" else "disk size")

    for key in ("rid", "cpuSockets", "cpuCores", "cpuThreads", "vncPort", "startOrder"):
        if key in payload and payload[key] not in (None, ""):
            payload[key] = _as_int(payload[key], key)

    for key in (
        "tpmEmulation",
        "serial",
        "vncEnabled",
        "vncWait",
        "startAtBoot",
        "apic",
        "acpi",
        "cloudInit",
        "ignoreUMSR",
        "qemuGuestAgent",
        "wol",
    ):
        if key in payload and payload[key] is not None:
            payload[key] = _as_bool(payload[key], key)

    for key in ("storageType", "storageEmulationType", "timeOffset", "bootRom"):
        if key in payload and payload[key] is not None:
            payload[key] = str(payload[key]).strip().lower()

    if "pciDevices" in payload and isinstance(payload["pciDevices"], str):
        payload["pciDevices"] = [
            item.strip() for item in payload["pciDevices"].split(",") if item.strip()
        ]
    if "extraBhyveOptions" in payload and isinstance(payload["extraBhyveOptions"], str):
        payload["extraBhyveOptions"] = [
            item.strip() for item in payload["extraBhyveOptions"].split() if item.strip()
        ]
    return payload


def _config_to_template_payload(cfg: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for source, target in _TEMPLATE_ALIASES.items():
        if source in cfg and cfg[source] is not None:
            payload[target] = cfg[source]
    for key in ("mode", "rid", "name", "startRid", "count", "namePrefix"):
        if key in cfg and cfg[key] is not None:
            payload[key] = cfg[key]
    if "storagePools" in payload:
        payload["storagePools"] = _normalize_storage_pools(payload["storagePools"])
    if "pool" in cfg and cfg["pool"] is not None:
        payload["_pool"] = cfg["pool"]
    if "storage_pool" in cfg and cfg["storage_pool"] is not None:
        payload["_storage_pool"] = cfg["storage_pool"]
    return payload


def _normalize_storage_pools(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, dict):
        return [
            {"sourceStorageId": _as_int(source, "sourceStorageId"), "pool": str(pool)}
            for source, pool in value.items()
        ]
    if isinstance(value, list):
        result: list[dict[str, Any]] = []
        for item in value:
            if not isinstance(item, dict):
                raise SylveError("storagePools entries must be objects.")
            source = item.get("sourceStorageId", item.get("source_storage_id", item.get("id")))
            pool = item.get("pool")
            if source is None or not pool:
                raise SylveError("Each storagePools entry needs sourceStorageId and pool.")
            result.append(
                {"sourceStorageId": _as_int(source, "sourceStorageId"), "pool": str(pool)}
            )
        return result
    raise SylveError("storagePools must be a list or a mapping of sourceStorageId to pool.")


def _resolve_host(client: SylveClient, node: str | None) -> str:
    host = client.resolve_node_hostname(node)
    if not host:
        host = client.context.hostname or ""
    if not host:
        nodes = client.get_online_nodes()
        if len(nodes) == 1:
            host = str(nodes[0].get("hostname") or "")
    if not host:
        raise SylveError("No target node selected. Pass --node <hostname>.")
    return host


def _next_guest_id(client: SylveClient) -> int:
    max_id = 0
    try:
        for node in client.get_cluster_nodes():
            for guest_id in node.get("guestIDs") or []:
                try:
                    max_id = max(max_id, int(guest_id))
                except (TypeError, ValueError):
                    continue
    except SylveError:
        pass

    if max_id == 0:
        try:
            for node_res in client.get_cluster_resources():
                for guest in node_res.get("vms") or []:
                    if isinstance(guest, dict) and guest.get("rid") is not None:
                        max_id = max(max_id, int(guest["rid"]))
                for guest in node_res.get("jails") or []:
                    if isinstance(guest, dict) and guest.get("ctId") is not None:
                        max_id = max(max_id, int(guest["ctId"]))
        except SylveError:
            pass

    next_id = 100 if max_id < 100 else max_id + 1
    if next_id > 9999:
        raise SylveError(
            "No free guest IDs remain in the 1-9999 range. "
            "Pass --rid explicitly or delete an unused guest."
        )
    return next_id


def _list_pools(client: SylveClient, host: str) -> list[dict[str, Any]]:
    try:
        data = client.get("/zfs/pools", node=host)
    except SylveError:
        return []
    if not isinstance(data, list):
        return []
    return [pool for pool in data if isinstance(pool, dict) and pool.get("name")]


def _resolve_pool(client: SylveClient, host: str, requested: Any) -> tuple[str, dict[str, Any]]:
    pools = _list_pools(client, host)
    if not pools:
        raise SylveError(f"No usable ZFS pools found on '{host}'.")

    if requested:
        wanted = str(requested).strip().lower()
        for pool in pools:
            if str(pool.get("name") or "").lower() == wanted:
                return str(pool["name"]), pool
        names = ", ".join(str(pool.get("name")) for pool in pools)
        raise SylveError(f"ZFS pool '{requested}' not found on '{host}'. Available: {names}.")

    if len(pools) == 1:
        pool = pools[0]
        return str(pool["name"]), pool

    names = ", ".join(str(pool.get("name")) for pool in pools)
    raise SylveError(
        f"Multiple ZFS pools are available on '{host}'; pass --pool. Available: {names}."
    )


def _list_switches(client: SylveClient, host: str) -> list[str]:
    try:
        data = client.get("/network/switch", node=host)
    except SylveError:
        return []
    if not isinstance(data, dict):
        return []
    names: list[str] = []
    for key in ("standard", "manual"):
        for switch in data.get(key) or []:
            if isinstance(switch, dict) and switch.get("name"):
                names.append(str(switch["name"]))
    return names


def _resolve_switch(client: SylveClient, host: str, requested: Any) -> str:
    switches = _list_switches(client, host)
    wanted = str(requested).strip().lower()
    for name in switches:
        if name.lower() == wanted:
            return name
    available = ", ".join(switches) if switches else "none"
    raise SylveError(f"Network switch '{requested}' not found on '{host}'. Available: {available}.")


def _resolve_iso(client: SylveClient, host: str, requested: Any) -> str | None:
    if requested is None:
        return None
    ident = str(requested).strip()
    if not ident or ident.lower() == "none":
        return None

    try:
        downloads = client.get("/utilities/downloads", node=host)
    except SylveError:
        downloads = []
    ident_lower = ident.lower()
    for item in downloads if isinstance(downloads, list) else []:
        if not isinstance(item, dict):
            continue
        values = {
            str(item.get("uuid") or "").lower(),
            str(item.get("name") or "").lower(),
            str(item.get("id") or "").lower(),
        }
        if ident_lower in values:
            uuid = str(item.get("uuid") or "")
            if not uuid:
                raise SylveError(f"Download '{item.get('name')}' has no UUID.")
            return uuid

    if _UUID_RE.fullmatch(ident):
        return ident

    names = [
        str(item.get("name") or item.get("uuid") or "")
        for item in (downloads if isinstance(downloads, list) else [])
        if isinstance(item, dict)
    ]
    available = ", ".join(name for name in names if name) or "none"
    raise SylveError(f"ISO/download '{requested}' not found on '{host}'. Available: {available}.")


def _resolve_mac_id(client: SylveClient, host: str, requested: Any) -> int | None:
    if requested is None or str(requested).strip() == "":
        return None
    text = str(requested).strip()
    if text.isdigit():
        return int(text)

    try:
        objects = client.get("/network/object", node=host)
    except SylveError:
        objects = []
    for obj in objects if isinstance(objects, list) else []:
        if not isinstance(obj, dict):
            continue
        if str(obj.get("type") or "").lower() != "mac":
            continue
        if str(obj.get("name") or "").lower() == text.lower():
            if obj.get("id") is None:
                break
            return int(obj["id"])
    raise SylveError(f"MAC object '{requested}' not found on '{host}'.")


def _resolve_pci_devices(client: SylveClient, host: str, requested: list[str] | None) -> list[int]:
    if not requested:
        return []
    try:
        devices = client.get("/system/ppt-devices", node=host)
    except SylveError:
        devices = []

    by_name: dict[str, int] = {}
    for device in devices if isinstance(devices, list) else []:
        if not isinstance(device, dict) or device.get("id") is None:
            continue
        device_id = int(device["id"])
        for key in ("deviceID", "deviceId", "name"):
            key_text = str(device.get(key) or "").strip().lower()
            if key_text:
                by_name[key_text] = device_id

    result: list[int] = []
    for item in requested:
        text = str(item).strip()
        if not text:
            continue
        if text.isdigit():
            pci_id = int(text)
        else:
            pci_id = by_name.get(text.lower(), 0)
            if pci_id == 0:
                raise SylveError(f"PCI passthrough device '{item}' not found on '{host}'.")
        if pci_id not in result:
            result.append(pci_id)
    return result


def _next_vnc_port(client: SylveClient, host: str) -> int:
    used: set[int] = set()
    try:
        vms = client.get("/vm", node=host)
    except SylveError:
        vms = []
    for vm in vms if isinstance(vms, list) else []:
        if not isinstance(vm, dict) or vm.get("vncEnabled") is False:
            continue
        port = vm.get("vncPort", vm.get("vnc_port"))
        try:
            if port:
                used.add(int(port))
        except (TypeError, ValueError):
            continue
    for port in range(5900, 6000):
        if port not in used:
            return port
    raise SylveError("No free VNC port found in the 5900-5999 range; pass --vnc-port.")


def _generate_vnc_password() -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(12))


def _validate_vnc_bind(value: str) -> None:
    try:
        ipaddress.ip_address(value)
    except ValueError as exc:
        raise SylveError(
            f"Invalid VNC bind address '{value}'. Use an IP like 127.0.0.1 or 0.0.0.0."
        ) from exc


def _friendly_create_error(exc: SylveAPIError) -> str:
    combined = f"{exc.error_code} {str(exc)}".lower()
    mappings = (
        ("rid_or_name_already_in_use", "RID or VM name is already in use."),
        ("vm_name_already_in_use", "VM name is already in use."),
        ("guest_id_already_in_use", "RID is already used by another guest."),
        ("template_not_found", "The selected VM template was not found."),
        ("template_has_no_cloneable_storage", "The template has no cloneable storage."),
        ("template_storage_dataset", "The template storage dataset is missing or unavailable."),
        ("template_network_switch_not_found", "A switch used by the template no longer exists."),
        ("invalid_rid_range", "The template RID range is invalid."),
        ("rid_range_contains_used_values", "One or more requested RIDs are already in use."),
        ("insufficient_pool_space", "Not enough free space in the selected pool."),
        ("pool_not_found", "The selected storage pool was not found."),
        ("storage_size_greater_than_available", "Not enough free space in the pool."),
        ("disk_size_must_be_greater_than_128mb", "Disk size must be at least 128 MiB."),
        ("size_should_be_at_least", "Disk size is below the minimum supported size."),
        ("memory_must_be_greater_than_128mb", "Memory must be at least 128 MiB."),
        ("image_not_resolvable", "The selected ISO/image could not be resolved."),
        ("media_not_cloud_init_capable", "The selected ISO is not a cloud-init image."),
        ("cloud_init_requires_iso", "Cloud-init requires an ISO."),
        ("cloud_init_requires_storage", "Cloud-init requires a primary disk."),
        ("cloud_init_data_missing", "Cloud-init user-data and meta-data are required."),
        ("invalid_cloud_init_yaml", "Cloud-init user-data or meta-data is invalid YAML."),
        ("vnc_port_already_in_use_by_another_vm", "That VNC port is already used by another VM."),
        ("vnc_port_already_in_use_by_another_service", "That VNC port is already in use."),
        ("switch_not_found", "The selected network switch was not found."),
        ("no_switch_emulation_type_selected", "A network emulation type is required."),
        ("no_emulation_type_selected", "A storage emulation type is required."),
        ("no_pool_selected_for", "A storage pool is required."),
    )
    for code, message in mappings:
        if code in combined:
            return message
    return str(exc) or "VM creation failed."


def _apply_scratch_flags(payload: dict[str, Any], **flags: Any) -> None:
    mapping = {
        "name": "name",
        "rid": "rid",
        "description": "description",
        "sockets": "cpuSockets",
        "threads": "cpuThreads",
        "storage_type": "storageType",
        "pool": "storagePool",
        "disk_size": "storageSize",
        "storage_emulation": "storageEmulationType",
        "iso": "iso",
        "switch": "switchName",
        "switch_emulation": "switchEmulationType",
        "mac_object": "macId",
        "vnc_bind": "vncBind",
        "vnc_port": "vncPort",
        "vnc_password": "vncPassword",
        "vnc_resolution": "vncResolution",
        "vnc_wait": "vncWait",
        "serial": "serial",
        "tpm": "tpmEmulation",
        "qemu_guest_agent": "qemuGuestAgent",
        "ignore_umsr": "ignoreUMSR",
        "apic": "apic",
        "acpi": "acpi",
        "boot_rom": "bootRom",
        "time_offset": "timeOffset",
        "start_at_boot": "startAtBoot",
        "start_order": "startOrder",
    }
    for source, target in mapping.items():
        value = flags.get(source)
        if value is not None:
            payload[target] = value

    if flags.get("cpu") is not None:
        payload["cpuCores"] = flags["cpu"]
    if flags.get("memory") is not None:
        payload["ram"] = flags["memory"]
    if flags.get("cloud_init") is not None:
        payload["cloudInit"] = flags["cloud_init"]
    if flags.get("vnc") is not None:
        payload["vncEnabled"] = flags["vnc"]
    if flags.get("pci_device") is not None:
        payload["pciDevices"] = list(flags["pci_device"])
    if flags.get("extra_bhyve_option") is not None:
        payload["extraBhyveOptions"] = list(flags["extra_bhyve_option"])
    if flags.get("user_data") is not None:
        payload["cloudInitData"] = _read_text_value(flags["user_data"], "user-data")
    if flags.get("meta_data") is not None:
        payload["cloudInitMetaData"] = _read_text_value(flags["meta_data"], "meta-data")
    if flags.get("network_config") is not None:
        payload["cloudInitNetworkConfig"] = _read_text_value(
            flags["network_config"], "network-config"
        )

    _coerce_scratch_values(payload)


def _normalize_scratch_payload(
    client: SylveClient,
    host: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    name = str(payload.get("name") or "").strip()
    if not name:
        raise SylveError("VM name is required. Pass it as NAME or --name.")
    if not _VM_NAME_RE.fullmatch(name):
        raise SylveError("VM names may contain only letters, numbers, '-' and '_'.")
    payload["name"] = name

    rid = payload.get("rid")
    if rid in (None, "", 0, "0"):
        rid = _next_guest_id(client)
    rid = _as_int(rid, "RID")
    if not 1 <= rid <= 9999:
        raise SylveError("RID must be between 1 and 9999.")
    payload["rid"] = rid

    description = str(payload.get("description") or "")
    if len(description) > 1024:
        raise SylveError("Description must be 1024 characters or fewer.")
    if description:
        payload["description"] = description
    else:
        payload.pop("description", None)

    for key, default in (("cpuSockets", 1), ("cpuCores", 1), ("cpuThreads", 1)):
        value = _as_int(payload.get(key, default), key)
        if value < 1:
            raise SylveError(f"{key} must be at least 1.")
        payload[key] = value

    ram = _parse_size(payload.get("ram", 1024**3), "memory")
    if ram < 128 * 1024**2:
        raise SylveError("Memory must be at least 128 MiB.")
    payload["ram"] = ram

    time_offset = str(payload.get("timeOffset") or "utc").strip().lower()
    if time_offset not in _TIME_OFFSETS:
        raise SylveError("--time-offset must be 'utc' or 'localtime'.")
    payload["timeOffset"] = time_offset

    boot_rom = str(payload.get("bootRom") or "uefi").strip().lower()
    if boot_rom not in _BOOT_ROMS:
        raise SylveError("--boot-rom must be 'uefi', 'uboot', or 'none'.")
    payload["bootRom"] = boot_rom

    storage_type = str(payload.get("storageType") or "zvol").strip().lower()
    if storage_type not in _STORAGE_TYPES:
        raise SylveError("storageType must be one of: " + ", ".join(sorted(_STORAGE_TYPES)) + ".")
    payload["storageType"] = storage_type

    pool: dict[str, Any] | None = None
    if storage_type != "none":
        pool_name, pool = _resolve_pool(client, host, payload.get("storagePool"))
        payload["storagePool"] = pool_name
        size = _parse_size(payload.get("storageSize", 1024**3), "disk size")
        if size < 128 * 1024**2:
            raise SylveError("Disk size must be at least 128 MiB.")
        if pool.get("free") is not None and size > int(pool["free"]):
            raise SylveError(
                f"Not enough free space in pool '{pool_name}' "
                f"({format_bytes(pool.get('free'))} available)."
            )
        payload["storageSize"] = size
        emulation = str(payload.get("storageEmulationType") or "virtio-blk").strip().lower()
        if emulation not in _STORAGE_EMULATIONS:
            raise SylveError(
                "storageEmulationType must be one of: "
                + ", ".join(sorted(_STORAGE_EMULATIONS))
                + "."
            )
        payload["storageEmulationType"] = emulation
    else:
        for key in ("storagePool", "storageSize", "storageEmulationType"):
            payload.pop(key, None)

    iso = _resolve_iso(client, host, payload.get("iso"))
    if iso:
        payload["iso"] = iso
    else:
        payload.pop("iso", None)

    switch_name = payload.get("switchName")
    if switch_name is None or str(switch_name).strip().lower() in ("", "none"):
        for key in ("switchName", "switchEmulationType", "macId"):
            payload.pop(key, None)
    else:
        canonical = _resolve_switch(client, host, switch_name)
        payload["switchName"] = canonical
        emulation = str(payload.get("switchEmulationType") or "virtio").strip()
        if not emulation:
            raise SylveError("A network emulation type is required.")
        payload["switchEmulationType"] = emulation
        mac_id = _resolve_mac_id(client, host, payload.get("macId"))
        if mac_id is not None:
            payload["macId"] = mac_id
        else:
            payload.pop("macId", None)

    vnc_enabled = payload.get("vncEnabled")
    vnc_enabled = True if vnc_enabled is None else _as_bool(vnc_enabled, "vncEnabled")
    if vnc_enabled:
        bind = str(payload.get("vncBind") or "127.0.0.1").strip()
        _validate_vnc_bind(bind)
        payload["vncBind"] = bind
        port = payload.get("vncPort")
        if port in (None, "", 0, "0"):
            port = _next_vnc_port(client, host)
        port = _as_int(port, "vncPort")
        if not 1 <= port <= 65535:
            raise SylveError("VNC port must be between 1 and 65535.")
        payload["vncPort"] = port
        resolution = str(payload.get("vncResolution") or "640x480").strip()
        if not resolution:
            raise SylveError("A VNC resolution is required.")
        payload["vncResolution"] = resolution
        password = str(payload.get("vncPassword") or _generate_vnc_password())
        if "," in password:
            raise SylveError("VNC passwords cannot contain commas.")
        payload["vncPassword"] = password
        payload["vncWait"] = _as_bool(payload.get("vncWait", False), "vncWait")
        payload["vncEnabled"] = True
    else:
        payload["vncEnabled"] = False
        for key in ("vncBind", "vncPort", "vncPassword", "vncResolution", "vncWait"):
            payload.pop(key, None)

    cloud_init = _as_bool(payload.get("cloudInit", False), "cloudInit")
    user_data = _read_text_value(payload.get("cloudInitData"), "cloud-init user-data")
    meta_data = _read_text_value(payload.get("cloudInitMetaData"), "cloud-init meta-data")
    network_config = _read_text_value(
        payload.get("cloudInitNetworkConfig"), "cloud-init network-config"
    )
    if not cloud_init and (user_data or meta_data or network_config):
        cloud_init = True
    if cloud_init:
        if storage_type == "none":
            raise SylveError("Cloud-init requires a primary disk.")
        if not payload.get("iso"):
            raise SylveError("Cloud-init requires --iso with a cloud-init capable image.")
        if not user_data or not meta_data:
            raise SylveError("Cloud-init requires both user-data and meta-data.")
        _validate_yaml(user_data, "cloud-init user-data")
        _validate_yaml(meta_data, "cloud-init meta-data")
        if network_config:
            _validate_yaml(network_config, "cloud-init network-config")
        payload["cloudInit"] = True
        payload["cloudInitData"] = user_data
        payload["cloudInitMetaData"] = meta_data
        if network_config:
            payload["cloudInitNetworkConfig"] = network_config
        else:
            payload.pop("cloudInitNetworkConfig", None)
    else:
        payload["cloudInit"] = False
        for key in (
            "cloudInitData",
            "cloudInitMetaData",
            "cloudInitNetworkConfig",
        ):
            payload.pop(key, None)

    for key, default in (
        ("serial", False),
        ("tpmEmulation", False),
        ("qemuGuestAgent", False),
        ("ignoreUMSR", False),
        ("apic", True),
        ("acpi", True),
        ("startAtBoot", False),
    ):
        payload[key] = _as_bool(payload.get(key, default), key)

    start_order = _as_int(payload.get("startOrder", 0), "startOrder")
    if start_order < 0:
        raise SylveError("startOrder must be 0 or greater.")
    payload["startOrder"] = start_order

    payload["pciDevices"] = _resolve_pci_devices(client, host, payload.get("pciDevices"))

    extra = payload.get("extraBhyveOptions")
    if extra is None:
        payload["extraBhyveOptions"] = []
    elif isinstance(extra, list):
        payload["extraBhyveOptions"] = [str(item) for item in extra if str(item).strip()]
    else:
        payload["extraBhyveOptions"] = [str(extra)] if str(extra).strip() else []

    if "cpuPinning" not in payload:
        payload["cpuPinning"] = []

    return {key: value for key, value in payload.items() if value is not None}


def _resolve_template(
    client: SylveClient,
    host: str,
    identifier: Any,
) -> tuple[int, str]:
    text = str(identifier).strip()
    if text.isdigit():
        return int(text), text

    try:
        templates = client.get("/vm/templates", node=host)
    except SylveError:
        templates = []
    for template in templates if isinstance(templates, list) else []:
        if not isinstance(template, dict):
            continue
        name = str(template.get("name") or "")
        if name.lower() == text.lower() and template.get("id") is not None:
            return int(template["id"]), name

    names = [
        str(template.get("name") or template.get("id") or "")
        for template in (templates if isinstance(templates, list) else [])
        if isinstance(template, dict)
    ]
    available = ", ".join(name for name in names if name) or "none"
    raise SylveError(f"VM template '{identifier}' not found on '{host}'. Available: {available}.")


def _template_detail(client: SylveClient, host: str, template_id: int) -> dict[str, Any]:
    try:
        detail = client.get(f"/vm/templates/{template_id}", node=host)
    except SylveError:
        return {}
    return detail if isinstance(detail, dict) else {}


def _template_storage_mappings(
    client: SylveClient,
    host: str,
    template_id: int,
    detail: dict[str, Any],
    pool: Any,
    storage_pools: list[str] | None,
) -> list[dict[str, Any]]:
    requested: dict[int, str] = {}
    if storage_pools:
        for item in storage_pools:
            if "=" not in item:
                raise SylveError("--storage-pool must use SOURCE_ID=POOL format.")
            source_text, target_pool = item.split("=", 1)
            requested[_as_int(source_text, "storage-pool source ID")] = target_pool.strip()

    if pool is None and not requested:
        return []

    storages: list[Any] = detail["storages"] if isinstance(detail.get("storages"), list) else []
    source_ids = []
    for storage in storages:
        if not isinstance(storage, dict):
            continue
        source = storage.get("sourceStorageId", storage.get("id"))
        if source is not None:
            source_ids.append(_as_int(source, "sourceStorageId"))

    if pool is not None:
        if not source_ids:
            raise SylveError("Template has no cloneable storage metadata; cannot apply --pool.")
        for source in source_ids:
            requested.setdefault(source, str(pool))

    if source_ids:
        unknown = sorted(set(requested) - set(source_ids))
        if unknown:
            raise SylveError(
                "Unknown template storage IDs: " + ", ".join(str(item) for item in unknown)
            )
    elif requested:
        raise SylveError("Template has no cloneable storage metadata.")

    return [
        {"sourceStorageId": source, "pool": target_pool}
        for source, target_pool in requested.items()
    ]


def _print_payload(payload: dict[str, Any], fmt: OutputFormat) -> None:
    if fmt == OutputFormat.yaml:
        sys.stdout.write(yaml.safe_dump(payload, sort_keys=False))
    elif fmt == OutputFormat.value:
        sys.stdout.write(json.dumps(payload, separators=(",", ":")) + "\n")
    else:
        sys.stdout.write(json.dumps(payload, indent=2) + "\n")


def _print_result(result: dict[str, Any], fmt: OutputFormat, message: str) -> None:
    print_result(result, fmt=fmt, message=message)


def _print_plan(lines: list[str], title: str) -> None:
    console.print(title, style="bold")
    for line in lines:
        console.print(f"  {line}", markup=False)


def _start_vm(client: SylveClient, rid: int, host: str, wait: bool) -> dict[str, Any]:
    try:
        response = client.post(f"/vm/{rid}/actions/start", node=host)
    except SylveAPIError as exc:
        raise SylveError(f"VM {rid} was created but could not be started: {str(exc)}") from exc
    task_id = response.get("taskId") if isinstance(response, dict) else None
    if wait and task_id:
        wait_for_lifecycle_task(client, int(task_id), node=host)
    return response if isinstance(response, dict) else {}


def _post_scratch(client: SylveClient, host: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        response = client.post("/vm", json_body=payload, node=host)
    except SylveAPIError as exc:
        raise SylveError(_friendly_create_error(exc)) from exc
    if isinstance(response, dict):
        return response
    return {}


def _post_template(
    client: SylveClient,
    host: str,
    template_id: int,
    payload: dict[str, Any],
) -> dict[str, Any]:
    try:
        response = client.post(
            f"/vm/templates/{template_id}/vms",
            json_body=payload,
            node=host,
        )
    except SylveAPIError as exc:
        raise SylveError(_friendly_create_error(exc)) from exc
    if isinstance(response, dict):
        return response
    return {}


def _confirm(plan: list[str], title: str, yes: bool, fmt: OutputFormat) -> None:
    if yes or not sys.stdin.isatty() or fmt != OutputFormat.table:
        return
    _print_plan(plan, title)
    typer.confirm("Create the VM(s) with this configuration?", abort=True)


def register_vm_create_commands(app: typer.Typer) -> None:
    @app.command("create")
    def vm_create(
        ctx: typer.Context,
        name: Annotated[
            str | None,
            typer.Argument(help="Name for the new VM. Omit to use the config/template default."),
        ] = None,
        name_option: Annotated[
            str | None,
            typer.Option("--name", help="VM name (overrides the positional argument or config)."),
        ] = None,
        node: NodeOption = None,
        rid: Annotated[
            int | None,
            typer.Option("--rid", help="VM RID (1-9999). Defaults to the next free guest ID."),
        ] = None,
        template: Annotated[
            str | None,
            typer.Option("--template", help="Create from a VM template ID or name."),
        ] = None,
        config_file: Annotated[
            Path | None,
            typer.Option(
                "--file",
                exists=True,
                dir_okay=False,
                readable=True,
                help=(
                    "YAML or JSON create configuration. The CLI fills defaults and parses "
                    "sizes; unlike --data, it is not sent verbatim."
                ),
            ),
        ] = None,
        description: Annotated[
            str | None,
            typer.Option("--description", "-d", help="VM description."),
        ] = None,
        cpu: Annotated[
            int | None,
            typer.Option("--cpu", help="CPU cores (shorthand; sockets/threads default to 1)."),
        ] = None,
        sockets: Annotated[
            int | None,
            typer.Option("--sockets", help="CPU sockets."),
        ] = None,
        threads: Annotated[
            int | None,
            typer.Option("--threads", help="CPU threads per core."),
        ] = None,
        memory: Annotated[
            str | None,
            typer.Option("--memory", help="Memory size, e.g. 2G or 512M."),
        ] = None,
        storage_type: Annotated[
            str | None,
            typer.Option(
                "--storage-type", help="Storage type: zvol, raw, image, filesystem, none."
            ),
        ] = None,
        pool: Annotated[
            str | None,
            typer.Option("--pool", help="ZFS pool for the primary disk or template clone."),
        ] = None,
        disk_size: Annotated[
            str | None,
            typer.Option("--disk-size", help="Primary disk size, e.g. 20G."),
        ] = None,
        storage_emulation: Annotated[
            str | None,
            typer.Option("--storage-emulation", help="Disk emulation (virtio-blk, nvme, etc.)."),
        ] = None,
        iso: Annotated[
            str | None,
            typer.Option("--iso", help="Installation/cloud-init ISO download UUID or filename."),
        ] = None,
        switch: Annotated[
            str | None,
            typer.Option("--switch", help="Network switch name, or 'none'."),
        ] = None,
        switch_emulation: Annotated[
            str | None,
            typer.Option("--switch-emulation", help="NIC emulation: virtio or e1000."),
        ] = None,
        mac_object: Annotated[
            str | None,
            typer.Option("--mac-object", help="Existing MAC object name or ID."),
        ] = None,
        cloud_init: Annotated[
            bool | None,
            typer.Option("--cloud-init/--no-cloud-init", help="Enable cloud-init."),
        ] = None,
        user_data: Annotated[
            Path | None,
            typer.Option("--user-data", exists=True, dir_okay=False, readable=True),
        ] = None,
        meta_data: Annotated[
            Path | None,
            typer.Option("--meta-data", exists=True, dir_okay=False, readable=True),
        ] = None,
        network_config: Annotated[
            Path | None,
            typer.Option("--network-config", exists=True, dir_okay=False, readable=True),
        ] = None,
        vnc: Annotated[
            bool | None,
            typer.Option("--vnc/--no-vnc", help="Enable or disable VNC."),
        ] = None,
        vnc_bind: Annotated[
            str | None,
            typer.Option("--vnc-bind", help="VNC bind address."),
        ] = None,
        vnc_port: Annotated[
            int | None,
            typer.Option("--vnc-port", help="VNC port; auto-selected when omitted."),
        ] = None,
        vnc_password: Annotated[
            str | None,
            typer.Option("--vnc-password", help="VNC password; generated when omitted."),
        ] = None,
        vnc_resolution: Annotated[
            str | None,
            typer.Option("--vnc-resolution", help="VNC resolution, e.g. 1024x768."),
        ] = None,
        vnc_wait: Annotated[
            bool | None,
            typer.Option("--vnc-wait/--no-vnc-wait", help="Wait for VNC before starting."),
        ] = None,
        serial: Annotated[
            bool | None,
            typer.Option("--serial/--no-serial", help="Enable a serial console."),
        ] = None,
        tpm: Annotated[
            bool | None,
            typer.Option("--tpm/--no-tpm", help="Enable TPM emulation."),
        ] = None,
        qemu_guest_agent: Annotated[
            bool | None,
            typer.Option("--qemu-guest-agent/--no-qemu-guest-agent"),
        ] = None,
        ignore_umsr: Annotated[
            bool | None,
            typer.Option("--ignore-umsr/--no-ignore-umsr"),
        ] = None,
        apic: Annotated[
            bool | None,
            typer.Option("--apic/--no-apic"),
        ] = None,
        acpi: Annotated[
            bool | None,
            typer.Option("--acpi/--no-acpi"),
        ] = None,
        boot_rom: Annotated[
            str | None,
            typer.Option("--boot-rom", help="Boot ROM: uefi, uboot, or none."),
        ] = None,
        time_offset: Annotated[
            str | None,
            typer.Option("--time-offset", help="Clock offset: utc or localtime."),
        ] = None,
        start_at_boot: Annotated[
            bool | None,
            typer.Option("--start-at-boot/--no-start-at-boot"),
        ] = None,
        start_order: Annotated[
            int | None,
            typer.Option("--start-order", help="Autostart order."),
        ] = None,
        pci_device: Annotated[
            list[str] | None,
            typer.Option("--pci-device", help="PCI passthrough device name or ID (repeatable)."),
        ] = None,
        extra_bhyve_option: Annotated[
            list[str] | None,
            typer.Option("--extra-bhyve-option", help="Extra bhyve option (repeatable)."),
        ] = None,
        start_rid: Annotated[
            int | None,
            typer.Option("--start-rid", help="Template mode: first RID for multiple VMs."),
        ] = None,
        count: Annotated[
            int | None,
            typer.Option("--count", help="Template mode: number of VMs to create."),
        ] = None,
        name_prefix: Annotated[
            str | None,
            typer.Option("--name-prefix", help="Template mode: name prefix for multiple VMs."),
        ] = None,
        storage_pool: Annotated[
            list[str] | None,
            typer.Option(
                "--storage-pool",
                help="Template storage mapping SOURCE_ID=POOL (repeatable).",
            ),
        ] = None,
        rewrite_cloud_init_identity: Annotated[
            bool | None,
            typer.Option("--rewrite-cloud-init-identity/--no-rewrite-cloud-init-identity"),
        ] = None,
        cloud_init_prefix: Annotated[
            str | None,
            typer.Option("--cloud-init-prefix", help="Template mode: cloud-init identity prefix."),
        ] = None,
        start: Annotated[
            bool,
            typer.Option("--start", help="Start the VM(s) after creation."),
        ] = False,
        wait: Annotated[
            bool,
            typer.Option("-w", "--wait/--no-wait", help="Wait for template/start tasks."),
        ] = False,
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
        """Create a VM from scratch or from a template."""
        state: CLIState = ctx.obj
        cfg = _load_config(config_file) if config_file else {}
        if name_option is not None:
            name = name_option
        cfg_node = cfg.get("node") or cfg.get("host")
        if node is None and cfg_node is not None and str(cfg_node).strip():
            node = str(cfg_node).strip()

        with state.get_client(node_override=node) as client:
            host = _resolve_host(client, node)
            config_template = cfg.get("template") or cfg.get("template_id") or cfg.get("templateId")
            template_ref = template or config_template
            template_only_options = (
                start_rid,
                count,
                name_prefix,
                storage_pool,
                rewrite_cloud_init_identity,
                cloud_init_prefix,
            )
            if not template_ref and any(value is not None for value in template_only_options):
                raise SylveError("Template options require --template or a template config.")

            if template_ref:
                template_payload = _config_to_template_payload(cfg)
                if template:
                    template_payload["template"] = template
                if name is not None:
                    template_payload["name"] = name
                if rid is not None:
                    template_payload["rid"] = rid
                if start_rid is not None:
                    template_payload["startRid"] = start_rid
                if count is not None:
                    template_payload["count"] = count
                if name_prefix is not None:
                    template_payload["namePrefix"] = name_prefix
                if rewrite_cloud_init_identity is not None:
                    template_payload["rewriteCloudInitIdentity"] = rewrite_cloud_init_identity
                if cloud_init_prefix is not None:
                    template_payload["cloudInitPrefix"] = cloud_init_prefix
                if pool is not None:
                    template_payload["_pool"] = pool
                if storage_pool is not None:
                    template_payload["_storage_pool"] = storage_pool

                template_id, template_label = _resolve_template(client, host, template_ref)
                needs_detail = bool(
                    template_payload.get("_pool")
                    or template_payload.get("_storage_pool")
                    or template_payload.get("storagePools")
                )
                detail = _template_detail(client, host, template_id) if needs_detail else {}
                mode = str(template_payload.get("mode") or "").strip().lower()
                configured_count = (
                    _as_int(template_payload["count"], "count")
                    if template_payload.get("count") is not None
                    else None
                )
                multiple = (
                    mode == "multiple"
                    or template_payload.get("startRid") is not None
                    or (configured_count is not None and configured_count > 1)
                    or template_payload.get("namePrefix") is not None
                )
                if mode not in ("", "single", "multiple"):
                    raise SylveError("Template mode must be 'single' or 'multiple'.")

                request: dict[str, Any] = {"mode": "multiple" if multiple else "single"}
                if multiple:
                    start_value = template_payload.get("startRid")
                    if start_value in (None, "", 0, "0"):
                        start_value = _next_guest_id(client)
                    start_value = _as_int(start_value, "startRid")
                    vm_count = _as_int(template_payload.get("count", 1), "count")
                    if vm_count < 1 or vm_count > 200:
                        raise SylveError("Template count must be between 1 and 200.")
                    if start_value < 1 or start_value + vm_count - 1 > 9999:
                        raise SylveError("Template RID range must stay within 1-9999.")
                    request["startRid"] = start_value
                    request["count"] = vm_count
                    prefix = str(template_payload.get("namePrefix") or "").strip()
                    if prefix:
                        if not _VM_NAME_RE.fullmatch(prefix):
                            raise SylveError(
                                "VM name prefix may contain only letters, numbers, '-' and '_'."
                            )
                        request["namePrefix"] = prefix
                else:
                    rid_value = template_payload.get("rid")
                    if rid_value in (None, "", 0, "0"):
                        rid_value = _next_guest_id(client)
                    rid_value = _as_int(rid_value, "rid")
                    if not 1 <= rid_value <= 9999:
                        raise SylveError("RID must be between 1 and 9999.")
                    request["rid"] = rid_value
                    vm_name = str(template_payload.get("name") or "").strip()
                    if vm_name:
                        if not _VM_NAME_RE.fullmatch(vm_name):
                            raise SylveError(
                                "VM name may contain only letters, numbers, '-' and '_'."
                            )
                        request["name"] = vm_name

                config_storage_specs = [
                    f"{item['sourceStorageId']}={item['pool']}"
                    for item in template_payload.get("storagePools") or []
                ]
                raw_storage_specs = template_payload.get("_storage_pool")
                if isinstance(raw_storage_specs, str):
                    cli_storage_specs = [raw_storage_specs]
                else:
                    cli_storage_specs = list(raw_storage_specs or [])
                request["storagePools"] = _template_storage_mappings(
                    client,
                    host,
                    template_id,
                    detail,
                    template_payload.get("_pool"),
                    cli_storage_specs + config_storage_specs,
                )
                rewrite = _as_bool(
                    template_payload.get("rewriteCloudInitIdentity", False),
                    "rewriteCloudInitIdentity",
                )
                request["rewriteCloudInitIdentity"] = rewrite
                if rewrite:
                    prefix = str(template_payload.get("cloudInitPrefix") or "").strip()
                    if prefix:
                        request["cloudInitPrefix"] = prefix

                if dry_run:
                    _print_payload(request, fmt)
                    return

                plan = [
                    f"Node: {host}",
                    f"Template: {detail.get('name') or template_label}",
                    f"Mode: {request['mode']}",
                ]
                if request["mode"] == "single":
                    plan.append(f"RID: {request['rid']}")
                    if request.get("name"):
                        plan.append(f"Name: {request['name']}")
                else:
                    plan.append(
                        f"RID range: {request['startRid']}-{request['startRid'] + request['count'] - 1}"
                    )
                    plan.append(f"Count: {request['count']}")
                plan.append(f"Start after create: {'yes' if start else 'no'}")
                _confirm(plan, "VM template creation plan", yes, fmt)

                if start and not wait:
                    wait = True
                response = _post_template(client, host, template_id, request)
                task_id = response.get("taskId") if isinstance(response, dict) else None
                result: dict[str, Any] = {
                    "templateId": template_id,
                    "node": host,
                    "mode": request["mode"],
                }
                if request["mode"] == "single":
                    result["rid"] = request["rid"]
                    result["name"] = request.get("name")
                else:
                    result["startRid"] = request["startRid"]
                    result["count"] = request["count"]
                    result["namePrefix"] = request.get("namePrefix")
                if task_id:
                    result["taskId"] = int(task_id)

                if wait and task_id:
                    wait_for_lifecycle_task(client, int(task_id), node=host)
                    result["status"] = "created"
                    if start:
                        rids = (
                            [request["rid"]]
                            if request["mode"] == "single"
                            else list(
                                range(
                                    request["startRid"],
                                    request["startRid"] + request["count"],
                                )
                            )
                        )
                        for vm_rid in rids:
                            _start_vm(client, vm_rid, host, wait=True)
                        result["started"] = True
                    message = (
                        f"Created VM(s) from template "
                        f"'{detail.get('name') or template_label}' on {host}."
                    )
                else:
                    result["status"] = "queued"
                    message = (
                        f"Queued creation from template "
                        f"'{detail.get('name') or template_label}' on {host}"
                        + (f" (task #{task_id})." if task_id else ".")
                    )

                _print_result(result, fmt, message)
                return

            scratch_payload = _config_to_scratch_payload(cfg)
            _apply_scratch_flags(
                scratch_payload,
                name=name,
                rid=rid,
                description=description,
                cpu=cpu,
                sockets=sockets,
                threads=threads,
                memory=memory,
                storage_type=storage_type,
                pool=pool,
                disk_size=disk_size,
                storage_emulation=storage_emulation,
                iso=iso,
                switch=switch,
                switch_emulation=switch_emulation,
                mac_object=mac_object,
                cloud_init=cloud_init,
                user_data=user_data,
                meta_data=meta_data,
                network_config=network_config,
                vnc=vnc,
                vnc_bind=vnc_bind,
                vnc_port=vnc_port,
                vnc_password=vnc_password,
                vnc_resolution=vnc_resolution,
                vnc_wait=vnc_wait,
                serial=serial,
                tpm=tpm,
                qemu_guest_agent=qemu_guest_agent,
                ignore_umsr=ignore_umsr,
                apic=apic,
                acpi=acpi,
                boot_rom=boot_rom,
                time_offset=time_offset,
                start_at_boot=start_at_boot,
                start_order=start_order,
                pci_device=pci_device,
                extra_bhyve_option=extra_bhyve_option,
            )
            request = _normalize_scratch_payload(client, host, scratch_payload)

            if dry_run:
                _print_payload(request, fmt)
                return

            plan = [
                f"Node: {host}",
                f"Name: {request['name']}",
                f"RID: {request['rid']}",
                (
                    f"CPU: {request['cpuSockets']} socket(s), "
                    f"{request['cpuCores']} core(s), {request['cpuThreads']} thread(s)"
                ),
                f"Memory: {format_bytes(request['ram'])}",
            ]
            if request.get("storageType") == "none":
                plan.append("Storage: none")
            else:
                plan.append(
                    f"Storage: {request['storageType']} "
                    f"{format_bytes(request['storageSize'])} on {request['storagePool']} "
                    f"({request['storageEmulationType']})"
                )
            plan.append(f"Network: {request.get('switchName') or 'none'}")
            plan.append(f"VNC: {'enabled' if request.get('vncEnabled') else 'disabled'}")
            plan.append(f"Start after create: {'yes' if start else 'no'}")
            _confirm(plan, "VM creation plan", yes, fmt)

            response = _post_scratch(client, host, request)
            created_rid = int(response.get("rid") or request["rid"])
            created_name = str(response.get("name") or request["name"])
            result = {"rid": created_rid, "name": created_name, "node": host}
            if request.get("vncEnabled") and request.get("vncPassword"):
                result["vncPassword"] = request["vncPassword"]
            if start:
                _start_vm(client, created_rid, host, wait=wait)
                result["started"] = True
                if wait:
                    message = f"Created and started VM {created_name} ({created_rid}) on {host}."
                else:
                    message = f"Created VM {created_name} ({created_rid}) on {host}; start queued."
            else:
                message = f"Created VM {created_name} ({created_rid}) on {host}."
            if result.get("vncPassword"):
                message += f" VNC password: {result['vncPassword']}"
            _print_result(result, fmt, message)
