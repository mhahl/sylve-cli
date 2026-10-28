# SYLVE-NOTIFICATIONS(1)

## NAME

`sylve-notifications` — manage notification transports, rules, and active notifications

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
| `rules` | none | List notification rules |
| `rules-update` | none | Replace or update notification rules |
| `rule-create` | none | Create a notification rule |
| `rule-update` | `ID` | Update rule `ID` |
| `rule-delete` | `ID` | Delete rule `ID` |
| `rules-bulk-delete` | none | Delete multiple rules |
| `rules-bulk-update` | none | Update multiple rules |
| `rule-test` | `ID` | Send a test notification for rule `ID` |
| `transports` | none | List notification transports |
| `transport-create` | none | Create a notification transport |
| `transport-update` | `ID` | Update transport `ID` |
| `transport-delete` | `ID` | Delete transport `ID` |
| `transport-test` | `ID` | Test delivery on transport `ID` |

## OPTIONS

All subcommands accept:

- `-d, --data BODY`
  JSON or YAML request body, or `@FILE`.
- `-p, --param KEY=VALUE`
  Query parameter (repeatable).
- `-y, --yes`
  Skip destructive-request confirmation.
- `-n, --node NODE`
  Target node.
- `-f, --format {table,json,yaml,value,csv}`
  Output format (default: `table`).

## EXIT STATUS

- `0` — Success.
- `1` — API error or aborted confirmation.
- `2` — Command-line usage error.

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
sylve notifications rule-create \
  --data '{"name":"node-offline","event":"node.offline","transportId":1,"enabled":true}'
sylve notifications rule-update 2 --data '{"enabled":false}' -f json
sylve notifications rule-test 2

sylve notifications transport-create \
  --data '{"name":"mail","type":"email","config":{"to":"admin@example.test"}}'
sylve notifications transport-test 1
sylve notifications transport-delete 1 --yes
```

## SEE ALSO

[sylve(1)](../../README.md),
[sylve-system(1)](system.md),
[sylve-options(7)](../global-options.md)
