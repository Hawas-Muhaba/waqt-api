// An independent implementation of the Waqt scheduling semantics
// (docs/SCHEDULING.md), written from the specification, not translated from
// the Python source. It computes NO astronomy: it reads a "day table" —
// consecutive Waqt days with their frozen event instants — and applies the
// temporal rules to it.

import { civilDate, formatInstant, formatPosition, parseInstant, roundHalfUp } from "./instant.mjs";

export const EVENT_NAMES = ["fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha"];
const REF_NAMES = [...EVENT_NAMES, "day_start", "day_end"];
// Events whose instant lies in the Waqt day AFTER the one that lists them.
const DAY_SHIFT = { maghrib: 1, isha: 1 };
const MAX_LOOKAHEAD = 8;
const MAX_SPAN_DAYS = 400;

const ABSOLUTE = "absolute_instant";
const ASTRONOMICAL = "astronomical_event";
const WAQT_POSITION = "waqt_position";
const RULE_DERIVED = "rule_derived";

export const Status = {
  OK: "OK",
  EVENT_UNDEFINED: "EVENT_UNDEFINED",
  WINDOW_UNDEFINED: "WINDOW_UNDEFINED",
  NO_VALID_WINDOW: "NO_VALID_WINDOW",
};

export class RuleError extends Error {}
// A vector needs a day the table does not contain: a defect in the vector, never a status.
export class TableExhausted extends Error {}
class DayUnavailable extends Error {}
class Undef extends Error {
  constructor(ref, cause, reason) {
    super(reason);
    this.ref = ref;
    this.cause = cause;
  }
}

// ------------------------------------------------------------------ parsing

const isInt = (v) => Number.isInteger(v);
const isNum = (v) => typeof v === "number" && Number.isFinite(v);

function parsePoint(d, depth = 0) {
  if (depth > 16) throw new RuleError("nesting too deep");
  if (d === null || typeof d !== "object" || Array.isArray(d)) throw new RuleError("point must be an object");
  switch (d.type) {
    case "instant":
      return { type: "instant", us: parseInstant(d.value) };
    case "anchor":
      return { type: "anchor" };
    case "event": {
      if (!REF_NAMES.includes(d.name)) throw new RuleError(`unknown event ${d.name}`);
      if (d.day !== undefined && !isInt(d.day)) throw new RuleError("day must be an integer");
      return { type: "event", name: d.name, day: d.day ?? 0 };
    }
    case "next_event":
    case "prev_event": {
      if (!EVENT_NAMES.includes(d.name)) throw new RuleError(`cannot search for ${d.name}`);
      const on = d.on_undefined ?? "strict";
      if (on !== "strict" && on !== "skip") throw new RuleError("on_undefined must be strict|skip");
      return { type: d.type, name: d.name, inclusive: d.inclusive ?? true, onUndefined: on };
    }
    case "position":
      if (!isNum(d.seconds)) throw new RuleError("position.seconds must be a number");
      return { type: "position", seconds: d.seconds, day: d.day ?? 0 };
    case "offset": {
      const units = { seconds: 1, minutes: 60, waqt_hours: 3600 };
      const given = Object.keys(units).filter((k) => k in d);
      if (given.length !== 1) throw new RuleError("offset needs exactly one of seconds|minutes|waqt_hours");
      if (!isNum(d[given[0]])) throw new RuleError("offset amount must be a number");
      return { type: "offset", base: parsePoint(d.base, depth + 1), seconds: d[given[0]] * units[given[0]] };
    }
    case "fraction":
      if (!isNum(d.fraction)) throw new RuleError("fraction must be a number");
      return { type: "fraction", start: parsePoint(d.start, depth + 1), end: parsePoint(d.end, depth + 1), fraction: d.fraction };
    default:
      throw new RuleError(`unknown point type ${d.type}`);
  }
}

function parseInterval(d) {
  if (!d || d.type !== "interval") throw new RuleError("interval expected");
  const start = d.start == null ? null : parsePoint(d.start);
  const end = d.end == null ? null : parsePoint(d.end);
  if (!start && !end) throw new RuleError("an interval needs at least one bound");
  return { start, end, startInclusive: d.start_inclusive ?? true, endInclusive: d.end_inclusive ?? false };
}

// ------------------------------------------------------------- the day table

export class DayTable {
  constructor(context) {
    this.days = context.days.map((e, index) => {
      const ok = e.status === "OK";
      const events = {};
      if (ok) for (const n of EVENT_NAMES) events[n] = e.events[n] == null ? null : parseInstant(e.events[n]);
      return {
        index, ok, status: e.status, undefinedReason: e.undefined_reason,
        open: ok ? parseInstant(e.open) : null, close: ok ? parseInstant(e.close) : null,
        openIso: e.open, closeIso: e.close, events, hijriLabel: e.hijri_label,
      };
    });
    this.anchorIndex = context.anchor_index;
    this.utcOffset = context.civil_utc_offset_seconds;
  }

  anchorDay(anchorUs) {
    const d = this.days[this.anchorIndex];
    if (d.ok && !(d.open <= anchorUs && anchorUs < d.close)) {
      throw new TableExhausted("the table's anchor day does not contain the anchor");
    }
    return d;
  }

  dayContaining(us, anchorUs) {
    const a = this.days[this.anchorIndex];
    if (a.ok ? a.open <= us && us < a.close : us === anchorUs) return a;
    for (const d of this.days) if (d.ok && d.open <= us && us < d.close) return d;
    throw new TableExhausted(`no table day contains ${formatInstant(us)}`);
  }

  // Step k days from `day`. Stepping FROM an undefined day is impossible;
  // arriving AT one is fine (the caller inspects it).
  neighbor(day, k) {
    let cur = day;
    const step = k > 0 ? 1 : -1;
    for (let i = 0; i < Math.abs(k); i++) {
      if (!cur.ok) throw new DayUnavailable(cur.undefinedReason ?? `Waqt day is ${cur.status}`);
      const next = this.days[cur.index + step];
      if (!next) throw new TableExhausted(`day table ends ${step > 0 ? "after" : "before"} index ${cur.index}`);
      cur = next;
    }
    return cur;
  }
}

// ---------------------------------------------------------------- resolution

const ref = (name, k) => `${name}@day${k >= 0 ? "+" : "-"}${Math.abs(k)}`;

class Env {
  constructor(table, anchorUs) {
    this.table = table;
    this.anchor = anchorUs;
    this.day0 = null;
    this.cache = new Map();
  }
  day(k, r) {
    if (this.cache.has(k)) return this.cache.get(k);
    if (!this.day0) this.day0 = this.table.anchorDay(this.anchor);
    let d;
    try {
      d = this.table.neighbor(this.day0, k);
    } catch (e) {
      if (e instanceof DayUnavailable) throw new Undef(r, "DAY_UNDEFINED", e.message);
      throw e;
    }
    this.cache.set(k, d);
    return d;
  }
  slot(name, k) {
    const r = ref(name, k);
    const d = this.day(k, r);
    if (!d.ok) throw new Undef(r, "DAY_UNDEFINED", d.undefinedReason ?? `Waqt day is ${d.status}`);
    if (name === "day_start") return d.open;
    if (name === "day_end") return d.close;
    const us = d.events[name];
    if (us == null) throw new Undef(r, "EVENT_UNDEFINED_ON_DAY", `Event ${name} does not occur on this Waqt day`);
    return us;
  }
}

const union = (...sets) => new Set(sets.flatMap((s) => [...s]));

function evalPoint(p, env) {
  switch (p.type) {
    case "instant":
      return { us: p.us, bases: new Set([ABSOLUTE]), basis: ABSOLUTE, skipped: [] };
    case "anchor":
      return { us: env.anchor, bases: new Set([ABSOLUTE]), basis: ABSOLUTE, skipped: [] };
    case "event":
      return { us: env.slot(p.name, p.day), bases: new Set([ASTRONOMICAL]), basis: ASTRONOMICAL, skipped: [] };
    case "next_event":
    case "prev_event":
      return evalOccurrence(p, env);
    case "position": {
      const r = `position@day${p.day >= 0 ? "+" : "-"}${Math.abs(p.day)}`;
      const d = env.day(p.day, r);
      if (!d.ok) throw new Undef(r, "DAY_UNDEFINED", d.undefinedReason ?? `Waqt day is ${d.status}`);
      const us = d.open + roundHalfUp(p.seconds * 1e6);
      return { us, bases: new Set([WAQT_POSITION]), basis: WAQT_POSITION, withinDay: d.open <= us && us < d.close, skipped: [] };
    }
    case "offset": {
      const b = evalPoint(p.base, env);
      return { us: b.us + roundHalfUp(p.seconds * 1e6), bases: b.bases, basis: RULE_DERIVED, skipped: b.skipped };
    }
    case "fraction": {
      const a = evalPoint(p.start, env);
      const b = evalPoint(p.end, env);
      return { us: a.us + roundHalfUp((b.us - a.us) * p.fraction), bases: union(a.bases, b.bases), basis: RULE_DERIVED, skipped: [...a.skipped, ...b.skipped] };
    }
    default:
      throw new RuleError(`not a point: ${p.type}`);
  }
}

function evalOccurrence(p, env) {
  const isNext = p.type === "next_event";
  const shift = DAY_SHIFT[p.name] ?? 0;
  const step = isNext ? 1 : -1;
  let k = -shift;
  const skipped = [];
  let firstUndef = null;
  for (let i = 0; i < MAX_LOOKAHEAD; i++) {
    let us;
    try {
      us = env.slot(p.name, k);
    } catch (e) {
      if (!(e instanceof Undef) || p.onUndefined !== "skip") throw e;
      skipped.push(e.ref);
      firstUndef ??= e;
      k += step;
      continue;
    }
    const a = env.anchor;
    const ok = isNext ? (p.inclusive ? us >= a : us > a) : p.inclusive ? us <= a : us < a;
    if (ok) return { us, bases: new Set([ASTRONOMICAL]), basis: ASTRONOMICAL, skipped };
    k += step;
  }
  throw new Undef(firstUndef ? firstUndef.ref : ref(p.name, k), "NO_OCCURRENCE_IN_RANGE", "no occurrence in range");
}

function point(p, env) {
  try {
    const v = evalPoint(p, env);
    return {
      status: Status.OK, instant: formatInstant(v.us), basis: v.basis, depends_on: [...v.bases].sort(),
      within_day: v.withinDay ?? null, cause: null, undefined_ref: null, skipped: v.skipped, _us: v.us,
    };
  } catch (e) {
    if (!(e instanceof Undef)) throw e;
    return {
      status: Status.EVENT_UNDEFINED, instant: null, basis: null, depends_on: [], within_day: null,
      cause: e.cause, undefined_ref: e.ref, skipped: [], _us: null,
    };
  }
}

const publicPoint = (rp) => {
  if (rp === null) return null;
  const { _us, ...rest } = rp;
  return rest;
};

function assembleInterval(iv, s, e) {
  const common = { start_inclusive: iv.startInclusive, end_inclusive: iv.endInclusive };
  const bad = [s, e].filter((x) => x && x.status !== Status.OK);
  const pub = { start: publicPoint(s), end: publicPoint(e) };
  if (bad.length) {
    return { status: Status.WINDOW_UNDEFINED, ...pub, ...common, duration_seconds: null, causes: bad.map(publicPoint) };
  }
  if (s && e) {
    const empty = e._us < s._us || (e._us === s._us && !(iv.startInclusive && iv.endInclusive));
    if (empty) return { status: Status.NO_VALID_WINDOW, ...pub, ...common, duration_seconds: null, causes: [] };
    return { status: Status.OK, ...pub, ...common, duration_seconds: (e._us - s._us) / 1e6, causes: [] };
  }
  return { status: Status.OK, ...pub, ...common, duration_seconds: null, causes: [] };
}

function containsUs(iv, s, e, t) {
  if (s) {
    if (!(t > s._us || (t === s._us && iv.startInclusive))) return false;
  }
  if (e) {
    if (!(t < e._us || (t === e._us && iv.endInclusive))) return false;
  }
  return true;
}

// --------------------------------------------------------------- operations

export class SchedulingEngine {
  constructor(context, anchorIso) {
    this.table = new DayTable(context);
    this.anchor = parseInstant(anchorIso);
  }

  run(op) {
    const inst = op.instant != null ? parseInstant(op.instant) : this.anchor;
    switch (op.op) {
      case "resolve_point":
        return publicPoint(point(parsePoint(op.point), new Env(this.table, this.anchor)));
      case "resolve_interval": {
        const iv = parseInterval(op.interval);
        const env = new Env(this.table, this.anchor);
        return assembleInterval(iv, iv.start && point(iv.start, env), iv.end && point(iv.end, env));
      }
      case "evaluate":
        return this.evaluate(parseInterval(op.interval), parseInstant(op.instant));
      case "check_deadline":
        return this.checkDeadline(parsePoint(op.point), op.now != null ? parseInstant(op.now) : this.anchor);
      case "until":
      case "since":
        return this.measure(op.op, op.name, inst, op.on_undefined ?? "strict");
      case "next_event":
        return this.nextEvent(inst);
      case "event_position":
        return this.eventPosition(op.name, op.day ?? null);
      case "day_bounds":
        return this.dayBounds(inst);
      case "classify_span":
        return this.classifySpan(parseInstant(op.start), parseInstant(op.end), op.end_inclusive ?? false);
      default:
        throw new RuleError(`unknown op ${op.op}`);
    }
  }

  evaluate(iv, t) {
    const env = new Env(this.table, this.anchor);
    const s = iv.start && point(iv.start, env);
    const e = iv.end && point(iv.end, env);
    const w = assembleInterval(iv, s, e);
    const base = { status: w.status, instant: formatInstant(t), window: w };
    if (w.status !== Status.OK) return { ...base, inside: null, relation: null };
    const inside = containsUs(iv, s, e, t);
    let relation = "inside";
    if (!inside) relation = s && (t < s._us || (t === s._us && !iv.startInclusive)) ? "before_window" : "after_window";
    return { ...base, inside, relation };
  }

  checkDeadline(p, now) {
    const rp = point(p, new Env(this.table, this.anchor));
    if (rp.status !== Status.OK) return { status: rp.status, state: null, remaining_seconds: null, deadline: publicPoint(rp) };
    const delta = (rp._us - now) / 1e6;
    return { status: Status.OK, state: delta > 0 ? "pending" : delta === 0 ? "reached" : "passed", remaining_seconds: delta, deadline: publicPoint(rp) };
  }

  measure(kind, name, t, onUndefined) {
    const p = { type: kind === "until" ? "next_event" : "prev_event", name, inclusive: true, onUndefined };
    const rp = point(p, new Env(this.table, t));
    if (rp.status !== Status.OK) return { kind, status: rp.status, seconds: null, target: publicPoint(rp) };
    return { kind, status: Status.OK, seconds: kind === "until" ? (rp._us - t) / 1e6 : (t - rp._us) / 1e6, target: publicPoint(rp) };
  }

  dayBounds(t) {
    const d = this.table.dayContaining(t, this.anchor);
    if (!d.ok) {
      return { status: Status.EVENT_UNDEFINED, instant: formatInstant(t), open: null, close: null, length_seconds: null, position: null, hijri_label: null };
    }
    return {
      status: Status.OK, instant: formatInstant(t), open: d.openIso, close: d.closeIso,
      length_seconds: (d.close - d.open) / 1e6,
      position: { seconds: (t - d.open) / 1e6, display: formatPosition(t - d.open) },
      hijri_label: d.hijriLabel,
    };
  }

  nextEvent(t) {
    let best = null;
    const undefinedEvents = [];
    for (const name of EVENT_NAMES) {
      const rp = point({ type: "next_event", name, inclusive: false, onUndefined: "strict" }, new Env(this.table, t));
      if (rp.status !== Status.OK) undefinedEvents.push({ name, cause: rp.cause });
      else if (best === null || rp._us < best.us) best = { name, us: rp._us };
    }
    if (!best) return { status: Status.EVENT_UNDEFINED, name: null, instant: null, seconds_until: null, position: null, undefined_events: undefinedEvents };
    const d = this.table.dayContaining(best.us, this.anchor);
    return {
      status: Status.OK, name: best.name, instant: formatInstant(best.us), seconds_until: (best.us - t) / 1e6,
      position: d.ok ? { seconds: (best.us - d.open) / 1e6, display: formatPosition(best.us - d.open) } : null,
      undefined_events: undefinedEvents,
    };
  }

  eventPosition(name, day) {
    const env = new Env(this.table, this.anchor);
    const p = day === null ? { type: "next_event", name, inclusive: true, onUndefined: "strict" } : { type: "event", name, day };
    const rp = point(p, env);
    const none = { status: rp.status, name, instant: null, listed: { seconds: null, display: null }, containing: { day_relative_to_listed: null, seconds: null, display: null } };
    if (rp.status !== Status.OK) return none;
    const containing = this.table.dayContaining(rp._us, this.anchor);
    const shift = DAY_SHIFT[name] ?? 0;
    let listed;
    try {
      listed = this.table.neighbor(containing, -shift);
    } catch (e) {
      if (e instanceof DayUnavailable) return { ...none, status: Status.EVENT_UNDEFINED };
      throw e;
    }
    if (!listed.ok) return { ...none, status: Status.EVENT_UNDEFINED };
    return {
      status: Status.OK, name, instant: formatInstant(rp._us),
      listed: { seconds: (rp._us - listed.open) / 1e6, display: formatPosition(rp._us - listed.open) },
      containing: { day_relative_to_listed: shift, seconds: (rp._us - containing.open) / 1e6, display: formatPosition(rp._us - containing.open) },
    };
  }

  classifySpan(s, e, endInclusive) {
    const base = { start: formatInstant(s), end: formatInstant(e), end_inclusive: endInclusive };
    const none = {
      same_waqt_day: null, crosses_maghrib: null, maghrib_boundaries: [], waqt_days_touched: null, start_day: null, end_day: null,
      crosses_civil_midnight: null, start_civil_date: null, end_civil_date: null,
    };
    if (e < s || (e === s && !endInclusive)) return { status: Status.NO_VALID_WINDOW, ...base, duration_seconds: null, ...none };
    const last = endInclusive ? e : e - 1;
    const dur = (e - s) / 1e6;
    const undef = { status: Status.WINDOW_UNDEFINED, ...base, duration_seconds: dur, ...none };
    let d = this.table.dayContaining(s, this.anchor);
    if (!d.ok) return undef;
    const d0 = d;
    const boundaries = [];
    let found = false;
    for (let i = 0; i < MAX_SPAN_DAYS; i++) {
      if (d.open <= last && last < d.close) { found = true; break; }
      boundaries.push(d.closeIso);
      d = this.table.neighbor(d, 1);
      if (!d.ok) return undef;
    }
    if (!found) return undef;
    const info = (x) => ({ open: x.openIso, close: x.closeIso, hijri_label: x.hijriLabel });
    const cs = civilDate(s, this.table.utcOffset);
    const ce = civilDate(last, this.table.utcOffset);
    return {
      status: Status.OK, ...base, duration_seconds: dur, same_waqt_day: boundaries.length === 0, crosses_maghrib: boundaries.length > 0,
      maghrib_boundaries: boundaries, waqt_days_touched: boundaries.length + 1, start_day: info(d0), end_day: info(d),
      crosses_civil_midnight: cs !== ce, start_civil_date: cs, end_civil_date: ce,
    };
  }
}

// Recursively drop the two non-normative prose fields before comparing.
export function normative(x) {
  if (Array.isArray(x)) return x.map(normative);
  if (x && typeof x === "object") {
    const out = {};
    for (const [k, v] of Object.entries(x)) if (k !== "description" && k !== "reason") out[k] = normative(v);
    return out;
  }
  return x;
}
