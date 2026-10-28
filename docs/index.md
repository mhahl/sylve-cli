# sylve-cli documentation

## NAME

`sylve-cli` — index of command guides and installed manual pages

## DESCRIPTION

`sylve` is a command-line client for Sylve FreeBSD clusters, managing Bhyve
virtual machines, jails, networking, ZFS storage, backups, HA replication, and
host maintenance.

`sylve-cli` is an independent tool and is not affiliated with or endorsed by
the Sylve project.

## COMMAND GUIDES

These links lead to Markdown guides. Only `sylve(1)` and `sylve-config(5)`
are installed as pages for `man(1)`.

| Guide | Description |
|---|---|
| [Overview](../README.md) | Installation, global options, and quick start |
| [login](commands/login.md) | Authenticate and save a context |
| [logout](commands/logout.md) | Revoke the active token and clear it |
| [whoami](commands/whoami.md) | Display the active session and token status |
| [config](commands/config.md) | Manage saved contexts |
| [cluster](commands/cluster.md) | Cluster status, join/leave, Raft, and notes |
| [node](commands/node.md) | Node inventory, telemetry, drain, reboot, and audit logs |
| [vm](commands/vm.md) | Bhyve VMs, snapshots, and templates (hidden alias: `server`) |
| [jail](commands/jail.md) | FreeBSD jails, snapshots, bootstraps, and templates |
| [network](commands/network.md) | Interfaces, switches, routes, DHCP, PF, and WireGuard |
| [download](commands/download.md) | ISO and image downloads, uploads, and signed URLs |
| [replication](commands/replication.md) | HA replication policies, failovers, and events |
| [backup](commands/backup.md) | Backup targets, jobs, events, and restores |
| [zfs](commands/zfs.md) | Pools, datasets, snapshots, and periodic snapshot jobs |
| [task](commands/task.md) | Guest lifecycle tasks and migration cancellation |
| [system](commands/system.md) | Disks, SMART, PCI passthrough, files, certificates, and settings |
| [samba](commands/samba.md) | Samba global configuration and shares |
| [iscsi](commands/iscsi.md) | iSCSI initiators, targets, LUNs, and portals |
| [ddns](commands/ddns.md) | Dynamic DNS entries |
| [mdns](commands/mdns.md) | mDNS configuration and records |
| [notifications](commands/notifications.md) | Notification transports, rules, and active notifications |
| [user](commands/user.md) | Local, PAM, and imported users, plus passkeys |
| [group](commands/group.md) | Authentication groups and members |
| [auth](commands/auth.md) | Login configuration, SSE tokens, and passkeys |
| [cloud-init](commands/cloud-init.md) | Reusable cloud-init templates |

## INSTALLED MANUAL PAGES

| Manual | Description |
|---|---|
| [sylve(1)](man/man1/sylve.1) | Installed command reference |
| [sylve-config(5)](man/man5/sylve-config.5) | Roff manual page for `~/.config/sylve/config.yaml` |

## OTHER GUIDES

| Guide | Description |
|---|---|
| [Options](global-options.md) | Global flags, output formats, environment variables, config format, exit status |
| [Development](developer-guide.md) | Development setup, source layout, adding commands, and regenerating manpages |
| [Testing](../TESTING.md) | Unit tests, live OpenAPI contract suite, linting, and type checks |
| [Contributing](../CONTRIBUTING.md) | Bug reports, pull requests, and AI usage policy |
| [Licences](../THIRD-PARTY-LICENCES.md) | Third-party dependency licences |

## SEE ALSO

[sylve(1)](man/man1/sylve.1),
[sylve-config(5)](man/man5/sylve-config.5),
[LICENSE](../LICENSE)
