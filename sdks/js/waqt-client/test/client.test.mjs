// test/client.test.mjs — integration tests for WaqtClient against a
// REAL, locally-spawned instance of the FastAPI app (see
// helpers/server.mjs). Genuine HTTP, not a mock.

import { test, before, after } from "node:test";
import assert from "node:assert/strict";

import { WaqtClient } from "../src/client.mjs";
import { WaqtApiError } from "../src/errors.mjs";
import { startServer } from "../test-support/server.mjs";

let server;
let client;

before(async () => {
  server = await startServer();
  client = new WaqtClient({ baseUrl: server.baseUrl });
});

after(async () => {
  await server.stop();
});

test("getWaqt: ordinary instant", async () => {
  const resp = await client.getWaqt(9.0192, 38.7525, { instant: "2026-09-19T15:42:00Z" });
  assert.equal(resp.status, "OK");
  assert.equal(resp.hijri.year, 1448);
  assert.ok(resp.raw);
});

test("getWaqt: polar UNDEFINED", async () => {
  const resp = await client.getWaqt(69.6492, 18.9553, { instant: "2026-06-21T12:00:00Z" });
  assert.equal(resp.status, "UNDEFINED");
  assert.ok(resp.undefinedReason);
});

test("getDay / getEvents subset shapes", async () => {
  const day = await client.getDay(9.0192, 38.7525, { instant: "2026-09-19T15:42:00Z" });
  assert.ok(day.day);

  const events = await client.getEvents(9.0192, 38.7525, { instant: "2026-09-19T15:42:00Z" });
  assert.equal(events.events.length, 6);
});

test("getHijri", async () => {
  const resp = await client.getHijri({ date: "2026-09-19" });
  assert.equal(resp.hijri.year, 1448);
});

test("listCalendarProviders", async () => {
  const providers = await client.listCalendarProviders();
  const names = new Set(providers.map((p) => p.name));
  assert.ok(names.has("arithmetic-tabular"));
  assert.ok(names.has("umm-al-qura"));
});

test("getLocation", async () => {
  const info = await client.getLocation(9.0192, 38.7525, { instant: "2026-09-19T15:42:00Z" });
  assert.equal(info.timezone.name, "Africa/Addis_Ababa");
});

test("convert to-hijri / to-gregorian", async () => {
  const toHijri = await client.convert("to-hijri", { date: "2026-09-19" });
  const hd = toHijri.output.hijri;
  const toGreg = await client.convert("to-gregorian", { year: hd.year, month: hd.month, day: hd.day });
  assert.equal(toGreg.output.gregorian_date, "2026-09-19");
});

test("representInstant / waqtDayForGregorianDate", async () => {
  const rep = await client.representInstant({ instant: "2026-09-19T15:42:00Z", lat: 9.0192, lon: 38.7525 });
  assert.equal(rep.gregorianUtc.date, "2026-09-19");

  const dayRep = await client.waqtDayForGregorianDate("2026-09-20", 9.0192, 38.7525);
  assert.equal(dayRep.direction, "gregorian-date-to-waqt");
});

test("boundaryCrossing", async () => {
  const result = await client.boundaryCrossing("2026-09-19T00:00:00Z", "2026-09-20T00:00:00Z", 9.0192, 38.7525);
  assert.equal(result.crossesCivilMidnight, true);
  assert.equal(result.crossesMaghrib, true);
});

test("scheduleSnapshot / scheduleSpan", async () => {
  const snap = await client.scheduleSnapshot(9.0192, 38.7525, { instant: "2026-09-19T15:42:00Z" });
  assert.ok(Math.abs(snap.location.lat - 9.0192) < 1e-9);

  const span = await client.scheduleSpan(9.0192, 38.7525, "2026-09-19T00:00:00Z", "2026-09-21T00:00:00Z");
  assert.ok(Object.keys(span.raw).length > 0);
});

test("institutionalWeek / institutionalDefaultProfile", async () => {
  const week = await client.institutionalWeek(9.0192, 38.7525, { instant: "2026-09-19T15:42:00Z" });
  assert.ok("week_start" in week.raw);

  const profile = await client.institutionalDefaultProfile();
  assert.ok(Object.keys(profile.raw).length > 0);
});

test("error: VALIDATION_ERROR surfaces code and details", async () => {
  await assert.rejects(
    () => client.getWaqt(999, 38.7525),
    (err) => {
      assert.ok(err instanceof WaqtApiError);
      assert.equal(err.code, "VALIDATION_ERROR");
      assert.equal(err.statusCode, 422);
      assert.ok(err.details);
      return true;
    }
  );
});

test("error: INVALID_INSTANT", async () => {
  await assert.rejects(
    () => client.getWaqt(9.0192, 38.7525, { instant: "not-a-date" }),
    (err) => {
      assert.equal(err.code, "INVALID_INSTANT");
      return true;
    }
  );
});

test("health", async () => {
  const h = await client.health();
  assert.equal(h.status, "ok");
});

test("config defaults applied, per-call overrides win", async () => {
  const c = new WaqtClient({ baseUrl: server.baseUrl, defaultAsrShadowRatio: 2.0 });
  const resp = await c.getWaqt(21.4225, 39.8262, { instant: "2026-09-19T10:00:00Z" });
  assert.equal(resp.profile.asrShadowRatio, 2.0);

  const resp2 = await c.getWaqt(21.4225, 39.8262, { instant: "2026-09-19T10:00:00Z", asrRatio: 1.0 });
  assert.equal(resp2.profile.asrShadowRatio, 1.0);
});
