#!/usr/bin/env python3
"""CLI: render carousel text cards from a validated post JSON."""
from __future__ import annotations

import argparse
import json
import sys

from scripts.lib.config import resolve_brand
from templates.render import render_text_cards


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Render carousel text cards")
    ap.add_argument("--post", required=True)
    ap.add_argument("--paper", default=None,
                    help="selected_paper.json; drives deterministic card footers "
                         "(source + full publication date). Omit to keep authored footers.")
    ap.add_argument("--out", required=True, help="assets output directory")
    ap.add_argument("--account", default=None, help="account id, e.g. cs or bio")
    ap.add_argument("--brand", default=None, help="explicit brand file (overrides --account)")
    ap.add_argument("--start-index", type=int, default=1,
                    help="skip cards below this number (use 2 if card 1 is a screenshot)")
    ap.add_argument("--motif-key", default=None,
                    help="rotation key for the front-card backdrop, e.g. the run date")
    args = ap.parse_args(argv)

    with open(args.post) as f:
        post = json.load(f)
    paper = None
    if args.paper:
        with open(args.paper) as f:
            paper = json.load(f)
    brand = resolve_brand(account=args.account, brand_path=args.brand)
    try:
        paths = render_text_cards(post, brand, out_dir=args.out,
                                  start_index=args.start_index, motif_key=args.motif_key,
                                  paper=paper)
    except Exception as exc:  # noqa: BLE001 — overflow/render errors are recoverable upstream
        print(f"render failed: {exc}", file=sys.stderr)
        return 3
    print(json.dumps({"rendered": [str(p) for p in paths]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
