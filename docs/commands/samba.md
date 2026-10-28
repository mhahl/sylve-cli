# SYLVE-SAMBA(1)

## NAME

`sylve-samba` — manage Samba global configuration, shares, and audit logs

## SYNOPSIS

```sh
sylve samba COMMAND [ARGS ...]
```

## DESCRIPTION

`sylve samba` configures the host Samba server and SMB file shares via generic
Sylve API bindings. Request payloads are supplied with `--data` in JSON or YAML
format.

## SUBCOMMANDS

| Subcommand | Path Arguments | Description |
|---|---|---|
| `config` | none | Show global Samba configuration |
| `config-set` | none | Update global Samba configuration |
| `shares` | none | List configured SMB shares |
| `share-create` | none | Create a share |
| `share-update` | `ID` | Update share `ID` |
| `share-delete` | `ID` | Delete share `ID` |
| `share-enable` | `ID` | Enable or disable share `ID` |
| `audit-logs` | none | Display Samba audit logs |

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

List shares as JSON:

```sh
sylve samba shares -f json
```

```json
[
  {
    "id": 1,
    "name": "media",
    "path": "/zroot/media",
    "enabled": true
  }
]
```

Create, update, disable, and delete a share:

```sh
sylve samba share-create \
  --data '{"name":"media","path":"/zroot/media","readOnly":false,"guestOk":true}' \
  --param validate=1 \
  --node node1.example.test \
  --format json

sylve samba share-update 2 --data '{"readOnly":true}' -f json
sylve samba share-enable 2 --data '{"enabled":false}' -f json
sylve samba share-delete 2 --yes
```

Inspect and update global Samba settings and read audit logs:

```sh
sylve samba config -f json
sylve samba config-set --data '{"workgroup":"WORKGROUP","serverString":"Sylve"}' -f json
sylve samba audit-logs --param limit=20
```

## SEE ALSO

[sylve(1)](../../README.md),
[sylve-iscsi(1)](iscsi.md),
[sylve-zfs(1)](zfs.md),
[sylve-options(7)](../global-options.md)
