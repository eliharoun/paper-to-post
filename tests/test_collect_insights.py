
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


def test_ingest_skips_posts_without_metrics(tmp_path):
    led = Ledger(tmp_path / "led.db")
    n = ingest_snapshot(_snap([{"media_id": "ig_1", "timestamp": "2026-07-30T00:00:00+0000",
                                "metrics": {}}]),
                        led, today="2026-08-01", freeze_days=7)
    assert n == 0
    assert led.metrics("ig_1") is None


def test_ingest_tolerates_null_or_empty_timestamp(tmp_path):
    # A real IG response can carry timestamp: null / "" for an odd item. One bad
    # timestamp must NOT crash the whole batch — that post ingests (treated as fresh).
    led = Ledger(tmp_path / "led.db")
    snap = _snap([
        {"media_id": "ig_null", "timestamp": None, "metrics": {"reach": 5}},
        {"media_id": "ig_empty", "timestamp": "", "metrics": {"reach": 6}},
        {"media_id": "ig_ok", "timestamp": "2026-07-30T00:00:00+0000", "metrics": {"reach": 7}},
    ])
    n = ingest_snapshot(snap, led, today="2026-08-01", freeze_days=7)
    assert n == 3
    assert led.metrics("ig_null")["reach"] == 5
    assert led.metrics("ig_ok")["reach"] == 7


def test_freeze_pins_the_numbers(tmp_path):
    # Once frozen, a later poll must NOT overwrite the metrics (the PerfSignal will
    # trust frozen rows as stable). Only pre-freeze polls update the numbers.
    led = Ledger(tmp_path / "led.db")
    ingest_snapshot(_snap([{"media_id": "ig_1", "timestamp": "2026-07-01T00:00:00+0000",
                            "metrics": {"reach": 100, "saved": 5}}]),
                    led, today="2026-07-08", freeze_days=7)
    assert led.metrics("ig_1")["frozen_at"] == "2026-07-08"
    ingest_snapshot(_snap([{"media_id": "ig_1", "timestamp": "2026-07-01T00:00:00+0000",
                            "metrics": {"reach": 999, "saved": 88}}]),
                    led, today="2026-07-20", freeze_days=7)
    m = led.metrics("ig_1")
    assert m["reach"] == 100 and m["saved"] == 5  # pinned at the freeze snapshot


def test_unfrozen_metrics_still_update(tmp_path):
    led = Ledger(tmp_path / "led.db")
    ingest_snapshot(_snap([{"media_id": "ig_1", "timestamp": "2026-07-30T00:00:00+0000",
                            "metrics": {"reach": 10}}]),
                    led, today="2026-07-31", freeze_days=7)
    ingest_snapshot(_snap([{"media_id": "ig_1", "timestamp": "2026-07-30T00:00:00+0000",
                            "metrics": {"reach": 50}}]),
                    led, today="2026-08-01", freeze_days=7)
    assert led.metrics("ig_1")["reach"] == 50  # updated, not yet frozen


def test_freeze_boundary_exactly_at_window(tmp_path):
    led = Ledger(tmp_path / "led.db")
    ingest_snapshot(_snap([{"media_id": "ig_1", "timestamp": "2026-07-25T00:00:00+0000",
                            "metrics": {"reach": 1}}]),
                    led, today="2026-08-01", freeze_days=7)  # exactly 7 days
    assert led.metrics("ig_1")["frozen_at"] == "2026-08-01"
