# SYLVE-BACKUP(1)

## NAME

`sylve-backup` — manage backup targets, scheduled jobs, restores, and backup events

## SYNOPSIS

```sh
sylve backup GROUP COMMAND [ARGS ...]
```

## DESCRIPTION

`sylve backup` configures remote SSH backup targets, schedules and runs guest
or dataset backup jobs, lists restorable snapshots, queues restores, and tracks
backup execution events.

## SUBCOMMANDS

| Subcommand | Description |
|---|---|
| `target list` | List backup targets |
| `target show TARGET_ID` | Display target details and readiness |
| `target datasets TARGET_ID` | List restorable datasets on a target |
| `target validate TARGET_ID` | Validate SSH/storage connectivity to a target |
| `target delete TARGET_ID` | Delete a disabled backup target |
| `target create`, `target update ID`, `target running-jobs ID`, `target dataset-snapshots ID`, `target vm-metadata ID`, `target jail-metadata ID`, `target restore ID` | Generic target API commands |
| `job list` | List scheduled backup jobs |
| `job run JOB_ID` | Queue an immediate backup job run |
| `job snapshots JOB_ID` | List restorable snapshots for a job |
| `job restore JOB_ID` | Queue a snapshot restore from a job |
| `job delete JOB_ID` | Delete a backup job |
| `job create`, `job update ID` | Generic job API commands |
| `event list` | List recent backup events |
| `event show EVENT_ID` | Show event details or follow live progress |
| `event remote-list` | Generic remote backup event list |

## OPTIONS

### `target`

- `list`: `-f, --format`, `-c, --column`, `--sort-column NAME`, `--long`
  (adds `Port`, `Backup Root`, and `Description`).
- `show TARGET_ID`: `-f/--format`, `-c/--column`.
- `datasets TARGET_ID`: `-f/--format`, `-c/--column`, `--long`.
- `validate TARGET_ID`: takes no additional options.
- `delete TARGET_ID`: `-y, --yes`.

### `job`

- `list`: `--target-id ID`, `--guest-type {vm,jail}`, `--guest-id ID`,
  `-f/--format`, `-c/--column`, `--sort-column`, `--long`.
- `run JOB_ID`: takes no additional options.
- `snapshots JOB_ID`: `--limit, -l N` (default: `100`), `-f/--format`,
  `-c/--column`, `--long`.
- `restore JOB_ID`: `--snapshot, -s NAME` (required),
  `--encryption-key KEY` (for encrypted backups).
- `delete JOB_ID`: `-y, --yes`.

### `event`

- `list`: `--job-id ID`, `--limit, -l N` (default: `50`), `-f/--format`,
  `-c/--column`, `--long`.
- `show EVENT_ID`: `-w, --wait / --no-wait` (default: `--no-wait`),
  `-f/--format`, `-c/--column`.

### Generic Subcommands

All generic backup subcommands accept `--data/-d`, `--param/-p`, `-y/--yes`,
`-n/--node`, and `-f/--format`:

| Subcommand | Path Arguments |
|---|---|
| `target update`, `target running-jobs`, `target dataset-snapshots`, `target vm-metadata`, `target jail-metadata`, `target restore` | `id` |
| `job update` | `id` |
| `target create`, `job create`, `event remote-list` | none |

## EXIT STATUS

- `0` — Success.
- `1` — API error, failed event while waiting, or aborted confirmation.
- `2` — Command-line usage error.

## EXAMPLES

List, inspect, validate, and list datasets on a backup target:

```sh
sylve backup target list
sylve backup target show 1 --format json -c 'Name,SSH Host,Port,Backup Root,Enabled'
sylve backup target datasets 1 --long
sylve backup target validate 1
# Backup target #1 validated successfully.
```

List jobs, trigger an immediate backup, and restore a snapshot:

```sh
sylve backup job list --target-id 1 --guest-type vm --guest-id 101 --long --sort-column name
sylve backup job run 3
sylve backup job snapshots 3 --limit 5 --long
sylve backup job restore 3 --snapshot zroot/vm/101@auto-2026-10-28 --encryption-key 'secret'
# Queued restore of snapshot 'zroot/vm/101@auto-2026-10-28' from backup job #3.
```

Follow a backup event to completion:

```sh
sylve backup event list --job-id 3 --limit 10 --long
sylve backup event show 7 --wait
```

Create a target from a YAML payload file:

```sh
sylve backup target create --data @target.yaml --param validate=1 --node node1.example.test -f json
```

## SEE ALSO

[sylve(1)](../../README.md),
[sylve-replication(1)](replication.md),
[sylve-zfs(1)](zfs.md),
[sylve-options(7)](../global-options.md)
