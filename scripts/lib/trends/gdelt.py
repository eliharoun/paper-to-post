"""GDELT DOC 2.0 news-volume provider (topic-level). For each topic keyword it
fetches a recent coverage timeline and computes a recent-vs-baseline ratio; a
paper is scored by the max ratio over the keywords it mentions. Topic-only:
`refine_top_slice` is a documented no-op (there is no per-paper GDELT signal)."""
from __future__ import annotations

import json

from scripts.lib.config import SignalConfig
from scripts.lib.fetch_http import FetchError, get_text
from scripts.lib.trends.base import RunContext
from scripts.lib.trends.cache import read_cache, write_cache

_URL = "https://api.gdeltproject.org/api/v2/doc/doc"


def _ratio(series: list[dict]) -> float:
    """Recent (last point) vs baseline (mean of the rest), mapped (1, inf) -> (0, 1).
    r=1 -> 0, r=3 -> 0.5, r -> inf -> 1. Monotonic; no ad-hoc scaling."""
    vals = [pt.get("value", 0.0) for pt in series]
    if len(vals) < 2:
        return 0.0
    recent = vals[-1]
    base = sum(vals[:-1]) / (len(vals) - 1) or 1e-9
    r = recent / base
    if r <= 1.0:
        return 0.0
    return max(0.0, min(1.0, (r - 1.0) / (r + 1.0)))


class GdeltSignal:
    name = "gdelt"

    def __init__(self, cfg: SignalConfig):
        self.cfg = cfg

    def prepare(self, corpus, topic, ctx: RunContext) -> dict[str, float]:
        # Cache key is provider+topic+day only — changing params like timespan
        # mid-day serves cached data until the TTL expires (applies to all providers).
        cached = read_cache(ctx.data_dir, self.name, ctx.topic_id, ctx.today,
                            ttl_min=self.cfg.cache_ttl_min)
        if cached is not None:
            return cached
        timespan = self.cfg.params.get("timespan", "1w")
        heat: dict[str, float] = {}
        for kw in list(getattr(topic, "keywords", []) or []):
            try:
                body = get_text(
                    _URL,
                    params={"query": f'"{kw}"', "mode": "timelinevol",
                            "timespan": timespan, "format": "json"},
                    timeout=self.cfg.timeout_s, transport=ctx.transport,
                )
                data = json.loads(body).get("timeline", [])
            except (FetchError, ValueError):
                continue      # isolate a failing/malformed keyword; keep the rest
            series = data[0].get("data", []) if data else []
            heat[kw.lower()] = _ratio(series)
        write_cache(ctx.data_dir, self.name, ctx.topic_id, ctx.today, heat)
        return heat

    def score(self, paper: dict, state: dict[str, float]) -> float | None:
        if not state:
            return None
        hay = f"{paper.get('title') or ''} {paper.get('abstract') or ''}".lower()
        vals = [v for kw, v in state.items() if kw in hay]
        return max(vals) if vals else 0.0

    def refine_top_slice(self, papers, state) -> dict[str, float]:
        return {}      # topic-level only; no per-paper GDELT signal
