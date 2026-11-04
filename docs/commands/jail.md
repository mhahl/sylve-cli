# SYLVE-JAIL(1)

## NAME

`sylve-jail` - manage FreeBSD jails, snapshots, pkgbase bootstraps, and templates

## SYNOPSIS

```sh
sylve jail COMMAND [ARGS ...]
```

## DESCRIPTION

`sylve jail` lists, inspects, starts, stops, migrates, snapshots, and deletes
FreeBSD jails across Sylve cluster nodes, and manages `pkgbase` jail bootstraps
and jail templates.

## SUBCOMMANDS

| Subcommand | Description |
|---|---|
| `list` | List jails across nodes |
| `show JAIL` | Show full details for a jail by CTID or name |
| `start`, `stop`, `restart` | Power actions on one or more jails |
| `migrate JAIL` | Validate preflight and migrate a jail to another node |
| `delete JAIL` | Delete a jail, with flags to keep its root dataset and MACs |
| `logs JAIL` | Display jail console logs |
| `console JAIL` | Attach to a running jail's interactive console |
| `guest-info JAIL` | Display live OS and network data |
| `rename JAIL NEW_NAME` | Rename a jail |
| `snapshot list/create/rollback/delete` | Manage ZFS jail snapshots |
| `bootstrap list/create/delete` | Manage `pkgbase` jail bootstraps |
| `template list/show/capture/deploy/delete` | Manage jail templates |
| `create [NAME]` | Create a jail from flags or a YAML/JSON file |
| `description`, `hardware cpu/ram/resource-limits` | Generic jail hardware update commands |
| `network inheritance/attach/detach/set` | Generic jail network commands |
| `options additional/allowed/boot-order/devfs-rules/execution-timeout/fstab/lifecycle-hooks/metadata/resolv-conf/wol` | Generic jail option commands |
| `root-mountpoint`, `state`, `stats`, `stats-step`, `validate`, `zfs-sources` | Generic read and validation commands |

## OPTIONS

### `jail list` and `jail show`

- `list`: `-n, --node NODE`, `-f, --format`, `-c, --column`,
  `--sort-column NAME`, `--long` (adds the `Limits` column).
- `show JAIL`: `JAIL` (CTID or name), `--long` (pretty-prints nested storage,
  network, snapshot, and hook JSON and prints full multi-line fstab/resolv.conf/logs),
  `-n, --node NODE`, `-f, --format`, `-c, --column`.

### `jail create`

- `NAME` / `--name NAME`
  Jail name. `--name` overrides the positional argument.
- `-n, --node NODE`
  Target node.
- `--ctid CTID`
  Jail CTID (`1`–`9999`, default: next free guest ID).
- `--pool, -p POOL`
  ZFS pool for the jail root dataset.
- `--type, -t TYPE`
  `freebsd` or `linux` (default: `freebsd`).
- `--bootstrap NAME`
  `pkgbase` bootstrap name (e.g. `15-1-Base`). Resolved against the pool.
- `--base TEXT`
  Base release for the jail.
- `--cores N`, `--memory SIZE`
  CPU core limit and memory limit, e.g. `--memory 2G` (parsed to bytes).
- `--resource-limits / --no-resource-limits`
  Enforce `rctl` limits.
- `--description, -d TEXT`
  Jail description (up to 1024 characters).
- `--hostname HOSTNAME`
  Hostname inside the jail (defaults to the name).
- `--switch NAME`
  Network switch name, or `none` (default: no switch).
- `--dhcp / --no-dhcp`, `--slaac / --no-slaac`
  Configure addresses via DHCP or IPv6 SLAAC.
- `--inherit-ipv4 / --no-inherit-ipv4`, `--inherit-ipv6 / --no-inherit-ipv6`
  Inherit host addresses.
- `--ipv4 ADDR`, `--ipv4-gw ADDR`, `--ipv6 ADDR`, `--ipv6-gw ADDR`
  Static addresses and gateways.
- `--mac MAC`, `--mac-object NAME|ID`
  Static MAC address or existing MAC object (pass one, not both).
- `--vlan-mode MODE`, `--vlan-untagged ID`, `--vlan-tagged ID`
  VLAN policy for filtered switches (`--vlan-tagged` is repeatable).
- `--start-at-boot / --no-start-at-boot`, `--start-order N`
  Autostart at host boot (default: off) and boot order (`0`).
- `--devfs-ruleset TEXT`, `--fstab TEXT`, `--resolv-conf TEXT`
  DevFS, fstab, and resolv.conf configuration.
- `--additional-options TEXT`, `--allowed-option TEXT`
  Extra `jail.conf` options (`--allowed-option` is repeatable).
- `--metadata-env TEXT`, `--metadata-meta TEXT`
  Metadata environment and document.
- `--clean-environment / --no-clean-environment`
  Start the jail with a clean environment.
- `--zfs-source-dataset DATASET`, `--zfs-source-guid GUID`,
  `--zfs-source-mode {copy,rename}`
  Clone from an existing ZFS dataset instead of a bootstrap.
- `--file FILE`
  Read the create configuration from a YAML or JSON file. Keys may be flat
  (`cores`, `memory`, `switch`, `pool`) or grouped under `cpu`, `network`,
  `boot`, and `options`. Command-line flags override file values.
- `--set KEY=VALUE`
  Set any other API field without JSON (repeatable, dotted keys nest), e.g.
  `--set hooks.prestart.enabled=true`. Values go through the same parsing as
  flags, so `--set memory=2G` works.
- `--start`
  Start the jail as soon as creation finishes.
- `-w, --wait / --no-wait`
  Wait for the start task (default: `--wait`, pass `--no-wait` to skip).
- `--dry-run`
  Print the normalized API payload without creating anything.
- `-y, --yes`
  Skip interactive confirmation.
- `-f, --format {table,json,yaml,value,csv}`
  Output format (default: `table`).

On a terminal, `jail create` prints a confirmation plan before sending the API
request unless you pass `-y` / `--yes` or `--dry-run`.

### `jail start`, `stop`, `restart`

- `JAILS...` (required)
  One or more CTIDs or names.
- `-n, --node NODE`
  Target node.
- `-w, --wait / --no-wait`
  Wait for the lifecycle task (default: `--no-wait`). Action commands start
  immediately; pass `--wait` to block until the task finishes.
- `-f, --format`
  Output format. With `json`/`yaml`/`csv`/`value` the command prints each jail's
  result (`action`, `ctid`, `name`, `node`, `outcome`, `status`, `taskId`)
  instead of prose. A failure on one jail does not stop the others; the command
  reports every failure and exits `1`.

### `jail migrate`

- `JAIL` (required)
  CTID or name.
- `--target, -t NODE` (required)
  Destination node hostname or UUID.
- `--validate-only`, `--dry-run`
  Run preflight validation only.
- `-n, --node NODE`
  Source node.
- `-w, --wait / --no-wait`
  Wait for migration completion (default: `--wait`).
- `-f, --format`
  Output format. With `json`/`yaml`/`csv`/`value` the command prints the
  migration result (`ctid`, `source`, `target`, `status`, `taskId`) instead of prose.

### `jail delete`

- `JAIL` (required)
  CTID or name.
- `--delete-rootfs / --keep-rootfs`
  Delete the root ZFS dataset (default: `--delete-rootfs`).
- `--delete-macs / --keep-macs`
  Delete unused MAC objects (default: `--delete-macs`).
- `--dry-run`
  Print what the command would delete (CTID, name, node, root dataset) without deleting anything.
- `-y, --yes`, `-n, --node NODE`, `-f, --format`
  Skip confirmation; target node; output format.

### `jail logs`, `jail console`, `jail guest-info`, `jail rename`

- `JAIL` (required): CTID or name.
- `NEW_NAME` (required for `rename`): new jail name.
- `-n, --node NODE`: target node.
- `-f, --format`, `-c, --column`: output options (`guest-info` only; `rename`
  takes `-f/--format` and prints `{"ctid","name","renamed"}` in machine modes).
- `console` attaches over WebSocket. Press `Enter`, then type `~.` to detach.

### `jail snapshot`, `jail bootstrap`, and `jail template`

- `snapshot list JAIL`: `-n/--node`, `-f/--format`, `-c/--column`,
  `--sort-column NAME`, `--filter COLUMN==VALUE|COLUMN!=VALUE|COLUMN~VALUE`, `-l/--limit N`, `--long`.
- `snapshot create JAIL`: `--name, -m NAME` (required),
  `--description, -d TEXT`, `-n/--node`, `-f/--format`.
- `snapshot rollback JAIL SNAPSHOT_ID`: `-y/--yes`, `-n/--node`, `-f/--format`.
- `snapshot delete JAIL SNAPSHOT_ID`: `-y/--yes`, `-n/--node`, `-f/--format`.
- `bootstrap list`: `--pool, -p POOL` (required), `-n/--node`, `-f/--format`,
  `-c/--column`, `--sort-column NAME`, `--filter COLUMN==VALUE|COLUMN!=VALUE|COLUMN~VALUE`, `-l/--limit N`.
- `bootstrap create`: `--pool, -p POOL` (required), `--major N` (required),
  `--minor N` (default: `0`), `--type TYPE` (default: `base`, e.g. `base` or
  `minimal`), `-n/--node`, `-f/--format`.
- `template list`: `-n/--node`, `-f/--format`, `-c/--column`,
  `--sort-column NAME`, `--filter COLUMN=VALUE`, `-l/--limit N`.

### Generic Subcommands

All generic jail write subcommands accept `--data/-d`, `--set/--property/-s`, `--param/-p`,
`--dry-run`, `-y/--yes` (destructive only), `-n/--node`, and `-f/--format`. Small updates need no
JSON: `sylve jail hardware cpu 201 --set cores=4`.

| Subcommand | Path Arguments |
|---|---|
| `description`, `hardware cpu`, `hardware ram`, `hardware resource-limits` | `ctid` |
| `network inheritance`, `network attach` | `ctid` |
| `network detach`, `network set` | `ctid networkId` |
| `options *`, `root-mountpoint`, `state`, `stats`, `template capture` | `ctid` |
| `stats-step` | `ctid step` |
| `template show`, `template delete`, `template deploy` | `templateId` |
| `bootstrap delete` | `name` |
| `validate`, `zfs-sources` | none |

## EXIT STATUS

- `0`: Success.
- `1`: API error, failed task, or aborted confirmation.
- `2`: Command-line usage error.

## EXAMPLES

List jails across the cluster:

```sh
sylve jail list
```

```text
FreeBSD Jails
 CTID  Name     State    Type     Node                 Cores  Memory
 201   dns-01   RUNNING  freebsd  node1.example.test   2      2.0 GiB
 202   cache    STOPPED  freebsd  node2.example.test   1      1.0 GiB
```

Create a jail from flags, or preview a definition file with `--dry-run`:

```sh
sylve jail create dns-03 --ctid 203 --pool zroot --type freebsd \
  --bootstrap 15-1-Base --cores 2 --memory 2G --resource-limits \
  --switch vm-switch --dhcp --description "secondary resolver" \
  --node node1.example.test --dry-run -f json

sylve jail create dns-03 --pool zroot --bootstrap 15-1-Base \
  --switch vm-switch --dhcp --start --yes
```

`--file` separates the machine definition from the command line, so the same
file you can review in a pull request and reuse across nodes. Keys are flat
or grouped; flags such as `--memory` override the file:

```yaml
# jail.yaml
name: dns-03
ctid: 203
type: freebsd
pool: zroot
bootstrap: 15-1-Base
description: secondary resolver

cpu:
  cores: 2
  memory: 2G

network:
  switch: vm-switch
  dhcp: true

options:
  resource_limits: true
```

```sh
sylve jail create --file jail.yaml --dry-run   # print the request without sending it
sylve jail create --file jail.yaml --memory 4G --yes
```

Migrating from the old raw-body syntax: `--data @jail.yaml` becomes
`--file jail.yaml`, and inline `--data '{"cores":4}'` becomes
`--set cores=4`.

Create and list a jail snapshot:

```sh
sylve jail snapshot create 201 --name pre-upgrade --description "before package update" --node node1.example.test
# Created snapshot 'pre-upgrade' for Jail 201.

sylve jail snapshot list 201 --long --format json -c 'ID,Name,Snapshot,Root Dataset,Created At'
```

```json
[
  {
    "id": 1,
    "name": "pre-upgrade",
    "snapshotName": "zroot/jail/201@pre-upgrade",
    "rootDataset": "zroot/jail/201",
    "createdAt": "2026-10-28T20:00:00Z"
  }
]
```

Queue and list a FreeBSD 14.2 `pkgbase` bootstrap:

```sh
sylve jail bootstrap create --pool zroot --major 14 --minor 2 --type base --node node1.example.test
# Queued jail bootstrap (14.2 base) on pool 'zroot'.

sylve jail bootstrap list --pool zroot
```

Migrate, update CPU limits, deploy a template, or delete a jail:

```sh
sylve jail migrate 201 --target node2.example.test --dry-run
sylve jail migrate 201 --target node2.example.test --wait
sylve jail hardware cpu 201 --set cores=4 --node node1.example.test -f json
sylve jail template deploy 3 --set name=dns-02 --set ctid=203 -f json
sylve jail delete 201 --keep-rootfs --keep-macs --yes
```

Resize jail RAM or CPU without JSON, previewing the exact request first.
Integer byte fields take raw byte counts, so `2147483648` means 2 GiB:

```sh
sylve jail hardware ram 201 --set memory=2147483648 --dry-run -f json
# {"method":"PUT","path":"/jail/201/hardware/ram","body":{"memory":2147483648}}

sylve jail hardware ram 201 --set memory=2147483648     # 2 GiB
sylve jail hardware cpu 201 --set cores=4
sylve jail hardware resource-limits 201 --set enabled=true
sylve jail options boot-order 201 --set bootOrder=5 --set startAtBoot=true
```

Arrays take comma-separated values or one YAML value; nested objects take dotted keys:

```sh
sylve jail options allowed 201 --set allowedOptions=exec,mount --dry-run -f json
# body: {"allowedOptions":["exec","mount"]}

sylve jail options lifecycle-hooks 201 \
  --set hooks.prestart.enabled=true --set hooks.prestart.script=/bin/true \
  --dry-run -f json
# body: {"hooks":{"prestart":{"enabled":true,"script":"/bin/true"}}}
```

Slice list output to the rows and columns you need. `jail list`,
`jail snapshot list`, and `jail template list` take `-c/--column`,
`--sort-column`, `--filter`, and `-l/--limit`; `jail list` also takes
`--long` for the extra `Limits` column:

```sh
sylve jail list --long -c CTID,Name,State,Node -l 5
sylve jail list --filter State=RUNNING --sort-column Name
sylve jail snapshot list 201 --long --sort-column Name --filter Name=pre -l 10
sylve jail template list --filter Name=dns --sort-column Name
```

Full snapshot and template lifecycle for a jail:

```sh
sylve jail snapshot create 201 --name pre-upgrade --description "before package update"
sylve jail snapshot list 201 --long
sylve jail snapshot rollback 201 1 --yes
sylve jail template capture 201 --set name=dns-tmpl --dry-run -f json
sylve jail template capture 201 --set name=dns-tmpl
sylve jail template deploy 3 --set name=dns-02 --set ctid=203 --dry-run -f json
sylve jail template deploy 3 --set name=dns-02 --set ctid=203
sylve jail snapshot delete 201 1 --yes
```

Attach a NIC or set jail options without JSON. The dry run shows the
exact request body before anything changes:

```sh
sylve jail network attach 201 --set name=vnet0 --set switchName=vm-switch --set dhcp=true --dry-run -f json
sylve jail network attach 201 --set name=vnet0 --set switchName=vm-switch --set dhcp=true
sylve jail network inheritance 201 --set ipv4=false --set ipv6=false
sylve jail options resolv-conf 201 --set resolvConf="nameserver 10.0.0.1"
```

Preview a ready-made definition file, overriding values on the command
line. Run from the repo root:

```sh
sylve jail create --file examples/jail/basic.yaml --dry-run -f json
sylve jail create --file examples/jail/basic.yaml --memory 4G --yes
```

## SEE ALSO

[sylve(1)](../../README.md),
[sylve-vm(1)](vm.md),
[sylve-zfs(1)](zfs.md),
[sylve-task(1)](task.md),
[sylve-options(7)](../global-options.md)
