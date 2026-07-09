.PHONY: install test lint

install:
	pip install -e ".[dev]"

test:
	pytest -q

lint:
	ruff check scripts tests
