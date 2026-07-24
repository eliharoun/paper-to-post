from __future__ import annotations

import re

from pydantic import BaseModel, ValidationError

from scripts.lib.config import BrandConfig
from scripts.lib.models import GeneratedPost
from scripts.lib.textutil import avg_sentence_length, normalize_title

BANNED_HYPE = (
    "cure", "proven", "proves", "guaranteed", "miracle", "breakthrough",
    "revolutionary", "game-changer", "game changer",
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
        # Source cards carry the full paper title verbatim; exempt from heading cap.
        if card.card_type != "source" and len(card.heading) > 70:
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


_SHARE_VERB_RE = re.compile(r"\b(send|share|tag|forward|dm)\b", re.IGNORECASE)


def check_engagement(post: GeneratedPost) -> tuple[list[str], list[str]]:
    """Enforce the engagement fields. Returns (errors, warnings).

    share_cta is REQUIRED (the DM-send lever, the top 2026 reach signal) and must
    actually prompt a send/share/tag. takeaway and debate_question are advisory
    (their engagement multipliers are plausible but unproven), so their absence is
    a warning, not a gate."""
    errors: list[str] = []
    warnings: list[str] = []
    cta = (post.share_cta or "").strip()
    if not cta:
        errors.append("share_cta is required (a role-specific 'send this to…' line)")
    elif not _SHARE_VERB_RE.search(cta):
        errors.append(
            "share_cta must prompt a share (use 'send'/'share'/'tag'), "
            f"got: {cta[:60]!r}"
        )
    if not (post.takeaway or "").strip():
        warnings.append(
            "takeaway is empty — add a portable, screenshot-worthy one-liner "
            "(the finding as a standalone quotable line) to drive saves"
        )
    if not (post.debate_question or "").strip():
        warnings.append(
            "debate_question is empty — a short opinion question drives comments"
        )
    return errors, warnings


def check_caption_link(post: GeneratedPost, paper: dict) -> list[str]:
    url = (paper.get("url") or "").strip()
    if url and url not in post.caption:
        return ["caption missing the article link (source_url must appear in caption)"]
    return []


# "AI tell" punctuation. The em dash (U+2014), en dash (U+2013) and horizontal
# bar (U+2015) rarely appear in text people actually type; their presence reads as
# machine-generated. Ban them everywhere so writers use commas, colons, parentheses,
# or separate sentences instead. Hyphen-minus (U+002D) for ranges/compounds is fine.
_AI_TELL_DASHES = {"—": "em dash", "–": "en dash", "―": "horizontal bar"}


def check_style(post: GeneratedPost) -> list[str]:
    """Reject AI-tell punctuation (em/en dashes) in any card or the caption."""
    errors: list[str] = []
    fields: list[tuple[str, str]] = [("caption", post.caption)]
    for c in post.carousel_cards:
        fields.append((f"card {c.card_number} heading", c.heading))
        fields.append((f"card {c.card_number} body", c.body))
    for where, text in fields:
        present = sorted({name for ch, name in _AI_TELL_DASHES.items() if ch in text})
        if present:
            errors.append(
                f"style: {where} uses {', '.join(present)} — replace with a comma, "
                "colon, parentheses, or two sentences (people don't type these)"
            )
    return errors


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


# Content cards that carry substance (a paper fact). The title/hero card has an
# empty body by design and the source card is a citation, so neither is expected
# to carry a quantitative anchor; they are excluded from the substance proxy.
_NON_SUBSTANCE_CARD_TYPES = {"title", "source"}

# Spelled-out quantities count as anchors too, so a mechanism card that says
# "two-thirds of trials" or "a threefold increase" isn't falsely flagged. This is
# deliberately a coarse presence check, not an NLP judgment of "interestingness"
# (which stays with the writer + rubric) — hence warning-level, never a gate.
_NUMBER_WORDS = (
    "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
    "eleven", "twelve", "dozen", "hundred", "thousand", "million", "billion",
    "trillion", "half", "third", "quarter", "twofold", "threefold", "tenfold",
    "double", "triple", "quadruple",
)
_NUMBER_WORD_RE = re.compile(r"\b(" + "|".join(_NUMBER_WORDS) + r")s?\b", re.IGNORECASE)
# A digit anywhere (covers "37%", "0.43", "2,991", "F1 89.83") — the strongest,
# least ambiguous substance signal.
_DIGIT_RE = re.compile(r"\d")


def _has_quantitative_anchor(text: str) -> bool:
    return bool(_DIGIT_RE.search(text) or _NUMBER_WORD_RE.search(text))


def check_substance(post: GeneratedPost) -> list[str]:
    """Warning-level proxy for the guide's #1 failure mode: a card that frames a
    finding without delivering a specific fact ("the results are impressive").

    Deterministic and coarse by design: it only checks for the presence of a
    *quantitative anchor* (a digit or a spelled-out number) across the content
    cards — NOT for named entities or "technical terms", which have no
    topic-agnostic definition across cs/bio/physics and would false-positive.
    Post-level, not per-card: warns only when NOT ONE content-card body carries a
    number, since a single genuinely qualitative mechanism card is legitimate.
    Returns warnings (never errors) so it informs the writer's judgment without
    touching the hard gate."""
    content = [
        c for c in post.carousel_cards
        if c.card_type not in _NON_SUBSTANCE_CARD_TYPES and c.body.strip()
    ]
    if not content:
        return []
    if any(_has_quantitative_anchor(c.body) for c in content):
        return []
    return [
        "substance: no content card carries a specific number — the results card "
        "should state the paper's headline figure (e.g. a rate, effect size, "
        "sample, or speedup). Add the concrete fact rather than framing it."
    ]


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
    post_dict: dict, paper: dict | None, brand: BrandConfig, *, requires_guardrails: bool
) -> ValidationResult:
    """Run every check. passed=True only if there are zero errors.

    `paper` may be None for a paperless post (e.g. a weekly roundup): the
    paper-grounding, caption-link, and paper-based health checks are skipped, but
    schema/length/hype/style/readability/engagement still gate."""
    schema_errors, post = check_schema(post_dict, brand)
    if post is None:
        return ValidationResult(passed=False, errors=schema_errors)

    errors = list(schema_errors)
    errors += check_lengths(post, brand)
    errors += check_hype(post)
    errors += check_style(post)
    errors += check_readability(post)
    if paper is not None:
        errors += check_grounding(post, paper)
        errors += check_caption_link(post, paper)
        errors += check_health(post, paper, requires_guardrails=requires_guardrails)
    eng_errors, eng_warnings = check_engagement(post)
    errors += eng_errors
    # Warnings inform the writer's judgment but never gate: passed keys on errors only.
    warnings = check_substance(post) + eng_warnings
    return ValidationResult(passed=not errors, errors=errors, warnings=warnings)
