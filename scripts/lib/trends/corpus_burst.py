"""Local corpus term-burst signal. No network.

Rolling basis (>=2 days of history): score a paper by how over-represented its
terms are today vs a smoothed baseline, via a tanh-saturated positive log-ratio.
Cold-start basis (no history): approximate trend by cluster prominence -- terms
shared by many of today's papers, discounting near-ubiquitous ones. Both bases
take the MEAN of a paper's top-N term weights (no length bias) and convert to a
tie-fair rank percentile in [0, 1].
"""
from __future__ import annotations

import bisect
import math
from collections import Counter
from dataclasses import dataclass
from typing import Any

from scripts.lib.config import CorpusBurstConfig
from scripts.lib.trends.base import RunContext, text_terms
from scripts.lib.trends.history import TermHistory

_ALPHA = 1.0        # additive smoothing for the baseline distribution
_EPS = 1e-9


@dataclass
class _BurstState:
    basis: str                              # rolling | cluster | insufficient_corpus
    n_today: int
    df_today: dict[str, int]
    term_weight: dict[str, float]
    percentile: dict[int, float]            # id(paper) -> 0..1
    doc_terms: dict[int, set[str]]


def _cat_terms(paper: dict) -> set[str]:
    cats = paper.get("arxiv_categories") or []
    raw = paper.get("raw_payload") or {}
    if not cats and isinstance(raw, dict):
        cats = raw.get("arxiv_categories", [])
    return {f"cat:{c}" for c in cats}


class CorpusBurstSignal:
    name = "corpus_burst"

    def __init__(self, cfg: CorpusBurstConfig):
        self.cfg = cfg

    def _doc_terms(self, paper: dict) -> set[str]:
        return text_terms(
            paper.get("title") or "", paper.get("abstract") or "",
            extra_stopwords=set(self.cfg.extra_stopwords),
        ) | _cat_terms(paper)

    def prepare(self, corpus: list[dict], topic: Any, ctx: RunContext) -> _BurstState:
        n_today = len(corpus)
        doc_terms = {id(p): self._doc_terms(p) for p in corpus}
        df_today: Counter[str] = Counter()
        for terms in doc_terms.values():
            df_today.update(terms)

        if n_today < self.cfg.min_corpus:
            return _BurstState("insufficient_corpus", n_today, dict(df_today),
                               {}, {}, doc_terms)

        eligible = {t: c for t, c in df_today.items()
                    if c >= self.cfg.min_doc_freq}
        hist = TermHistory(ctx.data_dir / "term_history.json")
        base_n, base_df = hist.window_totals(
            ctx.topic_id, today=ctx.today, window_days=self.cfg.window_days)
        has_history = base_n >= 1 and len(hist.dates(ctx.topic_id)) >= 2

        term_weight: dict[str, float] = {}
        if has_history:
            basis = "rolling"
            vocab = len(set(df_today) | set(base_df)) or 1
            for t, c in eligible.items():
                p_today = c / n_today
                p_base = (base_df.get(t, 0) + _ALPHA) / (base_n + _ALPHA * vocab)
                burst = math.log((p_today + _EPS) / (p_base + _EPS))
                # continuous 0..1, gently saturating; burst_cap is the scale, not a clamp
                term_weight[t] = math.tanh(burst / self.cfg.burst_cap) if burst > 0 else 0.0
        else:
            basis = "cluster"
            # No baseline yet: cluster prominence (log-damped doc-frequency),
            # discounting near-ubiquitous terms like the topic's own category.
            for t, c in eligible.items():
                term_weight[t] = math.log1p(c) * (1.0 - c / n_today)

        raw: dict[int, float] = {}
        for pid, terms in doc_terms.items():
            weights = sorted((term_weight.get(t, 0.0) for t in terms), reverse=True)
            top = [w for w in weights[: self.cfg.top_terms] if w > 0]
            raw[pid] = sum(top) / len(top) if top else 0.0     # MEAN -> no length bias

        return _BurstState(basis, n_today, dict(df_today), term_weight,
                           self._percentiles(raw), doc_terms)

    @staticmethod
    def _percentiles(raw: dict[int, float]) -> dict[int, float]:
        """Rank percentile in [0,1]: bisect_left rank over the sorted raw scores,
        normalized by n-1. Equal raw -> equal percentile (tie-fair, deterministic);
        a unique max -> 1.0, min -> 0.0."""
        if not raw:
            return {}
        if len(raw) == 1:
            return {k: 1.0 for k in raw}
        vals = sorted(raw.values())
        n = len(vals)
        return {pid: bisect.bisect_left(vals, v) / (n - 1) for pid, v in raw.items()}

    def score(self, paper: dict, state: _BurstState) -> float | None:
        if state.basis == "insufficient_corpus":
            return None
        return state.percentile.get(id(paper))

    def terms_for(self, paper: dict, state: _BurstState) -> list[str]:
        terms = state.doc_terms.get(id(paper), set())
        ranked = sorted(terms, key=lambda t: (state.term_weight.get(t, 0.0), t),
                        reverse=True)
        return [t for t in ranked if state.term_weight.get(t, 0.0) > 0][
            : self.cfg.top_terms]

    def refine_top_slice(self, papers, state) -> dict[str, float]:
        return {}

    def persist(self, state: _BurstState, ctx: RunContext) -> None:
        if state.basis == "insufficient_corpus":
            return
        hist = TermHistory(ctx.data_dir / "term_history.json")
        hist.upsert(ctx.topic_id, ctx.today, n=state.n_today, df=state.df_today)
        hist.prune(ctx.topic_id, today=ctx.today, window_days=self.cfg.window_days)
        hist.save()
