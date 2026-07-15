#!/usr/bin/env python3
"""Fetch recent papers from named flagship journals (Nature, The Lancet, Cell, ...).

Top journals like Nature and The Lancet expose no free public API that lists
recent papers with abstracts. But they are indexed in OpenAlex with clean dates,
abstracts, DOIs and venue names. So "papers from journal X" is best done as a
source-id filter over OpenAlex — the exact mirror of how `fetch_labs.py` does
"papers from lab X" as an institution-id filter.

This reuses OpenAlex's response parser; it only differs in the filter (by
`primary_location.source.id` + date window) and in tagging the source as
``journals``. It gives flagship venues a guaranteed stream into the candidate
pool; the venue-prestige bonus in `filtering.rule_score` then ranks them up.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from scripts.fetch_openalex import parse_openalex_response
from scripts.lib.fetch_http import FetchError, get_text
from scripts.lib.journals import JOURNAL_SOURCES, resolve_source_ids
from scripts.lib.models import PaperInput

OPENALEX_API = "https://api.openalex.org/works"

# A few journals x a short window is low volume, so a single 100-result page
# comfortably covers it; we warn if it somehow doesn't (mirrors fetch_labs).
JOURNALS_PAGE_SIZE = 100


def build_journals_params(
    source_ids: list[str],
    since: str,
    until: str,
    query: str | None = None,
    per_page: int = JOURNALS_PAGE_SIZE,
) -> dict:
    filters = [
        f"primary_location.source.id:{'|'.join(source_ids)}",
        f"from_publication_date:{since}",
        f"to_publication_date:{until}",
        "type:article",
        "has_abstract:true",  # the writer needs an abstract; drops paratext
    ]
    params = {
        "filter": ",".join(filters),
        "per-page": per_page,
        "sort": "publication_date:desc",
    }
    if query:
        params["search"] = query
    mailto = os.environ.get("OPENALEX_MAILTO") or os.environ.get("CONTACT_EMAIL")
    if mailto:
        params["mailto"] = mailto
    return params


def _relabel_as_journals(papers: list[PaperInput]) -> list[PaperInput]:
    """OpenAlex parser tags source=openalex; mark these as the journals source."""
    for p in papers:
        p.source = "journals"
    return papers


def fetch_journals(
    journals: list[str],
    since: str,
    until: str,
    query: str | None = None,
    per_page: int = JOURNALS_PAGE_SIZE,
) -> list[PaperInput]:
    source_ids = resolve_source_ids(journals)
    params = build_journals_params(source_ids, since, until, query, per_page)
    payload = json.loads(get_text(OPENALEX_API, params=params))
    papers = _relabel_as_journals(parse_openalex_response(payload))
    total = (payload.get("meta") or {}).get("count")
    if total is not None and total > len(papers):
        print(
            f"journals: fetched {len(papers)} of {total} matches (single page of "
            f"{per_page}; widen per_page if journals regularly exceed this)",
            file=sys.stderr,
        )
    return papers


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Fetch recent papers from flagship journals")
    ap.add_argument(
        "--journals",
        default=",".join(sorted(JOURNAL_SOURCES)),
        help="comma-separated journal names (default: all). "
        f"Known: {', '.join(sorted(JOURNAL_SOURCES))}",
    )
    ap.add_argument("--query", help="optional topic search to narrow results")
    ap.add_argument("--since", required=True)
    ap.add_argument("--until", required=True)
    ap.add_argument("--per-page", type=int, default=JOURNALS_PAGE_SIZE)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    journals = [x for x in args.journals.split(",") if x.strip()]
    try:
        papers = fetch_journals(journals, args.since, args.until, args.query, args.per_page)
    except ValueError as exc:
        print(f"journals fetch: {exc}", file=sys.stderr)
        return 2
    except FetchError as exc:
        print(f"journals fetch failed: {exc}", file=sys.stderr)
        return 2

    with open(args.out, "w") as f:
        json.dump([p.model_dump(mode="json") for p in papers], f, indent=2, default=str)
    print(f"wrote {len(papers)} papers to {args.out} (journals: {', '.join(journals)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
