// The Sprint 5 conformance vectors, consumed by an implementation that shares
// no code with the Python reference. Sprint 5's report named this as the
// missing milestone ("nothing outside Python has actually consumed it").

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import { checkCrossVector, checkVector } from "../src/waqt_semantics.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const path = process.env.WAQT_VECTORS ?? join(here, "../../../tests/vectors/waqt_vectors.json");
const doc = JSON.parse(readFileSync(path, "utf8"));
const byId = new Map(doc.vectors.map((v) => [v.id, v]));

test("vector file identifies itself", () => {
  assert.equal(doc.spec, "waqt-core/0.1");
  assert.equal(doc.vectors.length, 10);
});

for (const v of doc.vectors) {
  test(`waqt_vectors / ${v.id}`, () => {
    assert.deepEqual(checkVector(v), []);
  });
}

test("waqt_vectors / cross-vector properties (boundary tiling, Asr isolation, elevation, long day)", () => {
  assert.deepEqual(checkCrossVector(byId), []);
});

test("this consumer actually rejects a corrupted vector (it is not vacuous)", () => {
  const v = structuredClone(byId.get("addis-normal-instant"));
  v.expected.waqt_position.display = "00:19:22";
  assert.notDeepEqual(checkVector(v), []);
  const w = structuredClone(byId.get("addis-exact-maghrib-boundary"));
  w.expected.waqt_position.total_seconds = 1;
  assert.notDeepEqual(checkVector(w), []);
});
