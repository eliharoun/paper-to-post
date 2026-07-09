from __future__ import annotations

import hashlib
import re

_VERSION_MARKER = re.compile(r"\[v\d+\]", re.IGNORECASE)
_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_WS = re.compile(r"\s+")
# Split on sentence-ending punctuation only when followed by whitespace or end of
# string, so decimals ("0.43") and version/id dots don't fragment a sentence.
_SENTENCE_SPLIT = re.compile(r"[.!?]+(?=\s|$)")


def normalize_title(title: str) -> str:
    """Lowercase, strip [vN] markers, drop punctuation, collapse whitespace."""
    t = _VERSION_MARKER.sub(" ", title)
    t = t.lower()
    t = _PUNCT.sub(" ", t)
    t = _WS.sub(" ", t).strip()
    return t


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def title_hash(title: str) -> str:
    return _sha256(normalize_title(title))


def content_hash(title: str, abstract: str | None) -> str:
    return _sha256(normalize_title(title) + "\x00" + (abstract or "").strip().lower())


def avg_sentence_length(text: str) -> float:
    """Average words per sentence. Returns 0.0 for empty text."""
    sentences = [s for s in _SENTENCE_SPLIT.split(text) if s.strip()]
    if not sentences:
        return 0.0
    total_words = sum(len(s.split()) for s in sentences)
    return total_words / len(sentences)
