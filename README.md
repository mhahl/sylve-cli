# SYLVE(1) — FreeBSD General Commands Manual

## NAME

**sylve** — command-line client for Sylve FreeBSD clusters, Bhyve virtual machines, Jails, ZFS, and networking

---

## SYNOPSIS

```sh
sylve [--config path] [--context name] [-n node] [-k] [--timeout seconds] [--max-width columns] [--no-truncate] [--version] <command> [<subcommand> ...] [args ...]
```

```sh
sylve login [server_url] [-u username] [-p password] [--auth-type sylve|pam] [--remember | --no-remember] [-k] [--ca-cert path] [--context-name name] [--default-node node]
sylve logout
sylve whoami [-f format] [-c column]
sylve config <view | get-contexts | use-context | set-node | delete-context> [args ...]
sylve cluster <show | status | resources | resync | create | join | join-key | leave | note> [args ...]
sylve node <list | show | drain | reboot | remove | audit-logs> [args ...]
sylve vm <list | show | start | stop | shutdown | reboot | migrate | delete | logs | guest-agent | rename | snapshot | template> [args ...]
sylve jail <list | show | start | stop | restart | migrate | delete | logs | guest-info | rename | snapshot | bootstrap | template> [args ...]
sylve network <interface | switch | route | dhcp | firewall | object | wireguard> [args ...]
sylve download <list | show | create | upload | delete | signed-url | storage> [args ...]
sylve replication <policy | event> [args ...]
sylve backup <target | job | event> [args ...]
sylve zfs <pool | dataset | snapshot | periodic> [args ...]
sylve task <list | show | wait | cancel-migration> [args ...]
```

---

## DESCRIPTION

The **sylve** utility is a command-line interface for administering [Sylve](https://github.com/AlchemillaHQ/Sylve) hypervisor nodes and Raft-backed FreeBSD clusters.

**sylve** authenticates against a Sylve API endpoint (`/api/auth/login`) using either local Sylve credentials or FreeBSD PAM credentials and stores the issued Bearer JWT in `~/.config/sylve/config.yaml` (mode `0600`) until the token's `exp` timestamp expires.

When connected to a multi-node cluster, **sylve** operates across all online nodes by default:
- `list` subcommands aggregate resources across every online node in the cluster (or target a single node when `-n` / `--node` is supplied).
- Action and inspection subcommands (`vm start`, `jail stop`, `vm show`, `vm snapshot`, etc.) automatically locate the node hosting the specified guest (`RID`, `CTID`, or guest name) and route the request to that node via Sylve's `X-Current-Hostname` intra-cluster proxy header.
- `sylve node drain` evacuates a cluster node for maintenance by failing over active High Availability (HA) replication policies and preflight-validating and migrating standalone VMs and Jails to healthy peer nodes.

---

## INSTALLATION

### FreeBSD `pkg(8)` + `pip`

```sh
pkg install py312-typer py312-click py312-httpx py312-rich py312-pyyaml
python3.12 -m pip install --no-build-isolation --no-deps --user .
```

### FreeBSD Ports (`packaging/freebsd/sysutils/py-sylve-cli`)

```sh
cd packaging/freebsd/sysutils/py-sylve-cli
make package
pkg add work/pkg/py312-sylve-cli-0.3.1.pkg
```

### Standard `pip` / `pipx`

```sh
pip install .
```

---

## GLOBAL OPTIONS

The following options are accepted before the top-level command:

`--config` *path*
: Path to the CLI configuration file. Overrides `SYLVE_CONFIG` and the default `~/.config/sylve/config.yaml`.

`--context` *name*
: Named configuration context to use for the invocation. Overrides `SYLVE_CONTEXT` and `current_context` in the configuration file.

`-n` *node*, `--node` *node*
: Target cluster node hostname or UUID. Restricts multi-node queries or explicitly routes node-scoped operations via the `X-Current-Hostname` header.

`-k`, `--insecure`
: Disable TLS certificate verification when connecting to the Sylve HTTPS API.

`--timeout` *seconds*
: HTTP request timeout in seconds (default: `30.0`).

`--max-width` *columns*
: Maximum width of table output in terminal columns. Defaults to the detected terminal width.

`--no-truncate`
: Wrap long table cells instead of shortening them with an ellipsis. By default, tables stay on one line per record and truncate identifiers and descriptions that do not fit.

`-V`, `--version`
: Print the **sylve** version and exit.

`-h`, `--help`
: Display command usage and exit.

---

## OUTPUT FORMATTING OPTIONS

Query and listing commands accept the following formatting flags. List commands with a compact default view also accept `--long`:

`-f` *format*, `--format` *format*
: Output format. One of:
  - `table` — Formatted ASCII table (default).
  - `json` — Pretty-printed JSON array or object.
  - `yaml` — YAML document.
  - `value` — Space-separated raw values without headers (suitable for shell pipelines).
  - `csv` — RFC 4180 comma-separated values with header row.

`-c` *column*, `--column` *column*
: Include only the specified column or field in the output. May be specified multiple times, or as a comma-separated list, to select and order columns (for example, `-c rid -c name -c state` or `-c rid,name,state`). Unknown columns are rejected with the list of valid names.

`--sort-column` *column*
: Sort list output ascending by the given column header or field key. Numeric values sort numerically, and empty values sort last.

`--long`
: Show the full set of columns for list commands that provide a compact default view. This is useful for wide resources such as nodes, tasks, backups, and storage. If the result is wider than the terminal, use `--max-width` or `--no-truncate` to control the layout.

`-w`, `--wait` / `--no-wait`
: Poll asynchronous lifecycle, migration, replication, or backup tasks until they reach a terminal state.

---

## COMMANDS

### Session and Context Management

`sylve login` [*server_url*] [`-u` *user*] [`-p` *password*] [`--token` *jwt*] [`--auth-type` `sylve`|`pam`] [`--remember`|`--no-remember`] [`-k`] [`--ca-cert` *path*] [`--context-name` *name*] [`--default-node` *node*]
: Authenticate to a Sylve server, decode the JWT expiration claim, and persist the session context in `~/.config/sylve/config.yaml`. Prompts interactively for missing credentials.

`sylve logout`
: Revoke the active JWT token via `POST /api/auth/logout` and clear the stored token from the active context.

`sylve whoami` [`-f` *format*] [`-c` *column*]
: Print the authenticated user, realm (`sylve` or `pam`), server URL, connected node, token expiration timestamp, and remaining session lifetime.

`sylve config view` [`--redact`|`--show-token`] [`-f` *format*]
: Display the contents of the configuration file with bearer tokens redacted by default.

`sylve config get-contexts` [`-f` *format*]
: List all configured cluster contexts and their token validity status.

`sylve config use-context` *name*
: Set the active context in `~/.config/sylve/config.yaml`.

`sylve config set-node` [*node*]
: Pin a default cluster node for the active context, or pass `all` to clear the pin and operate cluster-wide.

`sylve config delete-context` *name*
: Remove a saved context from the configuration file.

---

### Cluster Management (`sylve cluster`)

`sylve cluster show` (alias: `sylve cluster status`)
: Display cluster enablement, Raft leader ID and address, quorum member suffrage, and node health summary.

`sylve cluster resources`
: List all VMs, Jails, VM templates, and Jail templates across every node in the cluster.

`sylve cluster resync`
: Audit Raft cluster members and rebuild divergent follower state (`POST /api/cluster/resync-state`).

`sylve cluster create` `--ip` *raft_ip*
: Bootstrap a new cluster on the connected node.

`sylve cluster join-key`
: Reveal the cluster enrollment key (`GET /api/cluster/join-key`).

`sylve cluster join` `--leader-ip` *ip* `--node-ip` *ip* `--node-id` *uuid* `--cluster-key` *key*
: Join the connected node to an existing cluster.

`sylve cluster leave` [`--retain-guests`|`--no-retain-guests`] [`--force`] [`-y`]
: Remove the local node from Raft consensus and reset its cluster state.

`sylve cluster note list` | `create` `--title` *title* `--content` *body* | `delete` *id*
: List, create, or delete cluster-wide notes.

---

### Node Operations and Maintenance Drain (`sylve node`)

`sylve node list` [`--long`] [`-f` *format*] [`-c` *column*] [`--sort-column` *col*]
: List all cluster nodes with status, CPU cores, CPU%, RAM, RAM%, Disk, Disk%, guest count, and Sylve version.

`sylve node show` [*node*] [`-f` *format*]
: Display detailed system, CPU, memory, and swap telemetry for *node*.

`sylve node drain` *node* [`-t` *target_node*] [`--stop-only`] [`--fallback-stop`] [`--running-only`] [`--dry-run`] [`--ignore-errors`] [`--wait`|`--no-wait`] [`-y`]
: Evacuate workloads from *node* in preparation for host maintenance:
  1. **HA Replicated Guests**: Queues a safe failover (`POST /api/cluster/replication/policies/{id}/failover`) with `movePinnedSource=true` to `--target-node` or the highest-weight ready policy target.
  2. **Standalone VMs & Jails**: Runs preflight validation (`GET /api/tasks/migration/validate`) and migrates each guest (`POST /api/vm/{rid}/migrations`, `POST /api/jail/{ctid}/migrations`) to `--target-node` or the least-loaded online cluster node.
  3. **Graceful Stop Mode**: If `--stop-only` is set (or `--fallback-stop` when a guest cannot be migrated), queues `shutdown` for VMs and `stop` for Jails.
  4. **Preflight Preview**: If `--dry-run` is specified, prints the computed drain plan and validation results without modifying cluster state.

`sylve node reboot` [*node*] [`-y`]
: Initiate a host reboot on *node* (`POST /api/basic/system/reboot`).

`sylve node remove` *node* [`--retain-guests`|`--no-retain-guests`] [`--force`] [`-y`]
: Remove a peer node from the cluster (`POST /api/cluster/remove-node`).

`sylve node audit-logs` [`-n` *node*] [`-f` *format*]
: Display audit log records across cluster nodes.

---

### Virtual Machines (`sylve vm` / `sylve server`)

`sylve vm list` [`-l` | `--long`] [`-n` *node*] [`-f` *format*] [`-c` *column*]
: List Bhyve virtual machines across all cluster nodes (or `--node`). Pass `-l` / `--long` to include vCPU count, memory allocation, and autostart settings.

`sylve vm show` *vm* [`-n` *node*] [`-f` *format*]
: Show full configuration, storage attachments, networks, and domain state for *vm* (by RID or name).

`sylve vm start` *vm* [*vm* ...] [`-n` *node*] [`-w`]
: Start one or more virtual machines.

`sylve vm stop` *vm* [*vm* ...] [`-n` *node*] [`-w`]
: Force power-off one or more virtual machines.

`sylve vm shutdown` *vm* [*vm* ...] [`-n` *node*] [`-w`]
: Gracefully shut down one or more virtual machines via ACPI.

`sylve vm reboot` *vm* [*vm* ...] [`-n` *node*] [`-w`]
: Reboot one or more virtual machines.

`sylve vm migrate` *vm* `-t` *target_node* [`--validate-only`] [`-n` *node*] [`-w`]
: Validate and migrate *vm* to *target_node*.

`sylve vm delete` *vm* [`--delete-volumes`|`--keep-volumes`] [`--delete-raw-disks`|`--keep-raw-disks`] [`--delete-macs`|`--keep-macs`] [`--force`] [`-y`]
: Remove a virtual machine and selected backing resources.

`sylve vm logs` *vm* [`-n` *node*]
: Print serial/console log output for *vm*.

`sylve vm guest-agent` *vm* [`-n` *node*] [`-f` *format*]
: Query OS and network interface information reported by the QEMU Guest Agent.

`sylve vm rename` *vm* *new_name* [`-n` *node*]
: Rename a virtual machine.

`sylve vm snapshot list` *vm* | `create` *vm* `--name` *snap* [`-d` *desc*] | `rollback` *vm* *snap_id* [`-y`] | `delete` *vm* *snap_id*
: List, create, roll back, or delete crash-consistent VM ZFS snapshots.

`sylve vm template list` | `capture` *vm* `--name` *name* | `delete` *template_id*
: List, capture, or delete VM templates.

---

### FreeBSD Jails (`sylve jail`)

`sylve jail list` [`-n` *node*] [`-f` *format*] [`-c` *column*]
: List FreeBSD and Linuxulator jails across all cluster nodes (or `--node`).

`sylve jail show` *jail* [`-n` *node*] [`-f` *format*]
: Show full configuration, mount points, networks, hooks, and limits for *jail* (by CTID or name).

`sylve jail start` *jail* [*jail* ...] [`-n` *node*] [`-w`]
: Start one or more jails.

`sylve jail stop` *jail* [*jail* ...] [`-n` *node*] [`-w`]
: Stop one or more jails.

`sylve jail restart` *jail* [*jail* ...] [`-n` *node*] [`-w`]
: Restart one or more jails.

`sylve jail migrate` *jail* `-t` *target_node* [`--validate-only`] [`-n` *node*] [`-w`]
: Validate and migrate *jail* to *target_node*.

`sylve jail delete` *jail* [`--delete-rootfs`|`--keep-rootfs`] [`--delete-macs`|`--keep-macs`] [`-y`]
: Delete a jail and optionally destroy its root ZFS dataset and MAC objects.

`sylve jail logs` *jail* [`-n` *node*]
: Print the last 512 console log lines for *jail*.

`sylve jail guest-info` *jail* [`-n` *node*] [`-f` *format*]
: Query live OS and network addresses from a running jail.

`sylve jail rename` *jail* *new_name* [`-n` *node*]
: Rename a jail.

`sylve jail snapshot list` *jail* | `create` *jail* `--name` *snap* [`-d` *desc*] | `rollback` *jail* *snap_id* [`-y`] | `delete` *jail* *snap_id*
: List, create, roll back, or delete jail ZFS snapshots.

`sylve jail bootstrap list` `--pool` *pool* | `create` `--pool` *pool* `--major` *ver* [`--minor` *ver*] [`--type` *type*]
: List or queue pkgbase jail bootstraps on a ZFS pool.

`sylve jail template list`
: List jail templates across cluster nodes.

---

### Networking (`sylve network`)

`sylve network interface list` | `l3` [`-n` *node*] [`-f` *format*]
: List physical/virtual network interfaces and managed host Layer-3 configurations.

`sylve network switch list` | `create-standard` `--name` *name* [...] | `create-manual` `--name` *name* `--bridge` *bridge* | `delete` *id* [`--type` `standard`|`manual`] | `sync`
: List, create, delete, or reconcile standard and manual bridge switches.

`sylve network route list` | `delete` *id* [`-n` *node*]
: List or delete static routing table entries.

`sylve network dhcp config` | `range-list` | `lease-list` [`-n` *node*]
: Query DHCP server settings, IP ranges, and static/dynamic leases.

`sylve network firewall traffic-list` | `nat-list` | `logs` [`--limit` *n*] [`--action` `pass`|`block`] [`-i` *iface*]
: Inspect PF firewall traffic rules, NAT rules, and live rule hit logs.

`sylve network object list` | `create` `--name` *name* `--type` *type* `-v` *value* [...] | `delete` *id*
: List, create, or delete firewall/network alias objects.

`sylve network wireguard status` | `client-list` [`-n` *node*]
: Display WireGuard server status and outbound client tunnels.

---

### Downloader and Images (`sylve download`)

`sylve download list` [`-n` *node*] [`-f` *format*]
: List downloader records across cluster nodes with transfer progress, size, pool, and status.

`sylve download show` *id_or_uuid_or_name* [`-n` *node*] [`-f` *format*]
: Show detailed metadata and extracted files for a download.

`sylve download create` *url* [`-O` *filename*] [`-t` `uncategorized`|`cloud-init`|`base-rootfs`] [`-p` *pool*] [`--extract`|`--no-extract`] [`--raw-convert`|`--no-raw-convert`] [`--ignore-tls`]
: Queue a new download from an HTTP(S) URL, magnet URI, or local server path.

`sylve download upload` *local_file* [`-t` *type*] [`-p` *pool*] [`--extract`|`--no-extract`] [`--raw-convert`|`--no-raw-convert`] [`-n` *node*]
: Stream a local ISO or disk image into a node's downloader storage and complete processing.

`sylve download delete` *id* [*id* ...] [`-n` *node*]
: Delete one or more downloads (uses bulk preflight deletion when multiple IDs are given).

`sylve download signed-url` `--uuid` *uuid* `--name` *filename* [`-n` *node*]
: Generate a 2-hour node-bound signed download capability URL.

`sylve download storage` [`-n` *node*]
: List available downloader ZFS storage pools and default filesystem paths.

---

### HA Replication (`sylve replication`)

`sylve replication policy list` | `show` *id* | `create` `--name` *name* `--guest-type` `vm`|`jail` `--guest-id` *id* `-t` *node[:weight]* [...] | `run` *id* | `failover` *id* [`-t` *node*] [`--mode` `safe`|`force`] | `delete` *id*
: Manage Zelta-based cluster HA replication policies, trigger immediate replication runs, or execute HA failovers.

`sylve replication event list` [`--policy-id` *id*] | `show` *event_id* [`-w`]
: Inspect replication events and follow live transfer progress.

---

### Cluster Backups (`sylve backup`)

`sylve backup target list` | `show` *id* | `datasets` *id* | `validate` *id* | `delete` *id*
: Inspect, validate, browse remote datasets on, or delete SSH/Zelta cluster backup targets.

`sylve backup job list` | `run` *id* | `snapshots` *id* | `restore` *id* `--snapshot` *snap* | `delete` *id*
: List scheduled backup jobs, trigger immediate runs, inspect remote snapshots, or queue snapshot restoration.

`sylve backup event list` [`--job-id` *id*] | `show` *event_id* [`-w`]
: List backup events or monitor live backup progress.

---

### ZFS Storage (`sylve zfs`)

`sylve zfs pool list` [`-a`] | `status` *pool* | `scrub` *pool* [`-n` *node*]
: List ZFS storage pools across nodes, inspect pool vdev health and scan stats, or initiate a pool scrub.

`sylve zfs dataset list` [`-t` `FILESYSTEM`|`VOLUME`|`SNAPSHOT`|`ALL`] | `create-fs` `-p` *parent* `--name` *name* | `create-vol` `-p` *parent* `--name` *name* `-s` *size* | `delete` *dataset* [`-t` `filesystem`|`volume`]
: List, create, or delete ZFS filesystems and volumes.

`sylve zfs snapshot list` | `create` *dataset* `-m` *snap_name* [`-r`] | `rollback` *snapshot* [`--destroy-more-recent`] | `delete` *snapshot* [`-r`]
: List, create, roll back, or destroy ZFS dataset snapshots.

`sylve zfs periodic list` [`-n` *node*]
: List scheduled periodic ZFS snapshot jobs.

---

### Lifecycle & Migration Tasks (`sylve task`)

`sylve task list` [`--active`|`--recent`] [`--long`] [`--guest-type` `vm`|`jail`] [`--guest-id` *id*] [`-n` *node*]
: List active or recent guest lifecycle and migration tasks across cluster nodes.

`sylve task show` *task_id* [`-n` *node*]
: Show details for a specific lifecycle task.

`sylve task wait` *task_id* [`--timeout` *seconds*] [`-n` *node*]
: Block and display a progress spinner until *task_id* reaches a terminal status.

`sylve task cancel-migration` *task_id* [`-n` *node*]
: Request cancellation of a queued or pre-cutover guest migration.

---

## FILES

`~/.config/sylve/config.yaml`
: Default configuration file storing named server contexts, active context selection, TLS verification preferences, and Bearer JWT session tokens (created with mode `0600`).

---

## ENVIRONMENT

`SYLVE_CONFIG`
: Path to an alternate configuration file.

`SYLVE_CONTEXT`
: Override the active configuration context name.

`SYLVE_SERVER`
: Override the Sylve server URL for the current invocation.

`SYLVE_TOKEN`
: Override the Bearer JWT authentication token for the current invocation.

`SYLVE_NODE`
: Default target cluster node hostname or UUID.

`SYLVE_INSECURE`
: When set to `1`, `true`, or `yes`, disables TLS certificate verification.

---

## EXIT STATUS

The **sylve** utility exits `0` on success, and `>0` if an error occurs (including expired authentication tokens, failed preflight validations, API errors, or task failures).

---

## EXAMPLES

Authenticate to a Sylve cluster using local credentials and skip self-signed TLS verification:

```sh
$ sylve login https://sylve.lan:8181 -u admin -k
```

Verify the current session and remaining token lifetime:

```sh
$ sylve whoami
```

List all virtual machines across the cluster in table format, or export RIDs and names as raw values:

```sh
$ sylve vm list
$ sylve vm list -f value -c rid -c name -c state
```

Start a VM and a Jail by name (automatically resolving which cluster node hosts each guest) and wait for completion:

```sh
$ sylve vm start web-prod-01 --wait
$ sylve jail start dns-resolver --wait
```

Preview draining `node2.lan` for hardware maintenance without executing changes:

```sh
$ sylve node drain node2.lan --dry-run
```

Drain `node2.lan`, failing over HA replication policies and migrating standalone guests to `node1.lan`, while gracefully shutting down any guests that cannot be migrated:

```sh
$ sylve node drain node2.lan --target-node node1.lan --fallback-stop --yes
```

---

## SEE ALSO

`bhyve(8)`, `jail(8)`, `zfs(8)`, `zpool(8)`, `pfctl(8)`, `pkg(8)`

Sylve Documentation and API Specification: `https://github.com/AlchemillaHQ/Sylve`

---

## LICENSE

BSD 2-Clause License (`LICENSE`).
