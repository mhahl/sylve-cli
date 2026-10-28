# SYLVE-AUTH(1)

## NAME

`sylve-auth` — inspect login configuration, create SSE tokens, and perform WebAuthn passkey flows

## SYNOPSIS

```sh
sylve auth COMMAND [ARGS ...]
```

## DESCRIPTION

`sylve auth` queries server login capabilities, issues short-lived server-sent
event (`SSE`) tokens, and executes WebAuthn passkey login and registration
handshakes via generic Sylve API bindings.

`login-config`, `passkey-login-begin`, and `passkey-login-finish` are public
endpoints; the CLI does not send a bearer token when calling them.

## SUBCOMMANDS

| Subcommand | Description |
|---|---|
| `login-config` | Show enabled authentication realms and passkey support |
| `sse-token` | Create a short-lived token for SSE streams |
| `passkey-login-begin` | Begin a WebAuthn passkey login challenge |
| `passkey-login-finish` | Complete a WebAuthn passkey login challenge |
| `passkey-register-begin` | Begin a WebAuthn passkey registration ceremony |
| `passkey-register-finish` | Complete a WebAuthn passkey registration ceremony |

## OPTIONS

All subcommands accept:

- `-d, --data BODY`
  JSON or YAML request body, or `@FILE`.
- `-p, --param KEY=VALUE`
  Query parameter (repeatable).
- `-y, --yes`
  Accepted by the shared generic handler (no `auth` subcommand is destructive).
- `-n, --node NODE`
  Target node.
- `-f, --format {table,json,yaml,value,csv}`
  Output format (default: `table`).

## EXIT STATUS

- `0` — Success.
- `1` — API error.
- `2` — Command-line usage error.

## EXAMPLES

Query enabled login methods:

```sh
sylve auth login-config -f json
```

```json
{
  "sylve": true,
  "pam": false,
  "passkeys": true
}
```

Issue an SSE token:

```sh
sylve auth sse-token \
  --data '{"name":"monitoring","expiresIn":3600}' \
  --param dryRun=0 \
  --node node1.example.test \
  --format json
```

Run passkey login and registration ceremonies:

```sh
sylve auth passkey-login-begin --data '{"username":"admin"}' -f json
sylve auth passkey-login-finish --data @passkey-response.json -f json

sylve auth passkey-register-begin -f json
sylve auth passkey-register-finish --data @passkey-registration.json -f json
```

## SEE ALSO

[sylve(1)](../../README.md),
[sylve-login(1)](login.md),
[sylve-user(1)](user.md),
[sylve-options(7)](../global-options.md)
