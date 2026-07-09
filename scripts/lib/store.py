from __future__ import annotations

import sqlite3
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS delivered_papers (
    paper_key      TEXT PRIMARY KEY,
    delivered_date TEXT NOT NULL,
    post_id        TEXT
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

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def is_delivered(self, paper_key: str) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM delivered_papers WHERE paper_key = ?", (paper_key,)
            ).fetchone()
        return row is not None

    def mark_delivered(self, paper_key: str, delivered_date: str, post_id: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO delivered_papers "
                "(paper_key, delivered_date, post_id) VALUES (?, ?, ?)",
                (paper_key, delivered_date, post_id),
            )
            conn.commit()

    def seen_keys(self) -> set[str]:
        with self._conn() as conn:
            rows = conn.execute("SELECT paper_key FROM delivered_papers").fetchall()
        return {r[0] for r in rows}
