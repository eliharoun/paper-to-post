"""Hacker News (Algolia) provider. `prepare` builds a hot-term set from recent
high-scoring story titles (topic heat). `refine_top_slice` does a per-paper
lookup — was THIS paper posted to HN? — a sparse but strong additive signal."""
from __future__ import annotations

import json

from scripts.lib.config import SignalConfig
from scripts.lib.fetch_http import FetchError, get_text
from scripts.lib.trends.base import RunContext, _paper_id, text_terms
from scripts.lib.trends.cache import read_cache, write_cache

_URL = "https://hn.algolia.com/api/v1/search"


class HackerNewsSignal:
    name = "hackernews"

    def __init__(self, cfg: SignalConfig):
        self.cfg = cfg
        self._ctx: RunContext | None = None

    def prepare(self, corpus, topic, ctx: RunContext) -> dict[str, float]:
        self._ctx = ctx
        cached = read_cache(ctx.data_dir, self.name, ctx.topic_id, ctx.today,
                            ttl_min=self.cfg.cache_ttl_min)
        if cached is not None:
            return cached
        min_points = int(self.cfg.params.get("min_points", 50))
        body = get_text(
            _URL,
            params={"tags": "story", "hitsPerPage": "100",
                    "numericFilters": f"points>{min_points}"},
            timeout=self.cfg.timeout_s, transport=ctx.transport,
        )
        hits = json.loads(body).get("hits", [])
        hot: dict[str, float] = {}
        max_pts = max((h.get("points", 0) for h in hits), default=1) or 1
        for h in hits:
            w = (h.get("points", 0) + h.get("num_comments", 0)) / max_pts
            for term in text_terms(h.get("title") or "", ""):
                hot[term] = max(hot.get(term, 0.0), min(1.0, w))
        write_cache(ctx.data_dir, self.name, ctx.topic_id, ctx.today, hot)
        return hot

    def score(self, paper: dict, state: dict[str, float]) -> float | None:
        if not state:
            return None
        terms = text_terms(paper.get("title") or "", paper.get("abstract") or "")
        vals = [state[t] for t in terms if t in state]
        return max(vals) if vals else 0.0

    def refine_top_slice(self, papers, state) -> dict[str, float]:
        """Per-paper: search HN for the paper's id; bump = capped normalized points."""
        ctx = self._ctx
        bumps: dict[str, float] = {}
        if ctx is None:
            return bumps
        for p in papers:
            q = p.get("arxiv_id") or p.get("doi")
            if not q:
                continue
            try:
                body = get_text(_URL, params={"query": str(q), "tags": "story"},
                                timeout=self.cfg.timeout_s, transport=ctx.transport)
            except FetchError:
                continue
            hits = json.loads(body).get("hits", [])
            if not hits:
                continue
            pts = max(h.get("points", 0) for h in hits)
            bumps[_paper_id(p)] = min(0.3, pts / 1000.0)     # capped additive bump
        return bumps
