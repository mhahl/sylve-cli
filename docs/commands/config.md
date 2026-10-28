# sylve config

View and edit saved login contexts.

## Synopsis

    sylve config COMMAND [ARGS]...

## Commands

| Command | Purpose |
|---|---|
| `view` | Show the configuration file contents |
| `get-contexts` | List saved contexts |
| `use-context NAME` | Switch the active context |
| `set-node [NODE]` | Set or clear the default node |
| `delete-context NAME` | Remove a context |

## Options

### `config view`

- `--redact / --show-token`
  Redact bearer tokens. Default: `--redact`.
- `-f, --format {table,json,yaml,value,csv}`
  Output format. Default: `yaml`.

### `config get-contexts`

- `-f, --format {table,json,yaml,value,csv}`
  Output format. Default: `table`.
- `-c, --column NAME`
  Select columns: `current`, `name`, `server`, `username`, `auth_type`,
  `hostname`, `default_node`, `status`.

### `config use-context`

- `NAME`
  Context name to activate. Must exist.

### `config set-node`

- `NODE`
  Default node hostname or UUID. Omit, or use `all`, `none`, or `-`, to clear
  it and operate cluster-wide.

### `config delete-context`

- `NAME`
  Context name to remove. If it is current, the next saved context becomes
  current.

## Examples

### Minimal

    sylve config view

Output (illustrative; path and contexts depend on your config):

    config_file: /home/admin/.config/sylve/config.yaml
    current_context: ''
    contexts: {}

### List contexts

    sylve config get-contexts -f json

Output (illustrative, with one saved context):

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

### With every relevant option

    sylve config view --show-token -f json

Output shape (illustrative; the token is real when `--show-token` is used):

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

`--show-token` replaced the redacted token. Do not paste this output into an
issue.

### Switch and edit a context

    sylve config use-context prod

Output:

    Switched to context prod.

    sylve config set-node node2.example.test

Output:

    Default node for context prod set to node2.example.test.

    sylve config set-node all

Output:

    Cleared default node for context prod (operating cluster-wide).

    sylve config delete-context old

Output:

    Deleted context old.

## Inputs

- `--config FILE`, `SYLVE_CONFIG`, `$XDG_CONFIG_HOME/sylve/config.yaml`, or
  `~/.config/sylve/config.yaml`.
- YAML format:

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

## Outputs

- `view` prints the config path, current context, and contexts.
- `get-contexts` prints one row per context.
- `use-context`, `set-node`, and `delete-context` rewrite the config file with
  mode `0600`.
- Exit `0` on success. Exit `2` for an unknown context name.
