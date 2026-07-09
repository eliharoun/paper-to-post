from PIL import Image

from scripts.lib.imageutil import assert_dimensions, fit_onto_canvas


def test_fit_onto_canvas_produces_exact_size():
    src = Image.new("RGB", (800, 1000), "white")
    out = fit_onto_canvas(src, canvas_w=1080, canvas_h=1350, bg="#0F172A")
    assert out.size == (1080, 1350)
    assert out.mode == "RGB"


def test_fit_onto_canvas_preserves_aspect_no_crop():
    # a very wide source must be letterboxed, not stretched
    src = Image.new("RGB", (2000, 500), "white")
    out = fit_onto_canvas(src, canvas_w=1080, canvas_h=1350, bg="#000000")
    assert out.size == (1080, 1350)
    # top-left corner should be background (letterbox)
    assert out.getpixel((5, 5)) == (0, 0, 0)


def test_assert_dimensions_ok_and_raises():
    img = Image.new("RGB", (1080, 1350))
    assert_dimensions(img, 1080, 1350)  # no raise
    bad = Image.new("RGB", (100, 100))
    try:
        assert_dimensions(bad, 1080, 1350)
        raise AssertionError("should have raised")
    except ValueError:
        pass
