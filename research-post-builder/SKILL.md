---
name: research-post-builder
description: Use when the operator wants to turn recent research papers into ready-to-publish posts — e.g. "run the daily research posts", "build today's science posts", "make the research carousels". For each configured topic, produces the top posts from recent papers (how many is a per-channel `max_posts` setting) and delivers to that topic's channels (Instagram carousel, LinkedIn post, and/or email newsletter digest) via Composio. Topics, paper sources, and publishing channels are all read from config. Orchestrates deterministic gather/filter/render scripts and performs the scoring and writing judgment directly.
license: MIT
---

# Research Post Builder

## Overview

For each configured topic, produce the day's **top posts** from recently published research papers — accurate, plain-but-substantive — and **deliver each to that topic's channels** (Instagram carousel, LinkedIn post, and/or email-newsletter digest). **How many posts is a per-channel decision** (each channel's `max_posts`), not a fixed number. Topics, paper sources, and publishing channels are all defined in `config/topics.yml`; the shipped config has two example topics (CS, biology).

This is a **hybrid** workflow. Deterministic work (fetching papers, deduping, filtering, validating, rendering images) is done by the project's Python scripts. **You** do the judgment: reading candidates, scoring newsworthiness, picking the paper, and writing the carousel — because you are the language model this pipeline runs on. You never re-implement the scripts; you call them and you do the thinking between them.

**Core principle:** never render or deliver a post until the validation script exits 0. It is a hard gate that protects against hype, ungrounded claims, and length violations. If it fails, fix the post JSON and re-run it — do not skip it.

## Everything is config-driven (topics, sources, channels)

**This skill is agnostic of topics, paper sources, and publishing channels — all of it comes from `config/topics.yml`.** Never hardcode a topic id, a source, a category/subfield, or an account handle in your commands; read them from config. The shipped config has two example topics (CS, biology) — but the workflow below works unchanged for any topic you add.

Each topic entry defines:
- `id`, `account` (selects branding via `config/brand.<account>.yml`), `display_name`, `priority`.
- `keywords` + `hard_excludes` — used by the filter to assign/reject papers.
- `sources:` — **which paper sources run** (only the ones listed). Each carries its own params (arXiv `categories`, OpenAlex `subfields`, per-source `query`, labs `labs`, etc.). The `research-gather` command reads this block and runs exactly those sources — you never call individual fetchers.
- `publish:` — **a list of channels** this topic delivers to (`instagram`, `linkedin`, `newsletter`), each with its own config (e.g. Composio `alias`/`username`). You loop over this list at delivery time.

**By default a run does EVERY enabled topic**, and for each, publishes to EVERY enabled channel in its `publish` list. Only narrow it if the operator explicitly asks (e.g. "just the CS posts", "Instagram only"). To discover the topics and their channels, read config:
```bash
python -c "from scripts.lib.config import load_topics
for t in load_topics().enabled_topics():
    print(t.id, t.account, '| sources:', t.sources.active(),
          '| channels:', [c.channel for c in t.publish_targets()])"
```

## When to use this skill

Use this skill when:
- The operator asks to run/produce/generate the research posts or science carousels from recent papers.
- The operator wants a recent paper found and turned into an Instagram-ready bundle.

Do NOT use this skill when:
- The operator wants engagement analytics, or wants to work on the pipeline's code.

## Core concepts

- **Split of labor.** Scripts = deterministic (parsing, hashing, length checks, banned-term matching, image geometry). You = judgment (newsworthiness, writing, grounding). Never blur these.
- **The hard gate.** The validation script exits non-zero on any schema/length/hype/grounding failure. Rendering is forbidden until it exits 0. This keeps the "no bad post" guarantee independent of your judgment.
- **Fail forward.** A bad candidate → try the next. No good candidate → skip the day. Never force a weak post.
- **Publishing goes to the right account or not at all.** Instagram publishing selects the account with the Composio `account` key and **pre-verifies the resolved username before uploading**. There is no delete API, so a misroute is unrecoverable except by manual deletion — the guard is mandatory, not optional. See `references/instagram-publishing.md`.

## Setup & preconditions

Run all commands from the **repo root** with the project's environment active (`. .venv/bin/activate`, or invoke via `.venv/bin/python`). Before running anything:

1. **Confirm you're at the repo root** — `scripts/`, `config/`, and `templates/` exist here.
2. **Environment installed.** If a command isn't found or a script raises `ModuleNotFoundError`, run `make install` then `python -m playwright install chromium`.
3. **`.env` present** — `cp .env.example .env` if missing. API keys are optional but improve results. **`GOOGLE_API_KEY` is the on/off switch for the front-card hero image** (Gemini image generation; requires billing enabled): without it, `research-hero` fails and every front card falls back to the branded motif backdrop — expected, not a bug, but set it if you want hero images. Instagram publishing goes through the Composio CLI (`~/.composio/composio`), which must be authenticated with each account's connection (aliases set per topic in `config/topics.yml`). See the README "Composio setup" section for the one-time CLI/auth steps.

The installed console commands (`research-gather`, `research-validate`, `research-render`, `research-bundle`, `research-newsletter`, etc.) resolve project files relative to the repo automatically. If preconditions can't be met, stop and tell the operator what's missing — don't improvise around a broken environment.

## Workflow

**A full run does every enabled topic: for each, produce enough posts to feed its channels, then deliver to every channel in its `publish` list.** Process topics in sequence.

**Volume is a channel decision, not a topic decision.** A topic says *what to gather*; each channel's **`max_posts`** in the `publish` list says *how many it publishes*. So you **produce as many posts as the greediest enabled channel wants** (`TopicConfig.max_posts_needed()` — the largest `max_posts`; `None` if any enabled channel is uncapped → produce every paper that clears the bar), then each channel publishes its own `max_posts` cut. Never hardcode "5."

For each topic, do a **Gather → Select-N** pass once, then the **per-post pipeline (read → write → validate → render → bundle)** for each selected paper, then **Deliver** to each configured channel. Track it with a todo list. `$ACC` is the topic's `account` id, `$TOPIC` its `id`, `$D` the date `YYYY-MM-DD`, `$N` the post number `1..N`. Per-post dirs are `outputs/$D/$ACC/postN/run/` and `.../postN/assets/`, delivered to `outputs/$D/$ACC/postN/`.

Read the per-channel volume **and the hashtag bank** from config once, up front — the bank must be handed to each writer (a dispatched subagent won't otherwise see it):
```bash
python -c "from scripts.lib.config import load_topics
t=[x for x in load_topics().topics if x.id=='$TOPIC'][0]
print('produce N =', t.max_posts_needed())   # None => every paper that clears the bar
for c in t.publish_targets(): print(' ', c.channel, 'max_posts=', c.max_posts)
print('hashtag_bank =', t.hashtag_bank)"      # pass these tags into each post's brief
```

### A. Gather (once per topic)
Run the **topic-agnostic gather orchestrator** — it reads the topic's `sources` block, runs exactly those sources, paginates each to full coverage, dedupes, and filters to ranked `candidates.json` (delivered papers already dropped). You do **not** call individual fetchers or know which sources a topic uses:
```bash
research-gather --topic $TOPIC --date $D --out outputs/$D/$ACC
```
It prints per-source counts and writes `outputs/$D/$ACC/candidates.json`. A single flaky source (e.g. a rate-limited API) is logged and skipped, not fatal; it only fails if *every* source fails. If `candidates.json` is empty, skip this topic (see "Skip a topic"). (arXiv/PubMed exhaust the window; OpenAlex/Crossref are keyword sources bounded to the newest pages and log to stderr if they truncate a long tail.)

### B. Select the top N (your judgment, once per topic)
Let **N = `max_posts_needed()`** for this topic (the greediest channel's `max_posts`; if it's `None`, N = every candidate that clears the bar). Load `references/scoring-rubric.md`. Select in **two passes**:

1. **Abstract shortlist.** Score all candidates 0–100 from title+abstract (apply the **scroll test** — what would a curious professional stop for), and take a shortlist of ~`2×N` (min 8) top scorers that aren't already delivered.
2. **Full-text re-rank.** For each shortlisted paper, fetch the full text (`research-paper-text --paper <its candidate JSON> --out /tmp/shortlist_<id>.txt`) and re-score — the abstract is written for reviewers and routinely buries the most interesting result (a stunning number in Section 4, a surprising ablation), or oversells a thin one. This especially matters for bio, where the best papers often have dense abstracts. **Prefer papers whose full text is available**: an open-access paper you can mine for concrete numbers makes a far stronger post than a paywalled one you can only write from the abstract — apply a penalty when full text is unreachable. Then **take the best N that clear `MIN_SCORE_TO_POST`** (advisory `.env` knob, default 70 — honored by your judgment, not enforced by any script).

Pick *distinct, non-redundant* papers (avoid two near-identical results — spread the interest across sub-areas so the day's set isn't monotone). (The per-post pipeline's step 1 re-reads the winner's full text into its own `postN/run/` dir — the shortlist fetch here is only for selection judgment.)

**`candidates.json` shape (so you don't waste a step rediscovering it):** a list of `{paper, topic_id, filter_status, filter_reasons, rule_score, llm_score, final_score, score_breakdown}`. The `paper` object holds `title`/`abstract`/`source`/`doi`/`arxiv_id`/etc. **`final_score` is `0` for every entry unless an LLM scorer is configured** (usually not), so do NOT sort by it and assume it means anything — the ranking is **your** judgment via the rubric. `rule_score` reflects only recency/length and clusters near a ceiling, so it doesn't separate the interesting from the dull either. Read titles+abstracts and score them yourself. Sources skew by topic: arXiv dominates CS; PubMed/OpenAlex/bioRxiv dominate bio (bioRxiv/medRxiv are the freshest preprints).

**Clear each post dir before writing it** so a leftover `post.json`/`selected_paper.json`/`paper_page.jpg` from a previous run can never bleed into this one (a stale `post.json` = the wrong paper's post rendered under this slot):
```bash
for N in $(seq 1 <N>); do rm -rf outputs/$D/$ACC/post$N; mkdir -p outputs/$D/$ACC/post$N/run; done
```
Then write each `outputs/$D/$ACC/postN/run/selected_paper.json` for `N=1..N`, **ranked best-first** (post1 is the strongest) — channels that publish fewer than N take the top slice, so order matters. **Write the full candidate object** (the entire `{paper, topic_id, filter_status, filter_reasons, rule_score, ...}` dict from `candidates.json`, not a trimmed `{title, id}`) — every downstream script (`research-paper-text`, `research-validate`, `research-screenshot`, `research-render`, `research-bundle`) reads fields from it and a partial object breaks them.

**Quality gate over volume:** if fewer than N clear the bar, produce only that many — do NOT lower the threshold to force N. If none clear it, skip this topic ("Skip a topic").

### C. Per-post pipeline (steps 1–6, repeat for each selected post N)
For each `postN`, run the same pipeline the project has always used, in its own `postN/` dirs. **All commands run from the repo root** (per Setup); paths below are the full `outputs/$D/$ACC/postN/...` so they resolve regardless of cwd. `$D`/`$ACC`/`$TOPIC` and this post's `N` must be set — a dispatched subagent is given all of them plus its `postN` path.

**Series edition number (`$EP`).** Compute it ONCE per topic (all of the day's posts share it) before dispatch and pass it to every post's render + bundle:
```bash
EP=$(python -c "from scripts.lib.store import Ledger; print(Ledger().edition_number('$ACC', '$D'))")
```
Thread `--episode $EP` into both `research-hero` and `research-render` (it renders the "Series Name · #$EP" front-card eyebrow when the brand enables it; harmless if disabled), and `--account $ACC` into `research-bundle` (records the account so tomorrow's edition number is correct). A dispatched subagent is given `$EP` along with its other vars.

**For a large run (N ≳ 3, or multiple topics), dispatch one subagent per post** rather than doing them all in your own context. Each post requires reading a full paper (often tens of thousands of tokens), and doing 10–15 in sequence yourself risks exhausting context mid-run. The posts are fully independent (separate `postN/` dirs), so give each subagent the exact steps 1–6 below for its one `postN`, and have it report back only a short status (headline, validation exit 0?, front card = hero or motif fallback?, screenshot yes/no, card count, issues) — never the post body. **Do not trust the status report alone: a dispatched subagent can stop mid-run (even reporting "completed" with zero work done), so after the batch, run `research-verify-bundle` (step 6) yourself for every `postN` and re-dispatch any that fail before delivery.** Then handle delivery. Steps per post:

1. **Read the full paper.** `research-paper-text --paper outputs/$D/$ACC/postN/run/selected_paper.json --out outputs/$D/$ACC/postN/run/paper_text.txt`. Read it — for arXiv/OA this is the whole paper; use it for the real detail, the number that matters, the mechanism. (Closed-access falls back to the abstract; the printed `source` says which.)
2. **Write** → `outputs/$D/$ACC/postN/run/post.json`, for **curious professionals who apply knowledge, not researchers**. Read `references/instagram-writing-guide.md` + `references/headline-style-guide.md` + `references/post-schema.md` first, then author the fields in these sub-steps. (This is the most-failed step; work through 2a–2e and the checklist rather than writing it all in one pass.)

   - **2a — Title card (card 1, `card_type: "title"`).** Its `heading` IS the headline: the single most important line, the thumbnail that earns the scroll-stop. Per `references/headline-style-guide.md`: catchy, relatable, honest — a specific number or a real tension, a strong verb scaled to the evidence, ≤70 chars, **no jargon/acronyms**, and every de-jargoned word still motivated by its referent (don't orphan a metaphor like "looking" by dropping the "vision model" it referred to). Empty `body`. It must pass the honesty firewall (species in the subject for animal studies, "linked to" not "causes" for observational work, no banned hype).
   - **2b — Content cards (question → answer).** Each content card `heading` is a **question**; its `body` answers it **with a specific fact from the paper** (a number, a named method/gene/model, or the real mechanism — mined from the full text, not vague framing). Apply the writing guide's "Card-to-card momentum & density" rules: write the spine sentence first and break it into one-idea-per-card; escalate the questions into a curiosity ladder; end most cards on a small open loop (hide the how/why, never the whether); **make card 2 a standalone hook** (Instagram re-serves from it — it must make sense to someone who never saw card 1); keep bodies short (the 280-char limit is a ceiling, not a target; the strongest cards are the shortest). **Include a "does it actually work?" results card carrying the paper's concrete numbers** — use `card_type: "finding"` for it.
   - **2c — Source card.** Include one `source` card (`card_type: "source"`): its `heading` is the paper's **full title** (this card is the sole exception to the "heading is a question" rule), body = first author et al./year, venue/identifier. Do **NOT** author a screenshot card — the paper first-page screenshot is auto-inserted by `research-bundle` just before the source card; authoring one duplicates it and breaks the count.
   - **2d — Caption + engagement fields.** Author three discrete fields the caption is built from (see the writing guide's caption structure): **`takeaway`** (the portable, screenshot-worthy one-liner = caption line 1, drives saves), **`debate_question`** (a short opinion question, drives comments), and **`share_cta`** (**required** — a role-specific "send this to the [role] who…" line with a send/share/tag verb; the validator rejects an empty or verb-less one). Compose them into the `caption` in order: takeaway → depth → nuance → debate question → article link (`source_url` as a full `https://…` line, mandatory) → share CTA → ("Not medical advice" only if medical). Put **3–5 mid-tail hashtags from the topic's `hashtag_bank` in the `hashtags` field** (the pipeline appends them — do NOT inline tags in the caption prose). Never mention preprint/peer-review/publication status.
   - **2e — `hero_image_prompt`.** Author one per `references/hero-image-guide.md`, the topic's `hero_style.style`, and its `hero_style.concept_guidance` if set (`config/brand.$ACC.yml`): a single concrete, literal scene caught mid-action depicting the paper's **actual subject** (guide rule #1), NOT an abstract metaphor, grounded in the full paper — no text/diagrams in the image, and keep the **bottom ~40% of the frame calm and dark** for the headline overlay. Always attempt one (omit only if the subject is so abstract no concrete scene fits without violating "show the thing"); on omission or generation failure the front card falls back to the branded motif. The front card overlays the **title card's `heading`** in both hero and motif cases — the prompt describes background imagery only, never text.

   **MUST-PASS checklist before validating (these are the recurring failures):**
   - [ ] No banned hype terms **anywhere including the caption** — full list in 2b of step 3 below.
   - [ ] `source_title` copied **verbatim** from `selected_paper.json` (incl. LaTeX like `$\times$`); `source_url` matches too.
   - [ ] Exactly title + content cards + one `source` card. **No** authored screenshot card.
   - [ ] Results card present with the paper's real numbers.
   - [ ] Caption contains the full `https://…` `source_url` line.
   - [ ] Card 2 works as a standalone hook.
   - [ ] `share_cta` is present and contains a send/share/tag verb (validator **errors** without it), and `takeaway`/`debate_question` are authored.
   - [ ] `hashtags` field holds 3–5 mid-tail tags from the topic's `hashtag_bank` (not inlined in the caption).
   - [ ] Every card `footer` is `""` (footers are auto-generated).

   The `post.json` (cards + Instagram caption) is the base artifact. **Channel-specific copy is written per channel, not shared** — the caption is tuned for Instagram and must NOT be reused verbatim on LinkedIn or in the newsletter. LinkedIn copy is authored at delivery time (step D, from `references/linkedin-writing-guide.md`); the newsletter digest reads the `post.json` fields (`plain_english_headline`, `one_sentence_summary`, `why_it_matters`) and its style is governed by `references/newsletter-writing-guide.md`. Only author the channel copy for channels this topic actually publishes to.

   **2f — Self-critique before validating (quality gate, not schema).** Re-read your drafted `post.json` once as a skeptical reader and fix anything that fails: (1) Would you stop scrolling for the title card? (2) Does card 2 stand alone as a hook? (3) Is there a real open loop pulling card→card (no card resolves everything)? (4) Is the one quotable number given its own card, leading the card, not buried? (5) Does the "why it matters" card call back to the hook? (6) Would you DM this to a specific colleague? Validation (step 3) only checks schema/hype/length — it cannot catch a dull post. Rewrite weak cards here, before the gate.
3. **Validate (HARD GATE).** `research-validate --post outputs/$D/$ACC/postN/run/post.json --paper outputs/$D/$ACC/postN/run/selected_paper.json --account $ACC`. Exit 1 → read `errors[]`, fix `post.json` without adding facts, re-run (≤3 attempts). If it still fails, **drop this paper and promote the next-best candidate** from step B into `postN`. Never render while validation fails.

   **Pass on the first try — the recurring trip-ups (avoid these while writing, not on retry):**
   - **Banned hype terms** anywhere, including the caption — the validator's full list: `cure`, `proven`/`proves`, `guaranteed`, `miracle`, `breakthrough`, `revolutionary`, `game-changer`/`game-changing`, `doctors recommend`, `everyone should`, `eliminates risk`, `no risk`, `100%`. Write "shown"/"demonstrated"/"suggests" from the start; don't smuggle "proven" into a limitation or caption line, or "eliminates risk"/"no risk" into a health claim.
   - **`source_title` must match the paper's stored title** — the grounding check compares case- and punctuation-insensitively (after stripping `[vN]` version markers and collapsing whitespace), but the safe move is to **copy it verbatim** from `selected_paper.json`, including any LaTeX like `$\times$`. Paraphrasing or dropping words fails the check.
   - **Average sentence length cap** (~26 words) on card bodies: if a body reads long, split it into two sentences rather than trimming meaning.
   - **Card count is fixed by the pipeline:** author title + content + `source` only; the screenshot card is auto-inserted. Don't author a screenshot card.
4. **Render.** `research-screenshot --paper outputs/$D/$ACC/postN/run/selected_paper.json --out outputs/$D/$ACC/postN/run/paper_page.jpg --account $ACC` — screenshots arXiv/OA papers, and for DOI papers it auto-looks-up a legal open-access PDF via Unpaywall (needs a real `CONTACT_EMAIL`). `not_eligible` is normal for genuinely paywalled papers with no free copy. **Then generate the hero front card:** `research-hero --post outputs/$D/$ACC/postN/run/post.json --out outputs/$D/$ACC/postN/assets --account $ACC --hero-out outputs/$D/$ACC/postN/run/hero.png --episode $EP`. Exit 0 → the hero wrote `card_01.jpg`, so render the content cards from index 2: `research-render --post outputs/$D/$ACC/postN/run/post.json --paper outputs/$D/$ACC/postN/run/selected_paper.json --out outputs/$D/$ACC/postN/assets --account $ACC --motif-key "$D-$N" --episode $EP --start-index 2`. Any non-zero `research-hero` exit (2 = hero disabled, 3 = no `hero_image_prompt`, 4/5 = generation failed **or the front-card text failed the contrast QC check**) is a **graceful motif fallback, not an error to fix** → render every card including the motif title card from index 1: `research-render --post outputs/$D/$ACC/postN/run/post.json --paper outputs/$D/$ACC/postN/run/selected_paper.json --out outputs/$D/$ACC/postN/assets --account $ACC --motif-key "$D-$N" --episode $EP` (the `$D-$N` motif key varies the backdrop across the day's posts). **Always pass `--paper`**: it makes the card footers deterministic — the title/hero card gets no footer and every other card shows `Source · Month D, YYYY` (the paper's source and full publication date), computed from `selected_paper.json`, not authored by you. A **`research-render` exit 3** is a generic render failure (distinct from `research-hero`'s exit 3). Validated posts (body ≤280 chars) fit the card, so overflow is not expected; if exit 3 fires, first check the environment (e.g. is Chromium installed via `python -m playwright install chromium`?), and only if a card genuinely looks too long, shorten it, re-validate, and re-render.

   **Front-card legibility is enforced (two layers).** The compositor draws a soft dark halo behind the headline + account label so they read on any background, and runs a **contrast QC check**: if the imagery behind the text is too light/similar (e.g. a bright object drifted into the lower third), `research-hero` exits non-zero and the post falls back to the motif — a *worse* outcome than a good hero. So the `hero_image_prompt` must keep the **entire lower third dark, empty, and low-detail** (see `references/hero-image-guide.md`); a bright/accent-coloured lower third loses the hero. If a post falls back only because of contrast, consider re-running `research-hero --concept "<prompt that forces the subject into the upper half and an empty dark bottom half>"` once before accepting the motif.
   **Re-rendering the front card is cheap — you rarely need to regenerate the image.** The raw AI image is saved at `run/hero.png`. Any change to *text* (headline wording, font size, layout, halo, scrim) can be re-applied by re-compositing from that saved PNG (call `hero.composite_front_card` on the existing `run/hero.png`) — instant and free. Only a change to the *imagery itself* needs a new Gemini call (`research-hero --concept "…"`), which costs a generation. Don't pay for regeneration just to resize or reposition text.
5. **Bundle.** `research-bundle --post outputs/$D/$ACC/postN/run/post.json --paper outputs/$D/$ACC/postN/run/selected_paper.json --assets-dir outputs/$D/$ACC/postN/assets --screenshot outputs/$D/$ACC/postN/run/paper_page.jpg --out outputs/$D/$ACC/postN --date $D --account $ACC` → inserts the screenshot second-to-last, renumbers, writes `caption.txt` + `post.json`, records the paper in the ledger (with `--account` so the per-account edition number stays correct).
6. **Verify the bundle (artifact gate).** `research-verify-bundle --dir outputs/$D/$ACC/postN --account $ACC`. Exit 0 → the bundle is real and complete (manifest, `post.json`, `caption.txt` with the paper link, and contiguous `card_01..card_0N` within the account's bounds). Exit 1 → the bundle is missing or incomplete; read `errors[]` and re-run the failed step (or re-dispatch the post) before delivering. **This is a mandatory backstop for the dispatch model:** a subagent can report "done" yet have died mid-run without writing anything, and validation (step 3) only proves the `post.json` was sound, not that render/bundle actually ran. Never publish a post whose verify did not exit 0.

### D. Deliver to each configured channel (config-driven)

**Bundle-completeness gate (parent re-verifies).** The dispatched subagents each ran verify in step 6, but a silently-dead subagent can report success without writing anything — so the parent re-runs it once here, for every post, before presenting: for `N in 1..N`, `research-verify-bundle --dir outputs/$D/$ACC/postN --account $ACC` (must exit 0). Any failure = that post's production didn't finish; re-dispatch or re-run the failed step before going further. (This is the single authoritative verify pass; step 6 is the subagent's own self-check.)

**Front-card review gate (before publishing).** For each post, the parent reads `outputs/$D/$ACC/postN/run/post.json` to get the headline (`carousel_cards[0].heading`) and the `hero_image_prompt`, and checks whether `outputs/$D/$ACC/postN/run/hero.png` exists (present = hero front card; absent = motif fallback). Present each post to the operator: the `card_01.jpg` path, the headline, hero-vs-motif, and the `hero_image_prompt`. The operator responds per post:
- **approve** → keep as-is.
- **regenerate** → re-run `research-hero` for that post (optionally with a tweaked prompt via `--concept "<new prompt>"`), then re-bundle that post and re-present.
- **reject-to-motif** → rebuild the front card from the motif: `research-render --post outputs/$D/$ACC/postN/run/post.json --paper outputs/$D/$ACC/postN/run/selected_paper.json --out outputs/$D/$ACC/postN/assets --account $ACC --motif-key "$D-$N" --start-index 1`, then re-bundle that post (step 5).

Only publish posts the operator has approved. This gate is the reason production and publishing are separate — heroes are AI-generated and must be eyeballed before they go live.

**Grid-cohesion check (part of the review gate).** Before presenting, also render a mosaic of the day's + recent front cards so the operator judges the *profile grid* (what a visitor sees in the follow-decision moment), not just individual cards: `research-grid-preview --account $ACC --out outputs/$D/$ACC/grid_preview.jpg`. Show it alongside the per-post cards. If the grid looks incoherent (wildly different color/composition across cards), the fix is the hero color-grade (`hero_style.grade_strength` in `config/brand.$ACC.yml`), not per-post regeneration.

**Unattended / auto-approve runs.** The gate holds by default: if no operator is available to approve (e.g. a scheduled run) and the request did **not** authorize auto-publishing, STOP after bundling and report that the posts await front-card approval — do not publish. Publish without the gate **only** when the operator's request explicitly authorizes it (e.g. "auto-approve", "auto-publish", "publish without review", "hands-off run"); in that case treat all front cards as approved and proceed to deliver.

**Deliver only after ALL of a topic's posts are produced (validated + bundled) and the front cards are approved.** Produce is reversible; publishing to Instagram/LinkedIn is not. Finishing production first means a mid-publish interruption can never leave you with a half-built post live. Deliver to **every channel in that topic's `publish` list** — do not assume Instagram. **Each channel publishes only its own `max_posts` cut** of the produced posts (the top slice, since post1 is strongest); an uncapped channel publishes all of them. Read the channels + their config from `config/topics.yml`:
```bash
python -c "from scripts.lib.config import load_topics
t=[x for x in load_topics().topics if x.id=='$TOPIC'][0]
for c in t.publish_targets(): print(c.channel, c.alias, c.username, c.max_posts)"
```
For each channel, run its publisher over its top `max_posts` bundles (`MAX` below = that channel's `max_posts`; if it's `None`/unset, use the number of bundles produced).

**Publish ONE post per command — never loop multiple carousels in a single shell call.** An 8-card carousel takes ~20–30s (child uploads → carousel → publish → verify); a loop of several blows past the default 120s command timeout and leaves you unsure which posts went live. Both publishers are **idempotent**: on success they write `published.json` (IG) / `linkedin_published.json` (LinkedIn) into the bundle dir with `status: "confirmed"`, and a re-run with that file present **skips and reports `already-published`** — so re-running after an interruption is safe and will not double-post. **`status: "pending"` (IG)** means a prior run published to the API but crashed before confirming — the post is **very likely LIVE**, so the script **aborts with exit 1** instead of re-posting. Do NOT delete the marker and re-run. Instead probe read-only (`~/.composio/composio run -f scripts/check_published.mjs -- --account "$ALIAS"`): if the post is live, hand-edit `published.json` to `{"status":"confirmed","media_id":"…"}`; only if it is genuinely NOT live may you remove the marker and re-run. If you're ever unsure what actually posted (Instagram has no delete API), always probe first.

- **`instagram`** — one carousel per post. Read `references/instagram-publishing.md` (the account-selection rule is mandatory). The script selects the account with the Composio `account` key and **verifies the resolved username before uploading anything**; there is no delete API, so never bypass the guard. Publish each bundle in its **own** command (do not loop):
  ```bash
  # ALIAS/USER = the instagram target's alias/username from config. Run once per N (1..MAX):
  ~/.composio/composio run -f scripts/publish_instagram.mjs -- \
    --account "$ALIAS" --expect-username "$USER" --dir outputs/$D/$ACC/post1
  # ...then post2, post3, ... each as a separate command.
  ```
  Posts `card_NN.jpg` in order with `caption.txt`; prints `{"ok":true,…,"permalink":…}` (or `{"ok":true,"skipped":"already-published",…}` if re-run). On a username-mismatch abort, **stop** — do not retry with a different key.

- **`linkedin`** — one text post per paper, its own `max_posts` cut. **The guard `username` must be the member `sub`** (from `config/topics.yml`), not the display name — `LINKEDIN_GET_MY_INFO` reliably returns only `sub`, so a name/email guard value causes a false abort. On abort the script prints the resolved `sub`; set the config `username` to it. **First author the LinkedIn copy**: for each of the top `MAX` bundles, read `references/linkedin-writing-guide.md` and write a channel-native post to `outputs/$D/$ACC/post$N/linkedin.txt` (plain text ≤3000 chars — LinkedIn does NOT render Markdown; hook on line 1, the paper's number in the body, the `source_url` in-post, 2–3 hashtags). Do **not** reuse the Instagram caption verbatim; the publisher only falls back to `caption.txt` if `linkedin.txt` is missing, which produces off-register copy. Then publish each bundle in its own command:
  ```bash
  ~/.composio/composio run -f scripts/publish_linkedin.mjs -- \
    --account "$ALIAS" --expect-username "$SUB" --dir outputs/$D/$ACC/post1
  # ...one command per N. Idempotent: re-run skips already-posted bundles.
  ```

- **`newsletter`** — one **digest** across the topic's posts (not per-paper), governed by `references/newsletter-writing-guide.md`. It reads each `post.json`'s `plain_english_headline` / `one_sentence_summary` / `why_it_matters` — so ensure those fields read well as a scannable digest item, not just as carousel copy. Pass **`--topic $TOPIC`** so it picks up that topic's newsletter options from `config/topics.yml` (`max_posts`, title, `sort`, `min_confidence`, `show_why_it_matters`, `footer`) — you don't repeat those on the command line; the digest shows its own `max_posts` cut. **You author three short inbox strings** per the guide: a `--subject` (≤~45 chars, front-loaded), a `--preheader` (~40–90 chars, complements the subject — don't repeat it), and a one-line `--intro` TL;DR. Produces `newsletter.md` + `newsletter.html` ready to paste into email:
  ```bash
  research-newsletter --dir outputs/$D/$ACC --topic $TOPIC --date "$D" \
    --subject "<hook ≤45 chars>" --preheader "<complementary teaser>" --intro "<one-line TL;DR>"
  ```
  (Any of the config options can still be overridden per-run with the matching flag,
  e.g. `--max-posts`, `--sort`, `--min-confidence`, `--no-why-it-matters`, `--footer`,
  `--title`.)

Capture each permalink / artifact path for the report.

### E. Report
After all topics, show the operator a summary: per topic, how many posts were produced vs. the target N (e.g. "CS: produced 5/5"), each post's title + score + whether the front card was a hero image or a motif fallback + whether a screenshot was included, and — per channel — how many that channel published (its `max_posts` cut) with the **Instagram/LinkedIn permalinks** and the **newsletter file paths**. Note any topic or channel skipped and why.

### Skip a topic
If a topic has no candidate clearing the bar (or all fail validation), don't post for it. Write `outputs/$D/$ACC/SKIPPED.txt` with the reason and tell the operator. A skipped topic is a correct outcome — never force weak posts to hit the target N.

### Weekly roundup (optional format, format variety)
Once a week, assemble a **"papers you missed" roundup carousel** per account from the week's already-produced posts (gather-free — it reads the week's `post.json` files, not new papers). It reuses the standard render → bundle → verify → publish path unchanged; it is NOT about a single paper, so it skips paper-grounding validation but still passes schema/length/hype/style.
```bash
research-roundup --account $ACC --dates 2026-07-20,2026-07-21,2026-07-22,2026-07-23,2026-07-24 \
  --title "5 CS papers you missed this week" --out outputs/$D/$ACC/roundup --max-entries 5
```
This writes `outputs/$D/$ACC/roundup/run/post.json` (title + one `finding` card per paper, ranked #1..#N, + a source outro; every paper's link in the caption). Then run the normal pipeline on `outputs/$D/$ACC/roundup`, **omitting `--paper` at every step** (a roundup has no single paper — the scripts accept its absence and skip paper-grounding, screenshot insertion, and the ledger mark):
- **Validate:** `research-validate --post outputs/$D/$ACC/roundup/run/post.json --account $ACC` (no `--paper` → schema/length/hype/style still gate; grounding/caption-link skipped).
- **Render:** `research-render --post outputs/$D/$ACC/roundup/run/post.json --out outputs/$D/$ACC/roundup/assets --account $ACC --motif-key "$D-roundup" --episode $EP` (roundup front card is always the motif — no hero prompt; no `--paper`, so no footers).
- **Bundle:** `research-bundle --post outputs/$D/$ACC/roundup/run/post.json --assets-dir outputs/$D/$ACC/roundup/assets --out outputs/$D/$ACC/roundup --date $D` (no `--paper`, no `--screenshot`, no `--account` — nothing is recorded in the ledger).
- **Verify / review-gate / publish** exactly as for a regular post (`research-verify-bundle` tolerates the missing `selected_paper.json` for a roundup). Needs at least `min_cards - 2` papers that week (3 for the default min of 5), else skip the roundup.

## Quick reference

Run from the repo root with the venv active. Every script also accepts `--help`. Exit codes: `0` ok; `1` validation/verification failed (`research-validate` and `research-verify-bundle` both use `1` for a failed check); `2` external API/usage error; `3` render failure (generic; validated posts don't overflow, so first suspect the environment, e.g. missing Chromium). (`research-hero` is the exception: any non-zero exit — 2/3/4/5 — just means "fall back to the motif front card," never an error to fix; see step 4.) `$D` = date, `$ACC` = topic's account id, `$TOPIC` = topic id, `$N` = post number (1..N, where N is the topic's greediest channel `max_posts`). Gather is **once per topic**; the per-post steps run **per post** in `postN/` dirs; deliver runs **once per channel**, each over its own `max_posts` cut.

| Task | Command |
|---|---|
| **Gather (once per topic)** | `research-gather --topic $TOPIC --date $D --out outputs/$D/$ACC` (runs the topic's configured sources → dedupe → filter → `candidates.json`) |
| Full paper text (per post) | `research-paper-text --paper outputs/$D/$ACC/post$N/run/selected_paper.json --out outputs/$D/$ACC/post$N/run/paper_text.txt` |
| **Validate (gate)** | `research-validate --post outputs/$D/$ACC/post$N/run/post.json --paper outputs/$D/$ACC/post$N/run/selected_paper.json --account $ACC` |
| Paper screenshot (to run/) | `research-screenshot --paper outputs/$D/$ACC/post$N/run/selected_paper.json --out outputs/$D/$ACC/post$N/run/paper_page.jpg --account $ACC` |
| Render hero front card | `research-hero --post outputs/$D/$ACC/post$N/run/post.json --out outputs/$D/$ACC/post$N/assets --account $ACC --hero-out outputs/$D/$ACC/post$N/run/hero.png --episode $EP` (exit 0 → hero wrote `card_01.jpg`; non-zero → fall back to motif) |
| Render cards | `research-render --post outputs/$D/$ACC/post$N/run/post.json --paper outputs/$D/$ACC/post$N/run/selected_paper.json --out outputs/$D/$ACC/post$N/assets --account $ACC --motif-key "$D-$N" --episode $EP` (add `--start-index 2` when the hero wrote `card_01.jpg`; `--paper` makes footers deterministic: source + full pub date, none on the title card) |
| Assemble bundle | `research-bundle --post outputs/$D/$ACC/post$N/run/post.json --paper outputs/$D/$ACC/post$N/run/selected_paper.json --assets-dir outputs/$D/$ACC/post$N/assets --screenshot outputs/$D/$ACC/post$N/run/paper_page.jpg --out outputs/$D/$ACC/post$N --date $D --account $ACC` (`--account` keeps the per-account edition # correct; omit `--paper`/`--screenshot` for a roundup) |
| **Verify bundle (artifact gate)** | `research-verify-bundle --dir outputs/$D/$ACC/post$N --account $ACC` (exit 0 = complete bundle; exit 1 = missing/incomplete, re-run or re-dispatch before delivery) |
| **Publish Instagram** (one command per post) | `~/.composio/composio run -f scripts/publish_instagram.mjs -- --account "$ALIAS" --expect-username "$USER" --dir outputs/$D/$ACC/post$N` |
| **Publish LinkedIn** (one command per post) | `~/.composio/composio run -f scripts/publish_linkedin.mjs -- --account "$ALIAS" --expect-username "$SUB" --dir outputs/$D/$ACC/post$N` (guard = member **sub**) |
| Check what already posted (read-only) | `~/.composio/composio run -f scripts/check_published.mjs -- --account "$ALIAS"` |
| **Newsletter** (digest, once) | `research-newsletter --dir outputs/$D/$ACC --topic $TOPIC --date "$D" --subject "<hook>" --preheader "<teaser>" --intro "<TL;DR>"` (reads max_posts/title/sort/min_confidence/footer from the topic's newsletter config) |

Channels + their `alias`/`username` come from the topic's `publish` list; sources + their params come from the topic's `sources` block — both in `config/topics.yml`. You never pass source queries/categories by hand; `research-gather` reads them.

## Gotchas

- `research-gather` exiting `2` means the topic was unknown or *every* source failed — stop and tell the operator; never invent papers. A single source failing is logged and non-fatal.
- The paper screenshot is gated to arXiv/open-access and rendered to `run/paper_page.jpg`. A `not_eligible`/`fetch_failed` result is normal for paywalled papers — the bundle simply omits it (no screenshot card). Never render it into the assets dir. **Same-day bioRxiv/medRxiv preprints frequently have no fetchable PDF yet**, so `not_eligible` is expected for fresh-preprint topics; those posts are 7 cards, abstract-grounded, and that's correct — not a bug to chase.
- **Semantic Scholar returns HTTP 429 (rate limit) on most keyless runs.** The fetcher already retries with backoff and gather treats a dead source as non-fatal, so the run survives on the other sources — don't re-investigate it each time. Set `SEMANTIC_SCHOLAR_API_KEY` in `.env` if you want that source to contribute reliably.
- **Publish one carousel per command; never loop several in one shell call.** An 8-card carousel takes ~20–30s; a multi-post loop exceeds the 120s command timeout and leaves publish state ambiguous. The publishers are idempotent (write `published.json`/`linkedin_published.json`, skip on re-run), so recovering from an interruption is just re-running each command; use `scripts/check_published.mjs` (read-only) if unsure what went live.
- **LinkedIn guard value = the member `sub`, not the display name.** `LINKEDIN_GET_MY_INFO` reliably returns only `sub`; a `name`/`email` guard value causes a false abort on the correct account. The abort message prints the resolved `sub` to copy into `config/topics.yml`.
- The filter already drops delivered papers, but selection is your responsibility — pick within the topic's subject and double-check nothing is a repeat.
- Match the account to the branding: keep `--account <id>` consistent across a run so the cards render with that account's `account_name` from `config/brand.<id>.yml`.
- **Read topics/sources/channels from config every run — never hardcode them.** Adding or changing a topic, source, or channel is a `config/topics.yml` edit; the skill instructions do not change.
- **Instagram account selection is the `account` key, not `connectedAccountId`.** `connectedAccountId` is silently ignored and falls back to the Composio *default* connection, which can publish to the wrong account. The publish script uses `account` + `--expect-username` and aborts on mismatch. Since there is no delete API, always let the guard run; never bypass it. See `references/instagram-publishing.md`.

## Common mistakes

| Mistake | Fix |
|---|---|
| Rendering before validation passes | Run the validate command to exit 0 first. It is the safety gate. |
| Trusting a dispatched subagent's "done" report without checking its bundle | Run `research-verify-bundle` per post before delivery; a subagent can stop mid-run and still report success. |
| Mixing topics (one topic's paper under another's account, or wrong `--account`) | Keep `$ACC`/`$TOPIC` consistent across every command in the run. |
| Hardcoding topics, sources, or channels in commands | Read them from `config/topics.yml` (`research-gather` for sources; `publish_targets()` for channels). |
| Adding facts not in the abstract when fixing validation errors | Only rephrase/trim; remove claims you can't ground. |
| Lowering the threshold to force a post on a slow day | Skip the topic ("Skip a topic"). A weak post is worse than none. |
| Oversimplifying to grade-school level | Aim slightly above pop-science: real terms, briefly defined. |
| Re-implementing fetch/dedupe/render inline | Call the command — it is tested; your inline version is not. |
| Echoing API keys or credentials | Never print secrets; scripts and the Composio CLI read them from env/their own config. |
| Publishing to Instagram with `connectedAccountId` | Use the `account` key + `--expect-username`; the wrong key silently posts to the Composio default account and there's no delete API. |

## Red flags — STOP

- "This paper is borderline but I'll post it anyway." → Re-score honestly; skip if it doesn't clear the bar.
- "Validation complains about one word, I'll render past it." → No. Fix the JSON, re-run, exit 0.
- "I'll write a punchier headline than the abstract supports." → That's hype. Ground it.
