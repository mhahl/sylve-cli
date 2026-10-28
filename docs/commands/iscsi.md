# sylve iscsi

Manage iSCSI initiators, targets, LUNs, and portals.

These are generic API commands. The request body is the Sylve API shape.

## Synopsis

    sylve iscsi COMMAND [ARGS]...

## Commands

| Area | Commands |
|---|---|
| Initiators | `initiators`, `initiator-create`, `initiator-update ID`, `initiator-delete ID`, `initiator-connect ID` |
| Status | `status`, `sessions` |
| Targets | `targets`, `target-create`, `target-update TARGETID`, `target-delete TARGETID` |
| LUNs | `lun-add TARGETID`, `lun-remove TARGETID LUNID` |
| Portals | `portal-add TARGETID`, `portal-remove TARGETID PORTALID` |

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
| `initiator-update`, `initiator-delete`, `initiator-connect` | `id` |
| `target-update`, `target-delete` | `targetId` |
| `lun-add` | `targetId` |
| `lun-remove` | `targetId lunId` |
| `portal-add` | `targetId` |
| `portal-remove` | `targetId portalId` |
| all other commands | none |

## Examples

### Minimal

    sylve iscsi targets -f json

Output (illustrative):

    [
      {
        "id": 1,
        "name": "iqn.2026-10.test.sylve:storage",
        "enabled": true
      }
    ]

### With every relevant option

    sylve iscsi target-create \
      --data '{"name":"iqn.2026-10.test.sylve:storage","alias":"storage","enabled":true}' \
      --param validate=1 \
      --node node1.example.test \
      --format json

Output (illustrative):

    {
      "id": 2,
      "name": "iqn.2026-10.test.sylve:storage"
    }

### LUN and portal

    sylve iscsi lun-add 2 --data '{"path":"/dev/zvol/zroot/iscsi/disk0","lunId":0}'

    sylve iscsi portal-add 2 --data '{"address":"10.0.0.11","port":3260}'

    sylve iscsi lun-remove 2 0

    sylve iscsi portal-remove 2 1 --yes

Output (illustrative):

    OK

`--data` carries the body. `-y` skips the delete confirmation. `--param`
adds query parameters.

### Initiator

    sylve iscsi initiator-create --data '{"name":"iqn.2026-10.test.client:web-01"}'

    sylve iscsi initiator-connect 1

    sylve iscsi status -f json

## Inputs

- The active context and token.
- `--data` inline JSON/YAML or `@file`.
- Target, LUN, and portal IDs from the list commands.

## Outputs

- Tables, JSON, YAML, value, or CSV.
- Mutating commands print the API result, or `OK` when the response is empty.
- Exit `0` on success. Exit `1` on API error or aborted confirmation. Exit `2`
  on usage error.
