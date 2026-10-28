# sylve logout

Revoke the active session token and clear it from the saved context.

## Synopsis

    sylve logout

## Options

This command has no options. Use the global options before the command:

    sylve --context prod --config /path/to/config.yaml logout

## Examples

### Minimal

    sylve logout

Output (illustrative):

    Logged out of context admin@sylve.example.test (https://sylve.example.test).

The token is removed from the context and the config file is rewritten with
mode `0600`.

### With every relevant option

    sylve --context prod --config /home/admin/.config/sylve/prod.yaml logout

Output (illustrative):

    Logged out of context prod (https://sylve.example.test).

`--context prod` selected a saved context. `--config` selected a non-default
config file. These are global options, so they go before `logout`.

## Inputs

- The active context and token from the config file, `SYLVE_SERVER` and
  `SYLVE_TOKEN`, or `--context`.

## Outputs

- Calls the server logout endpoint.
- Clears `token` and `expires_at` in the saved context.
- Prints the context name and server URL.
- Exit `0` on success. Exit `1` if the server rejects the request or cannot be
  reached.
