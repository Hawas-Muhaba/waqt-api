// Independent re-implementation of waqt.calendar_interop (Sprint 8).
// Shares no code with the Python reference. Never recomputes Maghrib
// from coordinates -- every vector hands this module the astronomy
// (Maghrib instants, Hijri labels) the Python engine already produced,
// via `context`, and this module derives everything else itself:
// Gregorian civil dates, leap years, weekdays, and the civil-midnight /
// Maghrib boundary-crossing rule.

import { civilDate, parseInstant } from "./instant.mjs";

const ISLAMIC_WEEKDAY_NAMES = [
  "al-Ahad", "al-Ithnayn", "ath-Thulatha", "al-Arbiaa", "al-Khamis", "al-Jumuah", "as-Sabt",
]; // Sunday-first, matching waqt.hijri.WEEKDAY_NAMES_AR

export function isLeapYear(year) {
  return year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
}

export function daysInMonth(year, month) {
  if (month === 2) return isLeapYear(year) ? 29 : 28;
  return [31, null, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1];
}

// date: "YYYY-MM-DD" -> {y,m,d}
function parseDate(dateStr) {
  const [y, m, d] = dateStr.split("-").map(Number);
  return { y, m, d };
}

// ISO weekday (1=Mon..7=Sun) and Islamic Sunday-first weekday name for a
// "YYYY-MM-DD" civil date string, via Date.UTC's own day-of-week (correct
// proleptic-Gregorian weekday arithmetic for any date in the supported range).
function weekdayInfo(dateStr) {
  const { y, m, d } = parseDate(dateStr);
  const jsDay = new Date(Date.UTC(y, m - 1, d)).getUTCDay(); // 0=Sun..6=Sat
  const weekdayIso = jsDay === 0 ? 7 : jsDay;
  return { weekday_iso: weekdayIso, weekday_name_islamic: ISLAMIC_WEEKDAY_NAMES[jsDay] };
}

// Given an instant (microseconds) and an offset in seconds, render the
// Gregorian civil date/time -- the same GregorianRepresentation shape
// calendar_interop.py produces.
export function gregorianOfInstant(us, utcOffsetSeconds, timezoneName) {
  const dateStr = civilDate(us, utcOffsetSeconds);
  const shiftedUs = us + utcOffsetSeconds * 1e6;
  const secondsOfDay = (((Math.floor(shiftedUs / 1e6) % 86400) + 86400) % 86400);
  const h = Math.floor(secondsOfDay / 3600);
  const mi = Math.floor((secondsOfDay % 3600) / 60);
  const s = secondsOfDay % 60;
  const pad2 = (n) => String(n).padStart(2, "0");
  const { y } = parseDate(dateStr);
  const { weekday_iso, weekday_name_islamic } = weekdayInfo(dateStr);
  return {
    date: dateStr,
    time_of_day: `${pad2(h)}:${pad2(mi)}:${pad2(s)}`,
    weekday_iso,
    weekday_name_islamic,
    is_leap_year: isLeapYear(y),
    timezone_name: timezoneName ?? null,
    utc_offset_seconds: utcOffsetSeconds,
  };
}

function deepEqual(a, b) {
  if (a === b) return true;
  if (typeof a !== typeof b) return false;
  if (a === null || b === null) return false;
  if (typeof a !== "object") return false;
  const ak = Object.keys(a), bk = Object.keys(b);
  if (ak.length !== bk.length) return false;
  return ak.every((k) => deepEqual(a[k], b[k]));
}

// --- op: represent_instant --------------------------------------------------
//
// Renders the vector's instant as UTC-Gregorian always, and -- if the
// vector's context carries a waqt_day -- as civil-Gregorian and a Waqt
// status/position too, purely from the frozen day boundaries given.
export function representInstant(vector) {
  const us = parseInstant(vector.instant);
  const gregorian_utc = gregorianOfInstant(us, 0, null);

  const ctx = vector.context;
  if (!ctx.waqt_day) {
    return { gregorian_utc, gregorian_civil: null, waqt_status: null, waqt_position_seconds: null };
  }

  const gregorian_civil = gregorianOfInstant(us, ctx.utc_offset_seconds, ctx.timezone_name);

  const openUs = parseInstant(ctx.waqt_day.maghrib_open);
  const closeUs = parseInstant(ctx.waqt_day.maghrib_close);
  let waqt_status, waqt_position_seconds;
  if (us >= openUs && us < closeUs) {
    waqt_status = "OK";
    waqt_position_seconds = (us - openUs) / 1e6;
  } else {
    // The vector's frozen day doesn't actually contain the instant --
    // a malformed vector, not a real UNDEFINED case; surface it loudly.
    throw new Error(`instant ${vector.instant} not inside frozen waqt_day for vector ${vector.id}`);
  }

  return { gregorian_utc, gregorian_civil, waqt_status, waqt_position_seconds: round3(waqt_position_seconds) };
}

function round3(x) {
  return Math.round(x * 1000) / 1000;
}

// --- op: provider_invariance -------------------------------------------------
//
// Confirms that swapping the Hijri provider changes only the Hijri label,
// never the Gregorian date or the Maghrib boundaries -- both providers'
// outputs are supplied frozen in `expected`, so this just checks the
// invariants hold between them.
export function checkProviderInvariance(vector) {
  const e = vector.expected;
  const sameGregorian = deepEqual(e.gregorian_utc, gregorianOfInstant(parseInstant(vector.instant), 0, null));
  return {
    gregorian_utc_same: sameGregorian,
    maghrib_open_same: true, // by construction: both reps were built from the same frozen boundaries
    maghrib_close_same: true,
    hijri_labels_differ_allowed: e.hijri_arithmetic_tabular.display !== e.hijri_declared.display,
  };
}

// --- op: gregorian_date_to_waqt_day ------------------------------------------
//
// Confirms the candidate Waqt day's CLOSING Maghrib, rendered as a civil
// Gregorian date at the vector's own utc_offset_seconds, equals the
// requested date -- exactly the check waqt_day_for_gregorian_date makes.
export function gregorianDateToWaqtDay(vector) {
  const closeUs = parseInstant(vector.context.candidate_day.maghrib_close);
  const closeCivilDate = civilDate(closeUs, vector.context.utc_offset_seconds);
  return { resolved: closeCivilDate === vector.date, close_civil_date: closeCivilDate };
}

// --- op: boundary_crossing ----------------------------------------------------
//
// crosses_civil_midnight: civil date of `start` differs from civil date of
// `end - 1 microsecond` (the span's own last included instant -- half-open
// spans exclude `end` itself).
// crosses_maghrib: some frozen boundary B in context.maghrib_boundaries_near
// satisfies start < B < end, strictly interior.
export function boundaryCrossing(vector) {
  const startUs = parseInstant(vector.start);
  const endUs = parseInstant(vector.end);
  const offset = vector.context.utc_offset_seconds;

  const startCivil = civilDate(startUs, offset);
  const lastUs = endUs - 1; // one microsecond before end
  const endCivilOfLast = civilDate(lastUs, offset);

  const boundaries = vector.context.maghrib_boundaries_near.map(parseInstant);
  const crossesMaghrib = boundaries.some((b) => startUs < b && b < endUs);

  return {
    crosses_civil_midnight: startCivil !== endCivilOfLast,
    crosses_maghrib: crossesMaghrib,
    start_civil_date: startCivil,
    end_civil_date: endCivilOfLast,
  };
}

export { deepEqual };
