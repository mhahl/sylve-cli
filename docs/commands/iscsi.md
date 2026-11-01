# SYLVE-ISCSI(1)

## NAME

`sylve-iscsi` — manage iSCSI initiators, targets, LUNs, and portals

## SYNOPSIS

```sh
sylve iscsi COMMAND [ARGS ...]
```

## DESCRIPTION

`sylve iscsi` manages iSCSI initiators, targets, LUNs, portals, and active
sessions via generic Sylve API bindings. Request payloads are supplied with
`--data` in JSON or YAML format.

## SUBCOMMANDS

| Subcommand | Path Arguments | Description |
|---|---|---|
| `initiators` | none | List iSCSI initiators |
| `initiator-create` | none | Create an initiator |
| `initiator-update` | `ID` | Update initiator `ID` |
| `initiator-delete` | `ID` | Delete initiator `ID` |
| `initiator-connect` | `ID` | Connect initiator `ID` |
| `status` | none | Show iSCSI subsystem status |
| `sessions` | none | List active iSCSI sessions |
| `targets` | none | List iSCSI targets |
| `target-create` | none | Create a target |
| `target-update` | `TARGET_ID` | Update target `TARGET_ID` |
| `target-delete` | `TARGET_ID` | Delete target `TARGET_ID` |
| `lun-add` | `TARGET_ID` | Add a LUN to `TARGET_ID` |
| `lun-remove` | `TARGET_ID LUN_ID` | Remove LUN `LUN_ID` from `TARGET_ID` |
| `portal-add` | `TARGET_ID` | Add a portal to `TARGET_ID` |
| `portal-remove` | `TARGET_ID PORTAL_ID` | Remove portal `PORTAL_ID` from `TARGET_ID` |

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

List iSCSI targets as JSON:

```sh
sylve iscsi targets -f json
```

```json
[
  {
    "id": 1,
    "name": "iqn.2026-10.test.sylve:storage",
    "enabled": true
  }
]
```

Create a target, attach and remove a LUN and portal:

```sh
sylve iscsi target-create \
  --set targetName=iqn.2026-10.test.sylve:storage --set alias=storage \
  --node node1.example.test \
  --format json

sylve iscsi lun-add 2 --set zvol=zroot/iscsi/disk0 --set lunNumber=0
sylve iscsi portal-add 2 --set address=10.0.0.11 --set port=3260
sylve iscsi lun-remove 2 0
sylve iscsi portal-remove 2 1 --yes
```

Create and connect an initiator and check subsystem status:

```sh
sylve iscsi initiator-create --set nickname=web-01 --set targetName=iqn.2026-10.test.sylve:storage --set targetAddress=10.0.0.11
sylve iscsi initiator-connect 1
sylve iscsi status -f json
```

Preview target and initiator creates and updates with `--set`:

```sh
sylve iscsi target-create \
  --set targetName=iqn.2026-11.example.test:storage --set alias=example-storage \
  --dry-run -f json
sylve iscsi target-update 1 --set alias=example-storage-v2 --dry-run -f json
sylve iscsi initiator-create \
  --set nickname=example-web --set targetName=iqn.2026-11.example.test:storage \
  --set targetAddress=10.0.0.11 --dry-run -f json
sylve iscsi initiator-update 1 --set nickname=example-web-v2 --dry-run -f json
```

Wire up a LUN and portal, narrow list output, and clean up:

```sh
sylve iscsi lun-add 1 --set zvol=tank/iscsi/disk0 --set lunNumber=0 --dry-run -f json
sylve iscsi portal-add 1 --set address=10.0.0.11 --set port=3260 --dry-run -f json
sylve iscsi targets -c id -c targetName --sort-column targetName -l 10
sylve iscsi sessions -c id -c targetName -l 5
sylve iscsi initiator-connect 1 --dry-run -f json
sylve iscsi lun-remove 1 0 --yes
sylve iscsi portal-remove 1 1 --yes
sylve iscsi target-delete 1 --yes
sylve iscsi initiator-delete 1 --yes
```

## SEE ALSO

[sylve(1)](../../README.md),
[sylve-samba(1)](samba.md),
[sylve-zfs(1)](zfs.md),
[sylve-options(7)](../global-options.md)
