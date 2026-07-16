"""Reddit provider (app-only OAuth). `prepare` pulls hot/top posts from the
configured subreddits, building a hot-term map from titles plus an
arXiv/DOI -> engagement map from link posts. `refine_top_slice` looks up THIS
paper's arXiv/DOI URL via Reddit's /api/info and bumps by engagement.
Credentials come from REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET in the
environment; if either is missing, prepare raises and the scorer skips this
signal (the run continues). Uniquely covers biomed communities (r/science,
r/genetics) that HN/HuggingFace miss."""
from __future__ import annotations

import json
import math
import os
import re

from scripts.lib.config import SignalConfig
from scripts.lib.fetch_http import FetchError, get_text, post_text
from scripts.lib.trends.base import RunContext, _paper_id, text_terms
from scripts.lib.trends.cache import read_cache, write_cache

_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
_API = "https://oauth.reddit.com"
_ARXIV_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})")
# Stop at whitespace, quotes, angle brackets, and closing paren/query/fragment so
# a trailing ")" or "?utm=..." on a link-post URL isn't captured into the key.
_DOI_RE = re.compile(r"(10\.\d{4,9}/[^\s\"'<>)?#]+)", re.IGNORECASE)


def _link_key(url: str) -> str | None:
    """Extract a stable arXiv/DOI key from a link-post URL, or None."""
    m = _ARXIV_RE.search(url or "")
    if m:
        return m.group(1)
    m = _DOI_RE.search(url or "")
    return m.group(1).rstrip(".").lower() if m else None


class RedditSignal:
    name = "reddit"

    def __init__(self, cfg: SignalConfig):
        self.cfg = cfg
        self._ctx: RunContext | None = None
        self._token: str | None = None

    def _ua(self) -> str:
        """Reddit-compliant User-Agent. Reddit rate-limits generic/default UAs,
        so allow overriding via config param or REDDIT_USER_AGENT env."""
        return (self.cfg.params.get("user_agent")
                or os.environ.get("REDDIT_USER_AGENT")
                or "python:paper-to-post:0.1 (by /u/paper-to-post)")

    def _get_token(self, ctx: RunContext) -> str:
        if self._token:
            return self._token
        cid = os.environ.get("REDDIT_CLIENT_ID", "").strip()
        secret = os.environ.get("REDDIT_CLIENT_SECRET", "").strip()
        if not cid or not secret:
            raise FetchError(
                "reddit: REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET not set")
        body = post_text(_TOKEN_URL, data={"grant_type": "client_credentials"},
                         auth=(cid, secret), headers={"User-Agent": self._ua()},
                         timeout=self.cfg.timeout_s, transport=ctx.transport)
        self._token = json.loads(body).get("access_token")
        if not self._token:
            raise FetchError("reddit: no access_token in token response")
        return self._token

    def _get(self, ctx: RunContext, url: str, params: dict) -> dict:
        token = self._get_token(ctx)
        body = get_text(url, params=params,
                        headers={"Authorization": f"bearer {token}",
                                 "User-Agent": self._ua()},
                        timeout=self.cfg.timeout_s, transport=ctx.transport)
        return json.loads(body)

    def _children(self, payload: dict) -> list[dict]:
        return [c.get("data", {})
                for c in (payload.get("data", {}) or {}).get("children", [])]

    def prepare(self, corpus, topic, ctx: RunContext) -> dict:
        self._ctx = ctx
        cached = read_cache(ctx.data_dir, self.name, ctx.topic_id, ctx.today,
                            ttl_min=self.cfg.cache_ttl_min)
        if cached is not None:
            return cached
        # Fetch the token eagerly so missing creds fail fast (before the cache
        # write) and the scorer can isolate this signal.
        self._get_token(ctx)
        subreddits = list(self.cfg.params.get("subreddits", []) or [])
        listing = str(self.cfg.params.get("listing", "hot"))
        timespan = str(self.cfg.params.get("timespan", "week"))
        min_score = int(self.cfg.params.get("min_score", 0))
        listing_limit = int(self.cfg.params.get("listing_limit", 100))

        posts: list[dict] = []
        for sub in subreddits:
            url = f"{_API}/r/{sub}/{listing}"
            params = {"limit": str(listing_limit)}
            if listing == "top":
                params["t"] = timespan
            try:
                posts.extend(self._children(self._get(ctx, url, params)))
            except (FetchError, ValueError):
                continue      # isolate a failing subreddit; keep the rest

        posts = [p for p in posts if int(p.get("score", 0)) >= min_score]
        heat: dict[str, float] = {}
        urls: dict[str, float] = {}
        max_eng = max(
            (int(p.get("score", 0)) + int(p.get("num_comments", 0)) for p in posts),
            default=1) or 1
        for p in posts:
            eng = int(p.get("score", 0)) + int(p.get("num_comments", 0))
            w = min(1.0, eng / max_eng)
            for term in text_terms(p.get("title") or "", ""):
                heat[term] = max(heat.get(term, 0.0), w)
            key = _link_key(p.get("url") or "")
            if key:
                urls[key] = max(urls.get(key, 0.0), w)

        state = {"heat": heat, "urls": urls}
        write_cache(ctx.data_dir, self.name, ctx.topic_id, ctx.today, state)
        return state

    def score(self, paper: dict, state: dict) -> float | None:
        if not state or (not state.get("heat") and not state.get("urls")):
            return None
        urls = state.get("urls", {})
        for key in (paper.get("arxiv_id"), (paper.get("doi") or "").lower()):
            if key and key in urls:
                return urls[key]
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
        for p in papers:
            aid = p.get("arxiv_id")
            doi = p.get("doi")
            if aid:
                url = f"https://arxiv.org/abs/{aid}"
            elif doi:
                url = f"https://doi.org/{doi}"
            else:
                continue
            # /api/info?url= is Reddit's canonical "submissions linking this URL"
            # lookup — reliable, unlike free-text `url:` search.
            try:
                payload = self._get(ctx, f"{_API}/api/info", {"url": url})
            except (FetchError, ValueError):
                continue
            children = self._children(payload)
            eng = sum(int(c.get("score", 0)) + int(c.get("num_comments", 0))
                      for c in children)
            if eng > 0:
                bumps[_paper_id(p)] = min(cap, math.log10(1 + eng) / 10.0)
        return bumps
