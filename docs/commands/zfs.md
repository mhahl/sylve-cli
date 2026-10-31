# SYLVE-ZFS(1)

## NAME

`sylve-zfs` — manage ZFS storage pools, datasets, snapshots, periodic snapshot jobs, and telemetry

## SYNOPSIS

```sh
sylve zfs GROUP COMMAND [ARGS ...]
```

## DESCRIPTION

`sylve zfs` manages ZFS storage pools, filesystems, volumes (`zvol`s),
manual snapshots, and scheduled periodic snapshot jobs across Sylve nodes.

## SUBCOMMANDS

| Group | Subcommands |
|---|---|
| `pool` | `list`, `show`, `status`, `scrub`, `create`, `delete`, `edit`, `detach`, `replace-device`, `disks-usage` |
| `dataset` | `list`, `create-fs`, `create-vol`, `delete`, `edit`, `bulk-delete`, `paginated`, `volume-edit`, `volume-flash` |
| `snapshot` | `list`, `create`, `rollback`, `delete` |
| `periodic` | `list`, `create`, `update`, `delete` |
| top-level | `dashboard-snapshot`, `dashboard-history`, `dashboard-delta` |

## OPTIONS

### `pool`

- `list`: `--all, -a` (include pools not marked usable in Sylve settings),
  `-n, --node NODE`, `-f, --format`, `-c, --column`, `--sort-column`,
  `--long` (adds `GUID`, `Allocated`, and `Dedup`).
- `show POOL` / `status POOL`: `POOL` (name or GUID), `-n/--node`,
  `-f/--format`, `-c/--column`.
- `scrub POOL`: `POOL` (name or GUID), `-n/--node`.

### `dataset`

- `list`: `--type, -t {FILESYSTEM,VOLUME,SNAPSHOT,ALL}`, `-n/--node`,
  `-f/--format`, `-c/--column`, `--sort-column`, `--long`.
- `create-fs`: `--parent, -p PATH` (required, e.g. `zroot`), `--name NAME`
  (required), `-n/--node`.
- `create-vol`: `--parent, -p PATH` (required), `--name NAME` (required),
  `--size, -s SIZE` (required, e.g. `10G`), `-n/--node`.
- `delete DATASET`: `DATASET` (name or GUID),
  `--type, -t {filesystem,volume}` (default: `filesystem`), `-y/--yes`,
  `-n/--node`.

### `snapshot`

- `list`: `-n/--node`, `-f/--format`, `-c/--column`, `--sort-column`.
- `create DATASET`: `DATASET` (name or GUID), `--name, -m NAME` (required,
  snapshot name after `@`), `-r, --recursive / --no-recursive` (default: off),
  `-n/--node`.
- `rollback SNAPSHOT`: `SNAPSHOT` (`dataset@snap` or GUID),
  `--destroy-more-recent`, `-y/--yes`, `-n/--node`.
- `delete SNAPSHOT`: `SNAPSHOT` (`dataset@snap` or GUID),
  `-r, --recursive / --no-recursive` (default: off), `-n/--node`.

### `periodic`

- `list`: `-n/--node`, `-f/--format`, `-c/--column`, `--long`.

### Generic Subcommands

All remaining subcommands accept `--data/-d`, `--param/-p`, `-y/--yes`,
`-n/--node`, and `-f/--format`:

| Subcommand | Path Arguments |
|---|---|
| `pool delete`, `pool edit`, `pool detach`, `pool replace-device` | `guid` |
| `dataset edit`, `dataset volume-edit`, `dataset volume-flash` | `guid` |
| `periodic update`, `periodic delete` | `id` |
| `pool create`, `pool disks-usage`, `dataset bulk-delete`, `dataset paginated`, `periodic create`, `dashboard-*` | none |

## EXIT STATUS

- `0` — Success.
- `1` — API error or aborted confirmation.
- `2` — Command-line usage error.

## EXAMPLES

List ZFS storage pools:

```sh
sylve zfs pool list
```

```text
ZFS Storage Pools
 Name   Node                 State  Size     Free     Frag%
 zroot  node1.example.test   ONLINE 1.8 TiB  1.2 TiB    8.0%
```

List all pools including non-configured ones as JSON, check status, and start a
scrub:

```sh
sylve zfs pool list --all --long --sort-column name --format json -c Name,GUID,State,Size,Free
sylve zfs pool status zroot
sylve zfs pool scrub zroot --node node1.example.test
```

Create and delete filesystems and volumes:

```sh
sylve zfs dataset list --type VOLUME --long
sylve zfs dataset create-fs --parent zroot --name backups --node node1.example.test
sylve zfs dataset create-vol --parent zroot --name data --size 50G --node node1.example.test
sylve zfs dataset delete zroot/backups --type filesystem --dry-run   # preview
sylve zfs dataset delete zroot/backups --type filesystem --yes
```

Create, roll back, and delete ZFS snapshots:

```sh
sylve zfs snapshot create zroot/data --name pre-upgrade --recursive --node node1.example.test
sylve zfs snapshot rollback zroot/data@pre-upgrade --destroy-more-recent --yes
sylve zfs snapshot delete zroot/data@pre-upgrade --recursive --yes
```

Create a periodic snapshot schedule via the generic endpoint:

```sh
sylve zfs periodic create --param validate=1 --node node1.example.test \
  --data '{"pool":"zroot","prefix":"auto","cronExpr":"0 * * * *","keepLast":24,"recursive":true}' \
  -f json
```

## SEE ALSO

[sylve(1)](../../README.md),
[sylve-vm(1)](vm.md),
[sylve-jail(1)](jail.md),
[sylve-backup(1)](backup.md),
[sylve-replication(1)](replication.md),
[sylve-options(7)](../global-options.md)
