# Instagram publishing via Composio

How to publish a finished carousel bundle to the right Instagram account — the
skill's delivery step. Verified against Composio CLI **v0.2.31** (behaviours noted
below may change in later versions).

## The one rule that matters: account selection

If you have more than one Instagram connection, **selecting the wrong one silently
posts to your Composio *default* connection** — and there is no delete API, so a
misroute is unrecoverable except by deleting the post by hand. The guard is
non-negotiable:

- Select the account with the option key **`account`** — value is the connection
  alias or id, e.g. `{ account: "<your-alias>" }`.
- **Do NOT use `connectedAccountId`, `connected_account_id`, or `accountId`.** These
  are silently ignored by `composio run`'s `execute()` and fall back to the
  **default** connection. This is the single most important gotcha.
- **Always pre-verify** the resolved username with `INSTAGRAM_GET_USER_INFO` and abort
  if it doesn't match the intended account, *before* uploading any media. The publish
  script does this via `--expect-username`.

### Where the alias and username come from

Each topic in `config/topics.yml` has a `publish:` list; the Instagram entry carries
`alias` (the Composio connection alias) and `username` (the handle the pre-flight guard
checks):
```yaml
publish:
  - channel: instagram
    alias: <your-composio-connection-alias>
    username: <your-ig-handle>
```
Read them in-process (`[t for t in load_topics().topics if t.id==TOPIC][0].publish_targets("instagram")`).
The shipped config includes two example accounts; replace them with your own. To list the
live connection aliases/usernames/ids, use the Composio MCP
(`COMPOSIO_MANAGE_CONNECTIONS`, toolkit `instagram`, action `list`).

## How to run it

Use the committed script `scripts/publish_instagram.mjs`. It runs through the Composio
CLI, which injects an authenticated `execute()` and the env — do **not** try to call
the Instagram API directly or via the MCP `execute` for uploads.

```bash
# ALIAS / USERNAME come from the topic's instagram publish target (alias / username).
~/.composio/composio run -f scripts/publish_instagram.mjs -- \
  --account "$ALIAS" --expect-username "$USERNAME" \
  --dir outputs/$D/$ACC/post$N
```

On success it prints one JSON line:
`{"ok":true,"account":"<username>","media_id":"…","permalink":"https://www.instagram.com/p/…"}`.
On any mismatch or API failure it exits non-zero and posts nothing further.

### Why a script and not inline JS

The recipe has sharp edges (the `account` key, the pre-flight guard, the 3-call
container→carousel→publish sequence, local-file upload semantics). Encoding it once in
a committed, syntax-checked script means an agent runs one command with a few args
instead of reconstructing the flow from memory and risking a misroute.

## The publish flow (what the script does)

Instagram carousels are built from child containers, one per image:

1. **`INSTAGRAM_GET_USER_INFO`** `{ ig_user_id: "me" }` with `{ account }` → verify
   `username` matches the target. Abort otherwise.
2. For each `card_NN.jpg` (2–10, in order): **`INSTAGRAM_POST_IG_USER_MEDIA`**
   `{ ig_user_id: "me", is_carousel_item: true, image_file: "<local path>" }` with
   `{ account }`. `image_file` = a **local path**; the CLI uploads it — no external
   hosting/URL is needed. Collect each returned `id`.
3. **`INSTAGRAM_CREATE_CAROUSEL_CONTAINER`**
   `{ ig_user_id: "me", children: [ids…], caption }` with `{ account }`.
4. **`INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH`**
   `{ ig_user_id: "me", creation_id: <parent id>, max_wait_seconds: 120 }` with
   `{ account }`.
5. **`INSTAGRAM_GET_IG_MEDIA`** to read back `permalink,username` and confirm the owner.

The caption is read from the bundle's `caption.txt` verbatim (hook, article link,
CTA, hashtags — already assembled by `research-bundle`). Cards are the bundle's
`card_NN.jpg` in filename order (the screenshot is already inserted second-to-last).

## Constraints & gotchas

- **Carousel size is 2–10 items.** Our bundles are ~8 cards, within range. The script
  aborts outside 2–10.
- **No delete API.** Instagram's Graph API (via Composio) exposes **no** tool to delete
  a published post — only `INSTAGRAM_DELETE_COMMENT`. A misrouted post must be deleted
  **manually in the Instagram app**. This is exactly why the pre-flight username guard
  exists: prevention is the only remedy.
- **Idempotent re-runs.** On success the script writes `published.json` into the bundle
  dir; a re-run with that file present prints `{"ok":true,"skipped":"already-published",…}`
  and posts nothing. So recovering from an interrupted batch is just re-running each
  command — it will not double-post. **Publish one carousel per command** (an 8-card
  upload is ~20–30s; looping several exceeds a 120s shell timeout and leaves state
  ambiguous). To see what actually went live, probe read-only:
  `~/.composio/composio run -f scripts/check_published.mjs -- --account "<alias>"`.
- **Run a script file with `composio run -f <script> -- <args>`** (note the `-f` and
  the `--` separating the script's own args). In v0.2.31 the `composio execute
  --file`/`--account` flags were unreliable, so prefer `composio run` for local-file
  uploads and account selection.
- **`account_type: PRIVATE`** in the connection list can be a red herring — an account
  may still resolve to `MEDIA_CREATOR` via `GET_USER_INFO` and publish fine. (Publishing
  requires an Instagram professional/creator account connected through Composio.)
- **`composio run` is a Bun runtime** with a global authenticated `execute(slug, args,
  opts)`. Standard Node built-ins (`node:fs`) are available; the script reads args from
  `process.argv` (the CLI passes flags through).
