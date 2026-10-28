# sylve group

Manage authentication groups and membership.

These are generic API commands. The request body is the Sylve API shape.

## Synopsis

    sylve group COMMAND [ARGS]...

## Commands

| Command | Purpose |
|---|---|
| `list` | List groups |
| `create` | Create a group |
| `delete GROUPID` | Delete a group |
| `members GROUPID` | Replace group members |

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
| `delete`, `members` | `groupId` |
| `list`, `create` | none |

`members` replaces the full member list. It does not append.

## Examples

### Minimal

    sylve group list -f json

Output (illustrative):

    [
      {
        "id": 1,
        "name": "admins",
        "members": [1, 2]
      }
    ]

### With every relevant option

    sylve group create \
      --data '{"name":"operators","description":"VM and jail operators","permissions":["vm:write","jail:write"]}' \
      --param validate=1 \
      --node node1.example.test \
      --format json

Output (illustrative):

    {
      "id": 2,
      "name": "operators"
    }

### Replace members and delete

    sylve group members 2 --data '{"memberIds":[1,3]}' -f json

    sylve group delete 2 --yes

Output (illustrative):

    {
      "id": 2,
      "members": [1, 3]
    }
    OK

`--data` carries the replacement member list. `--param` adds query
parameters. `-y` skips the delete confirmation.

## Inputs

- The active context and token.
- `--data` inline JSON/YAML or `@file`.
- Group IDs from `group list`.

## Outputs

- Tables, JSON, YAML, value, or CSV.
- Mutating commands print the API result, or `OK` when the response is empty.
- Exit `0` on success. Exit `1` on API error or aborted confirmation. Exit `2`
  on usage error.
