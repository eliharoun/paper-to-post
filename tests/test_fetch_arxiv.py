from pathlib import Path

from scripts import fetch_arxiv as fa
from scripts.fetch_arxiv import build_arxiv_query, fetch_arxiv, parse_arxiv_atom

FIX = Path(__file__).parent / "fixtures" / "arxiv_response.xml"


def test_parse_arxiv_atom_normalizes_entries():
    papers = parse_arxiv_atom(FIX.read_text())
    assert len(papers) == 2
    p = papers[0]
    assert p.source == "arxiv"
    assert p.arxiv_id == "2406.00001"          # version stripped
    assert p.title == "A Simple Method for Better Language Models"
    assert p.authors == ["Ada Lovelace", "Alan Turing"]
    assert p.url == "http://arxiv.org/abs/2406.00001v2"
    assert p.pdf_url == "http://arxiv.org/pdf/2406.00001v2"
    assert p.is_preprint is True
    assert p.published_date.isoformat() == "2026-06-28"
    assert "language model" in (p.abstract or "").lower()


def test_parse_arxiv_atom_handles_single_author():
    papers = parse_arxiv_atom(FIX.read_text())
    assert papers[1].authors == ["Grace Hopper"]
    assert papers[1].arxiv_id == "2406.00002"


def test_build_arxiv_query_categories_and_dates():
    q = build_arxiv_query(
        categories=["cs.AI", "cs.CL"],
        since="2026-06-28",
        until="2026-07-01",
    )
    assert "cat:cs.AI" in q["search_query"]
    assert "cat:cs.CL" in q["search_query"]
    assert "submittedDate:[202606280000 TO 202607010000]" in q["search_query"]
    assert q["sortBy"] == "submittedDate"
    assert q["sortOrder"] == "descending"
    assert q["max_results"] == 50


def test_fetch_arxiv_paginates_until_short_page(monkeypatch):
    # Two full pages then a short one -> stop after the short page.
    full = FIX.read_text()  # 2 entries
    pages = [full, full, full]  # 2,2,2 entries; page size forced to 2 below

    calls = {"n": 0}

    def fake_get_text(url, params=None, **kw):
        i = calls["n"]
        calls["n"] += 1
        return pages[i] if i < len(pages) else "<feed></feed>"

    monkeypatch.setattr(fa, "get_text", fake_get_text)
    monkeypatch.setattr(fa, "ARXIV_PAGE_SIZE", 2)
    monkeypatch.setattr(fa, "ARXIV_MAX_PAGES", 10)
    papers = fetch_arxiv(["cs.AI"], "2026-07-01", "2026-07-03", sleep=lambda s: None)
    # page1=2 (==size, continue), page2=2 (continue), page3 also 2 but fixture
    # only has 3 pages then empty -> 4th call returns empty feed -> stop.
    assert calls["n"] == 4
    assert len(papers) == 6


def test_fetch_arxiv_respects_max_results(monkeypatch):
    monkeypatch.setattr(fa, "get_text", lambda *a, **k: FIX.read_text())
    monkeypatch.setattr(fa, "ARXIV_PAGE_SIZE", 2)
    papers = fetch_arxiv(
        ["cs.AI"], "2026-07-01", "2026-07-03", max_results=3, sleep=lambda s: None
    )
    assert len(papers) == 3


def test_fetch_arxiv_logs_when_ceiling_hit(monkeypatch, capsys):
    # Every page full + low ceiling -> loop exits via ceiling, must warn.
    monkeypatch.setattr(fa, "ARXIV_PAGE_SIZE", 2)
    monkeypatch.setattr(fa, "ARXIV_MAX_PAGES", 2)
    monkeypatch.setattr(fa, "get_text", lambda *a, **k: FIX.read_text())  # 2 entries = full
    papers = fetch_arxiv(["cs.AI"], "2026-07-01", "2026-07-03", sleep=lambda s: None)
    assert len(papers) == 4  # 2 pages x 2
    assert "hit the 2-page ceiling" in capsys.readouterr().err
