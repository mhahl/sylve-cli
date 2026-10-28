# Developer guide

## Set up

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
```

Python 3.10 or newer is required.

## Run unit tests

Unit tests use no network.

```sh
make test
```

Equivalent:

```sh
pytest tests/unit
```

## Run live tests

Live tests need a Sylve server and a valid token.

```sh
export SYLVE_LIVE=1
export SYLVE_SERVER=https://sylve.example.test
export SYLVE_TOKEN=eyJhbGciOi...
export SYLVE_INSECURE=1          # optional
export SYLVE_NODE=node1.example.test  # optional
export SYLVE_SWAGGER=docs/swagger.json  # optional

make live-test
```

Equivalent:

```sh
pytest -m live tests/live
```

The live suite is read-only by default. It runs every command with `--help` and
executes read-only commands. Responses are validated against
`docs/swagger.json`.

Skip live tests:

```sh
pytest -m "not live"
```

## Lint and type checks

```sh
make lint
make type
make tox
```

`make lint` runs `ruff check`, `ruff format --check`, and `pylint --errors-only`.
`make tox` runs the configured test matrix.

## Regenerate manpages

Edit the sources in `docs/man/src/`, then:

```sh
make man
```

This runs `python scripts/build_man.py` and writes:

- `docs/man/man1/sylve.1`
- `docs/man/man5/sylve-config.5`

Check that rendered files are current:

```sh
python scripts/build_man.py --check
```

The API contract is `docs/swagger.json`. Generic commands accept request bodies
from that contract through `--data`.

## Where the code lives

| Path | Purpose |
|---|---|
| `src/sylve_cli/main.py` | Console entry point `run()`, root options, command registration |
| `src/sylve_cli/state.py` | Shared `CLIState`, common option annotations |
| `src/sylve_cli/client.py` | HTTP client, authentication, error types |
| `src/sylve_cli/config.py` | Contexts, tokens, config file |
| `src/sylve_cli/formatter.py` | Table, JSON, YAML, value, and CSV output |
| `src/sylve_cli/tasks.py` | Lifecycle, replication, and backup task polling |
| `src/sylve_cli/commands/auth.py` | `login`, `logout`, `whoami`, `config` |
| `src/sylve_cli/commands/cluster.py` | `cluster` |
| `src/sylve_cli/commands/node.py` | `node` |
| `src/sylve_cli/commands/vm.py` | `vm` and `server` |
| `src/sylve_cli/commands/vm_create.py` | `vm create` |
| `src/sylve_cli/commands/jail.py` | `jail` |
| `src/sylve_cli/commands/network.py` | `network` |
| `src/sylve_cli/commands/download.py` | `download` |
| `src/sylve_cli/commands/replication.py` | `replication` |
| `src/sylve_cli/commands/backup.py` | `backup` |
| `src/sylve_cli/commands/zfs.py` | `zfs` |
| `src/sylve_cli/commands/task.py` | `task` |
| `src/sylve_cli/commands/extras.py` | `system`, `samba`, `iscsi`, `ddns`, `mdns`, `notifications`, `user`, `group`, `auth`, `cloud-init`, and generic API commands |

The installed `sylve` command points to `sylve_cli.main:run` in
`pyproject.toml`.

## Add a command

1. Add or extend a `typer.Typer` app in `src/sylve_cli/commands/`.
2. Register it in `src/sylve_cli/main.py`.
3. Use `FormatOption`, `ColumnsOption`, `NodeOption`, `WaitOption`, and the
   other annotations from `state.py` where applicable.
4. Add a unit test in `tests/unit/`.
5. Add or update the page in `docs/commands/` and the manpage source if the
   change is user-visible.

Generic API commands are registered in `extras.py` with `_add(...)`. They share
`--data`, `--param`, `--node`, `--format`, and `-y`.
