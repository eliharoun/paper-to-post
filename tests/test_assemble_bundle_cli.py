import json
from pathlib import Path

from scripts.assemble_bundle import run
from scripts.lib.store import Ledger

FIX = Path(__file__).parent / "fixtures"


def _setup(tmp_path):
    # a validated post + its paper + two rendered card images
    post = json.loads((FIX / "good_post.json").read_text())
    paper = json.loads((FIX / "good_paper.json").read_text())
    (tmp_path / "post.json").write_text(json.dumps(post))
    (tmp_path / "paper.json").write_text(json.dumps(paper))
    assets = tmp_path / "assets"
    assets.mkdir()
    for i in (1, 2):
        (assets / f"card_0{i}.jpg").write_bytes(b"\xff\xd8\xff")  # fake jpeg bytes
    return post, paper, assets


def test_run_writes_full_bundle(tmp_path):
    post, paper, assets = _setup(tmp_path)
    out = tmp_path / "bundle"
    ledger = Ledger(tmp_path / "led.db")

    result = run(
        post_path=str(tmp_path / "post.json"),
        paper_path=str(tmp_path / "paper.json"),
        assets_dir=str(assets),
        out_dir=str(out),
        ledger=ledger,
        delivered_date="2026-07-01",
    )

    assert (out / "card_01.jpg").exists()
    assert (out / "card_02.jpg").exists()
    caption = (out / "caption.txt").read_text()
    assert paper["url"] in caption           # article link present
    assert (out / "alt_text.txt").read_text() == post["alt_text"]
    assert (out / "post.json").exists()
    assert (out / "selected_paper.json").exists()
    assert result["card_count"] == 2
    # paper recorded in ledger (never re-post)
    assert ledger.is_delivered("arxiv:2406.00001")


def test_caption_link_falls_back_to_source_url(tmp_path):
    # Field-drift guard: candidates use `url`, but if a paper only has `source_url`
    # the bundle must still guarantee the article link in the caption.
    _post, paper, assets = _setup(tmp_path)
    paper.pop("url", None)
    paper["source_url"] = "https://arxiv.org/abs/2406.99999"
    (tmp_path / "paper.json").write_text(json.dumps(paper))
    run(post_path=str(tmp_path / "post.json"), paper_path=str(tmp_path / "paper.json"),
        assets_dir=str(assets), out_dir=str(tmp_path / "b"),
        ledger=Ledger(tmp_path / "led.db"), delivered_date="2026-07-01")
    assert "https://arxiv.org/abs/2406.99999" in (tmp_path / "b" / "caption.txt").read_text()


def test_run_marks_ledger_with_paper_key(tmp_path):
    _setup(tmp_path)
    ledger = Ledger(tmp_path / "led.db")
    run(post_path=str(tmp_path / "post.json"), paper_path=str(tmp_path / "paper.json"),
        assets_dir=str(tmp_path / "assets"), out_dir=str(tmp_path / "b"),
        ledger=ledger, delivered_date="2026-07-01")
    assert "arxiv:2406.00001" in ledger.seen_keys()


def test_run_inserts_screenshot_second_to_last(tmp_path):
    _setup(tmp_path)  # assets has card_01 (title), card_02 (source)
    shot = tmp_path / "paper_page.jpg"
    shot.write_bytes(b"\xff\xd8\xff")
    out = tmp_path / "bundle"
    result = run(
        post_path=str(tmp_path / "post.json"), paper_path=str(tmp_path / "paper.json"),
        assets_dir=str(tmp_path / "assets"), out_dir=str(out),
        ledger=Ledger(tmp_path / "led.db"), delivered_date="2026-07-01",
        screenshot_path=str(shot),
    )
    # 2 authored cards + screenshot = 3, renumbered; screenshot is card_02 (second-to-last)
    assert result["card_count"] == 3
    assert {"card_01.jpg", "card_02.jpg", "card_03.jpg"} <= set(result["cards"])
