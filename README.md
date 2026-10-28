# sylve-cli

Command-line client for Sylve FreeBSD clusters, Bhyve VMs, Jails, ZFS,
networking, backups, and node maintenance.

## Install

```sh
pip install .
```

Or from the FreeBSD port:

```sh
cd packaging/freebsd/sysutils/py-sylve-cli
make package
pkg add work/pkg/py312-sylve-cli-0.3.1.pkg
```

## Use

```sh
sylve login https://sylve.example.test
sylve node list
sylve vm list
sylve vm create web-01 --pool zroot --memory 2G --disk-size 20G
sylve jail list -f json
```

Full user documentation is installed as manpages:

```sh
man sylve
man sylve-config
```

Manpage sources live in `docs/man/src/`. Regenerate them with `make man`.

## Development

```sh
make test       # unit tests
make lint       # ruff + pylint
make format     # ruff format + fixes
make type       # mypy
make live-test  # tests against a real Sylve system
make tox        # full matrix
```

See [TESTING.md](TESTING.md) for live-test environment variables and exact
commands.
