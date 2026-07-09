import fitz  # pymupdf

from scripts.lib.pdf import extract_text_from_pdf_bytes, pdf_url_for
from scripts.paper_text import paper_text


def _pdf_from_lines(lines: list[str]) -> bytes:
    """Build a PDF from short lines that fit the page width (insert_text won't wrap)."""
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    y = 72
    for line in lines:
        if y > 760:  # new page when full
            page = doc.new_page(width=612, height=792)
            y = 72
        page.insert_text((72, y), line[:70])  # keep within page width
        y += 14
    return doc.tobytes()


def test_pdf_url_for_prefers_explicit_then_arxiv():
    assert pdf_url_for({"pdf_url": "https://x/y.pdf"}) == "https://x/y.pdf"
    assert pdf_url_for({"arxiv_id": "2406.1"}) == "https://arxiv.org/pdf/2406.1"
    assert pdf_url_for({}) is None


def test_extract_text_returns_body():
    lines = [f"Result line {i}: the method improves accuracy here." for i in range(30)]
    text = extract_text_from_pdf_bytes(_pdf_from_lines(lines))
    assert text is not None
    assert "method improves accuracy" in text


def test_extract_text_trims_references_tail():
    body = [f"Body sentence number {i} lives in the paper." for i in range(30)]
    tail = ["References"] + [f"[{i}] Citation that should be cut here." for i in range(30)]
    text = extract_text_from_pdf_bytes(_pdf_from_lines(body + tail))
    assert text is not None
    assert "Body sentence number" in text
    assert "Citation that should be cut" not in text


def test_extract_text_none_for_empty():
    assert extract_text_from_pdf_bytes(b"not a pdf") is None
    tiny = _pdf_from_lines(["too short"])
    assert extract_text_from_pdf_bytes(tiny) is None  # under 500 chars


def test_paper_text_falls_back_to_abstract_when_no_pdf():
    paper = {"abstract": "a" * 600, "url": "https://x/y"}
    r = paper_text(paper)
    assert r["source"] == "abstract"
    assert r["chars"] == 600


def test_paper_text_none_when_nothing():
    r = paper_text({"url": "https://x"})
    assert r["source"] == "none"
    assert r["text"] == ""
