from __future__ import annotations

import sqlite3
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS delivered_papers (
    paper_key      TEXT PRIMARY KEY,
    delivered_date TEXT NOT NULL,
    post_id        TEXT,
    account        TEXT
);
CREATE TABLE IF NOT EXISTS post_features (
    media_id         TEXT PRIMARY KEY,
    paper_key        TEXT,
    account          TEXT,
    topic_id         TEXT,
    source           TEXT,
    hero_vs_motif    TEXT,
    headline_pattern TEXT,
    published_date   TEXT
);
CREATE TABLE IF NOT EXISTS post_metrics (
    media_id           TEXT PRIMARY KEY,
    reach              INTEGER,
    views              INTEGER,
    saved              INTEGER,
    shares             INTEGER,
    likes              INTEGER,
    comments           INTEGER,
    total_interactions INTEGER,
    updated_at         TEXT,
    frozen_at          TEXT
);
"""

_METRIC_COLS = ("reach", "views", "saved", "shares", "likes", "comments",
                "total_interactions")


class Ledger:
    """Tiny SQLite ledger of papers already turned into delivered posts.

    paper_key is a stable identifier like 'arxiv:<id>' or 'doi:<doi>' so the
    same paper is never posted twice across runs.
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        if db_path is None:
            from scripts.lib import paths
            db_path = paths.ledger_path()
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.executescript(_SCHEMA)
            # Migrate older DBs created before the `account` column existed.
            cols = {r[1] for r in conn.execute("PRAGMA table_info(delivered_papers)")}
            if "account" not in cols:
                conn.execute("ALTER TABLE delivered_papers ADD COLUMN account TEXT")

    def _conn(self) -> sqlite3.Connection:
        # Parallel subagents each open the ledger and write concurrently at bundle
        # time. WAL lets readers and a single writer proceed without blocking, and
        # a busy timeout makes competing writers wait for the lock instead of
        # failing immediately with SQLITE_BUSY (which would silently drop a mark).
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def is_delivered(self, paper_key: str) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM delivered_papers WHERE paper_key = ?", (paper_key,)
            ).fetchone()
        return row is not None

    def mark_delivered(
        self, paper_key: str, delivered_date: str, post_id: str, account: str | None = None
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO delivered_papers "
                "(paper_key, delivered_date, post_id, account) VALUES (?, ?, ?, ?)",
                (paper_key, delivered_date, post_id, account),
            )
            conn.commit()

    def edition_number(self, account: str, today: str) -> int:
        """Per-account edition number for `today` = (distinct prior delivery days
        for this account) + 1. All posts delivered on the same day share the number,
        and it increments once per day the account actually posts. NULL-account rows
        (pre-migration) never count toward any account."""
        with self._conn() as conn:
            (n,) = conn.execute(
                "SELECT COUNT(DISTINCT delivered_date) FROM delivered_papers "
                "WHERE account = ? AND delivered_date < ?",
                (account, today),
            ).fetchone()
        return int(n) + 1

    def seen_keys(self) -> set[str]:
        with self._conn() as conn:
            rows = conn.execute("SELECT paper_key FROM delivered_papers").fetchall()
        return {r[0] for r in rows}

    # --- engagement feedback loop (collect-only) ---

    def attach_media(
        self, paper_key: str, *, media_id: str, account: str | None = None,
        features: dict | None = None,
    ) -> None:
        """Link a published media_id to its paper + record the feature tags used to
        attribute engagement (source, topic, hero-vs-motif, headline pattern)."""
        f = features or {}
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO post_features "
                "(media_id, paper_key, account, topic_id, source, hero_vs_motif, "
                " headline_pattern, published_date) VALUES (?,?,?,?,?,?,?,?)",
                (media_id, paper_key, account, f.get("topic_id"), f.get("source"),
                 f.get("hero_vs_motif"), f.get("headline_pattern"),
                 f.get("published_date")),
            )
            conn.commit()

    def post_features(self) -> dict[str, dict]:
        """All post_features rows keyed by media_id."""
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM post_features").fetchall()
        return {r["media_id"]: dict(r) for r in rows}

    def upsert_metrics(
        self, media_id: str, values: dict, *, updated_at: str, frozen: bool = False,
    ) -> None:
        """Insert/update a post's metric snapshot. Only known metric columns are
        written; `frozen` sets frozen_at=updated_at (a one-way freeze at ~7 days)."""
        cols = [c for c in _METRIC_COLS if c in values]
        with self._conn() as conn:
            existing = conn.execute(
                "SELECT 1 FROM post_metrics WHERE media_id = ?", (media_id,)
            ).fetchone()
            if existing is None:
                conn.execute("INSERT INTO post_metrics (media_id) VALUES (?)", (media_id,))
            sets = ", ".join(f"{c} = ?" for c in cols) + (", " if cols else "")
            params = [values[c] for c in cols]
            conn.execute(
                f"UPDATE post_metrics SET {sets}updated_at = ?, "
                "frozen_at = COALESCE(frozen_at, ?) WHERE media_id = ?",
                (*params, updated_at, updated_at if frozen else None, media_id),
            )
            conn.commit()

    def metrics(self, media_id: str) -> dict | None:
        """The metric snapshot for a media_id, or None if never polled."""
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM post_metrics WHERE media_id = ?", (media_id,)
            ).fetchone()
        return dict(row) if row else None
