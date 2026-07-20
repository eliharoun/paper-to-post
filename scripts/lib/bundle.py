from __future__ import annotations

import re
from pathlib import Path

_CARD_RE = re.compile(r"card_(\d+)\.jpg$")


def compose_caption(
    caption: str, source_url: str, hashtags: list[str] | None = None
) -> str:
    """Return a caption guaranteed to contain the article link, plus hashtags.

    Validation (Phase 4) already requires the link, but this is a defensive
    backstop so a bundle is never shipped with a linkless caption.

    `hashtags` is the post's structured `hashtags` field: each is normalized to a
    leading '#' and appended as a trailing block, skipping any already inline in
    the caption prose (so a writer who inlined tags isn't doubled). Without it the
    structured field never reached Instagram — only manually-inlined tags did.
    """
    body = caption
    if source_url and source_url not in caption:
        body = f"{caption}\n\n🔗 Read the paper: {source_url}"
    if hashtags:
        norm = [t if t.startswith("#") else f"#{t}" for t in hashtags if t.strip()]
        # skip tags already present in the caption prose (case-insensitive)
        low = body.lower()
        fresh = [t for t in norm if t.lower() not in low]
        if fresh:
            body = f"{body}\n\n{' '.join(fresh)}"
    return body


def ordered_card_paths(assets_dir: Path | str) -> list[Path]:
    """Return card_NN.jpg paths sorted by their numeric index (not lexically)."""
    assets_dir = Path(assets_dir)
    numbered: list[tuple[int, Path]] = []
    for p in assets_dir.iterdir():
        m = _CARD_RE.search(p.name)
        if m:
            numbered.append((int(m.group(1)), p))
    numbered.sort(key=lambda t: t[0])
    return [p for _, p in numbered]


def final_image_order(card_paths: list[Path], screenshot_path: Path | None) -> list[Path]:
    """Insert the paper screenshot second-to-last (just before the source card).

    Authored cards arrive title-first … source-last. If a screenshot exists, it
    goes immediately before that final source card, matching the intended reading
    order (title → story → the real paper → where it came from). With <2 cards or
    no screenshot, order is unchanged.
    """
    if not screenshot_path or not Path(screenshot_path).exists():
        return list(card_paths)
    if len(card_paths) < 2:
        return list(card_paths) + [Path(screenshot_path)]
    return list(card_paths[:-1]) + [Path(screenshot_path)] + [card_paths[-1]]
