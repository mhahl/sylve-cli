# SYLVE(1)

[![CI](https://github.com/mhahl/sylve-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/mhahl/sylve-cli/actions/workflows/ci.yml)

## NAME

`sylve` — command-line client for Sylve FreeBSD clusters, Bhyve VMs, jails, ZFS, and networking

## SYNOPSIS

```sh
sylve [--config FILE] [--context NAME] [-n NODE] [-k] [--timeout SECONDS]
      [--max-width COLUMNS] [--no-truncate] [-V] [-h]
      COMMAND [ARGS ...]
```

## DESCRIPTION

`sylve` manages Sylve FreeBSD nodes and clusters over HTTPS. It authenticates
against a Sylve server, stores the session bearer token in a local context file
(`mode 0600`), and executes resource, storage, network, and host operations
against the selected cluster node.

Output defaults to human-readable tables and can be switched to `json`, `yaml`,
`value`, or `csv` with `-f` / `--format` on data-producing commands.

`sylve-cli` is an independent tool and is not affiliated with or endorsed by
the Sylve project.

## INSTALLATION

From a local checkout with `pip`:

```sh
pip install .
```

From the FreeBSD port:

```sh
cd packaging/freebsd/sysutils/py-sylve-cli
make package
pkg add work/pkg/py312-sylve-cli-0.3.1.pkg
```

Only `sylve(1)` and `sylve-config(5)` are installed as roff manual pages. The
linked command guides below are Markdown, not separate `man` pages:

```sh
man sylve
man sylve-config
```

## GLOBAL OPTIONS

Global options must precede `COMMAND`:

- `--config FILE`
  Path to the configuration file.
- `--context NAME`
  Named login context to use for this invocation.
- `-n, --node NODE`
  Target cluster node hostname or UUID.
- `-k, --insecure`
  Disable TLS certificate verification.
- `--timeout SECONDS`
  HTTP request timeout in seconds (default: `30.0`).
- `--max-width COLUMNS`
  Maximum table width in columns (default: terminal width).
- `--no-truncate`
  Wrap long table cells instead of truncating them.
- `-V, --version`
  Print the version and exit.
- `-h, --help`
  Print usage information and exit.

See [sylve-options(7)](docs/global-options.md) for output formatting flags and
generic API request flags.

## COMMANDS

| Command guide | Summary |
|---|---|
| [login](docs/commands/login.md) | Authenticate and save a context |
| [logout](docs/commands/logout.md) | Revoke the active token and clear it |
| [whoami](docs/commands/whoami.md) | Display the active session and token status |
| [config](docs/commands/config.md) | View and modify saved contexts |
| [cluster](docs/commands/cluster.md) | Cluster status, Raft membership, and notes |
| [node](docs/commands/node.md) | Node inventory, telemetry, drain, reboot, audit logs |
| [vm](docs/commands/vm.md) | Bhyve VMs, snapshots, and templates (alias: `server`) |
| [jail](docs/commands/jail.md) | FreeBSD jails, snapshots, bootstraps, and templates |
| [network](docs/commands/network.md) | Interfaces, switches, routes, DHCP, PF, WireGuard |
| [download](docs/commands/download.md) | ISO and image downloads, uploads, signed URLs |
| [replication](docs/commands/replication.md) | HA replication policies, failovers, and events |
| [backup](docs/commands/backup.md) | Backup targets, scheduled jobs, restores, and events |
| [zfs](docs/commands/zfs.md) | ZFS pools, datasets, snapshots, and periodic jobs |
| [task](docs/commands/task.md) | Guest lifecycle tasks and migration cancellation |
| [system](docs/commands/system.md) | Disks, SMART, PCI passthrough, files, certs, settings |
| [samba](docs/commands/samba.md) | Samba global configuration and shares |
| [iscsi](docs/commands/iscsi.md) | iSCSI initiators, targets, LUNs, and portals |
| [ddns](docs/commands/ddns.md) | Dynamic DNS entries |
| [mdns](docs/commands/mdns.md) | mDNS configuration and records |
| [notifications](docs/commands/notifications.md) | Notification transports, rules, and active alerts |
| [user](docs/commands/user.md) | Local, PAM, and imported users, plus passkeys |
| [group](docs/commands/group.md) | Authentication groups and membership |
| [auth](docs/commands/auth.md) | Login configuration, SSE tokens, and passkeys |
| [cloud-init](docs/commands/cloud-init.md) | Reusable cloud-init templates |

## ENVIRONMENT

- `SYLVE_CONFIG` — override configuration file path.
- `SYLVE_CONTEXT` — override active context name.
- `SYLVE_SERVER` — override server URL without a saved context.
- `SYLVE_TOKEN` — override bearer token without a saved context.
- `SYLVE_NODE` — default target cluster node.
- `SYLVE_INSECURE` — set to `1`, `true`, or `yes` to skip TLS verification.
- `XDG_CONFIG_HOME` — base directory for the default configuration file.

## FILES

- `~/.config/sylve/config.yaml`
  Default configuration file containing saved contexts and bearer tokens.
- `docs/man/src/*.in`
  Roff manual page templates. Regenerate with `make man`.

## EXIT STATUS

- `0` — Success.
- `1` — API error, formatter error, aborted confirmation, or task failure.
- `2` — Command-line usage error.

## EXAMPLES

Authenticate, inspect cluster nodes, and provision a Bhyve VM:

```sh
sylve login https://sylve.example.test
sylve node list
sylve vm list
sylve vm create web-01 --pool zroot --memory 2G --disk-size 20G
sylve jail list -f json
sylve jail console 201     # interactive jail console; press Enter, then type ~. to detach
```

Run the development and test targets:

```sh
make test       # unit tests
make lint       # ruff + pylint
make format     # ruff format + fixes
make type       # mypy
make live-test  # read-only contract suite against a live Sylve node
make man        # render docs/man/man1/sylve.1 and docs/man/man5/sylve-config.5
make tox        # full test matrix
```

## SEE ALSO

[sylve-docs(7)](docs/index.md),
[sylve-options(7)](docs/global-options.md),
[sylve-devel(7)](docs/developer-guide.md),
[sylve-testing(7)](TESTING.md),
[sylve-contributing(7)](CONTRIBUTING.md),
[sylve-licences(7)](THIRD-PARTY-LICENCES.md),
[CHANGELOG](CHANGELOG.md),
[spec drift notes](docs/spec-drift.md),
[sylve(1)](docs/man/man1/sylve.1),
[sylve-config(5)](docs/man/man5/sylve-config.5)
