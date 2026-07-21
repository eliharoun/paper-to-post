// Pure, side-effect-free logic for collect_insights.mjs, extracted for `node --test`.
// The .mjs entrypoint only does the Composio calls + stdout; parsing/filtering lives here.

export const INSIGHT_METRICS = [
  "reach", "saved", "shares", "likes", "comments", "views", "total_interactions",
];

// Normalize the media-list response, which the API may return as a bare array or
// wrapped in { data: [...] }.
export function mediaList(responseData) {
  if (Array.isArray(responseData)) return responseData;
  return responseData?.data || [];
}

// Keep only media within the lookback window. An unparseable/missing timestamp is
// KEPT (we can't date it, so don't silently drop it) — matching the .py side which
// treats a bad timestamp as fresh.
export function withinLookback(list, nowMs, lookbackDays) {
  const cutoff = nowMs - lookbackDays * 86400 * 1000;
  return list.filter((m) => {
    const t = Date.parse(m?.timestamp || "");
    return Number.isNaN(t) ? true : t >= cutoff;
  });
}

// Extract a { name: value } metrics map from an insights response, tolerating the
// two shapes the Graph API uses (values[0].value or total_value.value) and dropping
// anything non-numeric or unnamed. Never throws on a malformed row.
export function extractMetrics(insightsResponse) {
  const out = {};
  if (!insightsResponse?.successful) return out;
  const rows = insightsResponse.data?.data || insightsResponse.data || [];
  for (const row of rows) {
    const name = row?.name;
    const val = row?.values?.[0]?.value ?? row?.total_value?.value;
    if (name && typeof val === "number") out[name] = val;
  }
  return out;
}
