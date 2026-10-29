#!/usr/bin/env bash
# Create a cloud-init provisioned VM with an NVMe-backed zvol.
#
# Usage:
#   ./scripts/create-fedora-vm.sh                  # create (prompts/confirms)
#   DRY_RUN=1 ./scripts/create-fedora-vm.sh        # print the request only
#   VM_NAME=web-01 NODE=node2.example.test \
#     ./scripts/create-fedora-vm.sh
#
# Everything can be overridden via environment variables; defaults are the
# placeholders in this file.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXAMPLES_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

SYLVE_BIN="${SYLVE_BIN:-sylve}"
VM_NAME="${VM_NAME:-fedora-cloud}"
NODE="${NODE:-node1.example.test}"
CPUS="${CPUS:-2}"
MEMORY="${MEMORY:-4G}"
POOL="${POOL:-tank}"
DISK_SIZE="${DISK_SIZE:-50G}"
STORAGE_EMULATION="${STORAGE_EMULATION:-nvme}"
IMAGE="${IMAGE:-Fedora-Cloud-Base-UEFI-UKI-44-1.7.x86_64.qcow2}"
SWITCH="${SWITCH:-vm-public}"
USER_DATA="${USER_DATA:-$EXAMPLES_DIR/cloud-init/user-data.yaml}"
META_DATA="${META_DATA:-$EXAMPLES_DIR/cloud-init/meta-data.yaml}"
NETWORK_CONFIG="${NETWORK_CONFIG:-$EXAMPLES_DIR/cloud-init/network-config.yaml}"

cmd=(
  "$SYLVE_BIN" vm create "$VM_NAME"
  -n "$NODE"
  --cpu "$CPUS" --memory "$MEMORY"
  --storage-type zvol --pool "$POOL" --disk-size "$DISK_SIZE"
  --storage-emulation "$STORAGE_EMULATION"
  --iso "$IMAGE"
  --switch "$SWITCH" --switch-emulation virtio
  --cloud-init
  --user-data "$USER_DATA"
  --meta-data "$META_DATA"
  --network-config "$NETWORK_CONFIG"
  --qemu-guest-agent
  --start --wait
  --yes
)

if [ "${DRY_RUN:-0}" = "1" ]; then
  "${cmd[@]}" --dry-run -f yaml
else
  "${cmd[@]}"
fi