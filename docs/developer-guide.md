# SYLVE-DEVEL(7)

## NAME

`sylve-devel` — developer manual, source architecture, and command authoring guide for `sylve-cli`

## SYNOPSIS

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
make test lint type man
```

## DESCRIPTION

`sylve-cli` is a Python 3.10+ command-line application built with `typer`,
`httpx`, `rich`, and `PyYAML`. The `sylve` console script entry point is
`sylve_cli.main:run`, declared in `pyproject.toml`.

## SOURCE LAYOUT

| Path | Purpose |
|---|---|
| `src/sylve_cli/main.py` | Console entry point `run()`, root options, command registration |
| `src/sylve_cli/state.py` | Shared `CLIState` and common option type annotations |
| `src/sylve_cli/client.py` | HTTP client, authentication, node routing, error types |
| `src/sylve_cli/config.py` | Context management, JWT inspection, config file I/O |
| `src/sylve_cli/formatter.py` | `table`, `json`, `yaml`, `value`, and `csv` output rendering |
| `src/sylve_cli/console_ws.py` | Stdlib RFC 6455 WebSocket console attach and hex auth payload |
| `src/sylve_cli/tasks.py` | Lifecycle, replication, and backup task polling |
| `src/sylve_cli/commands/auth.py` | `login`, `logout`, `whoami`, `config` |
| `src/sylve_cli/commands/cluster.py` | `cluster` |
| `src/sylve_cli/commands/node.py` | `node` |
| `src/sylve_cli/commands/vm.py` | `vm` and hidden `server` alias |
| `src/sylve_cli/commands/vm_create.py` | `vm create` |
| `src/sylve_cli/commands/jail.py` | `jail` |
| `src/sylve_cli/commands/network.py` | `network` |
| `src/sylve_cli/commands/download.py` | `download` |
| `src/sylve_cli/commands/replication.py` | `replication` |
| `src/sylve_cli/commands/backup.py` | `backup` |
| `src/sylve_cli/commands/zfs.py` | `zfs` |
| `src/sylve_cli/commands/task.py` | `task` |
| `src/sylve_cli/commands/extras.py` | `system`, `samba`, `iscsi`, `ddns`, `mdns`, `notifications`, `user`, `group`, `auth`, `cloud-init`, and generic API bindings |

## ADDING A COMMAND

1. Add or extend a `typer.Typer` application in `src/sylve_cli/commands/`.
2. Register new top-level command groups in `src/sylve_cli/main.py`.
3. Reuse `FormatOption`, `ColumnsOption`, `NodeOption`, `WaitOption`, and
   related annotations from `src/sylve_cli/state.py`.
4. For thin wrappers around endpoints in `docs/swagger.json`, register a
   generic command in `src/sylve_cli/commands/extras.py` with `_add(...)`; it
   automatically provides `--data`, `--param`, `--node`, `--format`, and `-y`.
5. Add unit tests in `tests/unit/`.
6. Update `docs/commands/<command>.md` and `docs/man/src/sylve.1.in`, then run
   `make man`.

## VERIFICATION AND BUILD TARGETS

### Unit Tests

Offline tests with mocked HTTP responses:

```sh
make test
# or
pytest tests/unit
```

### Live Contract Tests

Read-only tests against a live Sylve instance, validated against
`docs/swagger.json`:

```sh
export SYLVE_LIVE=1
export SYLVE_SERVER=https://sylve.example.test
export SYLVE_TOKEN=eyJhbGciOi...
export SYLVE_INSECURE=1                 # optional
export SYLVE_NODE=node1.example.test    # optional
export SYLVE_SWAGGER=docs/swagger.json  # optional

make live-test
```

### Lint and Static Analysis

`make lint` runs `ruff check`, `ruff format --check`, and
`pylint --errors-only`. `make type` runs `mypy`. `make tox` runs the full
configured matrix.

```sh
make lint
make type
make tox
```

### Manual Pages

Edit the roff templates in `docs/man/src/` and render them with:

```sh
make man
python scripts/build_man.py --check
```

This writes `docs/man/man1/sylve.1` and `docs/man/man5/sylve-config.5`.

## FILES

- `pyproject.toml` — package metadata, dependencies, and tool configuration.
- `docs/swagger.json` — Sylve API OpenAPI/Swagger specification.
- `scripts/build_man.py` — manual page renderer and freshness check.

## SEE ALSO

[sylve(1)](../README.md),
[sylve-docs(7)](index.md),
[sylve-testing(7)](../TESTING.md),
[sylve-contributing(7)](../CONTRIBUTING.md)
