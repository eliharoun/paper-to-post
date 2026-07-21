import { test } from "node:test";
import assert from "node:assert/strict";

import {
  decideFromMarker,
  orderedCardFiles,
  validateCarousel,
  pendingMarker,
  confirmedResult,
} from "../../scripts/jslib/publish_logic.mjs";

// --- the double-post idempotency decision (highest-risk logic) ---

test("no marker -> publish", () => {
  const d = decideFromMarker(null, "x/published.json");
  assert.equal(d.action, "publish");
});

test("confirmed marker -> skip, never re-post", () => {
  const marker = { status: "confirmed", media_id: "m1", permalink: "http://x" };
  const d = decideFromMarker(marker, "x/published.json");
  assert.equal(d.action, "skip");
  assert.equal(d.result.skipped, "already-published");
  assert.equal(d.result.media_id, "m1");
});

test("pending marker -> ABORT (post is live, do not double-post)", () => {
  const d = decideFromMarker({ status: "pending", media_id: "m9" }, "x/published.json");
  assert.equal(d.action, "abort");
  assert.equal(d.code, 1);
  assert.match(d.message, /pending/);
  assert.match(d.message, /m9/);
  assert.match(d.message, /do NOT re-post/i);
});

test("legacy marker with no status -> skip (treated as already published)", () => {
  const d = decideFromMarker({ media_id: "m1", permalink: "http://x" }, "p");
  assert.equal(d.action, "skip");
});

// --- card ordering + carousel validation ---

test("orderedCardFiles keeps only cards and sorts numerically", () => {
  const files = ["caption.txt", "card_02.jpg", "card_10.jpg", "card_01.jpg", "post.json"];
  assert.deepEqual(orderedCardFiles(files), ["card_01.jpg", "card_02.jpg", "card_10.jpg"]);
});

test("validateCarousel rejects <2 cards", () => {
  const r = validateCarousel(["card_01.jpg"], "cap");
  assert.equal(r.ok, false);
  assert.match(r.message, /2-10 cards/);
});

test("validateCarousel rejects >10 cards", () => {
  const cards = Array.from({ length: 11 }, (_, i) => `card_${i}.jpg`);
  assert.equal(validateCarousel(cards, "cap").ok, false);
});

test("validateCarousel rejects an over-long caption", () => {
  const r = validateCarousel(["a.jpg", "b.jpg"], "x".repeat(2201));
  assert.equal(r.ok, false);
  assert.match(r.message, /2200/);
});

test("validateCarousel accepts a normal 8-card post", () => {
  const cards = Array.from({ length: 8 }, (_, i) => `card_0${i}.jpg`);
  assert.deepEqual(validateCarousel(cards, "a fine caption"), { ok: true });
});

// --- marker shapes (the pending-before-verify contract) ---

test("pendingMarker carries status pending + media_id", () => {
  assert.deepEqual(pendingMarker("dailycsbits", "m1"),
    { status: "pending", account: "dailycsbits", media_id: "m1" });
});

test("confirmedResult carries status confirmed + permalink (null-safe)", () => {
  assert.deepEqual(confirmedResult("u", "m1", null),
    { ok: true, status: "confirmed", account: "u", media_id: "m1", permalink: null });
  assert.equal(confirmedResult("u", "m1", "http://x").permalink, "http://x");
});
