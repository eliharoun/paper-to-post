from scripts.lib.textutil import (
    avg_sentence_length,
    content_hash,
    normalize_title,
    title_hash,
)


def test_normalize_title_strips_version_and_punct():
    assert normalize_title("Attention Is All You Need [v2]!") == "attention is all you need"


def test_normalize_title_collapses_whitespace():
    assert normalize_title("  Deep   Learning\n") == "deep learning"


def test_title_hash_is_stable_and_version_insensitive():
    a = title_hash("Foo Bar [v1]")
    b = title_hash("foo   bar")
    assert a == b
    assert len(a) == 64  # sha256 hex


def test_content_hash_differs_on_abstract():
    h1 = content_hash("Title", "abstract one")
    h2 = content_hash("Title", "abstract two")
    assert h1 != h2


def test_avg_sentence_length():
    # 2 sentences: "One two three." (3) and "Four five." (2) -> avg 2.5
    assert avg_sentence_length("One two three. Four five.") == 2.5


def test_avg_sentence_length_ignores_decimals():
    # decimals must not be treated as sentence boundaries: this is ONE 24-word
    # sentence, not fragments. Guards the readability check against decimal-heavy
    # technical cards scoring artificially low.
    text = ("At under one false alarm per hour their network hit 0.43 detection "
            "and 0.30 isotope-ID rates edging out the previous matrix method here")
    # one sentence, 23 words — decimals 0.43 / 0.30 are NOT sentence breaks
    assert avg_sentence_length(text) == 23.0
