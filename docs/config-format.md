# Sylve CLI configuration file

The configuration file is YAML at `~/.config/sylve/config.yaml` (or `$SYLVE_CONFIG`
when set). It is written with permissions `0600` and stores named login contexts.

## Location

| Priority | Path |
|---|---|
| 1 | `$SYLVE_CONFIG` (environment variable) |
| 2 | `$XDG_CONFIG_HOME/sylve/config.yaml` |
| 3 | `~/.config/sylve/config.yaml` |

## Quick reference

```yaml
current_context: prod

contexts:
  prod:
    server: https://sylve.example.test
    username: admin
    auth_type: sylve
    node_id: 4c4c4544-0042-4610-8056-b6c04f593432
    hostname: node1.example.test
    token: eyJhbGciOi...
    expires_at: "2026-11-01T12:00:00Z"
    verify_ssl: true
    ca_cert: /etc/ssl/certs/ca-bundle.crt
    default_node: node1.example.test
```

## Fields

### `current_context`

String. The name of the context used when `--context` is not supplied on the
command line. Must match a key in `contexts`.

### `contexts`

A mapping of context names to context objects. Each key is an arbitrary label
(by default derived as `username@hostname`). Each value has the fields below.

#### `server`

Required. The base URL of the Sylve API. The `/api` path suffix is optional.
If no scheme is given (`http://` or `https://`) the client defaults to HTTPS.

#### `username`

Login name recorded for this context.

#### `auth_type`

Either `sylve` (default) or `pam`. Determines the authentication backend the
server uses for login.

#### `token`

Bearer JWT token. Saved by `sylve login`; do not edit this field by hand.
The token is never printed by `sylve config view` unless `--show-token` is
passed.

#### `expires_at`

Optional. ISO-8601 timestamp for when the token expires (e.g.
`2026-11-01T12:00:00Z`). If absent, the expiry is decoded from the JWT's
`exp` claim.

#### `verify_ssl`

Boolean. Defaults to `true`. Set to `false` only for self-signed test
clusters. When `false`, `sylve login` and every API call prints a one-line
stderr warning.

#### `ca_cert`

Optional. Filesystem path to a custom CA certificate bundle. Used for both
HTTPS requests and the WebSocket console/VNC bridge.

#### `node_id`

UUID of the node the client connected to during login. Populated automatically
on `sylve login`.

#### `hostname`

Hostname of the node the client connected to during login. Populated
automatically on `sylve login`.

#### `default_node`

Optional. Default target node hostname or UUID for this context. Used when
`-n/--node` is not supplied on the command line.

## Environment overrides

Any of these environment variables can override the saved config file
without modifying it:

| Variable | Overrides |
|---|---|
| `SYLVE_SERVER` | `server` |
| `SYLVE_TOKEN` | `token` |
| `SYLVE_NODE` | `default_node` |
| `SYLVE_CONTEXT` | Selects an alternative `current_context` |
| `SYLVE_CONFIG` | Changes the config file path itself |
| `SYLVE_INSECURE` | Sets `verify_ssl` to `false` (use `1`, `true`, or `yes`) |

## Validation

Run `sylve config validate` to check the configuration file for:

- parse errors (invalid YAML)
- contexts with no `server` key (silently dropped by the loader)
- a `current_context` that does not exist
- expired or missing tokens

## See also

- `sylve config view` — print the live config (redacted by default)
- `sylve login` — create a new context
- `sylve config get-contexts` — list all saved contexts
- `docs/global-options.md` — global flags, env vars, exit codes
- `docs/man/man5/sylve-config.5` — roff man page (installed as `sylve-config(5)`)
- `sylve-config(5)` (roff man page) — the same reference in man page format