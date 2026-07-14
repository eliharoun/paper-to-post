from PIL import Image

from scripts.lib.config import load_brand_for_account

BRAND = load_brand_for_account("cs")


def test_composite_front_card_writes_correct_size(tmp_path):
    from scripts.lib.hero import composite_front_card
    hero_png = tmp_path / "hero.png"
    Image.new("RGB", (1200, 1500), (20, 30, 60)).save(hero_png, "PNG")
    out = tmp_path / "card_01.jpg"
    composite_front_card(
        hero_png_path=hero_png,
        headline="AI agents broke into vulnerable smart devices 95% of the time",
        brand=BRAND,
        out_path=out,
    )
    assert out.exists()
    img = Image.open(out)
    assert img.size == (BRAND.canvas_width * BRAND.render_scale,
                        BRAND.canvas_height * BRAND.render_scale)
    assert img.mode == "RGB"


def test_composite_front_card_handles_long_headline(tmp_path):
    from scripts.lib.hero import composite_front_card
    hero_png = tmp_path / "hero.png"
    Image.new("RGB", (1200, 1500), (10, 10, 10)).save(hero_png, "PNG")
    out = tmp_path / "card_01.jpg"
    composite_front_card(
        hero_png_path=hero_png,
        headline="Why quitting smoking lowers one lung cancer risk but not another",
        brand=BRAND,
        out_path=out,
    )
    img = Image.open(out)
    assert img.size == (BRAND.canvas_width * BRAND.render_scale,
                        BRAND.canvas_height * BRAND.render_scale)


def test_generate_image_returns_png_bytes(monkeypatch):
    """generate_image extracts inline image bytes from the Gemini response."""
    import io as _io

    import scripts.lib.hero as hero

    png = _io.BytesIO()
    Image.new("RGB", (64, 80), (1, 2, 3)).save(png, "PNG")
    png_bytes = png.getvalue()

    class _InlineData:
        data = png_bytes

    class _Part:
        inline_data = _InlineData()

    class _Content:
        parts = [_Part()]

    class _Candidate:
        content = _Content()

    class _Resp:
        candidates = [_Candidate()]

    class _Models:
        def generate_content(self, **kwargs):
            return _Resp()

    class _FakeClient:
        models = _Models()

    out = hero.generate_image("a glowing cell", model="fake-model",
                              client=_FakeClient(), aspect_ratio="4:5")
    assert out == png_bytes


def test_generate_image_raises_when_no_image(monkeypatch):
    import scripts.lib.hero as hero

    class _Part:
        inline_data = None

    class _Content:
        parts = [_Part()]

    class _Candidate:
        content = _Content()

    class _Resp:
        candidates = [_Candidate()]

    class _Models:
        def generate_content(self, **kwargs):
            return _Resp()

    class _FakeClient:
        models = _Models()

    import pytest
    with pytest.raises(hero.HeroImageError):
        hero.generate_image("x", model="fake", client=_FakeClient(), aspect_ratio="4:5",
                            retry_delay=0)
