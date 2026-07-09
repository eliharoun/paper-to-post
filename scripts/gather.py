#!/usr/bin/env python3
"""Gather candidates for one topic: run its configured sources, dedupe, filter.

This is the topic-agnostic front door to the pipeline. Given a topic id, it
reads that topic's `sources` block from config/topics.yml and runs exactly the
sources listed there — no source knowledge lives in the caller (the skill just
calls `research-gather --topic <id>`). Adding/removing a source for a topic is a
config edit, nothing else.

Flow: for each configured source -> fetch (resilient: a failing source is logged
and skipped, not fatal) -> write raw_<source>.json -> dedupe -> rule-filter ->
candidates.json. Exit 0 with candidates (possibly empty); exit 2 only if the
topic is unknown or *every* source failed.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from xml.etree.ElementTree import ParseError as XMLParseError

from scripts.filter_prescore import run as filter_run
from scripts.lib.config import TopicConfig, load_topics
from scripts.lib.fetch_http import FetchError
from scripts.normalize_dedupe import dedupe_papers


def _window(day: str, lookback_hours: int) -> tuple[str, str]:
    """Return (since, until) YYYY-MM-DD for a lookback window ending on `day`."""
    until = datetime.fromisoformat(day)
    since = until - timedelta(hours=lookback_hours)
    return since.strftime("%Y-%m-%d"), until.strftime("%Y-%m-%d")


def _fetch_source(name: str, src, since: str, until: str) -> list:
    """Dispatch one configured source to its fetcher. Returns list[PaperInput]."""
    # Imported lazily so a fetcher's heavy deps don't load unless its source runs.
    if name == "arxiv":
        from scripts.fetch_arxiv import fetch_arxiv
        return fetch_arxiv(src.categories, since, until)
    if name == "openalex":
        from scripts.fetch_openalex import fetch_openalex
        return fetch_openalex(src.query, since, until, subfields=src.subfields or None)
    if name == "crossref":
        from scripts.fetch_crossref import fetch_crossref
        return fetch_crossref(src.query, since, until)
    if name == "semantic_scholar":
        from scripts.fetch_semantic_scholar import fetch_s2
        return fetch_s2(src.query, since, until)
    if name == "pubmed":
        from scripts.fetch_pubmed import fetch_pubmed
        return fetch_pubmed(src.query, since, until)
    if name == "biorxiv":
        from scripts.fetch_biorxiv import fetch_biorxiv
        return fetch_biorxiv(src.servers, since, until)
    if name == "labs":
        from scripts.fetch_labs import fetch_labs
        return fetch_labs(src.labs, since, until, src.query or None)
    raise ValueError(f"unknown source: {name}")


def gather(
    topic: TopicConfig,
    since: str,
    until: str,
    out_dir: str,
    *,
    topics_path: str | None = None,
) -> tuple[int, int]:
    """Run a topic's sources, dedupe, filter. Returns (n_candidates, n_sources_ok).

    Writes raw_<source>.json, papers.json, candidates.json under out_dir.
    Raises RuntimeError if every configured source failed.
    """
    import os
    os.makedirs(out_dir, exist_ok=True)

    active = topic.sources.active()
    if not active:
        raise RuntimeError(f"topic '{topic.id}' configures no sources")

    all_papers: list[dict] = []
    ok = 0
    for name in active:
        src = getattr(topic.sources, name)
        try:
            papers = _fetch_source(name, src, since, until)
        except (FetchError, ValueError, XMLParseError) as exc:
            # Resilient by design: one source failing (rate-limit, bad payload,
            # malformed XML/JSON) is logged and skipped, never fatal.
            print(f"gather: source '{name}' failed: {exc} (skipping)", file=sys.stderr)
            continue
        rows = [p.model_dump(mode="json") for p in papers]
        with open(f"{out_dir}/raw_{name}.json", "w") as f:
            json.dump(rows, f, indent=2, default=str)
        all_papers.extend(rows)
        ok += 1
        print(f"gather: {name} -> {len(rows)} papers")

    if ok == 0:
        raise RuntimeError(f"topic '{topic.id}': all {len(active)} sources failed")

    deduped = dedupe_papers(all_papers)
    papers_path = f"{out_dir}/papers.json"
    with open(papers_path, "w") as f:
        json.dump(deduped, f, indent=2, default=str)
    print(f"gather: deduped {len(all_papers)} -> {len(deduped)}")

    candidates_path = f"{out_dir}/candidates.json"
    n = filter_run(
        papers_path, candidates_path, topics_path=topics_path, only_topic=topic.id
    )
    print(f"gather: {n} candidates for topic '{topic.id}' -> {candidates_path}")
    return n, ok


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Gather + filter candidates for one topic")
    ap.add_argument("--topic", required=True, help="topic id from config/topics.yml")
    ap.add_argument("--date", default=None, help="window end date YYYY-MM-DD (default: today)")
    ap.add_argument("--out", required=True, help="output dir (raw_*, papers, candidates)")
    ap.add_argument("--topics", default=None, help="path to topics.yml (default: repo config)")
    args = ap.parse_args(argv)

    cfg = load_topics(args.topics)
    topic = next((t for t in cfg.topics if t.id == args.topic), None)
    if topic is None:
        known = ", ".join(t.id for t in cfg.topics)
        print(f"unknown topic '{args.topic}'; known: {known}", file=sys.stderr)
        return 2

    day = args.date or date.today().isoformat()
    since, until = _window(day, cfg.lookback_hours)
    try:
        gather(topic, since, until, args.out, topics_path=args.topics)
    except RuntimeError as exc:
        print(f"gather failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
