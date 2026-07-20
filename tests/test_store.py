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


def test_edition_number_counts_distinct_prior_days(tmp_path):
    led = Ledger(tmp_path / "led.db")
    # cs delivered on 2 distinct prior days (2 posts on day 1 share the day)
    led.mark_delivered("arxiv:1", "2026-07-18", post_id="a", account="cs")
    led.mark_delivered("arxiv:2", "2026-07-18", post_id="b", account="cs")
    led.mark_delivered("arxiv:3", "2026-07-19", post_id="c", account="cs")
    # today (2026-07-20) is the 3rd edition for cs
    assert led.edition_number("cs", "2026-07-20") == 3
    # all posts on the same current day share the number (today not yet recorded)
    assert led.edition_number("cs", "2026-07-19") == 2  # only 07-18 is strictly prior


def test_edition_number_is_per_account(tmp_path):
    led = Ledger(tmp_path / "led.db")
    led.mark_delivered("arxiv:1", "2026-07-18", post_id="a", account="cs")
    led.mark_delivered("pm:1", "2026-07-18", post_id="b", account="bio")
    led.mark_delivered("pm:2", "2026-07-19", post_id="c", account="bio")
    assert led.edition_number("cs", "2026-07-20") == 2   # cs delivered 1 prior day
    assert led.edition_number("bio", "2026-07-20") == 3  # bio delivered 2 prior days


def test_edition_number_first_ever_is_one(tmp_path):
    led = Ledger(tmp_path / "led.db")
    assert led.edition_number("cs", "2026-07-20") == 1


def test_mark_delivered_account_is_optional_backcompat(tmp_path):
    # Existing callers that don't pass account still work (account stored NULL).
    led = Ledger(tmp_path / "led.db")
    led.mark_delivered("arxiv:1", "2026-07-18", post_id="a")  # no account
    assert led.is_delivered("arxiv:1")
    # NULL-account rows don't count toward any account's edition number
    assert led.edition_number("cs", "2026-07-20") == 1


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
