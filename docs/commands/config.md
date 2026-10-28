# SYLVE-CONFIG(1)

## NAME

`sylve-config` — view and modify saved login contexts

## SYNOPSIS

```sh
sylve config view [--redact | --show-token] [-f FORMAT]
sylve config get-contexts [-f FORMAT] [-c COLUMN]
sylve config use-context NAME
sylve config set-node [NODE]
sylve config delete-context NAME
```

## DESCRIPTION

`sylve config` inspects and updates the CLI configuration file. Contexts store
the target server URL, user metadata, TLS settings, default node, and session
bearer token.

Mutating subcommands (`use-context`, `set-node`, `delete-context`) rewrite the
configuration file with mode `0600`. `view` redacts bearer tokens unless
`--show-token` is passed explicitly.

## SUBCOMMANDS

| Subcommand | Description |
|---|---|
| `view` | Print the configuration file path, current context, and contexts |
| `get-contexts` | List saved contexts, one row per context |
| `use-context NAME` | Switch the active context to `NAME` |
| `set-node [NODE]` | Set or clear the default cluster node for the active context |
| `delete-context NAME` | Delete context `NAME` (selects the next saved context if current) |

## OPTIONS

### `config view`

- `--redact / --show-token`
  Redact bearer tokens in output (default: `--redact`). Do not paste
  `--show-token` output into issue reports.
- `-f, --format {table,json,yaml,value,csv}`
  Output format (default: `yaml`).

### `config get-contexts`

- `-f, --format {table,json,yaml,value,csv}`
  Output format (default: `table`).
- `-c, --column NAME`
  Select columns: `current`, `name`, `server`, `username`, `auth_type`,
  `hostname`, `default_node`, `status`.

### `config use-context`

- `NAME`
  Context name to activate. Must already exist in the configuration file.

### `config set-node`

- `NODE`
  Default node hostname or UUID. Omit `NODE`, or pass `all`, `none`, or `-`, to
  clear the default node and operate cluster-wide.

### `config delete-context`

- `NAME`
  Context name to remove.

## FILES

- `~/.config/sylve/config.yaml`
  Default configuration file (overridden by `--config`, `SYLVE_CONFIG`, or
  `$XDG_CONFIG_HOME/sylve/config.yaml`):
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

- `0` — Success.
- `1` — Configuration file or formatting error.
- `2` — Usage error or unknown context name.

## EXAMPLES

View the configuration with tokens redacted:

```sh
sylve config view
```

```yaml
config_file: /home/admin/.config/sylve/config.yaml
current_context: admin@sylve.example.test
contexts:
  admin@sylve.example.test:
    server: https://sylve.example.test
    username: admin
    auth_type: sylve
    hostname: node1.example.test
    node_id: node-1
    default_node: node1.example.test
    verify_ssl: true
    ca_cert: null
    expires_at: '2026-11-01T00:00:00Z'
    token: eyJhbGciOi...REDACTED
```

List saved contexts as JSON:

```sh
sylve config get-contexts -f json
```

```json
[
  {
    "current": "*",
    "name": "admin@sylve.example.test",
    "server": "https://sylve.example.test",
    "username": "admin",
    "auth_type": "sylve",
    "hostname": "node1.example.test",
    "default_node": "node1.example.test",
    "status": "ACTIVE (3d 13h 59m)"
  }
]
```

Inspect the unredacted configuration as JSON:

```sh
sylve config view --show-token -f json
```

```json
{
  "config_file": "/home/admin/.config/sylve/config.yaml",
  "current_context": "admin@sylve.example.test",
  "contexts": {
    "admin@sylve.example.test": {
      "server": "https://sylve.example.test",
      "username": "admin",
      "auth_type": "sylve",
      "hostname": "node1.example.test",
      "node_id": "node-1",
      "default_node": "node1.example.test",
      "verify_ssl": true,
      "ca_cert": null,
      "expires_at": "2026-11-01T00:00:00Z",
      "token": "eyJhbGciOi..."
    }
  }
}
```

Switch contexts, set or clear the default node, and delete a stale context:

```sh
sylve config use-context prod
# Switched to context prod.

sylve config set-node node2.example.test
# Default node for context prod set to node2.example.test.

sylve config set-node all
# Cleared default node for context prod (operating cluster-wide).

sylve config delete-context old
# Deleted context old.
```

## SEE ALSO

[sylve(1)](../../README.md),
[sylve-login(1)](login.md),
[sylve-logout(1)](logout.md),
[sylve-whoami(1)](whoami.md),
[sylve-config(5)](../man/man5/sylve-config.5),
[sylve-options(7)](../global-options.md)
