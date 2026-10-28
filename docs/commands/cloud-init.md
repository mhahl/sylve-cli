# SYLVE-CLOUD-INIT(1)

## NAME

`sylve-cloud-init` — manage reusable cloud-init templates

## SYNOPSIS

```sh
sylve cloud-init COMMAND [ARGS ...]
```

## DESCRIPTION

`sylve cloud-init` lists, creates, updates, and deletes reusable cloud-init
templates via generic Sylve API bindings. Request payloads are supplied with
`--data` in JSON or YAML format.

## SUBCOMMANDS

| Subcommand | Path Arguments | Description |
|---|---|---|
| `templates` | none | List cloud-init templates |
| `template-create` | none | Create a cloud-init template |
| `template-update` | `TEMPLATE_ID` | Update template `TEMPLATE_ID` |
| `template-delete` | `TEMPLATE_ID` | Delete template `TEMPLATE_ID` |

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

List cloud-init templates as JSON:

```sh
sylve cloud-init templates -f json
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
sylve cloud-init template-create \
  --data @template.yaml \
  --param validate=1 \
  --node node1.example.test \
  --format json

sylve cloud-init template-update 2 --data '{"description":"Updated"}' -f json
sylve cloud-init template-delete 2 --yes
```

## SEE ALSO

[sylve(1)](../../README.md),
[sylve-vm(1)](vm.md),
[sylve-download(1)](download.md),
[sylve-options(7)](../global-options.md)
