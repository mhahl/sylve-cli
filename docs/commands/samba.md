# sylve samba

Manage Samba global configuration and shares.

These are generic API commands. The request body is the Sylve API shape.

## Synopsis

    sylve samba COMMAND [ARGS]...

## Commands

| Command | Purpose |
|---|---|
| `config` | Show global configuration |
| `config-set` | Update global configuration |
| `shares` | List shares |
| `share-create` | Create a share |
| `share-update ID` | Update a share |
| `share-delete ID` | Delete a share |
| `share-enable ID` | Enable or disable a share |
| `audit-logs` | Show audit logs |

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
| `share-update`, `share-delete`, `share-enable` | `id` |
| all other commands | none |

## Examples

### Minimal

    sylve samba shares -f json

Output (illustrative):

    [
      {
        "id": 1,
        "name": "media",
        "path": "/zroot/media",
        "enabled": true
      }
    ]

### With every relevant option

    sylve samba share-create \
      --data '{"name":"media","path":"/zroot/media","readOnly":false,"guestOk":true}' \
      --param validate=1 \
      --node node1.example.test \
      --format json

Output (illustrative):

    {
      "id": 2,
      "name": "media"
    }

### Update, enable, delete

    sylve samba share-update 2 --data '{"readOnly":true}' -f json

    sylve samba share-enable 2 --data '{"enabled":false}' -f json

    sylve samba share-delete 2 --yes

Output (illustrative):

    {
      "id": 2,
      "enabled": false
    }
    OK

`--param` adds query parameters. `--data` carries the body. `-y` skips the
confirmation for the delete.

### Global configuration

    sylve samba config -f json

    sylve samba config-set --data '{"workgroup":"WORKGROUP","serverString":"Sylve"}' -f json

    sylve samba audit-logs --param limit=20

## Inputs

- The active context and token.
- `--data` inline JSON/YAML or `@file`.
- Path IDs from `samba shares`.

## Outputs

- Tables, JSON, YAML, value, or CSV.
- Mutating commands print the API result, or `OK` when the response is empty.
- Exit `0` on success. Exit `1` on API error or aborted confirmation. Exit `2`
  on usage error.
