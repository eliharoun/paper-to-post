from datetime import date

from scripts.lib.models import CarouselCard, GeneratedPost, PaperInput


def test_paper_input_minimal():
    p = PaperInput(source="arxiv", source_id="2406.1", title="T", url="https://x")
    assert p.authors == []
    assert p.abstract is None


def test_paper_input_full():
    p = PaperInput(
        source="arxiv", source_id="2406.1", title="T", url="https://x",
        abstract="a" * 500, published_date=date(2026, 6, 30),
        arxiv_id="2406.1", is_preprint=True, is_open_access=True,
    )
    assert p.is_preprint and p.is_open_access


def test_generated_post_roundtrip():
    post = GeneratedPost(
        paper_id="p1", source_title="T", source_url="https://x", is_preprint=True,
        plain_english_headline="H", one_sentence_summary="S", why_it_matters="W",
        what_they_did="D", what_they_found="F", important_context="C",
        limitations=["small sample"], avoid_saying=["cure"],
        carousel_cards=[CarouselCard(card_number=1, card_type="hook",
                                     heading="H", body="B", footer="f")],
        caption="cap", hashtags=["#ScienceNews"], alt_text="alt", confidence="medium",
    )
    dumped = post.model_dump()
    assert GeneratedPost(**dumped).carousel_cards[0].card_type == "hook"
