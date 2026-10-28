# sylve network

Manage interfaces, switches, routes, DHCP, PF firewall rules, network objects,
and WireGuard.

## Synopsis

    sylve network COMMAND [ARGS]...

## Commands

| Group | Commands |
|---|---|
| `interface` | `list`, `l3` |
| `switch` | `list`, `create-standard`, `create-manual`, `delete`, `sync`, `update-standard` |
| `route` | `list`, `create`, `update`, `delete` |
| `dhcp` | `config`, `config-update`, `range-list`, `range-create`, `range-update`, `range-delete`, `lease-list`, `lease-create`, `lease-update`, `lease-delete`, `lease-delete-dynamic` |
| `firewall` | `traffic-list`, `nat-list`, `logs`, `advanced-show`, `advanced-update`, `advanced-preview`, `advanced-rendered`, `traffic-create`, `traffic-update`, `traffic-delete`, `traffic-bulk-delete`, `traffic-reorder`, `traffic-counters`, `nat-create`, `nat-update`, `nat-delete`, `nat-bulk-delete`, `nat-reorder`, `nat-counters`, `nat-route-suggestions` |
| `object` | `list`, `create`, `update`, `delete`, `bulk-delete` |
| `wireguard` | `status`, `client-list`, `server-init`, `server-update`, `server-delete`, `server-state`, `peer-add`, `peer-update`, `peer-remove`, `peer-state`, `client-create`, `client-update`, `client-delete`, `client-state` |

## Options

### `interface list`

- `-n, --node NODE`, `-f, --format`, `-c, --column`,
  `--sort-column NAME`, `--long`.

### `interface l3`

- `-n, --node NODE`, `-f, --format`, `-c, --column`.

### `switch list`

- `-n, --node NODE`, `-f, --format`, `-c, --column`,
  `--sort-column NAME`, `--long`.

### `switch create-standard`

- `--name NAME` (required)
  Switch name.
- `--port, -p INTERFACE`
  Bridge member port. Repeatable.
- `--private / --public`
  Host-only switch. Default: `--public`.
- `--dhcp / --no-dhcp`
  DHCP on the switch. Default: `--no-dhcp`.
- `--mtu N`
  MTU. Default: `1500`.
- `--vlan N`
  VLAN tag. Default: `0`.
- `--vlan-filtering / --no-vlan-filtering`
  FreeBSD bridge VLAN filtering. Default: off.
- `--default-access-vlan N`
  Default access VLAN when filtering is enabled. Default: `0`.
- `-n, --node NODE`
  Target node.

### `switch create-manual`

- `--name NAME` (required)
  Switch name.
- `--bridge BRIDGE` (required)
  Existing host bridge, for example `bridge0`.
- `-n, --node NODE`.

### `switch delete`

- `SWITCH_ID` (required)
  Switch ID.
- `--type, -t TYPE`
  `standard` or `manual`. Default: `standard`.
- `-n, --node NODE`.

### `switch sync`

- `-n, --node NODE`.

### `route list`, `route delete`

- `list`: `-n/--node`, `-f/--format`, `-c/--column`, `--long`.
- `delete`: `ROUTE_ID` (required), `-n/--node`.

### `dhcp config`, `range-list`, `lease-list`

- `-n/--node`, `-f/--format`, `-c/--column`.

### `firewall traffic-list`, `nat-list`

- `-n/--node`, `-f/--format`, `-c/--column`, `--long`.

### `firewall logs`

- `--limit, -l N`
  Maximum entries. Default: `50`.
- `--action ACTION`
  Filter by `pass` or `block`.
- `--interface, -i INTERFACE`
  Filter by interface.
- `-n/--node`, `-f/--format`, `-c/--column`.

### `object list`

- `-n/--node`, `-f/--format`, `-c/--column`.

### `object create`

- `--name NAME` (required)
  Object name.
- `--type, -t TYPE` (required)
  For example `Host`, `Network`, `Port`, or `Mac`.
- `--value, -v VALUE` (required)
  Object value. Repeatable.
- `-n/--node`.

### `object delete`

- `OBJECT_ID` (required), `-n/--node`.

### `wireguard status`, `client-list`

- `-n/--node`, `-f/--format`, `-c/--column`.

### Generic commands

All remaining commands accept `--data/-d`, `--param/-p`, `-y/--yes`,
`-n/--node`, and `-f/--format`. Path arguments:

| Command | Arguments |
|---|---|
| `switch update-standard` | `id` |
| `route create` | none |
| `route update` | `id` |
| `dhcp range-update`, `range-delete` | `id` |
| `dhcp lease-update`, `lease-delete` | `id` |
| `firewall traffic-update`, `traffic-delete` | `id` |
| `firewall nat-update`, `nat-delete`, `nat-route-suggestions` | `id` |
| `object update` | `id` |
| `wireguard peer-update`, `peer-remove`, `peer-state` | `peerId` |
| `wireguard client-update`, `client-delete`, `client-state` | `clientId` |
| `dhcp config-update`, `range-create`, `lease-create`, `lease-delete-dynamic`, firewall `advanced-*`, `traffic-create`, `traffic-bulk-delete`, `traffic-reorder`, `traffic-counters`, `nat-create`, `nat-bulk-delete`, `nat-reorder`, `nat-counters`, `object bulk-delete`, wireguard `server-*`, `peer-add`, `client-create` | none |

## Examples

### Minimal

    sylve network interface list

Output (illustrative):

    Network Interfaces
    +--------+---------------------+----------------+---------------------+-------------+
    | Name   | Node                | IPv4           | IPv6                | Description |
    +--------+---------------------+----------------+---------------------+-------------+
    | em0    | node1.example.test  | 10.0.0.11/24   | fe80::1/64          | uplink      |
    | vm-public | node1.example.test| 10.0.10.1/24  | -                   | VM bridge   |
    +--------+---------------------+----------------+---------------------+-------------+

### With every relevant option

    sylve network switch create-standard \
      --name vm-public \
      --port em1 --port em2 \
      --private \
      --dhcp \
      --mtu 9000 \
      --vlan 10 \
      --vlan-filtering \
      --default-access-vlan 10 \
      --node node1.example.test

Output:

    Created standard switch 'vm-public'.

`--private` changed the switch from public to host-only. `--vlan-filtering`
enabled bridge VLAN filtering and `--default-access-vlan 10` set its access
VLAN. `--port` is repeatable.

### Manual switch, delete, sync

    sylve network switch create-manual --name lab --bridge bridge0 --node node1.example.test

    sylve network switch delete 3 --type manual --node node1.example.test

    sylve network switch sync --node node1.example.test

Output (illustrative):

    Created manual switch 'lab' on bridge 'bridge0'.
    Deleted manual switch #3.
    Switch configuration synchronized.

### DHCP and firewall

    sylve network dhcp config --node node1.example.test -f json

    sylve network dhcp range-list --node node1.example.test

    sylve network firewall logs --limit 20 --action block --interface em0

    sylve network firewall traffic-list --long --sort-column priority

Output (illustrative):

    Firewall Live Logs
    +---------------------+--------+-----+-----------+-------+-------------+-------------+---------+
    | Time                | Action | Dir | Interface | Proto | Source      | Destination | Rule ID |
    +---------------------+--------+-----+-----------+-------+-------------+-------------+---------+
    | 2026-10-28T20:00:00Z| block  | in  | em0       | tcp   | 203.0.113.5 | 10.0.0.11   | 12      |
    +---------------------+--------+-----+-----------+-------+-------------+-------------+---------+

### Create an object with every option

    sylve network object create \
      --name web-servers \
      --type Host \
      --value 10.0.10.21 \
      --value 10.0.10.22 \
      --node node1.example.test

Output:

    Created network object 'web-servers' (Host).

### Generic command with every option

    sylve network route create --param validate=1 --node node1.example.test \
      --data '{"name":"lab","destinationRaw":"10.99.0.0/16","gatewayRaw":"10.0.0.1"}' \
      --format json

Output (illustrative):

    {
      "id": 4,
      "name": "lab"
    }

    sylve network firewall traffic-delete 12 --yes

Output (illustrative):

    OK

## Inputs

- The active context and token.
- `--data` inline JSON/YAML or `@file`.
- `--param KEY=VALUE` repeated for query parameters. Values are parsed as YAML
  scalars.

## Outputs

- Tables, JSON, YAML, value, or CSV.
- Mutating commands print a confirmation line, or the API result for generic
  commands.
- Exit `0` on success. Exit `1` on API error or aborted confirmation. Exit `2`
  on usage error.
