# Changelog

This file documents all notable changes to this project.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Typed `jail create` command with flags, `--file`, `--set`, `--dry-run`,
  and a confirmation plan, mirroring `vm create`. The CLI parses sizes like
  `2G` to bytes and resolves pool/switch/bootstrap names against the server.
- `--set KEY=VALUE` (`-s`, `--property`) on all generic write commands:
  schema-aware per-field updates with dotted keys for nesting, repeatable or
  comma-separated `k=v` pairs for lists and nested objects, and string-preserving
  type coercion (e.g. `jail hardware cpu 201 --set cores=4`), so small updates
  need no JSON.
- Unified `<noun> <verb>` sub-groups (`vm hardware|network|storage|options|template`,
  `jail hardware|network|options|template|bootstrap`, `network dhcp range|lease`,
  `network firewall traffic|nat|advanced`, `network wireguard server|peer|client`,
  `system note|disk|ppt|tunable|file|cert`, `samba share`, `iscsi initiator|target`,
  `mdns record`, `notifications rule|transport`, `user passkey`, `auth passkey`,
  `cloud-init template`) with `list`/`show`/`create`/`set`/`delete` verbs.
- `--dry-run` on all generic API commands: print `method`, `path`, `params`,
  and `body` without sending anything.
- Every generic command's `--help` now lists its settable `--set` body fields
  and `--param` query parameters with types and required markers, generated
  from `docs/swagger.json` by `make schemas` (`scripts/build_schemas.py`).
- `examples/jail/basic.yaml` starter definition for `jail create --file`.

### Changed
- `jail create` no longer takes a raw `--data` body; use flags, `--file`
  (the old `--data @jail.yaml` file works as `--file jail.yaml`), or `--set`.
  Generic `--data` remains as an escape hatch for the other commands.
- Every command guide now carries `--set`-based examples with `--dry-run`
  previews, selection-flag usage, and multi-step flows; we corrected stale
  examples to the `swagger.json` contract (real body fields, no invented
  `--param validate/dryRun/sendWelcome`, `-y/--yes` scoped to destructive
  commands only).

### Fixed
- Output conventions are now uniform: every list takes `-c/--column`,
  `--sort-column`, `--filter`, and `-l/--limit` (server-paginated lists keep
  their native `--limit` and add the rest); power actions (`vm/jail
  start/stop/restart`) and snapshot/rename/capture/restore commands emit pure
  machine output under `-f json|yaml|csv|value` instead of mixing prose into
  stdout; `vm/jail migrate --validate-only` honors `-f`; `node drain` prints
  no prose on non-table formats.
- `-p` no longer means `--password` on `login` (long form only), so `-p`
  means `--param`/`--port`/`--pool` elsewhere and secrets stay
  out of `ps` and shell history by default.
- `jail/vm console` and `system terminal` no longer freeze when the connection
  goes quiet or dies: TCP keepalive plus a periodic client ping keeps idle
  sessions alive through NATs/proxies, the CLI bounds reads so `~.` detach keeps
  working, and a lost connection prints an error instead of hanging.
- A generic command run with no path argument, body, or parameters prints its
  `--help` instead of erroring (like a bare command group); anything else
  supplied with a wrong path-argument count is a usage error (exit `2`).

## [0.3.1] - 2026-10-30

### Added
- Open VM VNC consoles in a local viewer, refusing VNC for VMs that are not running.
- Attach to an interactive host terminal over WebSocket.
- Attach to an interactive jail console; press Enter then `~.` to detach.
- SSE event streaming (`system events`) and live firewall log following
  (`network firewall logs`) with a short-lived `sse_token` capability.
- `vm create` from a YAML/JSON configuration file or a VM template, with
  dry-run, cloud-init, VNC, PCI passthrough, and storage-mapping options.
- `cluster note show` and `system notes-show` commands.
- Timestamps normalized to a fixed width in table output.
- Unit tests for VM create payload normalization, extras request helpers,
  client error contracts, config token handling, and task polling fallback.
  `examples/` now tracked in version control.
- Opt-in live mutation tests (`make live-mutate`) that create, start, migrate,
  and delete throwaway VMs and jails against a real cluster, cleaning up on
  every path and searching all nodes for resources that migrated away.
- CI dependency audit (`pip-audit`) job.
- `docs/spec-drift.md` documenting tracked-Swagger vs production differences.

### Fixed
- `network interface l3` now raises a clear error when the server answers with
  an HTML page (endpoint not implemented) instead of printing HTML as data.
- Live-test OpenAPI validator tolerates null optional fields and rejects
  non-JSON response bodies instead of validating HTML as data.
- `~.` detach in the jail console when keys arrive in separate packets.
- Resolve lifecycle tasks through the active/recent list endpoints on older
  servers that do not serve the single-task endpoint.
- Refuse VNC for VMs that are not running.

### Changed
- Read VM state from the live cluster summary.
- Default VM NICs to virtio and report guest IPs; request 32bpp for KRDC
  viewers.
- Keep the VNC bridge up across viewer reconnects.
- Modernized tests, packaging, and documentation (manual-style pages with
  examples and cross-links).

## Version tracking

`sylve-cli` releases mirror the Sylve server API version it targets. The
current release, 0.3.1, corresponds to the Sylve API contract in
`docs/swagger.json` (also 0.3.1). This project's version advances whenever the
Sylve API version advances.
