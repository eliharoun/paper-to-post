# Instagram Carousel Writing Guide

## Who you're writing for

You're writing for **curious professionals who are starting to follow science** — engineers, product managers, clinicians, analysts, founders. They're smart and can handle real terminology, but they are **not researchers in this field and won't reproduce the study**. They want to know *what's happening in the science world and whether it's relevant to them* — not the experimental minutiae they'd only need if they were reviewing the paper.

**You are their filter.** You picked this paper because it's one of the most interesting things published today. These cards are your summary — if it lands, they'll go read the paper themselves. So make it *appealing and useful*, not a methods recap. Favor:

- **The "so what"** over the "how exactly." What changed, what it means, where it might apply — not the ablation tables.
- **Implications a practitioner would act on** ("this could cut inference cost", "this shifts how screening might work") over reproduction detail.
- **One clear idea per card**, framed so a busy person gets it in five seconds.

**You have the full paper text** (when available), not just the abstract — so pull the genuinely interesting detail, the number that matters, the surprising result. Don't pad with generic method description just because it's in the paper.

**Register: a sharp explainer in a serious outlet (Quanta, Ars Technica, Stratechery), not a kids' science account and not a journal abstract.** Use the paper's real terms, gloss the specialist ones in a few words, and never flatten a precise concept into a vague verb.

**Calibration — match the "target," not "too simple":**

| Too simple (avoid) | Target register (use) |
|---|---|
| "a model that reads local image patterns" | "a convolutional neural network, which slides learned filters across the image to pick out local spectral-temporal features" |
| "reading stray tumor DNA in the blood could flag the disease" | "quantifying circulating tumor DNA — fragments tumors shed into plasma — as a non-invasive cancer signal" |
| "they invented fake physics worlds and asked the AI to reason" | "they built counterfactual physics regimes (e.g. F=mv instead of F=ma) to test whether models reason from first principles or pattern-match training data" |
| "the AI couldn't check its own work" | "models failed at self-verification, endorsing their own earlier errors in two-thirds of trials"

Keep sentences readable — the validator caps average sentence length at ~26 words (tuned for this register), so a dense, technical sentence is fine; an academic run-on is not. Density of *ideas* is the goal. If a card trips the cap, split one sentence, don't strip the terminology.

## Science-communication rules

- **Keep it about the science, not the publication.** Do **not** write about publication status — no "preprint", "not yet peer reviewed", "awaiting review", "pending publication" in the caption or on the cards. That meta-commentary adds nothing for the reader; spend the space on the topic instead. (Just never *claim* the work is peer-reviewed when it isn't.)
- **Distinguish correlation from causation.** Never imply a cause the source doesn't establish — this is a scientific limit worth stating, and it's about the finding, not the paper's status.
- **Be honest about the science's limits.** Every post names the real *scientific* limits — small sample, simulation-only, one cell line, animal model, narrow scope, association-not-causation. These add technical depth. Frame it as "how much to trust this finding," not as publication-stage talk and not with the word "caveat."
- **No consumer/clinical advice.** Don't recommend treatments, dosages, supplements, or behavior changes.
- **Absolute over relative risk.** For health content, give absolute risk if the source provides it; don't lead with a scary relative-risk number alone.
- **Keep the domain terms; gloss only the specialist ones.** "mRNA", "sensitivity", "convolutional network", "heteroplasmy" are fine for this audience; add a 3–6 word clause only for terms a professional-but-non-specialist wouldn't know. Never replace a precise term with a vague verb.
- **Use the number that matters.** One concrete figure from the source (effect size, rate, cost, speedup) makes a card credible — but pick the one a practitioner cares about, not every metric in a results table.

## Banned hype terms

Do not use these unless the source's own wording explicitly supports it (rare): `cure`, `proven`, `guaranteed`, `miracle`, `breakthrough`, `game-changing`, `doctors recommend`, `everyone should`, `eliminates risk`, `100%`, `no risk`. The validator will reject them.

## Banned punctuation: no em/en dashes (an "AI tell")

**Never use the em dash (`—`, U+2014), en dash (`–`, U+2013), or horizontal bar (`―`) in any heading, body, or caption.** Real people typing a caption almost never reach for these characters, so they read as machine-generated — and the validator now hard-rejects them. Use everyday punctuation instead:

- **Parenthetical aside** → wrap it in **commas** or **parentheses**: not `806 genomes — the deep-lung cells — stayed mutated`, but `806 genomes (the deep-lung cells) stayed mutated` or `806 genomes, the deep-lung cells, stayed mutated`.
- **A break or reversal** → use a **period** (two sentences) or a **comma**: not `it looks done — but files leak`, but `it looks done, but files leak.`
- **A lead-in to a list or explanation** → use a **colon**: not `one relation — a precondition, a cleanup`, but `one relation: a precondition, a cleanup`.
- Regular **hyphens** in compounds and ranges (`deep-lung`, `37%-70%`, `single-molecule`) are fine — those are hyphen-minus, not dashes.

Write it the way you'd type it in a hurry: short sentences and commas beat a dramatic dash.

## Substance is the point — mine the full text, don't paraphrase the abstract

The single biggest failure mode is a card that *frames* a finding without *delivering* it — "the results are impressive" instead of "detection rose from 37% to 70%." You have the full paper text (step 4). Use it. Every content card must carry **specific, checkable substance**:

- **Concrete numbers** — effect sizes, rates, sample sizes, speedups, %s, F1, counts ("11,692 genes across 2.5M cells", "F1 89.83%", "37%→70%"). At least one card must state the paper's headline number.
- **Named entities** — the actual method name, gene, model, dataset, benchmark, pathway ("D2D distills into a KV-cache cartridge", "validated ZBTB41 and RNF7", "on the Nanopore HCC1395 benchmark"). Name things; don't say "a technique."
- **The specific mechanism** — how it actually works at a useful altitude, not "a clever approach."

If a card could apply to a dozen different papers, it's too vague — rewrite it with a detail only *this* paper contains. Dig the interesting number/name out of the body; the abstract alone is usually too thin.

Also:
- Readable sentences (the validator caps average sentence length), but don't sacrifice a real concept to hit a word count.
- Honest hook — intriguing without overpromising.
- Assume the reader knows what a study, a model, a gene, or an algorithm is. Explain what's *specific and new* here, not the basics.
- Avoid long parenthetical pile-ups in card bodies.

## Card format: lead each card with a question, answer it with substance

**Every content card's `heading` is a plain, punchy question** the reader is already asking; the `body` answers it in 1–3 short sentences **with a specific fact from the paper** (a number, a name, a mechanism). Questions pull the reader card-to-card; substance is what makes them save and go read the paper.

- Good: "Does it actually work?" → *"On two bias types, detection rose from 37% and 33% to 70% and 100%."* · "Which gene turned out to matter?" → *"They flagged and validated ZBTB41 (metabolism) and RNF7 (pluripotency)."*
- Weak (vague framing): "The results are strong." · "It works well." · "A promising approach." · academic labels like "Methodology" / "Results".

Vary the questions per paper — don't mechanically reuse the same seven every time.

## Card footers are auto-generated — leave them empty

**You do not write the `footer` field. Set every card's `footer` to `""`.** At render time the pipeline fills footers deterministically from the paper: the title/hero card gets **no** footer, and every other card shows `Source · Month D, YYYY` (the paper's source/venue and full publication date, e.g. "arXiv · July 15, 2026"). This is computed from `selected_paper.json`, not from anything you type, so a footer you author is ignored and overwritten. Spend zero effort on footers; just leave them as empty strings (the schema still requires the field to be present).

## Card sequence (7 cards)

1. **`title`** — the front/thumbnail card: the headline over the branded backdrop (or hero image). `card_type: "title"`, `heading` = the headline, empty `body`, empty `footer` (the source line is auto-generated, and the title card intentionally gets none). This shows in the grid, so the headline must work as a standalone thumbnail.
2. **What's actually new?** — the core finding in one crisp idea, with the key specific.
3. **How does it work / what did they build?** — the mechanism at a useful altitude, naming the actual method/model/technique. Enough to understand the approach; not a reproduction recipe.
4. **Does it actually work? (the results card)** — **required, and it must contain the paper's concrete numbers**: the headline result, the benchmark, the comparison to prior work. This is the card that proves the post isn't hand-waving. Never skip it.
5. **Why does it matter (to someone like you)?** — the implication for a practitioner: what it could change, enable, or cost. This is the card that earns the save.
6. **How solid is it?** — the honest read on how much to trust *the finding*: sample size, simulation-only, scope, single cell line, animal model, association-not-causation. **Do not mention preprint / peer-review status** — keep this about the science. Frame as a question, never "caveat."
7. **`source`** — full title, first author et al./year, venue/identifier. (The paper first-page screenshot is inserted just before this at render time when available — you don't author it.) Do not add a preprint label.

Aim for 5 content cards + title + source (≤7 total). The physical carousel is: title → content cards → [paper screenshot if available] → source. If a paper genuinely has no numbers (rare — a pure taxonomy or theory paper), the results card instead states the single most concrete outcome (e.g. "revalidated the name *Manis aurita* from genomic + morphological evidence").

## Card-to-card momentum & density (make it swipeable, not just correct)

The card *sequence* above is the skeleton; this is what makes people actually swipe to the
end. The whole carousel is a **swipe machine** — each card must earn the next swipe, and the
reader retains ~one idea per card. Six rules, all of which live *inside* the anti-hype
guardrails (the honesty firewall below is non-negotiable).

- **Write the spine sentence first, then break it into cards.** Before drafting cards, write
  the whole post as *one* sentence — the finding, its mechanism, and its "so what." Its
  natural joints are your cards. This forces **one clear idea per card** and guarantees the
  deck builds instead of listing seven equal facts. Decide up front the **one takeaway** you
  want lodged by tomorrow and the **one quotable number** that carries it — and give that
  number its own card, leading the card, not buried third in a list.
- **Escalate the questions — each heading is the question the previous card just raised.**
  The question headings aren't a fixed checklist; they're a **curiosity ladder**. Card 2's
  answer should make the reader ask exactly what card 3's heading poses ("…new" → "how?" →
  "does it work?" → "so what for me?" → "should I believe it?"). When it's built right, the
  reader swipes because *they* generated the next question.
- **End most cards on a small open loop.** The last line is the highest-leverage spot on a
  card: a resolved card gives the brain permission to leave. End on tension the next card
  closes — a "but here's the catch", a setup whose payoff is next, a counterintuitive turn.
  **Honesty firewall: hide the *how/why*, never the *whether*.** You may defer the mechanism
  or the number across cards; you may never withhold, inflate, or fake the finding itself,
  its magnitude, or its limits to manufacture suspense. Every loop you open must close
  in-deck. The test: *would the paper's authors nod, or wince?*
- **Card 2 must also work as a standalone hook.** Instagram re-serves a carousel starting
  from card 2 to people who scrolled past card 1, so card 2 is a *second* thumbnail — it must
  independently stop the scroll (a sharp finding or a "wait, really?"), not read as a bland
  intro.
- **Spread, don't stack — the strongest cards are the shortest.** Depth comes from the number
  of cards, not the density per card. The 280-char body limit is a *ceiling, not a target*:
  aim ~40 words / ~200 chars, one idea, and let the punchiest cards (the reveal, the quotable
  number) be a single short line. Two ideas hiding behind an "and" = two cards. A card that
  reads as a wall of text gets skipped no matter how correct it is.
- **Anchor the unknown on the known, and pay off the hook.** Open a hard idea from something
  the reader already has in memory ("a model's KV-cache is its short-term memory of the chat
  so far — and it grows every token"), then reattach the real term. Reuse one **through-line
  phrase** across cards so they cohere into a single memory, and on the "why it matters" card
  **call back** to the hook's question/claim to close the loop the title opened.

These are momentum rules, not new cards — apply them *within* the 7-card sequence. Do not add
a "recap" card (it competes with the source/screenshot cards); land the portable takeaway
inside the "why it matters" card instead.

## Per-card limits (validator-enforced)

- Heading ≤ 70 chars.
- Body ≤ 280 chars.
- Footer ≤ 90 chars.

## Caption (required — every post ships a caption, not just images)

The caption format below reflects current (2025–2026) Instagram best-practices for a
general science audience, drawn from Instagram/Adam Mosseri's own guidance plus major
social-marketing sources (Sprout Social, Later, Buffer, Hootsuite).

**The first line is the whole game.** Instagram hides everything after ~125 characters
(about two lines) behind a "…more" button. That first line decides whether anyone reads
on. So:

- **Line 1 = the hook.** A plain-language finding or a curiosity gap that lands before the
  fold. A provocative question, a bold-but-true claim, or an open loop.
- **Never open with** "New study shows…", "We're excited to share…", or "Researchers at…".
  Lead with the *finding in human terms*.

**The caption is about the topic, not the paper's publication status.** Keep it purely
scientific and engaging — give the reader real insight and technical depth so the cards
feel like a natural continuation. **Never mention preprint / peer-review / publication
status in the caption.**

Structure, in order:
1. **Hook line** (≤ ~125 chars, front-loaded — the most important sentence).
2. **Plain-language summary with depth** — what they found, how it works, and why it
   matters, in a few short lines. This is where the reader earns insight; use a concrete
   number or named mechanism, and set up the extra technical depth the cards deliver.
3. **A genuine scientific nuance** (optional but encouraged) — the interesting *scientific*
   limit or subtlety that makes the reader smarter: association-not-causation, one cell
   line, a simulation regime, a surprising trade-off. Frame it as insight into the finding,
   **not** as "it hasn't been peer reviewed."
4. **The article link** — the paper's `source_url` as a full `https://…` URL, e.g.
   `📄 Paper: https://arxiv.org/abs/2406.xxxxx`. **Mandatory** — the validator rejects a
   caption without it. IG captions aren't clickable, so this is plain-text attribution.
5. **A CTA that drives saves/shares** — the signals Instagram now weights most. Prompt a
   **save** ("Save this for later"), a **question** to spark comments, and/or a DM share
   ("Send this to someone who'd find it interesting").
6. **Only for genuinely medical/clinical posts** (disease, patients, therapy, diagnosis, cancer, dementia, drugs), a brief **"Not medical advice"** line. This is a safety line, not publication-status talk. Skip it for basic science (evolution, plant biology, pure genomics) — the validator only requires it when the content is actually medical.

**Hashtags: 3–5, not a wall.** Instagram's own guidance is the "Rule of 5" — 3–5 *specific,
relevant* hashtags, not 30 broad ones. Discovery now comes from **keywords in the caption
text** (Instagram indexes and searches caption/alt text), so write naturally with the terms
a curious person would search ("gene editing", "battery storage", "language models") rather
than stuffing tags. Cap 5; the schema allows up to 8 but fewer-and-relevant wins.

Caption ≤ 2,200 chars — let it breathe for the explanation, but the hook + key takeaway
must read before the "…more" fold. The same `source_url` must appear in both the `caption`
field and the `source_url` field of the post JSON.

## Alt text

Write descriptive `alt_text` summarizing the post's finding for screen readers.
