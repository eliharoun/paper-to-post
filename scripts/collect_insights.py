#!/usr/bin/env python3
"""Collect Instagram post-insights into the ledger (collect-only, no scoring yet).

Two halves, split like the rest of the pipeline: `scripts/collect_insights.mjs`
talks to Composio (lists recent media, reads per-post insights) and prints a JSON
snapshot; this module ingests that snapshot into the SQLite `post_metrics` table,
freezing a post's numbers once it is `freeze_days` old (carousel saves/sends accrue
over days, so an early snapshot under-counts). Nothing here feeds selection — it
just accrues a queryable record of what actually earned saves/shares, so the
operator can tune topics by hand and a future PerfSignal can read frozen rows.

Run the fetch+ingest for a topic's account:
    research-insights --account DailyCSBits --acct-id cs --date 2026-08-01
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

from scripts.lib import paths
from scripts.lib.store import Ledger

_MJS = Path(__file__).parent / "collect_insights.mjs"


def _age_days(timestamp: str | None, today: str) -> int:
    """Whole days between an ISO media timestamp (YYYY-MM-DDT...) and `today`.

    A missing/blank/unparseable timestamp returns 0 (treat as fresh, don't freeze)
    rather than raising — one odd item must not crash the whole ingest batch."""
    if not timestamp:
        return 0
    try:
        d = date.fromisoformat(timestamp[:10])
    except ValueError:
        return 0
    return (date.fromisoformat(today) - d).days


def ingest_snapshot(snapshot: dict, ledger: Ledger, *, today: str, freeze_days: int) -> int:
    """Upsert each post's metrics into the ledger. Returns the count ingested.

    A post is frozen (its numbers finalized) once it is >= freeze_days old; frozen
    rows are never reopened (upsert_metrics keeps the first frozen_at). Posts with
    no metrics (older/ineligible media that returned nothing) are skipped."""
    n = 0
    for post in snapshot.get("posts", []):
        metrics = post.get("metrics") or {}
        if not metrics:
            continue
        media_id = post["media_id"]
        frozen = _age_days(post.get("timestamp"), today) >= freeze_days
        ledger.upsert_metrics(media_id, metrics, updated_at=today, frozen=frozen)
        n += 1
    return n


def _fetch_snapshot(account: str, lookback_days: int) -> dict:
    """Run the Composio .mjs fetcher and parse its JSON snapshot from stdout."""
    proc = subprocess.run(
        ["/bin/sh", "-c",
         f'~/.composio/composio run -f {_MJS} -- '
         f'--account "{account}" --lookback-days {lookback_days}'],
        capture_output=True, text=True,
    )
    # The CLI prints noise; the snapshot is the last JSON object on stdout.
    for line in reversed(proc.stdout.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    raise RuntimeError(f"no JSON snapshot from collector (stderr: {proc.stderr[-500:]})")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Collect IG post-insights into the ledger")
    ap.add_argument("--account", required=True, help="Composio connection alias, e.g. DailyCSBits")
    ap.add_argument("--date", default=None, help="collection date YYYY-MM-DD (default: today)")
    ap.add_argument("--lookback-days", type=int, default=20,
                    help="how far back to poll media (default 20)")
    ap.add_argument("--freeze-days", type=int, default=7,
                    help="freeze a post's metrics once it is this old (default 7)")
    ap.add_argument("--ledger", default=None)
    ap.add_argument("--snapshot", default=None,
                    help="read a pre-fetched snapshot JSON instead of calling Composio")
    args = ap.parse_args(argv)

    today = args.date or date.today().isoformat()
    ledger = Ledger(args.ledger) if args.ledger else Ledger(paths.ledger_path())

    if args.snapshot:
        snapshot = json.loads(Path(args.snapshot).read_text())
    else:
        try:
            snapshot = _fetch_snapshot(args.account, args.lookback_days)
        except RuntimeError as exc:
            print(f"insights fetch failed: {exc}", file=sys.stderr)
            return 2

    n = ingest_snapshot(snapshot, ledger, today=today, freeze_days=args.freeze_days)
    print(json.dumps({"account": args.account, "ingested": n, "date": today}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
