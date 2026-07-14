#!/usr/bin/env python3
"""CLI: generate the AI hero image and composite the carousel front card.

Reads `hero_image_prompt` from the post JSON (authored during the Write step),
calls the Gemini image model, and writes `<assets_dir>/card_01.jpg`. On ANY
failure it writes nothing and exits non-zero, so the caller falls back to the
existing motif title card. Never blocks a post.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scripts.lib import hero
from scripts.lib.config import load_env, resolve_brand


def _title_heading(post: dict) -> str:
    """The front-card headline = the title card's heading (card_number 1 / type
    'title'). Falls back to plain_english_headline only if no title card is found."""
    for card in post.get("carousel_cards", []):
        if card.get("card_type") == "title":
            return card.get("heading", "")
    return post.get("plain_english_headline", "")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Generate hero image + composite front card")
    ap.add_argument("--post", required=True)
    ap.add_argument("--out", required=True, help="assets output directory")
    ap.add_argument("--account", default=None, help="account id, e.g. cs or bio")
    ap.add_argument("--brand", default=None, help="explicit brand file (overrides --account)")
    ap.add_argument("--concept", default=None,
                    help="override the hero prompt (else read hero_image_prompt from post)")
    ap.add_argument("--hero-out", default=None,
                    help="path to save the raw hero PNG (default: <out>/../run/hero.png)")
    args = ap.parse_args(argv)

    load_env()
    brand = resolve_brand(account=args.account, brand_path=args.brand)

    if brand.hero_style is None or not brand.hero_style.enabled:
        print("hero disabled for this brand; falling back to motif", file=sys.stderr)
        return 2

    with open(args.post) as f:
        post = json.load(f)

    concept = args.concept or post.get("hero_image_prompt")
    if not concept or not concept.strip():
        print("no hero_image_prompt in post; falling back to motif", file=sys.stderr)
        return 3

    # Render the title card's heading — the same string the motif front card shows
    # and the one the writer crafts per references/headline-style-guide.md (<=70
    # chars, honesty firewall). This keeps the hero and motif front cards identical
    # in wording and avoids any drift with plain_english_headline.
    headline = _title_heading(post)
    assets = Path(args.out)
    hero_out = Path(args.hero_out) if args.hero_out else assets.parent / "run" / "hero.png"

    try:
        client = hero.build_client()
        png_bytes = hero.generate_image(
            concept, model=brand.hero_style.image_model, client=client,
            aspect_ratio=brand.hero_style.aspect_ratio,
        )
        hero_out.parent.mkdir(parents=True, exist_ok=True)
        hero_out.write_bytes(png_bytes)
        card = hero.composite_front_card(
            hero_png_path=hero_out, headline=headline, brand=brand,
            out_path=assets / "card_01.jpg",
        )
    except hero.HeroImageError as exc:
        print(f"hero generation failed: {exc}; falling back to motif", file=sys.stderr)
        return 4
    except Exception as exc:  # noqa: BLE001 — any failure must fall back, never crash the run
        print(f"hero step error: {exc}; falling back to motif", file=sys.stderr)
        return 5

    print(json.dumps({"hero": str(hero_out), "card": str(card)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
