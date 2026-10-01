// test/conformance.test.mjs — feeds sdks/vectors/sdk_conformance_vectors.json
// (real, captured `/v1/*` HTTP responses) through waqt-client's own
// envelope/type parsing and checks the parsed result. This is the SAME
// vectors file sdks/python/tests/test_conformance.py consumes with its
// own, independent parser.

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

import { unwrap } from "../src/envelope.mjs";
import { WaqtApiError } from "../src/errors.mjs";
import * as T from "../src/types.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const VECTORS_PATH = path.resolve(__dirname, "../../../vectors/sdk_conformance_vectors.json");

const file = JSON.parse(readFileSync(VECTORS_PATH, "utf-8"));
const VECTORS = file.vectors;
const byId = Object.fromEntries(VECTORS.map((v) => [v.id, v]));

test("vectors file exists and is non-empty", () => {
  assert.ok(VECTORS.length >= 15);
});

test("every success vector unwraps; every error vector throws WaqtApiError", () => {
  for (const v of VECTORS) {
    if (v.status_code < 400) {
      const data = unwrap(v.status_code, v.response, "ignore");
      assert.deepEqual(data, v.response.data);
    } else {
      assert.throws(
        () => unwrap(v.status_code, v.response, "ignore"),
        (err) => {
          assert.ok(err instanceof WaqtApiError);
          assert.equal(err.code, v.response.error.code);
          assert.equal(err.statusCode, v.status_code);
          return true;
        }
      );
    }
  }
});

test("waqt-addis-normal parses expected fields", () => {
  const resp = T.parseWaqtResponse(byId["waqt-addis-normal"].response.data);
  assert.equal(resp.status, "OK");
  assert.equal(resp.hijri.year, 1448);
  assert.equal(resp.hijri.month, 4);
  assert.equal(resp.hijri.day, 7);
  assert.ok(resp.waqt);
  assert.ok(T.findEvent(resp, "maghrib"));
  assert.ok(T.findEvent(resp, "fajr"));
  assert.ok(Math.abs(resp.location.lat - 9.0192) < 1e-9);
});

test("waqt-polar-undefined parses as UNDEFINED", () => {
  const resp = T.parseWaqtResponse(byId["waqt-polar-undefined"].response.data);
  assert.equal(resp.status, "UNDEFINED");
  assert.ok(resp.undefinedReason);
  assert.equal(resp.day.maghribOpen, null);
  assert.equal(resp.day.maghribClose, null);
});

test("waqt-hanafi-asr reflects custom profile", () => {
  const resp = T.parseWaqtResponse(byId["waqt-hanafi-asr"].response.data);
  assert.equal(resp.profile.asrShadowRatio, 2.0);
});

test("day and events subset shapes parse", () => {
  const day = T.parseWaqtResponse(byId["day-addis"].response.data);
  assert.ok(day.day);
  assert.equal(day.hijri, null);

  const events = T.parseWaqtResponse(byId["events-addis"].response.data);
  assert.equal(events.events.length, 6);
  const names = new Set(events.events.map((e) => e.name));
  assert.deepEqual(names, new Set(["fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha"]));
});

test("hijri vectors agree on gregorian date, differ by provider", () => {
  const ordinary = byId["hijri-ordinary"].response.data;
  const ummAlQura = byId["hijri-umm-al-qura"].response.data;
  assert.equal(ordinary.gregorian_date, "2026-09-19");
  assert.equal(ummAlQura.gregorian_date, "2026-09-19");
  assert.equal(ordinary.hijri.provider.name, "arithmetic-tabular");
  assert.equal(ummAlQura.hijri.provider.name, "umm-al-qura");
});

test("calendar providers list parses", () => {
  const providers = byId["calendar-providers"].response.data.providers.map(T.parseCalendarProviderInfo);
  const names = new Set(providers.map((p) => p.name));
  assert.ok(names.has("arithmetic-tabular"));
  assert.ok(names.has("umm-al-qura"));
});

test("location vector parses", () => {
  const info = T.parseLocationInfo(byId["location-addis"].response.data);
  assert.ok(Math.abs(info.location.lat - 9.0192) < 1e-9);
  assert.ok(info.localCivilDate);
});

test("conversions vectors parse", () => {
  const toHijri = T.parseConversionResult(byId["conversions-to-hijri"].response.data);
  assert.equal(toHijri.direction, "to-hijri");
  assert.equal(toHijri.output.hijri.year, 1448);

  const toGreg = T.parseConversionResult(byId["conversions-to-gregorian"].response.data);
  assert.equal(toGreg.direction, "to-gregorian");
  assert.ok(toGreg.output.gregorian_date.startsWith("2026-09-"));
});

test("instant representation vector parses", () => {
  const rep = T.parseInstantRepresentation(byId["calendar-convert-instant"].response.data);
  assert.equal(rep.direction, "instant-to-calendars");
  assert.equal(rep.gregorianUtc.date, "2026-09-19");
  assert.ok(rep.gregorianCivil);
  assert.equal(rep.waqtStatus, "OK");
});

test("gregorian-date-to-waqt vector parses", () => {
  const rep = T.parseInstantRepresentation(byId["calendar-convert-date-to-waqt"].response.data);
  assert.equal(rep.direction, "gregorian-date-to-waqt");
  assert.equal(rep.waqtStatus, "OK");
  assert.ok(rep.waqtDay.maghribClose);
  assert.equal(rep.waqtDay.maghribClose.toISOString().slice(0, 10), "2026-09-20");
});

test("boundary crossing vector parses", () => {
  const result = T.parseBoundaryCrossingResult(byId["boundary-crossing-both"].response.data);
  assert.equal(result.status, "OK");
  assert.equal(result.crossesCivilMidnight, true);
  assert.equal(result.crossesMaghrib, true);
});

test("schedule vectors parse", () => {
  const snap = T.parseSchedulingResult(byId["schedule-snapshot"].response.data);
  assert.ok(Math.abs(snap.location.lat - 9.0192) < 1e-9);

  const span = T.parseSchedulingResult(byId["schedule-span"].response.data);
  assert.ok(Object.keys(span.raw).length > 0);
});

test("institutional vectors parse", () => {
  const week = T.parseInstitutionalResult(byId["institutional-week"].response.data);
  assert.ok("week_start" in week.raw);
  assert.ok("week_end" in week.raw);

  const profile = T.parseInstitutionalResult(byId["institutional-profile"].response.data);
  assert.ok(Object.keys(profile.raw).length > 0);
});

for (const [id, expectedCode] of [
  ["error-invalid-instant", "INVALID_INSTANT"],
  ["error-invalid-span", "INVALID_SPAN"],
  ["error-validation", "VALIDATION_ERROR"],
]) {
  test(`error vector ${id} raises WaqtApiError with matching code`, () => {
    const v = byId[id];
    assert.throws(
      () => unwrap(v.status_code, v.response, "ignore"),
      (err) => {
        assert.equal(err.code, expectedCode);
        assert.equal(err.statusCode, v.status_code);
        return true;
      }
    );
  });
}

// ---- Sprint 14 (API 1.5.0): provenance survives SDK parsing ----
import { parseHijriDate as _parseHijri14 } from "../src/types.mjs";
import _test14 from "node:test";
import _assert14 from "node:assert/strict";
_test14("hijri source/provenance are exposed, not dropped; older servers give null", () => {
  const h = _parseHijri14({ date: "1448-04-19", display: "x", year: 1448, month: 4, month_name: "m", day: 19,
    provider: { name: "umm-al-qura", version: "v" }, source: "local-fallback",
    provenance: { requested_provider: "aladhan", fallback_reason: "timeout" } });
  _assert14.equal(h.source, "local-fallback"); _assert14.equal(h.isFallback, true);
  _assert14.equal(h.provenance.fallback_reason, "timeout");
  const old = _parseHijri14({ date: "d", display: "x", year: 1, month: 1, month_name: "m", day: 1, provider: {} });
  _assert14.equal(old.source, null); _assert14.equal(old.provenance, null); _assert14.equal(old.isFallback, false);
});
