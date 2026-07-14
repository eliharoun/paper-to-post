from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

Confidence = Literal["low", "medium", "high"]
CardType = Literal[
    "title", "hook", "finding", "method", "context", "limitation", "source", "next"
]


class PaperInput(BaseModel):
    source: str
    source_id: str
    doi: str | None = None
    arxiv_id: str | None = None
    semantic_scholar_id: str | None = None
    openalex_id: str | None = None
    title: str
    abstract: str | None = None
    authors: list[str] = Field(default_factory=list)
    venue: str | None = None
    published_date: date | None = None
    updated_date: datetime | None = None
    url: str
    pdf_url: str | None = None
    field_of_study: str | None = None
    topic_id: str | None = None
    citation_count: int | None = None
    is_preprint: bool | None = None
    is_open_access: bool | None = None
    license: str | None = None
    raw_payload: dict = Field(default_factory=dict)


class Candidate(BaseModel):
    paper: PaperInput
    topic_id: str | None = None
    filter_status: str = "passed"
    filter_reasons: list[str] = []
    rule_score: float | None = None
    llm_score: float | None = None
    final_score: float | None = None
    score_breakdown: dict = {}


class CarouselCard(BaseModel):
    card_number: int
    card_type: CardType
    heading: str
    body: str
    footer: str


class GeneratedPost(BaseModel):
    paper_id: str
    source_title: str
    source_url: str
    is_preprint: bool
    plain_english_headline: str
    one_sentence_summary: str
    why_it_matters: str
    what_they_did: str
    what_they_found: str
    important_context: str
    limitations: list[str]
    avoid_saying: list[str]
    carousel_cards: list[CarouselCard]
    caption: str
    hashtags: list[str]
    alt_text: str
    confidence: Confidence
    hero_image_prompt: str | None = None
