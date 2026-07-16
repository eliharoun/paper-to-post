from scripts.lib.trends.base import _paper_id, text_terms


def test_unigrams_and_bigrams():
    terms = text_terms("Large Language Systems", "reason over text")
    assert "large" in terms
    assert "large language" in terms          # adjacent bigram
    assert "language systems" in terms


def test_stopwords_and_short_tokens_dropped():
    terms = text_terms("A study of the novel method", "")
    assert "of" not in terms and "the" not in terms and "a" not in terms
    # generic academic stopwords are dropped
    assert "study" not in terms and "novel" not in terms and "method" not in terms


def test_extra_stopwords_applied():
    terms = text_terms("diffusion transformer", "", extra_stopwords={"diffusion"})
    assert "diffusion" not in terms
    assert "transformer" in terms


def test_two_letter_acronyms_kept():
    terms = text_terms("AI and ML models", "")
    assert "ai" in terms
    assert "ml" in terms


def test_no_cross_seam_bigrams():
    terms = text_terms("alpha beta", "gamma delta")
    assert "alpha beta" in terms
    assert "gamma delta" in terms
    assert "beta gamma" not in terms


def test_non_english_title_dropped_by_alpha_ratio():
    # <60% ASCII letters in title -> no terms extracted from this doc
    terms = text_terms("深層学習 ネットワーク モデル 研究", "")
    assert terms == set()


def test_non_english_title_with_english_abstract_dropped():
    # Title-only guard: a non-English title voids the whole doc even if the
    # abstract is English.
    terms = text_terms("深層学習 ネットワーク モデル 研究", "deep learning networks")
    assert terms == set()


def test_numbers_and_symbols_dropped():
    terms = text_terms("GPT 4o scores 92 on tests", "")
    assert "92" not in terms and "4o" not in terms
    assert "scores" in terms or "tests" in terms


def test_paper_id_prefers_arxiv_then_doi_then_source_id():
    assert _paper_id({"arxiv_id": "2607.1", "doi": "10.x"}) == "2607.1"
    assert _paper_id({"doi": "10.x/y"}) == "10.x/y"
    assert _paper_id({"source_id": "s1"}) == "s1"
    # no stable id -> falls back to object identity (a string)
    got = _paper_id({"title": "t"})
    assert isinstance(got, str) and got
    # empty-string id is skipped by the or-chain
    assert _paper_id({"arxiv_id": "", "doi": "10.x"}) == "10.x"
