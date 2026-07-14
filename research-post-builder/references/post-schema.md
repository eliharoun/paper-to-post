# Generated Post JSON Schema

Write `run/post.json` to match this schema exactly. `validate_post.py` enforces it. All fields are required except `hero_image_prompt` (optional).

```json
{
  "paper_id": "string — the selected paper's id/key",
  "source_title": "string — must match the paper title (or a close normalized form)",
  "source_url": "string — must match the stored paper URL",
  "is_preprint": true,
  "plain_english_headline": "string",
  "one_sentence_summary": "string",
  "why_it_matters": "string",
  "what_they_did": "string",
  "what_they_found": "string",
  "important_context": "string",
  "limitations": ["string — at least one"],
  "avoid_saying": ["string — phrases you deliberately avoided, e.g. 'cure'"],
  "carousel_cards": [
    {
      "card_number": 1,
      "card_type": "title|hook|finding|method|context|limitation|source|next",
      "heading": "string (<=70 chars) — for content cards this is a QUESTION",
      "body": "string (<=280 chars) — empty for the title card",
      "footer": "string (<=90 chars)"
    }
  ],
  "caption": "string (<=2200 chars)",
  "hashtags": ["string — aim for 3-5 specific tags; max 8 (Instagram's Rule of 5)"],
  "alt_text": "string",
  "confidence": "low|medium|high",
  "hero_image_prompt": "string (optional) — art-director prompt for the front-card hero image"
}
```

## Field notes

- **`source_title` / `source_url`** must match the selected paper — the validator does a normalized-title and URL grounding check. Copy them from `selected_paper.json`, don't paraphrase.
- **`is_preprint`** is **metadata only** — set it to match the paper, but **do not surface publication status in any caption or card**. It exists so the validator can reject a false "peer-reviewed" claim; it is not something to write about. Keep the caption and cards about the science, never about preprint/peer-review status.
- **`carousel_cards`** count must be between `brand.min_cards` (5) and `brand.max_cards` (7), numbered sequentially from 1. **Card 1 must be `card_type: "title"`** (headline in `heading`, source line in `footer`, empty `body`) — its `heading` is the front-card thumbnail headline. That `heading` is overlaid on the AI **hero image** when one is generated (see `hero-image-guide.md`), or on the branded **motif** backdrop as the fallback; either way the `heading` you write is the text that ships. Content cards use question `heading`s (see instagram-writing-guide). Include a `source` card. The paper first-page screenshot is inserted automatically before the source card at render time — you do not author a screenshot card.
- **`limitations`** must be non-empty — state the *scientific* limits of the finding (sample size, cell line, simulation, scope, association-not-causation). Do **not** list "preprint / not peer reviewed" as a limitation; that's publication status, not a limit of the science.
- **`confidence`** is your honest read of how well the source supports the framing.
- **`hero_image_prompt`** (optional) is the art-director prompt for the front-card hero image, authored per `hero-image-guide.md` and the topic's `hero_style.style` (in `config/brand.<account>.yml`). `research-hero` renders it into `card_01.jpg`. If absent, or if hero generation fails, the front card falls back to the branded motif backdrop.

## Validation the script runs (so write to pass it the first time)

- Valid JSON, matches this schema, all required fields present.
- Card count 5–7; per-card heading/body/footer length limits; caption ≤ 2200; hashtags ≤ 8.
- No banned hype terms (see instagram-writing-guide) unless flagged as source-supported.
- No em/en dashes (`—` / `–`) in any heading, body, or caption (they read as AI-generated) — use commas, colons, parentheses, or two sentences.
- Grounding: `source_title`/`source_url` match the paper; no "peer-reviewed" claim on a preprint; claims must trace to the paper (full text or abstract).
- **Caption contains the article link:** the paper's `source_url` must appear verbatim in the `caption` text. A caption without the link fails validation.
- Readability: average sentence length ≤ 26 words per card (dense technical sentences are fine; academic run-ons are not).
- Health guardrails on the guarded topic: a "not medical advice" disclaimer is required **only when the content is actually medical/clinical** (patients, disease, therapy, diagnosis, cancer, dementia, etc.) — basic science (evolution, plant biology, pure genomics) does not need it. Treatment/dosage/supplement advice phrasing is never allowed on the guarded topic.
