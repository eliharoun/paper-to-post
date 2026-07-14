.PHONY: install test lint

install:
	# SETUPTOOLS_USE_DISTUTILS=local forces setuptools' bundled distutils. Without
	# it, a shell exporting SETUPTOOLS_USE_DISTUTILS=stdlib breaks the build backend
	# on Python 3.12+ (stdlib distutils was removed), so `pip install -e` fails.
	SETUPTOOLS_USE_DISTUTILS=local pip install -e ".[dev]"

test:
	pytest -q

lint:
	ruff check scripts tests
