# SYLVE-USER(1)

## NAME

`sylve-user` — manage local, PAM, and imported users, plus passkeys

## SYNOPSIS

```sh
sylve user COMMAND [ARGS ...]
```

## DESCRIPTION

`sylve user` manages local Sylve accounts, PAM accounts, imported host Unix
accounts, and user WebAuthn passkeys via generic Sylve API bindings.

## SUBCOMMANDS

| Subcommand | Path Arguments | Description |
|---|---|---|
| `list` | none | List users |
| `create` | none | Create a local user |
| `capabilities` | none | Show user-management capabilities |
| `import` | none | Import an existing host Unix user |
| `importable` | none | List importable host Unix users |
| `pam-create` | none | Register a PAM user |
| `next-uid` | none | Show the next available Unix UID |
| `update` | `USER_ID` | Update user `USER_ID` |
| `delete` | `USER_ID` | Delete user `USER_ID` |
| `passkeys` | `USER_ID` | List passkeys for user `USER_ID` |
| `passkey-delete` | `USER_ID CREDENTIAL_ID` | Delete passkey `CREDENTIAL_ID` for `USER_ID` |

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

- `0` — Success.
- `1` — API error or aborted confirmation.
- `2` — Command-line usage error.

## EXAMPLES

List users and create a local account (the password stays out of shell
history in a file):

```json
{
  "username": "ops",
  "password": "secret",
  "admin": true,
  "uid": 1001,
  "fullName": "Operations"
}
```

```sh
sylve user list -f json
sylve user create \
  --data @ops-user.json \
  --node node1.example.test \
  --node node1.example.test \
  --format json
```

Import a Unix user, create a PAM account, and query the next UID:

```sh
sylve user importable -f json
sylve user import --set username=mark --set admin=false
sylve user pam-create --set username=ops-pam
sylve user next-uid
```

Update a user, manage passkeys, and delete an account:

```sh
sylve user update 2 --set fullName=Operations -f json
sylve user passkeys 2
sylve user passkey-delete 2 cred-abc
sylve user delete 2 --yes
```

Create a local account with the password kept in a file (never inline):

```json
{
  "username": "ops",
  "password": "secret",
  "admin": false,
  "fullName": "Operations"
}
```

```sh
sylve user create --data @ops-user.json --dry-run -f json
sylve user list -c id -c username -c admin --sort-column username -l 10
```

Preview an update, import a host user, and register a PAM account:

```sh
sylve user update 2 --set fullName=Operations --set admin=false --dry-run -f json
sylve user import --set username=ops --set admin=false --dry-run -f json
sylve user pam-create \
  --set username=ops-pam --set admin=false --set uid=1001 --set homeDirPerms=755 \
  --dry-run -f json
sylve user importable -c username -c uid --filter username=ops -l 5
```

List passkeys for a user and delete one with confirmation skipped:

```sh
sylve user passkeys 2 -c credentialId -c label -l 10
sylve user passkey-delete 2 cred-abc --yes --dry-run -f json
sylve user delete 2 --yes
```

## SEE ALSO

[sylve(1)](../../README.md),
[sylve-group(1)](group.md),
[sylve-auth(1)](auth.md),
[sylve-login(1)](login.md),
[sylve-options(7)](../global-options.md)
