import json
from datetime import date

from scripts.collect_insights import ingest_snapshot
from scripts.lib.store import Ledger


def _snap(posts):
    return {"account": "cs", "collected_at": "2026-08-01", "posts": posts}


def test_ingest_writes_metrics(tmp_path):
    led = Ledger(tmp_path / "led.db")
    snap = _snap([
        {"media_id": "ig_1", "timestamp": "2026-07-30T10:00:00+0000",
         "metrics": {"reach": 500, "saved": 20, "shares": 3}},
    ])
    n = ingest_snapshot(snap, led, today="2026-08-01", freeze_days=7)
    assert n == 1
    m = led.metrics("ig_1")
    assert m["reach"] == 500 and m["saved"] == 20
    # only 2 days old -> not frozen yet
    assert m["frozen_at"] is None


def test_ingest_freezes_posts_past_window(tmp_path):
    led = Ledger(tmp_path / "led.db")
    snap = _snap([
        {"media_id": "ig_old", "timestamp": "2026-07-01T10:00:00+0000",
         "metrics": {"reach": 900, "saved": 40}},
    ])
    ingest_snapshot(snap, led, today="2026-08-01", freeze_days=7)  # 31 days old
    assert led.metrics("ig_old")["frozen_at"] == "2026-08-01"


def test_ingest_does_not_reopen_frozen(tmp_path):
    led = Ledger(tmp_path / "led.db")
    # first pass freezes it
    ingest_snapshot(_snap([{"media_id": "ig_1", "timestamp": "2026-07-01T00:00:00+0000",
                            "metrics": {"reach": 100}}]),
                    led, today="2026-08-01", freeze_days=7)
    frozen_at = led.metrics("ig_1")["frozen_at"]
    # a later pass with new numbers must NOT move frozen_at
    ingest_snapshot(_snap([{"media_id": "ig_1", "timestamp": "2026-07-01T00:00:00+0000",
                            "metrics": {"reach": 999}}]),
                    led, today="2026-08-05", freeze_days=7)
    assert led.metrics("ig_1")["frozen_at"] == frozen_at


def test_ingest_skips_posts_without_metrics(tmp_path):
    led = Ledger(tmp_path / "led.db")
    n = ingest_snapshot(_snap([{"media_id": "ig_1", "timestamp": "2026-07-30T00:00:00+0000",
                                "metrics": {}}]),
                        led, today="2026-08-01", freeze_days=7)
    assert n == 0
    assert led.metrics("ig_1") is None
