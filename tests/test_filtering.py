from datetime import date, timedelta

from scripts.lib.config import load_topics
from scripts.lib.filtering import (
    assign_topic,
    hard_filter_reasons,
    rule_score,
)

TOPICS = load_topics("config/topics.yml")
TODAY = date(2026, 7, 1)


# --- assign_topic ---

def test_assign_topic_arxiv_category():
    paper = {"source": "arxiv", "arxiv_id": "2406.1",
             "raw_payload": {}, "field_of_study": None, "title": "X",
             "arxiv_categories": ["cs.LG"]}
    assert assign_topic(paper, TOPICS) == "swe_ml_ai"


def test_assign_topic_by_field_of_study():
    paper = {"source": "pubmed", "field_of_study": "Biology",
             "title": "Cancer genomics study", "arxiv_categories": []}
    assert assign_topic(paper, TOPICS) == "bio_genetics_biomed"


def test_assign_topic_by_title_keyword_bio():
    paper = {"source": "crossref", "field_of_study": None,
             "title": "A CRISPR genomics screen in tumor cells", "arxiv_categories": []}
    assert assign_topic(paper, TOPICS) == "bio_genetics_biomed"


def test_assign_topic_none_when_unmatched():
    paper = {"source": "crossref", "field_of_study": "History",
             "title": "Medieval trade routes", "arxiv_categories": []}
    assert assign_topic(paper, TOPICS) is None


# --- hard_filter_reasons ---

GOOD = {
    "title": "A Real Paper About Machine Learning Systems",
    "abstract": "x" * 500,
    "arxiv_id": "2406.1",
    "topic_id": "swe_ml_ai",
}


def test_hard_filter_passes_good_paper():
    assert hard_filter_reasons(dict(GOOD), TOPICS) == []


def test_hard_filter_rejects_missing_title():
    p = dict(GOOD, title="")
    assert "no_title" in hard_filter_reasons(p, TOPICS)


def test_hard_filter_rejects_short_abstract():
    p = dict(GOOD, abstract="too short")
    assert "abstract_too_short" in hard_filter_reasons(p, TOPICS)


def test_hard_filter_rejects_missing_abstract():
    p = dict(GOOD, abstract=None)
    assert "no_abstract" in hard_filter_reasons(p, TOPICS)


def test_hard_filter_rejects_no_topic():
    p = dict(GOOD, topic_id=None)
    assert "no_topic" in hard_filter_reasons(p, TOPICS)


def test_hard_filter_rejects_correction_erratum():
    p = dict(GOOD, title="Erratum: A Real Paper About Machine Learning")
    assert "correction_or_erratum" in hard_filter_reasons(p, TOPICS)


def test_hard_filter_rejects_hard_excluded_term():
    p = dict(GOOD, topic_id="bio_genetics_biomed",
             title="A Case Report of a Rare Genomic Variant",
             abstract="x" * 500)
    assert any(r.startswith("hard_exclude:") for r in hard_filter_reasons(p, TOPICS))


# --- rule_score ---

def _scored(**over) -> float:
    base = {
        "title": "Machine Learning for Systems",
        "abstract": "x" * 800,
        "arxiv_id": "2406.1",
        "topic_id": "swe_ml_ai",
        "published_date": TODAY.isoformat(),
        "pdf_url": "https://x/y.pdf",
        "citation_count": 0,
    }
    base.update(over)
    return rule_score(base, TOPICS, today=TODAY)


def test_rule_score_in_range():
    assert 0 <= _scored() <= 100


def test_recent_scores_higher_than_old():
    recent = _scored(published_date=TODAY.isoformat())
    old = _scored(published_date=(TODAY - timedelta(days=10)).isoformat())
    assert recent > old


def test_higher_priority_topic_scores_higher():
    ai = _scored(topic_id="swe_ml_ai")             # priority 1.0
    bio = _scored(topic_id="bio_genetics_biomed")  # priority 0.9
    assert ai > bio


def test_hype_title_penalized():
    plain = _scored(title="A Study of Protein Folding Methods")
    hype = _scored(title="A Miracle Breakthrough That Is Guaranteed To Work")
    assert hype < plain


def test_missing_ids_scores_lower():
    with_id = _scored(arxiv_id="2406.1", doi=None)
    without = _scored(arxiv_id=None, doi=None)
    assert with_id > without


def test_flagship_venue_scores_higher():
    # A brand-new Nature paper (0 citations) should outrank the same paper in an
    # unknown venue — that's the whole point of the prestige bonus.
    flagship = _scored(topic_id="bio_genetics_biomed", venue="Nature")
    obscure = _scored(topic_id="bio_genetics_biomed", venue="Journal of Obscure Results")
    assert flagship > obscure


def test_flagship_venue_matches_pubmed_style_name():
    # PubMed spells it "Lancet (London, England)"; the bonus must still apply.
    assert _scored(venue="Lancet (London, England)") > _scored(venue="Some Other Journal")
