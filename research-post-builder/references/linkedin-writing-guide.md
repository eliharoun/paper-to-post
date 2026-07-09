# LinkedIn Writing Guide

## What this governs

This guide governs the content of **`linkedin.txt`** — the single plain-text LinkedIn
post the pipeline publishes per paper. If `linkedin.txt` is absent, the publisher
(`scripts/publish_linkedin.mjs`) falls back to the Instagram caption, which is written for
a different medium — so **always write a real `linkedin.txt`**; don't let LinkedIn inherit
Instagram copy.

Hard constraints from the publisher:

- **One text post per paper.** No carousel, no images on the LinkedIn path.
- **≤ 3000 characters** (`MAX_LEN`). The script truncates with an ellipsis if you exceed it —
  never rely on that; write to length.
- **Plain text only.** LinkedIn does **not** render Markdown. `**bold**` shows literal
  asterisks, `# heading` shows a literal `#`, `- ` shows a literal dash. Do not use Markdown
  syntax for emphasis or structure. Use line breaks, plain Unicode, and (sparingly) Unicode
  bullets like `→` or `·` instead.

You are writing for the same audience and under the same science-communication ethics as the
Instagram Carousel Writing Guide (`instagram-writing-guide.md`). Read that guide too — this one only adds the
LinkedIn-specific craft.

## Who you're writing for

**Curious professionals who apply knowledge, not researchers** — engineers, PMs, clinicians,
analysts, founders. They're on LinkedIn between meetings. They're smart, can handle real
terminology, and want to know *what's new in the science and whether it's relevant to their
work* — not the ablation tables.

**Register: a sharp explainer in a serious outlet (Quanta, Ars Technica, Stratechery)** —
never dumbed down, never hype. Use the paper's real terms and gloss the specialist ones in a
few words. The LinkedIn feed rewards a confident, plain-spoken expert voice; it punishes both
jargon-fog and LinkedIn-influencer theatrics ("I was shocked when I read this 🤯").

## Science-communication ethics (carried over — non-negotiable)

These are identical to the carousel guide. They matter *more* on LinkedIn because the post is
one continuous piece of prose with no card structure to hide behind.

- **Keep it about the science, not the publication.** No "preprint", "not yet peer reviewed",
  "awaiting review", "pending publication". Spend the space on the topic. (Just never *claim*
  peer-review that didn't happen.)
- **Correlation ≠ causation.** Never imply a cause the source doesn't establish.
- **Be honest about the science's limits** — small sample, simulation-only, one cell line,
  animal model, narrow scope, association-not-causation. State the real *scientific* limit as
  "how much to trust this," not as a publication-stage disclaimer, and not with the word
  "caveat."
- **No consumer/clinical advice.** No treatments, dosages, supplements, or behavior changes.
- **Absolute over relative risk** for health content.
- **Mandatory paper link, in the post body** (see "Links" below).
- **Only for genuinely medical/clinical posts** (disease, patients, therapy, diagnosis,
  cancer, dementia, drugs): a brief "Not medical advice" line. Skip it for basic science.

### Banned hype terms

Do not use unless the source's own wording explicitly supports it (rare): `cure`, `proven`,
`guaranteed`, `miracle`, `breakthrough`, `game-changing`, `revolutionary`, `doctors
recommend`, `everyone should`, `eliminates risk`, `100%`, `no risk`. LinkedIn's own 2026
guidance also downranks hype-y, low-substance posts (see "What gets downranked"), so this rule
is both an ethics rule and a reach rule.

## The hook: the first ~140 characters are the whole game

LinkedIn truncates a text post in the feed with a **"…see more"** link. The commonly cited
fold is **~140 characters / ~2–3 lines on mobile**. Everything after the fold is invisible
until someone taps. So the first line has one job: earn the tap.

**Do:**

- Lead with the **finding in human terms** or a genuine curiosity gap that resolves below the
  fold. Make the reader feel they'll be smarter in 20 seconds.
- Front-load the single most surprising true thing — a concrete result, a counter-intuitive
  outcome, a sharp question a practitioner is already asking.
- Keep line 1 tight enough to survive the ~140-char fold intact.

**Don't:**

- Open with **"New study shows…", "Researchers at…", "Excited to share…", "A new paper…"**.
  These waste the fold on framing.
- Open with the publication venue or status.
- Open with engagement-bait theatrics ("You won't BELIEVE…", "Drop a 🔥 if…"). LinkedIn's
  2026 quality filter actively suppresses this.
- Bury the finding under a windup.

| Weak first line (avoid) | Strong first line (use) |
|---|---|
| "New study explores protein folding with a new model." | "A protein-folding model just matched lab X-ray structures it was never trained on." |
| "Excited to share fascinating research on batteries!" | "This lithium-metal battery held 80% capacity after 1,000 charge cycles — most die well before that." |
| "Researchers at a university published a paper on LLM reasoning." | "Asked to reason in a physics where F=mv, top LLMs mostly kept answering as if F=ma." |

## Ideal length for our use case

The 2026 consensus favors **short, high-signal text posts** — LinkedIn has been elevating
"bite-sized" text posts that generate sustained engagement, and generic length advice bottoms
out around 25 words for pure engagement. But that advice targets one-line thought-leadership
takes. Ours is an **educational explainer with real substance to deliver.**

**Target 900–1,600 characters (~150–260 words).** Long enough to deliver one paper's insight
with a real number and mechanism; short enough that a busy professional finishes it. Never pad
toward the 3000 limit — dwell-time signals reward posts people *finish*, and unfinished
long posts hurt more than short ones help. If the paper is thin, write 700 characters and
stop.

Rule of thumb: if you can't say what a reader *gained*, it's too long. If it reads like an
abstract, it's the wrong shape.

## Formatting for the feed

LinkedIn renders raw text. Structure comes from **whitespace**, not Markdown.

- **Short paragraphs — 1–3 lines each — with a blank line between them.** A wall of text dies
  in the feed. White space is the formatting.
- **One idea per paragraph.** Hook → context → the finding+number → so-what → question, each
  its own block (see template).
- **No Markdown.** No `**`, `#`, `>`, or `-` bullets — they render as literal characters.
  If you need a list, use line breaks with a leading `→`, `·`, or `–` (typed Unicode dash),
  and keep it to 2–4 items.
- **Emojis: at most one or two, functional, never decorative.** A single `📄` to label the
  paper link is fine and conventional. Skip the 🚀🔥🤯 register — it reads as bait to this
  audience and to the 2026 quality filter. Never use emoji as bullet points down the left
  margin.
- **No ALL-CAPS words** for emphasis (screen-reader-hostile and shouty). Rephrase instead.
- **Numbers as digits** ("37% → 70%", "1,000 cycles") — they catch the eye and read as
  precise.

## Links: put the paper link IN the post

This is the one place our ethics override pure reach optimization.

**The state of play (2026):** external links have long been the flashpoint of LinkedIn reach
debates. Reports vary — some analyses claim in-post links cut reach materially and that the
old "link in first comment" workaround was patched in early 2026; LinkedIn-aligned guidance is
milder, saying links aren't penalized *if the post delivers real value on its own*. The honest
synthesis: LinkedIn favors posts that keep the reader **on the post**, so a naked link-drop
underperforms — but a substantive post that *happens to* include a source link is not
meaningfully punished.

**Our decision: the paper link goes in the post body, every time.** Attribution is a
non-negotiable ethics requirement (same as the Instagram caption), and we will not launder it
into a first comment the automated pipeline may never post. We mitigate the reach cost the
right way — by making the post itself valuable enough to stand alone:

- Deliver the full insight (finding + number + so-what) **before** the link. The link is a
  "go deeper," not the payload.
- Put the link **near the end**, on its own line, labeled: `📄 Paper: https://…` — use the
  paper's real `source_url` as a full `https://` URL.
- Never make the post a teaser whose only value is behind the link. That is exactly the
  pattern the algorithm downranks *and* the pattern that fails the reader.

## Hashtags

**3 or fewer, specific, at the very end.** The 2026 consensus is firm: three is the ceiling,
and LinkedIn treats hashtags as "a nice to have, not a need to have." Discovery now comes from
**keywords in the post text**, which LinkedIn's semantic ranking reads directly — so write the
natural terms a curious professional would search ("gene editing", "battery storage", "protein
folding") into the prose, and use hashtags only as light topic signals.

- Use 2–3 specific tags (`#MachineLearning`, `#Genomics`), not broad ones (`#Science`,
  `#Innovation`).
- Place them on the last line, after the link. Never scatter them mid-sentence.

## CTA / engagement

An informative science post earns engagement by being worth reacting to — not by asking.
LinkedIn's 2026 quality filter explicitly downranks engagement-bait: "comment YES", reaction
polls, chain-letter "share this" requests, and one-word-comment farming. So:

- **Preferred CTA: one genuine, specific question** tied to the paper's implication, aimed at
  the practitioner reader. Good: *"If this holds up outside simulation, would you trust it in a
  production pipeline?"* It invites a real opinion, not a reflex.
- **Acceptable, sparingly:** an open invitation to a perspective — *"Curious whether anyone
  here has hit this limit in practice."*
- **Avoid:** "Follow for more," "Agree? 👇," "Repost if you found this useful," "Comment your
  thoughts," and any like/share request. These are bait and are downranked.
- One CTA line, at most. No CTA is better than a cringe CTA.

## Recommended structure (our template)

Five short blocks, blank line between each. This maps hook → context → insight → so-what →
question, then attribution.

1. **Hook (1 line, ≤ ~140 chars).** The finding in human terms or a real curiosity gap. Must
   survive the fold.
2. **Context (1–2 lines).** What problem this addresses / why it was hard — just enough for
   the finding to land. Name the actual method, model, gene, or dataset.
3. **The finding, with the number (2–3 lines).** The headline result and its concrete figure
   (effect size, rate, speedup, sample). This is the substance block — never skip it. Gloss one
   specialist term if needed.
4. **So-what + honest limit (1–2 lines).** What it could change for a practitioner, plus the
   real scientific limit (sample size, simulation-only, one cell line, association-not-
   causation). Both in the same breath — that's what makes you trustworthy.
5. **Question + link + hashtags (3 lines).** One genuine question · `📄 Paper: https://…` ·
   2–3 specific hashtags.

Total: aim for 900–1,600 characters.

## Full worked example (fictional paper)

> Asked to reason in a universe where force equals mass times velocity, not acceleration,
> the best language models mostly kept answering as if F still equaled ma.
>
> A team built "counterfactual physics" benchmarks — internally consistent worlds with one
> altered law — to test whether models reason from first principles or just replay their
> training data. It's a clean way to separate understanding from memorization.
>
> Across 12 such worlds, top models scored 41% on counterfactual questions versus 88% on the
> real-physics versions. Performance dropped most on multi-step problems, where a single wrong
> assumption compounds.
>
> For anyone shipping LLM reasoning features, that gap is the story: these systems are strong
> when the world matches their training and brittle when it doesn't. The benchmark is
> simulation-only and covers physics, not open-ended reasoning — so it's a lower bound on the
> problem, not a full map of it.
>
> If a model aced your eval but never saw a case that broke its assumptions, how much would
> you trust it?
>
> 📄 Paper: https://arxiv.org/abs/2406.xxxxx
>
> #MachineLearning #AIresearch #LLMs

Why this works: the hook resolves a curiosity gap and survives the fold; the number (41% vs
88%) is the payload and it's above the link; the limit is scientific, not publication-status;
the question is a real practitioner question, not bait; the link is in-post per our ethics;
three specific hashtags.

## Bad example (what not to do)

> 🚀🚀 Excited to share this game-changing new study that could be a total breakthrough!! 🤯
>
> Researchers have PROVEN that AI can't really reason. This changes everything.
>
> Want to know more? The link is in the comments 👇 Follow for more AI content and drop a 🔥
> if you agree!!
>
> #AI #Science #Innovation #Tech #Future #MachineLearning #DeepLearning #Trending #Viral

Everything wrong: hype/banned terms ("game-changing", "breakthrough", "PROVEN"), overclaims
causation, wastes the fold on "Excited to share… Researchers have…", emoji-as-decoration, an
engagement-bait CTA, link hidden in comments (violates our attribution ethics), and 9 broad
hashtags.

## What gets penalized / downranked in 2026

Design around these:

| Factor | Effect | Our handling |
|---|---|---|
| **Engagement bait** (comment-YES, reaction polls, like/share begging, chain letters) | Suppressed by the quality filter | Never. One genuine question only. |
| **Naked external link-drops** | Underperform; some analyses cite large reach cuts | Deliver full value in-post; link is "go deeper," placed after the payload. |
| **Over-hashtagging (>3)** | Historic reach reductions | 2–3 specific tags, at the end. |
| **AI-obvious filler / no original insight** | Reported reach and engagement penalties for low-insight AI posts | Every post carries a specific number, named entity, and real mechanism. |
| **Engagement pods** | ToS violation, detected and hard-downranked | N/A — never. |
| **Hype / low-substance** | Quality filter demotes | Banned-terms list; substance over spectacle. |
| **Quick-skim posts** | Low dwell time → less reach; posts held 30–60s+ outperform sharply | Short, finishable, front-loaded value keeps people on the post. |

## Sources

Guidance synthesized from 2025–2026 social-marketing analyses (Sprout Social's LinkedIn
algorithm guide, Jan 2026; Hootsuite/Buffer LinkedIn algorithm and post-length guides, Dec
2025 / Apr 2025; SocialPilot's LinkedIn algorithm report, Jun 2026). The strongest disagreement
in the literature is the *magnitude* of the external-link penalty; our decision (link in-post
for attribution) does not depend on the exact figure, and we mitigate it by leading with value.
