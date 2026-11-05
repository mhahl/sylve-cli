# SYLVE-ZFS(1)

## NAME

`sylve-zfs` - manage ZFS storage pools, datasets, snapshots, periodic snapshot jobs, and telemetry

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
| `pool` | `list`, `show`, `status`, `scrub`, `scrub-runs`, `scrub-schedules`, `scrub-schedule-create`, `scrub-schedule-set`, `scrub-schedule-delete`, `create`, `delete`, `set`, `detach`, `replace-device`, `disks-usage` |
| `dataset` | `list`, `create-fs`, `create-vol`, `delete`, `set`, `bulk-delete`, `paginated`, `volume-set`, `volume-flash` |
| `snapshot` | `list`, `create`, `rollback`, `delete` |
| `periodic` | `list`, `create`, `set`, `delete`, `bulk-delete` |
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

- `list`: `-n/--node`, `-f/--format`, `-c/--column`, `--sort-column`,
  `--filter COLUMN=VALUE`, `-l/--limit N`.
- `create DATASET`: `DATASET` (name or GUID), `--name, -m NAME` (required,
  snapshot name after `@`), `-r, --recursive / --no-recursive` (default: off),
  `-n/--node`.
- `rollback SNAPSHOT`: `SNAPSHOT` (`dataset@snap` or GUID),
  `--destroy-more-recent`, `-y/--yes`, `-n/--node`.
- `delete SNAPSHOT`: `SNAPSHOT` (`dataset@snap` or GUID),
  `-r, --recursive / --no-recursive` (default: off), `-n/--node`.

### `periodic`

- `list`: `-n/--node`, `-f/--format`, `-c/--column`, `--sort-column NAME`,
  `--filter COLUMN=VALUE`, `-l/--limit N`, `--long`.

### Generic Subcommands

All remaining write subcommands accept `--data/-d`, `--set/--property/-s`, `--param/-p`,
`--dry-run`, `-y/--yes` (destructive only), `-n/--node`, and `-f/--format` (reads also take
`-c/--column`, `--sort-column`, `--filter`, and `-l/--limit`). Small updates
need no JSON; see [sylve-options(7)](../global-options.md). Pool and dataset
subcommands that take a `pool` or `dataset` positional accept a **name or GUID**.

| Subcommand | Path Arguments |
|---|---|
| `pool delete`, `pool set`, `pool detach`, `pool replace-device`, `pool scrub-runs` | `pool` (name or GUID) |
| `pool scrub-schedule-set`, `pool scrub-schedule-delete` | `id` |
| `dataset set`, `dataset volume-set`, `dataset volume-flash` | `dataset` (name or GUID) |
| `periodic set`, `periodic delete` | `id` |
| `pool create`, `pool disks-usage`, `pool scrub-schedules`, `pool scrub-schedule-create`, `dataset bulk-delete`, `dataset paginated`, `periodic create`, `periodic bulk-delete`, `dashboard-*` | none |

## EXIT STATUS

- `0`: Success.
- `1`: API error or aborted confirmation.
- `2`: Command-line usage error.

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
sylve zfs periodic create --node node1.example.test \
  --set guid=zroot --set prefix=auto --set keepLast=24 --set recursive=true \
  -f json
```

Slice list output to the rows and columns you need. The pool, dataset,
snapshot, and periodic lists all take `-c/--column`, `--filter`, and
`-l/--limit`; pool, dataset, and periodic lists also take `--long` and
`--sort-column`:

```sh
sylve zfs pool list --all --long -c Name,State,Size,Free -l 5
sylve zfs dataset list --type VOLUME --long --sort-column Name
sylve zfs snapshot list --filter Name=pre --sort-column Name -l 10
sylve zfs periodic list --long --filter Prefix=auto
```

Full snapshot lifecycle, then a recurring schedule on top:

```sh
sylve zfs snapshot create zroot/data --name pre-upgrade --node node1.example.test
sylve zfs snapshot list --filter Name=pre-upgrade
sylve zfs snapshot rollback zroot/data@pre-upgrade --destroy-more-recent --yes
sylve zfs periodic create --node node1.example.test \
  --set guid=zroot --set prefix=auto --set keepLast=24 --set recursive=true
sylve zfs periodic list --filter Prefix=auto
sylve zfs snapshot delete zroot/data@pre-upgrade --yes
```

Tune a dataset or volume without JSON, previewing the exact request
first. Dotted `--set` keys nest into the `properties` object:

```sh
sylve zfs dataset set <guid> --set properties.compression=lz4 --dry-run -f json
sylve zfs dataset set <guid> --set properties.compression=lz4
sylve zfs dataset volume-set <guid> --set properties.volsize=10737418240 --dry-run -f json
# 10737418240 bytes = 10 GiB
sylve zfs pool detach <guid> --set device=/dev/da1 --dry-run -f json
```

## SEE ALSO

[sylve(1)](../../README.md),
[sylve-vm(1)](vm.md),
[sylve-jail(1)](jail.md),
[sylve-backup(1)](backup.md),
[sylve-replication(1)](replication.md),
[sylve-options(7)](../global-options.md)
