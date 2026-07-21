#!/usr/bin/env python3
"""Render a 3x3 mosaic of an account's recent front cards, cropped the way the
Instagram profile grid crops them, so the operator can judge GRID cohesion (not
just individual cards) before publishing.

The grid is what a visitor judges in the follow-decision moment, and it shows a
center crop of each 4:5 card — so this previews the actual cropped thumbnails
side by side. PIL-only, no new deps.

    research-grid-preview --account cs --out outputs/2026-07-24/cs/grid_preview.jpg
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image


def center_crop(img: Image.Image, *, ratio: float) -> Image.Image:
    """Center-crop img to width/height == ratio (e.g. 1.0 square, 0.8 = 4:5)."""
    w, h = img.size
    target_h = int(round(w / ratio))
    if target_h <= h:
        top = (h - target_h) // 2
        return img.crop((0, top, w, top + target_h))
    target_w = int(round(h * ratio))
    left = (w - target_w) // 2
    return img.crop((left, 0, left + target_w, h))


def build_mosaic(imgs: list[Image.Image], *, cols: int = 3, cell: int = 360,
                 gap: int = 8, ratio: float = 0.8, bg=(10, 10, 12)) -> Image.Image:
    """Tile imgs into a grid: each cropped to `ratio`, resized to `cell` wide."""
    cell_h = int(round(cell / ratio))
    rows = max(1, (len(imgs) + cols - 1) // cols)
    W = cols * cell + (cols + 1) * gap
    H = rows * cell_h + (rows + 1) * gap
    mosaic = Image.new("RGB", (W, H), bg)
    for i, img in enumerate(imgs):
        r, c = divmod(i, cols)
        cropped = center_crop(img.convert("RGB"), ratio=ratio).resize(
            (cell, cell_h), Image.LANCZOS)
        x = gap + c * (cell + gap)
        y = gap + r * (cell_h + gap)
        mosaic.paste(cropped, (x, y))
    return mosaic


def find_front_cards(outputs_root: str, *, account: str, limit: int = 9) -> list[Path]:
    """The most recent `limit` front cards (card_01.jpg) for an account, newest first.

    Sorts by date dir desc, then post dir, mirroring how the grid shows newest-first.
    Prefers the delivered bundle card (postN/card_01.jpg); falls back to assets."""
    root = Path(outputs_root)
    if not root.is_dir():
        return []
    cards: list[Path] = []
    for date_dir in sorted((p for p in root.iterdir() if p.is_dir()), reverse=True):
        acct = date_dir / account
        if not acct.is_dir():
            continue
        for post_dir in sorted(acct.glob("post*")) + sorted(acct.glob("roundup")):
            card = post_dir / "card_01.jpg"
            if not card.exists():
                card = post_dir / "assets" / "card_01.jpg"
            if card.exists():
                cards.append(card)
                if len(cards) >= limit:
                    return cards
    return cards


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Render a 3x3 grid preview of recent front cards")
    ap.add_argument("--account", required=True, help="account id, e.g. cs or bio")
    ap.add_argument("--out", required=True, help="output JPEG path")
    ap.add_argument("--outputs-root", default="outputs")
    ap.add_argument("--limit", type=int, default=9)
    ap.add_argument("--ratio", type=float, default=0.8,
                    help="grid cell aspect (w/h); 1.0=square, 0.8=4:5 (IG's tall grid)")
    args = ap.parse_args(argv)

    cards = find_front_cards(args.outputs_root, account=args.account, limit=args.limit)
    if not cards:
        print(f"no front cards found for account {args.account!r}", file=sys.stderr)
        return 1
    mosaic = build_mosaic([Image.open(c) for c in cards], ratio=args.ratio)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    mosaic.save(out, "JPEG", quality=90)
    print(f"grid preview ({len(cards)} cards) -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
