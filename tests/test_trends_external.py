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
