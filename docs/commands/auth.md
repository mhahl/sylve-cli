# SYLVE-AUTH(1)

## NAME

`sylve-auth` - inspect user preferences and login configuration, create SSE tokens, and perform WebAuthn passkey flows

## SYNOPSIS

```sh
sylve auth COMMAND [ARGS ...]
```

## DESCRIPTION

`sylve auth` queries user preferences and server login capabilities, issues short-lived server-sent
event (`SSE`) tokens, and executes WebAuthn passkey login and registration
handshakes via generic Sylve API bindings.

`login-config`, `passkey login-begin`, and `passkey login-finish` are public
endpoints; the CLI does not send a bearer token when calling them.

## SUBCOMMANDS

| Subcommand | Description |
|---|---|
| `preferences` | Show user preferences |
| `login-config` | Show enabled authentication realms and passkey support |
| `sse-token` | Create a short-lived token for SSE streams |
| `passkey login-begin` | Begin a WebAuthn passkey login challenge |
| `passkey login-finish` | Complete a WebAuthn passkey login challenge |
| `passkey register-begin` | Begin a WebAuthn passkey registration ceremony |
| `passkey register-finish` | Complete a WebAuthn passkey registration ceremony |

## OPTIONS

Write subcommands accept `--data/-d` and `--set/--property/-s`; all subcommands accept:

- `-d, --data BODY`
  JSON or YAML request body, or `@FILE` (write commands).
- `-s, --set, --property KEY=VALUE`
  Set one body field (repeatable, dotted keys nest); overrides `--data` (write commands).
- `-p, --param KEY=VALUE`
  Query parameter (repeatable).
- `--dry-run`
  Print the request without sending it.
- `-n, --node NODE`
  Target node.
- `-f, --format {table,json,yaml,value,csv}`
  Output format (default: `table`).
- `-c, --column`, `--sort-column`, `--filter`, `-l, --limit`
  Output selection (reads only).

## EXIT STATUS

- `0`: Success.
- `1`: API error.
- `2`: Command-line usage error.

## EXAMPLES

Query user preferences:

```sh
sylve auth preferences -f json
```
```json
{
  "rowsPerPage": 50,
  "terminalColumns": 120
}
```

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

Issue an SSE token for a monitoring job:

```sh
sylve auth sse-token --node node1.example.test --format json
# Prints the short-lived token id and expiry for SSE streams.
```

Run passkey login and registration ceremonies:

```sh
sylve auth passkey login-begin -f json
sylve auth passkey login-finish --data @passkey-response.json -f json

sylve auth passkey register-begin -f json
sylve auth passkey register-finish --data @passkey-registration.json -f json
```

Preview the SSE token request without sending it (the endpoint takes no
request body):

```sh
sylve auth sse-token --dry-run -f json
```

Preview the passkey registration and login finish requests (the real
ceremonies need a live server and a WebAuthn response):

```sh
sylve auth passkey login-begin --dry-run -f json
sylve auth passkey login-finish --set requestId=example-request --dry-run -f json
sylve auth passkey register-begin --set userId=2 --dry-run -f json
sylve auth passkey register-finish \
  --set requestId=example-request --set label=example-key --dry-run -f json
```

## SEE ALSO

[sylve(1)](../../README.md),
[sylve-login(1)](login.md),
[sylve-user(1)](user.md),
[sylve-options(7)](../global-options.md)
