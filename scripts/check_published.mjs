// List an account's most recent Instagram media — a read-only recovery probe.
//
// Use after an interrupted publish (e.g. a batch timeout) to see what actually
// went live before deciding whether to re-run a bundle. Instagram has no delete
// API, so confirming state first is how you avoid a duplicate post.
//
// Run through the Composio CLI:
//   ~/.composio/composio run -f scripts/check_published.mjs -- --account <alias> [--limit 8]
//
// Prints one JSON line per recent post: {timestamp, permalink, caption_head}.
// NOTE: INSTAGRAM_GET_USER_MEDIA accepts only {ig_user_id, limit, after,
// graph_api_version} — passing a `fields` key is rejected by the CLI schema.

function arg(name, required = true) {
  const i = process.argv.indexOf(`--${name}`);
  if (i === -1 || i === process.argv.length - 1) {
    if (required) { console.error(`missing --${name}`); process.exit(2); }
    return null;
  }
  return process.argv[i + 1];
}

const account = arg("account");
const limit = parseInt(arg("limit", false) || "8", 10);

const me = await execute("INSTAGRAM_GET_USER_INFO", { ig_user_id: "me" }, { account });
if (!me.successful) { console.error("account check failed:", me.error); process.exit(1); }
const username = me.data?.username;
const uid = me.data?.id || "me";

const r = await execute("INSTAGRAM_GET_USER_MEDIA", { ig_user_id: uid, limit }, { account });
if (!r.successful) { console.error("media fetch failed:", r.error); process.exit(1); }
const items = r.data?.data || r.data || [];

console.error(`account @${username} | ${items.length} recent media`);
for (const m of items) {
  console.log(JSON.stringify({
    timestamp: m.timestamp || null,
    permalink: m.permalink || m.id || null,
    caption_head: (m.caption || "").split("\n")[0].slice(0, 80),
  }));
}
