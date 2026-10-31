# SYLVE-CLUSTER(1)

## NAME

`sylve-cluster` — inspect cluster state, manage Raft membership, and edit cluster notes

## SYNOPSIS

```sh
sylve cluster COMMAND [ARGS ...]
```

## DESCRIPTION

`sylve cluster` queries cluster health and cluster-wide guest resources,
bootstraps or modifies Raft cluster membership, and manages cluster-wide notes.

## SUBCOMMANDS

| Subcommand | Description |
|---|---|
| `show`, `status` | Display cluster status, Raft leader, members, and node health |
| `resources` | List all VMs, jails, and templates across the cluster |
| `resync` | Audit Raft members and resynchronize followers |
| `create --ip IP` | Initialize a new cluster on this node |
| `join-key` | Display the cluster join key |
| `join` | Join this node to an existing cluster |
| `leave` | Remove this node from the cluster |
| `note list` | List cluster notes |
| `note show NOTE_ID` | Display full details of a cluster note |
| `note create` | Create a cluster note |
| `note delete NOTE_ID` | Delete a cluster note |
| `note update ID`, `note bulk-delete`, `accept-join` | Generic API commands |

## OPTIONS

### `cluster show` / `cluster status`

- `-f, --format {table,json,yaml,value,csv}`
  Output format (default: `table`).
- `-c, --column NAME`
  Select fields.
- `--long`
  Add `nodeUUID` and `api` columns to the node table.

### `cluster resources`

- `-f, --format {table,json,yaml,value,csv}`
  Output format (default: `table`).
- `-c, --column NAME`
  Select columns: `id`, `name`, `type`, `state`, `node`, `node_uuid`.
- `--sort-column NAME`
  Sort rows by column.
- `--long`
  Add the `Node UUID` column.

### `cluster resync`

- `-f, --format {table,json,yaml,value,csv}`
  Output format (default: `table`).

### `cluster create`

- `--ip IP` (required)
  Bootstrap Raft IP address for this node.

### `cluster join-key`

- `-f, --format {table,json,yaml,value,csv}`
  Output format (default: `table`).

### `cluster join`

- `--leader-ip IP` (required)
  IP address of the cluster leader.
- `--node-ip IP` (required)
  Raft IP address of this joining node.
- `--node-id UUID` (required)
  Node UUID of this joining node.
- `--cluster-key KEY` (required)
  Cluster join key.

### `cluster leave`

- `--retain-guests / --no-retain-guests`
  Keep local VM and jail registrations (default: `--retain-guests`). Ignored
  when `--force` is set.
- `--force`
  Force a local cluster state reset without contacting Raft.
- `-y, --yes`
  Skip confirmation prompt.

### `cluster note list`

- `-f, --format {table,json,yaml,value,csv}`
  Output format (default: `table`).
- `-c, --column NAME`
  Select columns: `id`, `title`, `content`, `updatedAt`.
- `--long`
  Add the `Content` column.

### `cluster note show`

- `NOTE_ID` (required)
  Cluster note ID.
- `-f, --format {table,json,yaml,value,csv}`
  Output format (default: `table`).
- `-c, --column NAME`
  Select fields.

### `cluster note create`

- `--title, -t TEXT` (required)
  Note title (3–128 characters).
- `--content, -m TEXT` (required)
  Note body.

### `cluster note delete`

- `NOTE_ID` (required)
  Cluster note ID.

### Generic Subcommands

`accept-join`, `note update ID`, and `note bulk-delete` accept `--data/-d`,
`--param/-p`, `-y/--yes`, `-n/--node`, and `-f/--format`.

| Subcommand | Path Arguments |
|---|---|
| `accept-join` | none |
| `note update` | `id` |
| `note bulk-delete` | none |

## EXIT STATUS

- `0` — Success.
- `1` — API failure or aborted confirmation.
- `2` — Command-line usage error.

## EXAMPLES

Inspect cluster status:

```sh
sylve cluster status
```

```text
Cluster Status
 Field            Value
 enabled          true
 node_id          node-1
 leader_id        node-1
 leader_address   10.0.0.11
 raft_ip          10.0.0.11
 raft_port        8182
 partial          false
 nodes_online     3/3
 total_guests     12
```

List cluster-wide resources sorted by name as JSON:

```sh
sylve cluster resources --long --sort-column name --format json -c 'Name,Type,State,Node,Node UUID'
```

```json
[
  {
    "name": "db-01",
    "type": "vm",
    "state": "RUNNING",
    "node": "node1.example.test",
    "node_uuid": "1f0f..."
  }
]
```

Initialize a cluster and join a second node:

```sh
sylve cluster create --ip 10.0.0.11
sylve cluster join-key
sylve cluster join \
  --leader-ip 10.0.0.11 \
  --node-ip 10.0.0.12 \
  --node-id 2b7c... \
  --cluster-key 'join-key-from-leader'
```

```text
Cluster created with bootstrap IP 10.0.0.11.
Node joined cluster via leader 10.0.0.11.
```

Force a node to leave the cluster without interactive confirmation:

```sh
sylve cluster leave --no-retain-guests --force --yes
# Node has left the cluster.
```

Create, list, show, and delete a cluster note:

```sh
sylve cluster note create --title "Maintenance" --content "node2 drains at 22:00"
# Created cluster note 'Maintenance'.

sylve cluster note list --long -f table
```

```text
Cluster Notes
 ID  Title        Content                   Updated At
 1   Maintenance  node2 drains at 22:00     2026-10-28T20:00:00Z
```

```sh
sylve cluster note show 1 -f json
sylve cluster note delete 1
# Deleted cluster note #1.
```

Execute generic cluster API endpoints:

```sh
sylve cluster accept-join --data '{"nodeId":"2b7c...","nodeIp":"10.0.0.12"}' --param dryRun=0 --node node1.example.test -f json
sylve cluster note bulk-delete --data '{"ids":[1,2]}' --yes
```

## SEE ALSO

[sylve(1)](../../README.md),
[sylve-node(1)](node.md),
[sylve-options(7)](../global-options.md)
