// Publish one paper as a single LinkedIn text post via Composio.
//
// Run through the Composio CLI so `execute()`/env are injected:
//   ~/.composio/composio run -f scripts/publish_linkedin.mjs -- \
//     --account <alias> --expect-username <name> --dir <bundleDir>
//
// The <alias>/<name> come from the topic's linkedin publish target in
// config/topics.yml (channel: linkedin). Text is read from the bundle:
// linkedin.txt if present (channel-specific copy), else caption.txt.
//
// Recipe (mirrors the Instagram guard):
//  - Select the account with the option key `account` (alias/connection id).
//    `connectedAccountId` is ignored and falls back to the Composio default, so
//    ALWAYS use `account` and pre-verify the resolved member before posting.
//  - Resolve the author URN via LINKEDIN_GET_MY_INFO, then publish text with
//    LINKEDIN_CREATE_LINKED_IN_POST (commentary <= 3000 chars, PUBLIC).
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

const MAX_LEN = 3000; // LinkedIn commentary hard limit

const account = arg("account");                    // Composio connection alias or id
const dir = arg("dir").replace(/\/$/, "");          // e.g. outputs/2026-01-15/cs/post1
const expectUser = arg("expect-username", false);   // guard: expected member SUB (see below)

// 0. Idempotency: skip if this bundle already posted to LinkedIn.
const publishedPath = `${dir}/linkedin_published.json`;
if (fs.existsSync(publishedPath)) {
  const prev = JSON.parse(fs.readFileSync(publishedPath, "utf8"));
  console.log(JSON.stringify({ ok: true, skipped: "already-published", ...prev }));
  process.exit(0);
}

// 1. Pre-flight: resolve the authenticated member and derive the author URN.
const me = await execute("LINKEDIN_GET_MY_INFO", {}, { account });
if (!me.successful) { console.error("account check failed:", me.error); process.exit(1); }
const info = me.data || {};
const sub = info.sub || info.id;
const name = info.name || info.given_name || sub;
if (!sub) { console.error("could not resolve LinkedIn member id"); process.exit(1); }
// The guard matches [sub, name, email], but LINKEDIN_GET_MY_INFO reliably returns
// only `sub` — `name`/`email` are often absent. So the config `username` guard value
// SHOULD be the member `sub`. On mismatch, print the full resolved identity so the
// correct guard value is obvious without a separate probe.
if (expectUser && ![sub, name, info.email].includes(expectUser)) {
  console.error(`ABORT: account "${account}" resolved to sub="${sub}" name="${name || ""}" email="${info.email || ""}", expected "${expectUser}".`);
  console.error(`Set the linkedin channel's username to the sub "${sub}" in config/topics.yml.`);
  process.exit(1);
}
const author = `urn:li:person:${sub}`;

// 2. Load the post text (channel-specific file preferred, caption as fallback).
function readFirst(...names) {
  for (const n of names) {
    if (fs.existsSync(`${dir}/${n}`)) return fs.readFileSync(`${dir}/${n}`, "utf8").trim();
  }
  return "";
}
let commentary = readFirst("linkedin.txt", "caption.txt");
if (!commentary) { console.error(`no linkedin.txt or caption.txt in ${dir}`); process.exit(1); }
if (commentary.length > MAX_LEN) {
  console.error(`text ${commentary.length} > ${MAX_LEN}; truncating`);
  commentary = commentary.slice(0, MAX_LEN - 1).trimEnd() + "…";
}
console.error(`target ${name} (${sub}) | ${commentary.length} chars`);

// 3. Publish.
const pub = await execute(
  "LINKEDIN_CREATE_LINKED_IN_POST",
  { author, commentary, visibility: "PUBLIC", lifecycleState: "PUBLISHED" },
  { account }
);
if (!pub.successful) { console.error("publish failed:", pub.error); process.exit(1); }

const d = pub.data || {};
const postId = d.id || d.postId || d.share || null;
const result = {
  ok: true,
  account: name,
  sub,
  post_id: postId,
  permalink: postId ? `https://www.linkedin.com/feed/update/${postId}/` : null,
};
try { fs.writeFileSync(publishedPath, JSON.stringify(result, null, 2)); } catch {}
console.log(JSON.stringify(result));
