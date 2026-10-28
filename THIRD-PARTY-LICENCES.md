# Third-party licences

`sylve-cli` is distributed under the BSD 2-Clause licence. It depends on the
following packages.

## Runtime dependencies

| Package | Constraint | Licence |
|---|---|---|
| typer | `>=0.12.0` | MIT |
| click | `>=8.1.0` | BSD-3-Clause |
| httpx | `>=0.25.0` | BSD-3-Clause |
| rich | `>=13.0.0` | MIT |
| PyYAML | `>=6.0` | MIT |

## Build dependencies

| Package | Constraint | Licence |
|---|---|---|
| setuptools | `>=69` | MIT |
| wheel | any | MIT |

## Test dependencies (`.[test]`)

| Package | Constraint | Licence |
|---|---|---|
| pytest | `>=8.0` | MIT |
| pytest-cov | `>=5.0` | MIT |

## Development dependencies (`.[dev]`)

| Package | Constraint | Licence |
|---|---|---|
| pytest | `>=8.0` | MIT |
| pytest-cov | `>=5.0` | MIT |
| pylint | `>=3.2,<3.3` | GPL-2.0-or-later |
| mypy | `==1.11.2` | MIT |
| tox | `>=4.15` | MIT |
| build | `>=1.2` | MIT |

## Host tools

`ruff` is expected on `PATH` for linting and formatting; install it from the
system package manager or `pipx` on platforms without a wheel.

## Verify this list

The runtime list is declared in `pyproject.toml`. Licences were read from
installed package metadata:

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

`build` is not installed in every development environment. Its MIT licence is
from its published package metadata.

`pip-licenses` produces the same result for installed packages:

```sh
python3 -m pip install pip-licenses
pip-licenses --format=markdown
```
