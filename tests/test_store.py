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


def test_attach_media_links_paper_to_media(tmp_path):
    led = Ledger(tmp_path / "led.db")
    led.mark_delivered("arxiv:1", "2026-07-20", post_id="p1", account="cs")
    led.attach_media("arxiv:1", media_id="ig_123", account="cs",
                     features={"source": "arxiv", "topic_id": "swe_ml_ai",
                               "hero_vs_motif": "hero", "headline_pattern": "number"})
    feats = led.post_features()
    assert feats["ig_123"]["paper_key"] == "arxiv:1"
    assert feats["ig_123"]["source"] == "arxiv"
    assert feats["ig_123"]["hero_vs_motif"] == "hero"


def test_upsert_and_read_metrics(tmp_path):
    led = Ledger(tmp_path / "led.db")
    led.upsert_metrics("ig_123", {"reach": 1000, "saved": 42, "shares": 7, "likes": 90,
                                  "comments": 5, "views": 1200, "total_interactions": 144},
                       updated_at="2026-07-21", frozen=False)
    m = led.metrics("ig_123")
    assert m["reach"] == 1000 and m["saved"] == 42 and m["frozen_at"] is None
    # a later poll updates the same row (still unfrozen)
    led.upsert_metrics("ig_123", {"reach": 2000, "saved": 80}, updated_at="2026-07-22",
                       frozen=True)
    m2 = led.metrics("ig_123")
    assert m2["reach"] == 2000 and m2["saved"] == 80 and m2["frozen_at"] == "2026-07-22"


def test_metrics_missing_returns_none(tmp_path):
    led = Ledger(tmp_path / "led.db")
    assert led.metrics("nope") is None


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
