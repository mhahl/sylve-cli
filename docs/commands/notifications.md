# SYLVE-NOTIFICATIONS(1)

## NAME

`sylve-notifications` - manage notification transports, rules, and active notifications

## SYNOPSIS

```sh
sylve notifications COMMAND [ARGS ...]
```

## DESCRIPTION

`sylve notifications` inspects and dismisses active notifications, and creates,
updates, tests, and deletes notification rules and delivery transports via
generic Sylve API bindings.

## SUBCOMMANDS

| Subcommand | Path Arguments | Description |
|---|---|---|
| `list` | none | List active notifications |
| `count` | none | Show active notification count |
| `dismiss` | `ID` | Dismiss notification `ID` |
| `dismiss-all` | none | Dismiss all active notifications |
| `rule list` | none | List notification rules |
| `rule set-all` | none | Replace or update notification rules |
| `rule create` | none | Create a notification rule |
| `rule set` | `ID` | Update rule `ID` |
| `rule delete` | `ID` | Delete rule `ID` |
| `rule bulk-delete` | none | Delete multiple rules |
| `rule bulk-set` | none | Update multiple rules |
| `rule test` | none | Send a test notification using a `--data` or `--property` payload |
| `transport list` | none | List notification transports |
| `transport create` | none | Create a notification transport |
| `transport set` | `ID` | Update transport `ID` |
| `transport delete` | `ID` | Delete transport `ID` |
| `transport test` | `ID` | Test delivery on transport `ID` |

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
- `-c, --column`, `--sort-column`, `--filter`, `-l, --limit`
  Output selection (reads only).

## EXIT STATUS

- `0`: Success.
- `1`: API error or aborted confirmation.
- `2`: Command-line usage error.

## EXAMPLES

Check active notification count and list recent alerts:

```sh
sylve notifications count -f json
sylve notifications list --param limit=10 --node node1.example.test --format json -c id,title,severity
```

Dismiss one or all notifications:

```sh
sylve notifications dismiss 1
sylve notifications dismiss-all
```

Create, update, test, and delete rules and transports:

```sh
sylve notifications rule create \
  --property templateKey=node-offline --property targetKey=mail --property uiEnabled=true --property emailEnabled=true
sylve notifications rule set 2 --property emailEnabled=false --property uiEnabled=true -f json
sylve notifications rule test \
  --property templateKey=node-offline --property targetKey=mail --property severity=warning

sylve notifications transport create \
  --property name=mail --property type=email --property enabled=true
sylve notifications transport test 1
sylve notifications transport delete 1 --yes
```

Preview rule and transport creates and updates with `--property`:

```sh
sylve notifications rule create \
  --property templateKey=node-offline --property targetKey=mail \
  --property uiEnabled=true --property emailEnabled=true \
  --dry-run -f json
sylve notifications rule set 2 --property emailEnabled=false --property uiEnabled=true --dry-run -f json
sylve notifications transport create \
  --property name=example-mail --property type=email --property enabled=true \
  --dry-run -f json
sylve notifications transport set 1 --property enabled=false --dry-run -f json
```

Configure a nested object with dotted keys, one field at a time:

```sh
sylve notifications transport create \
  --property name=mail --property type=email \
  --property email.smtpHost=mail.example.test --property email.smtpPort=587 \
  --dry-run -f json
# body: {"name":"mail","type":"email","email":{"smtpHost":"mail.example.test","smtpPort":587}}
```

Test delivery, bulk-update rules, and clean up:

```sh
sylve notifications rule test \
  --property templateKey=node-offline --property targetKey=mail --property severity=warning \
  --dry-run -f json
sylve notifications transport test 1 --dry-run -f json
sylve notifications rule list -c id -c templateKey -c targetKey -l 10
sylve notifications rule bulk-set --property ids=1,2 --property emailEnabled=false --dry-run -f json
sylve notifications rule bulk-delete --property ids=3,4 --dry-run -f json
sylve notifications rule delete 2 --yes
sylve notifications transport delete 1 --yes
```

Preview dismissing notifications without sending anything:

```sh
sylve notifications dismiss 1 --dry-run -f json
sylve notifications dismiss-all --dry-run -f json
```

## SEE ALSO

[sylve(1)](../../README.md),
[sylve-system(1)](system.md),
[sylve-options(7)](../global-options.md)
