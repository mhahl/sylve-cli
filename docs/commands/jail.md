# sylve jail

Manage FreeBSD jails, snapshots, pkgbase bootstraps, and templates.

## Synopsis

    sylve jail COMMAND [ARGS]...

## Commands

| Command | Purpose |
|---|---|
| `list` | List jails across nodes |
| `show JAIL` | Full jail details |
| `start`, `stop`, `restart` | Power actions on one or more jails |
| `migrate JAIL` | Preflight and migrate to another node |
| `delete JAIL` | Delete a jail |
| `logs JAIL` | Console logs |
| `guest-info JAIL` | Live OS and network data |
| `rename JAIL NEW_NAME` | Rename a jail |
| `snapshot list/create/rollback/delete` | ZFS snapshots |
| `bootstrap list/create` | pkgbase bootstraps |
| `template list` | Jail templates |
| `create`, `description`, `hardware-cpu`, `hardware-ram`, `hardware-resource-limits` | Generic API commands |
| `network-inheritance`, `network-attach`, `network-detach`, `network-update` | Generic network commands |
| `options-additional`, `options-allowed`, `options-boot-order`, `options-devfs-rules`, `options-execution-timeout` | Generic jail options |
| `options-fstab`, `options-lifecycle-hooks`, `options-metadata`, `options-resolv-conf`, `options-wol` | Generic jail options |
| `root-mountpoint`, `state`, `stats` | Generic read commands |
| `template-show`, `template-delete`, `template-capture`, `template-deploy` | Generic template commands |
| `bootstrap-delete` | Generic bootstrap delete |

## Options

### `jail list`

- `-n, --node NODE`
  Limit to one node.
- `-f, --format {table,json,yaml,value,csv}`
  Output format. Default: `table`.
- `-c, --column NAME`
  Select columns.
- `--sort-column NAME`
  Sort rows.
- `--long`
  Add the `Limits` column.

### `jail show`

- `JAIL` (required)
  CTID or name.
- `-n, --node NODE`
  Target node.
- `-f, --format {table,json,yaml,value,csv}`
  Output format. Default: `table`.
- `-c, --column NAME`
  Select fields.

### `jail start`, `stop`, `restart`

- `JAILS...` (required)
  One or more CTIDs or names.
- `-n, --node NODE`
  Target node.
- `-w, --wait / --no-wait`
  Wait for the task. Default: `--no-wait`.

### `jail migrate`

- `JAIL` (required)
  CTID or name.
- `--target, -t NODE` (required)
  Destination hostname or UUID.
- `--validate-only`, `--dry-run`
  Run preflight only.
- `-n, --node NODE`
  Source node.
- `-w, --wait / --no-wait`
  Wait for migration. Default: `--wait`.

### `jail delete`

- `JAIL` (required)
  CTID or name.
- `--delete-rootfs / --keep-rootfs`
  Delete the root ZFS dataset. Default: `--delete-rootfs`.
- `--delete-macs / --keep-macs`
  Delete unused MAC objects. Default: `--delete-macs`.
- `-y, --yes`
  Skip confirmation.
- `-n, --node NODE`
  Target node.

### `jail logs`, `jail guest-info`, `jail rename`

- `JAIL` (required)
  CTID or name.
- `NEW_NAME`
  New name, for `rename` only.
- `-n, --node NODE`
  Target node.
- `-f, --format` and `-c, --column`
  `guest-info` only.

### `jail snapshot list`

- `JAIL` (required), `-n/--node`, `-f/--format`, `-c/--column`, `--long`.

### `jail snapshot create`

- `JAIL` (required), `--name, -m NAME` (required),
  `--description, -d TEXT` (default empty), `-n/--node`.

### `jail snapshot rollback`

- `JAIL` (required), `SNAPSHOT_ID` (required), `-y/--yes`, `-n/--node`.

### `jail snapshot delete`

- `JAIL` (required), `SNAPSHOT_ID` (required), `-n/--node`.

### `jail bootstrap list`

- `--pool, -p POOL` (required)
  ZFS pool to query.
- `-n/--node`, `-f/--format`, `-c/--column`.

### `jail bootstrap create`

- `--pool, -p POOL` (required)
  ZFS pool.
- `--major N` (required)
  FreeBSD major version.
- `--minor N`
  FreeBSD minor version. Default: `0`.
- `--type TYPE`
  Bootstrap type, for example `base` or `minimal`. Default: `base`.
- `-n/--node`
  Target node.

### `jail template list`

- `-n/--node`, `-f/--format`, `-c/--column`.

### Generic commands

All generic jail commands accept `--data/-d`, `--param/-p`, `-y/--yes`,
`-n/--node`, and `-f/--format`. Path arguments:

| Command | Arguments |
|---|---|
| `description`, `hardware-cpu`, `hardware-ram`, `hardware-resource-limits` | `ctid` |
| `network-inheritance`, `network-attach` | `ctid` |
| `network-detach`, `network-update` | `ctid networkId` |
| `options-*`, `root-mountpoint`, `state`, `stats`, `template-capture` | `ctid` |
| `template-show`, `template-delete`, `template-deploy` | `templateId` |
| `bootstrap-delete` | `name` |
| `create` | none |

## Examples

### Minimal

    sylve jail list

Output (illustrative):

    FreeBSD Jails
    +------+---------+---------+---------+---------------------+-------+--------+
    | CTID | Name    | State   | Type    | Node                | Cores | Memory |
    +------+---------+---------+---------+---------------------+-------+--------+
    | 201  | dns-01  | RUNNING | freebsd | node1.example.test  | 2     | 2.0 GiB|
    | 202  | cache   | STOPPED | freebsd | node2.example.test  | 1     | 1.0 GiB|
    +------+---------+---------+---------+---------------------+-------+--------+

### With every relevant option

    sylve jail snapshot create 201 --name pre-upgrade --description "before package update" --node node1.example.test

Output:

    Created snapshot 'pre-upgrade' for Jail 201.

    sylve jail snapshot list 201 --long --format json -c 'ID,Name,Snapshot,Root Dataset,Created At'

Output (illustrative):

    [
      {
        "id": 1,
        "name": "pre-upgrade",
        "snapshotName": "zroot/jail/201@pre-upgrade",
        "rootDataset": "zroot/jail/201",
        "createdAt": "2026-10-28T20:00:00Z"
      }
    ]

### Bootstrap

    sylve jail bootstrap create --pool zroot --major 14 --minor 2 --type base --node node1.example.test

Output:

    Queued jail bootstrap (14.2 base) on pool 'zroot'.

    sylve jail bootstrap list --pool zroot

Output (illustrative):

    Jail Bootstraps (Pool: zroot)
    +----------+------+---------+------+---------+---------------------+
    | Name     | Pool | Version | Type | Status  | Node                |
    +----------+------+---------+------+---------+---------------------+
    | 14.2-base| zroot| 14.2    | base | READY   | node1.example.test  |
    +----------+------+---------+------+---------+---------------------+

### Migrate and delete

    sylve jail migrate 201 --target node2.example.test --dry-run

    sylve jail migrate 201 --target node2.example.test --wait

    sylve jail delete 201 --keep-rootfs --keep-macs --yes

Output (illustrative):

    Jail 201 Migration Preflight -> node2.example.test
    ...
    Jail 201 successfully migrated from node1.example.test to node2.example.test.
    Deleted Jail 201 (node1.example.test).

### Generic command with every option

    sylve jail hardware-cpu 201 --data '{"cores":4}' --param dryRun=0 --node node1.example.test --format json

Output (illustrative):

    {
      "ctId": 201,
      "cores": 4
    }

    sylve jail template-deploy 3 --data '{"name":"dns-02","ctid":203}' -f json

Output (illustrative):

    {
      "taskId": 77
    }

## Inputs

- The active context and token.
- `--data` inline JSON/YAML or `@file`.
- Generic `create` uses the Sylve jail API request body. Required fields are
  defined by the API, not the CLI.

## Outputs

- Tables, JSON, YAML, value, or CSV.
- Mutating commands print a confirmation line, or the API result for generic
  commands.
- Exit `0` on success. Exit `1` on API error or aborted confirmation. Exit `2`
  on usage error.
