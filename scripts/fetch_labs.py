#!/usr/bin/env python3
"""Fetch recent papers from named industry AI labs (Meta, Google, DeepMind, ...).

The labs' own sites (ai.meta.com, research.google/pubs) expose no date-filterable
API — Google Research is year-only server HTML and Meta AI is a JS SPA that blocks
plain HTTP. But those labs publish to arXiv and are indexed in OpenAlex with clean
dates, abstracts, DOIs and PDF links. So "papers from lab X" is best done as an
affiliation filter over OpenAlex, not by scraping the labs' websites.

This reuses OpenAlex's response parser; it only differs in the query (filter by
institution id + date window) and in tagging the source as ``labs``.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from scripts.fetch_openalex import parse_openalex_response
from scripts.lib.fetch_http import FetchError, get_text
from scripts.lib.models import PaperInput

OPENALEX_API = "https://api.openalex.org/works"

# OpenAlex institution ids per lab. A lab can span several country-scoped ids;
# we OR them so e.g. "google" covers the US and UK Google entities.
LAB_INSTITUTIONS: dict[str, list[str]] = {
    "meta": ["I4210114444", "I2252078561", "I4210111288"],  # Meta US / Israel / UK (FAIR)
    "google": ["I1291425158", "I4210113297"],               # Google US / UK
    "deepmind": ["I4210090411"],                            # Google DeepMind
}
DEFAULT_LABS = ["meta", "google", "deepmind"]


def resolve_institution_ids(labs: list[str]) -> list[str]:
    """Map lab names to OpenAlex institution ids, preserving order, de-duped."""
    ids: list[str] = []
    for lab in labs:
        key = lab.strip().lower()
        if key not in LAB_INSTITUTIONS:
            known = ", ".join(sorted(LAB_INSTITUTIONS))
            raise ValueError(f"unknown lab {lab!r}; known labs: {known}")
        for iid in LAB_INSTITUTIONS[key]:
            if iid not in ids:
                ids.append(iid)
    return ids


# Labs is affiliation-scoped (a few institutions × a short window = low volume),
# so a single 100-result page comfortably covers it; we warn if it somehow doesn't.
LABS_PAGE_SIZE = 100


def build_labs_params(
    institution_ids: list[str],
    since: str,
    until: str,
    query: str | None = None,
    per_page: int = LABS_PAGE_SIZE,
) -> dict:
    filters = [
        f"authorships.institutions.id:{'|'.join(institution_ids)}",
        f"from_publication_date:{since}",
        f"to_publication_date:{until}",
        "type:article",
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


def _relabel_as_labs(papers: list[PaperInput]) -> list[PaperInput]:
    """OpenAlex parser tags source=openalex; mark these as the labs source."""
    for p in papers:
        p.source = "labs"
    return papers


def fetch_labs(
    labs: list[str],
    since: str,
    until: str,
    query: str | None = None,
    per_page: int = LABS_PAGE_SIZE,
) -> list[PaperInput]:
    institution_ids = resolve_institution_ids(labs)
    params = build_labs_params(institution_ids, since, until, query, per_page)
    payload = json.loads(get_text(OPENALEX_API, params=params))
    papers = _relabel_as_labs(parse_openalex_response(payload))
    total = (payload.get("meta") or {}).get("count")
    if total is not None and total > len(papers):
        print(
            f"labs: fetched {len(papers)} of {total} matches (single page of "
            f"{per_page}; widen per_page if labs regularly exceed this)",
            file=sys.stderr,
        )
    return papers


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Fetch recent papers from industry AI labs")
    ap.add_argument(
        "--labs",
        default=",".join(DEFAULT_LABS),
        help="comma-separated lab names (default: all). "
        f"Known: {', '.join(sorted(LAB_INSTITUTIONS))}",
    )
    ap.add_argument("--query", help="optional topic search to narrow results")
    ap.add_argument("--since", required=True)
    ap.add_argument("--until", required=True)
    ap.add_argument("--per-page", type=int, default=50)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    labs = [x for x in args.labs.split(",") if x.strip()]
    try:
        papers = fetch_labs(labs, args.since, args.until, args.query, args.per_page)
    except ValueError as exc:
        print(f"labs fetch: {exc}", file=sys.stderr)
        return 2
    except FetchError as exc:
        print(f"labs fetch failed: {exc}", file=sys.stderr)
        return 2

    with open(args.out, "w") as f:
        json.dump([p.model_dump(mode="json") for p in papers], f, indent=2, default=str)
    print(f"wrote {len(papers)} papers to {args.out} (labs: {', '.join(labs)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
