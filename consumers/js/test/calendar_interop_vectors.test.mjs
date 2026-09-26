// Runs every vector in tests/vectors/calendar_interop_vectors.json through
// the independent JavaScript implementation (Sprint 8) and demands an exact
// match. No Maghrib is recomputed here -- every vector's astronomy comes
// frozen from its own `context`.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import {
  boundaryCrossing,
  checkProviderInvariance,
  daysInMonth,
  gregorianDateToWaqtDay,
  isLeapYear,
  representInstant,
} from "../src/calendar_interop.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const path = process.env.WAQT_CALENDAR_INTEROP_VECTORS ?? join(here, "../../../tests/vectors/calendar_interop_vectors.json");
const doc = JSON.parse(readFileSync(path, "utf8"));

test("vector file has all three groups, non-trivially sized", () => {
  assert.ok(doc.instant_representation.length >= 8);
  assert.ok(doc.gregorian_date_to_waqt_day.length >= 3);
  assert.ok(doc.boundary_crossing.length >= 6);
});

for (const v of doc.instant_representation) {
  test(`instant_representation / ${v.id}`, () => {
    if (v.op === "provider_invariance") {
      const result = checkProviderInvariance(v);
      assert.equal(result.gregorian_utc_same, v.expected.gregorian_utc_same);
      assert.equal(result.maghrib_open_same, v.expected.maghrib_open_same);
      assert.equal(result.maghrib_close_same, v.expected.maghrib_close_same);
      return;
    }
    const result = representInstant(v);
    assert.deepStrictEqual(result, v.expected);
  });
}

for (const v of doc.gregorian_date_to_waqt_day) {
  test(`gregorian_date_to_waqt_day / ${v.id}`, () => {
    assert.deepStrictEqual(gregorianDateToWaqtDay(v), v.expected);
  });
}

for (const v of doc.boundary_crossing) {
  test(`boundary_crossing / ${v.id}`, () => {
    assert.deepStrictEqual(boundaryCrossing(v), v.expected);
  });
}

test("Gregorian leap-year rule matches every vector year independently", () => {
  assert.equal(isLeapYear(2000), true);
  assert.equal(isLeapYear(1900), false);
  assert.equal(isLeapYear(2028), true);
  assert.equal(isLeapYear(2026), false);
});

test("days_in_month agrees with the standard Gregorian table", () => {
  assert.equal(daysInMonth(2028, 2), 29);
  assert.equal(daysInMonth(2026, 2), 28);
  assert.equal(daysInMonth(2026, 4), 30);
  assert.equal(daysInMonth(2026, 1), 31);
});
