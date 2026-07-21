import { test } from "node:test";
import assert from "node:assert/strict";

import {
  mediaList,
  withinLookback,
  extractMetrics,
} from "../../scripts/jslib/insights_logic.mjs";

test("mediaList handles bare array and wrapped {data}", () => {
  assert.deepEqual(mediaList([{ id: "1" }]), [{ id: "1" }]);
  assert.deepEqual(mediaList({ data: [{ id: "2" }] }), [{ id: "2" }]);
  assert.deepEqual(mediaList(null), []);
});

test("withinLookback keeps recent, drops old", () => {
  const now = Date.parse("2026-08-01T00:00:00Z");
  const list = [
    { id: "recent", timestamp: "2026-07-30T00:00:00Z" },
    { id: "old", timestamp: "2026-06-01T00:00:00Z" },
  ];
  const kept = withinLookback(list, now, 20).map((m) => m.id);
  assert.deepEqual(kept, ["recent"]);
});

test("withinLookback KEEPS items with unparseable/missing timestamp", () => {
  const now = Date.parse("2026-08-01T00:00:00Z");
  const list = [
    { id: "null", timestamp: null },
    { id: "empty", timestamp: "" },
    { id: "junk", timestamp: "not-a-date" },
  ];
  const kept = withinLookback(list, now, 20).map((m) => m.id);
  assert.deepEqual(kept, ["null", "empty", "junk"]);  // never silently dropped
});

test("extractMetrics reads values[0].value and total_value.value", () => {
  const resp = {
    successful: true,
    data: { data: [
      { name: "reach", values: [{ value: 100 }] },
      { name: "saved", total_value: { value: 7 } },
      { name: "shares", values: [{ value: 3 }] },
    ] },
  };
  assert.deepEqual(extractMetrics(resp), { reach: 100, saved: 7, shares: 3 });
});

test("extractMetrics drops unnamed / non-numeric rows, never throws", () => {
  const resp = {
    successful: true,
    data: [
      { name: "reach", values: [{ value: 5 }] },
      { name: null, values: [{ value: 9 }] },       // unnamed -> dropped
      { name: "likes", values: [{ value: "x" }] },  // non-numeric -> dropped
      {},                                            // malformed -> ignored
    ],
  };
  assert.deepEqual(extractMetrics(resp), { reach: 5 });
});

test("extractMetrics returns {} for an unsuccessful response", () => {
  assert.deepEqual(extractMetrics({ successful: false, error: "boom" }), {});
  assert.deepEqual(extractMetrics(null), {});
});
