# sylve-cli

Command-line client for Sylve FreeBSD clusters: VMs, jails, networking, ZFS,
backups, replication, and node maintenance.

`sylve-cli` is an independent tool. It is not affiliated with or endorsed by the
Sylve project.

## Contents

- [Commands](#commands)
- [Guides](#guides)
- [Project](#project)

## Commands

| Command | Purpose |
|---|---|
| [login](commands/login.md) | Authenticate and save a context |
| [logout](commands/logout.md) | Revoke the token and clear it |
| [whoami](commands/whoami.md) | Show the current session |
| [config](commands/config.md) | Manage saved contexts |
| [cluster](commands/cluster.md) | Cluster status, join/leave, Raft, notes |
| [node](commands/node.md) | Node inventory, telemetry, drain, reboot, audit logs |
| [vm](commands/vm.md) | Bhyve VMs, snapshots, templates (hidden alias: `server`) |
| [jail](commands/jail.md) | FreeBSD jails, snapshots, bootstraps, templates |
| [network](commands/network.md) | Interfaces, switches, routes, DHCP, PF, WireGuard |
| [download](commands/download.md) | ISO and image downloads, uploads, signed URLs |
| [replication](commands/replication.md) | HA replication policies and events |
| [backup](commands/backup.md) | Backup targets, jobs, events, restores |
| [zfs](commands/zfs.md) | Pools, datasets, snapshots, periodic jobs |
| [task](commands/task.md) | Lifecycle tasks and migration cancellation |
| [system](commands/system.md) | Disks, SMART, PCI passthrough, files, certificates, settings |
| [samba](commands/samba.md) | Samba configuration and shares |
| [iscsi](commands/iscsi.md) | iSCSI initiators, targets, LUNs, portals |
| [ddns](commands/ddns.md) | Dynamic DNS entries |
| [mdns](commands/mdns.md) | mDNS configuration and records |
| [notifications](commands/notifications.md) | Transports, rules, active notifications |
| [user](commands/user.md) | Local, PAM, imported users and passkeys |
| [group](commands/group.md) | Authentication groups and members |
| [auth](commands/auth.md) | Login configuration, SSE tokens, passkeys |
| [cloud-init](commands/cloud-init.md) | Reusable cloud-init templates |

## Guides

- [Global and common options](global-options.md): option placement, output
  formats, environment variables, config file, exit codes.
- [Developer guide](developer-guide.md): setup, tests, lint, manpages, source
  layout.

## Project

- [README](../README.md): install and quick start.
- [CONTRIBUTING](../CONTRIBUTING.md): bug reports, pull requests, AI usage
  policy.
- [LICENSE](../LICENSE): BSD 2-Clause.
- [THIRD-PARTY-LICENCES](../THIRD-PARTY-LICENCES.md): dependency licences.
- [TESTING](../TESTING.md): unit, live, lint, and packaging commands.
- [sylve(1) manpage](man/man1/sylve.1): installed reference page.
- [sylve-config(5) manpage](man/man5/sylve-config.5): configuration reference.
