# Sylve API contract drift (tracked spec vs. production 0.3.1)

> Findings from running the live test suite against the production cluster
> (2026-10-30). `docs/swagger.json` is generated from the upstream Sylve repo,
> so these are reported upstream rather than edited here.

## Summary

The bundled `docs/swagger.json` (Sylve API 0.3.1) disagrees with the running
production cluster in three ways. The live OpenAPI validator flags all of them.

## 1. Phantom endpoints — spec documents routes that return the HTML web-UI shell

These paths return **HTTP 200 with a `text/html`** body (the SvelteKit catch-all)
instead of the documented JSON:

| Method | Path |
|---|---|
| GET | `/network/interface/l3` |
| GET | `/network/interface/l3/pending` |
| GET | `/network/interface/{name}/l3` |
| GET | `/tasks/lifecycle/{taskId}` |

A 2xx-with-HTML response is indistinguishable from success unless the caller
checks the content type. The CLI never prints raw HTML: `network interface l3`
now raises a clear "endpoint not implemented" error, and task lookup falls back
to the list endpoints (`/tasks/lifecycle/active`, `/tasks/lifecycle/recent`).

**Ask (upstream):** implement these routes or return a proper JSON `4xx` (e.g.
`404 {"status":"error","message":"not_found"}`) instead of the HTML shell, so
clients can detect them.
**Ask (here):** the `swagger.json` refresh should not re-introduce these until
the server implements them.

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