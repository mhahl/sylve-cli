# sylve mdns

Manage mDNS configuration and records.

These are generic API commands. The request body is the Sylve API shape.

## Synopsis

    sylve mdns COMMAND [ARGS]...

## Commands

| Command | Purpose |
|---|---|
| `config` | Show mDNS settings |
| `config-set` | Update mDNS settings |
| `records` | List records |
| `record-create` | Create a record |
| `record-update ID` | Update a record |
| `record-delete ID` | Delete a record |

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
| `record-update`, `record-delete` | `id` |
| all other commands | none |

## Examples

### Minimal

    sylve mdns records -f json

Output (illustrative):

    [
      {
        "id": 1,
        "name": "sylve.local",
        "type": "A",
        "value": "10.0.0.11"
      }
    ]

### With every relevant option

    sylve mdns record-create \
      --data '{"name":"sylve.local","type":"A","value":"10.0.0.11","ttl":300}' \
      --param validate=1 \
      --node node1.example.test \
      --format json

Output (illustrative):

    {
      "id": 2,
      "name": "sylve.local"
    }

### Update and delete

    sylve mdns record-update 2 --data '{"ttl":600}' -f json

    sylve mdns record-delete 2 --yes

Output (illustrative):

    {
      "id": 2,
      "ttl": 600
    }
    OK

### Configuration

    sylve mdns config -f json

    sylve mdns config-set --data '{"enabled":true,"interfaces":["em0"]}' -f json

## Inputs

- The active context and token.
- `--data` inline JSON/YAML or `@file`.
- Record IDs from `mdns records`.

## Outputs

- Tables, JSON, YAML, value, or CSV.
- Mutating commands print the API result, or `OK` when the response is empty.
- Exit `0` on success. Exit `1` on API error or aborted confirmation. Exit `2`
  on usage error.
