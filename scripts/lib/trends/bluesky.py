"""Bluesky provider. `prepare` builds a hot-term map from recent top posts for
the topic's keywords (topic heat) plus an arXiv-id -> engagement map from a
posts-linking-arXiv sweep. `refine_top_slice` looks up whether THIS paper's
arXiv URL was posted, and how much engagement it drew — a sparse but strong
per-paper signal. No auth: uses the public AppView (public.api.bsky.app)."""
from __future__ import annotations

import json
import math
import re
from datetime import timedelta

from scripts.lib.config import SignalConfig
from scripts.lib.fetch_http import FetchError, get_text
from scripts.lib.trends.base import RunContext, _paper_id, text_terms
from scripts.lib.trends.cache import read_cache, write_cache

_URL = "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts"
_ARXIV_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})")


def _post_text(post: dict) -> str:
    return (post.get("record") or {}).get("text") or ""


def _post_links(post: dict) -> str:
    """Text plus any external embed URI, for arXiv-id extraction."""
    embed = (post.get("embed") or {}).get("external") or {}
    return f"{_post_text(post)} {embed.get('uri') or ''}"


def _engagement(post: dict) -> int:
    return (int(post.get("likeCount", 0)) + int(post.get("repostCount", 0))
            + int(post.get("replyCount", 0)))


class BlueskySignal:
    name = "bluesky"

    def __init__(self, cfg: SignalConfig):
        self.cfg = cfg
        self._ctx: RunContext | None = None

    def _search(self, ctx: RunContext, params: dict) -> list[dict]:
        body = get_text(_URL, params=params, timeout=self.cfg.timeout_s,
                        transport=ctx.transport)
        return json.loads(body).get("posts", [])

    def prepare(self, corpus, topic, ctx: RunContext) -> dict:
        self._ctx = ctx
        cached = read_cache(ctx.data_dir, self.name, ctx.topic_id, ctx.today,
                            ttl_min=self.cfg.cache_ttl_min)
        if cached is not None:
            return cached
        max_keywords = int(self.cfg.params.get("max_keywords", 6))
        limit = int(self.cfg.params.get("posts_per_query", 50))
        since_hours = int(self.cfg.params.get("since_hours", 72))
        # Derive `since` from ctx.today (not wall-clock) so same-day re-runs are
        # deterministic and cache-consistent. searchPosts accepts a YYYY-MM-DD date.
        since = (ctx.today - timedelta(days=max(1, since_hours // 24))).isoformat()
        keywords = list(getattr(topic, "keywords", []) or [])[:max_keywords]

        posts: list[dict] = []
        seen_uris: set[str] = set()
        for kw in keywords:
            try:
                hits = self._search(
                    ctx, {"q": kw, "sort": "top", "since": since,
                          "limit": str(limit)})
            except (FetchError, ValueError):
                continue      # isolate a failing keyword; keep the rest
            for p in hits:    # dedup across keywords by post uri
                uri = p.get("uri")
                if uri and uri in seen_uris:
                    continue
                if uri:
                    seen_uris.add(uri)
                posts.append(p)
        heat: dict[str, float] = {}
        max_eng = max((_engagement(p) for p in posts), default=1) or 1
        for p in posts:
            w = min(1.0, _engagement(p) / max_eng)
            for term in text_terms(_post_text(p), ""):
                heat[term] = max(heat.get(term, 0.0), w)

        # arXiv sweep -> {arxiv_id: normalized engagement}
        urls: dict[str, float] = {}
        try:
            ax_posts = self._search(
                ctx, {"q": "arxiv.org", "domain": "arxiv.org",
                      "sort": "top", "limit": str(limit)})
        except (FetchError, ValueError):
            ax_posts = []
        max_ax = max((_engagement(p) for p in ax_posts), default=1) or 1
        for p in ax_posts:
            m = _ARXIV_RE.search(_post_links(p))
            if m:
                aid = m.group(1)
                urls[aid] = max(urls.get(aid, 0.0),
                                min(1.0, _engagement(p) / max_ax))

        state = {"heat": heat, "urls": urls}
        write_cache(ctx.data_dir, self.name, ctx.topic_id, ctx.today, state)
        return state

    def score(self, paper: dict, state: dict) -> float | None:
        if not state or (not state.get("heat") and not state.get("urls")):
            return None
        aid = str(paper.get("arxiv_id") or "")
        if aid and aid in state.get("urls", {}):
            return state["urls"][aid]
        heat = state.get("heat", {})
        terms = text_terms(paper.get("title") or "", paper.get("abstract") or "")
        vals = [heat[t] for t in terms if t in heat]
        return max(vals) if vals else 0.0

    def refine_top_slice(self, papers, state) -> dict[str, float]:
        ctx = self._ctx
        bumps: dict[str, float] = {}
        if ctx is None:
            return bumps
        cap = float(self.cfg.params.get("bump_cap", 0.3))
        refine_limit = int(self.cfg.params.get("refine_limit", 25))
        for p in papers:
            aid = p.get("arxiv_id")
            if not aid:
                continue
            try:
                hits = self._search(
                    ctx, {"q": f"https://arxiv.org/abs/{aid}",
                          "limit": str(refine_limit)})
            except (FetchError, ValueError):
                continue
            eng = sum(_engagement(h) for h in hits)
            if eng > 0:
                bumps[_paper_id(p)] = min(cap, math.log10(1 + eng) / 10.0)
        return bumps
