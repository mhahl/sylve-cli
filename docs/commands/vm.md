# sylve vm

Manage Bhyve virtual machines, snapshots, and templates.

`server` is a hidden alias for this command group:

    sylve server list

is equivalent to:

    sylve vm list

## Synopsis

    sylve vm COMMAND [ARGS]...

## Commands

| Command | Purpose |
|---|---|
| `create` | Create a VM from flags, a YAML/JSON file, or a template |
| `list` | List VMs across nodes |
| `show VM` | Full VM details |
| `start`, `stop`, `shutdown`, `reboot` | Power actions on one or more VMs |
| `migrate VM` | Preflight and migrate to another node |
| `delete VM` | Delete a VM and optional attached storage |
| `logs VM` | Console logs |
| `guest-agent VM` | QEMU Guest Agent OS and network data |
| `rename VM NEW_NAME` | Rename a VM |
| `snapshot list/create/rollback/delete` | ZFS snapshots |
| `template list/capture/delete` | VM templates |
| `template-show`, `description`, `domain`, `stats`, `stats-step` | Generic API commands |
| `hardware-cpu`, `hardware-ram`, `hardware-pci`, `hardware-vnc` | Generic hardware updates |
| `network-attach`, `network-detach`, `network-update` | Generic network updates |
| `storage-attach`, `storage-from-image`, `storage-update`, `storage-delete` | Generic storage updates |
| `options-boot-order`, `options-boot-rom`, `options-clock` | Generic boot and clock updates |
| `options-cloud-init`, `options-extra-bhyve`, `options-ignore-umsrs` | Generic cloud-init and bhyve updates |
| `options-qemu-guest-agent`, `options-serial-console`, `options-shutdown-wait-time` | Generic guest-agent and shutdown updates |
| `options-tpm`, `options-wol` | Generic TPM and Wake-on-LAN updates |
| `registration-purge` | Purge an orphaned registration |

## Options

### `vm create`

- `NAME`
  VM name. Omit to use `--name`, the config file, or the template default.
- `--name NAME`
  VM name. Overrides the positional argument.
- `-n, --node NODE`
  Target node.
- `--rid RID`
  VM RID, 1-9999. Default: next free guest ID.
- `--template ID|NAME`
  Create from a VM template.
- `--file FILE`
  YAML or JSON create configuration.
- `--description, -d TEXT`
  VM description, up to 1024 characters.
- `--cpu N`
  CPU cores. Default: `1`.
- `--sockets N`
  CPU sockets. Default: `1`.
- `--threads N`
  CPU threads per core. Default: `1`.
- `--memory SIZE`
  Memory, for example `2G` or `512M`. Default: `1G`. Minimum 128 MiB.
- `--storage-type TYPE`
  `zvol`, `raw`, `image`, `filesystem`, or `none`. Default: `zvol`.
- `--pool POOL`
  ZFS pool for the primary disk or template clone.
- `--disk-size SIZE`
  Primary disk size, for example `20G`. Default: `1G`. Minimum 128 MiB.
- `--storage-emulation TYPE`
  `virtio-blk`, `virtio-9p`, `ahci-hd`, `ahci-cd`, or `nvme`.
  Default: `virtio-blk`.
- `--iso ID|NAME`
  Download UUID or filename.
- `--switch NAME`
  Network switch name, or `none`. Default: no switch.
- `--switch-emulation TYPE`
  NIC emulation, for example `virtio-net`. Default: `virtio-net` when a
  switch is set.
- `--mac-object NAME|ID`
  Existing MAC object.
- `--cloud-init / --no-cloud-init`
  Enable or disable cloud-init. Default: off. Supplying user-data or meta-data
  enables it.
- `--user-data FILE`
  Cloud-init user-data. Requires `--iso` and a primary disk.
- `--meta-data FILE`
  Cloud-init meta-data. Required with cloud-init.
- `--network-config FILE`
  Cloud-init network-config.
- `--vnc / --no-vnc`
  Enable or disable VNC. Default: enabled.
- `--vnc-bind ADDRESS`
  VNC bind address. Default: `127.0.0.1`.
- `--vnc-port PORT`
  VNC port. Default: next free port in 5900-5999.
- `--vnc-password PASSWORD`
  VNC password. Default: generated 12-character password. Commas are rejected.
- `--vnc-resolution WxH`
  VNC resolution. Default: `640x480`.
- `--vnc-wait / --no-vnc-wait`
  Wait for VNC before starting. Default: `--no-vnc-wait`.
- `--serial / --no-serial`
  Serial console. Default: off.
- `--tpm / --no-tpm`
  TPM emulation. Default: off.
- `--qemu-guest-agent / --no-qemu-guest-agent`
  QEMU Guest Agent. Default: off.
- `--ignore-umsr / --no-ignore-umsr`
  Ignore unknown MSRs. Default: off.
- `--apic / --no-apic`
  APIC. Default: on.
- `--acpi / --no-acpi`
  ACPI. Default: on.
- `--boot-rom ROM`
  `uefi`, `uboot`, or `none`. Default: `uefi`.
- `--time-offset OFFSET`
  `utc` or `localtime`. Default: `utc`.
- `--start-at-boot / --no-start-at-boot`
  Autostart. Default: off.
- `--start-order N`
  Autostart order. Default: `0`.
- `--pci-device DEVICE`
  PCI passthrough device name or ID. Repeatable.
- `--extra-bhyve-option OPTION`
  Extra bhyve option. Repeatable.
- `--start-rid RID`
  Template mode: first RID for multiple VMs.
- `--count N`
  Template mode: number of VMs, 1-200.
- `--name-prefix PREFIX`
  Template mode: name prefix.
- `--storage-pool SOURCE_ID=POOL`
  Template storage mapping. Repeatable.
- `--rewrite-cloud-init-identity / --no-rewrite-cloud-init-identity`
  Template mode: rewrite cloud-init identity.
- `--cloud-init-prefix PREFIX`
  Template mode: cloud-init identity prefix.
- `--start`
  Start the VM or VMs after creation. Default: off.
- `-w, --wait / --no-wait`
  Wait for template and start tasks. Default: `--no-wait`.
- `--dry-run`
  Print the API request without creating anything.
- `-y, --yes`
  Skip confirmation.
- `-f, --format {table,json,yaml,value,csv}`
  Output format for dry-run and results. Default: `table`.

### `vm list`

- `-n, --node NODE`
  Limit to one node.
- `--long, -l`
  Fetch full CPU, RAM, VNC, autostart, and description data.
- `-f, --format {table,json,yaml,value,csv}`
  Output format. Default: `table`.
- `-c, --column NAME`
  Select columns.
- `--sort-column NAME`
  Sort rows.

### `vm show`

- `VM` (required)
  RID or name.
- `-n, --node NODE`
  Target node.
- `-f, --format {table,json,yaml,value,csv}`
  Output format. Default: `table`.
- `-c, --column NAME`
  Select fields.

### `vm start`, `stop`, `shutdown`, `reboot`

- `VMS...` (required)
  One or more RIDs or names.
- `-n, --node NODE`
  Target node.
- `-w, --wait / --no-wait`
  Wait for the task. Default: `--no-wait`.

### `vm migrate`

- `VM` (required)
  RID or name.
- `--target, -t NODE` (required)
  Destination hostname or UUID.
- `--validate-only`, `--dry-run`
  Run preflight only.
- `-n, --node NODE`
  Source node.
- `-w, --wait / --no-wait`
  Wait for migration. Default: `--wait`.

### `vm delete`

- `VM` (required)
  RID or name.
- `--delete-volumes / --keep-volumes`
  Delete attached ZFS volumes. Default: `--delete-volumes`.
- `--delete-raw-disks / --keep-raw-disks`
  Delete RAW disk images. Default: `--delete-raw-disks`.
- `--delete-macs / --keep-macs`
  Delete associated MAC objects. Default: `--delete-macs`.
- `--force`
  Best-effort removal.
- `-y, --yes`
  Skip confirmation.
- `-n, --node NODE`
  Target node.

### `vm logs`, `vm guest-agent`, `vm rename`

- `VM` (required)
  RID or name.
- `NEW_NAME`
  New name, for `rename` only.
- `-n, --node NODE`
  Target node.
- `-f, --format` and `-c, --column`
  `guest-agent` only.

### `vm snapshot list`

- `VM` (required), `-n/--node`,
  `-f/--format`, `-c/--column`, `--long`.

### `vm snapshot create`

- `VM` (required), `--name, -m NAME` (required),
  `--description, -d TEXT` (default empty), `-n/--node`.

### `vm snapshot rollback`

- `VM` (required), `SNAPSHOT_ID` (required), `-y/--yes`, `-n/--node`.

### `vm snapshot delete`

- `VM` (required), `SNAPSHOT_ID` (required), `-n/--node`.

### `vm template list`

- `-n/--node`, `-f/--format`, `-c/--column`.

### `vm template capture`

- `VM` (required), `--name NAME` (required), `-n/--node`,
  `-w/--wait` (default `--wait`).

### `vm template delete`

- `TEMPLATE_ID` (required), `-n/--node`.

### Generic commands

All generic VM commands accept `--data/-d`, `--param/-p`, `-y/--yes`,
`-n/--node`, and `-f/--format`. Path arguments:

| Command | Arguments |
|---|---|
| `template-show` | `templateId` |
| `description`, `domain`, `stats` | `rid` |
| `stats-step` | `rid step` |
| `hardware-cpu`, `hardware-ram`, `hardware-pci`, `hardware-vnc` | `rid` |
| `network-attach`, `storage-attach`, `storage-from-image` | `rid` |
| `network-detach`, `network-update` | `rid networkId` |
| `storage-update`, `storage-delete` | `rid storageId` |
| `options-*`, `registration-purge` | `rid` |

## Examples

### Minimal

    sylve vm list

Output (illustrative):

    Virtual Machines
    +-----+---------+---------+---------------------+----------+
    | RID | Name    | State   | Node                | VNC Port |
    +-----+---------+---------+---------------------+----------+
    | 101 | web-01  | RUNNING | node1.example.test  | 5900     |
    | 102 | db-01   | SHUTOFF | node2.example.test  | -        |
    +-----+---------+---------+---------------------+----------+

### With every relevant option

This scratch example uses every non-conflicting hardware, storage, network,
VNC, boot, and runtime flag. Template and scratch options are mutually
exclusive; the template, cloud-init, config-file, and dry-run examples follow.

    sylve vm create web-01 \
      --node node1.example.test \
      --rid 120 \
      --description "Web frontend" \
      --sockets 1 --cpu 4 --threads 2 \
      --memory 4G \
      --storage-type zvol --pool zroot --disk-size 40G --storage-emulation virtio-blk \
      --iso debian-13-netinst.iso \
      --switch vm-public --switch-emulation virtio-net --mac-object web-01-mac \
      --vnc --vnc-bind 127.0.0.1 --vnc-port 5920 --vnc-password s3cret \
      --vnc-resolution 1024x768 --no-vnc-wait \
      --serial --tpm --qemu-guest-agent --ignore-umsr --apic --acpi \
      --boot-rom uefi --time-offset utc \
      --start-at-boot --start-order 10 \
      --pci-device 5 --extra-bhyve-option=-A \
      --start --wait --yes

Output (illustrative):

    Created and started VM web-01 (120) on node1.example.test.
    VNC password: s3cret

`--cpu 4` sets cores; `--sockets` and `--threads` set the other CPU
dimensions. `--pci-device` and `--extra-bhyve-option` are repeatable.
`--wait` is accepted with `--start`; the start task is then awaited.

### Create with every template option

    sylve vm create --template debian-13 \
      --node node1.example.test \
      --start-rid 200 \
      --count 3 \
      --name-prefix web \
      --pool zroot \
      --storage-pool 0=zroot \
      --rewrite-cloud-init-identity \
      --cloud-init-prefix web \
      --start --wait --yes

Output (illustrative):

    Created VM(s) from template 'debian-13' on node1.example.test.

Template mode ignores scratch hardware, network, and VNC options. `--count 3`
creates three VMs with RIDs 200-202 and names prefixed `web`. `--pool` and
`--storage-pool` map template storage to target pools.

### Cloud-init

    sylve vm create web-02 --iso debian-13-cloudinit.iso --pool zroot \
      --cloud-init --user-data user-data.yaml --meta-data meta-data.yaml \
      --network-config network-config.yaml --start --wait

Output (illustrative):

    Created and started VM web-02 (121) on node1.example.test.

`--cloud-init` is implied when user-data or meta-data is supplied. Both
user-data and meta-data are required, and the ISO must be cloud-init capable.

### Dry run and config file

    sylve vm create --name web-01 --file web.yaml --dry-run -f json

Output (illustrative):

    {
      "name": "web-01",
      "rid": 120,
      "cpuSockets": 1,
      "cpuCores": 4,
      "cpuThreads": 2,
      "ram": 4294967296,
      "storageType": "zvol",
      "storagePool": "zroot",
      "storageSize": 42949672960,
      "storageEmulationType": "virtio-blk",
      "vncEnabled": true,
      "vncBind": "127.0.0.1",
      "vncPort": 5920,
      "vncPassword": "s3cret",
      "vncResolution": "1024x768",
      "vncWait": false
    }

`--dry-run` prints the normalized request and sends nothing. `--format yaml`
and `--format value` change the request output; `--format value` prints compact
JSON.

### Show, actions, migration, delete

    sylve vm show 101 -f json

Output (illustrative):

    {
      "rid": 101,
      "name": "web-01",
      "state_name": "RUNNING",
      "node": "node1.example.test"
    }

    sylve vm start 101 102 --wait

Output (illustrative):

    VM 101 (node1.example.test): start completed.
    VM 102 (node2.example.test): start completed.

    sylve vm migrate 101 --target node2.example.test --dry-run

    sylve vm migrate 101 --target node2.example.test --wait

    sylve vm delete 101 --keep-volumes --keep-raw-disks --keep-macs --yes

Output (illustrative):

    VM 101 Migration Preflight -> node2.example.test
    ...
    VM 101 successfully migrated from node1.example.test to node2.example.test.
    Deleted VM 101 (node1.example.test).

### Snapshots and templates

    sylve vm snapshot create 101 --name pre-upgrade --description "before 0.4"

Output:

    Created snapshot 'pre-upgrade' for VM 101.

    sylve vm snapshot list 101 --long

Output (illustrative):

    VM 101 Snapshots (node1.example.test)
    +----+-------------+---------------------+---------------------+------------+
    | ID | Name        | Snapshot            | Description         | Created At |
    +----+-------------+---------------------+---------------------+------------+
    | 1  | pre-upgrade | zroot/vm/101@pre... | before 0.4          | 2026-10... |
    +----+-------------+---------------------+---------------------+------------+

    sylve vm snapshot rollback 101 1 --yes

Output:

    Rolled back VM 101 to snapshot #1.

    sylve vm template capture 101 --name debian-web --wait

Output:

    Captured VM 101 as template 'debian-web'.

### Generic command with every option

    sylve vm hardware-cpu 101 --data '{"sockets":1,"cores":4,"threads":2}' --param dryRun=0 --node node1.example.test -f json

Output (illustrative):

    {
      "rid": 101,
      "cpuSockets": 1,
      "cpuCores": 4,
      "cpuThreads": 2
    }

## Inputs

- The active context and token.
- `--file` accepts YAML or JSON. Common top-level keys: `name`, `node`, `rid`,
  `template`, `description`, `cpu`, `sockets`, `threads`, `memory`,
  `storage_type`, `pool`, `disk_size`, `storage_emulation`, `iso`, `switch`,
  `switch_emulation`, `mac_object`, `vnc`, `cloud_init`, `boot`, `options`.
- Cloud-init files must be valid YAML.
- Generic commands accept `--data` inline JSON/YAML or `@file`, plus repeatable
  `--param KEY=VALUE`.

## Outputs

- Tables, JSON, YAML, value, or CSV.
- `create` prints a confirmation plan on a terminal, then the created VM or
  task. JSON/YAML output includes `rid`, `name`, `node`, optional `taskId`,
  and the VNC password when one was generated.
- `--dry-run` prints the request body.
- Exit `0` on success. Exit `1` on API error or aborted confirmation. Exit `2`
  on usage error.
