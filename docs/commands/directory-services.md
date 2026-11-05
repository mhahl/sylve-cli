# SYLVE-DIRECTORY-SERVICES(1)

## NAME

`sylve-directory-services` - manage Active Directory, Kerberos realms, keytabs, and principals

## SYNOPSIS

```sh
sylve directory-services COMMAND [ARGS ...]
```

## DESCRIPTION

`sylve directory-services` configures Active Directory domain membership,
Kerberos realms and keytabs, and searches directory principals via generic
Sylve API bindings.

## SUBCOMMANDS

| Subcommand | Path Arguments | Description |
|---|---|---|
| `principals` | none | Search Active Directory user or group principals |
| `ad config show` | none | Show Active Directory configuration |
| `ad config set` | none | Update Active Directory configuration |
| `ad status` | none | Show cached Active Directory status |
| `ad check` | none | Check Active Directory trust and Winbind health |
| `ad enable` | none | Enable or disable Active Directory |
| `ad join` | none | Join the configured Active Directory domain |
| `ad leave` | none | Leave the Active Directory domain |
| `kerberos config show` | none | Show Kerberos defaults |
| `kerberos config set` | none | Update Kerberos defaults |
| `kerberos realm-list` | none | List Kerberos realms |
| `kerberos realm-create` | none | Create a Kerberos realm |
| `kerberos realm-discover` | none | Discover Kerberos servers via DNS SRV records |
| `kerberos realm-set` | `ID` | Update Kerberos realm `ID` |
| `kerberos realm-delete` | `ID` | Delete Kerberos realm `ID` |
| `kerberos keytab-list` | none | List Kerberos keytabs |
| `kerberos keytab-create` | none | Upload a Kerberos keytab |
| `kerberos keytab-set` | `ID` | Update Kerberos keytab `ID` |
| `kerberos keytab-delete` | `ID` | Delete Kerberos keytab `ID` |

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
- `1`: API error or aborted confirmation.
- `2`: Command-line usage error.

## EXAMPLES

Inspect Active Directory status and discover a Kerberos realm:

```sh
sylve directory-services ad status -f json
sylve directory-services kerberos realm-discover --property realm=EXAMPLE.TEST --dry-run -f json
```

Configure Active Directory, join a domain, and search principals:

```sh
sylve directory-services ad config set \
  --property domain=example.test --property workgroup=EXAMPLE \
  --property idmapBackend=rid --property rangeLow=10000 --property rangeHigh=99999 \
  --dry-run -f json
sylve directory-services ad join \
  --property username=Administrator --property password=secret --dry-run -f json
sylve directory-services principals --param q=admins --param kind=group -f json
```

## SEE ALSO

[sylve(1)](../../README.md),
[sylve-user(1)](user.md),
[sylve-group(1)](group.md),
[sylve-samba(1)](samba.md),
[sylve-options(7)](../global-options.md)
