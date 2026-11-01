# SYLVE-JAIL(1)

## NAME

`sylve-jail` — manage FreeBSD jails, snapshots, pkgbase bootstraps, and templates

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
| `delete JAIL` | Delete a jail and optionally its root dataset and MACs |
| `logs JAIL` | Display jail console logs |
| `console JAIL` | Attach to a running jail's interactive console |
| `guest-info JAIL` | Display live OS and network data |
| `rename JAIL NEW_NAME` | Rename a jail |
| `snapshot list/create/rollback/delete` | Manage ZFS jail snapshots |
| `bootstrap list/create` | List or build `pkgbase` jail bootstraps |
| `template list` | List jail templates |
| `create [NAME]` | Create a jail from flags or a YAML/JSON file |
| `description`, `hardware-cpu`, `hardware-ram`, `hardware-resource-limits` | Generic jail hardware update commands |
| `network-inheritance`, `network-attach`, `network-detach`, `network-update` | Generic jail network commands |
| `options-additional`, `options-allowed`, `options-boot-order`, `options-devfs-rules`, `options-execution-timeout`, `options-fstab`, `options-lifecycle-hooks`, `options-metadata`, `options-resolv-conf`, `options-wol` | Generic jail option commands |
| `root-mountpoint`, `state`, `stats` | Generic read commands |
| `template-show`, `template-delete`, `template-capture`, `template-deploy` | Generic jail template commands |
| `bootstrap-delete` | Generic bootstrap deletion command |

## OPTIONS

### `jail list` and `jail show`

- `list`: `-n, --node NODE`, `-f, --format`, `-c, --column`,
  `--sort-column NAME`, `--long` (adds the `Limits` column).
- `show JAIL`: `JAIL` (CTID or name), `-n, --node NODE`, `-f, --format`,
  `-c, --column`.

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
  Start the jail immediately after creation.
- `-w, --wait / --no-wait`
  Wait for the start task (default: `--no-wait`).
- `--dry-run`
  Print the normalized API payload without creating anything.
- `-y, --yes`
  Skip interactive confirmation.
- `-f, --format {table,json,yaml,value,csv}`
  Output format (default: `table`).

On a terminal, `jail create` prints a confirmation plan before sending the API
request unless `-y` / `--yes` or `--dry-run` is given.

### `jail start`, `stop`, `restart`

- `JAILS...` (required)
  One or more CTIDs or names.
- `-n, --node NODE`
  Target node.
- `-w, --wait / --no-wait`
  Wait for the lifecycle task (default: `--no-wait`).
- `-f, --format`
  Output format. With `json`/`yaml`/`csv`/`value` each jail's result (`action`,
  `ctid`, `name`, `node`, `outcome`, `status`, `taskId`) is printed instead of
  prose. A failure on one jail does not stop the others; the command reports
  every failure and exits `1`.

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
  Output format. With `json`/`yaml`/`csv`/`value` the migration result
  (`ctid`, `source`, `target`, `status`, `taskId`) is printed instead of prose.

### `jail delete`

- `JAIL` (required)
  CTID or name.
- `--delete-rootfs / --keep-rootfs`
  Delete the root ZFS dataset (default: `--delete-rootfs`).
- `--delete-macs / --keep-macs`
  Delete unused MAC objects (default: `--delete-macs`).
- `--dry-run`
  Print what would be deleted (CTID, name, node, root dataset) without deleting.
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
  `--sort-column NAME`, `--filter COLUMN=VALUE`, `-l/--limit N`, `--long`.
- `snapshot create JAIL`: `--name, -m NAME` (required),
  `--description, -d TEXT`, `-n/--node`, `-f/--format`.
- `snapshot rollback JAIL SNAPSHOT_ID`: `-y/--yes`, `-n/--node`, `-f/--format`.
- `snapshot delete JAIL SNAPSHOT_ID`: `-y/--yes`, `-n/--node`, `-f/--format`.
- `bootstrap list`: `--pool, -p POOL` (required), `-n/--node`, `-f/--format`,
  `-c/--column`, `--sort-column NAME`, `--filter COLUMN=VALUE`, `-l/--limit N`.
- `bootstrap create`: `--pool, -p POOL` (required), `--major N` (required),
  `--minor N` (default: `0`), `--type TYPE` (default: `base`, e.g. `base` or
  `minimal`), `-n/--node`, `-f/--format`.
- `template list`: `-n/--node`, `-f/--format`, `-c/--column`,
  `--sort-column NAME`, `--filter COLUMN=VALUE`, `-l/--limit N`.

### Generic Subcommands

All generic jail subcommands accept `--data/-d`, `--set/-s`, `--param/-p`,
`--dry-run`, `-y/--yes`, `-n/--node`, and `-f/--format`. Small updates need no
JSON: `sylve jail hardware-cpu 201 --set cores=4`.

| Subcommand | Path Arguments |
|---|---|
| `description`, `hardware-cpu`, `hardware-ram`, `hardware-resource-limits` | `ctid` |
| `network-inheritance`, `network-attach` | `ctid` |
| `network-detach`, `network-update` | `ctid networkId` |
| `options-*`, `root-mountpoint`, `state`, `stats`, `template-capture` | `ctid` |
| `template-show`, `template-delete`, `template-deploy` | `templateId` |
| `bootstrap-delete` | `name` |

## EXIT STATUS

- `0` — Success.
- `1` — API error, failed task, or aborted confirmation.
- `2` — Command-line usage error.

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
file can be reviewed in a pull request and reused across nodes. Keys are flat
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
sylve jail hardware-cpu 201 --set cores=4 --node node1.example.test -f json
sylve jail template-deploy 3 --set name=dns-02 --set ctid=203 -f json
sylve jail delete 201 --keep-rootfs --keep-macs --yes
```

## SEE ALSO

[sylve(1)](../../README.md),
[sylve-vm(1)](vm.md),
[sylve-zfs(1)](zfs.md),
[sylve-task(1)](task.md),
[sylve-options(7)](../global-options.md)
