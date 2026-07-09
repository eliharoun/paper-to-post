from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, field_validator


class Palette(BaseModel):
    background: str
    surface: str
    text_primary: str
    text_muted: str
    accent: str
    card_type_colors: dict[str, str]


class BrandConfig(BaseModel):
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


class ArxivSource(BaseModel):
    categories: list[str] = []


class OpenAlexSource(BaseModel):
    subfields: list[str] = []       # OpenAlex subfield ids (precise filter, preferred)
    query: str = ""                 # optional short search phrase (strict full-text AND)


class CrossrefSource(BaseModel):
    query: str = ""                 # relevance-ranked; keep short


class SemanticScholarSource(BaseModel):
    query: str = ""


class PubmedSource(BaseModel):
    query: str = ""


class BiorxivSource(BaseModel):
    servers: list[str] = ["biorxiv", "medrxiv"]


class LabsSource(BaseModel):
    labs: list[str] = []            # e.g. ["meta", "google", "deepmind"]
    query: str = ""


class TopicSources(BaseModel):
    """Which paper sources a topic pulls from. Absent source => not run."""
    arxiv: ArxivSource | None = None
    openalex: OpenAlexSource | None = None
    crossref: CrossrefSource | None = None
    semantic_scholar: SemanticScholarSource | None = None
    pubmed: PubmedSource | None = None
    biorxiv: BiorxivSource | None = None
    labs: LabsSource | None = None

    def active(self) -> list[str]:
        """Names of the sources configured for this topic (in a stable order)."""
        order = ["arxiv", "openalex", "crossref", "semantic_scholar", "pubmed", "biorxiv", "labs"]
        return [name for name in order if getattr(self, name) is not None]


# ---- Per-channel publish config (a topic publishes to each listed channel) ---


class PublishTarget(BaseModel):
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


class TopicConfig(BaseModel):
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


class TopicsConfig(BaseModel):
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
