# Swagger Spec Mismatches

The upstream Swagger spec at `docs/swagger.json` is downloaded from
AlchemillaHQ/Sylve by `scripts/fetch_swagger.py` (run via `make swagger`).

After download, **3 known upstream mismatches are patched automatically** so
the spec matches what the server actually returns. The remaining failures below
are server-side behaviour issues (missing params, uninitialised services,
non-JSON endpoints) that the spec cannot fix.

## Automatically patched (scripts/fetch_swagger.py)

| Model | Field | Upstream declares | Server sends | Patch |
|-------|-------|-------------------|--------------|-------|
| `time.Duration` | (used in AuditRecord.duration) | `enum` with named constants (1, 1000, 1000000, …) | Raw nanosecond int (e.g. `238000000`) | Remove enum constraint |
| `IPv4.ip` / `IPv4.broadcast` | `ip`, `broadcast` | `array` of `integer` | Dotted-quad string (`"10.0.0.1"`) | Change to `type: string` |
| `IPv6.ip` / `IPv6.broadcast` | `ip`, `broadcast` | `array` of `integer` | String address | Change to `type: string` |
| `ManagedCertificateOperation` | `issuanceOperation` | `enum ["initial", "renewal"]` | `""` (empty string for pending certs) | Add `""` to enum |

## Remaining failures (not spec mismatches)

These are server-side issues the CLI cannot control. They fail in the live
tests because the endpoint returns an error or non-JSON content.

### Missing-parameter errors (HTTP 400)

| Test | Error |
|------|-------|
| `node summary-delta` | `missing cpuAfter` — delta endpoint needs a cursor |
| `download storage` | `missing_required_params` |
| `zfs dataset paginated` | `DatasetType` field required |
| `zfs dashboard-delta` | `missing poolAfter` — delta endpoint needs a cursor |

### Non-JSON responses (endpoint returned plain text)

| Test | Error |
|------|-------|
| `network interface l3` | Returns plain string instead of JSON |
| `task show 78` | Returns plain string — hardcoded task ID 78 doesn't exist on this server |

### Not-initialised (HTTP 404)

| Test | Error |
|------|-------|
| `network wireguard status` | `wireguard_server_not_initialized` — WireGuard not set up on this node |