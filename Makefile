.PHONY: test lint format live-test live-mutate tox man type

PYTHON != command -v python3 2>/dev/null || command -v python3.12 2>/dev/null || command -v python

test:
	$(PYTHON) -m pytest tests/unit

lint:
	ruff check src tests
	ruff format --check src tests
	$(PYTHON) -m pylint --errors-only src/sylve_cli

format:
	ruff format src tests
	ruff check --fix src tests

type:
	$(PYTHON) -m mypy

live-test:
	$(PYTHON) -m pytest -m live tests/live

live-mutate:
	$(PYTHON) -m pytest -m live_mutate tests/live/test_mutate.py

tox:
	$(PYTHON) -m tox

man:
	$(PYTHON) scripts/build_man.py
