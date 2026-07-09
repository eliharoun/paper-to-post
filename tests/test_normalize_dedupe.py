from scripts.lib.models import PaperInput
from scripts.normalize_dedupe import dedupe_papers


def _p(**kw) -> dict:
    base = dict(source="x", source_id="s", title="T", url="https://x")
    base.update(kw)
    return PaperInput(**base).model_dump(mode="json")


def test_dedupe_by_arxiv_id_merges_and_keeps_longest_abstract():
    a = _p(source="arxiv", arxiv_id="2406.1", url="http://arxiv.org/abs/2406.1",
           abstract="short")
    b = _p(source="semantic_scholar", arxiv_id="2406.1", semantic_scholar_id="s2x",
           doi="10.1/x", url="https://s2/x", abstract="a much longer abstract body")
    merged = dedupe_papers([a, b])
    assert len(merged) == 1
    m = merged[0]
    assert m["arxiv_id"] == "2406.1"
    assert m["semantic_scholar_id"] == "s2x"   # id unioned in
    assert m["doi"] == "10.1/x"
    assert m["abstract"] == "a much longer abstract body"  # longest kept
    assert m["url"] == "https://doi.org/10.1/x"   # DOI landing page preferred


def test_dedupe_by_title_hash_when_no_ids():
    a = _p(title="Attention Is All You Need [v1]", abstract="one")
    b = _p(title="attention is all you need", abstract="two longer abstract")
    merged = dedupe_papers([a, b])
    assert len(merged) == 1
    assert merged[0]["abstract"] == "two longer abstract"


def test_distinct_papers_are_kept():
    a = _p(arxiv_id="2406.1", title="Paper One")
    b = _p(arxiv_id="2406.2", title="Paper Two")
    assert len(dedupe_papers([a, b])) == 2
