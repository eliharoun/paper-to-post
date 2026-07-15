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


def _hard_break_wide_lines(draw: ImageDraw.ImageDraw, lines: list[str],
                           font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    """Character-level break for any line still wider than max_w.

    _wrap only breaks on spaces, so a single token longer than the text column
    (e.g. a very long compound word) stays on one over-wide line and would clip
    off the canvas edge. Split such lines mid-token so text always fits."""
    out: list[str] = []
    for ln in lines:
        if draw.textlength(ln, font=font) <= max_w:
            out.append(ln)
            continue
        cur = ""
        for ch in ln:
            if cur and draw.textlength(cur + ch, font=font) > max_w:
                out.append(cur)
                cur = ch
            else:
                cur += ch
        if cur:
            out.append(cur)
    return out


def _fit_cover(img: Image.Image, tw: int, th: int) -> Image.Image:
    """Resize + center-crop so img exactly covers tw x th (no letterboxing)."""
    img = img.convert("RGB")
    scale = max(tw / img.width, th / img.height)
    img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))),
                     Image.LANCZOS)
    left, top = (img.width - tw) // 2, 0  # anchor to top so the subject (upper 2/3) stays
    return img.crop((left, top, left + tw, top + th))


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    """WCAG relative luminance of an sRGB colour, 0.0 (black) .. 1.0 (white)."""
    def _lin(c: float) -> float:
        c /= 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def _contrast_ratio(fg: tuple[int, int, int], bg: tuple[int, int, int]) -> float:
    """WCAG contrast ratio between two colours, 1.0 .. 21.0."""
    l1, l2 = _relative_luminance(fg), _relative_luminance(bg)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def _mean_rgb(img: Image.Image, box: tuple[int, int, int, int]) -> tuple[int, int, int]:
    """Mean RGB of a bounding box (clamped to the image), for a contrast probe."""
    x0, y0, x1, y1 = box
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(img.width, x1), min(img.height, y1)
    if x1 <= x0 or y1 <= y0:
        return (0, 0, 0)
    region = img.crop((x0, y0, x1, y1))
    stat = region.resize((1, 1), Image.BOX).getpixel((0, 0))
    return (stat[0], stat[1], stat[2])


def _draw_text_with_shadow(xy, text, *, draw: ImageDraw.ImageDraw, font, fill,
                           shadow=(0, 0, 0), offset: int = 2) -> None:
    """Draw text with a soft dark halo so it stays legible on ANY background.

    Invisible on the dark imagery we normally get, and the safety net when a hero
    image happens to be light behind the text. The halo is a symmetric ring drawn
    around the glyphs (not a directional drop shadow)."""
    x, y = xy
    r = max(1, offset)
    for dx in range(-r, r + 1):
        for dy in range(-r, r + 1):
            if dx == 0 and dy == 0:
                continue
            draw.text((x + dx, y + dy), text, font=font, fill=shadow)
    draw.text((x, y), text, font=font, fill=fill)


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
    eyebrow_px = int(34 * scale / 2)
    eyebrow_gap = int(40 * scale / 2)
    f_eye = _font("Inter-SemiBold.ttf", eyebrow_px)

    # Auto-size the headline so the bottom-anchored label + headline block fills
    # AT LEAST the bottom third of the card. Bigger headline = bigger block; we
    # grow the font until the block (eyebrow + accent bar + wrapped lines) spans
    # >= H/3, capping so it never eats more than ~46% of the card, overflows the
    # bottom, OR overflows the RIGHT edge (a single word too wide to fit the text
    # column at that size — _wrap cannot break a word, so we must stop growing).
    max_w = W - 2 * margin

    def _fits_width(f: ImageFont.FreeTypeFont, wrapped: list[str]) -> bool:
        return all(draw.textlength(ln, font=f) <= max_w for ln in wrapped)

    def _block_height(px: int) -> tuple[int, list[str]]:
        f = _font("Inter-Bold.ttf", px)
        wrapped = _wrap(draw, headline, f, max_w)
        lh = int(px * 1.16)
        # headline lines + gap + eyebrow + accent bar breathing room (~90px logical)
        h = lh * len(wrapped) + eyebrow_gap + eyebrow_px + int(90 * scale / 2)
        return h, wrapped

    target = H // 3
    cap = int(H * 0.46)
    floor_px = int(96 * scale / 2)
    head_px = floor_px
    lines = _wrap(draw, headline, _font("Inter-Bold.ttf", head_px), max_w)
    for px in range(floor_px, int(240 * scale / 2) + 1, 4):
        h, wrapped = _block_height(px)
        # Stop growing if the block would exceed the height cap OR any line would
        # spill past the right edge at this size (an unbreakable long word).
        if h > cap or not _fits_width(_font("Inter-Bold.ttf", px), wrapped):
            break
        head_px, lines = px, wrapped
        if h >= target:
            break
    line_h = int(head_px * 1.16)
    f_head = _font("Inter-Bold.ttf", head_px)

    # Safety net: even the floor size can overflow the column if the headline
    # contains a single very long token. Break any still-too-wide line at the
    # character level so text never clips off the canvas edge.
    lines = _hard_break_wide_lines(draw, lines, f_head, max_w)

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

    # QC contrast probe: sample the composited background luminance behind the
    # text before drawing. The eyebrow is accent-coloured, the headline white; if
    # either would read on a background too close to its own colour, we fail loud
    # so the caller falls back to the motif (guaranteed-legible) front card. The
    # shadow halo below handles moderate cases; this catches the hopeless ones
    # (e.g. a bright object sitting under the text) that a halo can't rescue.
    head_bg = _mean_rgb(card, (margin, head_top, W - margin, H - margin))
    eye_bg = _mean_rgb(card, (margin, eyebrow_y, W - margin, eyebrow_y + eyebrow_px))
    min_contrast = float(os.environ.get("HERO_MIN_TEXT_CONTRAST", "1.7"))
    head_c = _contrast_ratio((255, 255, 255), head_bg)
    eye_c = _contrast_ratio(accent, eye_bg)
    if head_c < min_contrast or eye_c < min_contrast:
        raise HeroImageError(
            "front-card text contrast too low "
            f"(headline {head_c:.2f}, eyebrow {eye_c:.2f}, need >= {min_contrast}); "
            "hero image is too light/similar behind the text"
        )

    # Accent bar + eyebrow label + headline, each drawn with a soft dark halo so
    # they stay legible on ANY background (invisible on the dark imagery we
    # normally get; the safety net when a hero happens to be light behind text).
    label = brand.account_name.upper()
    halo = max(2, int(3 * scale / 2))
    draw.rectangle([margin, bar_y, margin + int(90 * scale / 2), bar_y + bar_h], fill=accent)
    _draw_text_with_shadow((margin, eyebrow_y), label, draw=draw, font=f_eye,
                           fill=accent, offset=halo)
    y = head_top
    for ln in lines:
        _draw_text_with_shadow((margin, y), ln, draw=draw, font=f_head,
                               fill=(255, 255, 255), offset=halo)
        y += line_h

    assert_dimensions(card, W, H)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    card.save(out_path, "JPEG", quality=brand.jpeg_quality)
    return out_path
