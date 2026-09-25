// Independent verification of tests/vectors/waqt_vectors.json (the Sprint 5
// conformance vectors) — the part of them an implementation WITHOUT a solar
// engine can honestly check.
//
// What this does: treats each vector's frozen astronomical outputs (day
// boundaries, event instants) as INPUT, and re-derives every piece of Waqt
// *semantics* from them: half-open day membership, day length, the position of
// the vector's instant, the position of every event, HH:MM:SS display with no
// 24-hour ceiling, and event ordering.
//
// What this does NOT do, deliberately: recompute Maghrib/Fajr/... from
// latitude and longitude. That is the solar engine (docs/ASTRONOMY.md), and
// claiming to verify it from a table of its own answers would be circular.
// The `hijri_date` field is likewise not re-derived here — it is a calendar
// provider's output, out of scope for a temporal-semantics consumer.

import { formatPosition, parseInstant } from "./instant.mjs";

const EVENT_ORDER = ["fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha"];
const round3 = (x) => Math.round(x * 1000) / 1000;
// Python rounds half-to-even on binary floats, JS half-up on the decimal
// expansion; only an exact .0005 tie can differ, so allow one rounding step.
const near3 = (a, b) => Math.abs(a - b) <= 0.0011;

export function checkVector(v) {
  const problems = [];
  const bad = (msg) => problems.push(`${v.id}: ${msg}`);
  const e = v.expected;

  if (e.status !== "OK") {
    if (e.waqt_position !== undefined || e.events !== undefined || e.day !== undefined) {
      bad("a non-OK vector must not carry a position, events or day (never a guessed time)");
    }
    if (!e.undefined_reason) bad("a non-OK vector must carry an undefined_reason");
    return problems;
  }

  const t = parseInstant(v.input.instant);
  const open = parseInstant(e.day.maghrib_open);
  const close = parseInstant(e.day.maghrib_close);

  // §2 the Waqt day is the half-open interval [open, close)
  if (!(open <= t && t < close)) bad("input instant is not inside [maghrib_open, maghrib_close)");
  if (!(open < close)) bad("day does not have positive length");

  // day length
  if (!near3((close - open) / 1e6, e.day.length_si_seconds)) bad("day.length_si_seconds != close - open");

  // §4 position of the vector's own instant
  const off = t - open;
  const pos = e.waqt_position;
  if (!near3(off / 1e6, pos.total_seconds)) bad(`position total_seconds ${pos.total_seconds} != ${off / 1e6}`);
  if (formatPosition(off) !== pos.display) bad(`position display ${pos.display} != ${formatPosition(off)}`);
  const [h, m, s] = pos.display.split(":").map(Number);
  if (pos.hour !== h || pos.minute !== m || pos.second !== s) bad("hour/minute/second fields disagree with display");
  // position -> instant round trip
  if (Math.abs(open + Math.round(pos.total_seconds * 1e6) - t) > 1000) bad("position does not round-trip to the instant (> 1 ms)");

  // §5 event positions are positions on THIS day's grid, never a separate clock
  let prev = -Infinity;
  for (const name of EVENT_ORDER) {
    const ev = e.events[name];
    if (!ev) continue; // an individually undefined event is simply absent
    const at = parseInstant(ev.instant);
    const evOff = at - open;
    if (!near3(evOff / 1e6, ev.position_total_seconds)) bad(`${name}: position_total_seconds inconsistent with instant`);
    if (formatPosition(evOff) !== ev.position_display) bad(`${name}: display ${ev.position_display} != ${formatPosition(evOff)}`);
    if (at <= prev) bad(`${name}: events are not strictly chronological`);
    prev = at;
  }
  if (!e.events.maghrib) bad("Maghrib must exist whenever the day exists");
  else if (parseInstant(e.events.maghrib.instant) !== close) bad("the maghrib event must be the day's closing Maghrib");
  if (e.events.isha && parseInstant(e.events.isha.instant) < close) bad("Isha must fall after the closing Maghrib");

  // weekday/date shape (label only)
  if (!/^\d{4}-\d{2}-\d{2}$/.test(e.hijri_date)) bad("hijri_date shape");
  return problems;
}

// Properties that relate TWO vectors to each other — the ones a single-vector
// check cannot see. Returns a list of problems.
export function checkCrossVector(byId) {
  const problems = [];
  const bad = (m) => problems.push(m);
  const g = (id) => byId.get(id)?.expected;

  const exact = g("addis-exact-maghrib-boundary");
  if (exact) {
    if (parseInstant(byId.get("addis-exact-maghrib-boundary").input.instant) !== parseInstant(exact.day.maghrib_open)) {
      bad("exact-boundary: the instant must equal the day's opening Maghrib");
    }
    if (exact.waqt_position.display !== "00:00:00" || exact.waqt_position.total_seconds !== 0) {
      bad("exact-boundary: position must be exactly 00:00:00");
    }
  }
  const before = g("addis-one-second-before-maghrib");
  if (before && exact) {
    // half-open tiling: the day one second earlier CLOSES where this one OPENS
    if (before.day.maghrib_close !== exact.day.maghrib_open) bad("one-second-before: previous day's close != this day's open");
    if (parseInstant(byId.get("addis-one-second-before-maghrib").input.instant) >= parseInstant(before.day.maghrib_close)) {
      bad("one-second-before: instant must precede its own day's close");
    }
    if (!(before.waqt_position.total_seconds > before.day.length_si_seconds - 2)) bad("one-second-before: position should be within 2 s of the day length");
  }
  const long = g("london-long-day-near-24h-boundary");
  if (long) {
    if (!(long.day.length_si_seconds > 86400)) bad("london: day should exceed 24 h");
    if (long.waqt_position.hour !== 24 || !long.waqt_position.display.startsWith("24:")) bad("london: hour must be 24, not clamped to 23 or wrapped to 0");
  }
  const std = g("addis-asr-standard");
  const han = g("addis-asr-hanafi");
  if (std && han) {
    const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
    if (!same(std.day, han.day) || !same(std.waqt_position, han.waqt_position)) bad("asr pair: day/position must be identical");
    for (const n of ["fajr", "sunrise", "dhuhr", "maghrib", "isha"]) if (!same(std.events[n], han.events[n])) bad(`asr pair: ${n} must not change`);
    if (!(parseInstant(han.events.asr.instant) > parseInstant(std.events.asr.instant))) bad("asr pair: Hanafi Asr must be later");
  }
  const sea = g("addis-normal-instant");
  const hi = g("addis-elevation-2400m");
  if (sea && hi && !(parseInstant(hi.day.maghrib_close) > parseInstant(sea.day.maghrib_close))) bad("elevation: Maghrib must be later at altitude");
  const tromso = g("tromso-midsummer-undefined");
  if (tromso && tromso.status !== "UNDEFINED") bad("tromso: must be UNDEFINED");
  return problems;
}
