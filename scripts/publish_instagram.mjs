// Publish one post's carousel bundle to Instagram via Composio.
//
// Run through the Composio CLI so `execute()`/env are injected:
//   ~/.composio/composio run -f scripts/publish_instagram.mjs -- \
//     --account <alias> --expect-username <handle> --dir <bundleDir>
//
// The <alias> and <handle> come from the topic's instagram publish target
// (publish: [{channel: instagram, alias, username}]) in config/topics.yml.
//
// Recipe (see references/instagram-publishing.md):
//  - Select the account with the option key `account` (alias or connection id).
//    NOTE: `connectedAccountId` is IGNORED here and silently falls back to the
//    Composio DEFAULT connection, which can publish to the wrong account. There
//    is no delete API, so ALWAYS use `account` AND pre-verify the resolved
//    username with --expect-username before uploading anything.
//  - Local JPEGs upload directly via the `image_file` field = a local path.
//  - Flow: N child containers -> carousel parent -> publish -> verify owner.
//
// Args are read from process.argv (the CLI passes them through).

import fs from "node:fs";

function arg(name, required = true) {
  const i = process.argv.indexOf(`--${name}`);
  if (i === -1 || i === process.argv.length - 1) {
    if (required) { console.error(`missing --${name}`); process.exit(2); }
    return null;
  }
  return process.argv[i + 1];
}

const account = arg("account");                 // Composio connection alias or id
const dir = arg("dir").replace(/\/$/, "");       // e.g. outputs/2026-01-15/cs/post1
const expectUser = arg("expect-username", false); // guard: expected @handle, e.g. "your_handle"

// 0. Idempotency: if this bundle already published, do NOT post again (Instagram
//    has no delete API, so a duplicate is unrecoverable). Re-running is safe.
const publishedPath = `${dir}/published.json`;
if (fs.existsSync(publishedPath)) {
  const prev = JSON.parse(fs.readFileSync(publishedPath, "utf8"));
  console.log(JSON.stringify({ ok: true, skipped: "already-published", ...prev }));
  process.exit(0);
}

// 1. Pre-flight: confirm which account this selector actually resolves to.
const who = await execute("INSTAGRAM_GET_USER_INFO", { ig_user_id: "me" }, { account });
if (!who.successful) { console.error("account check failed:", who.error); process.exit(1); }
const username = who.data?.username;
if (expectUser && username !== expectUser) {
  console.error(`ABORT: account "${account}" resolved to @${username}, expected @${expectUser}`);
  process.exit(1);
}

// 2. Gather ordered cards + caption from the bundle.
const cards = fs.readdirSync(dir).filter((f) => /^card_\d+\.jpg$/.test(f)).sort();
if (cards.length < 2 || cards.length > 10) {
  console.error(`carousel needs 2-10 cards, found ${cards.length}`); process.exit(1);
}
const caption = fs.existsSync(`${dir}/caption.txt`) ? fs.readFileSync(`${dir}/caption.txt`, "utf8") : "";
// Instagram caption limit is 2200 chars. The validation gate enforces this
// upstream, but abort here too rather than let the API reject a half-uploaded post.
if (caption.length > 2200) {
  console.error(`ABORT: caption ${caption.length} > 2200 chars (Instagram limit)`); process.exit(1);
}
console.error(`target @${username} | cards ${cards.length} | caption ${caption.length} chars`);

// 3. Child containers (local file upload via image_file = path).
const childIds = [];
for (const c of cards) {
  const r = await execute(
    "INSTAGRAM_POST_IG_USER_MEDIA",
    { ig_user_id: "me", is_carousel_item: true, image_file: `${dir}/${c}` },
    { account }
  );
  if (!r.successful) { console.error("child upload failed:", c, r.error); process.exit(1); }
  childIds.push(r.data.id);
}

// 4. Carousel parent.
const parent = await execute(
  "INSTAGRAM_CREATE_CAROUSEL_CONTAINER",
  { ig_user_id: "me", children: childIds, caption },
  { account }
);
if (!parent.successful) { console.error("carousel container failed:", parent.error); process.exit(1); }

// 5. Publish, then verify owner.
const pub = await execute(
  "INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH",
  { ig_user_id: "me", creation_id: parent.data.id, max_wait_seconds: 120 },
  { account }
);
if (!pub.successful) { console.error("publish failed:", pub.error); process.exit(1); }

const check = await execute(
  "INSTAGRAM_GET_IG_MEDIA",
  { ig_user_id: "me", ig_media_id: pub.data.id, fields: "id,permalink,username" },
  { account }
);
const result = {
  ok: true,
  account: username,
  media_id: pub.data.id,
  permalink: check.data?.permalink || null,
};
// Record success so a re-run (e.g. after a batch timeout) skips this bundle
// instead of double-posting. See the idempotency guard at the top.
try { fs.writeFileSync(publishedPath, JSON.stringify(result, null, 2)); } catch {}
console.log(JSON.stringify(result));
