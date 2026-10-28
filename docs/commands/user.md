# sylve user

Manage local, PAM, and imported users, plus passkeys.

These are generic API commands. The request body is the Sylve API shape.

## Synopsis

    sylve user COMMAND [ARGS]...

## Commands

| Command | Purpose |
|---|---|
| `list` | List users |
| `create` | Create a local user |
| `capabilities` | Show user-management capabilities |
| `import` | Import a Unix user |
| `importable` | List importable Unix users |
| `pam-create` | Create a PAM user |
| `next-uid` | Show the next Unix UID |
| `update USERID` | Update a user |
| `delete USERID` | Delete a user |
| `passkeys USERID` | List user passkeys |
| `passkey-delete USERID CREDENTIALID` | Delete a passkey |

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
| `update`, `delete`, `passkeys` | `userId` |
| `passkey-delete` | `userId credentialId` |
| all other commands | none |

## Examples

### Minimal

    sylve user list -f json

Output (illustrative):

    [
      {
        "id": 1,
        "username": "admin",
        "authType": "sylve",
        "uid": 1000
      }
    ]

### With every relevant option

    sylve user create \
      --data '{"username":"ops","password":"secret","authType":"sylve","uid":1001,"groups":[1]}' \
      --param sendWelcome=0 \
      --node node1.example.test \
      --format json

Output (illustrative):

    {
      "id": 2,
      "username": "ops",
      "uid": 1001
    }

### Import and PAM

    sylve user importable -f json

    sylve user import --data '{"username":"mark","uid":1000}'

    sylve user pam-create --data '{"username":"ops-pam"}'

    sylve user next-uid

Output (illustrative):

    {
      "uid": 1002
    }

### Update, passkeys, delete

    sylve user update 2 --data '{"fullName":"Operations"}' -f json

    sylve user passkeys 2

    sylve user passkey-delete 2 cred-abc

    sylve user delete 2 --yes

Output (illustrative):

    {
      "id": 2,
      "fullName": "Operations"
    }
    OK

`--data` carries the body. `--param` adds query parameters. `-y` skips the
delete confirmation.

## Inputs

- The active context and token.
- `--data` inline JSON/YAML or `@file`.
- User and credential IDs from the list commands.

## Outputs

- Tables, JSON, YAML, value, or CSV.
- Mutating commands print the API result, or `OK` when the response is empty.
- Exit `0` on success. Exit `1` on API error or aborted confirmation. Exit `2`
  on usage error.
