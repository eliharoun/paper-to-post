from __future__ import annotations

from PIL import Image


def fit_onto_canvas(src: Image.Image, *, canvas_w: int, canvas_h: int, bg: str) -> Image.Image:
    """Scale src to fit within canvas preserving aspect, centered on a bg canvas."""
    canvas = Image.new("RGB", (canvas_w, canvas_h), bg)
    src = src.convert("RGB")
    scale = min(canvas_w / src.width, canvas_h / src.height)
    new_w, new_h = max(1, int(src.width * scale)), max(1, int(src.height * scale))
    resized = src.resize((new_w, new_h), Image.LANCZOS)
    x, y = (canvas_w - new_w) // 2, (canvas_h - new_h) // 2
    canvas.paste(resized, (x, y))
    return canvas


def assert_dimensions(img: Image.Image, width: int, height: int) -> None:
    if img.size != (width, height):
        raise ValueError(f"expected {width}x{height}, got {img.size[0]}x{img.size[1]}")
    if img.mode != "RGB":
        raise ValueError(f"expected RGB, got {img.mode}")
