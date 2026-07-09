import json
from pathlib import Path

import pytest

from scripts import fetch_pubmed as fp
from scripts.fetch_pubmed import build_esearch_params, fetch_pubmed, parse_pubmed_xml

FIX = Path(__file__).parent / "fixtures" / "pubmed_efetch.xml"


def test_parse_pubmed_xml():
    papers = parse_pubmed_xml(FIX.read_text())
    assert len(papers) == 1
    p = papers[0]
    assert p.source == "pubmed"
    assert p.source_id == "40000001"
    assert p.doi == "10.1038/ng.2026.1"
    assert p.title == "Genomic Markers Predict Cancer Outcomes"
    assert "survival" in p.abstract.lower()
    assert p.authors == ["Rosalind Franklin", "Craig Venter"]
    assert p.venue == "Nature Genetics"
    assert p.published_date.isoformat() == "2026-06-29"
    assert p.is_preprint is False
    assert p.url == "https://pubmed.ncbi.nlm.nih.gov/40000001/"


def test_build_esearch_params():
    p = build_esearch_params("cancer genomics", "2026-06-28", "2026-07-01", retmax=50)
    assert p["db"] == "pubmed"
    assert p["term"] == "cancer genomics"
    assert p["mindate"] == "2026/06/28"
    assert p["maxdate"] == "2026/07/01"
    assert p["retmax"] == 50
    assert p["retmode"] == "json"
    assert p["retstart"] == 0


def test_fetch_pubmed_paginates_esearch(monkeypatch):
    # esearch returns a full page, then a short page -> stop; efetch returns fixture.
    monkeypatch.setattr(fp, "PUBMED_ESEARCH_PAGE", 2)
    monkeypatch.setattr(fp, "PUBMED_EFETCH_BATCH", 100)
    esearch_pages = [["1", "2"], ["3"]]  # 2 (==page, continue), then 1 (stop)
    state = {"i": 0}

    def fake_get_text(url, params=None, **kw):
        if "esearch" in url:
            page = esearch_pages[state["i"]]
            state["i"] += 1
            return json.dumps({"esearchresult": {"idlist": page}})
        return FIX.read_text()  # efetch -> 1 article

    monkeypatch.setattr(fp, "get_text", fake_get_text)
    papers = fetch_pubmed("q", "2026-06-28", "2026-07-01", sleep=lambda s: None)
    assert state["i"] == 2  # two esearch pages
    # 3 IDs collected, efetched in one batch; fixture yields 1 article per call
    assert len(papers) == 1


def test_parse_pubmed_xml_bad_body_raises_fetcherror():
    # NCBI can return HTTP 200 with a non-XML error page; must surface as FetchError.
    from scripts.fetch_pubmed import parse_pubmed_xml
    from scripts.lib.fetch_http import FetchError
    with pytest.raises(FetchError, match="malformed XML"):
        parse_pubmed_xml("<html><body>Service temporarily unavailable</body>")


def test_esearch_logs_when_ceiling_hit(monkeypatch, capsys):
    from scripts.fetch_pubmed import _esearch_all_ids
    monkeypatch.setattr(fp, "PUBMED_ESEARCH_PAGE", 2)
    monkeypatch.setattr(fp, "PUBMED_MAX_PAGES", 2)
    # every page returns a full batch -> ceiling reached
    monkeypatch.setattr(fp, "get_text",
                        lambda *a, **k: json.dumps({"esearchresult": {"idlist": ["1", "2"]}}))
    ids = _esearch_all_ids("q", "2026-07-01", "2026-07-03", sleep=lambda s: None)
    assert len(ids) == 4
    assert "hit the 2-page ceiling" in capsys.readouterr().err
