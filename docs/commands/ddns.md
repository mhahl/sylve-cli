# SYLVE-DDNS(1)

## NAME

`sylve-ddns` - manage dynamic DNS entries

## SYNOPSIS

```sh
sylve ddns COMMAND [ARGS ...]
```

## DESCRIPTION

`sylve ddns` creates, updates, synchronizes, and deletes dynamic DNS entries via
generic Sylve API bindings. Supply request payloads with `--data` in JSON
or YAML format.

## SUBCOMMANDS

| Subcommand | Path Arguments | Description |
|---|---|---|
| `list` | none | List dynamic DNS entries |
| `create` | none | Create a dynamic DNS entry |
| `update` | `ID` | Update entry `ID` |
| `delete` | `ID` | Delete entry `ID` |
| `sync` | `ID` | Trigger an immediate sync for entry `ID` |

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

List dynamic DNS entries as JSON:

```sh
sylve ddns list -f json
```

```json
[
  {
    "id": 1,
    "name": "home.example.test",
    "provider": "cloudflare",
    "enabled": true
  }
]
```

Create, update, synchronize, and delete an entry:

```sh
sylve ddns create \
  --set hostname=home.example.test --set provider=cloudflare --set recordType=A \
  --set intervalMinutes=5 --set enabled=true \
  --node node1.example.test \
  --format json

sylve ddns update 2 --set enabled=false -f json
sylve ddns sync 2
sylve ddns delete 2 --yes
```

Preview a create with `--set` fields and show the request:

```sh
sylve ddns create \
  --set hostname=example.example.test --set provider=example-provider \
  --set recordType=A --set intervalMinutes=5 --set enabled=true \
  --dry-run -f json
```

Filter the list, preview an update, then sync and delete:

```sh
sylve ddns list -c id -c hostname -c provider --filter provider=example-provider -l 10
sylve ddns update 2 --set intervalMinutes=10 --set enabled=true --dry-run -f json
sylve ddns sync 2 --dry-run -f json
sylve ddns delete 2 --yes
```

## SEE ALSO

[sylve(1)](../../README.md),
[sylve-mdns(1)](mdns.md),
[sylve-network(1)](network.md),
[sylve-options(7)](../global-options.md)
