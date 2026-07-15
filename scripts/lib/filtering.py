from __future__ import annotations

import math
from datetime import date

from scripts.lib.config import TopicsConfig
from scripts.lib.journals import is_flagship_venue

MIN_ABSTRACT_CHARS = 400

_NON_ARTICLE_MARKERS = (
    "erratum", "corrigendum", "correction to", "retraction", "editorial",
    "obituary", "comment on", "reply to",
)

_HYPE_TERMS = (
    "cure", "proven", "guaranteed", "miracle", "breakthrough", "game-changing",
    "game changing", "100%", "revolutionary",
)


def _paper_arxiv_categories(paper: dict) -> list[str]:
    cats = paper.get("arxiv_categories")
    if cats:
        return cats
    raw = paper.get("raw_payload") or {}
    return raw.get("arxiv_categories", []) if isinstance(raw, dict) else []


def _topic_arxiv_categories(topic) -> list[str]:
    """A topic's configured arXiv categories (empty if it has no arXiv source)."""
    return topic.sources.arxiv.categories if topic.sources.arxiv else []


def assign_topic(paper: dict, topics: TopicsConfig) -> str | None:
    """Assign the paper to the first matching enabled topic, or None.

    Match priority: arXiv category overlap -> field_of_study/title keyword hints,
    weighted by topic priority so higher-priority topics win ties. Both the
    categories and the keywords come from config (per-topic), so adding a topic
    needs no code change.
    """
    enabled = sorted(topics.enabled_topics(), key=lambda t: t.priority, reverse=True)
    cats = _paper_arxiv_categories(paper)
    paper_cats = set(cats) | {c.split(".")[0] for c in cats}

    # 1. arXiv category match
    for topic in enabled:
        tcats = _topic_arxiv_categories(topic)
        topic_cats = set(tcats) | {c.split(".")[0] for c in tcats}
        if paper_cats & topic_cats:
            return topic.id

    # 2. keyword match against field_of_study + title
    haystack = f"{paper.get('field_of_study') or ''} {paper.get('title') or ''}".lower()
    for topic in enabled:
        for kw in topic.keywords:
            if kw.lower() in haystack:
                return topic.id
    return None


def hard_filter_reasons(paper: dict, topics: TopicsConfig) -> list[str]:
    """Return reasons the paper must be rejected. Empty list => passes."""
    reasons: list[str] = []
    title = (paper.get("title") or "").strip()
    abstract = paper.get("abstract")
    topic_id = paper.get("topic_id")

    if not title:
        reasons.append("no_title")
    if abstract is None:
        reasons.append("no_abstract")
    elif len(abstract.strip()) < MIN_ABSTRACT_CHARS:
        reasons.append("abstract_too_short")
    if not topic_id:
        reasons.append("no_topic")

    title_l = title.lower()
    if any(m in title_l for m in _NON_ARTICLE_MARKERS):
        reasons.append("correction_or_erratum")

    # per-topic hard_excludes (phrase match on title+abstract)
    topic = next((t for t in topics.topics if t.id == topic_id), None)
    if topic:
        haystack = f"{title_l} {(abstract or '').lower()}"
        for term in topic.hard_excludes:
            if term.lower() in haystack:
                reasons.append(f"hard_exclude:{term}")
    return reasons


def _parse_date(s) -> date | None:
    if not s:
        return None
    if isinstance(s, date):
        return s
    try:
        return date.fromisoformat(str(s)[:10])
    except ValueError:
        return None


def rule_score(
    paper: dict, topics: TopicsConfig, *, today: date, lookback_hours: int | None = None
) -> float:
    """Cheap 0-100 ranking heuristic (NOT newsworthiness judgment).

    Weights: recency 30, abstract length 20, topic priority 20,
    identifiability 10, open-access 5, citations 10 (log-damped),
    flagship venue +15, hype penalty -15.
    """
    lookback_days = (lookback_hours or topics.lookback_hours) / 24.0

    # recency (30): linear decay across the lookback window
    pub = _parse_date(paper.get("published_date"))
    if pub:
        age_days = max(0, (today - pub).days)
        recency = max(0.0, 1.0 - age_days / max(lookback_days, 1)) * 30
    else:
        recency = 5.0  # unknown date: small credit

    # abstract length (20): saturates at ~1500 chars
    alen = len(paper.get("abstract") or "")
    abstract_pts = min(alen / 1500.0, 1.0) * 20

    # topic priority (20)
    topic = next((t for t in topics.topics if t.id == paper.get("topic_id")), None)
    priority_pts = (topic.priority if topic else 0.0) * 20

    # identifiability (10)
    id_pts = 10.0 if (paper.get("arxiv_id") or paper.get("doi")) else 0.0

    # open access (5)
    oa_pts = 5.0 if paper.get("pdf_url") else 0.0

    # citations (10): log-damped so 0-citation new papers aren't buried
    cites = paper.get("citation_count") or 0
    cite_pts = min(math.log1p(max(cites, 0)) / math.log1p(100), 1.0) * 10

    # flagship venue (+15): a brand-new Nature/Lancet/Cell paper has ~0 citations,
    # so without this it ranks no higher than a random preprint. Reward the venue
    # directly, matched on the normalized venue name (works for any source).
    venue_pts = 15.0 if is_flagship_venue(paper.get("venue")) else 0.0

    # hype penalty (-15)
    title_l = (paper.get("title") or "").lower()
    hype_penalty = -15.0 if any(t in title_l for t in _HYPE_TERMS) else 0.0

    total = (recency + abstract_pts + priority_pts + id_pts + oa_pts
             + cite_pts + venue_pts + hype_penalty)
    return round(max(0.0, min(100.0, total)), 2)
