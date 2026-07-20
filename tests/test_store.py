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


def test_uses_wal_and_busy_timeout(tmp_path):
    # Parallel subagents each open the ledger and write concurrently; the default
    # SQLite config (no busy timeout, rollback journal) raises SQLITE_BUSY and can
    # drop a mark_delivered. WAL + a busy timeout let concurrent writers serialize
    # instead of failing.
    led = Ledger(tmp_path / "led.db")
    with led._conn() as conn:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        busy = conn.execute("PRAGMA busy_timeout").fetchone()[0]
    assert mode.lower() == "wal"
    assert busy >= 5000


def test_concurrent_writes_all_recorded(tmp_path):
    # Simulate parallel bundle steps writing distinct keys at once. With WAL + a
    # busy timeout none should be lost to lock contention.
    import threading

    db = tmp_path / "led.db"
    Ledger(db)  # create schema once up front

    def writer(n: int) -> None:
        Ledger(db).mark_delivered(f"arxiv:{n}", "2026-07-01", post_id=f"p{n}")

    threads = [threading.Thread(target=writer, args=(n,)) for n in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    seen = Ledger(db).seen_keys()
    assert seen == {f"arxiv:{n}" for n in range(12)}
