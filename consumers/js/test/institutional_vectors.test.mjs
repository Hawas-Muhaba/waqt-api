// Runs every vector in tests/vectors/institutional_vectors.json through the
// independent JavaScript implementation and demands an exact match.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import { islamicWeekdayOf, runVector } from "../src/institutional.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const path = process.env.WAQT_INSTITUTIONAL_VECTORS ?? join(here, "../../../tests/vectors/institutional_vectors.json");
const doc = JSON.parse(readFileSync(path, "utf8"));

test("vector file has the expected format", () => {
  assert.equal(doc.spec, "waqt-institutional/0.1");
  assert.equal(doc.vector_format_version, "1.0");
  assert.ok(doc.vectors.length >= 20);
});

for (const v of doc.vectors) {
  test(`${v.group} / ${v.id}`, () => {
    assert.deepStrictEqual(runVector(v), v.expected);
  });
}

test("week vectors carry no calendar table (pure Gregorian arithmetic)", () => {
  for (const v of doc.vectors) {
    if (v.group === "week") assert.deepStrictEqual(v.context, {});
  }
});

test("Jumu'ah (al-Jumuah) always lands on a Gregorian Friday, independent of any table", () => {
  // A handful of known Fridays/non-Fridays, computed with no Python involved.
  assert.equal(islamicWeekdayOf("2026-09-18"), "al-Jumuah"); // Friday
  assert.equal(islamicWeekdayOf("2026-09-17"), "al-Khamis"); // Thursday
  assert.equal(islamicWeekdayOf("2026-09-13"), "al-Ahad");   // Sunday
});

test("this consumer actually rejects a corrupted vector (it is not vacuous)", () => {
  const v = structuredClone(doc.vectors.find((x) => x.id.startsWith("rule-first-ahad-muharram-arithmetic-tabular")));
  v.expected.gregorian = "1900-01-01";
  assert.notDeepEqual(runVector(v), v.expected);
});
