#!/usr/bin/env python3
"""Card 1 = paper first-page screenshot, gated to arXiv/OA. Never raises to caller."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import fitz  # pymupdf

from scripts.lib.config import resolve_brand
from scripts.lib.imageutil import assert_dimensions, fit_onto_canvas
from scripts.lib.pdf import fetch_pdf, pdf_url_for

# Licenses that forbid reproducing the page. Unknown + OA-source(arXiv) is allowed;
# unknown + non-OA is not. Everything OA/CC is treated as displayable whole-page context.
_BLOCKING_LICENSES = ("all rights reserved", "copyright", "proprietary")


def card1_is_eligible(paper: dict) -> bool:
    """True iff we may screenshot the paper's first page (PRD §22.5)."""
    lic = (paper.get("license") or "").lower().strip()
    if any(b in lic for b in _BLOCKING_LICENSES):
        return False
    is_arxiv = bool(paper.get("arxiv_id"))
    is_oa = paper.get("is_open_access") is True
    if not pdf_url_for(paper):
        return False
    # arXiv is always OK; otherwise require confirmed open access
    return is_arxiv or is_oa


def render_card1_from_pdf_bytes(
    pdf_bytes: bytes, out_path: Path | str, *, canvas_w: int, canvas_h: int,
    bg: str, scale: int
) -> bool:
    """Rasterize page 1 and fit it onto the brand canvas at `scale`x. Never raises."""
    from PIL import Image
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        if doc.page_count < 1:
            return False
        page = doc.load_page(0)
        pix = page.get_pixmap(matrix=fitz.Matrix(scale * 2, scale * 2))  # oversample then fit
        src = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        out = fit_onto_canvas(src, canvas_w=canvas_w * scale, canvas_h=canvas_h * scale, bg=bg)
        assert_dimensions(out, canvas_w * scale, canvas_h * scale)
        out.save(out_path, "JPEG", quality=92)
        return True
    except Exception:  # noqa: BLE001 — any failure => fall back to title card
        return False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Render card 1 as the paper's first page (gated)")
    ap.add_argument("--paper", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--account", default=None, help="account id, e.g. cs or bio")
    ap.add_argument("--brand", default=None, help="explicit brand file (overrides --account)")
    args = ap.parse_args(argv)

    with open(args.paper) as f:
        paper = json.load(f)
    brand = resolve_brand(account=args.account, brand_path=args.brand)

    if os.environ.get("ENABLE_PAPER_SCREENSHOT", "true").lower() == "false":
        print(json.dumps({"ok": False, "reason": "disabled"}))
        return 0

    # If not already eligible but the paper has a DOI, try to find a legal
    # open-access PDF (Unpaywall) so paywalled-page papers with a free copy
    # can still get a screenshot. Never touches paywalled PDFs.
    if not card1_is_eligible(paper) and paper.get("doi") and not paper.get("pdf_url"):
        from scripts.lib.oa import contact_email, resolve_oa_pdf
        is_oa, oa_url = resolve_oa_pdf(paper["doi"], contact_email())
        if is_oa:
            paper["is_open_access"] = True
            if oa_url:
                paper["pdf_url"] = oa_url

    if not card1_is_eligible(paper):
        print(json.dumps({"ok": False, "reason": "not_eligible"}))
        return 0

    url = pdf_url_for(paper)
    max_bytes = int(os.environ.get("PDF_MAX_BYTES", 52_428_800))
    timeout = int(os.environ.get("PDF_FETCH_TIMEOUT_SECONDS", 30))
    pdf_bytes = fetch_pdf(url, max_bytes=max_bytes, timeout=timeout)
    if pdf_bytes is None:
        print(json.dumps({"ok": False, "reason": "fetch_failed", "url": url}))
        return 0

    ok = render_card1_from_pdf_bytes(
        pdf_bytes, args.out, canvas_w=brand.canvas_width, canvas_h=brand.canvas_height,
        bg=brand.palette.background, scale=brand.render_scale,
    )
    print(json.dumps({"ok": ok, "reason": "rendered" if ok else "render_failed",
                      "url": url if ok else None}))
    return 0  # always 0: fallback is the caller's job (the skill)


if __name__ == "__main__":
    raise SystemExit(main())
