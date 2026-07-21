// Pure, side-effect-free logic for publish_instagram.mjs, extracted so it can be
// unit-tested with `node --test` (the .mjs entrypoint only does I/O + Composio calls).
// The double-post idempotency decision is the highest-risk code in the pipeline
// (Instagram has no delete API), so it lives here and is tested directly.

// Decide what to do given an existing published.json (or null if none).
// Returns one of:
//   { action: "publish" }                      -> no marker: proceed to publish
//   { action: "skip", result }                 -> confirmed marker: already done
//   { action: "abort", code, message }         -> pending marker: LIVE-but-unconfirmed,
//                                                  must NOT re-post (reconcile by hand)
export function decideFromMarker(marker, publishedPath) {
  if (!marker) return { action: "publish" };
  if (marker.status === "pending") {
    return {
      action: "abort",
      code: 1,
      message:
        `ABORT: ${publishedPath} shows status "pending" (media_id ${marker.media_id}). ` +
        `A prior run published to the API but did not confirm; the post is likely LIVE. ` +
        `Reconcile with check_published.mjs before re-running (do NOT re-post blindly).`,
    };
  }
  // Any other existing marker (confirmed, or a legacy marker with no status) means
  // the bundle already published successfully -> skip, never double-post.
  return { action: "skip", result: { ok: true, skipped: "already-published", ...marker } };
}

// The list of card_NN.jpg filenames in a bundle dir, in numeric order, given the
// dir listing. Filters non-card files; sorts lexically (card_01..card_10 already sort).
export function orderedCardFiles(dirListing) {
  return dirListing.filter((f) => /^card_\d+\.jpg$/.test(f)).sort();
}

// Validate a carousel before uploading. Returns { ok } or { ok:false, code, message }.
// Mirrors Instagram's limits: 2-10 images, caption <= 2200 chars.
export function validateCarousel(cards, caption) {
  if (cards.length < 2 || cards.length > 10) {
    return { ok: false, code: 1, message: `carousel needs 2-10 cards, found ${cards.length}` };
  }
  if (caption.length > 2200) {
    return { ok: false, code: 1, message: `ABORT: caption ${caption.length} > 2200 chars (Instagram limit)` };
  }
  return { ok: true };
}

// The pending marker written immediately after the API accepts the post (before the
// verify GET), so a crash afterward can't cause a re-run to double-post.
export function pendingMarker(username, mediaId) {
  return { status: "pending", account: username, media_id: mediaId };
}

// The confirmed result written after the verify GET succeeds.
export function confirmedResult(username, mediaId, permalink) {
  return {
    ok: true,
    status: "confirmed",
    account: username,
    media_id: mediaId,
    permalink: permalink || null,
  };
}
