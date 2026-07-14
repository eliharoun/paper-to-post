# Configuration guide

Everything is config-driven. To run your own topics/accounts you edit three things:

1. `config/topics.yml` — topics, their paper sources, and where they publish.
2. `config/brand.<account>.yml` — one per account: card look (colors, fonts, size).
3. `.env` — API contact email, optional keys, toggles.

No code changes needed. After editing, verify with:

```bash
python -c "from scripts.lib.config import load_topics; load_topics()"   # raises on a bad config
```

---

## 1. `config/topics.yml`

### Top-level keys

| Key | Type | Meaning |
|---|---|---|
| `default_language` | str | Reserved; leave `en`. |
| `lookback_hours` | int | How far back "recent" papers go (default 48). |
| `max_candidates_per_topic` | int | Cap on candidates kept per topic after filtering. |
| `topics` | list | The topics (below). |

### Each topic

| Field | Required | Meaning |
|---|---|---|
| `id` | ✅ | Unique topic id. This is what `research-gather --topic <id>` uses. |
| `enabled` | ✅ | `false` skips the topic entirely. |
| `account` | ✅ | Which brand file to use → `config/brand.<account>.yml`. |
| `display_name` | ✅ | Human label (used in logs/reports). |
| `priority` | ✅ | Float. Higher wins when a paper matches two topics. |
| `keywords` | | Lowercase substrings; a paper matching any is assigned to this topic. |
| `hard_excludes` | | Substrings that reject a paper outright. |
| `requires_health_guardrails` | | `true` → validator enforces a "not medical advice" line on clinical content. |
| `sources` | ✅ | Which paper sources to pull (below). Only listed sources run. |
| `publish` | ✅ | Which channels to publish to (below). |

### `sources:` — only the sources you list run

Each source is optional. Include a source key to enable it; omit it to skip it.

```yaml
sources:
  arxiv:
    categories: ["cs.AI", "cs.LG"]      # arXiv category codes (arxiv.org/category_taxonomy)
  openalex:
    subfields: ["1702", "1707"]         # OpenAlex subfield ids (precise; preferred)
    query: ""                           # optional; strict full-text AND — keep empty or ONE phrase
  crossref:
    query: "machine learning"           # relevance-ranked; keep short
  semantic_scholar:
    query: "LLM OR RAG OR alignment"    # needs SEMANTIC_SCHOLAR_API_KEY or it rate-limits (429)
  pubmed:
    query: "(genetics OR cancer) AND research"   # PubMed query syntax
  biorxiv:
    servers: ["biorxiv", "medrxiv"]     # preprint servers to pull
  labs:
    labs: ["meta", "google", "deepmind"]  # pull by author affiliation (via OpenAlex)
    query: "large language models"
```

Guidance: prefer **arxiv categories** and **openalex subfields** (precise) over free-text queries. Keep queries short — long ones over-narrow. A single source failing (e.g. a 429) is logged and skipped, not fatal.

### `publish:` — one entry per channel

**Volume is per-channel.** The topic gathers papers; each channel's `max_posts` decides how many it publishes (the top-ranked slice). The pipeline produces enough to feed the greediest channel.

| Field | Channels | Meaning |
|---|---|---|
| `channel` | all | `instagram` \| `linkedin` \| `newsletter`. |
| `enabled` | all | `false` skips this channel (default `true`). |
| `max_posts` | all | Max posts this channel publishes. Omit = no cap (publish all produced). |
| `alias` | instagram, linkedin | Composio connection alias (see README "Composio setup"). |
| `username` | instagram, linkedin | Guard: verified before posting. IG = handle; **LinkedIn = member `sub`** (see note). |
| `title` | newsletter | Digest header (default `"Research Digest"`). |
| `sort` | newsletter | `position` (rank order) or `confidence` (high→low). |
| `min_confidence` | newsletter | Drop items below `low`/`medium`/`high` (default: keep all). |
| `show_why_it_matters` | newsletter | `true`/`false` — render the per-item "Why it matters" line. |
| `footer` | newsletter | Optional closing line. |

```yaml
publish:
  - channel: instagram
    alias: MyIGConnection
    username: myhandle
    max_posts: 5
  - channel: linkedin
    alias: MyLinkedInConnection
    username: "aBc123Xyz"       # member sub, NOT your name — see note below
    max_posts: 1
  - channel: newsletter         # no account needed
    max_posts: 10
    title: "My Research Digest"
    sort: confidence
    min_confidence: medium
    footer: "Forward this to a colleague."
```

**LinkedIn `username` = member `sub`.** LinkedIn's API reliably returns only the `sub` id, so the guard must match that, not your display name. Find it: `~/.composio/composio run -f scripts/publish_linkedin.mjs -- --account <alias> --expect-username x --dir <any>` — the abort message prints your `sub`. Put it in `username`.

---

## 2. `config/brand.<account>.yml`

One file per `account`. Filename must be `brand.<account>.yml` (e.g. `account: cs` → `config/brand.cs.yml`). Copy an existing one and adjust.

```yaml
brand:
  account_name: "Daily CS Bits"        # header rendered on every card
  footer_text: "Source linked in caption"
  canvas_width: 1080                   # px (1080x1350 = Instagram portrait)
  canvas_height: 1350
  render_scale: 2                      # 2 = export at 2x (2160x2700)
  margin: 90                           # inner padding, px
  min_cards: 5                         # validator: fewest content cards allowed
  max_cards: 7                         # validator: most cards allowed
  jpeg_quality: 92
  motif: ["circuit", "neural"]         # front-card backdrop (fallback when no hero image);
                                       # one name or a list that rotates by date. options:
                                       # neural circuit waveform orbits hexgrid particles topo grid molecule helix none
  hero_style:                          # optional: AI hero image on the front card (omit to always use the motif)
    enabled: true                      # false = skip hero, always use the motif backdrop
    image_model: "gemini-3.1-flash-image-preview"   # cheaper flash tier; swap to
                                       # nano-banana-pro-preview or gemini-3-pro-image-preview for top quality
    aspect_ratio: "4:5"                # matches the 1080x1350 card
    style: >                           # per-topic house style, folded into the hero prompt
      Premium editorial 3D render, dark studio void, single cyan (#38BDF8) accent,
      no text, no words, no diagrams.
  fonts:
    heading: "Inter"                   # font family names (Inter is bundled)
    body: "Inter"
  type_scale:                          # per-canvas font sizes (px)
    title_px: 84                       # title-card headline
    title_source_px: 40                # title-card source/venue line
    heading_px: 64                     # content-card question heading
    body_px: 50                        # content-card body copy
    label_px: 30                       # account eyebrow label
    footer_px: 32                      # content-card footer / source line
  palette:
    background: "#0B1220"
    surface: "#1E293B"
    text_primary: "#F8FAFC"
    text_muted: "#94A3B8"
    accent: "#38BDF8"
    card_type_colors:                  # accent color per card type
      hook: "#38BDF8"
      finding: "#34D399"
      method: "#A78BFA"
      context: "#FBBF24"
      limitation: "#F87171"
      source: "#94A3B8"
      next: "#38BDF8"
  logo_path: ""                        # optional path to a logo image
```

All fields are required except `motif` (default `none`), `hero_style` (optional — omit to always use the motif backdrop), and `logo_path` (default empty).

---

## 3. `.env`

Copy `.env.example` → `.env`. Only `CONTACT_EMAIL` matters for a basic run.

| Var | Meaning |
|---|---|
| `CONTACT_EMAIL` | **Required.** Real address for polite API pools + Unpaywall OA lookup. A placeholder disables OA screenshots (Unpaywall returns 422). |
| `GOOGLE_API_KEY` | Optional. Enables the front-card hero image (Gemini image generation; requires billing enabled). Without it, `research-hero` fails and the front card falls back to the branded motif backdrop. |
| `SEMANTIC_SCHOLAR_API_KEY` | Optional. Without it, Semantic Scholar usually rate-limits (429) and contributes nothing. |
| `NCBI_API_KEY` | Optional. Higher PubMed rate limit. |
| `OPENALEX_MAILTO` | Optional. Defaults to `CONTACT_EMAIL`. |
| `ENABLE_FULL_TEXT` | `true`/`false` — extract full paper text (falls back to abstract). |
| `ENABLE_PAPER_SCREENSHOT` | `true`/`false` — arXiv/OA first-page screenshot card. |
| `PDF_MAX_BYTES`, `PDF_FETCH_TIMEOUT_SECONDS` | PDF fetch limits. |
| `MIN_SCORE_TO_POST` | Advisory quality bar (default 70), honored by the skill's judgment — no script enforces it. A paper should score ≥ this to post. |
| `PAPER_LOOKBACK_HOURS`, `MAX_CANDIDATES_PER_RUN`, `MAX_LLM_SCORED_CANDIDATES` | Selection knobs (advisory). |
| `DATA_DIR`, `OUTPUT_DIR` | Where the ledger and outputs live. |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Optional legacy Telegram push. |

---

## Quick recipes

**Add a topic** → add an entry under `topics:` with its own `id`, `account`, `sources`, `publish`. Add `config/brand.<account>.yml` if it's a new account.

**Change how many posts a channel gets** → edit that channel's `max_posts`.

**Turn a channel on/off** → add/remove its `publish` entry, or set `enabled: false`.

**Newsletter only** → give the topic just a `newsletter` publish entry.

**Disable a topic for now** → `enabled: false`.
