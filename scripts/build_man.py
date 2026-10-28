#!/usr/bin/env python3
"""Render manpage sources from ``docs/man/src`` into installable manpages."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "man" / "src"
OUTPUT = ROOT / "docs" / "man"
VERSION_FILE = ROOT / "src" / "sylve_cli" / "__init__.py"
PAGES = {
    "sylve.1.in": ("man1", "sylve.1"),
    "sylve-config.5.in": ("man5", "sylve-config.5"),
}


def read_version() -> str:
    """Read the package version without importing the package."""
    match = re.search(
        r'^__version__\s*=\s*["\']([^"\']+)["\']',
        VERSION_FILE.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    if match is None:
        raise SystemExit(f"Could not find __version__ in {VERSION_FILE}")
    return match.group(1)


def render(*, check: bool) -> int:
    """Render all manpages, or verify that rendered files are current."""
    version = read_version()
    changed = 0
    for source_name, (section, output_name) in PAGES.items():
        source = SOURCE / source_name
        target = OUTPUT / section / output_name
        rendered = source.read_text(encoding="utf-8").replace("@VERSION@", version)
        if check:
            if not target.exists() or target.read_text(encoding="utf-8") != rendered:
                print(f"out of date: {target}", file=sys.stderr)
                changed += 1
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered, encoding="utf-8")
        print(f"rendered {target.relative_to(ROOT)}")
    if check and changed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(render(check="--check" in sys.argv[1:]))
