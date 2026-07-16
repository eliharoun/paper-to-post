"""Shared primitives for trend signals: the tokenizer, the provider protocol,
the per-run context, and the stable paper-id helper."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

# Generic academic filler that is common every day -> never a trend signal.
_STOPWORDS: frozenset[str] = frozenset("""
a an the of to in on for and or but with without via using use used based
we our this that these those is are was were be been being it its as at by
from into over under new novel study paper approach method methods model
models framework results result propose proposed present presents show shows
shown demonstrate can may toward towards more less than then also across
remains remain rather however while where which what when how why
has have had not their they
""".split())

_TOKEN_RE = re.compile(r"[a-z][a-z\-]{1,}")


def _alpha_ratio(text: str) -> float:
    if not text:
        return 0.0
    letters = sum(1 for c in text if c.isascii() and c.isalpha())
    non_space = sum(1 for c in text if not c.isspace())
    return letters / non_space if non_space else 0.0


def _tokens(text: str, stop: set[str] | frozenset[str]) -> list[str]:
    """Filtered token list for a single text (stopwords + short tokens dropped)."""
    return [t for t in _TOKEN_RE.findall((text or "").lower()) if t not in stop]


def text_terms(
    title: str,
    abstract: str,
    *,
    extra_stopwords: set[str] | frozenset[str] = frozenset(),
) -> set[str]:
    """Extract the DOCUMENT term set (unigrams + adjacent bigrams) from a paper's
    title+abstract. Returns a set (document-frequency semantics: one vote per doc).

    Drops stopwords, tokens <2 chars, and — via an alpha-ratio guard on the title —
    documents whose title is mostly non-ASCII (non-English), which would otherwise
    yield garbage terms. Title and abstract are tokenized separately so bigrams
    never span the title→abstract seam. Author/venue are intentionally NOT passed in.
    """
    title = title or ""
    if _alpha_ratio(title) < 0.6:
        return set()
    stop = _STOPWORDS | set(extra_stopwords)
    terms: set[str] = set()
    for tokens in (_tokens(title, stop), _tokens(abstract, stop)):
        terms.update(tokens)
        for a, b in zip(tokens, tokens[1:], strict=False):
            terms.add(f"{a} {b}")
    return terms


def _paper_id(paper: dict) -> str:
    """A stable id for merging breakdowns into candidates. Falls back to object
    identity when a paper has no external id."""
    return str(paper.get("arxiv_id") or paper.get("doi")
               or paper.get("source_id") or id(paper))


@dataclass
class RunContext:
    """Everything a provider needs about the current run that isn't the corpus."""
    topic_id: str
    today: date
    data_dir: Path
    transport: Any = None           # httpx.MockTransport in tests; None in prod


@runtime_checkable
class TrendSignal(Protocol):
    name: str

    def prepare(self, corpus: list[dict], topic: Any, ctx: RunContext) -> Any:
        """Called once per topic per run. Bounded I/O. Returns opaque state.
        May raise -> the scorer skips this source and logs it."""
        ...

    def score(self, paper: dict, state: Any) -> float | None:
        """Cheap, pure, per-paper. Returns 0..1 or None (no signal for this paper)."""
        ...

    def refine_top_slice(self, papers: list[dict], state: Any) -> dict[str, float]:
        """Optional per-paper engagement lookups for the top slice.
        Returns {_paper_id: bump_0_to_1}. No-op providers return {}."""
        ...
