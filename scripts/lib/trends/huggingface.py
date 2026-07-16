"""HuggingFace Daily Papers provider (CS/ML). `prepare` builds an arXiv-id ->
upvote map plus a hot-term set from that day's upvoted titles. Per-paper value is
already captured via the arXiv-id map in `score`, so `refine_top_slice` is a no-op."""
from __future__ import annotations

import json
from typing import Any

from scripts.lib.config import SignalConfig
from scripts.lib.fetch_http import get_text
from scripts.lib.trends.base import RunContext, text_terms
from scripts.lib.trends.cache import read_cache, write_cache

_URL = "https://huggingface.co/api/daily_papers"


class HuggingFaceSignal:
    name = "huggingface"

    def __init__(self, cfg: SignalConfig):
        self.cfg = cfg

    def prepare(self, corpus, topic, ctx: RunContext) -> dict[str, Any]:
        cached = read_cache(ctx.data_dir, self.name, ctx.topic_id, ctx.today,
                            ttl_min=self.cfg.cache_ttl_min)
        if cached is not None:
            return cached
        body = get_text(_URL, params={"date": ctx.today.isoformat()},
                        timeout=self.cfg.timeout_s, transport=ctx.transport)
        rows = json.loads(body)
        max_up = max((r.get("upvotes", 0) for r in rows), default=1) or 1
        by_id: dict[str, float] = {}
        hot: dict[str, float] = {}
        for r in rows:
            paper = r.get("paper", {})
            up = r.get("upvotes", 0) / max_up
            aid = paper.get("id")
            if aid:
                by_id[str(aid)] = min(1.0, up)
            for term in text_terms(paper.get("title") or "", ""):
                hot[term] = max(hot.get(term, 0.0), min(1.0, up))
        state = {"by_id": by_id, "hot": hot}
        write_cache(ctx.data_dir, self.name, ctx.topic_id, ctx.today, state)
        return state

    def score(self, paper: dict, state: dict[str, Any]) -> float | None:
        if not state:
            return None
        aid = str(paper.get("arxiv_id") or "")
        if aid and aid in state.get("by_id", {}):
            return state["by_id"][aid]
        hot = state.get("hot", {})
        terms = text_terms(paper.get("title") or "", paper.get("abstract") or "")
        vals = [hot[t] for t in terms if t in hot]
        return max(vals) if vals else 0.0

    def refine_top_slice(self, papers, state) -> dict[str, float]:
        return {}      # per-paper value already captured via by_id in score()
