import fitz  # pymupdf
from PIL import Image

from scripts.screenshot_page1 import (
    card1_is_eligible,
    pdf_url_for,
    render_card1_from_pdf_bytes,
)


def _paper(**over):
    base = {"source": "arxiv", "arxiv_id": "2406.1", "is_open_access": True,
            "license": None, "pdf_url": None, "doi": None}
    base.update(over)
    return base


# --- gating ---

def test_arxiv_paper_is_eligible():
    assert card1_is_eligible(_paper(arxiv_id="2406.1")) is True


def test_open_access_with_pdf_is_eligible():
    assert card1_is_eligible(
        _paper(arxiv_id=None, is_open_access=True, pdf_url="https://x/y.pdf")
    ) is True


def test_non_oa_without_arxiv_is_not_eligible():
    assert card1_is_eligible(
        _paper(arxiv_id=None, is_open_access=False, pdf_url="https://paywall/y.pdf")
    ) is False


def test_unknown_oa_non_arxiv_is_not_eligible():
    assert card1_is_eligible(
        _paper(arxiv_id=None, is_open_access=None, pdf_url="https://x/y.pdf")
    ) is False


def test_cc_license_still_eligible():
    assert card1_is_eligible(
        _paper(arxiv_id=None, is_open_access=True, pdf_url="https://x/y.pdf",
               license="cc-by-nc-nd")
    ) is True


def test_all_rights_reserved_blocks():
    assert card1_is_eligible(
        _paper(arxiv_id=None, is_open_access=True, pdf_url="https://x/y.pdf",
               license="all rights reserved")
    ) is False


def test_pdf_url_prefers_explicit_then_arxiv():
    assert pdf_url_for(_paper(pdf_url="https://x/y.pdf")) == "https://x/y.pdf"
    assert pdf_url_for(_paper(pdf_url=None, arxiv_id="2406.1")) == "https://arxiv.org/pdf/2406.1"
    assert pdf_url_for(_paper(pdf_url=None, arxiv_id=None)) is None


# --- rasterize ---

def _tiny_pdf_bytes() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)  # US Letter portrait
    page.insert_text((72, 100), "Sample Paper Title")
    return doc.tobytes()


def test_render_card1_from_pdf_bytes_produces_canvas(tmp_path):
    out = tmp_path / "card_01.jpg"
    ok = render_card1_from_pdf_bytes(_tiny_pdf_bytes(), out, canvas_w=1080,
                                     canvas_h=1350, bg="#0F172A", scale=2)
    assert ok is True
    img = Image.open(out)
    assert img.size == (1080 * 2, 1350 * 2)  # physical size at 2x


def test_render_card1_from_bad_bytes_returns_false(tmp_path):
    out = tmp_path / "card_01.jpg"
    ok = render_card1_from_pdf_bytes(b"not a pdf", out, canvas_w=1080,
                                     canvas_h=1350, bg="#000000", scale=1)
    assert ok is False
    assert not out.exists()
