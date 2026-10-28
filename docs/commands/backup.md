# sylve backup

Manage backup targets, scheduled jobs, restores, and events.

## Synopsis

    sylve backup COMMAND [ARGS]...

## Commands

| Command | Purpose |
|---|---|
| `target list` | List targets |
| `target show ID` | Target details and readiness |
| `target datasets ID` | Restorable datasets |
| `target validate ID` | Validate connectivity |
| `target delete ID` | Delete a disabled target |
| `target create`, `target update`, `target running-jobs`, `target dataset-snapshots`, `target vm-metadata`, `target jail-metadata`, `target restore` | Generic API commands |
| `job list` | Scheduled jobs |
| `job run ID` | Queue an immediate run |
| `job snapshots ID` | Restorable snapshots |
| `job restore ID` | Queue a restore |
| `job delete ID` | Delete a job |
| `job create`, `job update` | Generic API commands |
| `event list` | Recent events |
| `event show ID` | Event details or live progress |
| `event remote-list` | Generic remote event list |

## Options

### `target list`

- `-f, --format {table,json,yaml,value,csv}`
  Output format. Default: `table`.
- `-c, --column NAME`
  Select columns.
- `--sort-column NAME`
  Sort rows.
- `--long`
  Add `Port`, `Backup Root`, and `Description`.

### `target show`

- `TARGET_ID` (required), `-f/--format`, `-c/--column`.

### `target datasets`

- `TARGET_ID` (required), `-f/--format`, `-c/--column`, `--long`.

### `target validate`

- `TARGET_ID` (required).

### `target delete`

- `TARGET_ID` (required), `-y/--yes`.

### `job list`

- `--target-id ID`
  Filter by target.
- `--guest-type TYPE`
  `vm` or `jail`.
- `--guest-id ID`
  Filter by guest.
- `-f/--format`, `-c/--column`, `--sort-column`, `--long`.

### `job run`

- `JOB_ID` (required).

### `job snapshots`

- `JOB_ID` (required).
- `--limit, -l N`
  Maximum snapshots. Default: `100`.
- `-f/--format`, `-c/--column`, `--long`.

### `job restore`

- `JOB_ID` (required).
- `--snapshot, -s NAME` (required)
  Snapshot to restore.
- `--encryption-key KEY`
  Decryption key for encrypted backups.

### `job delete`

- `JOB_ID` (required), `-y/--yes`.

### `event list`

- `--job-id ID`
  Filter by job.
- `--limit, -l N`
  Maximum events. Default: `50`.
- `-f/--format`, `-c/--column`, `--long`.

### `event show`

- `EVENT_ID` (required).
- `-w, --wait / --no-wait`
  Follow live progress. Default: `--no-wait`.
- `-f/--format`, `-c/--column`.

### Generic commands

All generic backup commands accept `--data/-d`, `--param/-p`, `-y/--yes`,
`-n/--node`, and `-f/--format`. Path arguments:

| Command | Arguments |
|---|---|
| `target update`, `target running-jobs`, `target dataset-snapshots`, `target vm-metadata`, `target jail-metadata`, `target restore` | `id` |
| `job update` | `id` |
| `target create`, `job create`, `event remote-list` | none |

## Examples

### Minimal

    sylve backup target list

Output (illustrative):

    Backup Targets
    +----+---------+---------------------+---------+
    | ID | Name    | SSH Host            | Enabled |
    +----+---------+---------------------+---------+
    | 1  | offsite | backup.example.test | true    |
    +----+---------+---------------------+---------+

### Target details and datasets

    sylve backup target show 1 --long --format json -c 'Name,SSH Host,Port,Backup Root,Enabled'

Output (illustrative):

    {
      "name": "offsite",
      "sshHost": "backup.example.test",
      "sshPort": 22,
      "backupRoot": "/backups/sylve",
      "enabled": true
    }

    sylve backup target datasets 1 --long

Output (illustrative):

    Backup Target #1 Datasets
    +-------------------------+------+-----------+-----------+-------------+---------+
    | Dataset                 | Kind | Lineage   | VM RID    | Jail CTID   | Snapshots|
    +-------------------------+------+-----------+-----------+-------------+---------+
    | zroot/vm/101            | vm   | zroot/vm  | 101       | -           | 4       |
    +-------------------------+------+-----------+-----------+-------------+---------+

### Validate and delete

    sylve backup target validate 1

Output:

    Backup target #1 validated successfully.

    sylve backup target delete 1 --yes

Output:

    Deleted backup target #1.

### With every relevant option

    sylve backup job list --target-id 1 --guest-type vm --guest-id 101 --long --sort-column name

Output (illustrative):

    Backup Jobs
    +----+---------+------+-----------+-----------+---------------+-------------+---------+
    | ID | Name    | Mode | Source    | Target ID | Runner Node   | Cron        | Enabled |
    +----+---------+------+-----------+-----------+---------------+-------------+---------+
    | 3  | web-bak | full | vm 101    | 1         | node1.example | 0 2 * * *   | true    |
    +----+---------+------+-----------+-----------+---------------+-------------+---------+

    sylve backup job run 3

Output:

    Queued immediate run for backup job #3.

    sylve backup job snapshots 3 --limit 5 --long

    sylve backup job restore 3 --snapshot zroot/vm/101@auto-2026-10-28 --encryption-key 'secret'

Output:

    Queued restore of snapshot 'zroot/vm/101@auto-2026-10-28' from backup job #3.

    sylve backup job delete 3 --yes

Output:

    Deleted backup job #3.

### Events

    sylve backup event list --job-id 3 --limit 10 --long

Output (illustrative):

    Backup Events
    +----+--------+------+---------------------+---------+---------+
    | ID | Job ID | Mode | Source Dataset      | Status  | Started |
    +----+--------+------+---------------------+---------+---------+
    | 7  | 3      | full | zroot/vm/101        | SUCCESS | 2026... |
    +----+--------+------+---------------------+---------+---------+

    sylve backup event show 7 --wait

Output (illustrative):

    Backup Event #7
    +-------+---------+
    | Field | Value   |
    +-------+---------+
    | id    | 7       |
    | status| SUCCESS |
    +-------+---------+

### Generic create with every option

    sylve backup target create --data @target.yaml --param validate=1 --node node1.example.test -f json

Output (illustrative):

    {
      "id": 2,
      "name": "secondary"
    }

`target.yaml` is the API request body:

```yaml
name: secondary
sshHost: backup2.example.test
sshPort: 22
backupRoot: /backups/sylve
enabled: true
```

## Inputs

- The active context and token.
- IDs from list commands.
- `--data` inline JSON/YAML or `@file`; `--param KEY=VALUE` repeated.

## Outputs

- Target, dataset, job, snapshot, and event tables.
- Mutating commands print a confirmation line or the API result.
- Exit `0` on success. Exit `1` on API error or aborted confirmation. Exit `2`
  on usage error.
