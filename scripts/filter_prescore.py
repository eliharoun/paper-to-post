#!/usr/bin/env python3
"""Filter deduped papers, assign topics, exclude delivered, rule-score, and rank."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from scripts.lib import paths
from scripts.lib.config import load_topics
from scripts.lib.filtering import assign_topic, hard_filter_reasons, rule_score
from scripts.lib.paperkey import paper_key_from_dict
from scripts.lib.store import Ledger
from scripts.lib.trends import TrendScorer, _paper_id
from scripts.lib.trends.base import RunContext


def run(
    papers_path: str,
    out_path: str,
    *,
    topics_path: str | None = None,
    ledger: Ledger | None = None,
    today: date | None = None,
    only_topic: str | None = None,
    data_dir: str | None = None,
) -> int:
    """Produce ranked candidates.json. Returns the number of passing candidates.

    only_topic: if set, keep only candidates assigned to that topic id
    (used to limit a run to one account's subject area).
    """
    topics = load_topics(topics_path)
    today = today or date.today()
    ledger = ledger if ledger is not None else Ledger(paths.ledger_path())
    delivered = ledger.seen_keys()

    with open(papers_path) as f:
        papers = json.load(f)

    candidates: list[dict] = []
    for paper in papers:
        # assign topic first (hard filter depends on it)
        paper["topic_id"] = assign_topic(paper, topics)

        if only_topic and paper["topic_id"] != only_topic:
            continue

        # skip already-delivered papers
        if paper_key_from_dict(paper) in delivered:
            continue

        reasons = hard_filter_reasons(paper, topics)
        if reasons:
            continue  # rejected papers are not emitted as candidates

        score = rule_score(paper, topics, today=today)
        candidates.append(
            {
                "paper": paper,
                "topic_id": paper["topic_id"],
                "filter_status": "passed",
                "filter_reasons": [],
                "rule_score": score,
                "llm_score": None,
                "final_score": None,
                "score_breakdown": {},
            }
        )

    # --- trendiness (advisory: surfaced in score_breakdown + a sort-only nudge) ---
    # Trends assume a single-topic corpus (term history and GDELT keywords are
    # per-topic). Production always passes only_topic (gather runs one topic at a
    # time); a manual multi-topic run without only_topic falls back to the first
    # candidate's topic config for the whole corpus, which is why gather scopes it.
    topic_cfg = None
    if only_topic:
        topic_cfg = next((t for t in topics.topics if t.id == only_topic), None)
    elif candidates:
        tid = candidates[0]["topic_id"]
        topic_cfg = next((t for t in topics.topics if t.id == tid), None)

    sorted_by_trend = False
    if topic_cfg is not None and topic_cfg.trends.enabled and candidates:
        try:
            ddir = Path(data_dir) if data_dir else paths.data_dir()
            ctx = RunContext(topic_id=topic_cfg.id, today=today, data_dir=ddir)
            scorer = TrendScorer.from_config(topic_cfg.trends)
            papers_only = [c["paper"] for c in candidates]
            breakdowns = scorer.score_corpus(papers_only, topic=topic_cfg, ctx=ctx)
            for c in candidates:
                bd = breakdowns.get(_paper_id(c["paper"]))
                if bd:
                    c["score_breakdown"].update(bd)
            # per-paper engagement refinement on the top slice only
            top = sorted(candidates, key=lambda c: c["rule_score"], reverse=True)
            top_papers = [c["paper"] for c in top[: topic_cfg.trends.top_slice]]
            scorer.refine_top_slice(top_papers, breakdowns)
            for c in candidates:                 # re-merge refined trendiness
                bd = breakdowns.get(_paper_id(c["paper"]))
                if bd:
                    c["score_breakdown"]["trendiness"] = bd["trendiness"]
            scorer.persist(ctx)
            bump = topic_cfg.trends.sort_bump
            candidates.sort(
                key=lambda c: c["rule_score"]
                + bump * c["score_breakdown"].get("trendiness", 0.0),
                reverse=True,
            )
            sorted_by_trend = True
        except Exception as exc:  # noqa: BLE001 — trendiness is advisory, never fatal
            print(f"trends: scoring failed, falling back to rule_score "
                  f"({exc}) (skipping)", file=sys.stderr)

    if not sorted_by_trend:
        candidates.sort(key=lambda c: c["rule_score"], reverse=True)

    with open(out_path, "w") as f:
        json.dump(candidates, f, indent=2, default=str)
    return len(candidates)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Filter + rule-score deduped papers -> candidates.json"
    )
    ap.add_argument("papers", help="path to deduped papers.json")
    ap.add_argument("--topics", default=None)
    ap.add_argument("--ledger", default=None)
    ap.add_argument("--only-topic", default=None,
                    help="keep only candidates in this topic id (limits to one account)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--date", default=None,
                    help="score recency against this date YYYY-MM-DD "
                         "(default: today). Set it for reproducible ranking.")
    ap.add_argument("--data-dir", default=None,
                    help="override data dir for trend history/cache (default: repo data/)")
    args = ap.parse_args(argv)

    today = date.fromisoformat(args.date) if args.date else None
    ledger = Ledger(args.ledger) if args.ledger else Ledger(paths.ledger_path())
    n = run(args.papers, args.out, topics_path=args.topics, ledger=ledger,
            only_topic=args.only_topic, today=today, data_dir=args.data_dir)
    print(f"wrote {n} candidates to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
