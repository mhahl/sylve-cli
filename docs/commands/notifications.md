# sylve notifications

Manage notification transports, rules, and active notifications.

These are generic API commands. The request body is the Sylve API shape.

## Synopsis

    sylve notifications COMMAND [ARGS]...

## Commands

| Area | Commands |
|---|---|
| Active notifications | `list`, `count`, `dismiss-all`, `dismiss ID` |
| Rules | `rules`, `rules-update`, `rule-create`, `rule-update ID`, `rule-delete ID`, `rules-bulk-delete`, `rules-bulk-update`, `rule-test` |
| Transports | `transports`, `transport-create`, `transport-update ID`, `transport-delete ID`, `transport-test ID` |

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
| `dismiss` | `id` |
| `rule-update`, `rule-delete` | `id` |
| `transport-update`, `transport-delete`, `transport-test` | `id` |
| all other commands | none |

## Examples

### Minimal

    sylve notifications count -f json

Output (illustrative):

    {
      "count": 3
    }

### With every relevant option

    sylve notifications list --param limit=10 --node node1.example.test --format json -c id,title,severity

Output (illustrative):

    [
      {
        "id": 1,
        "title": "Node drain complete",
        "severity": "info"
      }
    ]

`--param` filters the list. `-f json` changes the output format.

### Dismiss

    sylve notifications dismiss 1

    sylve notifications dismiss-all

Output (illustrative):

    OK

### Rules and transports

    sylve notifications rule-create \
      --data '{"name":"node-offline","event":"node.offline","transportId":1,"enabled":true}'

    sylve notifications rule-update 2 --data '{"enabled":false}' -f json

    sylve notifications rule-test 2

    sylve notifications transport-create \
      --data '{"name":"mail","type":"email","config":{"to":"admin@example.test"}}'

    sylve notifications transport-test 1

    sylve notifications transport-delete 1 --yes

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
- IDs from `notifications list`, `rules`, and `transports`.

## Outputs

- Tables, JSON, YAML, value, or CSV.
- Mutating commands print the API result, or `OK` when the response is empty.
- Exit `0` on success. Exit `1` on API error or aborted confirmation. Exit `2`
  on usage error.
