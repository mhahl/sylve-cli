# SYLVE-WHOAMI(1)

## NAME

`sylve-whoami` — display the active user, context, server, and token status

## SYNOPSIS

```sh
sylve whoami [-f FORMAT] [-c COLUMN]
```

## DESCRIPTION

`sylve whoami` inspects the active context and bearer token (from the
configuration file or `SYLVE_SERVER` and `SYLVE_TOKEN`), decodes the JWT
payload locally without performing a cryptographic signature check, and prints
session metadata.

The `token_status` field reports `VALID (...)`, `EXPIRED`, or
`VALID (unknown remaining)` when no expiration claim is available. When
`--format value` is used without `--column`, only `username` is printed.

## OPTIONS

- `-f, --format {table,json,yaml,value,csv}`
  Output format (default: `table`).
- `-c, --column NAME`
  Select and order fields. Repeatable or comma-separated. Available fields:
  `context`, `server`, `username`, `user_id`, `auth_type`, `hostname`,
  `node_id`, `default_node`, `verify_ssl`, `expires_at`, `token_status`.

## EXIT STATUS

- `0` — Session details printed.
- `1` — No context or token is configured, or an invalid column was requested.
- `2` — Command-line usage error.

## EXAMPLES

Display the full session table without cell truncation:

```sh
sylve --no-truncate whoami
```

```text
                Current Session
 Field         Value
 context       admin@sylve.example.test
 server        https://sylve.example.test
 username      admin
 user_id       1
 auth_type     sylve
 hostname      node1.example.test
 node_id       node-1
 default_node  node1.example.test
 verify_ssl    true
 expires_at    2026-11-01T00:00:00Z
 token_status  VALID (3d 13h 57m remaining)
```

Select specific fields as JSON:

```sh
sylve whoami -f json -c username,server,token_status
```

```json
{
  "username": "admin",
  "server": "https://sylve.example.test",
  "token_status": "VALID (3d 13h 58m remaining)"
}
```

Print CSV or a bare username for shell scripting:

```sh
sylve whoami --format csv --column username,server,token_status
```

```text
Field,Value
username,admin
server,https://sylve.example.test
token_status,VALID (3d 13h 58m remaining)
```

```sh
sylve whoami -f value
```

```text
admin
```

## SEE ALSO

[sylve(1)](../../README.md),
[sylve-login(1)](login.md),
[sylve-logout(1)](logout.md),
[sylve-config(1)](config.md),
[sylve-options(7)](../global-options.md)
