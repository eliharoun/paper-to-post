from pathlib import Path

import pytest

from scripts.fetch_labs import (
    LAB_INSTITUTIONS,
    build_labs_params,
    fetch_labs,
    resolve_institution_ids,
)

FIX = Path(__file__).parent / "fixtures" / "labs_response.json"


def test_resolve_institution_ids_maps_and_dedupes():
    ids = resolve_institution_ids(["meta", "google", "deepmind"])
    # every mapped id present, order preserved, no dupes
    assert ids[: len(LAB_INSTITUTIONS["meta"])] == LAB_INSTITUTIONS["meta"]
    assert len(ids) == len(set(ids))
    assert "I4210090411" in ids  # deepmind


def test_resolve_institution_ids_case_insensitive():
    assert resolve_institution_ids(["Meta", "GOOGLE"]) == resolve_institution_ids(
        ["meta", "google"]
    )


def test_resolve_institution_ids_unknown_lab():
    with pytest.raises(ValueError, match="unknown lab"):
        resolve_institution_ids(["openai"])


def test_build_labs_params_filters_and_search():
    params = build_labs_params(["I1", "I2"], "2026-06-01", "2026-07-01", query="LLM")
    f = params["filter"]
    assert "authorships.institutions.id:I1|I2" in f
    assert "from_publication_date:2026-06-01" in f
    assert "to_publication_date:2026-07-01" in f
    assert "type:article" in f
    assert params["search"] == "LLM"
    assert params["sort"] == "publication_date:desc"


def test_build_labs_params_omits_search_when_no_query():
    params = build_labs_params(["I1"], "2026-06-01", "2026-07-01")
    assert "search" not in params


def test_fetch_labs_relabels_source(monkeypatch):
    monkeypatch.setattr("scripts.fetch_labs.get_text", lambda *a, **k: FIX.read_text())
    papers = fetch_labs(["meta"], "2026-07-01", "2026-07-06")
    assert len(papers) == 1
    p = papers[0]
    assert p.source == "labs"  # not "openalex"
    assert p.doi == "10.1234/labs.1"
    assert p.title == "Scaling Laws for Multimodal Foundation Models"
    assert p.pdf_url == "https://example.org/labs1.pdf"
