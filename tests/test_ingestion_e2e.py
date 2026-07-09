import json
from pathlib import Path

from scripts.fetch_arxiv import parse_arxiv_atom
from scripts.fetch_semantic_scholar import parse_s2_response
from scripts.normalize_dedupe import dedupe_papers

FIX = Path(__file__).parent / "fixtures"


def test_arxiv_and_s2_dedupe_into_one_for_shared_paper():
    arxiv = parse_arxiv_atom((FIX / "arxiv_response.xml").read_text())
    s2 = parse_s2_response(json.loads((FIX / "s2_response.json").read_text()))
    rows = [p.model_dump(mode="json") for p in (*arxiv, *s2)]
    merged = dedupe_papers(rows)

    # arxiv 2406.00001 and s2 s2aaa111 (ArXiv 2406.00001) collapse into one;
    # arxiv 2406.00002 and s2 s2bbb222 are distinct -> 3 total.
    assert len(merged) == 3
    # the shared paper kept the longer S2 abstract and gained citation_count + doi
    shared = next(p for p in merged if p.get("arxiv_id") == "2406.00001")
    assert shared["doi"] == "10.1234/abc"
    assert shared["citation_count"] == 3
    assert len(shared["abstract"]) > len("A short note.")


def test_biomed_sources_dedupe_by_doi():
    from scripts.lib.models import PaperInput
    from scripts.normalize_dedupe import dedupe_papers
    shared_doi = "10.1101/2026.06.28.111111"
    biorxiv = PaperInput(source="biorxiv", source_id=shared_doi, doi=shared_doi,
                         title="CRISPR Screen", url="https://biorxiv/x",
                         abstract="short", is_preprint=True).model_dump(mode="json")
    crossref = PaperInput(source="crossref", source_id=shared_doi, doi=shared_doi,
                          title="CRISPR Screen", url="https://doi.org/x",
                          abstract="a longer enriched abstract from crossref",
                          venue="Nature", citation_count=4).model_dump(mode="json")
    merged = dedupe_papers([biorxiv, crossref])
    assert len(merged) == 1
    m = merged[0]
    assert m["venue"] == "Nature"          # enrichment merged in
    assert m["citation_count"] == 4
    assert "enriched" in m["abstract"]     # longest abstract kept
    assert m["is_preprint"] is True        # preserved from biorxiv
