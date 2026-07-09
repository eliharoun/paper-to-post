from __future__ import annotations

from scripts.lib.models import PaperInput


def paper_key(paper: PaperInput) -> str:
    """Stable cross-source identity from a PaperInput. See paper_key_from_dict."""
    return paper_key_from_dict(paper.model_dump())


def paper_key_from_dict(paper: dict) -> str:
    """Stable cross-source identity, in priority order.

    arxiv:<id> > doi:<lower> > s2:<id> > openalex:<id> > <source>:<source_id>.
    Used by the dedupe ledger and dedupe merge so the same paper is never
    posted twice regardless of which source surfaced it. Works on a raw dict
    so callers need not reconstruct a full PaperInput.
    """
    if paper.get("arxiv_id"):
        return f"arxiv:{paper['arxiv_id']}"
    if paper.get("doi"):
        return f"doi:{paper['doi'].lower()}"
    if paper.get("semantic_scholar_id"):
        return f"s2:{paper['semantic_scholar_id']}"
    if paper.get("openalex_id"):
        return f"openalex:{paper['openalex_id']}"
    return f"{paper.get('source', '')}:{paper.get('source_id', '')}"
