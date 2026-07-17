# Newsworthiness Scoring Rubric

Score each candidate 0–100 using **only** the provided title, abstract, and metadata. Do not use outside knowledge about the paper, authors, or field. If the abstract doesn't say it, it doesn't count.

## The scroll test (apply first)

Before scoring, ask: **would a science-literate person stop scrolling for this?** The best picks have a hook a normal person feels in one line — a surprising result, a "wait, AI can't do that?", a health finding that touches everyday life, a number that defies intuition. A technically solid but inward-facing paper (yet another incremental benchmark, a narrow method tweak, a single-institution retrospective chart review) is a weak pick even if its rule-score is high. Rule-score reflects recency/citations/length; **you** judge whether it's genuinely interesting to a scrolling human. Favor the interesting-and-sound paper over the citation-heavy-but-dull one.

## Dimensions (sum to 100)

| Dimension | Points | What earns points |
|---|---:|---|
| Public relevance & pull | 25 | A scrolling person immediately gets why it's interesting or matters. High for surprising, counterintuitive, or life-relevant results; low for inward-facing incrementalism. **Includes a shareability read: would a reader forward this to a specific colleague ("you need to see this")?** DM sends/shares are a top-weighted 2026 distribution signal, so a finding with genuine social currency or direct practical utility for a role (a tool someone uses, a belief it overturns) scores toward the top of this band; a merely tidy result sits lower. Keep it honest, never chase virality. |
| Story quality / hook | 15 | There's a strong, honest one-line hook and a narrative arc. This is weighted up — a great hook is what stops the scroll. |
| Novelty | 15 | A genuinely new finding, method, dataset, or perspective — not incremental. |
| Evidence clarity | 15 | The abstract clearly states what was done and what was found, ideally with concrete numbers. |
| Freshness | 10 | Recently published/updated within the lookback window. |
| Visual carousel fit | 10 | Explainable in 5–7 substantive cards. |
| Safety / low hype risk | 10 | Can be explained accurately without dangerous overclaiming. |

## Trendiness signal (advisory input)

Each candidate in `candidates.json` may carry a `score_breakdown.trendiness` (0–1),
with `trend_terms` (the bursting terms that drove it) and `trend_signals` (per-source
contributions: `corpus_burst`, `hackernews`, `gdelt`, `huggingface`).

Use it as **corroborating evidence for the Public relevance & pull and Story quality /
hook dimensions** — a high trendiness with sensible `trend_terms` suggests the subject
is resonating right now, which strengthens a scroll-stop. **Weigh it, do not obey it:**

- Trendiness never overrides the honesty firewall or the safety caps. A trending-but-weak
  or trending-but-unsound paper is still skipped.
- Sanity-check `trend_signals` before trusting a high score. A GDELT-driven spike can come
  from an unrelated news event that happens to share a keyword; discount it if `trend_terms`
  don't actually match the paper's contribution.
- `trend_basis: cluster` means the rolling history was too short (cold start) — the signal
  is weaker; lean more on your own read. `insufficient_corpus` means no trendiness was
  computed; ignore the field.

Trendiness is one input to the same 0–100 judgment, not a separate gate.

## How to score

1. For each dimension, assign points against the descriptions above. Be strict on evidence clarity and safety.
2. Sum to a 0–100 total.
3. Note any **red flags** (see below). A red flag caps the total or disqualifies.

## Red flags (penalize hard or disqualify)

- Health/medical treatment, dosage, or supplement claims when the health topic is disabled → disqualify.
- Findings that only hold for animals/cells/simulations but are framed as human-relevant → cap safety at 0–3.
- Purely a benchmark/leaderboard result with no general-reader angle → cap public relevance at 0–5.
- Correlational result likely to be misread as causal → cap safety and note it.
- Survey/review with no clear new takeaway → cap novelty at 0–5.
- Abstract too vague to state what was actually found → cap evidence clarity at 0–3.

## Threshold

Post only if the top candidate scores **≥ MIN_SCORE_TO_POST** (advisory `.env` knob, default 70 — you honor it by judgment; no script enforces it). If nothing clears the bar, skip the day. Do not round up a 68 to a 70 to justify posting.

## What to record

For the selected paper, keep a one-line rationale and the dimension breakdown so the run is auditable (include it in `selected_paper.json` under a `score` field if convenient).
