// test/requests_types.test.mjs — pure shape tests, no network. Each
// asserts a typed builder's toJSON() matches the wire format
// waqt.scheduling.model / waqt.scheduling.ops / waqt.institutional.rules
// define server-side (checked independently -- see requests_types.mjs's
// module docstring).

import { test } from "node:test";
import assert from "node:assert/strict";

import * as R from "../src/requests_types.mjs";

test("event point", () => {
  assert.deepEqual(R.event("maghrib", 0).toJSON(), { type: "event", name: "maghrib", day: 0 });
});

test("event rejects unknown name", () => {
  assert.throws(() => R.event("nonsense"), R.RequestValidationError);
});

test("instant point with string", () => {
  assert.deepEqual(R.instant("2026-09-19T15:42:00Z").toJSON(), { type: "instant", value: "2026-09-19T15:42:00Z" });
});

test("offset and fraction nest correctly", () => {
  const off = R.offset(R.event("maghrib"), 600);
  assert.deepEqual(off.toJSON(), { type: "offset", base: { type: "event", name: "maghrib", day: 0 }, seconds: 600 });

  const frac = R.fraction(R.event("maghrib"), R.event("fajr", 1), 2 / 3);
  assert.deepEqual(frac.toJSON(), {
    type: "fraction",
    start: { type: "event", name: "maghrib", day: 0 },
    end: { type: "event", name: "fajr", day: 1 },
    fraction: 2 / 3,
  });
});

test("interval requires at least one bound", () => {
  assert.throws(() => R.interval(), R.RequestValidationError);
});

test("interval toJSON", () => {
  const iv = R.interval(R.event("maghrib", 0), R.event("isha", 0));
  assert.deepEqual(iv.toJSON(), {
    type: "interval",
    start: { type: "event", name: "maghrib", day: 0 },
    end: { type: "event", name: "isha", day: 0 },
    start_inclusive: true,
    end_inclusive: false,
  });
});

test("generic constructors match manual interval", () => {
  assert.deepEqual(R.before(R.event("fajr")).toJSON(), R.interval(null, R.event("fajr"), { endInclusive: false }).toJSON());
  assert.deepEqual(R.after(R.event("maghrib")).toJSON(), R.interval(R.event("maghrib"), null, { startInclusive: true }).toJSON());
  assert.deepEqual(R.withinDay(0).toJSON(), R.interval(R.event("day_start", 0), R.event("day_end", 0)).toJSON());
});

test("operation shapes", () => {
  assert.deepEqual(R.resolvePoint(R.event("fajr")).toJSON(), {
    op: "resolve_point", point: { type: "event", name: "fajr", day: 0 },
  });
  assert.deepEqual(R.nextEventOp().toJSON(), { op: "next_event" });
  assert.deepEqual(R.dayBounds().toJSON(), { op: "day_bounds" });
  assert.deepEqual(R.eventPosition("isha", 1).toJSON(), { op: "event_position", name: "isha", day: 1 });
  assert.deepEqual(R.until("maghrib").toJSON(), { op: "until", name: "maghrib", on_undefined: "strict" });
  assert.deepEqual(R.since("fajr", { onUndefined: "skip" }).toJSON(), { op: "since", name: "fajr", on_undefined: "skip" });
  assert.deepEqual(
    R.classifySpan("2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z").toJSON(),
    { op: "classify_span", start: "2026-01-01T00:00:00Z", end: "2026-01-02T00:00:00Z", end_inclusive: false },
  );
});

test("scheduleResolveRequest full shape", () => {
  const req = R.scheduleResolveRequest({
    lat: 9.0192, lon: 38.7525,
    anchor: "2026-09-19T15:42:00Z",
    operation: R.resolveInterval(R.interval(R.event("maghrib", 0), R.event("isha", 0))),
    profile: R.profile({ fajrAngleDeg: 15.0 }),
    calendarProvider: "umm-al-qura",
    precision: "microsecond",
  });
  const body = req.toJSON();
  assert.deepEqual(body.location, { lat: 9.0192, lon: 38.7525, elevation_m: 0.0 });
  assert.equal(body.anchor, "2026-09-19T15:42:00Z");
  assert.equal(body.operation.op, "resolve_interval");
  assert.deepEqual(body.profile, { fajr_angle_deg: 15.0, isha_angle_deg: 17.0, asr_shadow_ratio: 1.0 });
  assert.equal(body.calendar_provider, "umm-al-qura");
  assert.equal(body.precision, "microsecond");
});

test("scheduleResolveRequest minimal shape omits optionals", () => {
  const body = R.scheduleResolveRequest({ lat: 9.0, lon: 38.0, operation: R.nextEventOp() }).toJSON();
  assert.deepEqual(Object.keys(body).sort(), ["location", "operation"]);
});

test("fiscalYearResolveRequest shape", () => {
  const req = R.fiscalYearResolveRequest({
    hijriYear: 1448, startRule: R.monthDay(1, 1), endRule: R.monthEnd(12), label: "Custom Fiscal Year",
  });
  assert.deepEqual(req.toJSON(), {
    hijri_year: 1448,
    start_rule: { type: "month_day", month: 1, day: 1 },
    end_rule: { type: "month_end", month: 12 },
    label: "Custom Fiscal Year",
  });
});

test("academicYearResolveRequest shape with terms", () => {
  const req = R.academicYearResolveRequest({
    hijriYear: 1448,
    openingRule: R.nthWeekdayOfMonth("al-Ahad", 1, 1),
    closingRule: R.nthWeekdayOfMonth("al-Khamis", -1, 8),
    termRules: [R.termRule("Term 1", R.monthDay(1, 1), R.monthEnd(3))],
  });
  const body = req.toJSON();
  assert.deepEqual(body.opening_rule, { type: "nth_weekday_of_month", weekday: "al-Ahad", n: 1, month: 1 });
  assert.deepEqual(body.term_rules, [{
    label: "Term 1",
    start_rule: { type: "month_day", month: 1, day: 1 },
    end_rule: { type: "month_end", month: 3 },
    year_offset: 0,
  }]);
  assert.deepEqual(body.holidays, []);
});
