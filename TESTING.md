# Testing

```sh
python3 -m pip install -e '.[dev]'
```

## Unit tests

Fast, isolated, no network.

```sh
make test
# or
pytest tests/unit
```

## Live tests

Run against a real Sylve node or cluster.

```sh
export SYLVE_LIVE=1
export SYLVE_SERVER=https://sylve.example.test
export SYLVE_TOKEN=eyJ...
# optional
export SYLVE_INSECURE=1
export SYLVE_NODE=node1.example.test
export SYLVE_SWAGGER=docs/swagger.json

make live-test
# or
pytest -m live tests/live
```

The live suite is read-only by default. It runs every command with `--help`
and executes the read-only commands against the target. Destructive commands
are not run automatically.

Every HTTP response made by the live suite is validated against the
`docs/swagger.json` response schema. A response that does not match the
swagger contract fails with the method, path, and schema error.

Skip live tests with:

```sh
pytest -m "not live"
```

## Lint, type checks, packaging

`make lint` and the tox `lint` environment expect `ruff` on `PATH`
(for example `pkg install ruff` or `pipx install ruff`).

```sh
make lint
make type
make tox
```

## Manpages

```sh
make man
man sylve
man sylve-config
```

Manpage sources: `docs/man/src/*.in`.
Rendered files: `docs/man/man1/`, `docs/man/man5/`.
