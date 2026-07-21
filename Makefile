.PHONY: install test test-py test-js lint

install:
	# SETUPTOOLS_USE_DISTUTILS=local forces setuptools' bundled distutils. Without
	# it, a shell exporting SETUPTOOLS_USE_DISTUTILS=stdlib breaks the build backend
	# on Python 3.12+ (stdlib distutils was removed), so `pip install -e` fails.
	SETUPTOOLS_USE_DISTUTILS=local pip install -e ".[dev]"

test: test-py test-js

test-py:
	pytest -q

# Pure-logic unit tests for the .mjs Composio scripts (publish idempotency, insights
# parsing). No deps — Node's built-in test runner. The scripts import these same
# modules, so the tested code is the code that runs.
test-js:
	node --test tests/js/

lint:
	ruff check scripts tests
