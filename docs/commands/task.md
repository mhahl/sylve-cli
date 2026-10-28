# sylve task

Inspect, wait for, or cancel guest lifecycle and migration tasks.

## Synopsis

    sylve task COMMAND [ARGS]...

## Commands

| Command | Purpose |
|---|---|
| `list` | Active or recent lifecycle tasks |
| `show ID` | Full task details |
| `wait ID` | Wait for completion |
| `cancel-migration ID` | Request migration cancellation |
| `active` | Generic active task for one guest |

## Options

### `task list`

- `--active / --recent`
  Show active queued/running tasks or recent tasks. Default: `--recent`.
- `--guest-type TYPE`
  `vm` or `jail`.
- `--guest-id ID`
  VM RID or jail CTID.
- `--limit, -l N`
  Maximum recent tasks per node. Default: `25`. Ignored with `--active`.
- `-n, --node NODE`, `-f, --format`, `-c, --column`,
  `--sort-column`, `--long`.

### `task show`

- `TASK_ID` (required), `-n/--node`, `-f/--format`, `-c/--column`.

### `task wait`

- `TASK_ID` (required).
- `--timeout SECONDS`
  Timeout. Default: `600.0`.
- `-n/--node`, `-f/--format`.

### `task cancel-migration`

- `TASK_ID` (required), `-n/--node`.

### `task active`

- `GUEST_TYPE GUEST_ID` (required).
- Generic options: `--data/-d`, `--param/-p`, `-y/--yes`, `-n/--node`,
  `-f/--format`.

## Examples

### Minimal

    sylve task list

Output (illustrative):

    Recent Lifecycle Tasks
    +----+---------------------+------------+----------+---------+---------+---------------------+
    | ID | Node                | Guest Type | Guest ID | Action  | Status  | Created At          |
    +----+---------------------+------------+----------+---------+---------+---------------------+
    | 42 | node1.example.test  | vm         | 101      | start   | SUCCESS | 2026-10-28T20:00:00Z|
    +----+---------------------+------------+----------+---------+---------+---------------------+

### With every relevant option

    sylve task list --active --guest-type vm --guest-id 101 --long --node node1.example.test -f json

Output (illustrative):

    [
      {
        "id": 43,
        "node": "node1.example.test",
        "guestType": "vm",
        "guestId": 101,
        "action": "migrate",
        "status": "RUNNING",
        "createdAt": "2026-10-28T20:00:00Z",
        "requestedBy": "admin",
        "message": "migration in progress",
        "error": ""
      }
    ]

`--active` switched the endpoint from recent to active. `--limit` has no
effect in active mode. `--long` added `Requested By`, `Message`, and `Error`.

### Show, wait, cancel

    sylve task show 42 -f json

    sylve task wait 42 --timeout 120 --node node1.example.test

Output (illustrative):

    Completed Task #42
    +-------+---------+
    | Field | Value   |
    +-------+---------+
    | id    | 42      |
    | status| SUCCESS |
    +-------+---------+

    sylve task cancel-migration 43 --node node1.example.test

Output:

    Requested cancellation of migration task #43.

### Generic active task

    sylve task active vm 101 -f json

Output (illustrative):

    {
      "id": 43,
      "guestType": "vm",
      "guestId": 101,
      "status": "RUNNING"
    }

## Inputs

- The active context and token.
- Task IDs from `task list` or from a command that printed `task #N`.
- Generic commands accept `--data` and `--param`.

## Outputs

- Task tables, task details, or the completed task object.
- Exit `0` on success. Exit `1` on API failure, timeout, or failed task. Exit
  `2` on usage error.
