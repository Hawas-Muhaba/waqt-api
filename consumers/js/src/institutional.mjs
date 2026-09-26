// waqt-consumer-js / institutional.mjs
//
// Independent JavaScript implementation of Sprint 7's calendar-convention
// rules (waqt.institutional.rules / week / fiscal_year / academic_year),
// consuming ONLY the frozen `month_table` each vector carries — never any
// Hijri arithmetic, never astronomy. See tests/vectors/institutional_vectors.json
// and docs/INSTITUTIONAL.md for the specification this reproduces.
//
// Week arithmetic needs no table at all: it's pure Gregorian-civil-date
// math, computed straight from JS's own Date, which is exactly the point
// docs/INSTITUTIONAL.md makes about weeks being calendar-independent.

const ISLAMIC_WEEKDAY_NAMES = [
  "al-Ahad", "al-Ithnayn", "ath-Thulatha", "al-Arbiaa", "al-Khamis", "al-Jumuah", "as-Sabt",
];

// A UTC Date's getUTCDay() is already Sunday=0..Saturday=6, which lines up
// with ISLAMIC_WEEKDAY_NAMES index-for-index (al-Ahad=Sunday=0).
export function islamicWeekdayOf(isoDate) {
  const d = new Date(`${isoDate}T00:00:00Z`);
  return ISLAMIC_WEEKDAY_NAMES[d.getUTCDay()];
}

function pad2(n) {
  return String(n).padStart(2, "0");
}

function hijriIso(year, month, day) {
  return `${String(year).padStart(4, "0")}-${pad2(month)}-${pad2(day)}`;
}

// -- rule resolution over a frozen month_table -------------------------------

function monthEntries(monthTable, month) {
  const entries = monthTable[String(month)];
  if (!entries) throw new Error(`month_table has no entries for month ${month}`);
  return entries;
}

export function resolveRule(rule, year, monthTable) {
  if (rule.type === "month_day") {
    const entries = monthEntries(monthTable, rule.month);
    const e = entries.find((x) => x.day === rule.day);
    if (!e) throw new Error(`day ${rule.day} does not exist in month ${rule.month}`);
    return { hijri: hijriIso(year, rule.month, e.day), gregorian: e.gregorian };
  }
  if (rule.type === "month_end") {
    const entries = monthEntries(monthTable, rule.month);
    const e = entries[entries.length - 1];
    return { hijri: hijriIso(year, rule.month, e.day), gregorian: e.gregorian };
  }
  if (rule.type === "nth_weekday_of_month") {
    const entries = monthEntries(monthTable, rule.month);
    const matches = entries.filter((x) => x.weekday === rule.weekday);
    if (matches.length === 0) throw new Error(`no ${rule.weekday} in month ${rule.month}`);
    const idx = rule.n > 0 ? rule.n - 1 : matches.length + rule.n;
    if (idx < 0 || idx >= matches.length) throw new Error(`n=${rule.n} out of range (${matches.length} matches)`);
    const e = matches[idx];
    return { hijri: hijriIso(year, rule.month, e.day), gregorian: e.gregorian };
  }
  throw new Error(`unknown rule type ${rule.type}`);
}

// -- operations ---------------------------------------------------------------

export function weekDates(dateStr, firstDay) {
  const startIdx = ISLAMIC_WEEKDAY_NAMES.indexOf(firstDay);
  if (startIdx < 0) throw new Error(`unknown weekday ${firstDay}`);
  const dIdx = ISLAMIC_WEEKDAY_NAMES.indexOf(islamicWeekdayOf(dateStr));
  const back = (dIdx - startIdx + 7) % 7;
  const d = new Date(`${dateStr}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() - back);
  const week_dates = [];
  for (let k = 0; k < 7; k++) {
    const x = new Date(d);
    x.setUTCDate(d.getUTCDate() + k);
    week_dates.push(x.toISOString().slice(0, 10));
  }
  const weekdays = Array.from({ length: 7 }, (_, k) => ISLAMIC_WEEKDAY_NAMES[(startIdx + k) % 7]);
  return { week_dates, weekdays };
}

export function fiscalYear(op, monthTable) {
  const start = resolveRule(op.start_rule, op.year, monthTable);
  const end = resolveRule(op.end_rule, op.year, monthTable);
  return { start, end };
}

export function academicYear(op, monthTable) {
  const opening = resolveRule(op.opening_rule, op.year, monthTable);
  const closing = resolveRule(op.closing_rule, op.year, monthTable);
  const terms = (op.term_rules || []).map((t) => ({
    label: t.label,
    start: resolveRule(t.start_rule, op.year, monthTable),
    end: resolveRule(t.end_rule, op.year, monthTable),
  }));
  return { opening, closing, terms };
}

// -- vector runner --------------------------------------------------------------

export function runVector(v) {
  const op = v.operation;
  const monthTable = v.context.month_table || {};
  const year = v.context.hijri_year;
  switch (op.op) {
    case "month_day":
    case "month_end":
    case "nth_weekday_of_month":
      return resolveRule({ ...op, type: op.op }, year, monthTable);
    case "week_dates":
      return weekDates(op.date, op.first_day);
    case "fiscal_year":
      return fiscalYear(op, monthTable);
    case "academic_year":
      return academicYear(op, monthTable);
    default:
      throw new Error(`unknown op ${op.op}`);
  }
}
