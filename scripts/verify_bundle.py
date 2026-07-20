#!/usr/bin/env python3
"""Verify a finished post bundle has all required artifacts (delivery gate).

The per-post pipeline is run by (often dispatched) agents, and an agent can die
silently after being told it "completed" without having produced anything. The
validation gate (`research-validate`) only proves a *post.json* is sound; it says
nothing about whether the render/bundle steps actually ran. This script closes
that seam: it asserts the on-disk bundle is real and complete before publishing.

It is deliberately cheap and dependency-light (existence + count + link checks,
no network, no image decode) so it can run once per postN right before delivery.
Exit 0 = safe to publish; exit 1 = something is missing, do not publish.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.lib.bundle import ordered_card_paths
from scripts.lib.config import resolve_brand


def verify(bundle_dir: str | Path, *, account: str | None = None,
           brand_path: str | None = None) -> dict:
    """Return {ok, errors, dir, card_count} for a delivered bundle dir.

    Checks (all must hold for ok=True):
      - the bundle dir exists,
      - bundle_manifest.json exists (written last by research-bundle, so its
        absence means production never finished),
      - post.json and selected_paper.json audit copies exist,
      - caption.txt exists, is non-empty, and contains the paper link,
      - card_01.jpg..card_0N.jpg exist, are contiguous from 1, and match the
        manifest's card_count,
      - the card count is within the account's brand min/max (when resolvable).
    """
    out = Path(bundle_dir)
    errors: list[str] = []

    if not out.is_dir():
        return {"ok": False, "errors": [f"bundle dir missing: {out}"],
                "dir": str(out), "card_count": 0}

    # bundle_manifest.json is written last by assemble_bundle -> its presence is
    # the "production actually completed" anchor.
    manifest_path = out / "bundle_manifest.json"
    manifest: dict = {}
    if not manifest_path.exists():
        errors.append("bundle_manifest.json missing (research-bundle never completed)")
    else:
        try:
            manifest = json.loads(manifest_path.read_text())
        except (OSError, json.JSONDecodeError) as e:
            errors.append(f"bundle_manifest.json unreadable: {e}")

    for required in ("post.json", "selected_paper.json"):
        if not (out / required).exists():
            errors.append(f"{required} missing")

    # caption must exist, be non-empty, and carry the article link.
    caption_path = out / "caption.txt"
    if not caption_path.exists():
        errors.append("caption.txt missing")
    else:
        caption = caption_path.read_text().strip()
        if not caption:
            errors.append("caption.txt is empty")
        else:
            paper_url = ""
            paper_file = out / "selected_paper.json"
            if paper_file.exists():
                try:
                    paper = json.loads(paper_file.read_text())
                    paper_url = paper.get("url") or paper.get("source_url") or ""
                except (OSError, json.JSONDecodeError):
                    pass
            if paper_url and paper_url not in caption:
                errors.append("caption.txt does not contain the paper link")

    # card_01..card_0N present and contiguous from 1.
    cards = ordered_card_paths(out)
    card_count = len(cards)
    if card_count == 0:
        errors.append("no card_NN.jpg images in bundle")
    else:
        indices = sorted(int(p.name[len("card_"):-len(".jpg")]) for p in cards)
        expected = list(range(1, card_count + 1))
        if indices != expected:
            errors.append(f"card numbering not contiguous from 1: found {indices}")
        if manifest and manifest.get("card_count") not in (None, card_count):
            errors.append(
                f"card_count mismatch: manifest={manifest.get('card_count')} on-disk={card_count}"
            )
        # card count within brand bounds (best-effort; skipped if brand unresolvable).
        # The delivered bundle may carry one extra card beyond the authored range:
        # research-bundle inserts the paper first-page screenshot before the source
        # card, so the valid final range is [min_cards, max_cards + 1].
        try:
            brand = resolve_brand(account=account, brand_path=brand_path)
        except Exception:
            brand = None
        if brand is not None and not (brand.min_cards <= card_count <= brand.max_cards + 1):
            errors.append(
                f"card_count {card_count} outside delivered bounds "
                f"[{brand.min_cards}, {brand.max_cards + 1}] "
                f"(authored {brand.min_cards}-{brand.max_cards} + optional screenshot)"
            )

    return {"ok": not errors, "errors": errors, "dir": str(out), "card_count": card_count}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Verify a finished post bundle (delivery gate)")
    ap.add_argument("--dir", required=True, help="bundle dir, e.g. outputs/DATE/ACC/post1")
    ap.add_argument("--account", default=None, help="account id (cs/bio); card-bounds check")
    ap.add_argument("--brand", default=None, help="explicit brand file (overrides --account)")
    args = ap.parse_args(argv)

    result = verify(args.dir, account=args.account, brand_path=args.brand)
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
