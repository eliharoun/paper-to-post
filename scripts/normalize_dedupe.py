#!/usr/bin/env python3
"""Merge raw paper JSON files and dedupe into a single papers.json."""
from __future__ import annotations

import argparse
import glob
import json

from scripts.lib.textutil import title_hash


def _identity_keys(p: dict) -> list[str]:
    """Ordered dedupe keys for a paper: DOI, arXiv, S2, then title hash."""
    keys = []
    if p.get("doi"):
        keys.append(f"doi:{p['doi'].lower()}")
    if p.get("arxiv_id"):
        keys.append(f"arxiv:{p['arxiv_id']}")
    if p.get("semantic_scholar_id"):
        keys.append(f"s2:{p['semantic_scholar_id']}")
    keys.append(f"title:{title_hash(p.get('title', ''))}")
    return keys


def _canonical_url(p: dict) -> str:
    if p.get("doi"):
        return f"https://doi.org/{p['doi']}"
    if p.get("arxiv_id"):
        return f"https://arxiv.org/abs/{p['arxiv_id']}"
    return p.get("url", "")


def _merge(a: dict, b: dict) -> dict:
    """Merge b into a: union IDs, keep longest abstract, earliest date, canonical url."""
    out = dict(a)
    for field in (
        "doi", "arxiv_id", "semantic_scholar_id", "openalex_id",
        "venue", "pdf_url", "citation_count", "is_open_access",
        "is_preprint", "license", "field_of_study",
    ):
        if not out.get(field) and b.get(field) is not None:
            out[field] = b[field]
    if len(b.get("abstract") or "") > len(out.get("abstract") or ""):
        out["abstract"] = b["abstract"]
    # earliest published_date
    da, db = a.get("published_date"), b.get("published_date")
    if db and (not da or db < da):
        out["published_date"] = db
    out["url"] = _canonical_url(out)
    return out


def dedupe_papers(papers: list[dict]) -> list[dict]:
    """Deduplicate a list of paper dicts. First occurrence wins identity; others merge in."""
    key_to_idx: dict[str, int] = {}
    result: list[dict] = []
    for p in papers:
        keys = _identity_keys(p)
        hit = next((key_to_idx[k] for k in keys if k in key_to_idx), None)
        if hit is None:
            idx = len(result)
            # set canonical url even for singletons
            p = dict(p)
            p["url"] = _canonical_url(p)
            result.append(p)
            for k in keys:
                key_to_idx[k] = idx
        else:
            result[hit] = _merge(result[hit], p)
            for k in _identity_keys(result[hit]):
                key_to_idx.setdefault(k, hit)
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Merge + dedupe raw paper JSON -> papers.json")
    ap.add_argument("inputs", nargs="+", help="raw_*.json files (globs allowed)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    papers: list[dict] = []
    for pattern in args.inputs:
        for path in sorted(glob.glob(pattern)) or [pattern]:
            with open(path) as f:
                data = json.load(f)
            papers.extend(data if isinstance(data, list) else data.get("data", []))

    merged = dedupe_papers(papers)
    with open(args.out, "w") as f:
        json.dump(merged, f, indent=2, default=str)
    print(f"deduped {len(papers)} -> {len(merged)} papers, wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
