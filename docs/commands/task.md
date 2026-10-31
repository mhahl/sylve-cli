# SYLVE-TASK(1)

## NAME

`sylve-task` — inspect, wait for, or cancel guest lifecycle and migration tasks

## SYNOPSIS

```sh
sylve task COMMAND [ARGS ...]
```

## DESCRIPTION

`sylve task` lists, inspects, polls, and cancels asynchronous VM and jail
lifecycle or migration tasks created by Sylve. Task IDs are returned by
`task list` or by commands that queue background work.

## SUBCOMMANDS

| Subcommand | Description |
|---|---|
| `list` | List active or recent lifecycle tasks |
| `show TASK_ID` | Display full details for a task |
| `wait TASK_ID` | Poll a task until it completes or times out |
| `cancel-migration TASK_ID` | Request cancellation of an active migration task |
| `active GUEST_TYPE GUEST_ID` | Show the active task for one guest |

## OPTIONS

### `task list`

- `--active / --recent`
  Show queued/running tasks (`--active`) or recent completed/active tasks
  (`--recent`). Default: `--recent`.
- `--guest-type TYPE`
  Filter by guest type (`vm` or `jail`).
- `--guest-id ID`
  Filter by VM RID or jail CTID.
- `--limit, -l N`
  Maximum recent tasks per node (default: `25`; ignored with `--active`).
- `-n, --node NODE`, `-f, --format`, `-c, --column`, `--sort-column`, `--long`
  Standard node and output options. `--long` adds `Requested By`, `Message`,
  and `Error`.

### `task show`

- `TASK_ID` (required)
  Task ID.
- `-n, --node NODE`, `-f, --format`, `-c, --column`
  Standard node and output options.

### `task wait`

- `TASK_ID` (required)
  Task ID to poll.
- `--timeout SECONDS`
  Maximum wait time in seconds (default: `600.0`).
- `-n, --node NODE`, `-f, --format`
  Standard node and output options.

### `task cancel-migration`

- `TASK_ID` (required)
  Migration task ID.
- `-n, --node NODE`
  Target node.

### `task active`

- `GUEST_TYPE GUEST_ID` (required)
  Guest type (`vm` or `jail`) and guest ID.
- `-d, --data`, `-p, --param`, `-n, --node`, `-f, --format`
  Generic API options. `task active` is read-only and has no `--yes`.

## EXIT STATUS

- `0` — Success.
- `1` — API error, wait timeout, or task finished in a failed state.
- `2` — Command-line usage error.

## EXAMPLES

List recent lifecycle tasks:

```sh
sylve task list
```

```text
Recent Lifecycle Tasks
 ID  Node                Guest Type  Guest ID  Action  Status   Created At
 42  node1.example.test  vm               101  start   SUCCESS  2026-10-28 20:00:00 +0000
```

List active tasks for VM `101` on one node with extended fields as JSON:

```sh
sylve task list --active --guest-type vm --guest-id 101 --long --node node1.example.test -f json
```

```json
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
```

Inspect, wait for, or cancel a task:

```sh
sylve task show 42 -f json
sylve task wait 42 --timeout 120 --node node1.example.test
sylve task cancel-migration 43 --node node1.example.test
# Requested cancellation of migration task #43.
```

Query the active task for VM `101`:

```sh
sylve task active vm 101 -f json
```

## SEE ALSO

[sylve(1)](../../README.md),
[sylve-vm(1)](vm.md),
[sylve-jail(1)](jail.md),
[sylve-node(1)](node.md),
[sylve-options(7)](../global-options.md)
