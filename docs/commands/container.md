# SYLVE-CONTAINER(1)

## NAME

`sylve-container` - manage OCI/Podman containers, images, networks, registries, and catalog apps

## SYNOPSIS

```sh
sylve container COMMAND [ARGS ...]
```

## DESCRIPTION

`sylve container` manages OCI/Podman containers, ZFS pool container images,
container networks, registry credentials, and catalog applications on Sylve
nodes via generic API bindings and an interactive WebSocket console.

## SUBCOMMANDS

| Subcommand | Path Arguments | Description |
|---|---|---|
| `list` | none | List containers |
| `simple` | none | List containers in brief (ID, name, and live state) |
| `create` | none | Create a container |
| `show` | `OCID` | Show container `OCID` |
| `set` | `OCID` | Update container `OCID` |
| `delete` | `OCID` | Delete container `OCID` |
| `start`, `stop`, `restart`, `kill` | `OCID` | Queue a lifecycle action on container `OCID` |
| `console` | `OCID` | Attach to container `OCID`'s interactive console over WebSocket |
| `logs` | `OCID` | Show container logs |
| `stats` | `OCID` | Show current container statistics |
| `stats-step` | `OCID STEP` | Show container statistics for `STEP` |
| `image-info` | `OCID` | Show container `OCID`'s image metadata |
| `options` | `OCID` | Update container boot and web options |
| `ports` | none | List used host ports |
| `stack` | none | Create a catalog application stack |
| `stack-rename` | `STACK` | Rename container stack `STACK` |
| `updates-check` | none | Check registries for container image updates |
| `image list` | `POOL` | List container images on `POOL` |
| `image pull` | `POOL` | Pull a container image to `POOL` |
| `image prune` | `POOL` | Remove unused container images from `POOL` |
| `image delete` | `POOL ID` | Remove image `ID` from `POOL` |
| `network list` | none | List container networks |
| `network create` | none | Create a container network |
| `network delete` | `ID` | Delete container network `ID` |
| `registry list` | none | List container registry credentials |
| `registry set` | none | Save a container registry credential |
| `registry delete` | `ID` | Delete registry credential `ID` |
| `catalog list` | none | List catalog applications |
| `catalog show` | `SOURCE ID` | Show settings for catalog application `SOURCE/ID` |
| `catalog render` | `SOURCE ID` | Render a deployment plan for `SOURCE/ID` |
| `catalog source-icon` | `SOURCE` | Download the logo for catalog `SOURCE` |
| `catalog icon` | `SOURCE ID` | Download the icon for catalog application `SOURCE/ID` |

## OPTIONS

### `container console`

- `OCID` (required): numeric container ID.
- `--shell PATH`: shell executable inside the container.
- `-n, --node NODE`: target node.
- Press `Enter`, then type `~.` to detach.

### `catalog source-icon` and `catalog icon`

- `--output, -o FILE` (required): local file path to write.
- `-p, --param KEY=VALUE`: query parameter (repeatable).
- `-n, --node NODE`: target node.

### Generic Subcommands

Write subcommands accept `--data/-d` and `--property/--property/-s`; all generic subcommands accept:

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

List containers and pull an image onto a ZFS pool:

```sh
sylve container list
sylve container image pull zroot --property image=docker.io/library/nginx:alpine --dry-run -f json
```

Create a container with `--property`, start it, and attach to its console:

```sh
sylve container create \
  --property name=web --property ocId=301 --property pool=zroot \
  --property image=docker.io/library/nginx:alpine --property startAfterCreate=true \
  --dry-run -f json
sylve container start 301
sylve container console 301 --shell /bin/sh
```

Inspect logs, stats, networks, and catalog apps:

```sh
sylve container simple -f json
sylve container logs 301 --param tail=100 -f json
sylve container stats 301 -f json
sylve container stack-rename media --property title="Media Stack" --dry-run -f json
sylve container updates-check --dry-run -f json
sylve container network list -f json
sylve container catalog list -f json
```

## SEE ALSO

[sylve(1)](../../README.md),
[sylve-jail(1)](jail.md),
[sylve-vm(1)](vm.md),
[sylve-options(7)](../global-options.md)
