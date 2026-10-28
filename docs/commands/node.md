# sylve node

List cluster nodes, read telemetry, drain a node, reboot, remove peers, and read
audit logs.

## Synopsis

    sylve node COMMAND [ARGS]...

## Commands

| Command | Purpose |
|---|---|
| `list` | Nodes with CPU, RAM, disk, guests, version |
| `show [NODE]` | Detailed system and telemetry |
| `drain NODE` | Migrate or stop all workloads before maintenance |
| `reboot [NODE]` | Reboot a node |
| `remove NODE` | Remove a peer from the cluster |
| `audit-logs` | Audit records, optionally from one node |
| `cpu-history`, `ram-history`, `swap-history`, `network-history`, `summary-history`, `summary-delta` | Generic history API commands |

## Options

### `node list`

- `-f, --format {table,json,yaml,value,csv}`
  Output format. Default: `table`.
- `-c, --column NAME`
  Select columns.
- `--sort-column NAME`
  Sort rows.
- `--long`
  Add `Node UUID`, `API`, `Cores`, `Memory`, and `Disk`.

### `node show`

- `NODE`
  Hostname or UUID. Defaults to the connected node.
- `-f, --format {table,json,yaml,value,csv}`
  Output format. Default: `table`.
- `-c, --column NAME`
  Select fields.

### `node drain`

- `NODE` (required)
  Hostname or UUID to drain.
- `--target-node, -t NODE`
  Destination node. Default: least-loaded online node.
- `--stop-only`
  Shut down VMs and jails instead of migrating them.
- `--fallback-stop`
  Stop guests that cannot be migrated instead of blocking.
- `--running-only`
  Leave stopped guests on the node.
- `--dry-run`
  Validate migrations and print the plan, changing nothing.
- `--ignore-errors`
  Continue after failed preflight or execution.
- `-w, --wait / --no-wait`
  Wait for tasks. Default: `--wait`.
- `-y, --yes`
  Skip confirmation.
- `-f, --format {table,json,yaml,value,csv}`
  Output format. Default: `table`.
- `-c, --column NAME`
  Select plan columns: `guest_type`, `guest_id`, `name`, `current_state`,
  `action`, `source_node`, `target_node`, `reason`, `result`.

### `node reboot`

- `NODE`
  Hostname or UUID. Defaults to the connected node.
- `-y, --yes`
  Skip confirmation.

### `node remove`

- `NODE` (required)
  Hostname or UUID to remove.
- `--retain-guests / --no-retain-guests`
  Keep VM and jail registrations. Default: `--retain-guests`.
- `--force`
  Force removal of an offline, externally fenced peer.
- `-y, --yes`
  Skip confirmation.

### `node audit-logs`

- `-n, --node NODE`
  Target node. Omit for all nodes.
- `-f, --format {table,json,yaml,value,csv}`
  Output format. Default: `table`.
- `-c, --column NAME`
  Select columns.

### Generic history commands

`cpu-history`, `ram-history`, `swap-history`, `network-history`,
`summary-history`, and `summary-delta` accept `--data/-d`, `--param/-p`,
`-y/--yes`, `-n/--node`, and `-f/--format`.

## Examples

### Minimal

    sylve node list

Output (illustrative):

    Cluster Nodes
    +---------------------+--------+------+------+------+--------+---------+
    | Hostname            | Status | CPU% | RAM% | Disk%| Guests | Version |
    +---------------------+--------+------+------+------+--------+---------+
    | node1.example.test  | ONLINE |  8.2%| 31.4%| 44.0%|     5  | 0.3.1   |
    | node2.example.test  | ONLINE | 12.7%| 48.1%| 52.3%|     7  | 0.3.1   |
    +---------------------+--------+------+------+------+--------+---------+

### With every relevant option

    sylve node drain node1.example.test \
      --target-node node2.example.test \
      --fallback-stop \
      --running-only \
      --ignore-errors \
      --no-wait \
      --yes \
      --format json \
      --column Type,ID,Name,State,Action,Target,Result

Output (illustrative):

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

`--running-only` left stopped guests in place. `--fallback-stop` allowed
non-migratable guests to be stopped. `--no-wait` returned after queueing.
`--ignore-errors` kept the drain going after failures.

### Dry run

    sylve node drain node1.example.test --dry-run --stop-only

Output (illustrative):

    Drain Plan (DRY RUN) for node1.example.test
    +-------+-----+---------+---------+----------+---------------------+--------+------------------+---------+
    | Type  | ID  | Name    | State   | Action   | Source              | Target | Preflight/Reason | Result  |
    +-------+-----+---------+---------+----------+---------------------+--------+------------------+---------+
    | vm    | 101 | web-01  | RUNNING | shutdown | node1.example.test  | -      | stop-only...     | pending |
    +-------+-----+---------+---------+----------+---------------------+--------+------------------+---------+

### Show, reboot, remove

    sylve node show node1.example.test -f json

Output (illustrative):

    {
      "hostname": "node1.example.test",
      "sylveVersion": "0.3.1",
      "cpuUsage": 8.2,
      "memoryUsage": 31.4,
      "diskUsage": 44.0
    }

    sylve node reboot node1.example.test --yes

Output:

    Reboot initiated for node 'node1.example.test'.

    sylve node remove node3.example.test --no-retain-guests --yes

Output (illustrative):

    Removed node 'node3.example.test' (3c4d...) from the cluster.

### Audit logs with every option

    sylve node audit-logs --node node1.example.test -f json -c User,Action,Path,Status

Output (illustrative):

    [
      {
        "username": "admin",
        "action": "vm.start",
        "path": "/vm/101/actions/start",
        "status": "success"
      }
    ]

### History command

    sylve node cpu-history --param hours=24 -f json

Output (illustrative):

    [
      {
        "timestamp": "2026-10-28T20:00:00Z",
        "usage": 8.2
      }
    ]

## Inputs

- The active context and token.
- `NODE` arguments, or `-n/--node`.
- Generic commands accept `--data` inline JSON/YAML or `@file`, plus repeatable
  `--param KEY=VALUE`.

## Outputs

- Tables, JSON, YAML, value, or CSV.
- `drain` prints the plan, the summary, and a success or failure line. A
  blocked plan exits `1` until resolved.
- Exit `0` on success. Exit `1` on API failure or aborted confirmation. Exit
  `2` on usage error.
