# SYLVE-MDNS(1)

## NAME

`sylve-mdns` — manage mDNS configuration and records

## SYNOPSIS

```sh
sylve mdns COMMAND [ARGS ...]
```

## DESCRIPTION

`sylve mdns` manages multicast DNS (mDNS) daemon settings and advertised
records via generic Sylve API bindings. Request payloads are supplied with
`--data` in JSON or YAML format.

## SUBCOMMANDS

| Subcommand | Path Arguments | Description |
|---|---|---|
| `config` | none | Show mDNS daemon configuration |
| `config-set` | none | Update mDNS daemon configuration |
| `records` | none | List mDNS records |
| `record-create` | none | Create an mDNS record |
| `record-update` | `ID` | Update record `ID` |
| `record-delete` | `ID` | Delete record `ID` |

## OPTIONS

All subcommands accept:

- `-d, --data BODY`
  JSON or YAML request body, or `@FILE`.
- `-s, --set KEY=VALUE`
  Set one body field (repeatable, dotted keys nest); overrides `--data`.
- `-p, --param KEY=VALUE`
  Query parameter (repeatable).
- `--dry-run`
  Print the request without sending it.
- `-y, --yes`
  Skip destructive-request confirmation.
- `-n, --node NODE`
  Target node.
- `-f, --format {table,json,yaml,value,csv}`
  Output format (default: `table`).
- `-c, --column`, `--sort-column`, `--filter`, `-l, --limit`
  Output selection (reads only).

## EXIT STATUS

- `0` — Success.
- `1` — API error or aborted confirmation.
- `2` — Command-line usage error.

## EXAMPLES

List mDNS records as JSON:

```sh
sylve mdns records -f json
```

```json
[
  {
    "id": 1,
    "name": "sylve.local",
    "type": "A",
    "value": "10.0.0.11"
  }
]
```

Create, update, and delete a record, and configure the mDNS service:

```sh
sylve mdns record-create \
  --set name=sylve.local --set type=A --set value=10.0.0.11 --set ttl=300 \
  --param validate=1 \
  --node node1.example.test \
  --format json

sylve mdns record-update 2 --set ttl=600 -f json
sylve mdns record-delete 2 --yes
sylve mdns config -f json
sylve mdns config-set --set enabled=true --set 'interfaces=[em0]' -f json
```

## SEE ALSO

[sylve(1)](../../README.md),
[sylve-ddns(1)](ddns.md),
[sylve-network(1)](network.md),
[sylve-options(7)](../global-options.md)
