# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
`docs/swagger.json` (also 0.3.1). When the Sylve project advances its API
version, this project's version advances to match.
