#!/usr/bin/env python3
"""Fetch/enrich works from the Crossref REST API."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import date

from scripts.lib.fetch_http import FetchError, get_text
from scripts.lib.models import PaperInput

CROSSREF_API = "https://api.crossref.org/works"
_TAG = re.compile(r"<[^>]+>")

# Crossref is a keyword source (relevance-ranked, noisy tail), so we page a
# bounded number of times rather than exhausting it. 3 x 100 = 300 newest works.
CROSSREF_PAGE_SIZE = 100
CROSSREF_MAX_PAGES = 3
CROSSREF_PAGE_DELAY_S = 0.5


def strip_jats(text: str | None) -> str | None:
    if text is None:
        return None
    return " ".join(_TAG.sub(" ", text).split()) or None


def _first(seq) -> str | None:
    return seq[0] if isinstance(seq, list) and seq else None


def _date_from_parts(published: dict | None) -> date | None:
    if not published:
        return None
    parts = (published.get("date-parts") or [[]])[0]
    if not parts:
        return None
    y = parts[0]
    m = parts[1] if len(parts) > 1 else 1
    d = parts[2] if len(parts) > 2 else 1
    try:
        return date(y, m, d)
    except (ValueError, TypeError):
        return None


def parse_crossref_response(payload: dict) -> list[PaperInput]:
    items = payload.get("message", {}).get("items", [])
    papers: list[PaperInput] = []
    for item in items:
        authors = []
        for a in item.get("author", []):
            name = " ".join(x for x in (a.get("given"), a.get("family")) if x)
            if name:
                authors.append(name)
        doi = item.get("DOI")
        papers.append(
            PaperInput(
                source="crossref",
                source_id=doi or "",
                doi=doi,
                title=" ".join((_first(item.get("title")) or "").split()),
                abstract=strip_jats(item.get("abstract")),
                authors=authors,
                venue=_first(item.get("container-title")),
                published_date=_date_from_parts(item.get("published")),
                url=item.get("URL") or (f"https://doi.org/{doi}" if doi else ""),
                citation_count=item.get("is-referenced-by-count"),
                raw_payload={},
            )
        )
    return papers


def build_crossref_params(
    query: str, since: str, until: str, rows: int = 50, offset: int = 0
) -> dict:
    params = {
        "query": query,
        "filter": f"from-pub-date:{since},until-pub-date:{until}",
        "rows": rows,
        "offset": offset,
        "sort": "published",
        "order": "desc",
    }
    email = os.environ.get("CONTACT_EMAIL")
    if email:
        params["mailto"] = email
    return params


def fetch_crossref(
    query: str, since: str, until: str, max_pages: int | None = None, *, sleep=time.sleep
) -> list[PaperInput]:
    """Fetch newest Crossref works for the query, up to a bounded number of pages.

    Crossref is a relevance-ranked keyword source with a noisy long tail, so this
    deliberately caps coverage (and logs when the tail is truncated) rather than
    exhausting it. `max_pages` defaults to CROSSREF_MAX_PAGES (resolved at call
    time). `sleep` is injectable for tests.
    """
    if max_pages is None:
        max_pages = CROSSREF_MAX_PAGES
    papers: list[PaperInput] = []
    total = None
    for page in range(max_pages):
        params = build_crossref_params(
            query, since, until, rows=CROSSREF_PAGE_SIZE, offset=page * CROSSREF_PAGE_SIZE
        )
        payload = json.loads(get_text(CROSSREF_API, params=params))
        if total is None:
            total = payload.get("message", {}).get("total-results")
        batch = parse_crossref_response(payload)
        papers.extend(batch)
        if len(batch) < CROSSREF_PAGE_SIZE:
            break  # exhausted before hitting the page cap
        sleep(CROSSREF_PAGE_DELAY_S)
    if total is not None and total > len(papers):
        print(
            f"crossref: fetched {len(papers)} of {total} matches "
            f"(capped at {max_pages} pages; keyword tail truncated)",
            file=sys.stderr,
        )
    return papers


def _enrich(base: list[dict], cr: list[PaperInput]) -> list[dict]:
    by_doi = {p.doi.lower(): p for p in cr if p.doi}
    for row in base:
        if row.get("doi") and row["doi"].lower() in by_doi:
            match = by_doi[row["doi"].lower()]
            if not row.get("venue") and match.venue:
                row["venue"] = match.venue
            if row.get("citation_count") is None and match.citation_count is not None:
                row["citation_count"] = match.citation_count
            if not row.get("abstract") and match.abstract:
                row["abstract"] = match.abstract
    return base


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Fetch/enrich via Crossref")
    ap.add_argument("--query")
    ap.add_argument("--since")
    ap.add_argument("--until")
    ap.add_argument("--max-pages", type=int, default=CROSSREF_MAX_PAGES,
                    help=f"pages of {CROSSREF_PAGE_SIZE} to fetch (default {CROSSREF_MAX_PAGES})")
    ap.add_argument("--enrich", help="path to papers JSON to enrich in place (matches by DOI)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    try:
        if args.enrich:
            with open(args.enrich) as f:
                base = json.load(f)
            dois = [p["doi"] for p in base if p.get("doi")]
            cr: list[PaperInput] = []
            for doi in dois:
                body = get_text(f"{CROSSREF_API}/{doi}")
                msg = json.loads(body).get("message")
                if msg:
                    cr.extend(parse_crossref_response({"message": {"items": [msg]}}))
            out = _enrich(base, cr)
        else:
            if not (args.query and args.since and args.until):
                print("--query/--since/--until required unless --enrich", file=sys.stderr)
                return 2
            out = [
                p.model_dump(mode="json")
                for p in fetch_crossref(args.query, args.since, args.until, args.max_pages)
            ]
    except FetchError as exc:
        print(f"crossref fetch failed: {exc}", file=sys.stderr)
        return 2

    with open(args.out, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"wrote {len(out)} records to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
