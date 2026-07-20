from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, field_validator


class _Strict(BaseModel):
    """Base for all config models: reject unknown keys so a typo in a YAML file
    (e.g. `hero_syle:` or a misspelled field) raises a clear ValidationError at
    load time instead of silently dropping the key and degrading the output."""
    model_config = ConfigDict(extra="forbid")


# Keys allowed inside the free-form `type_scale` dict (pydantic can't guard dict
# values, so a typo like `titel_px` would silently fall back to a render default).
_ALLOWED_TYPE_SCALE_KEYS = {
    "title_px", "title_source_px", "heading_px", "body_px", "label_px", "footer_px",
}


class Palette(_Strict):
    background: str
    surface: str
    text_primary: str
    text_muted: str
    accent: str
    card_type_colors: dict[str, str]


class HeroStyle(_Strict):
    enabled: bool = True
    # Default = cheaper flash tier. To upgrade quality, swap image_model to:
    #   nano-banana-pro-preview     (top quality, ~pro pricing)
    #   gemini-3-pro-image-preview
    image_model: str = "gemini-3.1-flash-image-preview"
    aspect_ratio: str = "4:5"
    # per-topic house style (visual medium/palette/mood), folded into hero_image_prompt
    style: str = ""
    # Optional per-topic guidance on WHAT to depict (the concept), separate from
    # `style` (HOW it looks). Writer-facing only — steers subject choice, never
    # pasted into the image prompt verbatim. Empty = follow the guide's defaults.
    concept_guidance: str = ""
    # Post-generation brand color grade applied to the hero image (duotone toward
    # the brand background+accent). This is the top grid-coherence lever: it gives
    # every post one recognizable color signature. 0 = off; ~0.35 is a good
    # default (subject stays readable); >0.6 gets heavy-handed.
    grade_strength: float = 0.0


class BrandConfig(_Strict):
    account_name: str
    footer_text: str
    canvas_width: int
    canvas_height: int
    render_scale: int = 2
    margin: int
    max_cards: int
    min_cards: int
    jpeg_quality: int
    motif: str | list[str] = "none"
    fonts: dict[str, str]
    type_scale: dict[str, int]
    palette: Palette
    logo_path: str = ""
    hero_style: HeroStyle | None = None
    # Series identity on the front card. When show_episode_number is true, the
    # title-card eyebrow reads "<series_name> · #<edition>" (series_name defaults
    # to account_name). The edition number comes from the ledger (per-account
    # count of delivery days) and is passed in at render time.
    series_name: str = ""
    show_episode_number: bool = False

    @field_validator("type_scale")
    @classmethod
    def _check_type_scale(cls, v: dict[str, int]) -> dict[str, int]:
        unknown = set(v) - _ALLOWED_TYPE_SCALE_KEYS
        if unknown:
            raise ValueError(
                f"unknown type_scale key(s) {sorted(unknown)}; "
                f"allowed: {sorted(_ALLOWED_TYPE_SCALE_KEYS)}"
            )
        return v

    def eyebrow_label(self, episode: int | None = None) -> str:
        """The uppercase front-card eyebrow, optionally with the series edition.

        Plain account name unless `show_episode_number` is set AND an `episode` is
        given, in which case it reads '<SERIES_NAME> · #<episode>'. series_name
        defaults to account_name. Shared by both front-card render paths so the
        motif card and the hero card format the eyebrow identically."""
        base = (self.series_name or self.account_name).upper()
        if self.show_episode_number and episode is not None:
            return f"{base} · #{episode}"
        return base

    def resolve_motif(self, key: str | None = None) -> str:
        """Pick one motif. If `motif` is a list, rotate deterministically by `key`
        (e.g. the run date 'YYYY-MM-DD') so the front card varies across posts."""
        if isinstance(self.motif, str):
            return self.motif
        if not self.motif:
            return "none"
        if key is None:
            return self.motif[0]
        # stable index from the key so the same date always yields the same motif
        idx = sum(ord(c) for c in key) % len(self.motif)
        return self.motif[idx]


# ---- Per-source config (only listed sources run for a topic) ----------------
# Each source is optional; its presence under a topic's `sources:` means "run it".


class ArxivSource(_Strict):
    categories: list[str] = []


class OpenAlexSource(_Strict):
    subfields: list[str] = []       # OpenAlex subfield ids (precise filter, preferred)
    query: str = ""                 # optional short search phrase (strict full-text AND)


class CrossrefSource(_Strict):
    query: str = ""                 # relevance-ranked; keep short


class SemanticScholarSource(_Strict):
    query: str = ""


class PubmedSource(_Strict):
    query: str = ""


class BiorxivSource(_Strict):
    servers: list[str] = ["biorxiv", "medrxiv"]


class LabsSource(_Strict):
    labs: list[str] = []            # e.g. ["meta", "google", "deepmind"]
    query: str = ""


class JournalsSource(_Strict):
    journals: list[str] = []        # e.g. ["nature", "lancet", "cell"] (via OpenAlex source id)
    query: str = ""


class TopicSources(_Strict):
    """Which paper sources a topic pulls from. Absent source => not run."""
    arxiv: ArxivSource | None = None
    openalex: OpenAlexSource | None = None
    crossref: CrossrefSource | None = None
    semantic_scholar: SemanticScholarSource | None = None
    pubmed: PubmedSource | None = None
    biorxiv: BiorxivSource | None = None
    labs: LabsSource | None = None
    journals: JournalsSource | None = None

    def active(self) -> list[str]:
        """Names of the sources configured for this topic (in a stable order)."""
        order = ["arxiv", "openalex", "crossref", "semantic_scholar", "pubmed",
                 "biorxiv", "labs", "journals"]
        return [name for name in order if getattr(self, name) is not None]


# ---- Per-channel publish config (a topic publishes to each listed channel) ---


class PublishTarget(_Strict):
    """One publishing destination. `channel` selects the publisher; other fields
    are channel-specific (e.g. Instagram/LinkedIn account identity).

    Volume is a *channel* decision: the topic gathers papers, and each channel's
    `max_posts` controls how many of the produced posts that channel publishes
    (for the newsletter, how many items appear in the digest). None = no cap
    (publish every produced post that cleared the quality gate)."""
    channel: str                    # "instagram" | "linkedin" | "newsletter"
    alias: str = ""                 # Composio connection alias (instagram/linkedin)
    username: str = ""              # expected handle for the pre-publish guard
    enabled: bool = True
    max_posts: int | None = None    # how many posts this channel publishes (None = all)

    # --- newsletter-only options (ignored by instagram/linkedin) --------------
    # Control how the daily digest for this topic is assembled. All optional; the
    # defaults reproduce the previous behaviour (every produced post, in order).
    sort: str = "position"          # "position" (selection order) | "confidence"
    min_confidence: str = ""        # drop items below this: "low"|"medium"|"high"
    title: str = ""                 # digest title override (default: account_name)
    show_why_it_matters: bool = True  # render the per-item "Why it matters" line
    footer: str = ""                # optional footer line (e.g. reply/forward CTA)

    @field_validator("sort")
    @classmethod
    def _check_sort(cls, v: str) -> str:
        if v not in ("position", "confidence"):
            raise ValueError(f"sort must be 'position' or 'confidence', got {v!r}")
        return v

    @field_validator("min_confidence")
    @classmethod
    def _check_min_confidence(cls, v: str) -> str:
        if v not in ("", "low", "medium", "high"):
            raise ValueError(
                f"min_confidence must be '', 'low', 'medium', or 'high', got {v!r}"
            )
        return v


class BlendConfig(_Strict):
    local_weight: float = 0.6
    external_weight: float = 0.4
    method: str = "weighted"        # weighted | max | multiplier

    @field_validator("method")
    @classmethod
    def _check_method(cls, v: str) -> str:
        if v not in ("weighted", "max", "multiplier"):
            raise ValueError(
                f"blend method must be weighted|max|multiplier, got {v!r}"
            )
        return v


class CorpusBurstConfig(_Strict):
    enabled: bool = True
    # `weight` is reserved for future multi-local-signal blending; today corpus_burst
    # is the sole local signal, so the local/external split is set by blend.local_weight.
    weight: float = 1.0
    window_days: int = 14
    min_doc_freq: int = 3           # a term must appear in >= this many of today's papers
    top_terms: int = 5              # raw score = mean of a paper's top-N term weights
    burst_cap: float = 3.0          # tanh scale for per-term burst (soft saturation)
    min_corpus: int = 30            # below this, no trendiness is computed
    extra_stopwords: list[str] = []


class SignalConfig(_Strict):
    """One external signal provider's config. `params` is a free-form dict the
    provider interprets, so adding a provider needs no new config class."""
    name: str                       # registry key: hackernews | gdelt | huggingface | ...
    enabled: bool = True
    weight: float = 1.0
    timeout_s: float = 8.0
    cache_ttl_min: int = 180
    params: dict = {}


class TrendsConfig(_Strict):
    enabled: bool = True
    sort_bump: float = 8.0
    top_slice: int = 25
    blend: BlendConfig = BlendConfig()
    corpus_burst: CorpusBurstConfig = CorpusBurstConfig()
    signals: list[SignalConfig] = []

    def active_signals(self) -> list[SignalConfig]:
        return [s for s in self.signals if s.enabled]


class TopicConfig(_Strict):
    id: str
    enabled: bool
    account: str = ""
    display_name: str
    priority: float
    keywords: list[str] = []        # topic-assignment hints (moved out of code)
    hard_excludes: list[str] = []
    requires_health_guardrails: bool = False
    sources: TopicSources = TopicSources()
    publish: list[PublishTarget] = []
    trends: TrendsConfig = TrendsConfig()
    # Curated mid-tail hashtags (10K-500K posts) for this topic; the writer picks
    # 3-5 per post from this bank. Advisory — empty means the writer free-forms.
    hashtag_bank: list[str] = []

    def publish_targets(self, channel: str | None = None) -> list[PublishTarget]:
        """Enabled publish targets, optionally filtered to one channel."""
        return [
            t for t in self.publish
            if t.enabled and (channel is None or t.channel == channel)
        ]

    def max_posts_needed(self) -> int | None:
        """How many posts to PRODUCE for this topic = the largest `max_posts`
        across its enabled channels (so every channel can take its cut). Returns
        None if any enabled channel is uncapped (produce every post that clears
        the gate), or if there are no enabled channels."""
        targets = self.publish_targets()
        if not targets:
            return None
        caps = [t.max_posts for t in targets]
        if any(c is None for c in caps):
            return None                     # an uncapped channel wants them all
        return max(caps)


class TopicsConfig(_Strict):
    default_language: str = "en"
    lookback_hours: int = 48
    max_candidates_per_topic: int = 20
    topics: list[TopicConfig] = []

    def enabled_topics(self) -> list[TopicConfig]:
        return [t for t in self.topics if t.enabled]

    def for_account(self, account: str) -> list[TopicConfig]:
        """Enabled topics belonging to one account (e.g. 'cs' or 'bio')."""
        return [t for t in self.enabled_topics() if t.account == account]


def load_env() -> None:
    """Load .env into os.environ if present. Call once at script start."""
    load_dotenv(override=False)


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def load_brand(path: Path | str | None = None) -> BrandConfig:
    """Load a brand config. Path defaults are handled by callers/paths.py."""
    if path is None:
        from scripts.lib import paths
        path = paths.brand_path("cs")
    data = yaml.safe_load(Path(path).read_text())
    return BrandConfig(**data["brand"])


def load_brand_for_account(account: str) -> BrandConfig:
    """Load the brand config for an account id, e.g. 'cs' -> config/brand.cs.yml."""
    from scripts.lib import paths
    return load_brand(paths.brand_path(account))


def resolve_brand(*, account: str | None = None, brand_path: str | None = None) -> BrandConfig:
    """Resolve a brand config from an explicit path or an account id.

    Precedence: explicit brand_path > account id. Raises if neither is given.
    """
    if brand_path:
        return load_brand(brand_path)
    if account:
        return load_brand_for_account(account)
    raise ValueError("provide either --account or --brand")


def load_topics(path: Path | str | None = None) -> TopicsConfig:
    if path is None:
        from scripts.lib import paths
        path = paths.topics_path()
    data = yaml.safe_load(Path(path).read_text())
    return TopicsConfig(**data)
