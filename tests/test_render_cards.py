import json
from pathlib import Path

import pytest
from PIL import Image

from scripts.lib.config import load_brand_for_account

BRAND = load_brand_for_account("cs")
GOOD_POST = json.loads((Path(__file__).parent / "fixtures" / "good_post.json").read_text())


def test_resolve_footer_skips_title_and_source_cards():
    # The auto footer appears on content cards only: the opening title/hero card
    # and the closing source card get no footer; cards between them show the
    # deterministic 'Source · Category · Date' line from the paper.
    from templates.render import _resolve_footer
    paper = {"source": "arxiv", "field_of_study": "cs.LG",
             "published_date": "2026-07-15"}
    assert _resolve_footer({"card_type": "title"}, paper) == ""
    assert _resolve_footer({"card_type": "source"}, paper) == ""
    assert _resolve_footer({"card_type": "finding"}, paper) == \
        "arXiv · Machine Learning · July 15, 2026"


def test_resolve_footer_falls_back_to_authored_when_no_paper():
    from templates.render import _resolve_footer
    assert _resolve_footer({"card_type": "finding", "footer": "authored"}, None) == "authored"


def test_render_raises_when_no_cards_match_start_index(tmp_path):
    # If start_index skips every card (or carousel_cards is empty), the render must
    # raise rather than return [] with exit 0 — an empty render otherwise flows into
    # an empty (broken) bundle that still gets marked delivered.
    from templates.render import render_text_cards
    with pytest.raises(ValueError, match="no cards"):
        render_text_cards(GOOD_POST, BRAND, out_dir=tmp_path, start_index=99)


def test_render_raises_on_empty_carousel(tmp_path):
    from templates.render import render_text_cards
    with pytest.raises(ValueError, match="no cards"):
        render_text_cards({"carousel_cards": []}, BRAND, out_dir=tmp_path)


@pytest.mark.browser
def test_render_text_cards_writes_correct_size(tmp_path):
    from templates.render import render_text_cards
    paths = render_text_cards(GOOD_POST, BRAND, out_dir=tmp_path, start_index=2)
    # good_post has 6 cards; start_index=2 renders cards 2..6 => 5 files
    assert len(paths) == 5
    for p in paths:
        img = Image.open(p)
        assert img.size == (BRAND.canvas_width * BRAND.render_scale,
                            BRAND.canvas_height * BRAND.render_scale)
        assert img.mode == "RGB"


@pytest.mark.browser
def test_render_all_cards_from_index_1(tmp_path):
    from templates.render import render_text_cards
    paths = render_text_cards(GOOD_POST, BRAND, out_dir=tmp_path, start_index=1)
    assert len(paths) == 6
    assert paths[0].name == "card_01.jpg"


@pytest.mark.browser
def test_render_title_card_over_motif(tmp_path):
    from templates.render import render_text_cards
    post = {"carousel_cards": [
        {"card_number": 1, "card_type": "title",
         "heading": "A bold title over the motif", "body": "", "footer": "arXiv · 2026"},
    ]}
    paths = render_text_cards(post, BRAND, out_dir=tmp_path, start_index=1)
    assert len(paths) == 1
    img = Image.open(paths[0])
    assert img.size == (BRAND.canvas_width * BRAND.render_scale,
                        BRAND.canvas_height * BRAND.render_scale)
    assert img.mode == "RGB"
