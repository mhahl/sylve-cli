# SYLVE-LOGIN(1)

## NAME

`sylve-login` — authenticate to a Sylve server and save the session token in a context

## SYNOPSIS

```sh
sylve login [OPTIONS] [SERVER]
```

## DESCRIPTION

`sylve login` authenticates against a Sylve server using a username and
password (or an existing JWT bearer token via `--token`), writes the context
entry to the CLI configuration file with mode `0600`, and sets `current_context`
to the saved context.

On success it prints the server URL, username, authentication realm, connected
node, token expiration timestamp, and configuration file path.

## OPTIONS

- `SERVER`
  Server URL. Defaults to the active context URL; prompts interactively if
  omitted and no active context exists.
- `-u, --username USER`
  Username. Prompts if omitted.
- `-p, --password PASSWORD`
  Password. Prompts with hidden input if omitted.
- `--token JWT`
  Use an existing bearer token instead of username and password.
- `--auth-type TYPE`
  Authentication realm: `sylve` or `pam` (default: `sylve`).
- `--remember / --no-remember`
  Request a 7-day token (`--remember`) or a 24-hour token (`--no-remember`).
  Default: `--remember`.
- `-k, --insecure-skip-tls-verify`
  Skip TLS certificate verification.
- `--ca-cert FILE`
  Path to a custom CA certificate bundle.
- `--context-name NAME`
  Context name to save (default: `USER@HOST`, or `HOST` when the username is
  unknown).
- `--default-node NODE`
  Default cluster node hostname or UUID for this context.

## FILES

- `~/.config/sylve/config.yaml`
  Default configuration file written with mode `0600`. Overridden by `--config`
  or `SYLVE_CONFIG`.

## EXIT STATUS

- `0` — Authentication succeeded and the context was saved.
- `1` — API, authentication, or TLS error.
- `2` — Command-line usage error.

## EXAMPLES

Interactive login with minimal arguments:

```sh
sylve login https://sylve.example.test
```

```text
Username: admin
Password:
Login successful! Logged into https://sylve.example.test as admin (sylve).
Connected node: node1.example.test (node-1)
Session token valid until 2026-10-29T12:00:00Z (23h 59m remaining).
Context admin@sylve.example.test saved to /home/admin/.config/sylve/config.yaml.
```

PAM login with a 24-hour token, custom CA bundle, context name, and default
node (the password is prompted for without showing it on the command line):

```sh
sylve login https://sylve.example.test \
  --username admin \
  --auth-type pam \
  --no-remember \
  --ca-cert /etc/ssl/certs/internal-ca.pem \
  --context-name prod \
  --default-node node1.example.test
```

```text
Password:
Login successful! Logged into https://sylve.example.test as admin (pam).
Connected node: node1.example.test (node-1)
Session token valid until 2026-10-29T12:00:00Z (23h 59m remaining).
Context prod saved to /home/admin/.config/sylve/config.yaml.
```

Save a pre-issued bearer token:

```sh
sylve login https://sylve.example.test --token eyJhbGciOi... --context-name ci
```

```text
Login successful! Logged into https://sylve.example.test as token-user (sylve).
Context ci saved to /home/admin/.config/sylve/config.yaml.
```

## SEE ALSO

[sylve(1)](../../README.md),
[sylve-logout(1)](logout.md),
[sylve-whoami(1)](whoami.md),
[sylve-config(1)](config.md),
[sylve-options(7)](../global-options.md)
