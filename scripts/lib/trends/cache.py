"""Per-day JSON cache for external trend `prepare()` results so same-day re-runs
make no extra API calls. now_ts is injectable for deterministic tests."""
from __future__ import annotations

import json
import os
import time
from datetime import date
from pathlib import Path


def _cache_path(data_dir, provider: str, topic_id: str, day: date) -> Path:
    return Path(data_dir) / "trend_cache" / f"{provider}_{topic_id}_{day.isoformat()}.json"


def write_cache(data_dir, provider, topic_id, day, payload, *, now_ts=None) -> None:
    ts = time.time() if now_ts is None else now_ts
    p = _cache_path(data_dir, provider, topic_id, day)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps({"ts": ts, "payload": payload}))
    os.replace(tmp, p)


def read_cache(data_dir, provider, topic_id, day, *, ttl_min, now_ts=None):
    ts = time.time() if now_ts is None else now_ts
    p = _cache_path(data_dir, provider, topic_id, day)
    try:
        blob = json.loads(p.read_text())
    except (FileNotFoundError, ValueError, OSError):
        return None
    if ts - blob.get("ts", 0) > ttl_min * 60:
        return None
    return blob.get("payload")
