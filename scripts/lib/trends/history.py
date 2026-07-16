"""Rolling per-topic, per-date term-frequency history persisted as one JSON file.

Shape: {topic_id: {"YYYY-MM-DD": {"n": int, "df": {term: count}}}}
Baseline windows exclude `today` so same-day re-runs are deterministic.
"""
from __future__ import annotations

import json
import os
from collections import Counter
from datetime import date, timedelta
from pathlib import Path


class TermHistory:
    def __init__(self, path: Path | str):
        self._path = Path(path)
        self._data: dict[str, dict[str, dict]] = {}
        self._load()

    def _load(self) -> None:
        try:
            self._data = json.loads(self._path.read_text())
        except (FileNotFoundError, ValueError, OSError):
            self._data = {}                          # missing/corrupt -> cold start

    def upsert(self, topic_id: str, day: date, *, n: int, df: dict[str, int]) -> None:
        # store only terms seen in >=2 docs to bound file size
        slim = {t: c for t, c in df.items() if c >= 2}
        self._data.setdefault(topic_id, {})[day.isoformat()] = {"n": n, "df": slim}

    def dates(self, topic_id: str) -> list[date]:
        return [date.fromisoformat(d) for d in self._data.get(topic_id, {})]

    def window_totals(
        self, topic_id: str, *, today: date, window_days: int
    ) -> tuple[int, dict[str, int]]:
        """Sum n and df across days in [today-window_days, today-1] (excludes today)."""
        start = today - timedelta(days=window_days)
        total_n = 0
        df: Counter[str] = Counter()
        for d_str, entry in self._data.get(topic_id, {}).items():
            d = date.fromisoformat(d_str)
            if start <= d < today:                   # strictly before today
                total_n += entry.get("n", 0)
                df.update(entry.get("df", {}))
        return total_n, dict(df)

    def prune(self, topic_id: str, *, today: date, window_days: int) -> None:
        # keep today plus the full baseline window (window_days back). Cutoff is
        # window_days+1 so the retained set is at most window_days+1 entries.
        if topic_id not in self._data:
            return                                   # nothing to prune
        cutoff = today - timedelta(days=window_days + 1)
        topic = self._data[topic_id]
        self._data[topic_id] = {
            d: e for d, e in topic.items() if date.fromisoformat(d) > cutoff
        }

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(json.dumps(self._data))
        os.replace(tmp, self._path)                  # atomic
