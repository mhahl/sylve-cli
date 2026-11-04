# SYLVE-MDNS(1)

## NAME

`sylve-mdns` - manage mDNS configuration and records

## SYNOPSIS

```sh
sylve mdns COMMAND [ARGS ...]
```

## DESCRIPTION

`sylve mdns` manages multicast DNS (mDNS) daemon settings and advertised
records via generic Sylve API bindings. Supply request payloads with
`--data` in JSON or YAML format.

## SUBCOMMANDS

| Subcommand | Path Arguments | Description |
|---|---|---|
| `config` | none | Show mDNS daemon configuration |
| `config-set` | none | Update mDNS daemon configuration |
| `record list` | none | List mDNS records |
| `record create` | none | Create an mDNS record |
| `record set` | `ID` | Update record `ID` |
| `record delete` | `ID` | Delete record `ID` |

## OPTIONS

Write subcommands accept `--data/-d` and `--set/--property/-s`; all subcommands accept:

- `-d, --data BODY`
  JSON or YAML request body, or `@FILE` (write commands).
- `-s, --set, --property KEY=VALUE`
  Set one body field (repeatable, dotted keys nest); overrides `--data` (write commands).
- `-p, --param KEY=VALUE`
  Query parameter (repeatable).
- `--dry-run`
  Print the request without sending it.
- `-y, --yes`
  Skip confirmation (destructive commands only, e.g. deletes).
- `-n, --node NODE`
  Target node.
- `-f, --format {table,json,yaml,value,csv}`
  Output format (default: `table`).
- `-c, --column`, `--sort-column`, `--filter`, `-l, --limit`
  Output selection (reads only).

## EXIT STATUS

- `0`: Success.
- `1`: API error or aborted confirmation.
- `2`: Command-line usage error.

## EXAMPLES

List mDNS records as JSON:

```sh
sylve mdns record list -f json
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
sylve mdns record create \
  --set name=sylve.local --set type=A --set interfaces=em0 \
  --node node1.example.test \
  --format json

sylve mdns record set 2 --set interfaces=em0,em1 -f json
sylve mdns record delete 2 --yes
sylve mdns config -f json
sylve mdns config-set --set hostname=example-host --set interfaces=em0 -f json
```

Preview a daemon config change and a record create with `--set`:

```sh
sylve mdns config-set --set hostname=example-host --set interfaces=em0 --dry-run -f json
sylve mdns record create \
  --set name=example-service --set type=_http._tcp \
  --set port=8080 --set interfaces=em0 \
  --dry-run -f json
```

Filter the record list, preview an update, and delete:

```sh
sylve mdns record list -c id -c name -c type --filter type=_http -l 10
sylve mdns record set 2 --set port=9090 --dry-run -f json
sylve mdns record delete 2 --yes
```

## SEE ALSO

[sylve(1)](../../README.md),
[sylve-ddns(1)](ddns.md),
[sylve-network(1)](network.md),
[sylve-options(7)](../global-options.md)
