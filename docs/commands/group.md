# SYLVE-GROUP(1)

## NAME

`sylve-group` — manage authentication groups and group membership

## SYNOPSIS

```sh
sylve group COMMAND [ARGS ...]
```

## DESCRIPTION

`sylve group` creates, lists, updates membership for, and deletes authentication
groups via generic Sylve API bindings. Note that `group members` replaces the
entire member list rather than appending to it.

## SUBCOMMANDS

| Subcommand | Path Arguments | Description |
|---|---|---|
| `list` | none | List authentication groups |
| `create` | none | Create an authentication group |
| `delete` | `GROUP_ID` | Delete group `GROUP_ID` |
| `members` | `GROUP_ID` | Replace the member list of `GROUP_ID` |

## OPTIONS

All subcommands accept:

- `-d, --data BODY`
  JSON or YAML request body, or `@FILE`.
- `-p, --param KEY=VALUE`
  Query parameter (repeatable).
- `-y, --yes`
  Skip destructive-request confirmation.
- `-n, --node NODE`
  Target node.
- `-f, --format {table,json,yaml,value,csv}`
  Output format (default: `table`).

## EXIT STATUS

- `0` — Success.
- `1` — API error or aborted confirmation.
- `2` — Command-line usage error.

## EXAMPLES

List groups as JSON:

```sh
sylve group list -f json
```

```json
[
  {
    "id": 1,
    "name": "admins",
    "members": [1, 2]
  }
]
```

Create a group, replace its member list, and delete it:

```sh
sylve group create \
  --data '{"name":"operators","description":"VM and jail operators","permissions":["vm:write","jail:write"]}' \
  --param validate=1 \
  --node node1.example.test \
  --format json

sylve group members 2 --data '{"memberIds":[1,3]}' -f json
sylve group delete 2 --yes
```

## SEE ALSO

[sylve(1)](../../README.md),
[sylve-user(1)](user.md),
[sylve-auth(1)](auth.md),
[sylve-options(7)](../global-options.md)
