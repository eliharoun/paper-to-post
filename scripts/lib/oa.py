"""Resolve a legal open-access PDF for a paper via its DOI (Unpaywall).

Many papers on paywalled journal pages still have a free, legal OA copy (author
manuscript, PubMed Central, repository). Unpaywall indexes these by DOI. We use it
to populate pdf_url / is_open_access so the (copyright-gated) first-page screenshot
can fire for any paper that has a legitimately free PDF — not just arXiv/bioRxiv.

We never fetch paywalled PDFs; if no OA location exists, we leave the paper as-is.
"""
from __future__ import annotations

import json
import os

import httpx

UNPAYWALL = "https://api.unpaywall.org/v2"


def parse_unpaywall(payload: dict) -> tuple[bool, str | None]:
    """From an Unpaywall response, return (is_oa, best_oa_pdf_url_or_None)."""
    is_oa = bool(payload.get("is_oa"))
    if not is_oa:
        return False, None
    # prefer best_oa_location, then scan all locations for a direct PDF url
    best = payload.get("best_oa_location") or {}
    url = best.get("url_for_pdf") or best.get("url")
    if not url:
        for loc in payload.get("oa_locations") or []:
            url = loc.get("url_for_pdf") or loc.get("url")
            if url:
                break
    return True, url or None


def resolve_oa_pdf(
    doi: str, email: str, *, timeout: float = 20.0,
    transport: httpx.BaseTransport | None = None,
) -> tuple[bool, str | None]:
    """Look up a DOI on Unpaywall. Returns (is_oa, pdf_url). (False, None) on any error."""
    if not doi or not email:
        return False, None
    try:
        with httpx.Client(timeout=timeout, transport=transport, follow_redirects=True) as c:
            resp = c.get(f"{UNPAYWALL}/{doi}", params={"email": email})
        if resp.status_code != 200:
            return False, None
        return parse_unpaywall(resp.json())
    except (httpx.HTTPError, json.JSONDecodeError, ValueError):
        return False, None


def enrich_papers_with_oa(papers: list[dict], email: str) -> int:
    """Fill pdf_url / is_open_access for papers that have a DOI and an OA copy.

    Skips papers that already have a pdf_url (e.g. arXiv). Returns count enriched.
    """
    enriched = 0
    for p in papers:
        if p.get("pdf_url"):
            continue
        doi = p.get("doi")
        if not doi:
            continue
        is_oa, url = resolve_oa_pdf(doi, email)
        if is_oa:
            p["is_open_access"] = True
            if url:
                p["pdf_url"] = url
                enriched += 1
    return enriched


def contact_email() -> str:
    return os.environ.get("CONTACT_EMAIL", "")
