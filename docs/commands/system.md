# SYLVE-SYSTEM(1)

## NAME

`sylve-system` - manage host disks, SMART tests, PCI passthrough, files, certificates, settings, and events

## SYNOPSIS

```sh
sylve system COMMAND [ARGS ...]
```

## DESCRIPTION

`sylve system` exposes host-level administration endpoints on a Sylve node,
including disk partitioning, SMART health and test schedules, PCI passthrough
(`ppt`) configuration, `sysctl`/loader tunables, remote file transfers, TLS
certificates, health checks, and server-sent event streams.

Most subcommands are generic API bindings that take their request payloads from
`--data` according to `docs/swagger.json`.

## SUBCOMMANDS

| Category | Subcommands |
|---|---|
| Initialization & settings | `init`, `init-host-state`, `basic-settings` (from `/basic/settings`), `settings` (from `/system/basic-settings`), `settings-pools`, `service SERVICE` |
| Host notes | `note list`, `note show ID`, `note create`, `note set ID`, `note delete ID`, `note bulk-delete` |
| Disks | `disk list`, `disk partition-delete PARTITION`, `disk gpt-init DEVICE`, `disk gpt-clear DEVICE`, `disk partition-create DEVICE` |
| SMART | `disk smart-info`, `disk smart-start`, `disk smart-abort`, `disk smart-schedules`, `disk smart-schedule-create`, `disk smart-schedule-set ID`, `disk smart-schedule-delete ID` |
| PCI passthrough | `pci-list`, `ppt list`, `ppt enable`, `ppt import`, `ppt prepare`, `ppt disable ID` |
| Tunables | `tunable list`, `tunable set` |
| Files | `file list`, `file create`, `file copy-move`, `file delete`, `file rename`, `file upload-revert`, `file upload`, `file download` |
| Certificates | `cert list`, `cert create`, `cert domain-check`, `cert set ID`, `cert delete ID`, `cert activate ID`, `cert activate-cancel ID`, `cert renew ID`, `cert retry ID`, `cert archive ID` |
| Health, events & terminal | `health-basic`, `health-http`, `events`, `terminal` |

## OPTIONS

### Generic Subcommands

All write subcommands accept `--data/-d` and `--property/--property/-s`, and all generic subcommands except `file upload`, `file download`, `cert archive`, `events`, `terminal`, and `note show` accept:

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

### `file upload`, `file download`, `cert archive`, `events`, `terminal`, and `note show`

- `file upload`: `--file FILE` (required), `-p, --param KEY=VALUE` (e.g.
  `path=/destination`), `-n, --node NODE`, `-f, --format`.
- `file download`: `--output, -o PATH` (required), `-p, --param KEY=VALUE` (e.g.
  `id=/absolute/path`), `-n, --node NODE`.
- `cert archive ID`: `ID` (required), `--output, -o PATH` (required),
  `-p, --param KEY=VALUE`, `-n, --node NODE`.
- `events`: `--lines, -l N` (stop after `N` non-empty lines),
  `--reconnect / --no-reconnect` (default: `--reconnect`),
  `-p, --param KEY=VALUE`, `-n, --node NODE`. Mints a short-lived `sse_token`
  via `POST /auth/sse-tokens` and streams `/events/stream`.
- `terminal`: `--kill-on-exit / --keep-alive` (default: `--kill-on-exit`),
  `-n, --node NODE`. Opens an interactive host shell over WebSocket. Press
  `Enter`, then type `~.` to detach.
- `note show ID`: `ID` (required), `-n, --node NODE`, `-f, --format`,
  `-c, --column`. Displays one host note without truncation.

## EXIT STATUS

- `0`: Success.
- `1`: API or file I/O error, or aborted confirmation.
- `2`: Command-line usage error.

## EXAMPLES

List physical disks as JSON:

```sh
sylve system disk list -f json
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
sylve system tunable set \
  --property name=kern.maxfiles --property value=200000 \
  --node node1.example.test \
  --format json
```

Create, list, show, and delete host notes:

```sh
sylve system note create --property title=Maintenance --property 'content=Disk replacement 22:00'
sylve system note list -f json
sylve system note show 3 -f json
sylve system note delete 3 --yes
```

Upload and download host files, export a certificate archive, and stream SSE
events:

```sh
sylve system file upload --file ./config.json --param path=/root --node node1.example.test -f json
sylve system file download --param id=/root/config.json --output ./config.json --node node1.example.test
sylve system cert archive 7 --output ./cert-7.zip
sylve system events --lines 20
sylve system terminal --node node1.example.test
```

Preview a tunable change before sending it:

```sh
sylve system tunable set \
  --property name=kern.maxfiles --property value=200000 \
  --dry-run -f json
```

```json
{
  "method": "PUT",
  "path": "/system/tunables",
  "params": null,
  "body": {
    "name": "kern.maxfiles",
    "value": "200000"
  }
}
```

Narrow list output with selection flags (reads only):

```sh
sylve system tunable list -c Name -c Value --filter name=kern --sort-column name -l 5
sylve system disk list -c Name -c Size -c Model --sort-column name -l 5
sylve system cert list --filter name=web --sort-column name -l 5
sylve system note list -c ID -c Title --filter title=Maintenance -l 5
```

Schedule SMART self-tests, then adjust and remove the schedule:

```sh
sylve system disk smart-schedule-create \
  --property device=ada0 --property testType=long --property 'cronExpr=0 2 * * 0' \
  --dry-run -f json
sylve system disk smart-schedule-set 1 \
  --property device=ada0 --property testType=short --property 'cronExpr=0 3 * * 0' \
  --dry-run -f json
sylve system disk smart-start --property device=ada0 --property testType=short --dry-run -f json
sylve system disk smart-schedule-delete 1 --yes --dry-run -f json
```

```json
{
  "method": "POST",
  "path": "/disk/smart/self-test/schedules",
  "params": null,
  "body": {
    "device": "ada0",
    "testType": "long",
    "cronExpr": "0 2 * * 0"
  }
}
```

Enable a service, create a file, and delete files with confirmation skipped:

```sh
sylve system service sshd --property enabled=true --dry-run -f json
sylve system file create --property path=/root --property name=notes.txt --property isFolder=false --dry-run -f json
sylve system file delete --property paths=/root/old.iso --yes --dry-run -f json
```

```json
{
  "method": "PATCH",
  "path": "/system/basic-settings/services/sshd",
  "params": null,
  "body": {
    "enabled": true
  }
}
```

Full certificate lifecycle with dry-run previews and a confirmation-safe delete:

```sh
sylve system cert create --property name=web --property domain=example.test --dry-run -f json
sylve system cert set 7 --property name=web-renamed --dry-run -f json
sylve system cert activate 7 --dry-run -f json
sylve system cert renew 7 --dry-run -f json
sylve system cert delete 7 --yes --dry-run -f json
```

```json
{
  "method": "POST",
  "path": "/certificates",
  "params": null,
  "body": {
    "name": "web",
    "domain": "example.test"
  }
}
```

Update a host note and delete it without a prompt:

```sh
sylve system note create --property title=Maintenance --property 'content=Disk replacement 22:00' --dry-run -f json
sylve system note set 3 --property title=Maintenance --property content=Done --dry-run -f json
sylve system note delete 3 --yes --dry-run -f json
```

## SEE ALSO

[sylve(1)](../../README.md),
[sylve-node(1)](node.md),
[sylve-zfs(1)](zfs.md),
[sylve-options(7)](../global-options.md)
