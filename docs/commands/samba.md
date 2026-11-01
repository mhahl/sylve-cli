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
  --set name=media --set dataset=zroot/media --set enabled=true \
  --node node1.example.test \
  --format json

sylve samba share-update 2 --set guest=true -f json
sylve samba share-enable 2 --set enabled=false -f json
sylve samba share-delete 2 --yes
```

Inspect and update global Samba settings and read audit logs:

```sh
sylve samba config -f json
sylve samba config-set --set workgroup=WORKGROUP --set serverString=Sylve -f json
sylve samba audit-logs --param size=20
```

Preview a global config change and a share create with `--set`:

```sh
sylve samba config-set --set workgroup=EXAMPLE --set serverString=Example --dry-run -f json
sylve samba share-create \
  --set name=example-media --set dataset=tank/media --set enabled=true \
  --dry-run -f json
```

Update, disable, and delete a share, and narrow list output:

```sh
sylve samba share-update 2 --set enabled=true --set timeMachine=false --dry-run -f json
sylve samba share-enable 2 --set enabled=false --dry-run -f json
sylve samba shares -c id -c name -c dataset --sort-column name -l 10
sylve samba audit-logs -c id -c share -l 5
sylve samba share-delete 2 --yes
```

## SEE ALSO

[sylve(1)](../../README.md),
[sylve-iscsi(1)](iscsi.md),
[sylve-zfs(1)](zfs.md),
[sylve-options(7)](../global-options.md)
