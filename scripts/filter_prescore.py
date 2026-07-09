#!/usr/bin/env python3
"""Filter deduped papers, assign topics, exclude delivered, rule-score, and rank."""
from __future__ import annotations

import argparse
import json
from datetime import date

from scripts.lib import paths
from scripts.lib.config import load_topics
from scripts.lib.filtering import assign_topic, hard_filter_reasons, rule_score
from scripts.lib.paperkey import paper_key_from_dict
from scripts.lib.store import Ledger


def run(
    papers_path: str,
    out_path: str,
    *,
    topics_path: str | None = None,
    ledger: Ledger | None = None,
    today: date | None = None,
    only_topic: str | None = None,
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
    args = ap.parse_args(argv)

    ledger = Ledger(args.ledger) if args.ledger else Ledger(paths.ledger_path())
    n = run(args.papers, args.out, topics_path=args.topics, ledger=ledger,
            only_topic=args.only_topic)
    print(f"wrote {n} candidates to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
