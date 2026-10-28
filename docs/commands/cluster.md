# sylve cluster

Show cluster status, manage Raft membership, and edit cluster notes.

## Synopsis

    sylve cluster COMMAND [ARGS]...

## Commands

| Command | Purpose |
|---|---|
| `show`, `status` | Cluster status, leader, Raft members, node health |
| `resources` | All VMs, jails, and templates across the cluster |
| `resync` | Audit Raft members and resynchronize followers |
| `create --ip IP` | Initialize a cluster |
| `join-key` | Reveal the cluster join key |
| `join` | Join this node to a cluster |
| `leave` | Remove this node from the cluster |
| `note list` | List cluster notes |
| `note create` | Create a cluster note |
| `note delete` | Delete a cluster note |
| `note update`, `note bulk-delete`, `accept-join` | Generic API commands |

## Options

### `cluster show` / `cluster status`

- `-f, --format {table,json,yaml,value,csv}`
  Output format. Default: `table`.
- `-c, --column NAME`
  Select fields.
- `--long`
  Add `nodeUUID` and `api` columns to the node table.

### `cluster resources`

- `-f, --format {table,json,yaml,value,csv}`
  Output format. Default: `table`.
- `-c, --column NAME`
  Select columns: `id`, `name`, `type`, `state`, `node`, `node_uuid`.
- `--sort-column NAME`
  Sort rows.
- `--long`
  Add the `Node UUID` column.

### `cluster resync`

- `-f, --format {table,json,yaml,value,csv}`
  Output format. Default: `table`.

### `cluster create`

- `--ip IP` (required)
  Bootstrap Raft IP address for this node.

### `cluster join-key`

- `-f, --format {table,json,yaml,value,csv}`
  Output format. Default: `table`.

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
  Keep local VM and jail registrations. Default: `--retain-guests`.
- `--force`
  Force a local cluster reset without contacting Raft.
- `-y, --yes`
  Skip confirmation.

### `cluster note list`

- `-f, --format {table,json,yaml,value,csv}`
  Output format. Default: `table`.
- `-c, --column NAME`
  Select columns: `id`, `title`, `content`, `updatedAt`.
- `--long`
  Add the `Content` column.

### `cluster note create`

- `--title, -t TEXT` (required)
  Note title, 3-128 characters.
- `--content, -m TEXT` (required)
  Note body.

### `cluster note delete`

- `NOTE_ID` (required)
  Cluster note ID.

### Generic commands

`cluster accept-join`, `cluster note update`, and `cluster note bulk-delete`
accept `--data/-d`, `--param/-p`, `-y/--yes`, `-n/--node`, and
`-f/--format`. Path arguments:

| Command | Arguments |
|---|---|
| `accept-join` | none |
| `note update` | `id` |
| `note bulk-delete` | none |

See [Global and common options](../global-options.md).

## Examples

### Minimal

    sylve cluster status

Output (illustrative):

    Cluster Status
    +-----------------+-----------------------------+
    | Field           | Value                       |
    +-----------------+-----------------------------+
    | enabled         | true                        |
    | node_id         | node-1                      |
    | leader_id       | node-1                      |
    | leader_address  | 10.0.0.11                   |
    | raft_ip         | 10.0.0.11                   |
    | raft_port       | 8182                        |
    | partial         | false                       |
    | nodes_online    | 3/3                         |
    | total_guests    | 12                          |
    +-----------------+-----------------------------+

### With every relevant option

    sylve cluster resources --long --sort-column name --format json -c 'Name,Type,State,Node,Node UUID'

Output (illustrative):

    [
      {
        "name": "db-01",
        "type": "vm",
        "state": "RUNNING",
        "node": "node1.example.test",
        "node_uuid": "1f0f..."
      }
    ]

### Create and join

    sylve cluster create --ip 10.0.0.11

    sylve cluster join-key

    sylve cluster join \
      --leader-ip 10.0.0.11 \
      --node-ip 10.0.0.12 \
      --node-id 2b7c... \
      --cluster-key 'join-key-from-leader'

Output (illustrative):

    Cluster created with bootstrap IP 10.0.0.11.
    Node joined cluster via leader 10.0.0.11.

### Leave with every option

    sylve cluster leave --no-retain-guests --force --yes

Output:

    Node has left the cluster.

`--no-retain-guests` would be ignored with `--force`; the force path resets
local cluster state.

### Notes

    sylve cluster note create --title "Maintenance" --content "node2 drains at 22:00"

Output:

    Created cluster note 'Maintenance'.

    sylve cluster note list --long -f table

Output (illustrative):

    Cluster Notes
    +----+-------------+--------------------------+---------------------+
    | ID | Title       | Content                  | Updated At          |
    +----+-------------+--------------------------+---------------------+
    | 1  | Maintenance | node2 drains at 22:00    | 2026-10-28T20:00:00Z|
    +----+-------------+--------------------------+---------------------+

    sylve cluster note delete 1

Output:

    Deleted cluster note #1.

### Generic command with every option

    sylve cluster accept-join --data '{"nodeId":"2b7c...","nodeIp":"10.0.0.12"}' --param dryRun=0 --node node1.example.test -f json

Output (illustrative):

    {
      "status": "accepted"
    }

    sylve cluster note bulk-delete --data '{"ids":[1,2]}' --yes

Output (illustrative):

    OK

## Inputs

- The active context and token.
- Cluster and Raft state from the Sylve API.
- `--data` accepts inline JSON/YAML or `@file`.

## Outputs

- Status and resource tables, or JSON/YAML/value/CSV.
- Mutating commands print a single confirmation line.
- Exit `0` on success. Exit `1` on API failure or aborted confirmation. Exit
  `2` on usage error.
