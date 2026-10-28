# SYLVE-LICENCES(7)

## NAME

`sylve-licences` — third-party dependency licence inventory for `sylve-cli`

## DESCRIPTION

`sylve-cli` is distributed under the BSD 2-Clause licence ([LICENSE](LICENSE)).
This manual lists the direct runtime, build, test, and development
dependencies declared in `pyproject.toml` and their licences.

## RUNTIME DEPENDENCIES

| Package | Constraint | Licence |
|---|---|---|
| `typer` | `>=0.12.0` | MIT |
| `click` | `>=8.1.0` | BSD-3-Clause |
| `httpx` | `>=0.25.0` | BSD-3-Clause |
| `rich` | `>=13.0.0` | MIT |
| `PyYAML` | `>=6.0` | MIT |

## BUILD DEPENDENCIES

| Package | Constraint | Licence |
|---|---|---|
| `setuptools` | `>=69` | MIT |
| `wheel` | any | MIT |

## TEST DEPENDENCIES (`.[test]`)

| Package | Constraint | Licence |
|---|---|---|
| `pytest` | `>=8.0` | MIT |
| `pytest-cov` | `>=5.0` | MIT |

## DEVELOPMENT DEPENDENCIES (`.[dev]`)

| Package | Constraint | Licence |
|---|---|---|
| `pytest` | `>=8.0` | MIT |
| `pytest-cov` | `>=5.0` | MIT |
| `pylint` | `>=3.2,<3.3` | GPL-2.0-or-later |
| `mypy` | `==1.11.2` | MIT |
| `tox` | `>=4.15` | MIT |
| `build` | `>=1.2` | MIT |

`ruff` is expected on `PATH` for linting and formatting; install it from the
system package manager or `pipx`.

## EXAMPLES

Inspect licence metadata from installed packages in the active Python
environment:

```sh
python3 - <<'PY'
from importlib.metadata import PackageNotFoundError, metadata, version

for name in [
    "typer", "click", "httpx", "rich", "PyYAML",
    "pytest", "pytest-cov", "pylint", "mypy", "tox", "build",
]:
    try:
        meta = metadata(name)
    except PackageNotFoundError:
        print(name, "not installed")
        continue
    print(name, version(name), meta.get("License-Expression") or meta.get("License"))
PY
```

`build` may not be installed in every environment; its MIT licence is recorded
from its published package metadata.

Generate the same report with `pip-licenses`:

```sh
python3 -m pip install pip-licenses
pip-licenses --format=markdown
```

## FILES

- `pyproject.toml` — canonical dependency declarations.
- `LICENSE` — BSD 2-Clause project licence.

## SEE ALSO

[sylve(1)](README.md),
[sylve-contributing(7)](CONTRIBUTING.md)
