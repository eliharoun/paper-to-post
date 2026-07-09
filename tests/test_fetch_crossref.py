import json
from pathlib import Path

from scripts import fetch_crossref as cr
from scripts.fetch_crossref import fetch_crossref, parse_crossref_response, strip_jats

FIX = Path(__file__).parent / "fixtures" / "crossref_response.json"


def test_strip_jats():
    assert strip_jats("<jats:p>Hello <jats:italic>world</jats:italic></jats:p>") == "Hello world"
    assert strip_jats(None) is None


def test_parse_crossref_normalizes():
    papers = parse_crossref_response(json.loads(FIX.read_text()))
    assert len(papers) == 1
    p = papers[0]
    assert p.source == "crossref"
    assert p.doi == "10.1234/crossref.1"
    assert p.title == "Transformers for Genomics"
    assert p.abstract == "We apply transformers to genomic sequences with strong results."
    assert p.authors == ["Ada Lovelace", "Rosalind Franklin"]
    assert p.venue == "Bioinformatics"
    assert p.published_date.isoformat() == "2026-06-30"
    assert p.citation_count == 2


def _cr_page(n_items, total):
    item = json.loads(FIX.read_text())["message"]["items"][0]
    return json.dumps({"message": {"total-results": total, "items": [item] * n_items}})


def test_fetch_crossref_page_bounded_and_logs_cap(monkeypatch, capsys):
    monkeypatch.setattr(cr, "CROSSREF_PAGE_SIZE", 2)
    monkeypatch.setattr(cr, "CROSSREF_MAX_PAGES", 2)
    monkeypatch.setattr(cr, "get_text", lambda *a, **k: _cr_page(2, 500))
    papers = fetch_crossref("q", "2026-07-01", "2026-07-03", sleep=lambda s: None)
    assert len(papers) == 4  # 2 pages x 2
    assert "capped at 2 pages" in capsys.readouterr().err


def test_fetch_crossref_stops_early_no_log(monkeypatch, capsys):
    monkeypatch.setattr(cr, "CROSSREF_PAGE_SIZE", 2)
    monkeypatch.setattr(cr, "CROSSREF_MAX_PAGES", 5)
    monkeypatch.setattr(cr, "get_text", lambda *a, **k: _cr_page(1, 1))
    papers = fetch_crossref("q", "2026-07-01", "2026-07-03", sleep=lambda s: None)
    assert len(papers) == 1
    assert "capped" not in capsys.readouterr().err
