# SYLVE-BACKUP(1)

## NAME

`sylve-backup` - manage backup targets, scheduled jobs, restores, and backup events

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
| `target create`, `target set ID`, `target readiness ID`, `target running-jobs ID`, `target dataset-snapshots ID`, `target vm-metadata ID`, `target jail-metadata ID`, `target restore ID` | Generic target API commands |
| `job list` | List scheduled backup jobs |
| `job run JOB_ID` | Queue an immediate backup job run |
| `job snapshots JOB_ID` | List restorable snapshots for a job |
| `job restore JOB_ID` | Queue a snapshot restore from a job |
| `job delete JOB_ID` | Delete a backup job |
| `job create`, `job set ID` | Generic job API commands |
| `event list` | List recent backup events |
| `event show EVENT_ID` | Show event details or follow live progress |
| `event remote-list` | Generic remote backup event list |

## OPTIONS

### `target`

- `list`: `-f, --format`, `-c, --column`, `--sort-column NAME`, `--long`
  (adds `Port`, `Backup Root`, and `Description`).
- `show TARGET_ID`: `-f/--format`, `-c/--column`.
- `datasets TARGET_ID`: `-f/--format`, `-c/--column`, `--sort-column NAME`,
  `--filter COLUMN=VALUE`, `-l/--limit N`, `--long`.
- `validate TARGET_ID`: `-f/--format`.
- `delete TARGET_ID`: `-y, --yes`, `-f/--format`.

### `job`

- `list`: `--target-id ID`, `--guest-type {vm,jail}`, `--guest-id ID`,
  `-f/--format`, `-c/--column`, `--sort-column`, `--long`.
- `run JOB_ID`: queue an immediate run (`-f/--format`).
- `snapshots JOB_ID`: `--limit, -l N` (default: `100`), `-f/--format`,
  `-c/--column`, `--sort-column NAME`, `--filter COLUMN=VALUE`, `--long`.
- `restore JOB_ID`: `--snapshot, -s NAME` (required),
  `--encryption-key KEY` (for encrypted backups), `-f/--format`.
- `delete JOB_ID`: `-y, --yes`.

### `event`

- `list`: `--job-id ID`, `--limit, -l N` (default: `50`), `-f/--format`,
  `-c/--column`, `--sort-column NAME`, `--filter COLUMN=VALUE`, `--long`.
- `show EVENT_ID`: `-w, --wait / --no-wait` (default: `--no-wait`),
  `-f/--format`, `-c/--column`.

### Generic Subcommands

All generic backup write subcommands accept `--data/-d`, `--property/--property/-s`, `--param/-p`,
`--dry-run`, `-y/--yes` (destructive only), `-n/--node`, and `-f/--format` (reads also take
`-c/--column`, `--sort-column`, `--filter`, and `-l/--limit`). Small updates
need no JSON; see [sylve-options(7)](../global-options.md):

| Subcommand | Path Arguments |
|---|---|
| `target set`, `target readiness`, `target running-jobs`, `target dataset-snapshots`, `target vm-metadata`, `target jail-metadata`, `target restore` | `id` |
| `job set` | `id` |
| `target create`, `job create`, `event remote-list` | none |

## EXIT STATUS

- `0`: Success.
- `1`: API error, failed event while waiting, or aborted confirmation.
- `2`: Command-line usage error.

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
sylve backup target create --data @target.yaml --node node1.example.test -f json
```

Preview a new backup target before sending it. `backupRoot` must be a ZFS
dataset name (`tank/backups`), not a filesystem path, and the server rejects
anything else at creation time:

```sh
sylve backup target create \
  --property name=offsite \
  --property sshHost=backup.example.test \
  --property backupRoot=tank/backups \
  --property sshPort=22 \
  --dry-run -f json
```

```json
{
  "method": "POST",
  "path": "/cluster/backups/targets",
  "params": null,
  "body": {
    "name": "offsite",
    "sshHost": "backup.example.test",
    "backupRoot": "tank/backups",
    "sshPort": 22
  }
}
```

Preview a new backup job before sending it:

```sh
sylve backup job create \
  --property name=vm101-nightly \
  --property mode=vm \
  --property targetId=1 \
  --property sourceDataset=zroot/vm/101 \
  --property 'cronExpr=0 2 * * *' \
  --property recursive=true \
  --dry-run -f json
```

```json
{
  "method": "POST",
  "path": "/cluster/backups/jobs",
  "params": null,
  "body": {
    "name": "vm101-nightly",
    "mode": "vm",
    "targetId": 1,
    "sourceDataset": "zroot/vm/101",
    "cronExpr": "0 2 * * *",
    "recursive": true
  }
}
```

Disable a job and rename a target with small `--property` updates:

```sh
sylve backup job set 3 --property mode=vm --property name=vm101-nightly --property targetId=1 --property enabled=false --dry-run -f json
sylve backup target set 1 --property 'description=Nightly offsite' --property enabled=true --dry-run -f json
```

Run the full validate -> run -> follow-progress flow for one job:

```sh
sylve backup target validate 1
# Backup target #1 validated successfully.
sylve backup job run 3
sylve backup event show 7 --wait
sylve backup event list --job-id 3 --limit 10 --filter status=SUCCESS --long
```

Slice list output with selection flags:

```sh
sylve backup target list --long --sort-column name --filter enabled=true -l 5
sylve backup target datasets 1 -c Name -c Size --sort-column name -l 5 --long
sylve backup job snapshots 3 -c Name -c Created --filter name=auto --sort-column name -l 5
sylve backup event list --job-id 3 --filter status=FAILED --sort-column created -l 10
```

Queue a dataset restore from a target and clean up with confirmation skipped:

```sh
sylve backup target restore 1 \
  --property remoteDataset=tank/backups/vm-101 \
  --property 'snapshot=zroot/vm/101@auto-2026-10-28' \
  --property destinationDataset=zroot/vm/101-restored \
  --dry-run -f json
sylve backup job delete 3 --yes
# Deleted backup job #3.
sylve backup target delete 2 --yes
# Deleted backup target #2.
```

```json
{
  "method": "POST",
  "path": "/cluster/backups/targets/1/restore",
  "params": null,
  "body": {
    "remoteDataset": "tank/backups/vm-101",
    "snapshot": "zroot/vm/101@auto-2026-10-28",
    "destinationDataset": "zroot/vm/101-restored"
  }
}
```

## SEE ALSO

[sylve(1)](../../README.md),
[sylve-replication(1)](replication.md),
[sylve-zfs(1)](zfs.md),
[sylve-options(7)](../global-options.md)
