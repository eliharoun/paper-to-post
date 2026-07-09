#!/usr/bin/env python3
"""Fetch recent bioRxiv/medRxiv preprints and normalize to PaperInput."""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date

from scripts.lib.fetch_http import FetchError, get_text
from scripts.lib.models import PaperInput

BIORXIV_API = "https://api.biorxiv.org/details"

# bioRxiv /details returns ~100 records per call and is cursor-paginated. We
# advance the cursor to exhaust the window (it's a date-scoped, precise source).
BIORXIV_PAGE_SIZE = 100
BIORXIV_PAGE_DELAY_S = 0.3
BIORXIV_MAX_PAGES = 50  # safety ceiling: 50 x 100 = 5000 preprints/server


def build_biorxiv_url(server: str, since: str, until: str, cursor: int = 0) -> str:
    return f"{BIORXIV_API}/{server}/{since}/{until}/{cursor}"


def _to_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def parse_biorxiv_response(payload: dict) -> list[PaperInput]:
    papers: list[PaperInput] = []
    for item in payload.get("collection", []):
        server = (item.get("server") or "biorxiv").lower()
        doi = item.get("doi")
        authors = [a.strip() for a in (item.get("authors") or "").split(";") if a.strip()]
        papers.append(
            PaperInput(
                source=server,
                source_id=doi or item.get("title", ""),
                doi=doi,
                title=" ".join((item.get("title") or "").split()),
                abstract=(item.get("abstract") or None),
                authors=authors,
                venue=server,
                published_date=_to_date(item.get("date")),
                url=f"https://www.{server}.org/content/{doi}" if doi else "",
                field_of_study=item.get("category"),
                is_preprint=True,
                is_open_access=True,
                raw_payload={},
            )
        )
    return papers


def fetch_biorxiv(
    servers: list[str], since: str, until: str, *, sleep=time.sleep
) -> list[PaperInput]:
    """Fetch bioRxiv/medRxiv preprints for the window, paginating each server's
    cursor to exhaust results. `sleep` is injectable for tests."""
    out: list[PaperInput] = []
    for server in servers:
        cursor = 0
        for _ in range(BIORXIV_MAX_PAGES):
            body = get_text(build_biorxiv_url(server, since, until, cursor))
            batch = parse_biorxiv_response(json.loads(body))
            out.extend(batch)
            if len(batch) < BIORXIV_PAGE_SIZE:
                break  # last page for this server
            cursor += len(batch)
            sleep(BIORXIV_PAGE_DELAY_S)
        else:
            print(
                f"biorxiv: {server} hit the {BIORXIV_MAX_PAGES}-page ceiling; "
                f"window may be truncated",
                file=sys.stderr,
            )
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Fetch bioRxiv/medRxiv preprints")
    ap.add_argument("--servers", default="biorxiv,medrxiv")
    ap.add_argument("--since", required=True)
    ap.add_argument("--until", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    servers = [s.strip() for s in args.servers.split(",") if s.strip()]
    try:
        papers = fetch_biorxiv(servers, args.since, args.until)
    except FetchError as exc:
        print(f"biorxiv fetch failed: {exc}", file=sys.stderr)
        return 2

    with open(args.out, "w") as f:
        json.dump([p.model_dump(mode="json") for p in papers], f, indent=2, default=str)
    print(f"wrote {len(papers)} papers to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
