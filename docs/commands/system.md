# SYLVE-SYSTEM(1)

## NAME

`sylve-system` — manage host disks, SMART tests, PCI passthrough, files, certificates, settings, and events

## SYNOPSIS

```sh
sylve system COMMAND [ARGS ...]
```

## DESCRIPTION

`sylve system` exposes host-level administration endpoints on a Sylve node,
including disk partitioning, SMART health and test schedules, PCI passthrough
(`ppt`) configuration, `sysctl`/loader tunables, remote file transfers, TLS
certificates, health checks, and server-sent event streams.

Most subcommands are generic API bindings whose request payloads are passed via
`--data` according to `docs/swagger.json`.

## SUBCOMMANDS

| Category | Subcommands |
|---|---|
| Initialization & settings | `init`, `basic-settings` (from `/basic/settings`), `settings` (from `/system/basic-settings`), `settings-pools`, `service SERVICE` |
| Host notes | `notes-list`, `notes-create`, `notes-update ID`, `notes-delete ID`, `notes-bulk-delete` |
| Disks | `disk-list`, `disk-partition-delete PARTITION`, `disk-gpt-init DEVICE`, `disk-gpt-clear DEVICE`, `disk-partition-create DEVICE` |
| SMART | `disk-smart-info`, `disk-smart-start`, `disk-smart-abort`, `disk-smart-schedules`, `disk-smart-schedule-create`, `disk-smart-schedule-update ID`, `disk-smart-schedule-delete ID` |
| PCI passthrough | `pci-list`, `ppt-list`, `ppt-enable`, `ppt-import`, `ppt-prepare`, `ppt-disable ID` |
| Tunables | `tunables`, `tunable-set` |
| Files | `file-list`, `file-create`, `file-copy-move`, `file-delete`, `file-rename`, `file-upload-revert`, `file-upload`, `file-download` |
| Certificates | `cert-list`, `cert-create`, `cert-domain-check`, `cert-update ID`, `cert-delete ID`, `cert-activate ID`, `cert-activate-cancel ID`, `cert-renew ID`, `cert-retry ID`, `cert-archive ID` |
| Health & events | `health-basic`, `health-http`, `events` |

## OPTIONS

### Generic Subcommands

All subcommands except `file-upload`, `file-download`, `cert-archive`, and
`events` accept:

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

### `file-upload`, `file-download`, `cert-archive`, and `events`

- `file-upload`: `--file FILE` (required), `-p, --param KEY=VALUE` (e.g.
  `path=/destination`), `-n, --node NODE`, `-f, --format`.
- `file-download`: `--output, -o PATH` (required), `-p, --param KEY=VALUE` (e.g.
  `id=/absolute/path`), `-n, --node NODE`.
- `cert-archive ID`: `ID` (required), `--output, -o PATH` (required),
  `-p, --param KEY=VALUE`, `-n, --node NODE`.
- `events`: `-p, --param KEY=VALUE`, `-n, --node NODE`. Streams raw server-sent
  events (`SSE`) to standard output until interrupted.

## EXIT STATUS

- `0` — Success.
- `1` — API or file I/O error, or aborted confirmation.
- `2` — Command-line usage error.

## EXAMPLES

List physical disks as JSON:

```sh
sylve system disk-list -f json
```

```json
[
  {
    "name": "ada0",
    "size": 1000204886016,
    "model": "Samsung SSD 870"
  }
]
```

Set a kernel tunable:

```sh
sylve system tunable-set \
  --data '{"name":"kern.maxfiles","value":"200000","comment":"raised for jails"}' \
  --param dryRun=0 \
  --node node1.example.test \
  --format json
```

Create, list, and delete host notes:

```sh
sylve system notes-create --data '{"title":"Maintenance","content":"Disk replacement 22:00"}'
sylve system notes-list -f json
sylve system notes-delete 3 --yes
```

Upload and download host files, export a certificate archive, and stream SSE
events:

```sh
sylve system file-upload --file ./config.json --param path=/root --node node1.example.test -f json
sylve system file-download --param id=/root/config.json --output ./config.json --node node1.example.test
sylve system cert-archive 7 --output ./cert-7.zip
sylve system events --param topic=vm
```

## SEE ALSO

[sylve(1)](../../README.md),
[sylve-node(1)](node.md),
[sylve-zfs(1)](zfs.md),
[sylve-options(7)](../global-options.md)
