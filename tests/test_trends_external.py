from datetime import date
from pathlib import Path

import httpx
import pytest

from scripts.lib.config import SignalConfig, TopicConfig
from scripts.lib.fetch_http import FetchError
from scripts.lib.trends.base import RunContext
from scripts.lib.trends.gdelt import GdeltSignal
from scripts.lib.trends.hackernews import HackerNewsSignal
from scripts.lib.trends.huggingface import HuggingFaceSignal

FIX = Path(__file__).parent / "fixtures" / "trends"


def _transport(body: str):
    return httpx.MockTransport(lambda req: httpx.Response(200, text=body))


def _ctx(tmp_path, transport):
    return RunContext(topic_id="cs", today=date(2026, 7, 15),
                      data_dir=tmp_path, transport=transport)


def _topic():
    return TopicConfig(id="cs", enabled=True, display_name="CS", priority=1.0,
                       keywords=["quantum annealing", "diffusion"])


def test_hackernews_scores_matching_paper(tmp_path):
    body = (FIX / "hn_search.json").read_text()
    sig = HackerNewsSignal(SignalConfig(name="hackernews", params={"min_points": 50}))
    state = sig.prepare([], _topic(), _ctx(tmp_path, _transport(body)))
    hot = sig.score({"title": "a quantum annealing method", "abstract": ""}, state)
    cold = sig.score({"title": "unrelated cryptography lemma", "abstract": ""}, state)
    assert hot is not None and hot > (cold or 0.0)


def test_gdelt_scores_from_volume_ratio(tmp_path):
    body = (FIX / "gdelt_timeline.json").read_text()
    sig = GdeltSignal(SignalConfig(name="gdelt"))
    state = sig.prepare([], _topic(), _ctx(tmp_path, _transport(body)))
    v = sig.score({"title": "a new quantum annealing result", "abstract": ""}, state)
    # fixture: recent 0.5, baseline mean 0.1 -> r=5 -> (5-1)/(5+1) = 0.667
    assert v is not None and abs(v - 0.6667) < 0.01


def test_huggingface_matches_by_arxiv_id(tmp_path):
    body = (FIX / "hf_daily.json").read_text()
    sig = HuggingFaceSignal(SignalConfig(name="huggingface"))
    state = sig.prepare([], _topic(), _ctx(tmp_path, _transport(body)))
    v = sig.score({"arxiv_id": "2607.13034", "title": "x", "abstract": ""}, state)
    assert v == 1.0                          # top-upvoted paper -> normalized 1.0


def test_huggingface_matches_by_term_overlap_when_id_absent(tmp_path):
    body = (FIX / "hf_daily.json").read_text()
    sig = HuggingFaceSignal(SignalConfig(name="huggingface"))
    state = sig.prepare([], _topic(), _ctx(tmp_path, _transport(body)))
    v = sig.score({"arxiv_id": "9999.99999", "title": "world simulation study",
                   "abstract": ""}, state)
    assert v is not None and v > 0.0


def test_hackernews_refine_top_slice_bumps_posted_paper(tmp_path):
    body = (FIX / "hn_search.json").read_text()
    t = httpx.MockTransport(lambda req: httpx.Response(200, text=body))
    sig = HackerNewsSignal(SignalConfig(name="hackernews"))
    ctx = _ctx(tmp_path, t)
    sig.prepare([], _topic(), ctx)           # sets provider's ctx
    bumps = sig.refine_top_slice(
        [{"arxiv_id": "2607.1", "title": "x", "abstract": ""}], "state")
    assert bumps                              # fixture hits have points -> a bump
    assert all(0.0 <= v <= 0.3 for v in bumps.values())


def test_provider_error_raises_cleanly(tmp_path):
    t = httpx.MockTransport(lambda req: httpx.Response(500, text="err"))
    sig = HackerNewsSignal(SignalConfig(name="hackernews"))
    with pytest.raises(FetchError):
        sig.prepare([], _topic(), _ctx(tmp_path, t))


def test_cache_prevents_second_call(tmp_path):
    body = (FIX / "hf_daily.json").read_text()
    calls = {"n": 0}

    def handler(req):
        calls["n"] += 1
        return httpx.Response(200, text=body)

    t = httpx.MockTransport(handler)
    sig = HuggingFaceSignal(SignalConfig(name="huggingface", cache_ttl_min=180))
    sig.prepare([], _topic(), _ctx(tmp_path, t))
    sig.prepare([], _topic(), _ctx(tmp_path, t))     # second run same day
    assert calls["n"] == 1                            # served from cache


def test_gdelt_isolates_failing_keyword(tmp_path):
    good = (FIX / "gdelt_timeline.json").read_text()

    def handler(req):
        # "quantum annealing" succeeds; the other keyword returns a 500
        if "quantum" in req.url.query.decode():
            return httpx.Response(200, text=good)
        return httpx.Response(500, text="err")

    t = httpx.MockTransport(handler)
    sig = GdeltSignal(SignalConfig(name="gdelt"))
    state = sig.prepare([], _topic(), _ctx(tmp_path, t))     # must not raise
    assert state.get("quantum annealing", 0.0) > 0.0        # survivor kept
    assert "diffusion" not in state                          # failing kw dropped


def test_score_returns_none_on_empty_state(tmp_path):
    paper = {"title": "x", "abstract": ""}
    assert HackerNewsSignal(SignalConfig(name="hackernews")).score(paper, {}) is None
    assert GdeltSignal(SignalConfig(name="gdelt")).score(paper, {}) is None
    assert HuggingFaceSignal(SignalConfig(name="huggingface")).score(paper, {}) is None


def test_wikipedia_scores_from_pageview_ratio(tmp_path):
    from scripts.lib.trends.wikipedia import WikipediaSignal
    body = (FIX / "wiki_pageviews.json").read_text()
    sig = WikipediaSignal(SignalConfig(name="wikipedia"))
    state = sig.prepare([], _topic(), _ctx(tmp_path, _transport(body)))
    v = sig.score({"title": "a new diffusion result", "abstract": ""}, state)
    # recent 500 vs baseline mean 100 -> r=5 -> (5-1)/(5+1) = 0.667
    assert v is not None and abs(v - 0.6667) < 0.01


def test_wikipedia_refine_is_noop(tmp_path):
    from scripts.lib.trends.wikipedia import WikipediaSignal
    sig = WikipediaSignal(SignalConfig(name="wikipedia"))
    assert sig.refine_top_slice([{"arxiv_id": "1"}], {"diffusion": 0.5}) == {}


def test_wikipedia_score_none_on_empty_state(tmp_path):
    from scripts.lib.trends.wikipedia import WikipediaSignal
    sig = WikipediaSignal(SignalConfig(name="wikipedia"))
    assert sig.score({"title": "x", "abstract": ""}, {}) is None


def _bsky_router(tmp_path):
    """Transport routing: arxiv-domain query -> arxiv fixture, else keyword fixture."""
    kw_body = (FIX / "bsky_search.json").read_text()
    ax_body = (FIX / "bsky_arxiv.json").read_text()

    def handler(req):
        q = req.url.query.decode()
        if "arxiv" in q:
            return httpx.Response(200, text=ax_body)
        return httpx.Response(200, text=kw_body)

    return httpx.MockTransport(handler)


def test_bluesky_scores_term_heat(tmp_path):
    from scripts.lib.trends.bluesky import BlueskySignal
    sig = BlueskySignal(SignalConfig(name="bluesky"))
    state = sig.prepare([], _topic(), _ctx(tmp_path, _bsky_router(tmp_path)))
    hot = sig.score({"title": "a diffusion study", "abstract": ""}, state)
    cold = sig.score({"title": "unrelated topology proof", "abstract": ""}, state)
    assert hot is not None and hot > (cold or 0.0)


def test_bluesky_exact_arxiv_hit(tmp_path):
    from scripts.lib.trends.bluesky import BlueskySignal
    sig = BlueskySignal(SignalConfig(name="bluesky"))
    state = sig.prepare([], _topic(), _ctx(tmp_path, _bsky_router(tmp_path)))
    v = sig.score({"arxiv_id": "2607.13034", "title": "x", "abstract": ""}, state)
    assert v == 1.0      # seeded from arXiv sweep -> normalized to 1.0


def test_bluesky_refine_bumps_linked_paper(tmp_path):
    from scripts.lib.trends.bluesky import BlueskySignal
    sig = BlueskySignal(SignalConfig(name="bluesky"))
    ctx = _ctx(tmp_path, _bsky_router(tmp_path))
    sig.prepare([], _topic(), ctx)
    bumps = sig.refine_top_slice(
        [{"arxiv_id": "2607.13034", "title": "x", "abstract": ""}], "state")
    assert bumps and all(0.0 <= v <= 0.3 for v in bumps.values())


def test_bluesky_score_none_on_empty_state(tmp_path):
    from scripts.lib.trends.bluesky import BlueskySignal
    sig = BlueskySignal(SignalConfig(name="bluesky"))
    assert sig.score({"title": "x", "abstract": ""},
                     {"heat": {}, "urls": {}}) is None


def _reddit_router():
    """Route token POST, listing GET, and /api/info lookup to their fixtures."""
    token = (FIX / "reddit_token.json").read_text()
    listing = (FIX / "reddit_listing.json").read_text()
    search = (FIX / "reddit_search.json").read_text()

    def handler(req):
        path = req.url.path
        if "access_token" in path:
            return httpx.Response(200, text=token)
        if "/api/info" in path:
            return httpx.Response(200, text=search)
        return httpx.Response(200, text=listing)

    return httpx.MockTransport(handler)


def test_reddit_scores_term_and_exact(tmp_path, monkeypatch):
    from scripts.lib.trends.reddit import RedditSignal
    monkeypatch.setenv("REDDIT_CLIENT_ID", "id")
    monkeypatch.setenv("REDDIT_CLIENT_SECRET", "secret")
    sig = RedditSignal(SignalConfig(
        name="reddit", params={"subreddits": ["MachineLearning"]}))
    state = sig.prepare([], _topic(), _ctx(tmp_path, _reddit_router()))
    exact = sig.score({"arxiv_id": "2607.13034", "title": "x", "abstract": ""}, state)
    term = sig.score({"title": "a diffusion model", "abstract": ""}, state)
    assert exact == 1.0                       # linked paper -> normalized 1.0
    assert term is not None and term > 0.0


def test_reddit_refine_bumps_linked_paper(tmp_path, monkeypatch):
    from scripts.lib.trends.reddit import RedditSignal
    monkeypatch.setenv("REDDIT_CLIENT_ID", "id")
    monkeypatch.setenv("REDDIT_CLIENT_SECRET", "secret")
    sig = RedditSignal(SignalConfig(
        name="reddit", params={"subreddits": ["MachineLearning"]}))
    ctx = _ctx(tmp_path, _reddit_router())
    sig.prepare([], _topic(), ctx)
    bumps = sig.refine_top_slice(
        [{"arxiv_id": "2607.13034", "title": "x", "abstract": ""}], "state")
    assert bumps and all(0.0 <= v <= 0.3 for v in bumps.values())


def test_reddit_missing_credentials_raises(tmp_path, monkeypatch):
    from scripts.lib.fetch_http import FetchError
    from scripts.lib.trends.reddit import RedditSignal
    monkeypatch.delenv("REDDIT_CLIENT_ID", raising=False)
    monkeypatch.delenv("REDDIT_CLIENT_SECRET", raising=False)
    sig = RedditSignal(SignalConfig(name="reddit"))
    with pytest.raises(FetchError):
        sig.prepare([], _topic(), _ctx(tmp_path, _reddit_router()))


def test_reddit_missing_credentials_skipped_by_scorer(tmp_path, monkeypatch):
    """The scorer isolates the raise -> run continues without Reddit."""
    from scripts.lib.config import TrendsConfig
    from scripts.lib.trends import TrendScorer
    monkeypatch.delenv("REDDIT_CLIENT_ID", raising=False)
    monkeypatch.delenv("REDDIT_CLIENT_SECRET", raising=False)
    cfg = TrendsConfig(signals=[SignalConfig(name="reddit")],
                       corpus_burst={"enabled": False})
    scorer = TrendScorer.from_config(cfg)
    corpus = [{"arxiv_id": "1", "title": "diffusion", "abstract": ""}]
    out = scorer.score_corpus(corpus, topic=_topic(),
                              ctx=_ctx(tmp_path, _reddit_router()))
    # Reddit dropped; no signals -> trendiness 0.0, run did not raise.
    assert out["1"]["trendiness"] == 0.0


def test_reddit_cache_prevents_second_call_and_excludes_token(tmp_path, monkeypatch):
    import json as _json

    from scripts.lib.trends.reddit import RedditSignal
    monkeypatch.setenv("REDDIT_CLIENT_ID", "id")
    monkeypatch.setenv("REDDIT_CLIENT_SECRET", "secret")
    calls = {"n": 0}
    token = (FIX / "reddit_token.json").read_text()
    listing = (FIX / "reddit_listing.json").read_text()

    def handler(req):
        calls["n"] += 1
        if "access_token" in req.url.path:
            return httpx.Response(200, text=token)
        return httpx.Response(200, text=listing)

    t = httpx.MockTransport(handler)
    sig = RedditSignal(SignalConfig(
        name="reddit", cache_ttl_min=180,
        params={"subreddits": ["MachineLearning"]}))
    sig.prepare([], _topic(), _ctx(tmp_path, t))
    first = calls["n"]
    sig2 = RedditSignal(SignalConfig(
        name="reddit", cache_ttl_min=180,
        params={"subreddits": ["MachineLearning"]}))
    sig2.prepare([], _topic(), _ctx(tmp_path, t))     # same day -> cache hit
    assert calls["n"] == first                         # no new API calls
    # The cached state must NOT contain the OAuth token.
    cache_file = next((tmp_path / "trend_cache").glob("reddit_*.json"))
    blob = _json.loads(cache_file.read_text())
    assert "access_token" not in _json.dumps(blob)


def test_registry_includes_new_signals():
    from scripts.lib.trends import _registry
    reg = _registry()
    assert reg["bluesky"].__name__ == "BlueskySignal"
    assert reg["wikipedia"].__name__ == "WikipediaSignal"
    assert reg["reddit"].__name__ == "RedditSignal"
