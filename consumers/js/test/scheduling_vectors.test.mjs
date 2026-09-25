// Runs every vector in tests/vectors/scheduling_vectors.json through the
// independent JavaScript implementation and demands an exact match.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import { SchedulingEngine, normative } from "../src/scheduling.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const path = process.env.WAQT_SCHEDULING_VECTORS ?? join(here, "../../../tests/vectors/scheduling_vectors.json");
const doc = JSON.parse(readFileSync(path, "utf8"));
const byId = new Map(doc.vectors.map((v) => [v.id, v]));

function run(v) {
  return new SchedulingEngine(v.context, v.anchor).run(v.operation);
}

test("vector file has the expected format", () => {
  assert.equal(doc.spec, "waqt-scheduling/0.1");
  assert.equal(doc.vector_format_version, "1.0");
  assert.ok(doc.vectors.length >= 100);
});

for (const v of doc.vectors) {
  test(`${v.group} / ${v.id}`, () => {
    assert.deepStrictEqual(normative(run(v)), normative(v.expected));
  });
}

// ---- Cross-vector properties, checked from the JS side ----------------------------------

const strip = (o) => JSON.parse(JSON.stringify(o, (k, val) => (k === "hijri_label" ? undefined : val)));

test("calendar substitution: identical tables (bar labels) and identical results (bar labels)", () => {
  const ids = ["arithmetic-tabular", "umm-al-qura", "regional-offset"];
  for (const suffix of ["window", "span", "day-bounds"]) {
    const vs = ids.map((id) => byId.get(`calendar-${id}-${suffix}`));
    for (const v of vs.slice(1)) {
      assert.deepStrictEqual(strip(normative(run(v))), strip(normative(run(vs[0]))), `${suffix} under ${v.context.calendar_provider}`);
      assert.deepStrictEqual(strip(v.context.days), strip(vs[0].context.days), "day tables differ only in labels");
    }
  }
  const labels = new Set(ids.map((id) => run(byId.get(`calendar-${id}-day-bounds`)).hijri_label));
  assert.ok(labels.size >= 2, "providers must actually disagree on the label for this test to mean anything");
});

test("Asr profile moves Asr only: every non-Asr result is identical, the Asr-bearing ones differ", () => {
  const r = (id) => normative(run(byId.get(id)));
  assert.deepStrictEqual(r("profile-asr-standard-maghrib-isha-window"), r("profile-asr-hanafi-maghrib-isha-window"));
  assert.deepStrictEqual(r("profile-asr-standard-day-bounds"), r("profile-asr-hanafi-day-bounds"));
  assert.notDeepEqual(r("profile-asr-standard-asr-point").instant, r("profile-asr-hanafi-asr-point").instant);
  assert.notEqual(r("profile-asr-standard-dhuhr-asr-window").duration_seconds, r("profile-asr-hanafi-dhuhr-asr-window").duration_seconds);
});

test("the three undefined statuses are all exercised and distinct", () => {
  const seen = new Set(doc.vectors.map((v) => v.expected.status));
  for (const s of ["OK", "EVENT_UNDEFINED", "WINDOW_UNDEFINED", "NO_VALID_WINDOW"]) assert.ok(seen.has(s), s);
});
