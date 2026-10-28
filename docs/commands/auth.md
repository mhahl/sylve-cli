# sylve auth

Inspect login configuration, create SSE tokens, and use passkeys.

These are generic API commands. The request body is the Sylve API shape.

## Synopsis

    sylve auth COMMAND [ARGS]...

## Commands

| Command | Purpose |
|---|---|
| `login-config` | Show login configuration |
| `sse-token` | Create an SSE token |
| `passkey-login-begin` | Begin passkey login |
| `passkey-login-finish` | Finish passkey login |
| `passkey-register-begin` | Begin passkey registration |
| `passkey-register-finish` | Finish passkey registration |

`login-config`, `passkey-login-begin`, and `passkey-login-finish` are public
endpoints. The CLI does not send a bearer token for them.

## Options

All commands accept:

- `-d, --data BODY`
  JSON or YAML request body, or `@FILE`.
- `-p, --param KEY=VALUE`
  Query parameter. Repeatable.
- `-y, --yes`
  Skip the destructive-request confirmation.
- `-n, --node NODE`
  Target node.
- `-f, --format {table,json,yaml,value,csv}`
  Output format. Default: `table`.

No command has path arguments. `-y/--yes` is accepted by the shared generic
handler, but no `auth` command is destructive, so it changes nothing.

## Examples

### Minimal

    sylve auth login-config -f json

Output (illustrative):

    {
      "sylve": true,
      "pam": false,
      "passkeys": true
    }

### With every relevant option

    sylve auth sse-token \
      --data '{"name":"monitoring","expiresIn":3600}' \
      --param dryRun=0 \
      --node node1.example.test \
      --format json

Output (illustrative):

    {
      "token": "eyJhbGciOi...",
      "expiresAt": "2026-10-28T21:00:00Z"
    }

`--data` carries the body. `--param` adds query parameters. `-f json` changes
the output format.

### Passkey login

    sylve auth passkey-login-begin --data '{"username":"admin"}' -f json

    sylve auth passkey-login-finish --data @passkey-response.json -f json

Output (illustrative):

    {
      "challenge": "...",
      "allowCredentials": []
    }

### Passkey registration

    sylve auth passkey-register-begin -f json

    sylve auth passkey-register-finish --data @passkey-registration.json -f json

## Inputs

- The server URL from the active context, `SYLVE_SERVER`, or environment.
- `--data` inline JSON/YAML or `@file`.
- `--param` repeated query parameters.

## Outputs

- Tables, JSON, YAML, value, or CSV.
- Login and passkey commands return WebAuthn challenge or credential objects.
- Exit `0` on success. Exit `1` on API error or aborted confirmation. Exit `2`
  on usage error.
