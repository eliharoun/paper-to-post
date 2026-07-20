from pathlib import Path

from scripts.lib.bundle import compose_caption, final_image_order, ordered_card_paths


def test_compose_caption_keeps_link_when_present():
    caption = "A finding. Read the paper: https://arxiv.org/abs/2406.1 #ScienceNews"
    out = compose_caption(caption, "https://arxiv.org/abs/2406.1")
    assert out == caption  # unchanged; link already present


def test_compose_caption_appends_link_when_missing():
    caption = "A finding with no link. #ScienceNews"
    out = compose_caption(caption, "https://arxiv.org/abs/2406.1")
    assert "https://arxiv.org/abs/2406.1" in out
    assert out.startswith(caption)
    assert "Read the paper" in out


def test_compose_caption_noop_when_no_url():
    caption = "A finding. #ScienceNews"
    assert compose_caption(caption, "") == caption


def test_compose_caption_appends_hashtags_from_field():
    caption = "A finding with no link."
    out = compose_caption(caption, "https://arxiv.org/abs/2406.1",
                          hashtags=["AIresearch", "machinelearning"])
    assert "#AIresearch #machinelearning" in out
    # normalizes bare tags to #-prefixed
    assert "#AIresearch" in out and "AIresearch #" not in out.replace("#AIresearch", "")


def test_compose_caption_normalizes_and_dedupes_hashtags():
    # tags already inline in the caption prose must NOT be doubled
    caption = "A finding. #AIresearch already here."
    out = compose_caption(caption, "", hashtags=["#AIresearch", "LLM"])
    assert out.count("#AIresearch") == 1  # not duplicated
    assert "#LLM" in out


def test_compose_caption_no_hashtags_is_unchanged_behaviour():
    caption = "A finding."
    # None / empty list => no trailing hashtag block
    assert compose_caption(caption, "", hashtags=None) == caption
    assert compose_caption(caption, "", hashtags=[]) == caption


def test_ordered_card_paths_sorts_numerically(tmp_path):
    # create out-of-order files incl. double digits to prove numeric (not lexical) sort
    for name in ["card_02.jpg", "card_10.jpg", "card_01.jpg", "notes.txt"]:
        (tmp_path / name).write_bytes(b"x")
    paths = ordered_card_paths(tmp_path)
    assert [p.name for p in paths] == ["card_01.jpg", "card_02.jpg", "card_10.jpg"]


def test_final_image_order_inserts_screenshot_before_source(tmp_path):
    cards = [tmp_path / f"card_0{i}.jpg" for i in range(1, 5)]  # title..source (4)
    for c in cards:
        c.write_bytes(b"x")
    shot = tmp_path / "paper_page.jpg"
    shot.write_bytes(b"x")
    order = final_image_order(cards, shot)
    # screenshot goes second-to-last, source (last authored card) stays last
    assert order[-1] == cards[-1]
    assert order[-2] == shot
    assert len(order) == 5


def test_final_image_order_no_screenshot_unchanged(tmp_path):
    cards = [tmp_path / f"card_0{i}.jpg" for i in range(1, 4)]
    for c in cards:
        c.write_bytes(b"x")
    assert final_image_order(cards, None) == cards
    assert final_image_order(cards, Path(tmp_path / "missing.jpg")) == cards
