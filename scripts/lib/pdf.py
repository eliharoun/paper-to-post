"""Shared PDF helpers: resolve a fetchable URL, download (size/timeout capped),
and extract full text. Used by the first-page screenshot and full-text extraction.
"""
from __future__ import annotations

import re

import httpx


def pdf_url_for(paper: dict) -> str | None:
    """Best fetchable PDF URL for a paper, or None."""
    if paper.get("pdf_url"):
        return paper["pdf_url"]
    if paper.get("arxiv_id"):
        return f"https://arxiv.org/pdf/{paper['arxiv_id']}"
    return None


def fetch_pdf(url: str, *, max_bytes: int = 52_428_800, timeout: int = 30) -> bytes | None:
    """Download a PDF, streaming with a byte cap. Returns None on any failure."""
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            with client.stream("GET", url) as resp:
                if resp.status_code != 200:
                    return None
                buf = bytearray()
                for chunk in resp.iter_bytes():
                    buf += chunk
                    if len(buf) > max_bytes:
                        return None
                return bytes(buf)
    except httpx.HTTPError:
        return None


# References/acknowledgments/appendix add noise and cost without content value for
# a summary; cut the body at the first of these section headers when present.
_TAIL_SECTIONS = re.compile(
    r"\n\s*(references|bibliography|acknowledgments?|acknowledgements?|"
    r"supplementary\s+materials?|appendix|appendices)\b",
    re.IGNORECASE,
)
_WS = re.compile(r"[ \t]+")
_MULTINL = re.compile(r"\n{3,}")


def extract_text_from_pdf_bytes(pdf_bytes: bytes, *, max_chars: int = 60_000) -> str | None:
    """Extract readable body text from a PDF. Trims reference/appendix tails and
    caps length. Returns None if extraction yields little usable text.
    """
    try:
        import fitz  # pymupdf
    except ImportError:
        return None
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        parts = [page.get_text("text") for page in doc]
    except Exception:  # noqa: BLE001 — malformed PDF => no text, caller falls back
        return None

    text = "\n".join(parts)
    text = _WS.sub(" ", text)
    text = _MULTINL.sub("\n\n", text).strip()

    m = _TAIL_SECTIONS.search(text)
    if m and m.start() > 1000:  # only trim if there's a real body before it
        text = text[: m.start()].strip()

    if len(text) < 500:  # too little to be a real body (scanned/figure-only PDF)
        return None
    return text[:max_chars]
