#!/usr/bin/env python3
"""Hard gate: validate a generated post. Exit 0 if it passes, 1 if it fails."""
from __future__ import annotations

import argparse
import json

from scripts.lib.config import load_topics, resolve_brand
from scripts.lib.validation import validate_post


def _requires_guardrails(paper: dict, topics_path: str | None) -> bool:
    topic_id = paper.get("topic_id")
    if not topic_id:
        return False
    topics = load_topics(topics_path)
    topic = next((t for t in topics.topics if t.id == topic_id), None)
    return bool(topic and topic.requires_health_guardrails)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Validate a generated post (hard gate)")
    ap.add_argument("--post", required=True)
    ap.add_argument("--paper", default=None,
                    help="selected paper JSON; omit for a paperless post (e.g. roundup) "
                         "to skip grounding/caption-link/health checks")
    ap.add_argument("--account", default=None, help="account id, e.g. cs or bio")
    ap.add_argument("--brand", default=None, help="explicit brand file (overrides --account)")
    ap.add_argument("--topics", default=None)
    args = ap.parse_args(argv)

    with open(args.post) as f:
        post = json.load(f)
    paper = None
    if args.paper:
        with open(args.paper) as f:
            paper = json.load(f)

    brand = resolve_brand(account=args.account, brand_path=args.brand)
    guarded = _requires_guardrails(paper, args.topics) if paper else False
    result = validate_post(post, paper, brand, requires_guardrails=guarded)

    print(json.dumps(result.model_dump(), indent=2))
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
