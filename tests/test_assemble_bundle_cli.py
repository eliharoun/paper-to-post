import json
from pathlib import Path

import pytest

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


def test_run_aborts_on_empty_assets_without_marking_ledger(tmp_path):
    # If render produced no cards (empty assets dir), the bundle must NOT be written
    # and the paper must NOT be marked delivered — otherwise the paper is burned
    # from the pool with a broken (0-card) bundle that can never be re-posted.
    post, paper, _assets = _setup(tmp_path)
    empty = tmp_path / "empty_assets"
    empty.mkdir()
    ledger = Ledger(tmp_path / "led.db")
    with pytest.raises(ValueError, match="no cards"):
        run(
            post_path=str(tmp_path / "post.json"),
            paper_path=str(tmp_path / "paper.json"),
            assets_dir=str(empty),
            out_dir=str(tmp_path / "bundle"),
            ledger=ledger,
            delivered_date="2026-07-01",
        )
    # paper stays re-postable
    assert not ledger.is_delivered("arxiv:2406.00001")


def test_ledger_marked_only_after_manifest_written(tmp_path):
    # Data-loss guard: if mark_delivered runs before the manifest is written, a
    # crash between them burns the paper with no usable bundle. Assert the manifest
    # exists at the moment the ledger records the paper, by failing the ledger write
    # and confirming the manifest is already on disk.
    _setup(tmp_path)
    out = tmp_path / "bundle"

    class ExplodingLedger(Ledger):
        def mark_delivered(self, *a, **k):
            # At the point of recording delivery, the full bundle must already exist.
            assert (out / "bundle_manifest.json").exists(), \
                "ledger marked before manifest written (crash here would burn the paper)"
            raise RuntimeError("boom")

    ledger = ExplodingLedger(tmp_path / "led.db")
    with pytest.raises(RuntimeError, match="boom"):
        run(
            post_path=str(tmp_path / "post.json"),
            paper_path=str(tmp_path / "paper.json"),
            assets_dir=str(tmp_path / "assets"),
            out_dir=str(out),
            ledger=ledger,
            delivered_date="2026-07-01",
        )


def test_run_without_paper_bundles_a_roundup(tmp_path):
    # A roundup has no single paper: run() must accept paper_path=None, skip the
    # selected_paper.json write and the ledger mark, and still produce a valid bundle
    # (caption from post["caption"], cards copied, manifest written).
    post, _paper, assets = _setup(tmp_path)
    post["caption"] = "5 papers you missed.\n\n📄 https://arxiv.org/abs/1"
    (tmp_path / "post.json").write_text(json.dumps(post))
    out = tmp_path / "roundup"
    ledger = Ledger(tmp_path / "led.db")

    result = run(
        post_path=str(tmp_path / "post.json"),
        paper_path=None,
        assets_dir=str(assets),
        out_dir=str(out),
        ledger=ledger,
        delivered_date="2026-07-24",
    )
    assert (out / "card_01.jpg").exists()
    assert (out / "caption.txt").read_text().startswith("5 papers you missed")
    assert (out / "post.json").exists()
    assert not (out / "selected_paper.json").exists()   # no paper to write
    assert result["card_count"] == 2
    assert result.get("paper_key") is None
    assert ledger.seen_keys() == set()                  # nothing marked delivered


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
