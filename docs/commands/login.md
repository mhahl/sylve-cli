# sylve login

Authenticate to a Sylve server and save the session token in a context.

## Synopsis

    sylve login [OPTIONS] [SERVER]

## Options

- `SERVER`
  Server URL. Defaults to the active context URL. If omitted and no context
  exists, the command prompts.

- `-u, --username USER`
  Username. Prompts if omitted.

- `-p, --password PASSWORD`
  Password. Prompts with hidden input if omitted.

- `--token JWT`
  Use an existing bearer token instead of username and password.

- `--auth-type TYPE`
  Authentication realm: `sylve` or `pam`. Default: `sylve`.

- `--remember / --no-remember`
  Request a 7-day token or a 24-hour token. Default: `--remember`.

- `-k, --insecure-skip-tls-verify`
  Skip TLS certificate verification.

- `--ca-cert FILE`
  Path to a custom CA certificate bundle.

- `--context-name NAME`
  Context name to save. Default: `USER@HOST`, or `HOST` when the username is
  unknown.

- `--default-node NODE`
  Default cluster node hostname or UUID for this context.

## Examples

### Minimal

    sylve login https://sylve.example.test

Prompts for username and password. Output (illustrative):

    Username: admin
    Password:
    Login successful! Logged into https://sylve.example.test as admin (sylve).
    Connected node: node1.example.test (node-1)
    Session token valid until 2026-10-29T12:00:00Z (23h 59m remaining).
    Context admin@sylve.example.test saved to /home/admin/.config/sylve/config.yaml.

### With every relevant option

    sylve login https://sylve.example.test \
      --username admin \
      --password 'correct horse battery staple' \
      --auth-type pam \
      --no-remember \
      --insecure-skip-tls-verify \
      --ca-cert /etc/ssl/certs/internal-ca.pem \
      --context-name prod \
      --default-node node1.example.test

Output (illustrative):

    Login successful! Logged into https://sylve.example.test as admin (pam).
    Connected node: node1.example.test (node-1)
    Session token valid until 2026-10-29T12:00:00Z (23h 59m remaining).
    Context prod saved to /home/admin/.config/sylve/config.yaml.

`--no-remember` changed the token lifetime from 7 days to 24 hours.
`--context-name prod` changed the saved context name.
`--default-node` made `node1.example.test` the default for this context.

### Existing token

    sylve login https://sylve.example.test --token eyJhbGciOi... --context-name ci

Output (illustrative):

    Login successful! Logged into https://sylve.example.test as token-user (sylve).
    Context ci saved to /home/admin/.config/sylve/config.yaml.

## Inputs

- `SERVER`, or the active context URL.
- A username and password, or `--token`.
- `--config FILE`, `SYLVE_CONFIG`, or the default config path.

## Outputs

- Writes the context to the config file with mode `0600`.
- Sets `current_context` to the saved context.
- Prints the server, username, auth type, node, expiry, and config path.
- Exit `0` on success. Exit `1` on an API or TLS error.
