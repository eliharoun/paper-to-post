from datetime import date

from scripts.lib.config import SignalConfig, TrendsConfig
from scripts.lib.trends import TrendScorer
from scripts.lib.trends.base import RunContext


class _Fake:
    """Fake provider: fixed score per paper (keyed by title), optional refine bumps."""
    def __init__(self, name, table, raise_on_prepare=False, refine=None):
        self.name = name
        self._table = table
        self._raise = raise_on_prepare
        self._refine = refine or {}

    def prepare(self, corpus, topic, ctx):
        if self._raise:
            raise RuntimeError("boom")
        return "state"

    def score(self, paper, state):
        return self._table.get(paper["title"])

    def refine_top_slice(self, papers, state):
        return self._refine


def _ctx(tmp_path):
    return RunContext(topic_id="cs", today=date(2026, 7, 15), data_dir=tmp_path)


def _papers():
    return [{"title": "a", "arxiv_id": "a"}, {"title": "b", "arxiv_id": "b"}]


def test_weighted_blend(tmp_path):
    cfg = TrendsConfig(blend={"local_weight": 0.6, "external_weight": 0.4,
                              "method": "weighted"})
    local = _Fake("corpus_burst", {"a": 1.0, "b": 0.0})
    ext = _Fake("hackernews", {"a": 0.0, "b": 1.0})
    scorer = TrendScorer(cfg, local=local, externals=[ext])
    out = scorer.score_corpus(_papers(), topic=None, ctx=_ctx(tmp_path))
    assert abs(out["a"]["trendiness"] - 0.6) < 1e-9
    assert abs(out["b"]["trendiness"] - 0.4) < 1e-9
    assert out["a"]["trend_signals"] == {"corpus_burst": 1.0, "hackernews": 0.0}


def test_failed_external_is_skipped_and_renormalized(tmp_path):
    cfg = TrendsConfig(blend={"local_weight": 0.6, "external_weight": 0.4})
    local = _Fake("corpus_burst", {"a": 0.5, "b": 0.5})
    ext = _Fake("hackernews", {}, raise_on_prepare=True)
    scorer = TrendScorer(cfg, local=local, externals=[ext])
    out = scorer.score_corpus(_papers(), topic=None, ctx=_ctx(tmp_path))
    assert abs(out["a"]["trendiness"] - 0.5) < 1e-9      # external empty -> local only
    assert "hackernews" not in out["a"]["trend_signals"]


def test_max_method(tmp_path):
    cfg = TrendsConfig(blend={"method": "max"})
    local = _Fake("corpus_burst", {"a": 0.2})
    ext = _Fake("hackernews", {"a": 0.9})
    scorer = TrendScorer(cfg, local=local, externals=[ext])
    out = scorer.score_corpus([{"title": "a", "arxiv_id": "a"}], topic=None, ctx=_ctx(tmp_path))
    assert abs(out["a"]["trendiness"] - 0.9) < 1e-9


def test_multiplier_method_clamps(tmp_path):
    cfg = TrendsConfig(blend={"method": "multiplier"})
    local = _Fake("corpus_burst", {"a": 0.8})
    ext = _Fake("hackernews", {"a": 0.9})
    scorer = TrendScorer(cfg, local=local, externals=[ext])
    out = scorer.score_corpus([{"title": "a", "arxiv_id": "a"}], topic=None, ctx=_ctx(tmp_path))
    assert out["a"]["trendiness"] == 1.0        # 0.8*(1+0.9) clamped to 1.0


def test_none_local_yields_zero_without_error(tmp_path):
    cfg = TrendsConfig()
    local = _Fake("corpus_burst", {"a": None})   # insufficient corpus
    scorer = TrendScorer(cfg, local=local, externals=[])
    out = scorer.score_corpus([{"title": "a", "arxiv_id": "a"}], topic=None, ctx=_ctx(tmp_path))
    assert out["a"]["trendiness"] == 0.0


def test_refine_top_slice_bumps_trendiness(tmp_path):
    cfg = TrendsConfig(blend={"local_weight": 0.6, "external_weight": 0.4})
    local = _Fake("corpus_burst", {"a": 0.9, "b": 0.1})
    ext = _Fake("hackernews", {"a": 0.0, "b": 0.0}, refine={"a": 0.2})
    scorer = TrendScorer(cfg, local=local, externals=[ext])
    papers = _papers()
    out = scorer.score_corpus(papers, topic=None, ctx=_ctx(tmp_path))
    before = out["a"]["trendiness"]              # 0.6*0.9 + 0.4*0 = 0.54
    b_before = out["b"]["trendiness"]
    scorer.refine_top_slice(papers, out)
    assert out["a"]["trendiness"] > before
    assert out["a"]["trendiness"] <= 1.0
    assert out["b"]["trendiness"] == b_before    # b had no bump


def test_scorer_determinism(tmp_path):
    cfg = TrendsConfig()
    local = _Fake("corpus_burst", {"a": 0.3, "b": 0.7})
    scorer = TrendScorer(cfg, local=local, externals=[])
    papers = _papers()
    o1 = scorer.score_corpus(papers, topic=None, ctx=_ctx(tmp_path))
    o2 = scorer.score_corpus(papers, topic=None, ctx=_ctx(tmp_path))
    assert o1 == o2


def test_external_only_branch_when_local_none(tmp_path):
    # local returns None for the paper -> external-only fallback returns raw ext,
    # regardless of blend method.
    cfg = TrendsConfig(signals=[SignalConfig(name="hackernews", weight=1.0)])
    local = _Fake("corpus_burst", {"a": None})
    ext = _Fake("hackernews", {"a": 0.7})
    scorer = TrendScorer(cfg, local=local, externals=[ext])
    out = scorer.score_corpus([{"title": "a", "arxiv_id": "a"}], topic=None, ctx=_ctx(tmp_path))
    assert out["a"]["trendiness"] == 0.7
    assert "corpus_burst" not in out["a"]["trend_signals"]
    assert out["a"]["trend_signals"] == {"hackernews": 0.7}


def test_multi_external_renormalizes_when_one_drops(tmp_path):
    # cfg declares two externals (weights 1.0 and 3.0) but only gdelt is live.
    # A single surviving external normalizes to its own score (wsum cancels),
    # so ext == 0.8 and weighted blend = (0.6*0.4 + 0.4*0.8) / 1.0 = 0.56.
    cfg = TrendsConfig(
        blend={"local_weight": 0.6, "external_weight": 0.4},
        signals=[SignalConfig(name="hackernews", weight=1.0),
                 SignalConfig(name="gdelt", weight=3.0)],
    )
    local = _Fake("corpus_burst", {"a": 0.4})
    gdelt = _Fake("gdelt", {"a": 0.8})
    scorer = TrendScorer(cfg, local=local, externals=[gdelt])
    out = scorer.score_corpus([{"title": "a", "arxiv_id": "a"}], topic=None, ctx=_ctx(tmp_path))
    assert abs(out["a"]["trendiness"] - 0.56) < 1e-9
    assert out["a"]["trend_signals"] == {"corpus_burst": 0.4, "gdelt": 0.8}
    assert "hackernews" not in out["a"]["trend_signals"]
