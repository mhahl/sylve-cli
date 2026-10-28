# Global and common options

Global options go before the command:

```sh
sylve --context prod --node node2 vm list
```

Most commands also define common output options after the command:

```sh
sylve vm list --format json --column RID,Name,State
```

## Global options

- `--config FILE`
  Configuration file. Default: `$SYLVE_CONFIG`, else
  `$XDG_CONFIG_HOME/sylve/config.yaml`, else `~/.config/sylve/config.yaml`.

- `--context NAME`
  Named context to use. Overrides the saved current context. Env:
  `SYLVE_CONTEXT`.

- `-n, --node NODE`
  Target cluster node hostname or UUID. Commands that also define `--node` use
  their own value. Env: `SYLVE_NODE`.

- `-k, --insecure`
  Skip TLS certificate verification. Env: `SYLVE_INSECURE`.

- `--timeout SECONDS`
  HTTP request timeout. Default: `30.0`.

- `--max-width COLUMNS`
  Maximum table width. Default: terminal width. Must be at least 1.

- `--no-truncate`
  Wrap long table cells instead of truncating them.

- `-V, --version`
  Print the version and exit.

- `-h, --help`
  Show help and exit.

## Output options

These appear on commands that print data.

- `-f, --format {table,json,yaml,value,csv}`
  Output format. Default: `table`.

  | Format | Output |
  |---|---|
  | `table` | Rich ASCII table |
  | `json` | Indented JSON |
  | `yaml` | YAML |
  | `value` | Space-separated values, one row per line |
  | `csv` | CSV with headers |

- `-c, --column NAME`
  Select and order columns. Repeat the flag or use commas. Accepts a column
  header or field key, case-insensitive.

  ```sh
  sylve vm list -c RID,Name,State
  sylve vm list -c RID -c Name
  ```

- `--sort-column NAME`
  Sort rows by a column header or field key.

- `--long`
  Add lower-priority columns. The added columns differ per command.

- `-n, --node NODE`
  Limit a list command to one node, or select the node for a single-object
  command.

- `-w, --wait / --no-wait`
  Wait for an asynchronous task. Defaults vary by command.

- `-y, --yes`
  Skip a confirmation prompt. Prompts appear only on a terminal.

## Environment

| Variable | Effect |
|---|---|
| `SYLVE_CONFIG` | Configuration file path |
| `SYLVE_CONTEXT` | Active context name |
| `SYLVE_SERVER` | Server URL override |
| `SYLVE_TOKEN` | Bearer token override |
| `SYLVE_NODE` | Default target node |
| `SYLVE_INSECURE` | `1`, `true`, or `yes` skips TLS verification |
| `XDG_CONFIG_HOME` | Base directory for the default config path |

`SYLVE_SERVER` and `SYLVE_TOKEN` allow use without a saved context:

```sh
export SYLVE_SERVER=https://sylve.example.test
export SYLVE_TOKEN=eyJhbGciOi...
sylve node list
```

## Configuration file

The file is YAML and is written with mode `0600`.

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

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | API error, formatter error, failed confirmation, or command failure |
| `2` | Usage error, unknown option, or missing argument |
