# sylve whoami

Show the current user, context, server, and token status.

## Synopsis

    sylve whoami [OPTIONS]

## Options

- `-f, --format {table,json,yaml,value,csv}`
  Output format. Default: `table`.

- `-c, --column NAME`
  Select fields. Repeat or use commas. Field names: `context`, `server`,
  `username`, `user_id`, `auth_type`, `hostname`, `node_id`, `default_node`,
  `verify_ssl`, `expires_at`, `token_status`.

## Examples

### Minimal

    sylve --no-truncate whoami

Output (exact shape; the remaining time changes):

                    Current Session
    +--------------+------------------------------+
    | Field        | Value                        |
    +--------------+------------------------------+
    | context      | admin@sylve.example.test     |
    | server       | https://sylve.example.test   |
    | username     | admin                        |
    | user_id      | 1                            |
    | auth_type    | sylve                        |
    | hostname     | node1.example.test           |
    | node_id      | node-1                       |
    | default_node | node1.example.test           |
    | verify_ssl   | true                         |
    | expires_at   | 2026-11-01T00:00:00Z         |
    | token_status | VALID (3d 13h 57m remaining) |
    +--------------+------------------------------+

### With every relevant option

    sylve whoami -f json -c username,server,token_status

Output:

    {
      "username": "admin",
      "server": "https://sylve.example.test",
      "token_status": "VALID (3d 13h 58m remaining)"
    }

### CSV and value formats

    sylve whoami --format csv --column username,server,token_status

Output:

    Field,Value
    username,admin
    server,https://sylve.example.test
    token_status,VALID (3d 13h 58m remaining)

`--format value` prints only the username:

    sylve whoami -f value

Output:

    admin

## Inputs

- The active context and token from the config file, or `SYLVE_SERVER` and
  `SYLVE_TOKEN`.
- The JWT payload is decoded locally. No signature check is performed.

## Outputs

- Prints the selected session fields.
- `token_status` is `VALID (...)`, `EXPIRED`, or `VALID (unknown remaining)`
  when no expiry is available.
- Exit `0` on success. Exit `1` when no context is configured.
