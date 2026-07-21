// Fetch recent Instagram media + per-post insights for one account via Composio,
// and print a JSON snapshot for scripts/collect_insights.py to ingest.
//
//   ~/.composio/composio run -f scripts/collect_insights.mjs -- \
//     --account <alias> --lookback-days 20
//
// Read-only (no publishing). Emits, on the last stdout line, a snapshot:
//   { account, collected: N, posts: [{ media_id, timestamp, permalink, metrics: {...} }] }
// where metrics has whatever the API returned (reach/saved/shares/likes/comments/
// views/total_interactions). Per-post insight failures (older/ineligible media)
// are tolerated: that post ships with metrics: {} and is skipped downstream.

import {
  INSIGHT_METRICS, mediaList, withinLookback, extractMetrics,
} from "./jslib/insights_logic.mjs";

function arg(name, def = null) {
  const i = process.argv.indexOf(`--${name}`);
  if (i === -1 || i === process.argv.length - 1) return def;
  return process.argv[i + 1];
}

const account = arg("account");
if (!account) { console.error("missing --account"); process.exit(2); }
const lookbackDays = parseInt(arg("lookback-days", "20"), 10);

// 1. List recent media (id, timestamp, permalink).
const media = await execute(
  "INSTAGRAM_GET_IG_USER_MEDIA",
  { ig_user_id: "me", fields: "id,timestamp,permalink" },
  { account }
);
if (!media.successful) { console.error("media list failed:", media.error); process.exit(1); }

// 2. Keep those within the lookback window.
const recent = withinLookback(mediaList(media.data), Date.now(), lookbackDays);

// 3. Per-post insights (tolerate per-item failure).
const posts = [];
for (const m of recent) {
  let metrics = {};
  try {
    const ins = await execute(
      "INSTAGRAM_GET_IG_MEDIA_INSIGHTS",
      { ig_media_id: m.id, metric: INSIGHT_METRICS },
      { account }
    );
    metrics = extractMetrics(ins);
  } catch (e) {
    // Older/ineligible media can throw (400). Skip its metrics; keep the run alive.
    console.error(`insights failed for ${m.id}: ${e?.message || e}`);
  }
  posts.push({ media_id: m.id, timestamp: m.timestamp, permalink: m.permalink, metrics });
}

console.log(JSON.stringify({ account, collected: posts.length, posts }));
