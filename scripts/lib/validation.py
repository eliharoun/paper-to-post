from __future__ import annotations

import re

from pydantic import BaseModel, ValidationError

from scripts.lib.config import BrandConfig
from scripts.lib.models import GeneratedPost
from scripts.lib.textutil import avg_sentence_length, normalize_title

BANNED_HYPE = (
    "cure", "proven", "proves", "guaranteed", "miracle", "breakthrough",
    "game-changing", "game changing", "doctors recommend", "everyone should",
    "eliminates risk", "100%", "no risk",
)

_TREATMENT_PHRASES = (
    "you should take", "take this", "recommended dose", "dosage", "start taking",
    "supplement daily", "take a supplement", "stop taking", "treat your",
)

_PEER_REVIEW_RE = re.compile(r"peer[ -]review(ed)?")
_NEGATION_RE = re.compile(r"\b(not|yet|before|prior to|awaiting|pre-?print)\b|n't")

# Max average words/sentence for a card body. Calibrated for a technically literate,
# serious-outlet register (Quanta/Ars/Nature-news run ~24-28 words): dense-but-clear
# cards measure ~25-27 and must pass, while academic run-ons (~34+) must fail.
MAX_AVG_SENTENCE_WORDS = 26


class ValidationResult(BaseModel):
    passed: bool
    errors: list[str] = []
    warnings: list[str] = []
    repaired: bool = False


def check_schema(post_dict: dict, brand: BrandConfig) -> tuple[list[str], GeneratedPost | None]:
    """Validate JSON against GeneratedPost + card-count bounds. Returns (errors, post|None)."""
    try:
        post = GeneratedPost(**post_dict)
    except ValidationError as exc:
        return [f"schema: {e['loc']}: {e['msg']}" for e in exc.errors()], None
    n = len(post.carousel_cards)
    errors: list[str] = []
    if n < brand.min_cards:
        errors.append(f"too few cards: {n} < {brand.min_cards}")
    if n > brand.max_cards:
        errors.append(f"too many cards: {n} > {brand.max_cards}")
    return errors, post


def check_lengths(post: GeneratedPost, brand: BrandConfig) -> list[str]:
    errors: list[str] = []
    for card in post.carousel_cards:
        if len(card.heading) > 70:
            errors.append(f"card {card.card_number} heading too long ({len(card.heading)}>70)")
        if len(card.body) > 280:
            errors.append(f"card {card.card_number} body too long ({len(card.body)}>280)")
        if len(card.footer) > 90:
            errors.append(f"card {card.card_number} footer too long ({len(card.footer)}>90)")
    if len(post.caption) > 2200:
        errors.append(f"caption too long ({len(post.caption)}>2200)")
    if len(post.hashtags) > 8:
        errors.append(f"too many hashtags ({len(post.hashtags)}>8)")
    return errors


def _all_text(post: GeneratedPost) -> str:
    parts = [post.caption, post.plain_english_headline, post.one_sentence_summary]
    for c in post.carousel_cards:
        parts += [c.heading, c.body, c.footer]
    return " ".join(parts).lower()


def check_hype(post: GeneratedPost) -> list[str]:
    text = _all_text(post)
    errors: list[str] = []
    for t in BANNED_HYPE:
        # Word-boundary match so a banned word doesn't fire inside a larger word
        # (e.g. "proven" must not match "provenance"). Anchor \b only at ends that
        # are alphanumeric, so terms like "100%" still match literally.
        lead = r"\b" if t[0].isalnum() else ""
        trail = r"\b" if t[-1].isalnum() else ""
        if re.search(lead + re.escape(t) + trail, text):
            errors.append(f"hype term present: '{t}'")
    return errors


def check_grounding(post: GeneratedPost, paper: dict) -> list[str]:
    errors: list[str] = []
    paper_title = paper.get("title") or ""
    if normalize_title(post.source_title) != normalize_title(paper_title):
        errors.append("grounding: source_title does not match paper title")
    paper_url = (paper.get("url") or "").strip()
    if post.source_url.strip() != paper_url:
        errors.append("grounding: source_url does not match paper url")
    # peer-reviewed claim on a preprint: flag only a bare claim, not a negated
    # one. For each "peer review(ed)" mention, look for a negation in the ~40
    # chars before it ("not", "yet", "before", "prior to", "n't", "awaiting").
    if paper.get("is_preprint"):
        text = _all_text(post)
        for m in _PEER_REVIEW_RE.finditer(text):
            preceding = text[max(0, m.start() - 40):m.start()]
            if not _NEGATION_RE.search(preceding):
                errors.append("grounding: claims peer-reviewed but paper is a preprint")
                break
    return errors


def check_caption_link(post: GeneratedPost, paper: dict) -> list[str]:
    url = (paper.get("url") or "").strip()
    if url and url not in post.caption:
        return ["caption missing the article link (source_url must appear in caption)"]
    return []


def check_readability(post: GeneratedPost) -> list[str]:
    errors: list[str] = []
    for c in post.carousel_cards:
        avg = avg_sentence_length(c.body)
        if avg > MAX_AVG_SENTENCE_WORDS:
            errors.append(
                f"card {c.card_number} avg sentence length "
                f"{avg:.1f} > {MAX_AVG_SENTENCE_WORDS}"
            )
    return errors


# Signals that a post is actually about human health/medicine (so a
# "not medical advice" disclaimer is warranted). Deliberately clinical/disease
# terms — NOT generic biology ("gene", "genome", "protein", "immune") — so basic
# science on the bio account (evolution, plant biology, taxonomy, pure genomics)
# is not forced to carry a medical disclaimer.
_HEALTH_MARKERS = (
    "patient", "clinical", "disease", "disorder", "syndrome", "diagnos",
    "prognos", "therapy", "therapeutic", "treatment", "symptom", "mortality",
    "morbidity", "dementia", "alzheimer", "parkinson", "cancer", "tumor", "tumour",
    "oncolog", "carcinoma", "diabetes", "cardiovascular", "infection", "vaccine",
    "drug", "dosage", "screening", "depression", "psychiatr", "mental health",
    "epidemi", "pathogen", "medication",
)


def looks_like_health_content(paper: dict, post: GeneratedPost) -> bool:
    """True if the paper/post reads as human-health/medical (vs. basic science)."""
    hay = " ".join(
        [paper.get("title") or "", paper.get("abstract") or "", _all_text(post)]
    ).lower()
    return any(m in hay for m in _HEALTH_MARKERS)


def check_health(post: GeneratedPost, paper: dict, *, requires_guardrails: bool) -> list[str]:
    """Health guardrails for the guarded topic.

    The 'not medical advice' disclaimer is required only when the content is
    actually medical (content-based, not blanket-by-topic). Treatment/consumer
    advice phrasing is never allowed on the guarded topic.
    """
    if not requires_guardrails:
        return []
    errors: list[str] = []
    if looks_like_health_content(paper, post):
        caption_l = post.caption.lower()
        if "not medical advice" not in caption_l and "not a substitute for" not in caption_l:
            errors.append(
                "health: medical/clinical content detected — caption must include a "
                "'not medical advice' disclaimer"
            )
    text = _all_text(post)
    for phrase in _TREATMENT_PHRASES:
        if phrase in text:
            errors.append(f"health: treatment/consumer advice phrasing present: '{phrase}'")
    return errors


def validate_post(
    post_dict: dict, paper: dict, brand: BrandConfig, *, requires_guardrails: bool
) -> ValidationResult:
    """Run every check. passed=True only if there are zero errors."""
    schema_errors, post = check_schema(post_dict, brand)
    if post is None:
        return ValidationResult(passed=False, errors=schema_errors)

    errors = list(schema_errors)
    errors += check_lengths(post, brand)
    errors += check_hype(post)
    errors += check_grounding(post, paper)
    errors += check_caption_link(post, paper)
    errors += check_readability(post)
    errors += check_health(post, paper, requires_guardrails=requires_guardrails)
    return ValidationResult(passed=not errors, errors=errors)
