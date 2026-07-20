#!/usr/bin/env python3
"""Assemble the final post-ready bundle and record the paper in the ledger."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from scripts.lib import paths
from scripts.lib.bundle import compose_caption, final_image_order, ordered_card_paths
from scripts.lib.paperkey import paper_key_from_dict
from scripts.lib.store import Ledger


def run(
    *,
    post_path: str,
    paper_path: str,
    assets_dir: str,
    out_dir: str,
    ledger: Ledger,
    delivered_date: str,
    screenshot_path: str | None = None,
) -> dict:
    """Write the bundle to out_dir and mark the paper delivered. Returns a manifest.

    If screenshot_path is given and exists, the paper first-page image is placed
    second-to-last (just before the source card). Final images are renumbered
    card_01..card_0N in posting order.
    """
    with open(post_path) as f:
        post = json.load(f)
    with open(paper_path) as f:
        paper = json.load(f)

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    # 1. copy images in final posting order (screenshot inserted before source),
    #    renumbered sequentially so Instagram shows them in order.
    cards = ordered_card_paths(assets_dir)
    if not cards:
        # Render produced nothing (empty/missing assets). Abort BEFORE writing any
        # artifacts or touching the ledger, so the paper stays re-postable instead
        # of being burned with a broken 0-card bundle.
        raise ValueError(f"no cards found in assets dir {assets_dir!r}; nothing to bundle")
    shot = Path(screenshot_path) if screenshot_path else None
    ordered = final_image_order(cards, shot)
    copied: list[str] = []
    for i, src in enumerate(ordered, start=1):
        dest = out / f"card_{i:02d}.jpg"
        shutil.copyfile(src, dest)
        copied.append(dest.name)

    # 2. caption.txt (guaranteed to contain the article link). The paper link field
    #    is `url` on candidates but the post JSON / schema uses `source_url`; accept
    #    either so the link-guarantee never silently breaks on a field-name drift.
    paper_url = paper.get("url") or paper.get("source_url") or post.get("source_url", "")
    caption = compose_caption(post.get("caption", ""), paper_url)
    (out / "caption.txt").write_text(caption)

    # 3. alt_text.txt
    (out / "alt_text.txt").write_text(post.get("alt_text", ""))

    # 4. audit copies
    (out / "post.json").write_text(json.dumps(post, indent=2))
    (out / "selected_paper.json").write_text(json.dumps(paper, indent=2))

    key = paper_key_from_dict(paper)
    manifest = {
        "out_dir": str(out),
        "cards": copied,
        "card_count": len(copied),
        "paper_key": key,
        "caption_chars": len(caption),
    }
    (out / "bundle_manifest.json").write_text(json.dumps(manifest, indent=2))

    # 5. record delivered LAST — only after the full bundle (incl. manifest) is on
    #    disk. If a crash happens earlier, the paper stays re-postable rather than
    #    being burned from the pool with no usable output.
    ledger.mark_delivered(key, delivered_date, post_id=post.get("paper_id", key))
    return manifest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Assemble the final post-ready bundle")
    ap.add_argument("--post", required=True)
    ap.add_argument("--paper", required=True)
    ap.add_argument("--assets-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--ledger", default=None)
    ap.add_argument("--screenshot", default=None,
                    help="paper first-page image to place second-to-last (before source)")
    ap.add_argument("--date", required=True, help="delivered date YYYY-MM-DD")
    args = ap.parse_args(argv)

    ledger = Ledger(args.ledger) if args.ledger else Ledger(paths.ledger_path())
    manifest = run(
        post_path=args.post, paper_path=args.paper, assets_dir=args.assets_dir,
        out_dir=args.out, ledger=ledger, delivered_date=args.date,
        screenshot_path=args.screenshot,
    )
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
