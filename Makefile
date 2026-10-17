PYTHON := .venv/bin/python
RUFF := .venv/bin/ruff

.PHONY: install test test-integration test-all lint format run clean

install:
	$(PYTHON) -m pip install -r requirements-dev.txt
	.venv/bin/pre-commit install

test:
	$(PYTHON) -m pytest -q tests/unit tests/security

test-integration:
	$(PYTHON) -m pytest -q tests/integration

test-all:
	$(PYTHON) -m pytest -q

lint:
	$(RUFF) check .

format:
	$(RUFF) format .

run:
	$(PYTHON) app.py

clean:
	find . -type d \( -name __pycache__ -o -name .pytest_cache \) -prune -exec rm -rf {} +
	find . -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete
