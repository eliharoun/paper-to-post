import json
from pathlib import Path

from scripts.lib.config import load_brand_for_account
from scripts.lib.validation import (
    check_caption_link,
    check_grounding,
    check_health,
    check_hype,
    check_lengths,
    check_readability,
    check_schema,
    check_style,
    validate_post,
)

EM_DASH = "—"
EN_DASH = "–"

FIX = Path(__file__).parent / "fixtures"
BRAND = load_brand_for_account("cs")
GOOD_POST = json.loads((FIX / "good_post.json").read_text())
GOOD_PAPER = json.loads((FIX / "good_paper.json").read_text())


# --- schema + lengths ---

def test_check_schema_passes_good_post():
    errors, post = check_schema(GOOD_POST, BRAND)
    assert errors == []
    assert post is not None


def test_check_schema_rejects_missing_field():
    bad = dict(GOOD_POST)
    del bad["caption"]
    errors, post = check_schema(bad, BRAND)
    assert errors and post is None


def test_check_schema_rejects_too_few_cards():
    bad = dict(GOOD_POST, carousel_cards=GOOD_POST["carousel_cards"][:3])
    errors, _ = check_schema(bad, BRAND)
    assert any("card" in e.lower() for e in errors)


def test_check_lengths_passes_good_post():
    _, post = check_schema(GOOD_POST, BRAND)
    assert check_lengths(post, BRAND) == []


def test_check_lengths_flags_long_heading():
    bad = dict(GOOD_POST)
    bad["carousel_cards"] = [dict(GOOD_POST["carousel_cards"][0], heading="x" * 80)] + \
        GOOD_POST["carousel_cards"][1:]
    _, post = check_schema(bad, BRAND)
    errors = check_lengths(post, BRAND)
    assert any("heading" in e.lower() for e in errors)


def test_check_lengths_flags_too_many_hashtags():
    bad = dict(GOOD_POST, hashtags=[f"#t{i}" for i in range(9)])
    _, post = check_schema(bad, BRAND)
    assert any("hashtag" in e.lower() for e in check_lengths(post, BRAND))


# --- hype, grounding, caption link ---

def test_check_hype_passes_clean_post():
    _, post = check_schema(GOOD_POST, BRAND)
    assert check_hype(post) == []


def test_check_hype_flags_banned_term_in_body():
    bad = json.loads((FIX / "good_post.json").read_text())
    bad["carousel_cards"][0]["body"] = "This is a guaranteed cure for the problem."
    _, post = check_schema(bad, BRAND)
    errors = check_hype(post)
    assert any("cure" in e or "guaranteed" in e for e in errors)


def test_check_hype_flags_term_in_caption():
    bad = dict(GOOD_POST, caption=GOOD_POST["caption"] + " A total breakthrough!")
    _, post = check_schema(bad, BRAND)
    assert any("breakthrough" in e for e in check_hype(post))


def test_check_style_passes_clean_post():
    _, post = check_schema(GOOD_POST, BRAND)
    assert check_style(post) == []


def test_check_style_flags_em_dash_in_body():
    bad = json.loads((FIX / "good_post.json").read_text())
    bad["carousel_cards"][1]["body"] = f"It works {EM_DASH} but only sometimes."
    _, post = check_schema(bad, BRAND)
    errors = check_style(post)
    assert any("em dash" in e for e in errors)


def test_check_style_flags_en_dash_in_caption():
    bad = dict(GOOD_POST, caption=GOOD_POST["caption"] + f" A range {EN_DASH} here.")
    _, post = check_schema(bad, BRAND)
    assert any("en dash" in e and "caption" in e for e in check_style(post))


def test_check_style_allows_plain_hyphen():
    # Hyphen-minus in compounds/ranges is fine — only em/en dashes are banned.
    clean = json.loads((FIX / "good_post.json").read_text())
    clean["carousel_cards"][1]["body"] = "A single-molecule, deep-lung result at 37%-70%."
    _, post = check_schema(clean, BRAND)
    assert check_style(post) == []


def test_check_hype_word_boundary_no_false_positive():
    # "proven" must not fire inside "provenance"; "cure" not inside "secure"
    clean = json.loads((FIX / "good_post.json").read_text())
    clean["carousel_cards"][1]["body"] = "The provenance is implicit and the pipeline stays secure."
    _, post = check_schema(clean, BRAND)
    assert check_hype(post) == []


def test_check_hype_still_flags_whole_words_and_symbols():
    bad = json.loads((FIX / "good_post.json").read_text())
    bad["carousel_cards"][1]["body"] = "This is proven and works 100% of the time."
    _, post = check_schema(bad, BRAND)
    errs = " ".join(check_hype(post))
    assert "proven" in errs and "100%" in errs


def test_check_grounding_passes_matching_paper():
    _, post = check_schema(GOOD_POST, BRAND)
    assert check_grounding(post, GOOD_PAPER) == []


def test_check_grounding_flags_title_mismatch():
    bad = dict(GOOD_POST, source_title="A Completely Different Title About Cats")
    _, post = check_schema(bad, BRAND)
    assert any("title" in e.lower() for e in check_grounding(post, GOOD_PAPER))


def test_check_grounding_flags_url_mismatch():
    bad = dict(GOOD_POST, source_url="https://evil.example.com/x")
    _, post = check_schema(bad, BRAND)
    assert any("url" in e.lower() for e in check_grounding(post, GOOD_PAPER))


def test_check_grounding_flags_peer_reviewed_claim_on_preprint():
    bad = json.loads((FIX / "good_post.json").read_text())
    bad["carousel_cards"][1]["body"] = "This peer-reviewed study confirms the effect."
    _, post = check_schema(bad, BRAND)
    assert any("peer" in e.lower() for e in check_grounding(post, GOOD_PAPER))


def test_check_caption_link_passes_when_url_present():
    _, post = check_schema(GOOD_POST, BRAND)
    assert check_caption_link(post, GOOD_PAPER) == []


def test_check_caption_link_flags_missing_url():
    bad = dict(GOOD_POST, caption="No link here at all. #ScienceNews")
    _, post = check_schema(bad, BRAND)
    assert any("link" in e.lower() or "url" in e.lower()
               for e in check_caption_link(post, GOOD_PAPER))


# --- readability + health ---

def test_check_readability_passes_short_sentences():
    _, post = check_schema(GOOD_POST, BRAND)
    assert check_readability(post) == []


def test_check_readability_flags_long_sentences():
    bad = json.loads((FIX / "good_post.json").read_text())
    bad["carousel_cards"][0]["body"] = (
        "This is an extremely long run on sentence that keeps going and going with "
        "far too many words packed into a single clause without any punctuation to "
        "break it up so the average sentence length climbs well past the limit set."
    )
    _, post = check_schema(bad, BRAND)
    assert any("sentence" in e.lower() for e in check_readability(post))


def test_check_readability_allows_dense_technical_sentence():
    # A serious-outlet-register sentence (~25 words) must pass under the 26 cap;
    # this is the register we want, and the old 22 cap wrongly rejected it.
    from scripts.lib.textutil import avg_sentence_length
    dense = ("At under one false alarm per hour, their convolutional network hit 0.43 "
             "detection and 0.30 isotope-ID rates, edging out the previous matrix method.")
    assert 20 < avg_sentence_length(dense) <= 26  # in the intended band
    bad = json.loads((FIX / "good_post.json").read_text())
    bad["carousel_cards"][0]["body"] = dense
    _, post = check_schema(bad, BRAND)
    assert check_readability(post) == []


def test_check_health_noop_when_topic_not_guarded():
    _, post = check_schema(GOOD_POST, BRAND)
    assert check_health(post, GOOD_PAPER, requires_guardrails=False) == []


def test_check_health_requires_disclaimer_for_medical_content():
    # guarded topic + genuinely medical paper (cancer/patients) -> disclaimer required
    med_paper = dict(GOOD_PAPER, title="A clinical study of cancer patients",
                     abstract="We treated patients with a therapy for the disease.")
    _, post = check_schema(GOOD_POST, BRAND)
    errors = check_health(post, med_paper, requires_guardrails=True)
    assert any("medical advice" in e.lower() for e in errors)


def test_check_health_no_disclaimer_for_basic_science():
    # guarded topic BUT non-medical content (evolution/genomics) -> no disclaimer needed
    basic_paper = dict(GOOD_PAPER,
                       title="Ghost lineage introgression in modern genomes",
                       abstract="We estimate superarchaic ancestry from coalescent depth "
                                 "across populations using an ARG-free neural method.")
    _, post = check_schema(GOOD_POST, BRAND)  # AI-ish post text, no health markers
    assert check_health(post, basic_paper, requires_guardrails=True) == []


def test_check_health_flags_treatment_advice_always():
    bad = json.loads((FIX / "good_post.json").read_text())
    bad["caption"] = ("You should take this supplement daily. Not medical advice. "
                      "https://arxiv.org/abs/2406.00001")
    _, post = check_schema(bad, BRAND)
    # treatment phrasing is blocked on the guarded topic regardless of content type
    errors = check_health(post, GOOD_PAPER, requires_guardrails=True)
    assert any("advice" in e.lower() or "treatment" in e.lower()
               or "supplement" in e.lower() for e in errors)


def test_looks_like_health_content():
    from scripts.lib.validation import looks_like_health_content
    _, post = check_schema(GOOD_POST, BRAND)
    med = dict(GOOD_PAPER, title="Tumor prognosis in patients", abstract="clinical trial")
    basic = dict(GOOD_PAPER, title="Plant genome assembly", abstract="chromosome scaffolds")
    assert looks_like_health_content(med, post) is True
    assert looks_like_health_content(basic, post) is False


# --- composer ---

def test_validate_post_passes_good():
    result = validate_post(GOOD_POST, GOOD_PAPER, BRAND, requires_guardrails=False)
    assert result.passed
    assert result.errors == []


def test_validate_post_aggregates_errors():
    bad = dict(GOOD_POST, source_url="https://evil.example.com", caption="no link")
    result = validate_post(bad, GOOD_PAPER, BRAND, requires_guardrails=False)
    assert not result.passed
    assert len(result.errors) >= 2  # url mismatch + missing caption link
