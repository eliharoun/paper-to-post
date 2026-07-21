from PIL import Image

from scripts.render_grid_preview import build_mosaic, center_crop, find_front_cards


def test_center_crop_to_ratio():
    img = Image.new("RGB", (1080, 1350))  # 4:5
    out = center_crop(img, ratio=1.0)     # square grid cell
    assert out.width == out.height == 1080  # crops height to match width


def test_center_crop_wider_ratio():
    img = Image.new("RGB", (1000, 2000))
    out = center_crop(img, ratio=0.8)  # 4:5 target (w/h)
    # target height for width 1000 at ratio 0.8 = 1250
    assert out.size == (1000, 1250)


def test_build_mosaic_lays_out_grid(tmp_path):
    imgs = [Image.new("RGB", (300, 375), (i * 20, 0, 0)) for i in range(9)]
    mosaic = build_mosaic(imgs, cols=3, cell=200, gap=6, ratio=0.8)
    # 3 cols, 3 rows of 200x250 cells + gaps
    assert mosaic.width == 3 * 200 + 4 * 6
    rows = 3
    assert mosaic.height == rows * 250 + (rows + 1) * 6


def test_build_mosaic_handles_partial_last_row():
    imgs = [Image.new("RGB", (300, 375)) for _ in range(4)]  # 2 rows (3 + 1)
    mosaic = build_mosaic(imgs, cols=3, cell=100, gap=4, ratio=1.0)
    assert mosaic.height == 2 * 100 + 3 * 4


def test_find_front_cards_globs_recent(tmp_path):
    root = tmp_path / "outputs"
    for d, n in [("2026-07-18", 1), ("2026-07-19", 1), ("2026-07-19", 2)]:
        pd = root / d / "cs" / f"post{n}"
        pd.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (108, 135)).save(pd / "card_01.jpg")
    cards = find_front_cards(str(root), account="cs", limit=9)
    assert len(cards) == 3
    # newest first (2026-07-19 before 2026-07-18)
    assert "2026-07-19" in str(cards[0])
