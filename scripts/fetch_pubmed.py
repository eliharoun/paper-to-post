#!/usr/bin/env python3
"""Fetch recent PubMed articles via NCBI E-utilities (esearch + efetch)."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date
from xml.etree import ElementTree as ET

from scripts.lib.fetch_http import FetchError, get_text
from scripts.lib.models import PaperInput

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# esearch page size, and how many PMIDs to efetch per request (URL-length safe).
PUBMED_ESEARCH_PAGE = 200
PUBMED_EFETCH_BATCH = 200
PUBMED_PAGE_DELAY_S = 0.4  # NCBI allows ~3 req/s without a key, more with one
# Safety ceiling on total IDs collected (30 pages x 200 = 6000).
PUBMED_MAX_PAGES = 30

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def build_esearch_params(
    query: str, since: str, until: str, retmax: int = 50, retstart: int = 0
) -> dict:
    return {
        "db": "pubmed",
        "term": query,
        "mindate": since.replace("-", "/"),
        "maxdate": until.replace("-", "/"),
        "datetype": "pdat",
        "retmax": retmax,
        "retstart": retstart,
        "retmode": "json",
    }


def _pubdate(article: ET.Element) -> date | None:
    pd = article.find(".//PubDate")
    if pd is None:
        return None
    year = pd.findtext("Year")
    if not year:
        return None
    month_raw = (pd.findtext("Month") or "1").strip()
    month = _MONTHS.get(month_raw.lower()[:3], None)
    if month is None:
        try:
            month = int(month_raw)
        except ValueError:
            month = 1
    try:
        day = int(pd.findtext("Day") or "1")
        return date(int(year), month, day)
    except ValueError:
        return None


def parse_pubmed_xml(xml_text: str) -> list[PaperInput]:
    # NCBI sometimes returns HTTP 200 with a non-XML error page (esp. under load).
    # Surface that as FetchError so callers treat it as a source failure, not a
    # crash — ET.ParseError is a SyntaxError, which generic handlers won't catch.
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise FetchError(f"pubmed: malformed XML response ({exc})") from exc
    papers: list[PaperInput] = []
    for art in root.findall(".//PubmedArticle"):
        pmid = art.findtext(".//PMID") or ""
        title = " ".join((art.findtext(".//ArticleTitle") or "").split())
        abstract_parts = [
            (el.text or "") for el in art.findall(".//Abstract/AbstractText")
        ]
        abstract = " ".join(" ".join(abstract_parts).split()) or None
        authors = []
        for a in art.findall(".//AuthorList/Author"):
            last, fore = a.findtext("LastName"), a.findtext("ForeName")
            if last and fore:
                authors.append(f"{fore} {last}")
            elif last:
                authors.append(last)
        doi = None
        for aid in art.findall(".//ArticleIdList/ArticleId"):
            if aid.get("IdType") == "doi":
                doi = aid.text
        venue = art.findtext(".//Journal/Title")
        papers.append(
            PaperInput(
                source="pubmed",
                source_id=pmid,
                doi=doi,
                title=title,
                abstract=abstract,
                authors=authors,
                venue=venue,
                published_date=_pubdate(art),
                url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                is_preprint=False,
                raw_payload={},
            )
        )
    return papers


def _common_params() -> dict:
    p = {}
    email = os.environ.get("CONTACT_EMAIL")
    key = os.environ.get("NCBI_API_KEY")
    if email:
        p["email"] = email
    if key:
        p["api_key"] = key
    return p


def _esearch_all_ids(query: str, since: str, until: str, *, sleep=time.sleep) -> list[str]:
    """Page through esearch to collect all PMIDs in the window (ceiling-guarded)."""
    ids: list[str] = []
    for page in range(PUBMED_MAX_PAGES):
        params = {
            **build_esearch_params(
                query, since, until, retmax=PUBMED_ESEARCH_PAGE,
                retstart=page * PUBMED_ESEARCH_PAGE,
            ),
            **_common_params(),
        }
        body = get_text(f"{EUTILS}/esearch.fcgi", params=params)
        batch = json.loads(body).get("esearchresult", {}).get("idlist", [])
        ids.extend(batch)
        if len(batch) < PUBMED_ESEARCH_PAGE:
            break  # last page
        sleep(PUBMED_PAGE_DELAY_S)
    else:
        # Exhausted the page ceiling without a short page — window truncated.
        print(
            f"pubmed: hit the {PUBMED_MAX_PAGES}-page ceiling "
            f"({len(ids)} ids); window may be truncated",
            file=sys.stderr,
        )
    return ids


def fetch_pubmed(
    query: str, since: str, until: str, retmax: int | None = None, *, sleep=time.sleep
) -> list[PaperInput]:
    """Fetch PubMed articles in the window, paginating esearch to exhaust results.

    `retmax` caps the total (None = exhaust, subject to PUBMED_MAX_PAGES). PMIDs
    are then efetched in URL-safe batches. `sleep` is injectable for tests.
    """
    ids = _esearch_all_ids(query, since, until, sleep=sleep)
    if retmax is not None:
        ids = ids[:retmax]
    if not ids:
        return []
    papers: list[PaperInput] = []
    for i in range(0, len(ids), PUBMED_EFETCH_BATCH):
        batch_ids = ids[i : i + PUBMED_EFETCH_BATCH]
        fetch_params = {
            "db": "pubmed", "id": ",".join(batch_ids), "rettype": "abstract",
            "retmode": "xml", **_common_params(),
        }
        papers.extend(parse_pubmed_xml(get_text(f"{EUTILS}/efetch.fcgi", params=fetch_params)))
        if i + PUBMED_EFETCH_BATCH < len(ids):
            sleep(PUBMED_PAGE_DELAY_S)
    return papers


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Fetch PubMed articles via E-utilities")
    ap.add_argument("--query", required=True)
    ap.add_argument("--since", required=True)
    ap.add_argument("--until", required=True)
    ap.add_argument(
        "--retmax",
        type=int,
        default=0,
        help="cap total articles (0 = exhaust the window, the default)",
    )
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    try:
        papers = fetch_pubmed(args.query, args.since, args.until, args.retmax or None)
    except FetchError as exc:
        print(f"pubmed fetch failed: {exc}", file=sys.stderr)
        return 2

    with open(args.out, "w") as f:
        json.dump([p.model_dump(mode="json") for p in papers], f, indent=2, default=str)
    print(f"wrote {len(papers)} papers to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
