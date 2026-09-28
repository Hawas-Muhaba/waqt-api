// waqt-client/requests_types — typed request bodies for the three POST
// endpoints Sprint 9 left as raw objects (`POST /v1/schedule/resolve`,
// `POST /v1/institutional/fiscal-year/resolve`,
// `POST /v1/institutional/academic-year/resolve`).
//
// Mirrors sdks/python/waqt_client/requests.py field-for-field and both
// mirror the wire JSON format waqt.scheduling.model / waqt.scheduling.ops
// / waqt.institutional.rules define server-side (docs/SCHEDULING.md §8,
// docs/INSTITUTIONAL.md) -- a clean, independent re-expression of that
// format, not a port of server code: this package has no dependency on
// `waqt` at all (see package.json), by design (README.md).
//
// Passing a plain object as `body` to `scheduleResolve` etc. keeps
// working exactly as it did in Sprint 9 -- everything below is optional,
// additive convenience. Every builder returns a plain object with a
// `toJSON()` method; `WaqtClient` accepts either a plain object or
// anything with `toJSON()` (see client.mjs's `bodyJson`).
//
//   import * as R from "waqt-client/requests_types";
//   const req = R.scheduleResolveRequest({
//     lat: 9.0192, lon: 38.7525,
//     anchor: "2026-09-19T15:42:00Z",
//     operation: R.resolveInterval(R.interval(R.event("maghrib", 0), R.event("isha", 0))),
//   });
//   await client.scheduleResolve(req);

export class RequestValidationError extends Error {}

const EVENT_NAMES = ["fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha"];
const REF_NAMES = [...EVENT_NAMES, "day_start", "day_end"];

function fmtInstant(v) {
  if (v == null) return undefined;
  return v instanceof Date ? v.toISOString() : v;
}

function withToJSON(type, obj) {
  return { type, ...obj, toJSON() { return { type, ...obj }; } };
}

// ---------------------------------------------------------------------------
// Scheduling points
// ---------------------------------------------------------------------------

export function instant(value) {
  return withToJSON("instant", { value: fmtInstant(value) });
}

export function anchor() {
  return { type: "anchor", toJSON() { return { type: "anchor" }; } };
}

export function event(name, day = 0) {
  if (!REF_NAMES.includes(name)) {
    throw new RequestValidationError(`Unknown event ${JSON.stringify(name)}. Known: ${REF_NAMES.join(", ")}`);
  }
  return withToJSON("event", { name, day });
}

export function nextEvent(name, { inclusive = true, onUndefined = "strict" } = {}) {
  return withToJSON("next_event", { name, inclusive, on_undefined: onUndefined });
}

export function prevEvent(name, { inclusive = true, onUndefined = "strict" } = {}) {
  return withToJSON("prev_event", { name, inclusive, on_undefined: onUndefined });
}

export function position(seconds, day = 0) {
  return withToJSON("position", { seconds, day });
}

export function offset(base, seconds) {
  return { type: "offset", base, seconds, toJSON() { return { type: "offset", base: base.toJSON(), seconds }; } };
}

export function fraction(start, end, frac) {
  return {
    type: "fraction", start, end, fraction: frac,
    toJSON() { return { type: "fraction", start: start.toJSON(), end: end.toJSON(), fraction: frac }; },
  };
}

export function interval(start = null, end = null, { startInclusive = true, endInclusive = false } = {}) {
  if (start === null && end === null) {
    throw new RequestValidationError("An interval needs at least one bound");
  }
  return {
    type: "interval", start, end, startInclusive, endInclusive,
    toJSON() {
      return {
        type: "interval",
        start: start ? start.toJSON() : null,
        end: end ? end.toJSON() : null,
        start_inclusive: startInclusive,
        end_inclusive: endInclusive,
      };
    },
  };
}

// -- generic interval constructors, mirroring waqt.scheduling.model's --

export function before(p, inclusive = false) {
  return interval(null, p, { endInclusive: inclusive });
}

export function after(p, inclusive = true) {
  return interval(p, null, { startInclusive: inclusive });
}

export function between(a, b) {
  return interval(a, b);
}

export function within(p, seconds) {
  if (seconds <= 0) throw new RequestValidationError("within() needs a positive duration");
  return interval(p, offset(p, seconds));
}

export function withinDay(day = 0) {
  return interval(event("day_start", day), event("day_end", day));
}

// ---------------------------------------------------------------------------
// Scheduling operations
// ---------------------------------------------------------------------------

export function resolvePoint(point) {
  return { op: "resolve_point", point, toJSON() { return { op: "resolve_point", point: point.toJSON() }; } };
}

export function resolveInterval(iv) {
  return { op: "resolve_interval", interval: iv, toJSON() { return { op: "resolve_interval", interval: iv.toJSON() }; } };
}

export function evaluate(iv, at) {
  return {
    op: "evaluate", interval: iv, instant: at,
    toJSON() { return { op: "evaluate", interval: iv.toJSON(), instant: fmtInstant(at) }; },
  };
}

export function checkDeadline(point, now = null) {
  return {
    op: "check_deadline", point, now,
    toJSON() {
      const body = { op: "check_deadline", point: point.toJSON() };
      if (now != null) body.now = fmtInstant(now);
      return body;
    },
  };
}

function untilSince(kind) {
  return (name, { onUndefined = "strict", instant: at = null } = {}) => ({
    op: kind, name, onUndefined, instant: at,
    toJSON() {
      const body = { op: kind, name, on_undefined: onUndefined };
      if (at != null) body.instant = fmtInstant(at);
      return body;
    },
  });
}

export const until = untilSince("until");
export const since = untilSince("since");

export function nextEventOp({ instant: at = null } = {}) {
  return {
    op: "next_event", instant: at,
    toJSON() {
      const body = { op: "next_event" };
      if (at != null) body.instant = fmtInstant(at);
      return body;
    },
  };
}

export function eventPosition(name, day = null) {
  return { op: "event_position", name, day, toJSON() { return { op: "event_position", name, day }; } };
}

export function dayBounds({ instant: at = null } = {}) {
  return {
    op: "day_bounds", instant: at,
    toJSON() {
      const body = { op: "day_bounds" };
      if (at != null) body.instant = fmtInstant(at);
      return body;
    },
  };
}

export function classifySpan(start, end, endInclusive = false) {
  return {
    op: "classify_span", start, end, endInclusive,
    toJSON() {
      return { op: "classify_span", start: fmtInstant(start), end: fmtInstant(end), end_inclusive: endInclusive };
    },
  };
}

// ---------------------------------------------------------------------------
// ScheduleResolveRequest
// ---------------------------------------------------------------------------

export function profile({ fajrAngleDeg = 18.0, ishaAngleDeg = 17.0, asrShadowRatio = 1.0 } = {}) {
  return {
    toJSON() {
      return { fajr_angle_deg: fajrAngleDeg, isha_angle_deg: ishaAngleDeg, asr_shadow_ratio: asrShadowRatio };
    },
  };
}

export function scheduleResolveRequest({
  lat, lon, operation, elevationM = 0.0, anchor: anchorValue = null, profile: profileValue = null,
  calendarProvider = null, timezoneOverride = null, precision = null,
}) {
  return {
    toJSON() {
      const body = {
        location: { lat, lon, elevation_m: elevationM },
        operation: operation.toJSON(),
      };
      if (anchorValue != null) body.anchor = fmtInstant(anchorValue);
      if (profileValue != null) body.profile = profileValue.toJSON();
      if (calendarProvider != null) body.calendar_provider = calendarProvider;
      if (timezoneOverride != null) body.timezone_override = timezoneOverride;
      if (precision != null) body.precision = precision;
      return body;
    },
  };
}

// ---------------------------------------------------------------------------
// Institutional calendar rules
// ---------------------------------------------------------------------------

export function monthDay(month, day = 1) {
  return { toJSON() { return { type: "month_day", month, day }; } };
}

export function monthEnd(month) {
  return { toJSON() { return { type: "month_end", month }; } };
}

export function nthWeekdayOfMonth(weekday, n, month) {
  return { toJSON() { return { type: "nth_weekday_of_month", weekday, n, month }; } };
}

export function location(lat, lon, elevationM = 0.0) {
  return { toJSON() { return { lat, lon, elevation_m: elevationM }; } };
}

export function fiscalYearResolveRequest({
  hijriYear, startRule, endRule, label = null, calendarProvider = null, location: loc = null,
}) {
  return {
    toJSON() {
      const body = { hijri_year: hijriYear, start_rule: startRule.toJSON(), end_rule: endRule.toJSON() };
      if (label != null) body.label = label;
      if (calendarProvider != null) body.calendar_provider = calendarProvider;
      if (loc != null) body.location = loc.toJSON();
      return body;
    },
  };
}

export function termRule(label, startRule, endRule, yearOffset = 0) {
  return {
    toJSON() {
      return { label, start_rule: startRule.toJSON(), end_rule: endRule.toJSON(), year_offset: yearOffset };
    },
  };
}

export function holidayRule(label, rule, yearOffset = 0) {
  return { toJSON() { return { label, rule: rule.toJSON(), year_offset: yearOffset }; } };
}

export function academicYearResolveRequest({
  hijriYear, openingRule, closingRule, termRules = [], holidays = [],
  label = null, calendarProvider = null, location: loc = null,
}) {
  return {
    toJSON() {
      const body = {
        hijri_year: hijriYear,
        opening_rule: openingRule.toJSON(),
        closing_rule: closingRule.toJSON(),
        term_rules: termRules.map((t) => t.toJSON()),
        holidays: holidays.map((h) => h.toJSON()),
      };
      if (label != null) body.label = label;
      if (calendarProvider != null) body.calendar_provider = calendarProvider;
      if (loc != null) body.location = loc.toJSON();
      return body;
    },
  };
}
