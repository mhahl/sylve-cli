# SYLVE-GROUP(1)

## NAME

`sylve-group` - manage authentication groups and group membership

## SYNOPSIS

```sh
sylve group COMMAND [ARGS ...]
```

## DESCRIPTION

`sylve group` creates, lists, updates membership for, and deletes authentication
groups via generic Sylve API bindings. `group members` replaces the
entire member list. It does not append.

## SUBCOMMANDS

| Subcommand | Path Arguments | Description |
|---|---|---|
| `list` | none | List authentication groups |
| `create` | none | Create an authentication group |
| `delete` | `GROUP_ID` | Delete group `GROUP_ID` |
| `members` | `GROUP_ID` | Replace the member list of `GROUP_ID` |

## OPTIONS

Write subcommands accept `--data/-d` and `--property/--property/-s`; all subcommands accept:

- `-d, --data BODY`
  JSON or YAML request body, or `@FILE` (write commands).
- `-s, --property, --property KEY=VALUE`
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
  --property name=operators --property members=1,2 \
  --node node1.example.test \
  --format json

sylve group members 2 --property usernames=ops,admin -f json
sylve group delete 2 --yes
```

Preview a create with the required `members` field, then replace a full member list:

```sh
sylve group create --property name=operators --property members=1,2 --dry-run -f json
sylve group members 2 --property usernames=ops,admin --dry-run -f json
```

List a few columns and delete with confirmation skipped:

```sh
sylve group list -c id -c name --sort-column name -l 10
sylve group delete 2 --yes
```

## SEE ALSO

[sylve(1)](../../README.md),
[sylve-user(1)](user.md),
[sylve-auth(1)](auth.md),
[sylve-options(7)](../global-options.md)
