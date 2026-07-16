from datetime import date

from scripts.lib.trends.history import TermHistory


def test_upsert_and_window_excludes_today(tmp_path):
    p = tmp_path / "term_history.json"
    h = TermHistory(p)
    h.upsert("cs", date(2026, 7, 13), n=100, df={"llm": 20, "rag": 5})
    h.upsert("cs", date(2026, 7, 14), n=120, df={"llm": 30, "agents": 10})
    h.save()

    h2 = TermHistory(p)
    # window strictly BEFORE today(15), window_days=14 -> includes 13 and 14
    total_n, df = h2.window_totals("cs", today=date(2026, 7, 15), window_days=14)
    assert total_n == 220
    assert df["llm"] == 50
    # today's own entry must never be in the baseline
    h2.upsert("cs", date(2026, 7, 15), n=200, df={"llm": 999})
    total_n2, df2 = h2.window_totals("cs", today=date(2026, 7, 15), window_days=14)
    assert total_n2 == 220 and df2["llm"] == 50


def test_upsert_overwrites_same_date(tmp_path):
    p = tmp_path / "h.json"
    h = TermHistory(p)
    h.upsert("cs", date(2026, 7, 14), n=100, df={"llm": 20})
    h.upsert("cs", date(2026, 7, 14), n=150, df={"llm": 40})  # rerun same day
    total_n, df = h.window_totals("cs", today=date(2026, 7, 15), window_days=14)
    assert total_n == 150 and df["llm"] == 40


def test_prune_drops_old_dates(tmp_path):
    p = tmp_path / "h.json"
    h = TermHistory(p)
    for day in range(1, 21):                       # 20 days of history
        h.upsert("cs", date(2026, 6, day), n=10, df={"x": 2})
    h.prune("cs", today=date(2026, 6, 20), window_days=14)
    dates = h.dates("cs")
    # keeps 6/6..6/20 = 15 entries; older dates are dropped
    assert len(dates) == 15
    assert date(2026, 6, 1) not in dates
    assert date(2026, 6, 20) in dates              # today retained
    assert date(2026, 6, 6) in dates               # window start retained (excl. today)


def test_corrupt_file_loads_as_empty(tmp_path):
    p = tmp_path / "h.json"
    p.write_text("{ not valid json")
    h = TermHistory(p)                              # must not raise
    total_n, df = h.window_totals("cs", today=date(2026, 7, 15), window_days=14)
    assert total_n == 0 and df == {}


def test_atomic_save_creates_file(tmp_path):
    p = tmp_path / "sub" / "h.json"
    p.parent.mkdir()
    h = TermHistory(p)
    h.upsert("cs", date(2026, 7, 14), n=10, df={"x": 2})
    h.save()
    assert p.exists()
    assert not (p.parent / (p.name + ".tmp")).exists()   # temp cleaned up
