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
import {
  decideFromMarker, orderedCardFiles, validateCarousel, pendingMarker, confirmedResult,
} from "./jslib/publish_logic.mjs";

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
//    A marker with status "pending" means a previous run published to the API but
//    died before confirming — the post is very likely LIVE. We must NOT blindly
//    re-post; abort and tell the operator to reconcile (check_published.mjs) so a
//    wrapper-error-after-success can't cause a duplicate.
const publishedPath = `${dir}/published.json`;
const marker = fs.existsSync(publishedPath)
  ? JSON.parse(fs.readFileSync(publishedPath, "utf8")) : null;
const decision = decideFromMarker(marker, publishedPath);
if (decision.action === "abort") { console.error(decision.message); process.exit(decision.code); }
if (decision.action === "skip") { console.log(JSON.stringify(decision.result)); process.exit(0); }

// 1. Pre-flight: confirm which account this selector actually resolves to.
const who = await execute("INSTAGRAM_GET_USER_INFO", { ig_user_id: "me" }, { account });
if (!who.successful) { console.error("account check failed:", who.error); process.exit(1); }
const username = who.data?.username;
if (expectUser && username !== expectUser) {
  console.error(`ABORT: account "${account}" resolved to @${username}, expected @${expectUser}`);
  process.exit(1);
}

// 2. Gather ordered cards + caption from the bundle, then validate the carousel
//    (2-10 images, caption <= 2200) before uploading anything.
const cards = orderedCardFiles(fs.readdirSync(dir));
const caption = fs.existsSync(`${dir}/caption.txt`) ? fs.readFileSync(`${dir}/caption.txt`, "utf8") : "";
const carouselCheck = validateCarousel(cards, caption);
if (!carouselCheck.ok) { console.error(carouselCheck.message); process.exit(carouselCheck.code); }
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

// CRITICAL: the API has now accepted the post — it is LIVE. Persist a "pending"
// marker with the media_id BEFORE the verify GET, so that if anything after this
// point fails (verify error, wrapper crash, kill), a re-run sees the marker and
// refuses to double-post (there is no delete API). Instagram double-posts have
// happened exactly here: publish succeeded, a later step threw, no marker written.
try {
  fs.writeFileSync(publishedPath, JSON.stringify(pendingMarker(username, pub.data.id), null, 2));
} catch (e) {
  // The post is LIVE but we could not record it. A silent failure here would let a
  // re-run double-post — so fail loudly with the media_id and stop, don't proceed.
  console.error(
    `CRITICAL: post is LIVE (media_id ${pub.data.id}) but writing ${publishedPath} failed: ` +
    `${e?.message || e}. Do NOT re-run blindly — reconcile with check_published.mjs and ` +
    `hand-write {"status":"confirmed","media_id":"${pub.data.id}"} before any retry.`
  );
  process.exit(1);
}

const check = await execute(
  "INSTAGRAM_GET_IG_MEDIA",
  { ig_user_id: "me", ig_media_id: pub.data.id, fields: "id,permalink,username" },
  { account }
);
const result = confirmedResult(username, pub.data.id, check.data?.permalink);
// Upgrade the marker to confirmed (with permalink). A re-run now cleanly skips.
try { fs.writeFileSync(publishedPath, JSON.stringify(result, null, 2)); } catch {}
console.log(JSON.stringify(result));
