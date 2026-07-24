from scripts.lib.sourceline import card_footer_line


def test_arxiv_with_category_and_full_date():
    paper = {"source": "arxiv", "field_of_study": "cs.LG",
             "published_date": "2026-07-15", "updated_date": "2026-07-15T10:21:52"}
    assert card_footer_line(paper) == "arXiv · Machine Learning · July 15, 2026"


def test_prefers_venue_over_source_label():
    paper = {"source": "pubmed", "venue": "Nature medicine",
             "field_of_study": "Immunology", "published_date": "2026-07-15"}
    assert card_footer_line(paper) == "Nature medicine · Immunology · July 15, 2026"


def test_venue_slug_is_normalized_not_shown_raw():
    # Some feeds set venue to the source slug (e.g. 'biorxiv'); it must render as
    # the friendly source label, never a bare lowercase slug.
    paper = {"source": "biorxiv", "venue": "biorxiv",
             "field_of_study": "bioengineering", "published_date": "2026-07-18"}
    assert card_footer_line(paper) == "bioRxiv · Bioengineering · July 18, 2026"


def test_unknown_field_of_study_is_title_cased():
    paper = {"source": "crossref", "field_of_study": "quantum_information",
             "published_date": "2026-01-03"}
    assert card_footer_line(paper) == "Crossref · Quantum Information · January 3, 2026"


def test_full_date_includes_year_month_day():
    paper = {"source": "crossref", "venue": "Nature", "published_date": "2026-01-03"}
    assert card_footer_line(paper) == "Nature · January 3, 2026"


def test_datetime_updated_date_when_no_published_date():
    paper = {"source": "arxiv", "updated_date": "2026-07-15T10:21:52"}
    assert card_footer_line(paper) == "arXiv · July 15, 2026"


def test_missing_category_and_date_falls_back_to_source_only():
    paper = {"source": "arxiv"}
    assert card_footer_line(paper) == "arXiv"


def test_missing_date_keeps_source_and_category():
    paper = {"source": "arxiv", "field_of_study": "cs.CL"}
    assert card_footer_line(paper) == "arXiv · Natural Language Processing"


def test_unknown_source_uses_raw_value():
    paper = {"source": "myrepo", "published_date": "2026-07-15"}
    assert card_footer_line(paper) == "myrepo · July 15, 2026"


def test_deterministic_across_calls():
    paper = {"source": "openalex", "venue": "Nature Communications",
             "field_of_study": "cs.CV", "published_date": "2026-07-15"}
    assert card_footer_line(paper) == card_footer_line(paper) == \
        "Nature Communications · Computer Vision · July 15, 2026"
