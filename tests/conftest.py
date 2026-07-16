from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CONFIG_DIR = REPO / "config"


@pytest.fixture
def config_dir() -> Path:
    return CONFIG_DIR


@pytest.fixture(autouse=True)
def _block_trend_network(monkeypatch):
    """Keep the suite hermetic: the external trend providers (hackernews, gdelt,
    huggingface) call `get_text` at prepare() time. Trends are enabled in the
    shipped config, so any test that runs `filter_prescore.run()`/`gather` with
    the real config would otherwise make live HTTP calls (and hang on retries).

    This autouse guard replaces each provider module's `get_text` with a wrapper
    that raises `FetchError` immediately when called WITHOUT an injected transport
    (i.e. a real network call). Tests that pass an `httpx.MockTransport` via
    `RunContext.transport` (e.g. tests/test_trends_external.py) still exercise the
    real code path. The scorer catches the FetchError and degrades gracefully, so
    guarded runs behave exactly as they would when the APIs are unreachable.
    """
    from scripts.lib import fetch_http
    from scripts.lib.trends import gdelt, hackernews, huggingface

    real_get_text = fetch_http.get_text

    def guarded(url, *, transport=None, **kwargs):
        if transport is None:
            raise fetch_http.FetchError(f"blocked live trend fetch in tests: {url}")
        return real_get_text(url, transport=transport, **kwargs)

    for mod in (gdelt, hackernews, huggingface):
        monkeypatch.setattr(mod, "get_text", guarded)
