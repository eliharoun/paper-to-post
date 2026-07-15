from pathlib import Path

import pytest

from scripts.fetch_journals import (
    build_journals_params,
    fetch_journals,
)
from scripts.lib.journals import (
    JOURNAL_SOURCES,
    is_flagship_venue,
    resolve_source_ids,
)

FIX = Path(__file__).parent / "fixtures" / "journals_response.json"


def test_resolve_source_ids_maps_and_dedupes():
    ids = resolve_source_ids(["nature", "lancet", "nature"])  # dup nature
    assert ids == ["S137773608", "S49861241"]  # order preserved, deduped


def test_resolve_source_ids_case_insensitive():
    assert resolve_source_ids(["Nature", "LANCET"]) == resolve_source_ids(
        ["nature", "lancet"]
    )


def test_resolve_source_ids_unknown_journal():
    with pytest.raises(ValueError, match="unknown journal"):
        resolve_source_ids(["jama"])


def test_build_journals_params_filters_and_search():
    params = build_journals_params(["S1", "S2"], "2026-06-01", "2026-07-01", query="cancer")
    f = params["filter"]
    assert "primary_location.source.id:S1|S2" in f
    assert "from_publication_date:2026-06-01" in f
    assert "to_publication_date:2026-07-01" in f
    assert "type:article" in f
    assert "has_abstract:true" in f
    assert params["search"] == "cancer"
    assert params["sort"] == "publication_date:desc"


def test_build_journals_params_omits_search_when_no_query():
    params = build_journals_params(["S1"], "2026-06-01", "2026-07-01")
    assert "search" not in params


def test_fetch_journals_relabels_source(monkeypatch):
    monkeypatch.setattr("scripts.fetch_journals.get_text", lambda *a, **k: FIX.read_text())
    papers = fetch_journals(["nature"], "2026-07-01", "2026-07-06")
    assert len(papers) == 1
    p = papers[0]
    assert p.source == "journals"  # not "openalex"
    assert p.doi == "10.1038/journals.1"
    assert p.venue == "Nature"
    assert p.title == "A Single-Cell Atlas of the Human Cortex"


# --- is_flagship_venue (used by the scorer, any source) ---

def test_is_flagship_venue_matches_variants():
    assert is_flagship_venue("Nature")
    assert is_flagship_venue("The Lancet")
    assert is_flagship_venue("lancet")               # missing "the"
    assert is_flagship_venue("Lancet (London, England)")  # PubMed-style suffix


def test_is_flagship_venue_rejects_non_flagship():
    assert not is_flagship_venue("Journal of Obscure Results")
    assert not is_flagship_venue(None)
    assert not is_flagship_venue("")


def test_every_known_journal_display_name_is_flagship():
    # every journal in the map must be recognized by its own display name
    for _, display in JOURNAL_SOURCES.values():
        assert is_flagship_venue(display)
