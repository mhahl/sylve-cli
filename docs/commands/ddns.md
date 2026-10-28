# sylve ddns

Manage dynamic DNS entries.

These are generic API commands. The request body is the Sylve API shape.

## Synopsis

    sylve ddns COMMAND [ARGS]...

## Commands

| Command | Purpose |
|---|---|
| `list` | List entries |
| `create` | Create an entry |
| `update ID` | Update an entry |
| `delete ID` | Delete an entry |
| `sync ID` | Synchronize an entry now |

## Options

All commands accept:

- `-d, --data BODY`
  JSON or YAML request body, or `@FILE`.
- `-p, --param KEY=VALUE`
  Query parameter. Repeatable.
- `-y, --yes`
  Skip the destructive-request confirmation.
- `-n, --node NODE`
  Target node.
- `-f, --format {table,json,yaml,value,csv}`
  Output format. Default: `table`.

Path arguments:

| Command | Arguments |
|---|---|
| `update`, `delete`, `sync` | `id` |
| `list`, `create` | none |

## Examples

### Minimal

    sylve ddns list -f json

Output (illustrative):

    [
      {
        "id": 1,
        "name": "home.example.test",
        "provider": "cloudflare",
        "enabled": true
      }
    ]

### With every relevant option

    sylve ddns create \
      --data '{"name":"home.example.test","provider":"cloudflare","zone":"example.test","recordType":"A","proxied":false}' \
      --param validate=1 \
      --node node1.example.test \
      --format json

Output (illustrative):

    {
      "id": 2,
      "name": "home.example.test"
    }

### Update, sync, delete

    sylve ddns update 2 --data '{"enabled":false}' -f json

    sylve ddns sync 2

    sylve ddns delete 2 --yes

Output (illustrative):

    {
      "id": 2,
      "enabled": false
    }
    OK

`--data` carries the body. `--param` adds query parameters. `-y` skips the
delete confirmation.

## Inputs

- The active context and token.
- `--data` inline JSON/YAML or `@file`.
- Entry IDs from `ddns list`.

## Outputs

- Tables, JSON, YAML, value, or CSV.
- Mutating commands print the API result, or `OK` when the response is empty.
- Exit `0` on success. Exit `1` on API error or aborted confirmation. Exit `2`
  on usage error.
