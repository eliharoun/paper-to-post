"""Wikipedia Pageviews provider (topic-level, GDELT-shaped). For each topic
keyword it resolves an article title, fetches the recent daily pageview series,
and computes a recent-vs-baseline ratio (reusing GDELT's _ratio). A paper is
scored by the max ratio over the keywords it mentions. `refine_top_slice` is a
no-op (no per-paper Wikipedia signal — you can't pageview an individual paper)."""
from __future__ import annotations

import json
from datetime import timedelta

from scripts.lib.config import SignalConfig
from scripts.lib.fetch_http import FetchError, get_text
from scripts.lib.trends.base import RunContext
from scripts.lib.trends.cache import read_cache, write_cache
from scripts.lib.trends.gdelt import _ratio

_BASE = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
         "en.wikipedia/all-access/all-agents")


def _default_title(keyword: str) -> str:
    """Best-effort keyword -> article title: capitalize first letter, underscores."""
    kw = keyword.strip()
    if not kw:
        return kw
    return (kw[0].upper() + kw[1:]).replace(" ", "_")


class WikipediaSignal:
    name = "wikipedia"

    def __init__(self, cfg: SignalConfig):
        self.cfg = cfg

    def prepare(self, corpus, topic, ctx: RunContext) -> dict[str, float]:
        cached = read_cache(ctx.data_dir, self.name, ctx.topic_id, ctx.today,
                            ttl_min=self.cfg.cache_ttl_min)
        if cached is not None:
            return cached
        titles = dict(self.cfg.params.get("titles", {}) or {})
        baseline_days = int(self.cfg.params.get("baseline_days", 14))
        start = (ctx.today - timedelta(days=baseline_days)).strftime("%Y%m%d")
        end = ctx.today.strftime("%Y%m%d")
        heat: dict[str, float] = {}
        for kw in list(getattr(topic, "keywords", []) or []):
            article = titles.get(kw) or _default_title(kw)
            url = f"{_BASE}/{article}/daily/{start}/{end}"
            try:
                body = get_text(url, timeout=self.cfg.timeout_s,
                                transport=ctx.transport)
                items = json.loads(body).get("items", [])
            except (FetchError, ValueError):
                continue      # isolate a missing/redirected article; keep the rest
            series = [{"value": it.get("views", 0)} for it in items]
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
        return {}      # topic-level only; no per-paper Wikipedia signal
