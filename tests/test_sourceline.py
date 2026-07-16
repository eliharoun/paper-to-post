from scripts.lib.sourceline import card_footer_line


def test_arxiv_uses_friendly_label_and_full_date():
    paper = {"source": "arxiv", "published_date": "2026-07-15",
             "updated_date": "2026-07-15T10:21:52"}
    assert card_footer_line(paper) == "arXiv · July 15, 2026"


def test_prefers_venue_over_source_label():
    paper = {"source": "pubmed", "venue": "Nature medicine",
             "published_date": "2026-07-15"}
    assert card_footer_line(paper) == "Nature medicine · July 15, 2026"


def test_full_date_includes_year_month_day():
    paper = {"source": "crossref", "venue": "Nature", "published_date": "2026-01-03"}
    assert card_footer_line(paper) == "Nature · January 3, 2026"


def test_datetime_updated_date_when_no_published_date():
    paper = {"source": "arxiv", "updated_date": "2026-07-15T10:21:52"}
    assert card_footer_line(paper) == "arXiv · July 15, 2026"


def test_missing_date_falls_back_to_source_only():
    paper = {"source": "arxiv"}
    assert card_footer_line(paper) == "arXiv"


def test_unknown_source_uses_raw_value():
    paper = {"source": "myrepo", "published_date": "2026-07-15"}
    assert card_footer_line(paper) == "myrepo · July 15, 2026"


def test_deterministic_across_calls():
    paper = {"source": "openalex", "venue": "Nature Communications",
             "published_date": "2026-07-15"}
    assert card_footer_line(paper) == card_footer_line(paper) == \
        "Nature Communications · July 15, 2026"
