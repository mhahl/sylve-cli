# SYLVE-OPTIONS(7)

## NAME

`sylve-options` - global options, output formatting, environment variables, configuration file, and exit status

## SYNOPSIS

```sh
sylve [GLOBAL_OPTIONS] COMMAND [SUBCOMMAND] [COMMAND_OPTIONS] [ARGS ...]
```

## DESCRIPTION

`sylve` accepts two sets of common options:

1. **Global options**, placed before the top-level `COMMAND`:
   ```sh
   sylve --context prod --node node2 vm list
   ```
2. **Command and output options**, placed after the subcommand:
   ```sh
   sylve vm list --format json --column RID,Name,State
   ```

## GLOBAL OPTIONS

- `--config FILE`
  Configuration file path. Defaults to `$SYLVE_CONFIG`, then
  `$XDG_CONFIG_HOME/sylve/config.yaml`, then `~/.config/sylve/config.yaml`.
- `--context NAME`
  Named login context to use. Overrides `current_context` in the configuration
  file. Environment: `SYLVE_CONTEXT`.
- `-n, --node NODE`
  Target cluster node hostname or UUID. Subcommands that also define `--node`
  use their own value when supplied. Environment: `SYLVE_NODE`.
- `-k, --insecure`
  Skip TLS certificate verification. Environment: `SYLVE_INSECURE`.
- `--timeout SECONDS`
  HTTP request timeout in seconds (default: `30.0`).
- `--max-width COLUMNS`
  Maximum rendered table width in columns (default: terminal width; minimum: `1`).
- `--no-truncate`
  Wrap long table cells instead of truncating them.
- `-V, --version`
  Print the CLI version and exit.
- `-h, --help`
  Show command help and exit.

## OUTPUT AND COMMON OPTIONS

Commands that print records or mutate resources share the following flags where
applicable:

- `-f, --format {table,json,yaml,value,csv}`
  Output format (default: `table`).

  | Format | Description |
  |---|---|
  | `table` | ASCII/Unicode table rendered with Rich |
  | `json` | Indented JSON |
  | `yaml` | YAML document |
  | `value` | Space-separated values without headers, one row per line |
  | `csv` | Comma-separated values with a header row |

- `-c, --column NAME`
  Select and order output columns. Repeatable or comma-separated. Matches
  column headers or raw field keys ignoring case:
  ```sh
  sylve vm list -c RID,Name,State
  sylve vm list -c RID -c Name
  ```
- `--sort-column NAME`
  Sort table rows by column header or field key.
- `--filter COLUMN=VALUE`
  Keep only rows whose column contains `VALUE` (case-insensitive substring),
  or bare text matched against any field. Repeatable:
  ```sh
  sylve vm list --filter State=running --filter node1
  ```
- `-l, --limit N`
  Show at most `N` rows after filtering.
- `--long`
  Include lower-priority columns in table output. The extra columns vary by
  command.
- `-n, --node NODE`
  Restrict a list command to one cluster node, or select the target node for a
  single-resource command.
- `-w, --wait / --no-wait`
  Wait for an asynchronous task to finish before returning. Default behaviour
  varies by command.
- `-y, --yes`
  Skip interactive confirmation prompts on a terminal.

## GENERIC API OPTIONS

Generic API commands accept `--data`, `--set`, `--param`, and `--dry-run`.
Run one with nothing supplied and it prints its
own `--help` instead of erroring. A wrong or missing path argument with
anything else supplied is a usage error (exit `2`).

- `-d, --data BODY`
  Base JSON or YAML request body, or `@FILE` to read the body from disk.
- `-s, --set KEY=VALUE`
  Set one body field (repeatable). Dotted keys address nested objects and the
  CLI parses values as YAML, so common updates need no JSON.
  Every command's `--help` lists its settable fields with types and required
  markers, so key names are visible:
  ```sh
  sylve system tunable-set --help    # Settable body fields: name, value
  sylve system tunable-set --set name=vfs.zfs.prefetch_disable --set value=0
  sylve vm hardware-cpu 101 --set cpuSockets=1 --set cpuCores=4
  ```
  `--set` merges over `--data` (nested objects merge key by key) and is the
  preferred way to send small updates. Quote values the server expects as
  strings: `--set value='"200000"'`.

  Complex values go in one `--set` as YAML (single-quote it so the shell
  leaves brackets alone). Dotted keys descend into objects; arrays and
  objects given wholesale replace the field instead of merging into it:
  ```sh
  sylve vm hardware-cpu 101 --set 'cpuPinning=[{cores: [0, 1], socket: 0}]'
  sylve notifications transport-create --set name=mail --set type=email \
    --set email.smtpHost=mail.example.test --set email.smtpPort=587
  ```
  If quoting gets awkward, put the body in a file and keep `--set` for the
  small tweaks: `--data @body.yaml --set enabled=true`.
- `--dry-run`
  Print the request (`method`, `path`, `params`, `body`) without sending it.
  Useful with `-f json` to preview the request that `--set` and `--data` build.
- `-p, --param KEY=VALUE`
  Query string parameter. Repeatable; the CLI parses each value as a YAML scalar.
- `-c, --column`, `--sort-column`, `--filter`, `-l, --limit`
  Output selection on reads (see above).

`@FILE` keeps long bodies out of shell history and lets you review them like
any other configuration:

```yaml
# tunable.yaml
name: vfs.zfs.prefetch_disable
value: "0"
```

```sh
sylve system tunable-set --data @tunable.yaml
```

`--data` sends the body verbatim; `--set` overrides individual fields on top
of it. `vm create --file` and `jail create --file` are different: they read a
create configuration that the CLI normalizes first (defaults, aliases,
`2G`-style sizes). Two names for two behaviours. `-f` always means `--format`,
never "file".

## ENVIRONMENT

| Variable | Description |
|---|---|
| `SYLVE_CONFIG` | Configuration file path |
| `SYLVE_CONTEXT` | Active context name |
| `SYLVE_SERVER` | Server URL override |
| `SYLVE_TOKEN` | Bearer token override |
| `SYLVE_NODE` | Default target node hostname or UUID |
| `SYLVE_INSECURE` | `1`, `true`, or `yes` disables TLS certificate verification |
| `XDG_CONFIG_HOME` | Base directory for the default configuration file |

Setting `SYLVE_SERVER` and `SYLVE_TOKEN` allows stateless operation without a
saved configuration file:

```sh
export SYLVE_SERVER=https://sylve.example.test
export SYLVE_TOKEN=eyJhbGciOi...
sylve node list
```

## FILES

The CLI stores `~/.config/sylve/config.yaml` as YAML with permissions `0600`:

```yaml
current_context: admin@sylve.example.test
contexts:
  admin@sylve.example.test:
    server: https://sylve.example.test
    username: admin
    auth_type: sylve
    node_id: node-1
    hostname: node1.example.test
    token: eyJhbGciOi...
    expires_at: '2026-11-01T00:00:00Z'
    verify_ssl: true
    ca_cert: null
    default_node: node1.example.test
```

## EXIT STATUS

`Ctrl-C` in a streaming command (`vm logs --follow`, `system events`,
`network firewall logs --follow`) stops the stream and exits `0`.

Running a command group with no subcommand prints help and exits `0`, which is
not a usage error.

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | API error, formatter error, local I/O error, aborted confirmation, or task failure |
| `2` | Usage error, unknown option, or missing required argument |

## SEE ALSO

[sylve(1)](../README.md),
[sylve-options(7)](commands/config.md),
[sylve-config(5)](man/man5/sylve-config.5),
[config-format](config-format.md)
