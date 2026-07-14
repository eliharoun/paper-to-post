"""Generate and composite the AI hero image for the carousel front card.

Two responsibilities, kept separate so the compositor is testable without network:
  - generate_image(): the single Gemini image-model call (added in a later task).
  - composite_front_card(): PIL "hybrid" front card — full-bleed hero, fixed
    bottom gradient scrim, bottom-anchored eyebrow + headline.

The compositor reads colours/geometry from the same BrandConfig the HTML content
cards use, and the same Inter typeface (as TTF, since PIL cannot read .woff2), so
the front card stays visually consistent with the rest of the carousel.
"""
from __future__ import annotations

import base64
import os
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from scripts.lib import paths
from scripts.lib.config import BrandConfig
from scripts.lib.imageutil import assert_dimensions

_FONTS_DIR = paths.templates_dir() / "fonts"


class HeroImageError(RuntimeError):
    """Raised when hero image generation fails (no key, API error, no image bytes)."""


def build_client():
    """Build a google-genai client from GOOGLE_API_KEY. Raises HeroImageError if unset."""
    api_key = os.environ.get("GOOGLE_API_KEY", "").strip()
    if not api_key:
        raise HeroImageError(
            "GOOGLE_API_KEY is not set. Add it to .env to enable hero image generation."
        )
    from google import genai
    return genai.Client(api_key=api_key)


def generate_image(concept: str, *, model: str, client, aspect_ratio: str = "4:5",
                   max_attempts: int = 3, retry_delay: int = 5) -> bytes:
    """Call the Gemini image model and return PNG bytes. Raises HeroImageError on failure."""
    from google.genai import types

    config = types.GenerateContentConfig(
        response_modalities=["IMAGE"],
        image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
    )
    last_err: Exception | None = None
    for attempt in range(max_attempts):
        try:
            resp = client.models.generate_content(model=model, contents=concept, config=config)
            for cand in resp.candidates or []:
                for part in getattr(cand.content, "parts", []) or []:
                    inline = getattr(part, "inline_data", None)
                    if inline and getattr(inline, "data", None):
                        data = inline.data
                        if isinstance(data, bytes):
                            return data
                        return base64.b64decode(data)
            last_err = HeroImageError("response contained no image data")
        except Exception as exc:  # noqa: BLE001 — retry any transient API error
            last_err = exc
        if attempt < max_attempts - 1:
            time.sleep(min(retry_delay * (2 ** attempt), 30))
    raise HeroImageError(f"image generation failed after {max_attempts} attempts: {last_err}")


def _hex(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(_FONTS_DIR / name), size)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont,
          max_w: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _fit_cover(img: Image.Image, tw: int, th: int) -> Image.Image:
    """Resize + center-crop so img exactly covers tw x th (no letterboxing)."""
    img = img.convert("RGB")
    scale = max(tw / img.width, th / img.height)
    img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))),
                     Image.LANCZOS)
    left, top = (img.width - tw) // 2, 0  # anchor to top so the subject (upper 2/3) stays
    return img.crop((left, top, left + tw, top + th))


def composite_front_card(*, hero_png_path: Path, headline: str, brand: BrandConfig,
                         out_path: Path) -> Path:
    """Composite the hybrid front card from a hero PNG. Returns out_path.

    Layout (bottom-anchored, image-independent legibility):
      full-bleed hero -> fixed bottom gradient scrim -> accent bar + account
      label -> wrapped headline.
    """
    scale = brand.render_scale
    W, H = brand.canvas_width * scale, brand.canvas_height * scale
    margin = brand.margin * scale
    accent = _hex(brand.palette.accent)
    bg = _hex(brand.palette.background)

    card = _fit_cover(Image.open(hero_png_path), W, H)
    draw = ImageDraw.Draw(card)

    # Type sizes scale with the canvas (calibrated against the 2160x2700 mockups).
    head_px = int(96 * scale / 2)
    line_h = int(head_px * 1.16)
    eyebrow_px = int(34 * scale / 2)
    eyebrow_gap = int(40 * scale / 2)
    f_head = _font("Inter-Bold.ttf", head_px)
    f_eye = _font("Inter-SemiBold.ttf", eyebrow_px)
    lines = _wrap(draw, headline, f_head, W - 2 * margin)

    # Bottom-up layout math (no footer).
    head_bottom = H - margin
    head_top = head_bottom - line_h * len(lines)
    eyebrow_y = head_top - eyebrow_gap - eyebrow_px
    bar_h = int(8 * scale / 2)
    bar_y = eyebrow_y - int(34 * scale / 2)
    band_top = bar_y - int(90 * scale / 2)

    # Fixed bottom gradient scrim: transparent above band_top, ramping to opaque.
    grad = Image.new("L", (1, H), 0)
    for y in range(H):
        if y < band_top:
            v = 0
        else:
            frac = (y - band_top) / (H - band_top)
            v = int(255 * min(1.0, frac * 1.9))
        grad.putpixel((0, y), v)
    grad = grad.resize((W, H))
    card = Image.composite(Image.new("RGB", (W, H), bg), card, grad)
    draw = ImageDraw.Draw(card)

    # Accent bar + eyebrow label + headline. The bottom gradient scrim already
    # keeps the eyebrow legible, so it sits directly on the image (no pill).
    label = brand.account_name.upper()
    draw.rectangle([margin, bar_y, margin + int(90 * scale / 2), bar_y + bar_h], fill=accent)
    draw.text((margin, eyebrow_y), label, font=f_eye, fill=accent)
    y = head_top
    for ln in lines:
        draw.text((margin, y), ln, font=f_head, fill=(255, 255, 255))
        y += line_h

    assert_dimensions(card, W, H)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    card.save(out_path, "JPEG", quality=brand.jpeg_quality)
    return out_path
