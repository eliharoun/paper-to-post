"""Deterministic card footer: the paper's source and full publication date.

Card footers are computed here from `selected_paper.json` at render time, NOT
authored by the language model — so every run produces the same footer for the
same paper. The title/hero card gets no footer; every other rendered card
(the screenshot is not an authored card, so it is unaffected) shows this line.
"""
from __future__ import annotations

from datetime import date

# Human-friendly labels for known paper sources. The paper's `venue` (the real
# journal name) is preferred when present; these are the fallback when a source
# has no venue (e.g. arXiv), then the raw id as a last resort.
_SOURCE_LABELS = {
    "arxiv": "arXiv",
    "biorxiv": "bioRxiv",
    "medrxiv": "medRxiv",
    "pubmed": "PubMed",
    "openalex": "OpenAlex",
    "crossref": "Crossref",
    "semantic_scholar": "Semantic Scholar",
}


def _source_label(paper: dict) -> str:
    venue = (paper.get("venue") or "").strip()
    if venue:
        return venue
    src = (paper.get("source") or "").strip()
    return _SOURCE_LABELS.get(src.lower(), src)


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
    """Deterministic content/source-card footer: 'Source · Month D, YYYY'.

    Uses the paper's venue when available, else a friendly source label. Drops
    the date (and separator) when the paper carries no usable publication date,
    and returns just the date if somehow there is no source label.
    """
    label = _source_label(paper)
    when = _publication_date(paper)
    if label and when:
        return f"{label} · {when}"
    return label or when
