# sylve cloud-init

Manage reusable cloud-init templates.

These are generic API commands. The request body is the Sylve API shape.

## Synopsis

    sylve cloud-init COMMAND [ARGS]...

## Commands

| Command | Purpose |
|---|---|
| `templates` | List templates |
| `template-create` | Create a template |
| `template-update TEMPLATEID` | Update a template |
| `template-delete TEMPLATEID` | Delete a template |

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

Path arguments:

| Command | Arguments |
|---|---|
| `template-update`, `template-delete` | `templateId` |
| `templates`, `template-create` | none |

## Examples

### Minimal

    sylve cloud-init templates -f json

Output (illustrative):

    [
      {
        "id": 1,
        "name": "debian-base",
        "description": "Debian 13 cloud-init defaults"
      }
    ]

### With every relevant option

    sylve cloud-init template-create \
      --data @template.yaml \
      --param validate=1 \
      --node node1.example.test \
      --format json

Output (illustrative):

    {
      "id": 2,
      "name": "debian-base"
    }

`template.yaml` is the API request body:

```yaml
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

### Update and delete

    sylve cloud-init template-update 2 --data '{"description":"Updated"}' -f json

    sylve cloud-init template-delete 2 --yes

Output (illustrative):

    {
      "id": 2,
      "description": "Updated"
    }
    OK

`--data` carries the body. `--param` adds query parameters. `-y` skips the
delete confirmation.

## Inputs

- The active context and token.
- `--data` inline JSON/YAML or `@file`.
- Template IDs from `cloud-init templates`.

## Outputs

- Tables, JSON, YAML, value, or CSV.
- Mutating commands print the API result, or `OK` when the response is empty.
- Exit `0` on success. Exit `1` on API error or aborted confirmation. Exit `2`
  on usage error.
