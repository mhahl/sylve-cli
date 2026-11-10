# SYLVE-AUTH(1)

## NAME

`sylve-auth` - manage permissions, roles, grants, ACL groups, OIDC realms, passkeys, and SSE tokens

## SYNOPSIS

```sh
sylve auth COMMAND [ARGS ...]
```

## DESCRIPTION

`sylve auth` queries user preferences, effective permissions, and server login
capabilities; manages cluster RBAC roles, permission groups (`acl-group`), path
grants, and OpenID Connect (`OIDC`) realms; issues short-lived server-sent
event (`SSE`) tokens; and runs OIDC and WebAuthn passkey sign-in flows via
generic Sylve API bindings.

`login-config`, `oidc start`, `oidc callback`, `passkey login-begin`, and
`passkey login-finish` are public endpoints; the CLI does not send a bearer
token when calling them.

## SUBCOMMANDS

| Subcommand | Path Arguments | Description |
|---|---|---|
| `preferences` | none | Show user preferences |
| `permissions` | none | Show the signed-in user's effective permissions |
| `login-config` | none | Show enabled authentication realms and passkey support |
| `sse-token` | none | Create a short-lived token for SSE streams |
| `role list` | none | List built-in and custom authorization roles |
| `role set` | `NAME` | Create or update custom role `NAME` |
| `role delete` | `NAME` | Delete custom role `NAME` and its grants |
| `acl-group list` | none | List cluster-wide permission groups |
| `acl-group set` | `NAME` | Create permission group `NAME` or replace its members |
| `acl-group delete` | `NAME` | Delete permission group `NAME` and its grants |
| `grant list` | none | List all role grants across the cluster |
| `grant set` | none | Grant a role to a user or group on a path |
| `grant delete` | none | Revoke a role grant from a user or group on a path |
| `realm list` | none | List OpenID Connect realms |
| `realm discover` | none | Read an OIDC provider's discovery document |
| `realm set` | `NAME` | Create or update OIDC realm `NAME` |
| `realm delete` | `NAME` | Delete OIDC realm `NAME`, its users, and their grants |
| `realm user-add` | `NAME` | Pre-register a user in OIDC realm `NAME` |
| `oidc start` | `REALM` | Start an OIDC browser sign-in flow for `REALM` |
| `oidc callback` | none | Complete an OIDC sign-in callback |
| `passkey login-begin` | none | Begin a WebAuthn passkey login challenge |
| `passkey login-finish` | none | Complete a WebAuthn passkey login challenge |
| `passkey register-begin` | none | Begin a WebAuthn passkey registration ceremony |
| `passkey register-finish` | none | Complete a WebAuthn passkey registration ceremony |

## OPTIONS

Write subcommands accept `--data/-d` and `--property/--property/-s`; all subcommands accept:

- `-d, --data BODY`
  JSON or YAML request body, or `@FILE` (write commands).
- `-s, --property, --property KEY=VALUE`
  Set one body field (repeatable, dotted keys nest); overrides `--data` (write commands).
- `-p, --param KEY=VALUE`
  Query parameter (repeatable).
- `--dry-run`
  Print the request without sending it.
- `-y, --yes`
  Skip confirmation (destructive commands only, e.g. deletes).
- `-n, --node NODE`
  Target node.
- `-f, --format {table,json,yaml,value,csv}`
  Output format (default: `table`).
- `-c, --column`, `--sort-column`, `--filter`, `-l, --limit`, `--long`
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
sylve auth passkey login-finish --property requestId=example-request --dry-run -f json
sylve auth passkey register-begin --property userId=2 --dry-run -f json
sylve auth passkey register-finish \
  --property requestId=example-request --property label=example-key --dry-run -f json
```

Inspect permissions, roles, ACL groups, and grants, or preview RBAC and OIDC
changes:

```sh
sylve auth permissions -f json
sylve auth role list -f json
sylve auth role set vm-operator --property privileges=VM.Audit,VM.PowerMgmt --dry-run -f json
sylve auth acl-group set ops --property members=alice@sylve,bob@pam --dry-run -f json
sylve auth grant set \
  --property path=/vms --property role=vm-operator \
  --property subject=ops --property subjectType=group --property propagate=true \
  --dry-run -f json
sylve auth realm discover --property issuer=https://idp.example.test --dry-run -f json
sylve auth realm set corp \
  --property issuer=https://idp.example.test --property clientId=sylve-ui \
  --property enabled=true --dry-run -f json
sylve auth realm user-add corp --property username=alice --property email=alice@example.test --dry-run -f json
sylve auth oidc start corp --property redirectUri=https://sylve.example.test/api/auth/oidc/callback --dry-run -f json
```

## SEE ALSO

[sylve(1)](../../README.md),
[sylve-login(1)](login.md),
[sylve-user(1)](user.md),
[sylve-options(7)](../global-options.md)
