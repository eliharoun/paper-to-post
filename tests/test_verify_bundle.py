import json
from pathlib import Path

from scripts.assemble_bundle import run
from scripts.lib.store import Ledger
from scripts.verify_bundle import verify

FIX = Path(__file__).parent / "fixtures"


def _make_bundle(tmp_path, *, n_cards=2, screenshot=False):
    """Build a real delivered bundle via assemble_bundle.run and return its dir."""
    post = json.loads((FIX / "good_post.json").read_text())
    paper = json.loads((FIX / "good_paper.json").read_text())
    (tmp_path / "post.json").write_text(json.dumps(post))
    (tmp_path / "paper.json").write_text(json.dumps(paper))
    assets = tmp_path / "assets"
    assets.mkdir()
    for i in range(1, n_cards + 1):
        (assets / f"card_{i:02d}.jpg").write_bytes(b"\xff\xd8\xff")
    shot = None
    if screenshot:
        shot = tmp_path / "paper_page.jpg"
        shot.write_bytes(b"\xff\xd8\xff")
    out = tmp_path / "post1"
    run(
        post_path=str(tmp_path / "post.json"), paper_path=str(tmp_path / "paper.json"),
        assets_dir=str(assets), out_dir=str(out),
        ledger=Ledger(tmp_path / "led.db"), delivered_date="2026-07-01",
        screenshot_path=str(shot) if shot else None,
    )
    return out


def test_complete_bundle_passes(tmp_path):
    out = _make_bundle(tmp_path, n_cards=5)
    result = verify(out)
    assert result["ok"], result["errors"]
    assert result["card_count"] == 5


def test_bundle_with_screenshot_allows_one_over_authored_max(tmp_path):
    # brand max_cards is 7; a delivered bundle may hold 8 with the inserted screenshot.
    out = _make_bundle(tmp_path, n_cards=7, screenshot=True)
    result = verify(out, account="cs")
    assert result["ok"], result["errors"]
    assert result["card_count"] == 8


def test_missing_dir_fails(tmp_path):
    result = verify(tmp_path / "post_never_ran")
    assert not result["ok"]
    assert any("missing" in e for e in result["errors"])


def test_dead_subagent_empty_dir_fails(tmp_path):
    # The real failure mode: an agent stopped after 0 tool uses, so only an empty
    # run/ dir exists and no bundle artifacts were ever written.
    dead = tmp_path / "post_dead"
    (dead / "run").mkdir(parents=True)
    result = verify(dead)
    assert not result["ok"]
    assert any("bundle_manifest.json missing" in e for e in result["errors"])
    assert any("no card_NN.jpg" in e for e in result["errors"])


def test_missing_manifest_fails(tmp_path):
    out = _make_bundle(tmp_path, n_cards=5)
    (out / "bundle_manifest.json").unlink()
    result = verify(out)
    assert not result["ok"]
    assert any("bundle_manifest.json missing" in e for e in result["errors"])


def test_caption_without_link_fails(tmp_path):
    out = _make_bundle(tmp_path, n_cards=5)
    (out / "caption.txt").write_text("a caption with no article link")
    result = verify(out)
    assert not result["ok"]
    assert any("paper link" in e for e in result["errors"])


def test_non_contiguous_cards_fail(tmp_path):
    out = _make_bundle(tmp_path, n_cards=5)
    (out / "card_03.jpg").unlink()  # leaves 1,2,4,5
    result = verify(out)
    assert not result["ok"]
    assert any("contiguous" in e for e in result["errors"])
