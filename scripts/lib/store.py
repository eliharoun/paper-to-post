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
"""


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
