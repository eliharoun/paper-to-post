from scripts.lib.store import Ledger


def test_mark_and_check_delivered(tmp_path):
    led = Ledger(tmp_path / "led.db")
    assert not led.is_delivered("arxiv:2406.1")
    led.mark_delivered("arxiv:2406.1", "2026-07-01", post_id="post-abc")
    assert led.is_delivered("arxiv:2406.1")


def test_mark_delivered_is_idempotent(tmp_path):
    led = Ledger(tmp_path / "led.db")
    led.mark_delivered("arxiv:2406.1", "2026-07-01", post_id="a")
    led.mark_delivered("arxiv:2406.1", "2026-07-02", post_id="b")  # no error
    assert led.is_delivered("arxiv:2406.1")


def test_seen_keys_returns_all_delivered(tmp_path):
    led = Ledger(tmp_path / "led.db")
    led.mark_delivered("arxiv:1", "2026-07-01", post_id="a")
    led.mark_delivered("doi:10.1/x", "2026-07-02", post_id="b")
    assert led.seen_keys() == {"arxiv:1", "doi:10.1/x"}


def test_creates_parent_dir(tmp_path):
    led = Ledger(tmp_path / "nested" / "led.db")
    led.mark_delivered("k", "2026-07-01", post_id="p")
    assert led.is_delivered("k")
