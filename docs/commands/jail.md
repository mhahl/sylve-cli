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
| `create`, `description`, `hardware-cpu`, `hardware-ram`, `hardware-resource-limits` | Generic jail creation and hardware update commands |
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

### `jail start`, `stop`, `restart`

- `JAILS...` (required)
  One or more CTIDs or names.
- `-n, --node NODE`
  Target node.
- `-w, --wait / --no-wait`
  Wait for the lifecycle task (default: `--no-wait`).

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

### `jail delete`

- `JAIL` (required)
  CTID or name.
- `--delete-rootfs / --keep-rootfs`
  Delete the root ZFS dataset (default: `--delete-rootfs`).
- `--delete-macs / --keep-macs`
  Delete unused MAC objects (default: `--delete-macs`).
- `-y, --yes`, `-n, --node NODE`
  Skip confirmation; target node.

### `jail logs`, `jail console`, `jail guest-info`, `jail rename`

- `JAIL` (required): CTID or name.
- `NEW_NAME` (required for `rename`): new jail name.
- `-n, --node NODE`: target node.
- `-f, --format`, `-c, --column`: output options (`guest-info` only).
- `console` attaches over WebSocket; type `Enter` then `~.` to detach.

### `jail snapshot`, `jail bootstrap`, and `jail template`

- `snapshot list JAIL`: `-n/--node`, `-f/--format`, `-c/--column`, `--long`.
- `snapshot create JAIL`: `--name, -m NAME` (required),
  `--description, -d TEXT`, `-n/--node`.
- `snapshot rollback JAIL SNAPSHOT_ID`: `-y/--yes`, `-n/--node`.
- `snapshot delete JAIL SNAPSHOT_ID`: `-n/--node`.
- `bootstrap list`: `--pool, -p POOL` (required), `-n/--node`, `-f/--format`,
  `-c/--column`.
- `bootstrap create`: `--pool, -p POOL` (required), `--major N` (required),
  `--minor N` (default: `0`), `--type TYPE` (default: `base`, e.g. `base` or
  `minimal`), `-n/--node`.
- `template list`: `-n/--node`, `-f/--format`, `-c/--column`.

### Generic Subcommands

All generic jail subcommands accept `--data/-d`, `--param/-p`, `-y/--yes`,
`-n/--node`, and `-f/--format`:

| Subcommand | Path Arguments |
|---|---|
| `description`, `hardware-cpu`, `hardware-ram`, `hardware-resource-limits` | `ctid` |
| `network-inheritance`, `network-attach` | `ctid` |
| `network-detach`, `network-update` | `ctid networkId` |
| `options-*`, `root-mountpoint`, `state`, `stats`, `template-capture` | `ctid` |
| `template-show`, `template-delete`, `template-deploy` | `templateId` |
| `bootstrap-delete` | `name` |
| `create` | none |

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
+------+---------+---------+---------+---------------------+-------+--------+
| CTID | Name    | State   | Type    | Node                | Cores | Memory |
+------+---------+---------+---------+---------------------+-------+--------+
| 201  | dns-01  | RUNNING | freebsd | node1.example.test  | 2     | 2.0 GiB|
| 202  | cache   | STOPPED | freebsd | node2.example.test  | 1     | 1.0 GiB|
+------+---------+---------+---------+---------------------+-------+--------+
```

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
sylve jail hardware-cpu 201 --data '{"cores":4}' --param dryRun=0 --node node1.example.test -f json
sylve jail template-deploy 3 --data '{"name":"dns-02","ctid":203}' -f json
sylve jail delete 201 --keep-rootfs --keep-macs --yes
```

## SEE ALSO

[sylve(1)](../../README.md),
[sylve-vm(1)](vm.md),
[sylve-zfs(1)](zfs.md),
[sylve-task(1)](task.md),
[sylve-options(7)](../global-options.md)
