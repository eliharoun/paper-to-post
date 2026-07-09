#!/usr/bin/env python3
"""Fetch/enrich papers from the Semantic Scholar Academic Graph API."""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date

from scripts.lib.fetch_http import FetchError, get_text
from scripts.lib.models import PaperInput

S2_FIELDS = (
    "paperId,title,abstract,year,publicationDate,url,venue,"
    "citationCount,isOpenAccess,openAccessPdf,fieldsOfStudy,externalIds,authors"
)

S2_SEARCH = "https://api.semanticscholar.org/graph/v1/paper/search"


def _to_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def _paper_from_s2(item: dict) -> PaperInput:
    ext = item.get("externalIds") or {}
    oa_pdf = item.get("openAccessPdf") or {}
    fields = item.get("fieldsOfStudy") or []
    return PaperInput(
        source="semantic_scholar",
        source_id=item.get("paperId", ""),
        semantic_scholar_id=item.get("paperId"),
        doi=ext.get("DOI"),
        arxiv_id=ext.get("ArXiv"),
        title=" ".join((item.get("title") or "").split()),
        abstract=(item.get("abstract") or None),
        authors=[a.get("name", "").strip() for a in item.get("authors", []) if a.get("name")],
        venue=item.get("venue") or None,
        published_date=_to_date(item.get("publicationDate")),
        url=item.get("url") or "",
        pdf_url=oa_pdf.get("url"),
        field_of_study=fields[0] if fields else None,
        citation_count=item.get("citationCount"),
        is_open_access=item.get("isOpenAccess"),
        is_preprint=(item.get("venue") or "").lower() in {"arxiv", "biorxiv", "medrxiv"},
        raw_payload={},
    )


def parse_s2_response(payload: dict) -> list[PaperInput]:
    """Parse an S2 search/bulk response ({data: [...]}) into PaperInput objects."""
    return [_paper_from_s2(item) for item in payload.get("data", [])]


def build_s2_params(query: str, since: str, until: str, limit: int = 100) -> dict:
    return {
        "query": query,
        "fields": S2_FIELDS,
        "publicationDateOrYear": f"{since}:{until}",
        "limit": limit,
    }


def _headers() -> dict:
    key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "")
    return {"x-api-key": key} if key else {}


def fetch_s2(query: str, since: str, until: str, limit: int = 100) -> list[PaperInput]:
    params = build_s2_params(query, since, until, limit)
    body = get_text(S2_SEARCH, params=params, headers=_headers())
    return parse_s2_response(json.loads(body))


def _merge_enrichment(base: list[dict], enrich: list[PaperInput]) -> list[dict]:
    """Attach S2 citation/venue/OA to base papers matched by arxiv_id or doi."""
    by_arxiv = {p.arxiv_id: p for p in enrich if p.arxiv_id}
    by_doi = {p.doi.lower(): p for p in enrich if p.doi}
    for row in base:
        match = by_arxiv.get(row.get("arxiv_id")) or (
            by_doi.get(row["doi"].lower()) if row.get("doi") else None
        )
        if match:
            row.setdefault("citation_count", match.citation_count)
            row.setdefault("venue", match.venue)
            if match.is_open_access is not None and row.get("is_open_access") is None:
                row["is_open_access"] = match.is_open_access
            if match.pdf_url and not row.get("pdf_url"):
                row["pdf_url"] = match.pdf_url
    return base


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Fetch/enrich via Semantic Scholar")
    ap.add_argument("--query", required=True)
    ap.add_argument("--since", required=True)
    ap.add_argument("--until", required=True)
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--enrich", help="path to an existing papers JSON to enrich in place")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    try:
        s2_papers = fetch_s2(args.query, args.since, args.until, args.limit)
    except FetchError as exc:
        print(f"s2 fetch failed: {exc}", file=sys.stderr)
        return 2

    if args.enrich:
        with open(args.enrich) as f:
            base = json.load(f)
        out = _merge_enrichment(base, s2_papers)
    else:
        out = [p.model_dump(mode="json") for p in s2_papers]

    with open(args.out, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"wrote {len(out)} papers to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
