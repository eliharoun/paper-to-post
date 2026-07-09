# Email Newsletter Writing Guide (Digest Channel)

## What this channel is

The newsletter channel is a **daily digest**, not a per-paper post. For one topic on
one day, `scripts/newsletter.py` gathers **all** that day's bundled posts (up to 5
papers) and emits **one** email-ready document — Markdown **and** a ~600px responsive
HTML shell — that a human pastes into an email client. **The tool does not send email.**
The artifact is the deliverable.

So this guide is about writing **one skimmable digest email built from up-to-5 paper
blurbs**, in the same sharp-explainer register as the carousel guide, tuned for the
inbox. Think **TLDR / Morning Brew**: a reader should get the gist of all 5 papers in
about a **5-minute skim** and click through to the one or two that matter to them.

**Who you're writing for** (same as the carousel): curious professionals who *apply*
knowledge — engineers, PMs, clinicians, analysts, founders. Smart, not specialists in
the field, won't reproduce the study. You are their filter. Register: Quanta / Ars
Technica / Stratechery. Real terms, briefly glossed; no hype; honest about limits.

## Fields the tool has today (and what it renders)

Per paper, from `post.json`:

| Field | Used for |
|---|---|
| `plain_english_headline` | the item headline |
| `one_sentence_summary` | the item blurb (falls back to `why_it_matters`) |
| `why_it_matters` | fallback blurb / basis for a "why it matters" line |
| `source_url` | the "Read the paper" link (**mandatory**) |
| `source_title` | headline fallback |

Per paper it renders: `N. headline` → one-sentence summary → an optional "Why it
matters" line → "Read the paper →".

**Digest-level, from the CLI / the topic's newsletter config in `config/topics.yml`:**

| Option | Source | What it does |
|---|---|---|
| `--subject` | you author it | inbox subject line (rides along as an HTML comment) |
| `--preheader` | you author it | inbox preview text (hidden preheader div in the HTML) |
| `--intro` | you author it | one-line TL;DR under the header |
| `title` | config / `--title` | H1 header (default `"Research Digest"`) |
| `max_posts` | config / `--max-posts` | cap how many items the digest shows (default: all) |
| `sort` | config / `--sort` | `position` (selection order) or `confidence` (high→low) |
| `min_confidence` | config / `--min-confidence` | drop items below `low`/`medium`/`high` |
| `show_why_it_matters` | config / `--no-why-it-matters` | toggle the per-item line |
| `footer` | config / `--footer` | closing line (e.g. a forward/reply nudge) |

The `max_posts`/`title`/`sort`/`min_confidence`/`show_why_it_matters`/`footer` options
are read from the topic's `newsletter` entry when you pass `--topic <id>`; a CLI flag
overrides config. The three inbox strings (`--subject`, `--preheader`, `--intro`) are
**always** LLM-authored per this guide — there's no config default for them.

The notes marked `[TOOL CHANGE]` below documented these as proposals; they are now
implemented, so treat them as "here's why this option exists," not "to-do."

---

## Science-communication ethics (carried over — non-negotiable)

These are identical to the carousel/caption rules. The digest is shorter, so they matter
*more* per word, not less.

- **Banned hype terms** (validator-style): `cure`, `proven`, `guaranteed`, `miracle`,
  `breakthrough`, `game-changing`, `doctors recommend`, `everyone should`,
  `eliminates risk`, `100%`, `no risk`. Don't use them in a subject line, preheader,
  intro, headline, or blurb unless the source's own wording explicitly supports it (rare).
  Subject lines are the highest-temptation spot — resist.
- **Correlation ≠ causation.** Never imply a cause the source doesn't establish. In a
  one-sentence blurb this usually means choosing verbs carefully: "linked to" / "predicts"
  / "is associated with" — not "causes" — unless the study is a controlled intervention.
- **Be honest about the science's limits.** You often won't have room for a full limits
  clause in every blurb, but never *hide* a limit to make a headline pop (don't turn
  "in mice" into an implied human result, don't turn "in simulation" into "in the field").
- **Keep it about the science, not the publication.** No "preprint", "not yet peer
  reviewed", "awaiting review", "pending publication" anywhere in the email. Spend the
  space on the finding. (Just never *claim* peer-review that didn't happen.)
- **No consumer/clinical advice.** Don't recommend treatments, dosages, supplements, or
  behavior changes.
- **"Not medical advice" line** — include a single brief footer line **only when the
  digest contains genuinely medical/clinical content** (patients, disease, therapy,
  diagnosis, cancer, dementia, drugs). Skip it for basic science. One line in the footer
  covers the whole digest; don't repeat per item.
- **Every item links to its paper.** The `source_url` "Read the paper" link is mandatory
  on every item — it's the whole point of the digest and the reader's only path to the
  primary source.

---

## Subject line

The single highest-leverage line in the whole email — it decides the open. **Our tool
uses the account title as the H1 header only and has no subject field.** Recommend the
LLM write a real subject line.

### What the 2025 data says

- **Short wins, decisively.** beehiiv's 2025 State of Email Newsletters (52,809
  newsletters, 15.6B emails) found subject lines of **≤20 chars averaged a 37.6% open
  rate vs. 28.7% for 80+ chars**, with open rates dropping notably past ~40 chars.
  beehiiv's own recommendation: **under ~40 characters**; Twilio/SendGrid's 2025 guidance
  is even tighter — **2–4 words**.
- **Mobile truncates hard.** Most opens are mobile, and mobile inboxes show only the
  **first ~33–50 characters** (iPhone 33–41; Android 35–50); desktop shows ~70 (Gmail),
  ~50–70 (Outlook), ~46 (Yahoo). **Front-load meaning into the first ~35 characters.**
- **Questions and specificity pull opens**; generic labels ("Important", "Please read")
  and vague hype hurt. A concrete number or named subject beats an adjective.
- **Spam triggers cost you the inbox**, not just the open: avoid `free`, `guarantee`,
  money phrasing, ALL CAPS, and excessive `!!!`.
- **Emoji:** the data is favorable (beehiiv cites materially higher opens), but for a
  serious science-explainer brand, one leading emoji max, and only if it fits the voice.
  Default to none.

### Our recommended subject-line pattern

**Aim for ~30–45 characters, front-loaded, one specific hook.** For a digest of N papers
you have two good patterns:

- **Branded-cadence + count** (predictable, good for a recurring daily): a short standing
  name plus the day's count or lead. Keep the standing name tiny so it doesn't eat the
  mobile window.
  - `AI Bytes: 5 papers, 1 that matters`
  - `Bio Digest · agents that debug themselves`
- **Lead-with-the-best-finding** (higher curiosity, best when one paper clearly leads):
  pull the sharpest single finding from the top-ranked paper into the subject; let the
  rest be the reward inside.
  - `LLMs flunk real government data`
  - `Cut the KV cache 8× with no quality hit`

Rule of thumb: if one paper is clearly the standout, **lead with it**; if the set is
even, use the **branded-cadence + count**. Never pad to a hype adjective to fill space —
a short concrete line outperforms a long vague one.

**Good vs. bad:**

| Bad | Why | Better |
|---|---|---|
| `🚀 BREAKTHROUGH: 5 Amazing AI Papers You NEED To Read Today!!!` | hype term, ALL-CAPS spam trigger, 60+ chars, truncated on mobile, no substance | `5 CS papers · one predicts agent failure` |
| `Today's newsletter` | generic, zero curiosity, wastes the open | `Shrink the KV cache 8×` |
| `A curated selection of this week's most important research findings` | 66 chars, front-loads nothing, reads as filler | `Bio Digest · a 3-agent prover cracks it` |

> `[TOOL CHANGE]` The tool has no subject field. Recommend `newsletter.py` accept a
> `--subject` arg (and/or write it into the `.md` as a top comment / the `.html` as a
> commented block for easy copy-paste). The **LLM must author one new string: the subject
> line**, derived from the day's headlines/summaries (typically the top-ranked paper's
> `plain_english_headline` compressed to ≤45 chars).

---

## Preheader / preview text

The preview text is the snippet shown next to/under the subject in the inbox — **the
inbox's second line of persuasion**, and today our tool produces none (so the client
auto-fills it with "July 8, 2026 · 5 papers", which wastes it).

### What it is and why it matters

- Preview text is part of the inbox "envelope" (from-name + subject + preview). It
  measurably lifts opens (Litmus cites an ~8% open lift from adopting it) and, left blank,
  gets auto-filled from your first body text — often junk like an alt tag or "View in
  browser".
- **AI inbox summaries** (Apple, Gmail/Gemini, Yahoo) now sometimes *replace* the preview
  with a generated summary. Best defense: lead with live text (not images), and keep the
  subject + preview genuinely informative so the summary has good material.

### Length and how it complements the subject

- **Keep it ~40–90 characters**, front-loaded (mobile cuts it off).
- **Complement, don't repeat, the subject.** The subject hooks; the preview *extends* —
  add the second-most-interesting item or the concrete number the subject teased.

### Our recommended preheader pattern

Use the preview to **tease the breadth or the second-best item** the subject didn't spend:
give the reader a reason to open beyond the single hook.

- Subject: `LLMs flunk real government data`
  Preheader: `Plus: an 8× smaller KV cache and a math-prover agent team`
- Subject: `AI Bytes · 5 papers today`
  Preheader: `A probe that predicts agent failure after round one`

**Good vs. bad:**

| Bad | Why |
|---|---|
| *(blank)* → client shows "July 8, 2026 · 5 papers" | wastes the strongest real-estate; date is not a reason to open |
| `Read our newsletter to learn more about today's papers` | repeats the subject's job, says nothing specific |
| `LLMs flunk real government data — new benchmark shows…` | just re-states the subject; no new information |

> `[TOOL CHANGE]` Recommend `newsletter.py` accept a `--preheader` arg and inject it as a
> **hidden preheader div** at the top of the HTML body:
> `<div style="display:none;max-height:0;overflow:hidden;opacity:0">…</div>` (optionally
> padded with a zero-width-space run so body text doesn't leak into the preview). The
> **LLM must author one new string: the preheader (~40–90 chars)** that complements the
> subject.

---

## Digest structure (the body)

A multi-item digest is skimmable only if it's **ruthlessly consistent**: same shape for
every item, strong hierarchy, generous whitespace, one action per item. This is the
TLDR/Morning Brew formula — a themed, headline-plus-tight-summary list a reader clears in
~5 minutes.

### Recommended order

1. **Header** — the account `--title` (H1) + `--date · N papers`. *(Have today.)*
2. **One-line TL;DR intro** — a single sentence orienting the reader to the day's set:
   the theme, or "the one to read first." This is the digest equivalent of Morning Brew's
   opening line and it materially lifts scan-through. *(New — see `[TOOL CHANGE]`.)*
   - e.g. *"Five from CS today, heavy on making LLM agents cheaper and more reliable — start with the failure-prediction probe."*
3. **N items** (up to 5), each in the fixed shape below, separated by a rule/whitespace.
4. **Footer** — a single soft footer CTA + (if medical content) the "not medical advice"
   line. *(Partly new.)*

### The per-item shape (fixed)

```
N. [Headline — the finding in plain English]
[1–3 sentence blurb: what's new + the concrete number/name.]
Why it matters: [one clause — who this changes something for.]   ← optional line
Read the paper →
```

- **Headline** = `plain_english_headline`. Must work standalone in a skim: a finding, not
  a topic. "LLMs ace toy tables and stumble on real government data" > "A new benchmark".
- **Blurb** = `one_sentence_summary`, ideally carrying the paper's headline number/name.
- **"Why it matters"** = an optional one-clause line drawn from `why_it_matters` — the
  practitioner payoff. Keep it to a single clause so it stays scannable, not a paragraph.
- **Link** = "Read the paper →" on `source_url`. Descriptive link text, never "click here".

### Per-item length

**One to three sentences per item — most items should be one or two.** A digest of 5
papers lives or dies on brevity; TLDR's whole value is the ≤5-minute skim. Guidance:

| Element | Length | Notes |
|---|---|---|
| Headline | ≤ ~70 chars | one line on mobile; reuse the carousel headline discipline |
| Blurb | **1–2 sentences, ~25–45 words** | must contain one concrete number or named method |
| "Why it matters" | ≤ ~1 short sentence / 15 words | optional; drop it rather than pad |
| Whole item | ≤ ~4 lines rendered | if it needs more, it belongs in the carousel, not here |
| Whole email | ~5-min skim, ≤ ~5 items | the digest is a *menu*, the paper is the meal |

Do **not** try to reproduce the carousel's 5 content cards in the email. The email's job
is to make the reader *pick* and *click* — the depth lives on the paper (and the carousel).

> `[TOOL CHANGE]` Two optional additions, both requiring **new LLM-authored copy**:
> (a) a **digest `intro`/TL;DR** string (one sentence) — `newsletter.py` renders it under
> the header; (b) a per-item **`why_it_matters` line** rendered as a distinct "Why it
> matters:" line (the field already exists in `post.json`; the tool just doesn't surface
> it separately today). Both are low-risk, high-value. If you add neither, the current
> headline + one-sentence-summary + link is a valid minimal digest.

---

## Scannability & formatting (email-specific)

Email is not the web — clients are inconsistent, and most reads are a mobile thumb-scroll.
The current HTML shell (max-width 600px, system fonts, single column) is already right;
these rules keep the *copy* scannable within it.

- **Single column, ~600px.** NN/g finds multicolumn layouts read as "cluttered"; single
  column "feels clean and streamlined." Keep it.
- **Strong hierarchy with real semantic tags.** Headline in `<h2>`, blurb in `<p>` — not
  size-styled `<div>`s — so screen readers and "skim" both work.
- **Short paragraphs + whitespace.** One idea per paragraph; let items breathe with a rule
  or margin between them. Dense blocks get skipped in the inbox.
- **Bold lead-ins sparingly.** The headline already leads each item; a bold "Why it
  matters:" label is fine, but don't bold whole sentences (reads as shouting / hurts
  scanning).
- **Left-align body copy.** Centered multi-line copy forces the reader to hunt for each
  line's start (an accessibility problem, esp. dyslexia). Center only the H1/date if you
  like.
- **Mobile-first sizing.** Body ~15–16px, headline ~18px, tap targets big enough for a
  thumb. (Current inline styles already do this.)
- **Dark mode: ~35% of opens are in dark mode.** Don't hard-code black text on a white box
  that inverts badly. Prefer near-neutral colors that survive inversion; don't rely on a
  white background to create contrast for dark text. Test one send in dark mode before
  adopting a template change.

---

## Deliverability & spam avoidance (writing choices)

Most of this is copy, not infrastructure — the writer controls it.

- **Avoid spam-trigger words and formatting**: `free`, `guarantee`, money phrasing, ALL
  CAPS words, excessive `!!!`/`$$$`. This overlaps the hype ban — a win-win.
- **Keep a healthy text-to-image ratio.** The digest is text-first by design; that's good
  for deliverability and for AI inbox summaries. Never build the email as one big image.
- **Meaningful `alt` text on any image**; `alt=""` for purely decorative ones (otherwise
  screen readers read the file URL). Today the digest is text-only — keep it that way
  unless a paper image adds real value.
- **Plain-text-friendly.** The Markdown artifact is the plain-text fallback; make sure it
  reads well on its own (it already mirrors the HTML). Real links, not "click here."

---

## CTA norms

- **One primary action per item: "Read the paper →"** on the `source_url`. That's the
  only per-item CTA — don't stack "share/subscribe/reply" onto each item; it dilutes the
  click and clutters the skim. Descriptive text ("Read the paper"), never "click here".
- **At most one soft footer CTA** for the whole email — a single line inviting a reply or
  forward ("Know someone who'd want this? Forward it along.") is fine. Keep it to one line.
- Automated/curated digests earn their clicks on the *items*; a wall of footer CTAs is a
  deliverability and clutter liability, not a lift.

---

## Length & tone for retention (2026)

- **Short and consistent retains.** The winning digest format (TLDR, ~40% open rate) is a
  ≤5-minute skim with a fixed shape every day. Consistency of *format* is itself a
  retention feature — readers learn the shape.
- **Tone:** sharp, plain, confident, un-hyped. The same voice as the carousel, minus the
  space — every word earns its place. Lead with the finding, gloss one term if needed,
  give one real number, get out of the way.
- **The email is a menu, not the meal.** Its success metric is a click to the right paper,
  not time-on-email. Write to help a busy professional *choose*.

---

## Worked example (fictional paper)

**Subject line** (~38 chars, front-loaded, one concrete hook):
`A probe predicts agent failure round one`

**Preheader** (~55 chars, complements — teases breadth, no repeat):
`Plus: an 8× smaller KV cache and a math-prover agent team`

**Digest intro / TL;DR** (one line):
*Five from CS today, mostly on making LLM agents cheaper and more reliable — start with the failure-prediction probe.*

**One digest item:**

> **1. An agent's hidden state reveals it's doomed after round one**
> Lightweight probes on an LLM agent's internal activations flag eventual episode failure from the very first round, letting the system abort early and save ~47% of inference compute on the failing runs.
> **Why it matters:** cheap early-exit for anyone running agent workloads at scale.
> [Read the paper →](https://arxiv.org/abs/2607.06503)

*(Note the ethics in action: "flag" / "predicts", not "guarantees"; the concrete number
(~47%) is scoped to "the failing runs," not overclaimed; no hype term; no publication-status
talk; the paper link is present.)*

**Footer** (only if the digest had medical content, one line):
*This digest summarizes research for general interest and is not medical advice.*

---

## Sources

Guidance synthesized from 2024–2026 email-platform and UX research: beehiiv 2025 State of
Email Newsletters (subject-length open-rate data); Twilio/SendGrid 2025 (subject-line length
and per-client truncation); Litmus 2024–2025 (preview text, accessibility, dark-mode share);
Omnisend (preheader length); Paved/TLDR 2024–25 (digest curation and skim time); Nielsen
Norman Group 2017 (newsletter UX, single-column). Newsletter best-practices shift slowly, so
2024–2025 platform data is current for 2026.
