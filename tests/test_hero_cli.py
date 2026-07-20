import io
import json

from PIL import Image


def _write_post(tmp_path, prompt="a glowing cell"):
    post = {
        "paper_id": "x", "source_title": "t", "source_url": "https://e.com",
        "is_preprint": True, "plain_english_headline": "A short punchy headline",
        "one_sentence_summary": "s", "why_it_matters": "w", "what_they_did": "d",
        "what_they_found": "f", "important_context": "c", "limitations": ["l"],
        "avoid_saying": ["a"],
        "carousel_cards": [{"card_number": 1, "card_type": "title",
                            "heading": "H", "body": "", "footer": ""}],
        "caption": "cap", "hashtags": ["#x"], "alt_text": "alt", "confidence": "high",
    }
    if prompt is not None:
        post["hero_image_prompt"] = prompt
    p = tmp_path / "post.json"
    p.write_text(json.dumps(post))
    return p


def _fake_png_bytes():
    b = io.BytesIO()
    Image.new("RGB", (1200, 1500), (30, 40, 60)).save(b, "PNG")
    return b.getvalue()


def test_cli_writes_card_01_on_success(tmp_path, monkeypatch):
    import scripts.render_hero as rh
    monkeypatch.setattr(rh.hero, "build_client", lambda: object())
    monkeypatch.setattr(rh.hero, "generate_image", lambda *a, **k: _fake_png_bytes())

    post = _write_post(tmp_path)
    assets = tmp_path / "assets"
    rc = rh.main(["--post", str(post), "--out", str(assets), "--account", "cs",
                  "--hero-out", str(tmp_path / "hero.png")])
    assert rc == 0
    assert (assets / "card_01.jpg").exists()
    assert (tmp_path / "hero.png").exists()


def test_cli_exits_nonzero_when_prompt_missing(tmp_path, monkeypatch):
    import scripts.render_hero as rh
    monkeypatch.setattr(rh.hero, "build_client", lambda: object())
    post = _write_post(tmp_path, prompt=None)
    rc = rh.main(["--post", str(post), "--out", str(tmp_path / "assets"), "--account", "cs"])
    assert rc != 0
    assert not (tmp_path / "assets" / "card_01.jpg").exists()


def test_cli_exits_nonzero_on_generation_error(tmp_path, monkeypatch):
    import scripts.render_hero as rh
    monkeypatch.setattr(rh.hero, "build_client", lambda: object())

    def _boom(*a, **k):
        raise rh.hero.HeroImageError("api down")

    monkeypatch.setattr(rh.hero, "generate_image", _boom)
    post = _write_post(tmp_path)
    rc = rh.main(["--post", str(post), "--out", str(tmp_path / "assets"), "--account", "cs"])
    assert rc != 0
    assert not (tmp_path / "assets" / "card_01.jpg").exists()


def test_cli_uses_title_card_heading_not_plain_english_headline(tmp_path, monkeypatch):
    """The hero front card must render the title card's heading (the field crafted
    per headline-style-guide), not plain_english_headline — so hero and motif front
    cards show identical wording."""
    import scripts.render_hero as rh
    seen = {}

    monkeypatch.setattr(rh.hero, "build_client", lambda: object())
    monkeypatch.setattr(rh.hero, "generate_image", lambda *a, **k: _fake_png_bytes())

    def _capture(*, hero_png_path, headline, brand, out_path, **kwargs):
        seen["headline"] = headline
        return out_path

    monkeypatch.setattr(rh.hero, "composite_front_card", _capture)
    post = _write_post(tmp_path)  # title heading "H" != plain_english_headline
    rc = rh.main(["--post", str(post), "--out", str(tmp_path / "assets"),
                  "--account", "cs", "--hero-out", str(tmp_path / "hero.png")])
    assert rc == 0
    assert seen["headline"] == "H"


def test_title_heading_falls_back_to_plain_english_headline():
    from scripts.render_hero import _title_heading
    # no title card present -> fall back
    post = {"plain_english_headline": "fallback",
            "carousel_cards": [{"card_number": 1, "card_type": "hook", "heading": "Q"}]}
    assert _title_heading(post) == "fallback"
    # title card present -> use its heading
    post2 = {"plain_english_headline": "fallback",
             "carousel_cards": [{"card_number": 1, "card_type": "title", "heading": "Real"}]}
    assert _title_heading(post2) == "Real"


def test_cli_concept_override_used(tmp_path, monkeypatch):
    import scripts.render_hero as rh
    seen = {}

    def _capture(concept, **k):
        seen["concept"] = concept
        return _fake_png_bytes()

    monkeypatch.setattr(rh.hero, "build_client", lambda: object())
    monkeypatch.setattr(rh.hero, "generate_image", _capture)
    post = _write_post(tmp_path, prompt="from-json")
    rc = rh.main(["--post", str(post), "--out", str(tmp_path / "assets"),
                  "--account", "cs", "--concept", "from-cli",
                  "--hero-out", str(tmp_path / "hero.png")])
    assert rc == 0
    assert seen["concept"] == "from-cli"
