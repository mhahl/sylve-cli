# SYLVE-REPLICATION(1)

## NAME

`sylve-replication` — manage HA replication policies, manual runs, failovers, and events

## SYNOPSIS

```sh
sylve replication GROUP COMMAND [ARGS ...]
```

## DESCRIPTION

`sylve replication` manages high-availability (HA) ZFS replication policies for
VMs and jails across cluster nodes, triggers manual replication runs or safe/forced
failovers, and monitors replication events.

## SUBCOMMANDS

| Subcommand | Description |
|---|---|
| `policy list` | List replication policies and HA state |
| `policy show POLICY_ID` | Show full details for a policy |
| `policy create` | Create a replication policy |
| `policy run POLICY_ID` | Queue an immediate replication run |
| `policy failover POLICY_ID` | Queue a safe or forced failover |
| `policy delete POLICY_ID` | Delete a replication policy |
| `policy update POLICY_ID` | Update a policy (generic API command) |
| `event list` | List recent replication events |
| `event show EVENT_ID` | Show event details or follow live progress |

## OPTIONS

### `policy list` and `policy show`

- `list`: `-f, --format`, `-c, --column`, `--sort-column NAME`, `--long`
  (adds `Targets`, `Cron`, and `HA Eligible`).
- `show POLICY_ID`: `-f, --format`, `-c, --column`.

### `policy create`

- `--name NAME` (required)
  Policy name.
- `--guest-type {vm,jail}` (required)
  Guest type.
- `--guest-id ID` (required)
  VM RID or jail CTID.
- `--target, -t NODE[:WEIGHT]` (required, repeatable)
  Target node hostname or UUID, with an optional integer weight (default:
  `100`).
- `--cron EXPR`
  Cron schedule (default: `*/15 * * * *`).
- `--failover-mode {manual,auto}`
  Failover mode (default: `manual`).
- `--enabled / --disabled`
  Enable or disable the policy on creation (default: `--enabled`).

### `policy run`, `policy failover`, `policy delete`, `policy update`

- `run POLICY_ID`: queue an immediate run.
- `failover POLICY_ID`:
  - `--target, -t NODE`: destination node (default: auto-selected).
  - `--mode {safe,force}`: failover mode (default: `safe`).
  - `--move-pinned-source / --keep-pinned-source`: update the pinned source
    node (default: `--move-pinned-source`).
  - `--confirm-data-loss`: required acknowledgement when `--mode force` is set.
- `delete POLICY_ID`: `-y, --yes`.
- `update POLICY_ID`: `-d, --data BODY`, `-p, --param KEY=VALUE`, `-y, --yes`,
  `-n, --node NODE`, `-f, --format`.

### `event list` and `event show`

- `list`: `--policy-id ID`, `--limit, -l N` (default: `50`), `-f/--format`,
  `-c/--column`, `--long`.
- `show EVENT_ID`: `-w, --wait / --no-wait` (follow live progress; default:
  `--no-wait`), `-f/--format`, `-c/--column`.

## EXIT STATUS

- `0` — Success.
- `1` — API error, failed event while waiting, or aborted confirmation.
- `2` — Command-line usage error.

## EXAMPLES

List replication policies:

```sh
sylve replication policy list
```

```text
Replication Policies
+----+---------+------------+----------+---------------------+-------------+---------+
| ID | Name    | Guest Type | Guest ID | Active Node         | Last Status | Enabled |
+----+---------+------------+----------+---------------------+-------------+---------+
| 1  | web-ha  | vm         | 101      | node1.example.test  | SUCCESS     | true    |
+----+---------+------------+----------+---------------------+-------------+---------+
```

Create a weighted multi-target automatic failover policy:

```sh
sylve replication policy create \
  --name web-ha \
  --guest-type vm \
  --guest-id 101 \
  --target node2.example.test:150 \
  --target node3.example.test:100 \
  --cron '*/10 * * * *' \
  --failover-mode auto \
  --enabled
# Created replication policy 'web-ha' for vm 101.
```

Trigger an immediate run or a forced failover:

```sh
sylve replication policy run 1
sylve replication policy failover 1 \
  --target node2.example.test \
  --mode force \
  --keep-pinned-source \
  --confirm-data-loss
```

Inspect and follow replication events:

```sh
sylve replication event list --policy-id 1 --limit 10 --long
sylve replication event show 9 --wait
```

Disable or delete a policy:

```sh
sylve replication policy update 1 --data '{"enabled":false}' -f json
sylve replication policy delete 1 --yes
```

## SEE ALSO

[sylve(1)](../../README.md),
[sylve-backup(1)](backup.md),
[sylve-zfs(1)](zfs.md),
[sylve-vm(1)](vm.md),
[sylve-jail(1)](jail.md),
[sylve-options(7)](../global-options.md)
