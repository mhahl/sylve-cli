# SYLVE-NODE(1)

## NAME

`sylve-node` — list cluster nodes, inspect telemetry, drain workloads, reboot, remove peers, and read audit logs

## SYNOPSIS

```sh
sylve node COMMAND [ARGS ...]
```

## DESCRIPTION

`sylve node` inspects and manages individual Sylve cluster nodes. It provides
resource summaries, telemetry history, workload draining prior to maintenance,
host reboots, peer removal, and audit log queries.

`node drain` computes a migration/shutdown plan for all guests on the target
node, validates preflight checks, and executes or previews the plan. A blocked
drain plan exits with status `1` unless `--ignore-errors` or `--fallback-stop`
resolves the block.

## SUBCOMMANDS

| Subcommand | Description |
|---|---|
| `list` | List nodes with CPU, RAM, disk, guest count, and version |
| `show [NODE]` | Show detailed system information and telemetry |
| `drain NODE` | Migrate or stop all workloads on `NODE` before maintenance |
| `reboot [NODE]` | Reboot a node |
| `remove NODE` | Remove a peer node from the cluster |
| `audit-logs` | Read audit log records across the cluster or from one node |
| `cpu-history`, `ram-history`, `swap-history`, `network-history`, `summary-history`, `summary-delta` | Generic telemetry history API commands |

## OPTIONS

### `node list`

- `-f, --format {table,json,yaml,value,csv}`
  Output format (default: `table`).
- `-c, --column NAME`
  Select columns.
- `--sort-column NAME`
  Sort rows.
- `--long`
  Add `Node UUID`, `API`, `Cores`, `Memory`, and `Disk`.

### `node show`

- `NODE`
  Hostname or UUID (default: connected node).
- `-f, --format {table,json,yaml,value,csv}`
  Output format (default: `table`).
- `-c, --column NAME`
  Select fields.

### `node drain`

- `NODE` (required)
  Hostname or UUID to drain.
- `--target-node, -t NODE`
  Destination node for migrations (default: least-loaded online node).
- `--stop-only`
  Shut down VMs and jails instead of migrating them.
- `--fallback-stop`
  Stop guests that fail migration preflight instead of blocking the plan.
- `--running-only`
  Leave stopped guests on the source node.
- `--dry-run`
  Validate migrations and print the drain plan without making changes.
- `--ignore-errors`
  Continue draining after failed preflight or task execution.
- `-w, --wait / --no-wait`
  Wait for drain tasks to complete (default: `--wait`).
- `-y, --yes`
  Skip confirmation prompt.
- `-f, --format {table,json,yaml,value,csv}`
  Output format (default: `table`).
- `-c, --column NAME`
  Select plan columns: `guest_type`, `guest_id`, `name`, `current_state`,
  `action`, `source_node`, `target_node`, `reason`, `result`.

### `node reboot`

- `NODE`
  Hostname or UUID (default: connected node).
- `-y, --yes`
  Skip confirmation prompt.

### `node remove`

- `NODE` (required)
  Hostname or UUID to remove.
- `--retain-guests / --no-retain-guests`
  Keep VM and jail registrations (default: `--retain-guests`).
- `--force`
  Force removal of an offline, externally fenced peer.
- `-y, --yes`
  Skip confirmation prompt.

### `node audit-logs`

- `-n, --node NODE`
  Target node (omit to query all nodes).
- `-f, --format {table,json,yaml,value,csv}`
  Output format (default: `table`).
- `-c, --column NAME`
  Select columns.

### Generic History Subcommands

`cpu-history`, `ram-history`, `swap-history`, `network-history`,
`summary-history`, and `summary-delta` accept `--data/-d`, `--param/-p`,
`-y/--yes`, `-n/--node`, and `-f/--format`.

## EXIT STATUS

- `0` — Success.
- `1` — API failure, blocked drain plan, or aborted confirmation.
- `2` — Command-line usage error.

## EXAMPLES

List cluster nodes:

```sh
sylve node list
```

```text
Cluster Nodes
+---------------------+--------+------+------+------+--------+---------+
| Hostname            | Status | CPU% | RAM% | Disk%| Guests | Version |
+---------------------+--------+------+------+------+--------+---------+
| node1.example.test  | ONLINE |  8.2%| 31.4%| 44.0%|     5  | 0.3.1   |
| node2.example.test  | ONLINE | 12.7%| 48.1%| 52.3%|     7  | 0.3.1   |
+---------------------+--------+------+------+------+--------+---------+
```

Preview a stop-only drain plan without executing it:

```sh
sylve node drain node1.example.test --dry-run --stop-only
```

```text
Drain Plan (DRY RUN) for node1.example.test
+-------+-----+---------+---------+----------+---------------------+--------+------------------+---------+
| Type  | ID  | Name    | State   | Action   | Source              | Target | Preflight/Reason | Result  |
+-------+-----+---------+---------+----------+---------------------+--------+------------------+---------+
| vm    | 101 | web-01  | RUNNING | shutdown | node1.example.test  | -      | stop-only...     | pending |
+-------+-----+---------+---------+----------+---------------------+--------+------------------+---------+
```

Drain running guests to `node2.example.test` with fallback shutdown and JSON
output:

```sh
sylve node drain node1.example.test \
  --target-node node2.example.test \
  --fallback-stop \
  --running-only \
  --ignore-errors \
  --no-wait \
  --yes \
  --format json \
  --column Type,ID,Name,State,Action,Target,Result
```

```json
[
  {
    "guest_type": "vm",
    "guest_id": 101,
    "name": "web-01",
    "current_state": "RUNNING",
    "action": "migrate",
    "source_node": "node1.example.test",
    "target_node": "node2.example.test",
    "reason": "preflight ok",
    "result": "queued (task #42)"
  }
]
```

Show node telemetry, reboot a node, and remove a decommissioned peer:

```sh
sylve node show node1.example.test -f json
sylve node reboot node1.example.test --yes
sylve node remove node3.example.test --no-retain-guests --yes
```

Query audit logs and CPU history:

```sh
sylve node audit-logs --node node1.example.test -f json -c User,Action,Path,Status
sylve node cpu-history --param hours=24 -f json
```

## SEE ALSO

[sylve(1)](../../README.md),
[sylve-cluster(1)](cluster.md),
[sylve-vm(1)](vm.md),
[sylve-jail(1)](jail.md),
[sylve-task(1)](task.md),
[sylve-options(7)](../global-options.md)
