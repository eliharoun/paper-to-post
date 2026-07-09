#!/usr/bin/env python3
"""Fetch recent arXiv papers for configured categories and normalize to PaperInput."""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date, datetime

import feedparser

from scripts.lib.fetch_http import FetchError, get_text
from scripts.lib.models import PaperInput

# arXiv asks callers to page in batches and pause ~3s between requests.
ARXIV_PAGE_SIZE = 100
ARXIV_PAGE_DELAY_S = 3.0
# Safety ceiling on pages so a huge/misconfigured window can't loop forever.
# 30 pages x 100 = 3000 papers, well above a normal multi-day window.
ARXIV_MAX_PAGES = 30

_ARXIV_ID_RE = re.compile(r"arxiv\.org/abs/(?P<id>.+?)(v\d+)?$")

ARXIV_API = "http://export.arxiv.org/api/query"


def _arxiv_id_from_url(url: str) -> str | None:
    m = _ARXIV_ID_RE.search(url)
    return m.group("id") if m else None


def _to_date(struct_time) -> date | None:
    if not struct_time:
        return None
    return datetime(*struct_time[:6]).date()


def parse_arxiv_atom(atom_xml: str) -> list[PaperInput]:
    """Parse an arXiv Atom feed body into PaperInput objects."""
    feed = feedparser.parse(atom_xml)
    papers: list[PaperInput] = []
    for e in feed.entries:
        html_url = ""
        pdf_url = None
        for link in e.get("links", []):
            if link.get("type") == "text/html":
                html_url = link.get("href", "")
            elif link.get("title") == "pdf" or link.get("type") == "application/pdf":
                pdf_url = link.get("href")
        arxiv_id = _arxiv_id_from_url(e.get("id", "")) or _arxiv_id_from_url(html_url)
        authors = [a.get("name", "").strip() for a in e.get("authors", []) if a.get("name")]
        categories = [
            t.get("term") for t in e.get("tags", []) if t.get("term")
        ]
        papers.append(
            PaperInput(
                source="arxiv",
                source_id=arxiv_id or e.get("id", ""),
                arxiv_id=arxiv_id,
                title=" ".join(e.get("title", "").split()),
                abstract=" ".join(e.get("summary", "").split()) or None,
                authors=authors,
                url=html_url or e.get("id", ""),
                pdf_url=pdf_url,
                published_date=_to_date(e.get("published_parsed")),
                updated_date=(
                    datetime(*e.updated_parsed[:6]) if e.get("updated_parsed") else None
                ),
                field_of_study=categories[0] if categories else None,
                is_preprint=True,
                is_open_access=True,
                raw_payload={"arxiv_categories": categories},
            )
        )
    return papers


def build_arxiv_query(
    categories: list[str], since: str, until: str, start: int = 0, max_results: int = 50
) -> dict:
    """Build arXiv API query params. Dates are YYYY-MM-DD; converted to YYYYMMDDHHMM."""
    cats = " OR ".join(f"cat:{c}" for c in categories)
    s = since.replace("-", "") + "0000"
    u = until.replace("-", "") + "0000"
    search = f"({cats}) AND submittedDate:[{s} TO {u}]"
    return {
        "search_query": search,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "start": start,
        "max_results": max_results,
    }


def fetch_arxiv(
    categories: list[str],
    since: str,
    until: str,
    max_results: int | None = None,
    *,
    sleep=time.sleep,
) -> list[PaperInput]:
    """Fetch arXiv papers in the window, paginating to exhaust results.

    arXiv is category-scoped (high precision), so we page through the whole
    window rather than truncating. `max_results` caps the total for callers that
    want a bounded pull (None = exhaust, subject to ARXIV_MAX_PAGES). `sleep` is
    injectable for tests.
    """
    papers: list[PaperInput] = []
    for page in range(ARXIV_MAX_PAGES):
        params = build_arxiv_query(
            categories, since, until, start=page * ARXIV_PAGE_SIZE, max_results=ARXIV_PAGE_SIZE
        )
        batch = parse_arxiv_atom(get_text(ARXIV_API, params=params))
        papers.extend(batch)
        if max_results is not None and len(papers) >= max_results:
            return papers[:max_results]
        if len(batch) < ARXIV_PAGE_SIZE:
            break  # last page reached
        sleep(ARXIV_PAGE_DELAY_S)  # be polite between pages
    else:
        # Loop exhausted the page ceiling without a short page — window truncated.
        print(
            f"arxiv: hit the {ARXIV_MAX_PAGES}-page ceiling "
            f"({len(papers)} papers); window may be truncated",
            file=sys.stderr,
        )
    return papers


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Fetch recent arXiv papers -> PaperInput JSON")
    ap.add_argument("--since", required=True, help="YYYY-MM-DD (UTC)")
    ap.add_argument("--until", required=True, help="YYYY-MM-DD (UTC)")
    ap.add_argument("--categories", required=True, help="comma-separated, e.g. cs.AI,cs.CL")
    ap.add_argument(
        "--max-results",
        type=int,
        default=0,
        help="cap total papers (0 = exhaust the window, the default)",
    )
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    cats = [c.strip() for c in args.categories.split(",") if c.strip()]
    try:
        papers = fetch_arxiv(cats, args.since, args.until, args.max_results or None)
    except FetchError as exc:
        print(f"arxiv fetch failed: {exc}", file=sys.stderr)
        return 2

    with open(args.out, "w") as f:
        json.dump([p.model_dump(mode="json") for p in papers], f, indent=2, default=str)
    print(f"wrote {len(papers)} papers to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
