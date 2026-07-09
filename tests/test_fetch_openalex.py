import json
from pathlib import Path

from scripts import fetch_openalex as oa
from scripts.fetch_openalex import fetch_openalex, invert_abstract, parse_openalex_response

FIX = Path(__file__).parent / "fixtures" / "openalex_response.json"


def test_invert_abstract():
    idx = {"Deep": [0], "learning": [1], "wins": [2]}
    assert invert_abstract(idx) == "Deep learning wins"


def test_invert_abstract_empty():
    assert invert_abstract(None) is None
    assert invert_abstract({}) is None


def test_parse_openalex_normalizes():
    papers = parse_openalex_response(json.loads(FIX.read_text()))
    assert len(papers) == 1
    p = papers[0]
    assert p.source == "openalex"
    assert p.openalex_id == "W123456789"
    assert p.doi == "10.1234/openalex.1"       # https://doi.org/ stripped
    assert p.abstract == "Deep learning predicts structure"
    assert p.authors == ["Ada Lovelace", "Alan Turing"]
    assert p.pdf_url == "https://example.org/paper1.pdf"
    assert p.is_open_access is True
    assert p.citation_count == 5
    assert p.venue == "Journal of ML"


def _page(n_results, count, cursor_meta=True):
    base = json.loads(FIX.read_text())
    item = base["results"][0]
    return json.dumps({"meta": {"count": count}, "results": [item] * n_results})


def test_fetch_openalex_page_bounded_and_logs_cap(monkeypatch, capsys):
    monkeypatch.setattr(oa, "OPENALEX_PAGE_SIZE", 2)
    monkeypatch.setattr(oa, "OPENALEX_MAX_PAGES", 2)
    # Every page is "full" (2 items) and count is huge -> hits page cap, logs.
    monkeypatch.setattr(oa, "get_text", lambda *a, **k: _page(2, 999))
    papers = fetch_openalex("q", "2026-07-01", "2026-07-03", sleep=lambda s: None)
    assert len(papers) == 4  # 2 pages x 2
    assert "capped at 2 pages" in capsys.readouterr().err


def test_fetch_openalex_stops_early_no_log(monkeypatch, capsys):
    monkeypatch.setattr(oa, "OPENALEX_PAGE_SIZE", 2)
    monkeypatch.setattr(oa, "OPENALEX_MAX_PAGES", 5)
    # Short first page -> exhausted, no cap message.
    monkeypatch.setattr(oa, "get_text", lambda *a, **k: _page(1, 1))
    papers = fetch_openalex("q", "2026-07-01", "2026-07-03", sleep=lambda s: None)
    assert len(papers) == 1
    assert "capped" not in capsys.readouterr().err


def test_build_openalex_params_subfield_filter():
    p = oa.build_openalex_params(
        "", "2026-07-06", "2026-07-08", subfields=["1702", "1707", "1712"]
    )
    f = p["filter"]
    assert "primary_topic.subfield.id:1702|1707|1712" in f
    assert "type:article" in f
    assert "language:en" in f
    assert "has_abstract:true" in f
    assert "is_paratext:false" in f
    assert "from_publication_date:2026-07-06" in f
    assert "search" not in p  # empty query -> omitted (avoids strict AND matching nothing)


def test_build_openalex_params_query_only_omits_subfield_extras():
    p = oa.build_openalex_params("machine learning", "2026-07-06", "2026-07-08")
    assert p["search"] == "machine learning"
    assert "primary_topic.subfield.id" not in p["filter"]
    assert "language:en" not in p["filter"]  # only added alongside subfields


def test_fetch_openalex_passes_subfields(monkeypatch):
    seen = {}

    def fake_get_text(url, params=None, **kw):
        seen["filter"] = params["filter"]
        return json.dumps({"meta": {"count": 1}, "results": []})

    monkeypatch.setattr(oa, "get_text", fake_get_text)
    oa.fetch_openalex("", "2026-07-06", "2026-07-08", subfields=["1702"], sleep=lambda s: None)
    assert "primary_topic.subfield.id:1702" in seen["filter"]
