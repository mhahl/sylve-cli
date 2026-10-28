# sylve system

Manage host disks, SMART tests, PCI passthrough, files, certificates, settings,
services, notes, and health checks.

Most commands are generic API commands. They take a JSON/YAML body with
`--data` instead of typed flags. The Sylve API defines the body shape.

## Synopsis

    sylve system COMMAND [ARGS]...

## Commands

| Area | Commands |
|---|---|
| Initialization and settings | `init`, `basic-settings`, `settings`, `settings-pools`, `service` |
| Host notes | `notes-list`, `notes-create`, `notes-update`, `notes-delete`, `notes-bulk-delete` |
| Disks | `disk-list`, `disk-partition-delete`, `disk-gpt-init`, `disk-gpt-clear`, `disk-partition-create` |
| SMART | `disk-smart-info`, `disk-smart-start`, `disk-smart-abort`, `disk-smart-schedules`, `disk-smart-schedule-create`, `disk-smart-schedule-update`, `disk-smart-schedule-delete` |
| PCI | `pci-list`, `ppt-list`, `ppt-enable`, `ppt-import`, `ppt-prepare`, `ppt-disable` |
| Tunables | `tunables`, `tunable-set` |
| Files | `file-list`, `file-create`, `file-copy-move`, `file-delete`, `file-rename`, `file-upload-revert`, `file-upload`, `file-download` |
| Certificates | `cert-list`, `cert-create`, `cert-domain-check`, `cert-update`, `cert-delete`, `cert-activate`, `cert-activate-cancel`, `cert-renew`, `cert-retry`, `cert-archive` |
| Health | `health-basic`, `health-http` |
| Events | `events` |

## Options

### Generic commands

All commands except `events`, `file-upload`, `file-download`, and
`cert-archive` accept:

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
| `service` | `service` |
| `notes-update`, `notes-delete` | `id` |
| `disk-partition-delete` | `partition` |
| `disk-gpt-init`, `disk-gpt-clear`, `disk-partition-create` | `device` |
| `disk-smart-schedule-update`, `disk-smart-schedule-delete` | `id` |
| `ppt-disable` | `id` |
| `cert-update`, `cert-delete`, `cert-activate`, `cert-activate-cancel`, `cert-renew`, `cert-retry` | `id` |
| all other generic commands | none |

### `file-upload`

- `--file FILE` (required)
  Local file to upload.
- `-p, --param KEY=VALUE`
  Query parameters. Use `path=/destination`.
- `-n, --node NODE`
- `-f, --format {table,json,yaml,value,csv}`

### `file-download`

- `--output, -o PATH` (required)
  Local destination.
- `-p, --param KEY=VALUE`
  Query parameters. Use `id=/absolute/path`.
- `-n, --node NODE`

### `cert-archive`

- `ID` (required)
  Certificate ID.
- `--output, -o PATH` (required)
  Local destination.
- `-p, --param KEY=VALUE`
- `-n, --node NODE`

### `events`

- `-p, --param KEY=VALUE`
  Query parameters.
- `-n, --node NODE`

Streams server-sent events, one line per event.

## Examples

### Minimal

    sylve system disk-list -f json

Output (illustrative):

    [
      {
        "name": "ada0",
        "size": 1000204886016,
        "model": "Samsung SSD 870"
      }
    ]

### With every relevant option

    sylve system tunable-set \
      --data '{"name":"kern.maxfiles","value":"200000","comment":"raised for jails"}' \
      --param dryRun=0 \
      --node node1.example.test \
      --format json

Output (illustrative):

    {
      "name": "kern.maxfiles",
      "value": "200000"
    }

`--param` added the query parameter. `--data` carried the body. `-f json`
changed the output format.

### Host notes

    sylve system notes-create --data '{"title":"Maintenance","content":"Disk replacement 22:00"}'

    sylve system notes-list -f json

    sylve system notes-delete 3 --yes

Output (illustrative):

    {
      "id": 3,
      "title": "Maintenance",
      "content": "Disk replacement 22:00"
    }
    OK

### File upload and download

    sylve system file-upload --file ./config.json --param path=/root --node node1.example.test -f json

Output (illustrative):

    {
      "uploadId": "abc123"
    }

    sylve system file-download --param id=/root/config.json --output ./config.json --node node1.example.test

Output:

    Saved to config.json

### Certificate archive

    sylve system cert-archive 7 --output ./cert-7.zip

Output:

    Saved to cert-7.zip

### Events

    sylve system events --param topic=vm

Output (illustrative, streaming):

    event: vm.state
    data: {"rid":101,"state":"RUNNING"}

## Inputs

- The active context and token.
- `--data` inline JSON/YAML or `@file`.
- `--param` repeated query parameters.
- `--file` and `--output` local paths.

## Outputs

- Tables, JSON, YAML, value, or CSV.
- Binary commands write the destination path and print `Saved to PATH`.
- `events` writes raw SSE lines to stdout until interrupted.
- Exit `0` on success. Exit `1` on API error or aborted confirmation. Exit `2`
  on usage error.
