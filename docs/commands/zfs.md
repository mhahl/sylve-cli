# sylve zfs

Manage ZFS pools, datasets, snapshots, periodic snapshot jobs, and dashboard
data.

## Synopsis

    sylve zfs COMMAND [ARGS]...

## Commands

| Group | Commands |
|---|---|
| `pool` | `list`, `show`, `status`, `scrub`, `create`, `delete`, `edit`, `detach`, `replace-device`, `disks-usage` |
| `dataset` | `list`, `create-fs`, `create-vol`, `delete`, `edit`, `bulk-delete`, `paginated`, `volume-edit`, `volume-flash` |
| `snapshot` | `list`, `create`, `rollback`, `delete` |
| `periodic` | `list`, `create`, `update`, `delete` |
| top level | `dashboard-snapshot`, `dashboard-history`, `dashboard-delta` |

## Options

### `pool list`

- `--all, -a`
  Include pools not marked usable in Sylve settings.
- `-n, --node NODE`, `-f, --format`, `-c, --column`,
  `--sort-column`, `--long`.

### `pool show` / `pool status`

- `POOL` (required)
  Pool name or GUID.
- `-n/--node`, `-f/--format`, `-c/--column`.

### `pool scrub`

- `POOL` (required), `-n/--node`.

### `dataset list`

- `--type, -t TYPE`
  `FILESYSTEM`, `VOLUME`, `SNAPSHOT`, or `ALL`.
- `-n/--node`, `-f/--format`, `-c/--column`, `--sort-column`, `--long`.

### `dataset create-fs`

- `--parent, -p PATH` (required)
  Parent dataset, for example `zroot`.
- `--name NAME` (required)
  New filesystem name.
- `-n/--node`.

### `dataset create-vol`

- `--parent, -p PATH` (required)
  Parent dataset.
- `--name NAME` (required)
  New volume name.
- `--size, -s SIZE` (required)
  Volume size, for example `10G`.
- `-n/--node`.

### `dataset delete`

- `DATASET` (required)
  Name or GUID.
- `--type, -t TYPE`
  `filesystem` or `volume`. Default: `filesystem`.
- `-y/--yes`, `-n/--node`.

### `snapshot list`

- `-n/--node`, `-f/--format`, `-c/--column`, `--sort-column`.

### `snapshot create`

- `DATASET` (required)
  Name or GUID.
- `--name, -m NAME` (required)
  Snapshot name after `@`.
- `-r, --recursive / --no-recursive`
  Create recursively. Default: off.
- `-n/--node`.

### `snapshot rollback`

- `SNAPSHOT` (required)
  `dataset@snap` or GUID.
- `--destroy-more-recent`
  Destroy newer snapshots.
- `-y/--yes`, `-n/--node`.

### `snapshot delete`

- `SNAPSHOT` (required)
  `dataset@snap` or GUID.
- `-r, --recursive / --no-recursive`
  Delete child snapshots. Default: off.
- `-n/--node`.

### `periodic list`

- `-n/--node`, `-f/--format`, `-c/--column`, `--long`.

### Generic commands

All remaining commands accept `--data/-d`, `--param/-p`, `-y/--yes`,
`-n/--node`, and `-f/--format`. Path arguments:

| Command | Arguments |
|---|---|
| `pool delete`, `edit`, `detach`, `replace-device` | `guid` |
| `dataset edit`, `volume-edit`, `volume-flash` | `guid` |
| `periodic update`, `delete` | `id` |
| `pool create`, `disks-usage`, `dataset bulk-delete`, `paginated`, `periodic create`, `dashboard-*` | none |

## Examples

### Minimal

    sylve zfs pool list

Output (illustrative):

    ZFS Storage Pools
    +-------+---------------------+-------+---------+---------+-------+
    | Name  | Node                | State | Size    | Free    | Frag% |
    +-------+---------------------+-------+---------+---------+-------+
    | zroot | node1.example.test  | ONLINE| 1.8 TiB | 1.2 TiB |   8.0%|
    +-------+---------------------+-------+---------+---------+-------+

### With every relevant option

    sylve zfs pool list --all --long --sort-column name --format json -c Name,GUID,State,Size,Free

Output (illustrative):

    [
      {
        "name": "zroot",
        "pool_guid": "1234567890",
        "state": "ONLINE",
        "size": 1979120929996,
        "free": 1319413953331
      }
    ]

`--all` included pools not marked usable in Sylve settings. `--long` added
`GUID`, `Allocated`, and `Dedup`.

### Pool status and scrub

    sylve zfs pool status zroot

Output (illustrative):

    ZFS Pool Status: zroot (node1.example.test)
    +-------+---------+
    | Field | Value   |
    +-------+---------+
    | state | ONLINE  |
    | scan  | none    |
    +-------+---------+

    sylve zfs pool scrub zroot --node node1.example.test

Output:

    Started scrub on ZFS pool 'zroot' (node1.example.test).

### Datasets

    sylve zfs dataset list --type VOLUME --long

Output (illustrative):

    ZFS Datasets
    +----------------+------+---------+-------+---------+---------+-----------+------------+
    | Name           | GUID | Node    | Pool  | Type    | Used    | Avail     | Mountpoint |
    +----------------+------+---------+-------+---------+---------+-----------+------------+
    | zroot/vm/101   | 42   | node1   | zroot | volume  | 20.0 GiB| 1.2 TiB   | -          |
    +----------------+------+---------+-------+---------+---------+-----------+------------+

    sylve zfs dataset create-fs --parent zroot --name backups --node node1.example.test

Output:

    Created ZFS filesystem 'zroot/backups'.

    sylve zfs dataset create-vol --parent zroot --name data --size 50G --node node1.example.test

Output:

    Created ZFS volume 'zroot/data' (50G).

    sylve zfs dataset delete zroot/backups --type filesystem --yes

Output:

    Deleted ZFS filesystem 'zroot/backups'.

### Snapshots with every option

    sylve zfs snapshot create zroot/data --name pre-upgrade --recursive --node node1.example.test

Output:

    Created ZFS snapshot 'zroot/data@pre-upgrade'.

    sylve zfs snapshot list --node node1.example.test --sort-column name

    sylve zfs snapshot rollback zroot/data@pre-upgrade --destroy-more-recent --yes

Output:

    Rolled back to snapshot 'zroot/data@pre-upgrade'.

    sylve zfs snapshot delete zroot/data@pre-upgrade --recursive

Output:

    Deleted ZFS snapshot 'zroot/data@pre-upgrade'.

### Periodic snapshots

    sylve zfs periodic list --long

Output (illustrative):

    Periodic ZFS Snapshot Jobs
    +----+---------------------+-------+-------------+-----------+---------+-----------+
    | ID | Node                | Pool  | Prefix      | Cron      | Recursive| Keep Last |
    +----+---------------------+-------+-------------+-----------+---------+-----------+
    | 2  | node1.example.test  | zroot | auto        | 0 * * * * | true    | 24        |
    +----+---------------------+-------+-------------+-----------+---------+-----------+

### Generic command with every option

    sylve zfs periodic create --param validate=1 --node node1.example.test \
      --data '{"pool":"zroot","prefix":"auto","cronExpr":"0 * * * *","keepLast":24,"recursive":true}' \
      -f json

Output (illustrative):

    {
      "id": 3,
      "prefix": "auto"
    }

    sylve zfs pool delete 1234567890 --yes

Output (illustrative):

    OK

## Inputs

- The active context and token.
- Pool, dataset, and snapshot names or GUIDs.
- Generic commands accept `--data` inline JSON/YAML or `@file`, plus
  `--param KEY=VALUE`.

## Outputs

- Pool, dataset, snapshot, and periodic-job tables.
- Mutating commands print a confirmation line or the API result.
- Exit `0` on success. Exit `1` on API error or aborted confirmation. Exit `2`
  on usage error.
