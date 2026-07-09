#!/usr/bin/env python3
"""Deliver a finished bundle to Telegram: cards in order, then the caption.

Credentials come from the environment only (never arguments/files/logs):
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
The bot can only message a chat that has already started a conversation with it.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

from scripts.lib.bundle import ordered_card_paths

API = "https://api.telegram.org"


def _post(token: str, method: str, *, data: dict, files: dict | None = None) -> dict:
    url = f"{API}/bot{token}/{method}"
    with httpx.Client(timeout=60) as client:
        resp = client.post(url, data=data, files=files)
    payload = resp.json()
    if not payload.get("ok"):
        # surface Telegram's error description WITHOUT the token
        desc = payload.get("description", resp.status_code)
        raise RuntimeError(f"telegram {method} failed: {desc}")
    return payload


def send_media_group(token: str, chat_id: str, images: list[Path]) -> None:
    """Send cards as albums (Telegram caps media groups at 10 items)."""
    for start in range(0, len(images), 10):
        batch = images[start:start + 10]
        media = [{"type": "photo", "media": f"attach://p{i}"} for i in range(len(batch))]
        files = {f"p{i}": (p.name, p.read_bytes(), "image/jpeg") for i, p in enumerate(batch)}
        _post(token, "sendMediaGroup", data={"chat_id": chat_id,
              "media": json.dumps(media)}, files=files)


def send_text(token: str, chat_id: str, text: str) -> None:
    # Telegram hard-caps a text message at 4096 chars
    for start in range(0, len(text), 4096):
        _post(token, "sendMessage", data={"chat_id": chat_id, "text": text[start:start + 4096]})


def deliver_bundle(token: str, chat_id: str, bundle_dir: Path) -> dict:
    cards = ordered_card_paths(bundle_dir)
    if not cards:
        raise RuntimeError(f"no card_NN.jpg images found in {bundle_dir}")
    caption = bundle_dir / "caption.txt"

    send_media_group(token, chat_id, cards)
    if caption.exists():
        send_text(token, chat_id, "📝 CAPTION (copy for the post):\n\n" + caption.read_text())
    return {"cards_sent": len(cards), "caption": caption.exists()}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Send a bundle to Telegram (cards, caption, alt)")
    ap.add_argument("--bundle", required=True, help="bundle dir with card_NN.jpg + caption.txt")
    args = ap.parse_args(argv)

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        print("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in the environment",
              file=sys.stderr)
        return 2

    try:
        result = deliver_bundle(token, chat_id, Path(args.bundle))
    except (httpx.HTTPError, RuntimeError) as exc:
        print(f"delivery failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
