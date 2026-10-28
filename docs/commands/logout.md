# SYLVE-LOGOUT(1)

## NAME

`sylve-logout` — revoke the active session token and clear it from the saved context

## SYNOPSIS

```sh
sylve [GLOBAL_OPTIONS] logout
```

## DESCRIPTION

`sylve logout` calls the Sylve server logout endpoint to revoke the active
bearer token, clears `token` and `expires_at` from the active context in the
configuration file (rewriting it with mode `0600`), and prints the logged-out
context name and server URL.

The active session is read from the configuration file, `--context`, or
`SYLVE_SERVER` and `SYLVE_TOKEN`.

## OPTIONS

`logout` takes no subcommand-specific options. Global options (`--context`,
`--config`, `-k`) must be placed before `logout`:

```sh
sylve --context prod --config /path/to/config.yaml logout
```

## FILES

- `~/.config/sylve/config.yaml`
  Default configuration file updated with mode `0600`.

## EXIT STATUS

- `0` — Token revoked and cleared.
- `1` — Server rejected the request or could not be reached.
- `2` — Command-line usage error.

## EXAMPLES

Log out of the current context:

```sh
sylve logout
```

```text
Logged out of context admin@sylve.example.test (https://sylve.example.test).
```

Log out of a named context in an alternate configuration file:

```sh
sylve --context prod --config /home/admin/.config/sylve/prod.yaml logout
```

```text
Logged out of context prod (https://sylve.example.test).
```

## SEE ALSO

[sylve(1)](../../README.md),
[sylve-login(1)](login.md),
[sylve-whoami(1)](whoami.md),
[sylve-config(1)](config.md),
[sylve-options(7)](../global-options.md)
