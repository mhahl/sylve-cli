# SYLVE-CLOUD-INIT(1)

## NAME

`sylve-cloud-init` - manage reusable cloud-init templates

## SYNOPSIS

```sh
sylve cloud-init COMMAND [ARGS ...]
```

## DESCRIPTION

`sylve cloud-init` lists, creates, updates, and deletes reusable cloud-init
templates via generic Sylve API bindings. Supply request payloads with
`--data` in JSON or YAML format.

## SUBCOMMANDS

| Subcommand | Path Arguments | Description |
|---|---|---|
| `template list` | none | List cloud-init templates |
| `template create` | none | Create a cloud-init template |
| `template set` | `TEMPLATE_ID` | Update template `TEMPLATE_ID` |
| `template delete` | `TEMPLATE_ID` | Delete template `TEMPLATE_ID` |

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

List cloud-init templates as JSON:

```sh
sylve cloud-init template list -f json
```

```json
[
  {
    "id": 1,
    "name": "debian-base",
    "description": "Debian 13 cloud-init defaults"
  }
]
```

Create a template from `template.yaml`, update its description, and delete it:

```yaml
# template.yaml
name: debian-base
description: Debian 13 cloud-init defaults
userData: |
  #cloud-config
  packages:
    - qemu-guest-agent
metaData: |
  instance-id: debian-base
networkConfig: |
  version: 2
  ethernets:
    vtnet0:
      dhcp4: true
```

```sh
sylve cloud-init template create \
  --data @template.yaml \
  --node node1.example.test \
  --format json

sylve cloud-init template delete 2 --yes
```

Preview a create with `--property` fields and show the request:

```sh
sylve cloud-init template create \
  --property name=example-base --property user=example-user \
  --property meta=example-meta --property networkConfig=example-net \
  --dry-run -f json
```

Update a template, narrow the list to a few columns, and delete:

```sh
sylve cloud-init template set 1 \
  --property name=example-base-v2 --property user=example-user \
  --property meta=example-meta --property networkConfig=example-net \
  --dry-run -f json
sylve cloud-init template list -c id -c name --sort-column name -l 5
sylve cloud-init template delete 1 --yes
```

## SEE ALSO

[sylve(1)](../../README.md),
[sylve-vm(1)](vm.md),
[sylve-download(1)](download.md),
[sylve-options(7)](../global-options.md)
