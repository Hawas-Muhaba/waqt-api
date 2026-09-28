// test/typed_requests_integration.test.mjs — the Sprint 10 typed
// request builders actually work against a real, locally-spawned
// waqt.api server (see test-support/server.mjs), and produce the exact
// same response as the equivalent hand-written plain-object body did in
// Sprint 9. Closes the "typed POST request tests" item in Sprint 10's
// Required tests list.

import { test, before, after } from "node:test";
import assert from "node:assert/strict";

import { WaqtClient } from "../src/client.mjs";
import { WaqtApiError } from "../src/errors.mjs";
import * as R from "../src/requests_types.mjs";
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

test("typed scheduleResolve matches equivalent plain object", async () => {
  const plain = {
    location: { lat: 9.0192, lon: 38.7525, elevation_m: 0.0 },
    anchor: "2026-09-19T15:42:00Z",
    operation: {
      op: "resolve_interval",
      interval: {
        type: "interval",
        start: { type: "event", name: "maghrib", day: 0 },
        end: { type: "event", name: "isha", day: 0 },
        start_inclusive: true,
        end_inclusive: false,
      },
    },
  };
  const typed = R.scheduleResolveRequest({
    lat: 9.0192, lon: 38.7525,
    anchor: "2026-09-19T15:42:00Z",
    operation: R.resolveInterval(R.interval(R.event("maghrib", 0), R.event("isha", 0))),
  });

  const plainResult = await client.scheduleResolve(plain);
  const typedResult = await client.scheduleResolve(typed);

  assert.deepEqual(plainResult.raw, typedResult.raw);
  assert.equal(typedResult.raw.result.status, "OK");
});

test("typed scheduleResolve surfaces server errors the same way", async () => {
  const bad = R.scheduleResolveRequest({ lat: 200.0, lon: 38.7525, operation: R.nextEventOp() });
  await assert.rejects(() => client.scheduleResolve(bad), WaqtApiError);
});

test("typed fiscalYearResolve matches equivalent plain object", async () => {
  const plain = {
    hijri_year: 1448,
    start_rule: { type: "month_day", month: 1, day: 1 },
    end_rule: { type: "month_end", month: 12 },
    label: "Custom Fiscal Year",
  };
  const typed = R.fiscalYearResolveRequest({
    hijriYear: 1448, startRule: R.monthDay(1, 1), endRule: R.monthEnd(12), label: "Custom Fiscal Year",
  });

  const plainResult = await client.institutionalFiscalYearResolve(plain);
  const typedResult = await client.institutionalFiscalYearResolve(typed);

  assert.deepEqual(plainResult.raw, typedResult.raw);
  assert.equal(typedResult.raw.label, "Custom Fiscal Year");
});

test("typed academicYearResolve matches equivalent plain object", async () => {
  const plain = {
    hijri_year: 1448,
    opening_rule: { type: "nth_weekday_of_month", weekday: "al-Ahad", n: 1, month: 1 },
    closing_rule: { type: "nth_weekday_of_month", weekday: "al-Khamis", n: -1, month: 8 },
    term_rules: [], holidays: [],
  };
  const typed = R.academicYearResolveRequest({
    hijriYear: 1448,
    openingRule: R.nthWeekdayOfMonth("al-Ahad", 1, 1),
    closingRule: R.nthWeekdayOfMonth("al-Khamis", -1, 8),
  });

  const plainResult = await client.institutionalAcademicYearResolve(plain);
  const typedResult = await client.institutionalAcademicYearResolve(typed);

  assert.deepEqual(plainResult.raw, typedResult.raw);
});

test("plain object bodies still work unchanged", async () => {
  const result = await client.scheduleResolve({
    location: { lat: 9.0192, lon: 38.7525 },
    operation: { op: "day_bounds" },
  });
  assert.equal(result.raw.result.status, "OK");
});
