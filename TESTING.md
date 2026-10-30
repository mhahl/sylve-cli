# SYLVE-TESTING(7)

## NAME

`sylve-testing` — unit, live contract, lint, and manual page verification for `sylve-cli`

## SYNOPSIS

```sh
python3 -m pip install -e '.[dev]'
make test
make live-test
make lint
make type
make man
make tox
```

## DESCRIPTION

The `sylve-cli` test suite is divided into two layers:

1. **Unit tests** (`tests/unit/`), which run offline against mocked HTTP
   transports and temporary configuration files.
2. **Live contract tests** (`tests/live/`), which run against a real Sylve
   node or cluster and validate successful HTTP response payloads against the
   OpenAPI/Swagger schema in `docs/swagger.json`.

### Unit Tests

Unit tests require no network access or external services:

```sh
make test
# or
pytest tests/unit
```

### Live Contract Tests

The live suite is read-only by default. It invokes `--help` on every registered
command, executes read-only commands against the target server, and validates
successful HTTP response payloads against `docs/swagger.json`. Any schema
mismatch fails the test with the HTTP method, path, and validation error.
Destructive commands are not executed automatically.

```sh
export SYLVE_LIVE=1
export SYLVE_SERVER=https://sylve.example.test
export SYLVE_TOKEN=eyJ...
# optional overrides
export SYLVE_INSECURE=1
export SYLVE_NODE=node1.example.test
export SYLVE_SWAGGER=docs/swagger.json

make live-test
# or
pytest -m live tests/live
```

Exclude live tests explicitly when invoking `pytest` directly:

```sh
pytest -m "not live"
```

### Live Mutation Tests

An opt-in suite in `tests/live/test_mutate.py` creates throwaway VMs (and their
snapshots) and deletes them again. It is marked `live_mutate`, so the normal
`live` run never collects it. Every resource is named `zclitest-*` and is
deleted in fixture teardown even when a check fails. It also requires an
explicit node and pool, so it cannot touch production by accident:

```sh
export SYLVE_LIVE=1
export SYLVE_LIVE_MUTATE=1
export SYLVE_NODE=node1.example.test
export SYLVE_LIVE_POOL=zroot
make live-mutate
# or
pytest -m live_mutate tests/live/test_mutate.py
```

Jail lifecycle mutation (`tests/live/test_mutate_jails.py`) additionally needs a
node with an existing pkgbase bootstrap, a pool, a bootstrap name, and a network
switch:

```sh
export SYLVE_LIVE_JAIL_NODE=node1.example.test
export SYLVE_LIVE_JAIL_POOL=zroot
export SYLVE_LIVE_JAIL_BOOTSTRAP=15-1-Base
export SYLVE_LIVE_JAIL_SWITCH=example-switch
```

Both suites create→start→migrate→delete their resources. VM migration uses
`SYLVE_LIVE_MIGRATE_TARGET` (a node other than `SYLVE_NODE`); jail creation uses
the `SYLVE_LIVE_JAIL_*` variables. Cleanup searches every online node, so a
resource that migrated away is still found and deleted.

### Lint, Type Checking, and Matrix

`make lint` and the `tox` lint environment require `ruff` on `PATH` (for
example via `pkg install ruff` or `pipx install ruff`).

```sh
make lint
make type
make tox
```

### Manual Pages

Render and verify the roff manual pages:

```sh
make man
python3 scripts/build_man.py --check
man docs/man/man1/sylve.1
man docs/man/man5/sylve-config.5
```

## ENVIRONMENT

- `SYLVE_LIVE` — set to `1` to enable `tests/live/`.
- `SYLVE_SERVER` — target Sylve base URL for live tests.
- `SYLVE_TOKEN` — bearer token for live tests.
- `SYLVE_INSECURE` — set to `1` to skip TLS verification during live tests.
- `SYLVE_NODE` — optional target node hostname or UUID for live tests.
- `SYLVE_SWAGGER` — path to the Swagger contract (default: `docs/swagger.json`).

## FILES

- `tests/unit/` — offline unit and CLI tests.
- `tests/live/` — live read-only API contract tests.
- `docs/swagger.json` — Sylve OpenAPI/Swagger schema contract.
- `docs/man/src/*.in` — roff manual page sources.
- `docs/man/man1/sylve.1`, `docs/man/man5/sylve-config.5` — rendered manual pages.

## SEE ALSO

[sylve(1)](README.md),
[sylve-devel(7)](docs/developer-guide.md),
[sylve-contributing(7)](CONTRIBUTING.md)
