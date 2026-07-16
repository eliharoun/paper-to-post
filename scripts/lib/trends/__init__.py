"""Trend-signal registry and the TrendScorer that blends providers."""
from __future__ import annotations

import sys
from typing import Any

from scripts.lib.config import TrendsConfig
from scripts.lib.trends.base import RunContext, _paper_id
from scripts.lib.trends.corpus_burst import CorpusBurstSignal

__all__ = ["TrendScorer", "_paper_id", "RunContext"]


def _registry() -> dict[str, type]:
    """name -> external provider class. Imported lazily so httpx-touching modules
    don't load when trends are disabled. Add a provider here to make it configurable."""
    from scripts.lib.trends.bluesky import BlueskySignal
    from scripts.lib.trends.gdelt import GdeltSignal
    from scripts.lib.trends.hackernews import HackerNewsSignal
    from scripts.lib.trends.huggingface import HuggingFaceSignal
    from scripts.lib.trends.reddit import RedditSignal
    from scripts.lib.trends.wikipedia import WikipediaSignal
    return {
        "hackernews": HackerNewsSignal,
        "gdelt": GdeltSignal,
        "huggingface": HuggingFaceSignal,
        "bluesky": BlueskySignal,
        "wikipedia": WikipediaSignal,
        "reddit": RedditSignal,
    }


class TrendScorer:
    def __init__(self, cfg: TrendsConfig, *, local, externals: list):
        self.cfg = cfg
        self.local = local
        self.externals = externals
        self._last_local_state = None
        self._last_ext_live: list = []

    @classmethod
    def from_config(cls, cfg: TrendsConfig) -> TrendScorer:
        local = CorpusBurstSignal(cfg.corpus_burst) if cfg.corpus_burst.enabled else None
        reg = _registry()
        externals = []
        for sc in cfg.active_signals():
            klass = reg.get(sc.name)
            if klass is None:
                print(f"trends: unknown signal '{sc.name}' (skipping)", file=sys.stderr)
                continue
            externals.append(klass(sc))
        return cls(cfg, local=local, externals=externals)

    def _prepare(self, provider, corpus, topic, ctx):
        try:
            return provider.prepare(corpus, topic, ctx)
        except Exception as exc:  # noqa: BLE001 — resilient like gather.py
            print(f"trends: source '{provider.name}' failed: {exc} (skipping)",
                  file=sys.stderr)
            return None

    def score_corpus(self, corpus: list[dict], *, topic, ctx: RunContext) -> dict:
        """Returns {_paper_id -> score_breakdown dict}."""
        local_state = (self._prepare(self.local, corpus, topic, ctx)
                       if self.local else None)
        ext_states = [(p, self._prepare(p, corpus, topic, ctx)) for p in self.externals]
        ext_live = [(p, s) for p, s in ext_states if s is not None]
        weights = {s.name: s.weight for s in self.cfg.active_signals()}

        out: dict[str, dict] = {}
        for paper in corpus:
            signals: dict[str, float] = {}
            local_val = self.local.score(paper, local_state) if local_state is not None else None
            if local_val is not None:
                signals["corpus_burst"] = round(local_val, 4)
            ext_pairs = []
            for p, s in ext_live:
                v = p.score(paper, s)
                if v is not None:
                    signals[p.name] = round(v, 4)
                    ext_pairs.append((weights.get(p.name, 1.0), v))

            bd: dict[str, Any] = {
                "trendiness": round(self._blend(local_val, ext_pairs), 4),
                "trend_signals": signals,
            }
            if local_state is not None:
                bd["trend_basis"] = getattr(local_state, "basis", "n/a")
                if hasattr(self.local, "terms_for"):
                    bd["trend_terms"] = self.local.terms_for(paper, local_state)
            out[_paper_id(paper)] = bd

        self._last_local_state = local_state
        self._last_ext_live = ext_live
        return out

    def _blend(self, local_val, ext_pairs) -> float:
        ext = None
        if ext_pairs:
            # zero total external weight (degenerate config) -> unweighted mean
            wsum = sum(w for w, _ in ext_pairs) or 1.0
            ext = sum(w * v for w, v in ext_pairs) / wsum
        lw, ew = self.cfg.blend.local_weight, self.cfg.blend.external_weight
        method = self.cfg.blend.method
        if local_val is None and ext is None:
            return 0.0
        if local_val is None:                # external-only fallback (any method)
            return ext
        if ext is None:                      # local-only (external empty/failed)
            return local_val
        if method == "max":
            return max(local_val, ext)
        if method == "multiplier":
            return min(1.0, local_val * (1.0 + ext))
        total = lw + ew or 1.0               # weighted, renormalized
        return (lw * local_val + ew * ext) / total

    def refine_top_slice(self, top_papers: list[dict], out: dict) -> None:
        """Apply per-paper engagement bumps from providers that support it.
        Mutates `out` in place, capping trendiness at 1.0."""
        for p, s in self._last_ext_live:
            try:
                bumps = p.refine_top_slice(top_papers, s)
            except Exception as exc:  # noqa: BLE001
                print(f"trends: refine '{p.name}' failed: {exc} (skipping)",
                      file=sys.stderr)
                continue
            for paper in top_papers:
                b = bumps.get(_paper_id(paper))
                if b:
                    bd = out.get(_paper_id(paper))
                    if bd:
                        bd["trendiness"] = round(min(1.0, bd["trendiness"] + b), 4)

    def persist(self, ctx: RunContext) -> None:
        state = self._last_local_state
        if self.local and state is not None and hasattr(self.local, "persist"):
            self.local.persist(state, ctx)
