"""Deterministic card footer: the paper's source, category, and publication date.

Card footers are computed here from `selected_paper.json` at render time, NOT
authored by the language model — so every run produces the same footer for the
same paper. The footer reads 'Source · Category · Month D, YYYY' and appears on
the content cards only: the title/hero card and the closing source card get no
footer, and the paper first-page screenshot is not an authored card, so it is
unaffected.
"""
from __future__ import annotations

from datetime import date

# Human-friendly labels for known paper sources. The paper's `venue` (the real
# journal name) is preferred when present; these are the fallback when a source
# has no venue (e.g. arXiv), then the raw id as a last resort. They also
# normalize a `venue` that is really just the source slug (e.g. some feeds set
# venue='biorxiv') so the footer never shows a bare lowercase slug.
_SOURCE_LABELS = {
    "arxiv": "arXiv",
    "biorxiv": "bioRxiv",
    "medrxiv": "medRxiv",
    "pubmed": "PubMed",
    "openalex": "OpenAlex",
    "crossref": "Crossref",
    "semantic_scholar": "Semantic Scholar",
}

# Friendly category names for known field-of-study codes. arXiv-style codes are
# cryptic to a general audience, so map the common ones; any unmapped value is
# title-cased as-is (e.g. 'bioengineering' -> 'Bioengineering').
_CATEGORY_LABELS = {
    "cs.ai": "Artificial Intelligence",
    "cs.cl": "Natural Language Processing",
    "cs.lg": "Machine Learning",
    "cs.cv": "Computer Vision",
    "cs.se": "Software Engineering",
    "cs.dc": "Distributed Computing",
    "cs.cr": "Security & Cryptography",
    "cs.ir": "Information Retrieval",
    "cs.ro": "Robotics",
    "cs.pl": "Programming Languages",
    "cs.ma": "Multi-Agent Systems",
    "cs.et": "Emerging Technologies",
    "cs.cy": "Computers & Society",
    "stat.ml": "Machine Learning",
}


def unwrap_paper(paper: dict) -> dict:
    """Return the flat paper-metadata dict from a selected_paper.json payload.

    selected_paper.json wraps the paper under a "paper" key alongside scoring
    metadata (topic_id, filter_status, ...). Flatten it so callers can read
    venue/source/field_of_study/published_date directly. A dict that is already
    flat (no nested "paper") is returned unchanged, so this is safe to call twice.
    """
    inner = paper.get("paper")
    if isinstance(inner, dict):
        merged = {**paper, **inner}
        del merged["paper"]
        return merged
    return paper


def _source_label(paper: dict) -> str:
    """The publication venue when it is a real name, else a friendly source label.

    A `venue` that is really just the source slug (e.g. 'biorxiv') is treated as
    absent so it resolves to the normalized source label ('bioRxiv') instead of a
    bare lowercase slug.
    """
    venue = (paper.get("venue") or "").strip()
    if venue and venue.lower() not in _SOURCE_LABELS:
        return venue
    src = (paper.get("source") or "").strip()
    if src:
        return _SOURCE_LABELS.get(src.lower(), src)
    # No usable source; fall back to normalizing the venue slug if that's all we have.
    return _SOURCE_LABELS.get(venue.lower(), venue)


def _category_label(paper: dict) -> str:
    """Friendly research-area label from `field_of_study`. '' when none.

    Known codes (arXiv-style) map to readable names; anything else is title-cased.
    """
    fos = (paper.get("field_of_study") or "").strip()
    if not fos:
        return ""
    return _CATEGORY_LABELS.get(fos.lower(), fos.replace("_", " ").title())


def _publication_date(paper: dict) -> str:
    """Full 'Month D, YYYY' date from published_date (else updated_date). '' if none."""
    raw = paper.get("published_date") or paper.get("updated_date")
    if not raw:
        return ""
    try:
        # Accept both dates ('2026-07-15') and datetimes ('2026-07-15T10:21:52').
        d = date.fromisoformat(str(raw)[:10])
    except ValueError:
        return ""
    return f"{d:%B} {d.day}, {d.year}"


def card_footer_line(paper: dict) -> str:
    """Deterministic content-card footer: 'Source · Category · Month D, YYYY'.

    Uses the paper's venue when available (else a friendly source label), the
    friendly field-of-study category, and the full publication date. Any part
    that can't be resolved is dropped along with its separator, so a paper with
    no category renders 'Source · Month D, YYYY' and one with no date renders
    'Source · Category'. Accepts either a flat paper dict or the wrapped
    selected_paper.json payload (the "paper" key is unwrapped automatically).
    """
    paper = unwrap_paper(paper)
    parts = [_source_label(paper), _category_label(paper), _publication_date(paper)]
    return " · ".join(p for p in parts if p)
