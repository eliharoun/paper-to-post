#!/usr/bin/env python3
"""Fetch recent works from OpenAlex and normalize to PaperInput."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date

from scripts.lib.fetch_http import FetchError, get_text
from scripts.lib.models import PaperInput

OPENALEX_API = "https://api.openalex.org/works"

# OpenAlex is a keyword source (relevance-ranked, noisy tail), so we page a
# bounded number of times rather than exhausting it. 3 x 100 = 300 works.
OPENALEX_PAGE_SIZE = 100
OPENALEX_MAX_PAGES = 3
OPENALEX_PAGE_DELAY_S = 0.5


def invert_abstract(inverted_index: dict | None) -> str | None:
    """Reconstruct plain text from OpenAlex's {word: [positions]} inverted index."""
    if not inverted_index:
        return None
    positions: list[tuple[int, str]] = []
    for word, idxs in inverted_index.items():
        for i in idxs:
            positions.append((i, word))
    positions.sort()
    return " ".join(word for _, word in positions) or None


def _to_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def _strip_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    return doi.replace("https://doi.org/", "")


def parse_openalex_response(payload: dict) -> list[PaperInput]:
    papers: list[PaperInput] = []
    for item in payload.get("results", []):
        loc = item.get("primary_location") or {}
        source = loc.get("source") or {}
        oa_id = (item.get("id") or "").rsplit("/", 1)[-1] or None
        papers.append(
            PaperInput(
                source="openalex",
                source_id=oa_id or "",
                openalex_id=oa_id,
                doi=_strip_doi(item.get("doi")),
                title=" ".join((item.get("title") or "").split()),
                abstract=invert_abstract(item.get("abstract_inverted_index")),
                authors=[
                    a.get("author", {}).get("display_name", "").strip()
                    for a in item.get("authorships", [])
                    if a.get("author", {}).get("display_name")
                ],
                venue=source.get("display_name"),
                published_date=_to_date(item.get("publication_date")),
                url=loc.get("landing_page_url") or "",
                pdf_url=loc.get("pdf_url"),
                citation_count=item.get("cited_by_count"),
                is_open_access=(item.get("open_access") or {}).get("is_oa"),
                raw_payload={},
            )
        )
    return papers


def build_openalex_params(
    query: str,
    since: str,
    until: str,
    per_page: int = 50,
    page: int = 1,
    subfields: list[str] | None = None,
) -> dict:
    """Build OpenAlex /works params.

    Two query modes (they compose):
    - `subfields`: OR-list of OpenAlex subfield ids on `primary_topic.subfield.id`
      — a precise, arXiv-categories-equivalent filter. When set, we also restrict
      to English articles to cut cross-language/dataset noise. NOTE: OpenAlex
      `search` is full-text AND across ALL words, so a long multi-term search
      returns ~nothing; prefer subfields (+ at most a short `query` phrase).
    - `query`: free-text `search`. Omitted entirely when empty.
    """
    filters = [f"from_publication_date:{since}", f"to_publication_date:{until}"]
    if subfields:
        filters.append(f"primary_topic.subfield.id:{'|'.join(subfields)}")
        # Restrict to real English articles that carry an abstract (the writer
        # needs one) and drop paratext (tables of contents, dataset records, etc.).
        filters += ["type:article", "language:en", "has_abstract:true", "is_paratext:false"]
    params = {
        "filter": ",".join(filters),
        "per-page": per_page,
        "page": page,
        "sort": "publication_date:desc",
    }
    if query:
        params["search"] = query
    mailto = os.environ.get("OPENALEX_MAILTO") or os.environ.get("CONTACT_EMAIL")
    if mailto:
        params["mailto"] = mailto
    return params


def fetch_openalex(
    query: str,
    since: str,
    until: str,
    max_pages: int | None = None,
    *,
    subfields: list[str] | None = None,
    sleep=time.sleep,
) -> list[PaperInput]:
    """Fetch newest OpenAlex works, up to a bounded number of pages.

    OpenAlex is journal-heavy and lags arXiv preprints, so for CS it's a bounded
    supplement to the exhausted arXiv stream. Prefer `subfields` for precision;
    `query` alone is a strict full-text AND (long queries match nothing). Caps
    coverage and logs when the tail is truncated. `max_pages` defaults to
    OPENALEX_MAX_PAGES (resolved at call time). `sleep` is injectable for tests.
    """
    if max_pages is None:
        max_pages = OPENALEX_MAX_PAGES
    papers: list[PaperInput] = []
    total = None
    for page in range(1, max_pages + 1):
        params = build_openalex_params(
            query, since, until, per_page=OPENALEX_PAGE_SIZE, page=page, subfields=subfields
        )
        payload = json.loads(get_text(OPENALEX_API, params=params))
        if total is None:
            total = (payload.get("meta") or {}).get("count")
        batch = parse_openalex_response(payload)
        papers.extend(batch)
        if len(batch) < OPENALEX_PAGE_SIZE:
            break
        sleep(OPENALEX_PAGE_DELAY_S)
    if total is not None and total > len(papers):
        print(
            f"openalex: fetched {len(papers)} of {total} matches "
            f"(capped at {max_pages} pages; keyword tail truncated)",
            file=sys.stderr,
        )
    return papers


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Fetch OpenAlex works")
    ap.add_argument("--query", default="", help="optional short search phrase (AND across words)")
    ap.add_argument("--subfields", default="",
                    help="comma-separated OpenAlex subfield ids, e.g. 1702,1707,1712 (preferred)")
    ap.add_argument("--since", required=True)
    ap.add_argument("--until", required=True)
    ap.add_argument("--max-pages", type=int, default=OPENALEX_MAX_PAGES,
                    help=f"pages of {OPENALEX_PAGE_SIZE} to fetch (default {OPENALEX_MAX_PAGES})")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    subfields = [s.strip() for s in args.subfields.split(",") if s.strip()] or None
    if not args.query and not subfields:
        print("provide --subfields (preferred) and/or --query", file=sys.stderr)
        return 2
    try:
        papers = fetch_openalex(
            args.query, args.since, args.until, args.max_pages, subfields=subfields
        )
    except FetchError as exc:
        print(f"openalex fetch failed: {exc}", file=sys.stderr)
        return 2

    with open(args.out, "w") as f:
        json.dump([p.model_dump(mode="json") for p in papers], f, indent=2, default=str)
    print(f"wrote {len(papers)} papers to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
