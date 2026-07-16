"""Render carousel text cards from a validated post via headless Chromium.

The HTML is fully self-contained: the CSS is inlined into a <style> block and the
Inter fonts are embedded as base64 data URIs. This is required because Playwright's
set_content() serves an about:blank page with no base URL, so relative asset links
(stylesheet, @font-face url()) would never load.
"""
from __future__ import annotations

import base64
import functools
import io
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from PIL import Image
from playwright.sync_api import sync_playwright

from scripts.lib.config import BrandConfig
from scripts.lib.imageutil import assert_dimensions
from scripts.lib.sourceline import card_footer_line
from templates.motifs import motif_data_uri

_TEMPLATE_DIR = Path(__file__).parent
_FONTS_DIR = _TEMPLATE_DIR / "fonts"


@functools.lru_cache(maxsize=1)
def _inlined_css() -> str:
    """Load carousel.css and inline the two Inter fonts as base64 data URIs."""
    css = (_TEMPLATE_DIR / "carousel.css").read_text()
    for placeholder, filename in (
        ("__INTER_REGULAR_B64__", "Inter-Regular.woff2"),
        ("__INTER_BOLD_B64__", "Inter-Bold.woff2"),
    ):
        b64 = base64.b64encode((_FONTS_DIR / filename).read_bytes()).decode("ascii")
        css = css.replace(placeholder, b64)
    return css


def _resolve_footer(card: dict, paper: dict | None) -> str:
    """Deterministic footer, computed from the paper (not the authored JSON).

    When `paper` is provided, the footer is fully controlled here so it never
    varies with what the language model wrote: the title/hero card gets no
    footer, and every other card shows 'Source · Month D, YYYY' from the paper.
    The paper first-page screenshot is inserted at bundle time and is not an
    authored card, so it is unaffected. When no paper is given (e.g. a bare unit
    test), fall back to the authored `footer` for backward compatibility.
    """
    if paper is None:
        return card.get("footer", "")
    if card["card_type"] == "title":
        return ""
    return card_footer_line(paper)


def _card_html(env: Environment, card: dict, brand: BrandConfig, *,
               motif_key: str | None = None, paper: dict | None = None) -> str:
    accent = brand.palette.card_type_colors.get(card["card_type"], brand.palette.accent)
    # Font sizes are brand-tunable via `type_scale` in config/brand.<acct>.yml.
    # Sizes below are calibrated for the 1080x1350 canvas per social-carousel
    # legibility guidance (comfortable body ~48-50px, 1.5 body line-height); the
    # densest 280-char body still clears the 1350px height with margin to spare.
    ts = brand.type_scale
    common = dict(
        css=_inlined_css(),
        account_name=brand.account_name,
        heading=card["heading"], body=card.get("body", ""),
        footer=_resolve_footer(card, paper),
        bg=brand.palette.background, text=brand.palette.text_primary,
        muted=brand.palette.text_muted, accent=accent,
        fs_heading=ts.get("heading_px", 64), fs_body=ts.get("body_px", 50),
        fs_label=ts.get("label_px", 30), fs_footer=ts.get("footer_px", 32),
        fs_title=ts.get("title_px", 84), fs_title_source=ts.get("title_source_px", 40),
    )
    if card["card_type"] == "title":
        # front card: title + source over the account's concept motif
        motif_uri = motif_data_uri(brand.resolve_motif(motif_key), brand.palette.accent)
        return env.get_template("title.html.j2").render(motif_uri=motif_uri, **common)
    return env.get_template("carousel.html.j2").render(**common)


def render_text_cards(
    post: dict, brand: BrandConfig, *, out_dir: Path | str, start_index: int = 1,
    motif_key: str | None = None, paper: dict | None = None,
) -> list[Path]:
    """Render cards with card_number >= start_index to JPEGs. Returns ordered paths.

    motif_key rotates the front-card backdrop when the brand lists several motifs
    (pass the run date so a given day is stable).

    paper (the selected_paper.json dict) drives the deterministic card footers:
    the title/hero card gets no footer and every other card shows
    'Source · Month D, YYYY'. When omitted, the authored `footer` is used as-is."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    # autoescape for text fields; the CSS is passed through |safe in the template.
    env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)), autoescape=True)
    cards = [c for c in post["carousel_cards"] if c["card_number"] >= start_index]
    scale = brand.render_scale
    paths: list[Path] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        page = browser.new_page(
            viewport={"width": brand.canvas_width, "height": brand.canvas_height},
            device_scale_factor=scale,
        )
        for card in cards:
            html = _card_html(env, card, brand, motif_key=motif_key, paper=paper)
            page.set_content(html, wait_until="load")
            page.evaluate("document.fonts.ready")  # ensure embedded font is applied
            png = page.screenshot()
            img = Image.open(io.BytesIO(png)).convert("RGB")
            assert_dimensions(img, brand.canvas_width * scale, brand.canvas_height * scale)
            out = out_dir / f"card_{card['card_number']:02d}.jpg"
            img.save(out, "JPEG", quality=brand.jpeg_quality)
            paths.append(out)
        browser.close()
    return paths
