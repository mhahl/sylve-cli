# SYLVE-VM(1)

## NAME

`sylve-vm` - manage Bhyve virtual machines, snapshots, and templates

## SYNOPSIS

```sh
sylve vm COMMAND [ARGS ...]
sylve server COMMAND [ARGS ...]
```

## DESCRIPTION

`sylve vm` (and its hidden alias `sylve server`) creates, inspects, controls,
migrates, snapshots, and templates Bhyve virtual machines on Sylve cluster
nodes.

`vm create` supports three provisioning modes:

1. **Scratch creation** from command-line hardware, storage, network, VNC, and
   boot flags.
2. **Template deployment** via `--template ID|NAME`, which can clone multiple
   guests with `--count` and `--start-rid`.
3. **Configuration file creation** via `--file FILE` (YAML or JSON).

On a terminal, `vm create` prints a confirmation plan before sending the API
request unless you pass `-y` / `--yes` or `--dry-run`.

## SUBCOMMANDS

| Subcommand | Description |
|---|---|
| `create [NAME]` | Create a VM from flags, a YAML/JSON file, or a template |
| `list` | List VMs across cluster nodes |
| `show VM` | Show full details for a VM by RID or name |
| `start`, `stop`, `shutdown`, `reboot` | Perform power actions on one or more VMs |
| `migrate VM` | Validate preflight and migrate a VM to another node |
| `delete VM` | Delete a VM, with flags to keep its volumes, raw disks, and MACs |
| `logs VM` | Display VM console logs |
| `console VM` | Attach to a running VM's interactive serial console |
| `vnc VM` | Open a VM's graphical console in a local VNC viewer |
| `guest-agent VM` | Query QEMU Guest Agent OS and network information |
| `rename VM NEW_NAME` | Rename a VM |
| `snapshot list/create/rollback/delete` | Manage VM ZFS snapshots |
| `template list/show/capture/delete` | Manage VM templates |
| `description`, `domain`, `stats`, `stats-step` | Generic read/update API commands |
| `hardware cpu/ram/pci/vnc` | Generic hardware update commands |
| `network attach/detach/set` | Generic NIC management commands |
| `storage attach/from-image/set/delete` | Generic storage management commands |
| `options boot-order/boot-rom/clock/cloud-init/extra-bhyve/ignore-umsrs/qemu-guest-agent/serial-console/shutdown-wait-time/tpm/wol` | Generic VM option update commands |
| `registration-purge`, `domain-reinitialize` | Purge or reinitialize an orphaned VM registration/domain |

## OPTIONS

### `vm create`

- `NAME` / `--name NAME`
  VM name. `--name` overrides the positional argument. Omit to use the config
  file or template default.
- `-n, --node NODE`
  Target node.
- `--rid RID`
  VM RID (`1`–`9999`, default: next free guest ID).
- `--template ID|NAME`
  Create from a VM template.
- `--file FILE`
  Read the create configuration from a YAML or JSON file. Keys may be flat
  (`sockets`, `cores`, `threads`, `memory`, `storage_type`, `pool`,
  `disk_size`, `storage_emulation`, `iso`, `switch`, `switch_emulation`,
  `mac_object`) or grouped under `cpu`, `storage`, `network`, `vnc`,
  `cloud_init`, `boot`, and `options`. Command-line flags override file
  values. Worked examples appear under EXAMPLES.
- `--description, -d TEXT`
  VM description (up to 1024 characters).
- `--cpu N`, `--sockets N`, `--threads N`
  CPU cores, sockets, and threads per core (default: `1` each).
- `--memory SIZE`
  RAM allocation, e.g. `2G` or `512M` (default: `1G`, minimum: `128M`).
- `--storage-type TYPE`
  `zvol`, `raw`, `image`, `filesystem`, or `none` (default: `zvol`).
- `--pool POOL`
  ZFS pool for the primary disk or template clone.
- `--disk-size SIZE`
  Primary disk size, e.g. `20G` (default: `1G`, minimum: `128M`).
- `--storage-emulation TYPE`
  `virtio-blk`, `virtio-9p`, `ahci-hd`, `ahci-cd`, or `nvme` (default: `virtio-blk`).
- `--iso ID|NAME`
  Download UUID or filename to attach as optical/boot media.
- `--switch NAME`
  Network switch name, or `none` (default: no switch).
- `--switch-emulation TYPE`
  NIC emulation model (default: `virtio` when you attach a switch).
- `--mac-object NAME|ID`
  Existing MAC address object.
- `--cloud-init / --no-cloud-init`
  Enable or disable cloud-init (default: off; implied by `--user-data` or
  `--meta-data`).
- `--user-data FILE`, `--meta-data FILE`, `--network-config FILE`
  Cloud-init YAML files. Cloud-init requires both user-data and meta-data, a
  cloud-init-capable `--iso`, and a primary disk.
- `--vnc / --no-vnc`
  Enable or disable VNC (default: `--vnc`).
- `--vnc-bind ADDRESS`
  VNC bind address (default: `127.0.0.1`).
- `--vnc-port PORT`
  VNC port (default: next free port in `5900`–`5999`).
- `--vnc-password PASSWORD`
  VNC password (default: generated 12-character password; the CLI rejects commas).
- `--vnc-resolution WxH`
  VNC resolution (default: `640x480`).
- `--vnc-wait / --no-vnc-wait`
  Wait for a VNC connection before booting (default: `--no-vnc-wait`).
- `--serial / --no-serial`, `--tpm / --no-tpm`, `--qemu-guest-agent / --no-qemu-guest-agent`, `--ignore-umsr / --no-ignore-umsr`
  Enable or disable serial console, TPM emulation, QEMU Guest Agent, and
  unknown MSR ignoring (all default to off).
- `--apic / --no-apic`, `--acpi / --no-acpi`
  Enable or disable APIC and ACPI (both default to on).
- `--boot-rom ROM`
  Boot ROM: `uefi`, `uboot`, or `none` (default: `uefi`).
- `--time-offset OFFSET`
  RTC offset: `utc` or `localtime` (default: `utc`).
- `--start-at-boot / --no-start-at-boot`, `--start-order N`
  Autostart at host boot (default: off) and boot order (`0`).
- `--pci-device DEVICE`
  PCI passthrough device name or ID (repeatable).
- `--extra-bhyve-option OPTION`
  Additional `bhyve(8)` flag (repeatable).
- `--start-rid RID`, `--count N`, `--name-prefix PREFIX`, `--storage-pool SOURCE_ID=POOL`, `--rewrite-cloud-init-identity / --no-rewrite-cloud-init-identity`, `--cloud-init-prefix PREFIX`
  Template deployment options (`--count` accepts `1`–`200`; `--storage-pool` is
  repeatable).
- `--start`
  Start the VM(s) as soon as creation finishes.
- `-w, --wait / --no-wait`
  Wait for template and start tasks (default: `--wait`, pass `--no-wait` to skip).
- `--dry-run`
  Print the normalized API payload without creating anything.
- `-y, --yes`
  Skip interactive confirmation.
- `-f, --format {table,json,yaml,value,csv}`
  Output format (default: `table`).

### `vm list` and `vm show`

- `list`: `-n, --node NODE`, `--long` (fetches CPU, RAM, VNC, autostart,
  and description), `-f, --format`, `-c, --column`, `--sort-column NAME`,
  `--filter COLUMN==VALUE|COLUMN!=VALUE|COLUMN~VALUE` (repeatable;
  exact, exclude, or substring), `-l, --limit N`.
- `show VM`: `VM` (RID or name), `--long` (pretty-prints nested storage, network,
  and snapshot JSON and prints full multi-line cloud-init YAML instead of compact
  summaries), `-n, --node NODE`, `-f, --format`, `-c, --column`.
  If the VM runs with the QEMU guest agent enabled and responding,
  `show` also reports live `ipAddresses` (non-loopback IPv4 and global IPv6).
  The CLI omits the field when you disable the agent or it is unavailable.

### `vm start`, `stop`, `shutdown`, `reboot`

- `VMS...` (required)
  One or more VM RIDs or names.
- `-n, --node NODE`
  Target node.
- `-w, --wait / --no-wait`
  Wait for the lifecycle task (default: `--no-wait`). Action commands start
  immediately; pass `--wait` to block until the task finishes.
- `-f, --format`
  Output format. With `json`/`yaml`/`csv`/`value` the command prints each VM's
  result (`rid`, `name`, `node`, `outcome`, `status`, `taskId`) instead of prose.
  A failure on one VM does not stop the others; the command reports every
  failure and exits `1`.

### `vm migrate`

- `VM` (required)
  VM RID or name.
- `--target, -t NODE` (required)
  Destination node hostname or UUID.
- `--validate-only`, `--dry-run`
  Run migration preflight only.
- `-n, --node NODE`
  Source node.
- `-w, --wait / --no-wait`
  Wait for migration completion (default: `--wait`).
- `-f, --format`
  Output format. With `json`/`yaml`/`csv`/`value` the command prints the
  migration result (`rid`, `source`, `target`, `status`, `taskId`) instead of prose.

### `vm delete`

- `VM` (required)
  VM RID or name.
- `--delete-volumes / --keep-volumes`
  Delete attached ZFS volumes (default: `--delete-volumes`).
- `--delete-raw-disks / --keep-raw-disks`
  Delete RAW disk images (default: `--delete-raw-disks`).
- `--delete-macs / --keep-macs`
  Delete associated MAC objects (default: `--delete-macs`).
- `--force`
  Best-effort removal.
- `--dry-run`
  Print what the command would delete (RID, name, node, volumes/raw disks/MACs)
  without deleting anything.
- `-y, --yes`, `-n, --node NODE`, `-f, --format`
  Skip confirmation; target node; output format (prints `{"deleted":true,...}`).

### `vm logs`, `vm console`, `vm guest-agent`, `vm rename`

- `VM` (required): RID or name.
- `NEW_NAME` (required for `rename`): new VM name.
- `-F, --follow` (`logs` only): keep polling and print only lines appended
  since the last poll; `--interval SECONDS` sets the poll interval (default: `1.0`).
  Press `Ctrl-C` to stop.
- `--baudrate, -b N` (`console` only): serial baud rate (default: `115200`).
- `--takeover / --observe` (`console` only): request input control or attach
  read-only (default: `--takeover`). Press `Enter`, then type `~.` to detach.
- `-n, --node NODE`: target node.
- `-f, --format`, `-c, --column`: output options (`guest-agent` only; `rename`
  takes `-f/--format` and prints `{"rid","name","renamed"}` in machine modes).

### `vm vnc`

Expose the VM's VNC console on a loopback port and open a local viewer. The CLI
relays the node's WebSocket VNC stream to plain RFB, so the viewer talks to the
CLI, not the node. The command prints the VNC password once; enter it in the viewer.

- `VM` (required): RID or name. The VM must be running and have VNC enabled.
- `--overtake / --no-overtake`: take over an existing VNC session instead of
  reporting that another client has attached (default: `--no-overtake`).
- `--viewer CMD`: viewer command template; the command substitutes `{host}`,
  `{port}`, and `{url}`. By default the CLI uses the first installed viewer it knows
  (`xtigervncviewer`, `vncviewer`, `krdc`, `remmina`, `gvncviewer`, `vinagre`,
  or macOS `open`).
- `--local-port N`: loopback port for the bridge (default: `0`, pick a free
  port).
- `--print-only`: print the local `vnc://` address without starting a viewer.
- `-n, --node NODE`: target node.

The bridge keeps running until `Ctrl-C` and reopens the node session for each
viewer connection, so a viewer that probes or reconnects still works. Over SSH,
use `--print-only` and forward the printed port with `ssh -L`.

For KRDC, the CLI sets its quality for the loopback address to
High. The node's VNC server only accepts 32-bit pixels, and KRDC's lower quality
settings request 16- or 8-bit pixels and show a black screen.

Enable VNC first if you created the VM without it:

```sh
sylve vm hardware vnc 101 --set vncEnabled=true --set vncResolution=1024x768 --set vncWait=false
```

### `vm snapshot` and `vm template`

- `snapshot list VM`: `-n/--node`, `-f/--format`, `-c/--column`,
  `--sort-column NAME`, `--filter COLUMN=VALUE`, `-l/--limit N`, `--long`.
- `snapshot create VM`: `--name, -m NAME` (required), `--description, -d TEXT`,
  `-n/--node`, `-f/--format`.
- `snapshot rollback VM SNAPSHOT_ID`: `-y/--yes`, `-n/--node`, `-f/--format`.
- `snapshot delete VM SNAPSHOT_ID`: `-y/--yes`, `-n/--node`, `-f/--format`.
- `template list`: `-n/--node`, `-f/--format`, `-c/--column`,
  `--sort-column NAME`, `--filter COLUMN=VALUE`, `-l/--limit N`.
- `template show TEMPLATE_ID`: `-n/--node`, `-f/--format`, `-c/--column`.
- `template capture VM`: `--name NAME` (required), `-n/--node`, `-w/--wait` (default: `--wait`),
  `-f/--format`.
- `template delete TEMPLATE_ID`: `-y/--yes` (the command also deletes the
  template's stored datasets), `-n/--node`, `-f/--format`.

### Generic Subcommands

All generic VM write subcommands accept `--data/-d`, `--set/--property/-s`, `--param/-p`,
`--dry-run`, `-y/--yes` (destructive only), `-n/--node`, and `-f/--format` (reads also take
`-c/--column`, `--sort-column`, `--filter`, and `-l/--limit`). Small updates
need no JSON; see [sylve-options(7)](../global-options.md):

| Subcommand | Path Arguments |
|---|---|
| `template show` | `templateId` |
| `description`, `domain`, `stats` | `rid` |
| `stats-step` | `rid step` |
| `hardware cpu`, `hardware ram`, `hardware pci`, `hardware vnc` | `rid` |
| `network attach`, `storage attach`, `storage from-image` | `rid` |
| `network detach`, `network set` | `rid networkId` |
| `storage set`, `storage delete` | `rid storageId` |
| `options *`, `registration-purge`, `domain-reinitialize` | `rid` |

## EXIT STATUS

- `0`: Success.
- `1`: API error, failed task, or aborted confirmation.
- `2`: Command-line usage error.

## EXAMPLES

List virtual machines:

```sh
sylve vm list
```

```text
Virtual Machines
 RID  Name     State    Node                 VNC Port
 101  web-01   RUNNING  node1.example.test   5900
 102  db-01    SHUTOFF  node2.example.test   -
```

Create and start a VM from scratch with full hardware, storage, network, VNC,
and boot flags:

```sh
sylve vm create web-01 \
  --node node1.example.test \
  --rid 120 \
  --description "Web frontend" \
  --sockets 1 --cpu 4 --threads 2 \
  --memory 4G \
  --storage-type zvol --pool zroot --disk-size 40G --storage-emulation virtio-blk \
  --iso debian-13-netinst.iso \
  --switch vm-public --switch-emulation virtio --mac-object web-01-mac \
  --vnc --vnc-bind 127.0.0.1 --vnc-port 5920 --vnc-password s3cret \
  --vnc-resolution 1024x768 --no-vnc-wait \
  --serial --tpm --qemu-guest-agent --ignore-umsr --apic --acpi \
  --boot-rom uefi --time-offset utc \
  --start-at-boot --start-order 10 \
  --pci-device 5 --extra-bhyve-option=-A \
  --start --wait --yes
```

```text
Created and started VM web-01 (120) on node1.example.test.
VNC password: s3cret
```

Deploy three VMs from a template:

```sh
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
# Created VM(s) from template 'debian-13' on node1.example.test.
```

Provision with cloud-init or preview a YAML config file with `--dry-run`:

```sh
sylve vm create web-02 --iso debian-13-cloudinit.iso --pool zroot \
  --cloud-init --user-data user-data.yaml --meta-data meta-data.yaml \
  --network-config network-config.yaml --start --wait

sylve vm create --name web-01 --file web.yaml --dry-run -f json
```

`--file` separates the machine definition from the command line, so the same
file you can review in a pull request and reuse across nodes. Keys are flat
or grouped; flags such as `--memory` override the file.

Provision a VM from scratch:

```yaml
# web.yaml
name: web-01
node: node1.example.test
description: customer web frontend

cpu:
  sockets: 1
  cores: 4
  threads: 1
memory: 4G

storage:
  type: zvol
  pool: zroot
  size: 40G
  emulation: virtio-blk

network:
  switch: vm-switch
  emulation: virtio

vnc:
  enabled: true
  resolution: 1024x768

boot:
  rom: uefi

options:
  serial: true
  qemu_guest_agent: true
```

```sh
sylve vm create --file web.yaml --dry-run   # print the request without sending it
sylve vm create --file web.yaml --memory 8G --yes
```

The same definition as JSON, for generated files:

```json
{
  "name": "web-01",
  "cpu": { "cores": 4 },
  "memory": "4G",
  "storage": { "type": "zvol", "pool": "zroot", "size": "40G" },
  "network": { "switch": "vm-switch" }
}
```

Clone a template three times, numbering from RID 200:

```yaml
# fleet.yaml
template: debian-13
count: 3
startRid: 200
namePrefix: web
storagePools:
  0: zroot        # sourceStorageId: target pool
```

```sh
sylve vm create --file fleet.yaml --start --wait --yes
```

Power actions, live migration, snapshots, templates, and hardware updates:

```sh
sylve vm start 101 102 --wait
sylve vm console 101 --baudrate 115200
sylve vm vnc 101
sylve vm migrate 101 --target node2.example.test --dry-run
sylve vm migrate 101 --target node2.example.test --wait
sylve vm snapshot create 101 --name pre-upgrade --description "before 0.4"
sylve vm snapshot rollback 101 1 --yes
sylve vm template capture 101 --name debian-web --wait
sylve vm hardware cpu 101 --set cpuSockets=1 --set cpuCores=4 --set cpuThreads=2 -f json
sylve vm delete 101 --keep-volumes --keep-raw-disks --keep-macs --yes
```

Resize RAM or CPU without JSON, previewing the exact request first.
Integer byte fields take raw byte counts, so `4294967296` means 4 GiB:

```sh
sylve vm hardware ram 101 --set ram=4294967296 --dry-run -f json
# {"method":"PUT","path":"/vm/101/hardware/ram","body":{"ram":4294967296}}

sylve vm hardware ram 101 --set ram=4294967296        # 4 GiB
sylve vm hardware cpu 101 --set cpuSockets=1 --set cpuCores=4 --set cpuThreads=2
sylve vm options boot-order 101 --set bootOrder=10 --set startAtBoot=true
sylve vm options shutdown-wait-time 101 --set waitTime=60
```

Arrays and arrays of objects accept repeatable `--set` flags (with `k=v` pairs for objects) or inline YAML:

```sh
sylve vm hardware cpu 101 --set cpuSockets=1 --set cpuCores=4 --set cpuThreads=1 \
  --set 'cpuPinning=cores=[0, 1],socket=0' --dry-run -f json
# body: {"cpuSockets":1,"cpuCores":4,"cpuThreads":1,"cpuPinning":[{"cores":[0,1],"socket":0}]}

sylve vm options extra-bhyve 101 --set extraBhyveOptions=-A,-H
sylve vm hardware cpu 101 --set cpuSockets=1 --set cpuCores=4 --set cpuThreads=1 \
  --set 'cpuPinning=[{cores: [0, 1], socket: 0}]'
```

Slice list output to the rows and columns you need. `vm list` and
`vm snapshot list` both take `-c/--column`, `--sort-column`, `--filter`,
and `-l/--limit`, and both take `--long` for the full column set:

```sh
sylve vm list --long -c RID,Name,State,Node -l 5
sylve vm list --filter State=RUNNING --sort-column Name
sylve vm snapshot list 101 --long --sort-column Name --filter Name=pre -l 10
sylve vm template list --filter Name=debian --sort-column Name -c ID,Name
```

Full snapshot lifecycle for a VM:

```sh
sylve vm snapshot create 101 --name pre-upgrade --description "before 0.4"
sylve vm snapshot list 101 --long
sylve vm snapshot rollback 101 1 --yes
sylve vm snapshot delete 101 1 --yes
```

Capture a template, deploy from it, and migrate with a preflight check
first. Draining a node for maintenance works the same way
(`sylve node drain --help`):

```sh
sylve vm template capture 101 --name debian-web --wait
sylve vm template list --filter Name=debian-web
sylve vm create --template debian-web --node node2.example.test --rid 121 --yes
sylve vm migrate 101 --target node2.example.test --dry-run   # preflight only
sylve vm migrate 101 --target node2.example.test --wait
sylve node drain node1.example.test --dry-run
```

Preview a ready-made definition file, overriding values on the command
line. Run from the repo root so the relative cloud-init paths resolve:

```sh
sylve vm create --file examples/vm/fedora-cloud.yaml --dry-run -f json
sylve vm create --file examples/vm/fedora-cloud.yaml --memory 8G --yes
```

## SEE ALSO

[sylve(1)](../../README.md),
[sylve-jail(1)](jail.md),
[sylve-cloud-init(1)](cloud-init.md),
[sylve-download(1)](download.md),
[sylve-task(1)](task.md),
[sylve-options(7)](../global-options.md)
