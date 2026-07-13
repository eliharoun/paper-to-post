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
3. **`.env` present** — `cp .env.example .env` if missing. API keys are optional but improve results. Instagram publishing goes through the Composio CLI (`~/.composio/composio`), which must be authenticated with each account's connection (aliases set per topic in `config/topics.yml`). See the README "Composio setup" section for the one-time CLI/auth steps.

The installed console commands (`research-gather`, `research-validate`, `research-render`, `research-bundle`, `research-newsletter`, etc.) resolve project files relative to the repo automatically. If preconditions can't be met, stop and tell the operator what's missing — don't improvise around a broken environment.

## Workflow

**A full run does every enabled topic: for each, produce enough posts to feed its channels, then deliver to every channel in its `publish` list.** Process topics in sequence.

**Volume is a channel decision, not a topic decision.** A topic says *what to gather*; each channel's **`max_posts`** in the `publish` list says *how many it publishes*. So you **produce as many posts as the greediest enabled channel wants** (`TopicConfig.max_posts_needed()` — the largest `max_posts`; `None` if any enabled channel is uncapped → produce every paper that clears the bar), then each channel publishes its own `max_posts` cut. Never hardcode "5."

For each topic, do a **Gather → Select-N** pass once, then the **per-post pipeline (read → write → validate → render → bundle)** for each selected paper, then **Deliver** to each configured channel. Track it with a todo list. `$ACC` is the topic's `account` id, `$TOPIC` its `id`, `$D` the date `YYYY-MM-DD`, `$N` the post number `1..N`. Per-post dirs are `outputs/$D/$ACC/postN/run/` and `.../postN/assets/`, delivered to `outputs/$D/$ACC/postN/`.

Read the per-channel volume from config once, up front:
```bash
python -c "from scripts.lib.config import load_topics
t=[x for x in load_topics().topics if x.id=='$TOPIC'][0]
print('produce N =', t.max_posts_needed())   # None => every paper that clears the bar
for c in t.publish_targets(): print(' ', c.channel, 'max_posts=', c.max_posts)"
```

### A. Gather (once per topic)
Run the **topic-agnostic gather orchestrator** — it reads the topic's `sources` block, runs exactly those sources, paginates each to full coverage, dedupes, and filters to ranked `candidates.json` (delivered papers already dropped). You do **not** call individual fetchers or know which sources a topic uses:
```bash
research-gather --topic $TOPIC --date $D --out outputs/$D/$ACC
```
It prints per-source counts and writes `outputs/$D/$ACC/candidates.json`. A single flaky source (e.g. a rate-limited API) is logged and skipped, not fatal; it only fails if *every* source fails. If `candidates.json` is empty, skip this topic (see "Skip a topic"). (arXiv/PubMed exhaust the window; OpenAlex/Crossref are keyword sources bounded to the newest pages and log to stderr if they truncate a long tail.)

### B. Select the top N (your judgment, once per topic)
Let **N = `max_posts_needed()`** for this topic (the greediest channel's `max_posts`; if it's `None`, N = every candidate that clears the bar). Load `references/scoring-rubric.md`. Score the top ~15–25 candidates 0–100 (apply the **scroll test** — what would a curious professional stop for). **Rank them and take the best N that clear `MIN_SCORE_TO_POST` (default 70) and aren't already delivered.** Pick *distinct, non-redundant* papers (avoid two near-identical results — spread the interest).

**Clear each post dir before writing it** so a leftover `post.json`/`selected_paper.json`/`paper_page.jpg` from a previous run can never bleed into this one (a stale `post.json` = the wrong paper's post rendered under this slot):
```bash
for N in $(seq 1 <N>); do rm -rf outputs/$D/$ACC/post$N; mkdir -p outputs/$D/$ACC/post$N/run; done
```
Then write each `outputs/$D/$ACC/postN/run/selected_paper.json` for `N=1..N`, **ranked best-first** (post1 is the strongest) — channels that publish fewer than N take the top slice, so order matters.

**Quality gate over volume:** if fewer than N clear the bar, produce only that many — do NOT lower the threshold to force N. If none clear it, skip this topic ("Skip a topic").

### C–E. Per-post pipeline (repeat for each selected post N)
For each `postN`, run the same pipeline the project has always used, in its own `postN/` dirs.

**For a large run (N ≳ 3, or multiple topics), dispatch one subagent per post** rather than doing them all in your own context. Each post requires reading a full paper (often tens of thousands of tokens), and doing 10–15 in sequence yourself risks exhausting context mid-run. The posts are fully independent (separate `postN/` dirs), so give each subagent the exact steps 1–5 below for its one `postN`, and have it report back only a short status (headline, validation exit 0?, screenshot yes/no, card count, issues) — never the post body. Then you verify all bundles and handle delivery. Steps per post:

1. **Read the full paper.** `research-paper-text --paper postN/run/selected_paper.json --out postN/run/paper_text.txt`. Read it — for arXiv/OA this is the whole paper; use it for the real detail, the number that matters, the mechanism. (Closed-access falls back to the abstract; the printed `source` says which.)
2. **Write** (`references/instagram-writing-guide.md` + `references/headline-style-guide.md` + `references/post-schema.md`) → `postN/run/post.json`, for **curious professionals who apply knowledge, not researchers**. Card 1 is the `title` card — its `heading` is the headline and the single most important line in the post (it's the thumbnail that earns the scroll-stop). **Write it per `references/headline-style-guide.md`**: catchy, relatable, and honest — a specific number or a real tension, a strong verb scaled to the evidence, no jargon/acronyms on the title card, and every de-jargoned word still motivated by its referent (don't orphan a metaphor like "looking" by dropping the "vision model" it referred to). It must pass the guide's honesty firewall (species in the subject for animal studies, "linked to" not "causes" for observational work, no banned hype terms) and stay ≤70 chars. Each content card `heading` is a **question** answered by its `body` **with a specific fact from the paper** (a number, a named method/gene/model, or the real mechanism — mined from the full text, not vague framing). **Apply the writing guide's "Card-to-card momentum & density" rules**: write the spine sentence first and break it into one-idea-per-card, escalate the question headings into a curiosity ladder, end most cards on a small open loop (hide the how/why, never the whether), make card 2 a standalone hook (Instagram re-serves from it), and keep bodies short — the 280-char limit is a ceiling, not a target, and the strongest cards are the shortest. **Include a "does it actually work?" results card carrying the paper's concrete numbers.** Include a `source` card; do NOT author a screenshot card (the paper first-page screenshot is inserted automatically by `research-bundle` just before the source card — authoring one would duplicate it and break the card count). **Keep every card and the caption about the science — never mention preprint / peer-review / publication status** (`is_preprint` is metadata only). Caption line 1 is the hook (before the ~125-char fold); the caption stays on the topic for insight/depth, MUST include the article link (`source_url` as a full `https://…` line), a save/share CTA + a question, and 3–5 hashtags.

   The `post.json` (cards + Instagram caption) is the base artifact. **Channel-specific copy is written per channel, not shared** — the caption is tuned for Instagram and must NOT be reused verbatim on LinkedIn or in the newsletter. LinkedIn copy is authored at delivery time (step F, from `references/linkedin-writing-guide.md`); the newsletter digest reads the `post.json` fields (`plain_english_headline`, `one_sentence_summary`, `why_it_matters`) and its style is governed by `references/newsletter-writing-guide.md`. Only author the channel copy for channels this topic actually publishes to.
3. **Validate (HARD GATE).** `research-validate --post postN/run/post.json --paper postN/run/selected_paper.json --account $ACC`. Exit 1 → read `errors[]`, fix `post.json` without adding facts, re-run (≤3 attempts). If it still fails, **drop this paper and promote the next-best candidate** from step B into `postN`. Never render while validation fails.
4. **Render.** `research-screenshot --paper postN/run/selected_paper.json --out postN/run/paper_page.jpg --account $ACC` — screenshots arXiv/OA papers, and for DOI papers it auto-looks-up a legal open-access PDF via Unpaywall (needs a real `CONTACT_EMAIL`). `not_eligible` is normal for genuinely paywalled papers with no free copy. Then `research-render --post postN/run/post.json --out postN/assets --account $ACC --motif-key "$D-$N"` (the `$D-$N` motif key varies the backdrop across the day's posts). Exit 3 → shorten the offending card, re-validate, re-render.
5. **Bundle.** `research-bundle --post postN/run/post.json --paper postN/run/selected_paper.json --assets-dir postN/assets --screenshot postN/run/paper_page.jpg --out outputs/$D/$ACC/postN --date $D` → inserts the screenshot second-to-last, renumbers, writes `caption.txt` + `post.json`, records the paper in the ledger.

### F. Deliver to each configured channel (config-driven)
**Deliver only after ALL of a topic's posts are produced (validated + bundled).** Produce is reversible; publishing to Instagram/LinkedIn is not. Finishing production first means a mid-publish interruption can never leave you with a half-built post live. Deliver to **every channel in that topic's `publish` list** — do not assume Instagram. **Each channel publishes only its own `max_posts` cut** of the produced posts (the top slice, since post1 is strongest); an uncapped channel publishes all of them. Read the channels + their config from `config/topics.yml`:
```bash
python -c "from scripts.lib.config import load_topics
t=[x for x in load_topics().topics if x.id=='$TOPIC'][0]
for c in t.publish_targets(): print(c.channel, c.alias, c.username, c.max_posts)"
```
For each channel, run its publisher over its top `max_posts` bundles (`MAX` below = that channel's `max_posts`; if it's `None`/unset, use the number of bundles produced).

**Publish ONE post per command — never loop multiple carousels in a single shell call.** An 8-card carousel takes ~20–30s (child uploads → carousel → publish → verify); a loop of several blows past the default 120s command timeout and leaves you unsure which posts went live. Both publishers are **idempotent**: on success they write `published.json` (IG) / `linkedin_published.json` (LinkedIn) into the bundle dir, and a re-run with that file present **skips and reports `already-published`** — so re-running after an interruption is safe and will not double-post. If you're ever unsure what actually posted (Instagram has no delete API), probe read-only first: `~/.composio/composio run -f scripts/check_published.mjs -- --account "$ALIAS"`.

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

### G. Report
After all topics, show the operator a summary: per topic, how many posts were produced vs. the target N (e.g. "CS: produced 5/5"), each post's title + score + whether a screenshot was included, and — per channel — how many that channel published (its `max_posts` cut) with the **Instagram/LinkedIn permalinks** and the **newsletter file paths**. Note any topic or channel skipped and why.

### Skip a topic
If a topic has no candidate clearing the bar (or all fail validation), don't post for it. Write `outputs/$D/$ACC/SKIPPED.txt` with the reason and tell the operator. A skipped topic is a correct outcome — never force weak posts to hit 5.

## Quick reference

Run from the repo root with the venv active. Every script also accepts `--help`. Exit codes: `0` ok; `1` validation failed; `2` external API/usage error; `3` render/overflow. `$D` = date, `$ACC` = topic's account id, `$TOPIC` = topic id, `$N` = post number (1..N, where N is the topic's greediest channel `max_posts`). Gather is **once per topic**; the per-post steps run **per post** in `postN/` dirs; deliver runs **once per channel**, each over its own `max_posts` cut.

| Task | Command |
|---|---|
| **Gather (once per topic)** | `research-gather --topic $TOPIC --date $D --out outputs/$D/$ACC` (runs the topic's configured sources → dedupe → filter → `candidates.json`) |
| Full paper text (per post) | `research-paper-text --paper outputs/$D/$ACC/post$N/run/selected_paper.json --out outputs/$D/$ACC/post$N/run/paper_text.txt` |
| **Validate (gate)** | `research-validate --post outputs/$D/$ACC/post$N/run/post.json --paper outputs/$D/$ACC/post$N/run/selected_paper.json --account $ACC` |
| Paper screenshot (to run/) | `research-screenshot --paper outputs/$D/$ACC/post$N/run/selected_paper.json --out outputs/$D/$ACC/post$N/run/paper_page.jpg --account $ACC` |
| Render cards | `research-render --post outputs/$D/$ACC/post$N/run/post.json --out outputs/$D/$ACC/post$N/assets --account $ACC --motif-key "$D-$N"` |
| Assemble bundle | `research-bundle --post outputs/$D/$ACC/post$N/run/post.json --paper outputs/$D/$ACC/post$N/run/selected_paper.json --assets-dir outputs/$D/$ACC/post$N/assets --screenshot outputs/$D/$ACC/post$N/run/paper_page.jpg --out outputs/$D/$ACC/post$N --date $D` |
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
