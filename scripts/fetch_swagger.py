#!/usr/bin/env python3
"""Download the Swagger/OpenAPI spec from the Sylve server project.

The spec is used for live-test response validation and for generating the
checked-in ``body_schemas.py`` request-shape lookup. It is no longer vendored;
run this script (or ``make swagger``) before ``make schemas`` or live tests.

Known upstream spec mismatches are patched automatically after download so
the spec matches what the server actually returns.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "docs" / "swagger.json"

# Raw content URL (not the GitHub blob page).
SOURCE = "https://raw.githubusercontent.com/AlchemillaHQ/Sylve/master/docs/swagger/swagger.json"


# ---------------------------------------------------------------------------
# Patches — upstream swagger defs that don't match the server's wire format.
# Each patch is a (description, fn) pair where fn mutates the spec dict.
# ---------------------------------------------------------------------------

_PATCHES: list[tuple[str, Any]] = []


def _patch(description: str):
    """Decorator that registers a patch function."""

    def wrapper(fn):
        _PATCHES.append((description, fn))
        return fn

    return wrapper


@_patch("time.Duration: remove enum constraint (server sends raw int)")
def _duration(spec: dict[str, Any]) -> None:
    dur = spec.get("definitions", {}).get("time.Duration", {})
    dur.pop("enum", None)
    dur.pop("x-enum-varnames", None)


@_patch("IPv4.ip and IPv4.broadcast: string, not array-of-int")
@_patch("IPv6.ip and IPv6.broadcast: string, not array-of-int")
def _ip_addresses(spec: dict[str, Any]) -> None:
    for model in (
        "github_com_alchemillahq_sylve_pkg_network_iface.IPv4",
        "github_com_alchemillahq_sylve_pkg_network_iface.IPv6",
    ):
        props = spec.get("definitions", {}).get(model, {}).get("properties", {})
        for field in ("ip", "broadcast"):
            if props.get(field, {}).get("type") == "array":
                props[field] = {"type": "string"}


@_patch("ManagedCertificateOperation.issuanceOperation: add '' to enum")
def _cert_op(spec: dict[str, Any]) -> None:
    enum = (
        spec.get("definitions", {})
        .get("github_com_alchemillahq_sylve_internal_db_models.ManagedCertificateOperation", {})
        .get("enum")
    )
    if enum is not None and "" not in enum:
        enum.insert(0, "")


def _apply_patches(spec: dict[str, Any]) -> None:
    for desc, fn in _PATCHES:
        fn(spec)


def _patched_bytes(spec: dict[str, Any]) -> bytes:
    return json.dumps(spec, indent=2).encode("utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    check = "--check" in sys.argv[1:]

    try:
        req = urllib.request.Request(SOURCE, method="GET")
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        print(f"error: failed to download {SOURCE}: {exc}", file=sys.stderr)
        return 1

    _apply_patches(raw)
    patched_bytes = _patched_bytes(raw)

    if check:
        if not DEST.exists():
            print(f"out of date: {DEST.relative_to(ROOT)} is missing", file=sys.stderr)
            return 1
        existing = DEST.read_bytes()
        if existing != patched_bytes:
            print(
                f"out of date: {DEST.relative_to(ROOT)} differs from upstream",
                file=sys.stderr,
            )
            return 1
        return 0

    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_bytes(patched_bytes)
    print(f"downloaded + patched to {DEST.relative_to(ROOT)} ({len(patched_bytes)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
