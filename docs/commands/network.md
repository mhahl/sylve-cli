# SYLVE-NETWORK(1)

## NAME

`sylve-network` — manage interfaces, switches, routes, DHCP, PF firewall rules, network objects, and WireGuard

## SYNOPSIS

```sh
sylve network GROUP COMMAND [ARGS ...]
```

## DESCRIPTION

`sylve network` configures host and guest networking on Sylve nodes, including
physical/virtual interfaces, standard and manual bridge switches, static
routes, DHCP scopes and leases, PF traffic/NAT firewall rules and live logs,
reusable network objects, and WireGuard VPN servers, peers, and clients.

## SUBCOMMANDS

| Group | Subcommands |
|---|---|
| `interface` | `list`, `l3` |
| `switch` | `list`, `create-standard`, `create-manual`, `delete`, `sync`, `update-standard` |
| `route` | `list`, `create`, `update`, `delete` |
| `dhcp` | `config`, `config-update`, `range-list`, `range-create`, `range-update`, `range-delete`, `lease-list`, `lease-create`, `lease-update`, `lease-delete`, `lease-delete-dynamic` |
| `firewall` | `traffic-list`, `nat-list`, `logs`, `advanced-show`, `advanced-update`, `advanced-preview`, `advanced-rendered`, `traffic-create`, `traffic-update`, `traffic-delete`, `traffic-bulk-delete`, `traffic-reorder`, `traffic-counters`, `nat-create`, `nat-update`, `nat-delete`, `nat-bulk-delete`, `nat-reorder`, `nat-counters`, `nat-route-suggestions` |
| `object` | `list`, `create`, `update`, `delete`, `bulk-delete` |
| `wireguard` | `status`, `client-list`, `server-init`, `server-update`, `server-delete`, `server-state`, `peer-add`, `peer-update`, `peer-remove`, `peer-state`, `client-create`, `client-update`, `client-delete`, `client-state` |

## OPTIONS

### `interface`

- `list`: `-n, --node NODE`, `-f, --format`, `-c, --column`,
  `--sort-column NAME`, `--long`.
- `l3`: `-n, --node NODE`, `-f, --format`, `-c, --column`.

### `switch`

- `list`: `-n, --node NODE`, `-f, --format`, `-c, --column`,
  `--sort-column NAME`, `--long`.
- `create-standard`:
  - `--name NAME` (required): switch name.
  - `--port, -p INTERFACE`: bridge member port (repeatable).
  - `--private / --public`: host-only or uplinked switch (default: `--public`).
  - `--dhcp / --no-dhcp`: enable DHCP on the switch (default: `--no-dhcp`).
  - `--mtu N`: MTU (default: `1500`).
  - `--vlan N`: VLAN tag (default: `0`).
  - `--vlan-filtering / --no-vlan-filtering`: FreeBSD bridge VLAN filtering
    (default: `--no-vlan-filtering`).
  - `--default-access-vlan N`: default access VLAN when filtering is enabled
    (default: `0`).
  - `-n, --node NODE`: target node.
- `create-manual`: `--name NAME` (required), `--bridge BRIDGE` (required, e.g.
  `bridge0`), `-n, --node NODE`.
- `delete SWITCH_ID`: `--type, -t {standard,manual}` (default: `standard`),
  `-n, --node NODE`.
- `sync`: `-n, --node NODE`.

### `route`, `dhcp`, `firewall`, `object`, and `wireguard`

- `route list`: `-n/--node`, `-f/--format`, `-c/--column`, `--long`.
- `route delete ROUTE_ID`: `-n/--node`.
- `dhcp config`, `dhcp range-list`, `dhcp lease-list`: `-n/--node`,
  `-f/--format`, `-c/--column`.
- `firewall traffic-list`, `firewall nat-list`: `-n/--node`, `-f/--format`,
  `-c/--column`, `--long`.
- `firewall logs`: `--limit, -l N` (default: `50`), `--cursor N` (`0` starts at
  the live stream position), `--follow, -F` (poll continuously),
  `--interval SECONDS` (default: `1.5`), `--rule-type {traffic,nat}`,
  `--rule-id ID`, `--action {pass,block,scrub,nat,binat,rdr}`,
  `--direction {in,out}`, `--interface, -i INTERFACE`, `--query, -q TEXT`,
  `-n/--node`, `-f/--format`, `-c/--column`.
- `object list`: `-n/--node`, `-f/--format`, `-c/--column`.
- `object create`: `--name NAME` (required), `--type, -t TYPE` (required, e.g.
  `Host`, `Network`, `Port`, `Mac`), `--value, -v VALUE` (required, repeatable),
  `-n/--node`.
- `object delete OBJECT_ID`: `-n/--node`.
- `wireguard status`, `wireguard client-list`: `-n/--node`, `-f/--format`,
  `-c/--column`.

### Generic Subcommands

All remaining subcommands accept `--data/-d`, `--param/-p`, `-y/--yes`,
`-n/--node`, and `-f/--format`:

| Subcommand | Path Arguments |
|---|---|
| `switch update-standard`, `route update`, `object update` | `id` |
| `dhcp range-update`, `range-delete`, `lease-update`, `lease-delete` | `id` |
| `firewall traffic-update`, `traffic-delete`, `nat-update`, `nat-delete`, `nat-route-suggestions` | `id` |
| `wireguard peer-update`, `peer-remove`, `peer-state` | `peerId` |
| `wireguard client-update`, `client-delete`, `client-state` | `clientId` |
| all other generic subcommands | none |

## EXIT STATUS

- `0` — Success.
- `1` — API error or aborted confirmation.
- `2` — Command-line usage error.

## EXAMPLES

List network interfaces:

```sh
sylve network interface list
```

```text
Network Interfaces
+-----------+--------------------+---------------+-------------+-------------+
| Name      | Node               | IPv4          | IPv6        | Description |
+-----------+--------------------+---------------+-------------+-------------+
| em0       | node1.example.test | 10.0.0.11/24  | fe80::1/64  | uplink      |
| vm-public | node1.example.test | 10.0.10.1/24  | -           | VM bridge   |
+-----------+--------------------+---------------+-------------+-------------+
```

Create a VLAN-filtered standard switch, a manual switch, and synchronize switch
state:

```sh
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
# Created standard switch 'vm-public'.

sylve network switch create-manual --name lab --bridge bridge0 --node node1.example.test
sylve network switch delete 3 --type manual --node node1.example.test
sylve network switch sync --node node1.example.test
```

Inspect DHCP configuration and blocked PF firewall log entries:

```sh
sylve network dhcp config --node node1.example.test -f json
sylve network firewall logs --limit 20 --action block --interface em0
sylve network firewall logs --follow --rule-type traffic --direction in
```

Create a reusable host object and a static route:

```sh
sylve network object create \
  --name web-servers \
  --type Host \
  --value 10.0.10.21 \
  --value 10.0.10.22 \
  --node node1.example.test

sylve network route create --param validate=1 --node node1.example.test \
  --data '{"name":"lab","destinationRaw":"10.99.0.0/16","gatewayRaw":"10.0.0.1"}' \
  --format json
```

## SEE ALSO

[sylve(1)](../../README.md),
[sylve-vm(1)](vm.md),
[sylve-jail(1)](jail.md),
[sylve-ddns(1)](ddns.md),
[sylve-mdns(1)](mdns.md),
[sylve-options(7)](../global-options.md)
