# Sylve API contract drift (tracked spec vs. production 0.3.1)

> Findings from running the live test suite against the production cluster
> (2026-10-30). `docs/swagger.json` is generated from the upstream Sylve repo,
> so these are reported upstream rather than edited here.

## Summary

The bundled `docs/swagger.json` (Sylve API 0.3.1) disagrees with the running
production cluster in three ways. The live OpenAPI validator flags all of them,
and sections 4 and 5 record API design gaps where the spec is accurate but the
surface is incomplete.

## 1. Phantom endpoints — spec documents routes that return the HTML web-UI shell

These paths return **HTTP 200 with a `text/html`** body (the SvelteKit catch-all)
instead of the documented JSON:

| Method | Path |
|---|---|
| GET | `/network/interface/l3` |
| GET | `/network/interface/l3/pending` |
| GET | `/network/interface/{name}/l3` |
| GET | `/tasks/lifecycle/{taskId}` |

The layer-3 (`l3`) routes are **implemented on the Sylve master branch but are
not part of the 0.3.1 release**; the vendored `swagger.json` is generated from
master, so it documents them while the 0.3.1 server serves the HTML shell for
anything not yet released behind them. Confirm a node runs a linked-Sylve build
before expecting `network interface l3` to return JSON. The
`/tasks/lifecycle/{taskId}` route is a separate case (the CLI falls back to the
lifecycle list endpoints).

A 2xx-with-HTML response is indistinguishable from success unless the caller
checks the content type. The CLI never prints raw HTML: `network interface l3`
now raises a clear "endpoint not implemented" error, and task lookup falls back
to the list endpoints (`/tasks/lifecycle/active`, `/tasks/lifecycle/recent`).

**Ask (upstream):** return a proper JSON `4xx` (e.g.
`404 {"status":"error","message":"not_found"}`) instead of the HTML shell for
unreleased routes, so clients can detect them.
**Ask (here):** the `swagger.json` refresh should tag master-only endpoints so
spec-vs-release drift is visible instead of surfacing as phantom routes.

## 2. Field type mismatches — spec type differs from the payload

| Endpoint | Field | Spec | Production |
|---|---|---|---|
| `GET /network/interface` | `ipv4[].ip` | `array` | `string` (e.g. `"10.120.14.11"`) |
| `GET /network/interface` | `ipv4[].broadcast` | `array` | `string` (e.g. `"10.120.14.255"`) |

These IPv4 address fields are scalars in production, not arrays.

## 3. Over-restrictive enums — spec enum rejects legitimate values

| Endpoint | Field | Spec enum | Production |
|---|---|---|---|
| `GET /info/audit-records` | `duration` | `[…,1,1000,10⁶,10⁹,6×10¹⁰,3.6×10¹²]` (Go `time.Duration` units) | arbitrary nanoseconds, e.g. `20625903111` |
| `GET /certificates` | `issuanceOperation` | `["initial","renewal"]` | `""` (empty, no managed op yet) |

`duration` should be a plain `int64`, not an enum of `time.Duration` unit
constants. `issuanceOperation` should allow an empty/no-op value.

## 4. Template list omits `createdAt` — API design gap (not a drift)

The simple template list DTOs carry only identifiers and the source name:

| Endpoint | List item shape |
|---|---|
| `GET /vm/templates` | `{id, name, sourceVmName}` |
| `GET /jail/templates` | `{id, name, sourceJailName}` |

The full `VMTemplate`/`JailTemplate` models add `createdAt` (and, for jails,
`pool`), so this is a deliberate "simple" list shape, not a contract violation.
The CLI's `template list` declares a "Created At" column that the list response
can never fill, so the CLI enriches each row from the detail endpoint
(`GET /vm/templates/{id}`), which is N+1 over the cluster.

**Ask (upstream):** add `createdAt` (and jail `pool`) to the simple template
list DTOs — the values are already stored on the same row, so it costs nothing
and removes the CLI's per-template detail fetch.

## 5. Firewall live logs lack parsed protocol / address fields — design gap

`FirewallLiveHitEvent` (validation of `/network/firewall/logs/live`) exposes
`action, bytes, cursor, direction, interface, rawLine, ruleId, ruleName,
ruleType, timestamp` — but no `protocol`, `src`, or `dst`. The CLI's tabular
view shows the raw log line instead, so the gap is masked until `--format
csv|value` (or `--follow`) renders the `Proto`, `Source`, and `Destination`
columns, which then show `-`.

**Ask (upstream):** add `protocol`, `src`, and `dst` to the live hit event, or
the CLI must parse the raw pf/pflog line — brittle across log formats.

## CLI behavior (this repo)

The CLI now tolerates both phantom-endpoint and drift cases without crashing:

- `network interface l3` and the other phantom L3 routes raise a clean
  `SylveError` ("endpoint not implemented") instead of printing HTML.
- `task show <id>` still works via the list-endpoint fallback when the
  single-task route is a phantom.
- The live validator rejects any non-JSON response body as a parse failure,
  never validating HTML as if it were data.

The remaining live-suite failures against 0.3.1 production are the spec-drift
cases above, plus a few test cases that legitimately require query/body
parameters the suite does not send (`node summary-delta`, `zfs dashboard-delta`,
`zfs dataset paginated`, `download storage`, `network wireguard status` when
WireGuard is not initialized).