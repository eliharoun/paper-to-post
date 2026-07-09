import json
from pathlib import Path

from scripts.fetch_semantic_scholar import build_s2_params, parse_s2_response

FIX = Path(__file__).parent / "fixtures" / "s2_response.json"


def test_parse_s2_normalizes():
    papers = parse_s2_response(json.loads(FIX.read_text()))
    assert len(papers) == 2
    a = papers[0]
    assert a.source == "semantic_scholar"
    assert a.semantic_scholar_id == "s2aaa111"
    assert a.doi == "10.1234/abc"
    assert a.arxiv_id == "2406.00001"
    assert a.pdf_url == "https://arxiv.org/pdf/2406.00001"
    assert a.is_open_access is True
    assert a.citation_count == 3
    assert a.authors == ["Ada Lovelace", "Alan Turing"]


def test_parse_s2_handles_missing_pdf_and_ids():
    papers = parse_s2_response(json.loads(FIX.read_text()))
    b = papers[1]
    assert b.pdf_url is None
    assert b.arxiv_id is None
    assert b.doi == "10.5555/xyz"
    assert b.is_open_access is False
    assert b.venue == "Nature Genetics"


def test_build_s2_params():
    p = build_s2_params(query="machine learning", since="2026-06-28", until="2026-07-01")
    assert p["query"] == "machine learning"
    assert p["fields"].startswith("paperId,title,abstract")
    assert p["publicationDateOrYear"] == "2026-06-28:2026-07-01"
    assert p["limit"] == 100
