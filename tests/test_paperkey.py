from scripts.lib.models import PaperInput
from scripts.lib.paperkey import paper_key, paper_key_from_dict


def _p(**kw) -> PaperInput:
    base = dict(source="arxiv", source_id="x", title="T", url="https://x")
    base.update(kw)
    return PaperInput(**base)


def test_prefers_arxiv_id():
    assert paper_key(_p(arxiv_id="2406.00001", doi="10.1/x")) == "arxiv:2406.00001"


def test_falls_back_to_doi():
    assert paper_key(_p(doi="10.1/ABC")) == "doi:10.1/abc"  # doi lowercased


def test_falls_back_to_s2_then_source():
    assert paper_key(_p(semantic_scholar_id="s2abc")) == "s2:s2abc"
    assert paper_key(_p(source="openalex", source_id="W123")) == "openalex:W123"


def test_from_dict_matches_model_and_tolerates_missing_keys():
    # partial dict (no raw_payload etc.) must not raise
    assert paper_key_from_dict({"arxiv_id": "2406.1"}) == "arxiv:2406.1"
    assert paper_key_from_dict({"source": "x", "source_id": "s"}) == "x:s"
    p = _p(arxiv_id="2406.9")
    assert paper_key_from_dict(p.model_dump()) == paper_key(p)
