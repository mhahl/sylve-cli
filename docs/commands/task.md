# SYLVE-TASK(1)

## NAME

`sylve-task` - inspect, wait for, or cancel guest lifecycle and migration tasks

## SYNOPSIS

```sh
sylve task COMMAND [ARGS ...]
```

## DESCRIPTION

`sylve task` lists, inspects, polls, and cancels asynchronous VM and jail
lifecycle or migration tasks created by Sylve. `task list` and commands that
queue background work return task IDs.

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
- `-y, --yes`
  Skip confirmation prompt.
- `-n, --node NODE`
  Target node.
- `-f, --format`
  Standard output option.

### `task active`

- `GUEST_TYPE GUEST_ID` (required)
  Guest type (`vm` or `jail`) and guest ID.
- `-d, --data`, `-s, --property`, `-p, --param`, `--dry-run`, `-n, --node`,
  `-f, --format`, `-c, --column`, `--sort-column`, `--filter`, `-l, --limit`
  Generic API options. `task active` only reads and takes no `--yes`.

## EXIT STATUS

- `0`: Success.
- `1`: API error, wait timeout, or task finished in a failed state.
- `2`: Command-line usage error.

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

List only active tasks across all nodes, filtered and sorted:

```sh
sylve task list --active -f table -c ID,Node,Action,Status --sort-column Status
sylve task list --active --guest-type jail --filter Status=RUNNING
```

List recent tasks for one guest with a small page size:

```sh
sylve task list --recent --guest-type vm --guest-id 101 -l 5
sylve task list --recent --guest-type jail -l 10 --node node1.example.test -f json
```

Wait with a short timeout and show the completion output:

```sh
sylve task wait 42 --timeout 30
# Task #42 completed: SUCCESS.
```

Cancel a migration without prompting:

```sh
sylve task cancel-migration 43 --yes --node node1.example.test
# Requested cancellation of migration task #43.
```

Preview the active-task request for a jail without querying the server:

```sh
sylve task active jail 5 --dry-run
```

```text
Dry run: GET /tasks/lifecycle/active/jail/5
 Field   Value
 method  GET
 path    /tasks/lifecycle/active/jail/5
 params  -
 body    -
```

## SEE ALSO

[sylve(1)](../../README.md),
[sylve-vm(1)](vm.md),
[sylve-jail(1)](jail.md),
[sylve-node(1)](node.md),
[sylve-options(7)](../global-options.md)
