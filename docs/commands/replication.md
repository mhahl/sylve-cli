# sylve replication

Manage HA replication policies, manual runs, failovers, and replication events.

## Synopsis

    sylve replication COMMAND [ARGS]...

## Commands

| Command | Purpose |
|---|---|
| `policy list` | Policies and HA state |
| `policy show ID` | Full policy details |
| `policy create` | Create a policy |
| `policy run ID` | Queue an immediate replication run |
| `policy failover ID` | Queue a safe or forced failover |
| `policy delete ID` | Delete a policy |
| `policy update ID` | Generic update |
| `event list` | Recent events |
| `event show ID` | Event details or live progress |

## Options

### `policy list`

- `-f, --format {table,json,yaml,value,csv}`
  Output format. Default: `table`.
- `-c, --column NAME`
  Select columns.
- `--sort-column NAME`
  Sort rows.
- `--long`
  Add `Targets`, `Cron`, and `HA Eligible`.

### `policy show`

- `POLICY_ID` (required), `-f/--format`, `-c/--column`.

### `policy create`

- `--name NAME` (required)
  Policy name.
- `--guest-type TYPE` (required)
  `vm` or `jail`.
- `--guest-id ID` (required)
  VM RID or jail CTID.
- `--target, -t NODE[:WEIGHT]` (required)
  Target node hostname or UUID. Repeatable. Optional weight after `:`.
  Default weight: `100`.
- `--cron EXPR`
  Cron schedule. Default: `*/15 * * * *`.
- `--failover-mode MODE`
  `manual` or `auto`. Default: `manual`.
- `--enabled / --disabled`
  Enable the policy. Default: `--enabled`.

### `policy run`

- `POLICY_ID` (required).

### `policy failover`

- `POLICY_ID` (required).
- `--target, -t NODE`
  Target node. Default: auto-selected.
- `--mode MODE`
  `safe` or `force`. Default: `safe`.
- `--move-pinned-source / --keep-pinned-source`
  Update the pinned source node. Default: `--move-pinned-source`.
- `--confirm-data-loss`
  Acknowledge possible data loss for forced failover.

### `policy delete`

- `POLICY_ID` (required), `-y/--yes`.

### `policy update`

- `POLICY_ID` (required).
- `-d, --data BODY`, `-p, --param KEY=VALUE`, `-y/--yes`,
  `-n, --node NODE`, `-f, --format`.

### `event list`

- `--policy-id ID`
  Filter by policy.
- `--limit, -l N`
  Maximum events. Default: `50`.
- `-f/--format`, `-c/--column`, `--long`.

### `event show`

- `EVENT_ID` (required).
- `-w, --wait / --no-wait`
  Follow live progress. Default: `--no-wait`.
- `-f/--format`, `-c/--column`.

## Examples

### Minimal

    sylve replication policy list

Output (illustrative):

    Replication Policies
    +----+---------+------------+----------+---------------------+-------------+---------+
    | ID | Name    | Guest Type | Guest ID | Active Node         | Last Status | Enabled |
    +----+---------+------------+----------+---------------------+-------------+---------+
    | 1  | web-ha  | vm         | 101      | node1.example.test  | SUCCESS     | true    |
    +----+---------+------------+----------+---------------------+-------------+---------+

### With every relevant option

    sylve replication policy create \
      --name web-ha \
      --guest-type vm \
      --guest-id 101 \
      --target node2.example.test:150 \
      --target node3.example.test:100 \
      --cron '*/10 * * * *' \
      --failover-mode auto \
      --enabled

Output:

    Created replication policy 'web-ha' for vm 101.

`node2:150` set a weight of 150; `node3` used the default weight of 100.
`--failover-mode auto` allows automatic failover.

### Run and fail over with every option

    sylve replication policy run 1

Output:

    Queued immediate run for replication policy #1.

    sylve replication policy failover 1 \
      --target node2.example.test \
      --mode force \
      --keep-pinned-source \
      --confirm-data-loss

Output:

    Queued force failover for replication policy #1.

`--keep-pinned-source` left the pinned source unchanged. `--confirm-data-loss`
is required to acknowledge a forced failover.

### Events

    sylve replication event list --policy-id 1 --limit 10 --long

Output (illustrative):

    Replication Events
    +----+-----------+------------+-------+---------+---------------------+---------------------+---------+
    | ID | Policy ID | Event Type | Guest | Guest ID| Source Node         | Target Node         | Status  |
    +----+-----------+------------+-------+---------+---------------------+---------------------+---------+
    | 9  | 1         | failover   | vm    | 101     | node1.example.test  | node2.example.test  | SUCCESS |
    +----+-----------+------------+-------+---------+---------------------+---------------------+---------+

    sylve replication event show 9 --wait

Output (illustrative):

    Replication Event #9
    +-------+---------------------+
    | Field | Value               |
    +-------+---------------------+
    | id    | 9                   |
    | status| SUCCESS             |
    +-------+---------------------+

### Generic update

    sylve replication policy update 1 --data '{"enabled":false}' --param dryRun=0 --node node1.example.test -f json

Output (illustrative):

    {
      "id": 1,
      "enabled": false
    }

    sylve replication policy delete 1 --yes

Output:

    Deleted replication policy #1.

## Inputs

- The active context and token.
- `--target` accepts a node hostname or UUID; `policy create` also accepts
  `NODE:WEIGHT`.
- Generic update accepts `--data` inline JSON/YAML or `@file`, plus `--param`.

## Outputs

- Policy and event tables.
- Mutating commands print a confirmation line or the API result.
- Exit `0` on success. Exit `1` on API error or aborted confirmation. Exit `2`
  on usage error.
