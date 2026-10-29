#!/usr/bin/env bash
# Create a VM from the example YAML definition. The cloud-init paths inside the
# YAML are relative to the examples directory, so the script runs there.
#
# Usage:
#   ./scripts/create-from-yaml.sh                   # create
#   DRY_RUN=1 ./scripts/create-from-yaml.sh         # print the request only
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXAMPLES_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

SYLVE_BIN="${SYLVE_BIN:-sylve}"
FILE="${FILE:-$EXAMPLES_DIR/vm/fedora-cloud.yaml}"

cmd=("$SYLVE_BIN" vm create --file "$FILE" --start --wait --yes)

# Relative cloud-init file paths in the YAML resolve against the working
# directory, so run from the examples directory.
cd "$EXAMPLES_DIR"

if [ "${DRY_RUN:-0}" = "1" ]; then
  "$SYLVE_BIN" vm create --file "$FILE" --dry-run -f yaml
else
  "${cmd[@]}"
fi