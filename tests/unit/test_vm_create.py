"""Unit tests for VM create payload normalization and resolution logic.

These exercise the pure, client-parameterized helpers in vm_create.py directly:
size/bool parsing, config-to-payload mapping, storage normalization, guest-ID
allocation, pool/ISO/switch resolution, and the full scratch-payload contract.
"""

from __future__ import annotations

from typing import Any

import pytest

from sylve_cli.client import SylveAPIError, SylveError
from sylve_cli.commands.vm_create import (
    _as_bool,
    _config_to_scratch_payload,
    _friendly_create_error,
    _next_guest_id,
    _normalize_scratch_payload,
    _normalize_storage_pools,
    _parse_size,
    _resolve_pool,
    _template_storage_mappings,
)


class StubClient:
    """Client stub returning canned responses for the resolver helpers."""

    def __init__(self, **data: Any) -> None:
        self.data = data

    def resolve_node_hostname(self, node: str | None) -> str | None:
        return node

    def get_online_nodes(self, refresh: bool = False) -> list[dict[str, Any]]:
        return self.data.get("online_nodes", [])

    def get_cluster_nodes(self, refresh: bool = False) -> list[dict[str, Any]]:
        return self.data.get("cluster_nodes", [])

    def get_cluster_resources(self, refresh: bool = False) -> list[dict[str, Any]]:
        return self.data.get("cluster_resources", [])

    def get(self, path: str, **kwargs: Any) -> Any:
        if path == "/zfs/pools":
            return self.data.get("pools", [])
        if path == "/network/switch":
            return self.data.get("switches", {})
        if path == "/utilities/downloads":
            return self.data.get("downloads", [])
        if path == "/network/object":
            return self.data.get("objects", [])
        if path == "/system/ppt-devices":
            return self.data.get("pci_devices", [])
        if path == "/vm":
            return self.data.get("vms", [])
        raise AssertionError(f"unexpected path {path}")


def make_client(**data: Any) -> StubClient:
    return StubClient(**data)


# ---------------------------------------------------------------------------
# Size parsing: units, decimals, and rejection of non-sizes.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("512M", 512 * 1024**2),
        ("2G", 2 * 1024**3),
        ("1.5GiB", int(1.5 * 1024**3)),
        (512, 512),
        ("2048", 2048),
    ],
)
def test_parse_size_units_and_integers(value: object, expected: int) -> None:
    assert _parse_size(value, "memory") == expected


def test_parse_size_rejects_invalid_input() -> None:
    with pytest.raises(SylveError, match="Invalid memory"):
        _parse_size("abc", "memory")
    with pytest.raises(SylveError, match="Invalid memory unit"):
        _parse_size("2X", "memory")
    with pytest.raises(SylveError, match="greater than zero"):
        _parse_size("0", "memory")
    with pytest.raises(SylveError, match="Invalid memory"):
        _parse_size(True, "memory")


# ---------------------------------------------------------------------------
# Boolean coercion: the accepted truthy/falsy forms and rejection of others.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("value", [True, 1, "1", "true", "yes", "on"])
def test_as_bool_truthy_forms(value: object) -> None:
    assert _as_bool(value, "flag") is True


@pytest.mark.parametrize("value", [False, 0, "0", "false", "no", "off"])
def test_as_bool_falsy_forms(value: object) -> None:
    assert _as_bool(value, "flag") is False


def test_as_bool_rejects_unknown() -> None:
    with pytest.raises(SylveError, match="Invalid flag"):
        _as_bool("maybe", "flag")


# ---------------------------------------------------------------------------
# Storage pool normalization: mapping, list, and validation contracts.
# ---------------------------------------------------------------------------
def test_normalize_storage_pools_from_mapping() -> None:
    assert _normalize_storage_pools({"1": "zroot", "2": "tank"}) == [
        {"sourceStorageId": 1, "pool": "zroot"},
        {"sourceStorageId": 2, "pool": "tank"},
    ]


def test_normalize_storage_pools_from_list() -> None:
    assert _normalize_storage_pools([{"sourceStorageId": 7, "pool": "zroot"}]) == [
        {"sourceStorageId": 7, "pool": "zroot"}
    ]


def test_normalize_storage_pools_rejects_missing_fields() -> None:
    with pytest.raises(SylveError, match="sourceStorageId and pool"):
        _normalize_storage_pools([{"sourceStorageId": 1}])
    with pytest.raises(SylveError, match="sourceStorageId and pool"):
        _normalize_storage_pools([{"pool": "zroot"}])


# ---------------------------------------------------------------------------
# Config-to-payload mapping: aliases flatten into API keys and drop Nones.
# ---------------------------------------------------------------------------
def test_config_to_scratch_payload_flattens_sections() -> None:
    cfg = {
        "name": "web-01",
        "memory": "2G",
        "disk_size": "20G",
        "cpu": {"sockets": 2, "cores": 4, "threads": 1},
        "storage": {"type": "zvol", "pool": "zroot", "size": "10G"},
        "network": {"switch": "br0", "mac": "mac-1"},
        "vnc": {"enabled": True, "port": 5901},
        "options": {"tpm": True, "ignore_umsr": True},
    }
    payload = _config_to_scratch_payload(cfg)
    assert payload["ram"] == 2 * 1024**3
    assert payload["cpuCores"] == 4
    assert payload["storagePool"] == "zroot"
    assert payload["switchName"] == "br0"
    assert payload["vncPort"] == 5901
    assert payload["tpmEmulation"] is True


def test_config_to_scratch_payload_drops_none_values() -> None:
    payload = _config_to_scratch_payload({"name": None, "memory": None})
    assert payload == {}


# ---------------------------------------------------------------------------
# Guest-ID allocation: floor at 100, max+1 growth, and range exhaustion.
# ---------------------------------------------------------------------------
def test_next_guest_id_floors_at_100_and_grows() -> None:
    client = make_client(cluster_nodes=[{"guestIDs": [5, 90]}])
    assert _next_guest_id(client) == 100

    client = make_client(cluster_nodes=[{"guestIDs": [101, 250]}])
    assert _next_guest_id(client) == 251


def test_next_guest_id_raises_when_range_exhausted() -> None:
    client = make_client(cluster_nodes=[{"guestIDs": [9999]}])
    with pytest.raises(SylveError, match="1-9999"):
        _next_guest_id(client)


# ---------------------------------------------------------------------------
# Pool resolution: single-pool default, requested match, and error contracts.
# ---------------------------------------------------------------------------
def test_resolve_pool_uses_only_pool_by_default() -> None:
    client = make_client(pools=[{"name": "zroot", "free": 100}])
    assert _resolve_pool(client, "node1", None) == ("zroot", {"name": "zroot", "free": 100})


def test_resolve_pool_matches_requested_case_insensitively() -> None:
    client = make_client(pools=[{"name": "zroot"}, {"name": "tank"}])
    assert _resolve_pool(client, "node1", "TANK")[0] == "tank"


def test_resolve_pool_errors_on_multiple_without_request() -> None:
    client = make_client(pools=[{"name": "zroot"}, {"name": "tank"}])
    with pytest.raises(SylveError, match="pass --pool"):
        _resolve_pool(client, "node1", None)


def test_resolve_pool_errors_on_unknown_request() -> None:
    client = make_client(pools=[{"name": "zroot"}])
    with pytest.raises(SylveError, match="not found"):
        _resolve_pool(client, "node1", "nope")


# ---------------------------------------------------------------------------
# Template storage mappings: parse CLI specs and validate against the template.
# ---------------------------------------------------------------------------
def test_template_storage_mappings_parse_and_apply_default_pool() -> None:
    detail = {"storages": [{"sourceStorageId": 1}, {"sourceStorageId": 2}]}
    result = _template_storage_mappings(make_client(), "node1", 5, detail, "zroot", None)
    assert result == [
        {"sourceStorageId": 1, "pool": "zroot"},
        {"sourceStorageId": 2, "pool": "zroot"},
    ]


def test_template_storage_mappings_rejects_unknown_source() -> None:
    detail = {"storages": [{"sourceStorageId": 1}]}
    with pytest.raises(SylveError, match="Unknown template storage"):
        _template_storage_mappings(make_client(), "node1", 5, detail, None, ["9=zroot"])


def test_template_storage_mappings_requires_metadata_for_pool() -> None:
    with pytest.raises(SylveError, match="no cloneable storage"):
        _template_storage_mappings(make_client(), "node1", 5, {}, "zroot", None)


# ---------------------------------------------------------------------------
# Friendly error mapping: known server codes become actionable messages.
# ---------------------------------------------------------------------------
def test_friendly_create_error_maps_known_code() -> None:
    exc = SylveAPIError("vm 1 exists", status_code=409, error_code="rid_or_name_already_in_use")
    assert _friendly_create_error(exc) == "RID or VM name is already in use."


def test_friendly_create_error_falls_back_to_raw_message() -> None:
    exc = SylveAPIError("some other failure", status_code=500)
    assert _friendly_create_error(exc) == "some other failure"


# ---------------------------------------------------------------------------
# Full scratch-payload contract: defaults, validation, and cross-field rules.
# ---------------------------------------------------------------------------
def test_normalize_scratch_payload_applies_defaults_and_free_space() -> None:
    client = make_client(
        pools=[{"name": "zroot", "free": 100 * 1024**3}],
        switches={"standard": [{"name": "br0"}]},
        downloads=[],
        vms=[],
        objects=[],
        pci_devices=[],
    )
    payload = _normalize_scratch_payload(
        client,
        "node1",
        {"name": "web-01", "ram": "2G", "storageSize": "20G"},
    )
    assert payload["name"] == "web-01"
    assert payload["rid"] >= 100
    assert payload["ram"] == 2 * 1024**3
    assert payload["cpuCores"] == 1
    assert payload["storagePool"] == "zroot"
    assert payload["storageType"] == "zvol"
    assert payload["vncEnabled"] is True
    assert payload["cloudInit"] is False


def test_normalize_scratch_payload_rejects_bad_name_and_rid() -> None:
    with pytest.raises(SylveError, match="letters, numbers"):
        _normalize_scratch_payload(make_client(), "node1", {"name": "bad name!"})
    with pytest.raises(SylveError, match="VM name is required"):
        _normalize_scratch_payload(make_client(), "node1", {})


def test_normalize_scratch_payload_rejects_oversized_disk() -> None:
    client = make_client(pools=[{"name": "zroot", "free": 1024}])
    with pytest.raises(SylveError, match="free space"):
        _normalize_scratch_payload(client, "node1", {"name": "web", "storageSize": "20G"})


def test_normalize_scratch_payload_cloud_init_requires_iso_and_data() -> None:
    client = make_client(pools=[{"name": "zroot", "free": 1024**4}])
    with pytest.raises(SylveError, match="requires --iso"):
        _normalize_scratch_payload(
            client,
            "node1",
            {"name": "web", "cloudInit": True, "storageSize": "20G"},
        )
