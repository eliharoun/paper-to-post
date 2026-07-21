import json
from pathlib import Path

from scripts.build_roundup import build_roundup_post, collect_week_entries
from scripts.lib.config import load_brand_for_account
from scripts.lib.validation import check_hype, check_lengths, check_schema, check_style

BRAND = load_brand_for_account("cs")


def _entry(headline, summary, url):
    return {"headline": headline, "takeaway": summary, "source_url": url}


def test_build_roundup_shapes_a_valid_carousel():
    entries = [
        _entry("Model X beats Y on Z", "It cut error 30%.", "https://arxiv.org/abs/1"),
        _entry("A new dataset for W", "500k labeled samples.", "https://arxiv.org/abs/2"),
        _entry("Faster inference trick", "2x speedup, same accuracy.", "https://arxiv.org/abs/3"),
    ]
    post = build_roundup_post(entries, title="3 CS papers you missed this week",
                              account="cs")
    # first card is the title, then one per entry, then a source/outro card
    assert post["carousel_cards"][0]["card_type"] == "title"
    assert post["carousel_cards"][-1]["card_type"] == "source"
    assert len(post["carousel_cards"]) == 3 + 2  # title + 3 items + source
    # schema + safety checks pass (roundup reuses the standard render path)
    errors, parsed = check_schema(post, BRAND)
    assert errors == [] and parsed is not None
    assert check_hype(parsed) == []
    assert check_lengths(parsed, BRAND) == []
    assert check_style(parsed) == []


def test_roundup_caps_to_max_entries():
    entries = [_entry(f"Paper {i}", f"Finding {i}.", f"https://x/{i}") for i in range(10)]
    post = build_roundup_post(entries, title="Weekly roundup", account="cs", max_entries=5)
    # title + 5 items + source = 7 (within brand max_cards)
    assert len(post["carousel_cards"]) == 7


def test_roundup_caption_lists_all_links():
    entries = [
        _entry("A", "x.", "https://arxiv.org/abs/1"),
        _entry("B", "y.", "https://arxiv.org/abs/2"),
    ]
    post = build_roundup_post(entries, title="Roundup", account="cs")
    for e in entries:
        assert e["source_url"] in post["caption"]


def test_collect_week_entries_reads_recent_posts(tmp_path):
    # Build a fake outputs tree: outputs/<date>/cs/postN/post.json
    root = tmp_path / "outputs"
    good = json.loads((Path("tests/fixtures/good_post.json")).read_text())
    for d, n in [("2026-07-18", 1), ("2026-07-19", 1), ("2026-07-19", 2)]:
        pd = root / d / "cs" / f"post{n}"
        pd.mkdir(parents=True, exist_ok=True)
        (pd / "post.json").write_text(json.dumps(good))
    entries = collect_week_entries(str(root), account="cs", dates=["2026-07-18", "2026-07-19"])
    assert len(entries) == 3
    assert all("headline" in e and "source_url" in e for e in entries)
