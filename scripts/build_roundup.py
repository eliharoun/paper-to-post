#!/usr/bin/env python3
"""Assemble a weekly "papers you missed" roundup carousel from the week's posts.

A roundup is a normal carousel (title + one card per paper + a source/outro card),
so it reuses the existing render -> bundle -> publish path unchanged. It is NOT
about a single paper, so it skips the paper-grounding validator; the format-agnostic
safety checks (lengths, hype, AI-tell punctuation) still apply and the schema still
holds. Source is the week's produced `post.json` files (not the ledger, which only
stores keys), so this runs gather-free.

    research-roundup --account cs --out outputs/2026-07-24/cs/roundup \
        --dates 2026-07-20,2026-07-21,2026-07-22,2026-07-23,2026-07-24 \
        --title "5 CS papers you missed this week"
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scripts.lib.config import resolve_brand


def _title_heading(post: dict) -> str:
    for card in post.get("carousel_cards", []):
        if card.get("card_type") == "title":
            return card.get("heading", "")
    return post.get("plain_english_headline", "")


def collect_week_entries(outputs_root: str, *, account: str, dates: list[str]) -> list[dict]:
    """Scan outputs/<date>/<account>/post*/post.json across `dates` and return
    roundup entries {headline, takeaway, source_url} in date order."""
    entries: list[dict] = []
    root = Path(outputs_root)
    for d in dates:
        acct_dir = root / d / account
        if not acct_dir.is_dir():
            continue
        for post_dir in sorted(acct_dir.glob("post*")):
            pj = post_dir / "post.json"
            if not pj.exists():
                continue
            post = json.loads(pj.read_text())
            entries.append({
                "headline": _title_heading(post),
                "takeaway": (post.get("takeaway")
                             or post.get("one_sentence_summary") or "").strip(),
                "source_url": post.get("source_url", ""),
            })
    return entries


def build_roundup_post(
    entries: list[dict], *, title: str, account: str, max_entries: int | None = None,
) -> dict:
    """Build a roundup carousel post dict (GeneratedPost-shaped) from entries.

    Card layout: title -> one `finding` card per paper (ranked #1..#N) -> a `source`
    outro card. Card count is bounded by the brand's min/max_cards."""
    brand = resolve_brand(account=account)
    # Leave room for the title + source cards within max_cards.
    room = brand.max_cards - 2
    cap = min(room, max_entries) if max_entries else room
    picked = entries[:cap]

    cards: list[dict] = [{
        "card_number": 1, "card_type": "title", "heading": title, "body": "", "footer": "",
    }]
    for i, e in enumerate(picked, start=1):
        # Heading = rank + the paper's headline; body = its one-line takeaway.
        heading = f"#{i}: {e['headline']}"[:70]
        cards.append({
            "card_number": i + 1, "card_type": "finding",
            "heading": heading, "body": e.get("takeaway", "")[:280], "footer": "",
        })
    cards.append({
        "card_number": len(picked) + 2, "card_type": "source",
        "heading": "The week in research", "body": "Links to every paper in the caption.",
        "footer": "",
    })

    # Caption: hook + a numbered list of headlines + all links + a save CTA.
    lines = [title, ""]
    for i, e in enumerate(picked, start=1):
        lines.append(f"{i}. {e['headline']}")
    lines.append("")
    lines += [f"📄 {e['source_url']}" for e in picked if e.get("source_url")]
    lines += ["", "Save this to catch up on the week. Which one are you reading first?"]
    caption = "\n".join(lines)

    return {
        "paper_id": "roundup",
        "source_title": title,
        "source_url": picked[0]["source_url"] if picked else "",
        "is_preprint": False,
        "plain_english_headline": title,
        "one_sentence_summary": title,
        "why_it_matters": "A weekly digest of the most interesting papers.",
        "what_they_did": "", "what_they_found": "", "important_context": "",
        "limitations": ["A curated digest, not a single study."],
        "avoid_saying": [],
        "carousel_cards": cards,
        "caption": caption,
        "hashtags": [],
        "alt_text": f"Weekly research roundup: {title}",
        "confidence": "high",
        "hero_image_prompt": None,
        "takeaway": title,
        "share_cta": "Send this to a colleague who wants to stay current.",
        "debate_question": "Which paper are you reading first?",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Assemble a weekly roundup carousel post.json")
    ap.add_argument("--account", required=True, help="account id, e.g. cs or bio")
    ap.add_argument("--dates", required=True, help="comma-separated YYYY-MM-DD of the week")
    ap.add_argument("--title", required=True)
    ap.add_argument("--out", required=True, help="dir to write run/post.json into")
    ap.add_argument("--outputs-root", default="outputs")
    ap.add_argument("--max-entries", type=int, default=5)
    args = ap.parse_args(argv)

    dates = [d.strip() for d in args.dates.split(",") if d.strip()]
    entries = collect_week_entries(args.outputs_root, account=args.account, dates=dates)
    if not entries:
        print("no posts found for the given week/account; nothing to roll up", file=sys.stderr)
        return 1

    post = build_roundup_post(entries, title=args.title, account=args.account,
                              max_entries=args.max_entries)
    out = Path(args.out) / "run"
    out.mkdir(parents=True, exist_ok=True)
    (out / "post.json").write_text(json.dumps(post, indent=2))
    print(json.dumps({"entries": len(entries),
                      "cards": len(post["carousel_cards"]),
                      "out": str(out / "post.json")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
