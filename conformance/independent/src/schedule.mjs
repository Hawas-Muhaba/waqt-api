// schedule.mjs -- Waqt scheduling: points, windows, deadlines, spans (docs/SCHEDULING.md).
// Works over a DaySource: either a frozen DAY TABLE (exact mode) or LIVE astronomy.
import { parseInstant, formatInstant, WaqtError, US_PER_SEC, localDateNum, islamicWeekdayName } from './timeutil.mjs';
import { Site, posDisplay, UNDEF_MAGHRIB } from './waqtday.mjs';
import { EVENT_NAMES } from './astro/events.mjs';
import { hijriFromDay } from './calendar/providers.mjs';

const iso = (us) => (us === null || us === undefined ? null : formatInstant(us));
const halfUp = (x) => Math.floor(x + 0.5);
const slotRef = (name, k) => `${name}@day${k >= 0 ? '+' : '-'}${Math.abs(k)}`;
const MAX_SLOTS = 8;

// ---------------------------------------------------------------- day sources
export class TableSource {
  constructor(ctx) {
    this.days = ctx.days.map((d) => ({
      status: d.status, open: d.open ? parseInstant(d.open) : null, close: d.close ? parseInstant(d.close) : null,
      events: d.events ? Object.fromEntries(EVENT_NAMES.map((n) => [n, d.events[n] ? parseInstant(d.events[n]) : null])) : null,
      hijri_label: d.hijri_label ?? null, undefined_reason: d.undefined_reason ?? null,
    }));
    this.anchorIndex = ctx.anchor_index;
    this.offset = ctx.civil_utc_offset_seconds ?? 0;
  }
  day(k) { // k relative to the anchor's day
    const d = this.days[this.anchorIndex + k];
    return d ? { ...d, k } : null;
  }
  civilDate(us) { return Math.floor((us + this.offset * US_PER_SEC) / 86400e6); }
  locate(us) { // -> k of the day containing us, 'undefined', or null
    for (let i = 0; i < this.days.length; i++) {
      const d = this.days[i];
      if (d.status === 'OK' && d.open <= us && us < d.close) return i - this.anchorIndex;
    }
    return this.days.some((d) => d.status !== 'OK') ? 'undefined' : null;
  }
}
export class LiveSource {
  constructor(ctx, anchorUs) {
    this.site = new Site(ctx.location, ctx.timezone, ctx.profile, ctx.calendar);
    this.zone = ctx.timezone;
    const d0 = this.site.dayContaining(anchorUs);
    this.label0 = d0.idx;
    this.cache = new Map();
  }
  day(k) {
    let d = this.cache.get(k);
    if (!d) {
      d = this.site.dayByIndex(this.label0 + k);
      d.k = k;
      d.hijri_label = d.status === 'OK' ? (this.site.hijriLabelSafe(d).hijri || { date: null }).date : null;
      this.cache.set(k, d);
    }
    return d;
  }
  civilDate(us) { return localDateNum(this.zone, us); }
  locate(us) {
    const d = this.site.dayContaining(us);
    if (d.status !== 'OK') return 'undefined';
    return d.idx - this.label0;
  }
}

// ---------------------------------------------------------------- point results
const okPoint = (us, basis, deps, extra = {}) => ({ status: 'OK', instant: iso(us), basis, depends_on: [...new Set(deps)].sort(), description: '', within_day: null, reason: null, cause: null, undefined_ref: null, skipped: [], ...extra });
const badPoint = (cause, ref, reason, extra = {}) => ({ status: 'EVENT_UNDEFINED', instant: null, basis: null, depends_on: [], description: '', within_day: null, reason, cause, undefined_ref: ref, skipped: [], ...extra });
const isOk = (p) => p && p.status === 'OK';
const us = (p) => parseInstant(p.instant);

export class Engine {
  constructor(src, anchorUs) { this.src = src; this.A = anchorUs; }

  eventOfSlot(name, k) { // -> {us} | {bad}
    const d = this.src.day(k);
    const step = k > 0 ? 1 : -1;
    for (let j = step; Math.abs(j) < Math.abs(k) + (d ? 0 : 1) && k !== 0; j += step) {
      const m = this.src.day(j);
      if (m && m.status !== 'OK') return { bad: badPoint('DAY_UNDEFINED', slotRef(name, k), m.undefined_reason || UNDEF_MAGHRIB) };
    }
    if (!d) return { bad: badPoint('NO_OCCURRENCE_IN_RANGE', slotRef(name, k), `day slot ${k} is outside the available range`) };
    if (d.status !== 'OK') return { bad: badPoint('DAY_UNDEFINED', slotRef(name, k), d.undefined_reason || UNDEF_MAGHRIB) };
    if (name === 'day_start') return { us: d.open };
    if (name === 'day_end') return { us: d.close };
    const e = d.events[name];
    if (e === null || e === undefined) return { bad: badPoint('EVENT_UNDEFINED_ON_DAY', slotRef(name, k), `Event '${name}' does not occur on this Waqt day.`) };
    return { us: e };
  }

  // occurrence search. dir=+1 next (>= A), dir=-1 prev (<= A)
  occurrence(name, dir, policy, inclusive = true) {
    const skipped = [];
    const lo = -3, hi = MAX_SLOTS + 2;
    let examined = 0, firstRef = null;
    const slots = dir > 0 ? range(lo, hi) : range(-hi, 3).reverse();
    let best = null;
    for (const k of slots) {
      const d = this.src.day(k);
      if (!d) continue;
      const r = this.eventOfSlot(name, k);
      if (r.bad) {
        // an undefined slot matters only if its day could still hold the answer
        const relevant = dir > 0 ? (d.status !== 'OK' ? k >= 0 : d.close > this.A) : (d.status !== 'OK' ? k <= 0 : d.open <= this.A);
        if (!relevant) continue;
        if (best !== null) break;
        examined++;
        if (policy !== 'skip') return { ...r.bad, instant: null };
        skipped.push(r.bad.undefined_ref); firstRef ??= r.bad.undefined_ref;
        if (examined >= MAX_SLOTS) break;
        continue;
      }
      const inRange = dir > 0 ? (inclusive ? r.us >= this.A : r.us > this.A) : (inclusive ? r.us <= this.A : r.us < this.A);
      if (inRange) {
        if (dir > 0) { return okPoint(r.us, 'astronomical_event', ['astronomical_event'], { skipped }); }
        best = r.us; return okPoint(best, 'astronomical_event', ['astronomical_event'], { skipped });
      }
      if (dir > 0 ? false : false) continue;
    }
    return badPoint('NO_OCCURRENCE_IN_RANGE', firstRef ?? slotRef(name, 0),
      `No ${dir > 0 ? 'next' : 'previous'} ${name} found within ${MAX_SLOTS} day-slots (skipped undefined: ${skipped.join(', ')}).`, { skipped: [] });
  }

  resolve(pt, policy) {
    switch (pt.type) {
      case 'instant': return okPoint(parseInstant(pt.value), 'absolute_instant', ['absolute_instant']);
      case 'anchor': return okPoint(this.A, 'absolute_instant', ['absolute_instant']);
      case 'event': {
        const k = pt.day ?? 0;
        const r = this.eventOfSlot(pt.name, k);
        return r.bad ? r.bad : okPoint(r.us, 'astronomical_event', ['astronomical_event']);
      }
      case 'next_event': return this.occurrence(pt.name, +1, pt.on_undefined ?? policy, pt.inclusive !== false);
      case 'prev_event': return this.occurrence(pt.name, -1, pt.on_undefined ?? policy, pt.inclusive !== false);
      case 'position': {
        const k = pt.day ?? 0;
        const d = this.src.day(k);
        if (!d || d.status !== 'OK') return badPoint('DAY_UNDEFINED', `position@day${k >= 0 ? '+' : '-'}${Math.abs(k)}`, d?.undefined_reason || UNDEF_MAGHRIB);
        const secs = pt.seconds ?? 0;
        const t = d.open + halfUp(secs * 1e6);
        return okPoint(t, 'waqt_position', ['waqt_position'], { within_day: t >= d.open && t < d.close });
      }
      case 'offset': {
        const b = this.resolve(pt.base, policy);
        if (!isOk(b)) return { ...b, description: '' };
        const secs = (pt.seconds ?? 0) + (pt.minutes ?? 0) * 60 + (pt.hours ?? 0) * 3600 + (pt.waqt_hours ?? 0) * 3600;
        return okPoint(us(b) + halfUp(secs * 1e6), 'rule_derived', b.depends_on);
      }
      case 'fraction': {
        const a = this.resolve(pt.start, policy), b = this.resolve(pt.end, policy);
        if (!isOk(a)) return a;
        if (!isOk(b)) return b;
        const A = us(a), B = us(b);
        return okPoint(A + halfUp((B - A) * pt.fraction), 'rule_derived', [...a.depends_on, ...b.depends_on]);
      }
      default: throw new WaqtError('INVALID_RULE', `unknown point type: ${pt.type}`);
    }
  }

  resolveInterval(iv, policy) {
    const s = iv.start ? this.resolve(iv.start, policy) : null;
    const e = iv.end ? this.resolve(iv.end, policy) : null;
    const base = { start: s, end: e, start_inclusive: iv.start_inclusive ?? true, end_inclusive: iv.end_inclusive ?? false };
    const causes = [s, e].filter((p) => p && !isOk(p));
    if (causes.length) {
      return { status: 'WINDOW_UNDEFINED', ...base, duration_seconds: null, reason: causes.map((c) => c.reason).join('; '), causes };
    }
    if (s && e) {
      const a = us(s), b = us(e);
      if (b < a || (b === a && !(base.start_inclusive && base.end_inclusive))) {
        return { status: 'NO_VALID_WINDOW', ...base, duration_seconds: null, reason: b < a ? 'end is before start' : 'start equals end and the interval is not closed at both ends', causes: [] };
      }
      return { status: 'OK', ...base, duration_seconds: (b - a) / US_PER_SEC, reason: null, causes: [] };
    }
    return { status: 'OK', ...base, duration_seconds: null, reason: null, causes: [] };
  }

  evaluate(iv, t, policy) {
    const w = this.resolveInterval(iv, policy);
    if (w.status !== 'OK') return { status: w.status, instant: iso(t), inside: null, relation: null, window: w };
    const lo = w.start ? us(w.start) : -Infinity, hi = w.end ? us(w.end) : Infinity;
    const before = t < lo || (t === lo && !w.start_inclusive);
    const after = t > hi || (t === hi && !w.end_inclusive);
    return { status: 'OK', instant: iso(t), inside: !before && !after, relation: before ? 'before_window' : after ? 'after_window' : 'inside', window: w };
  }

  checkDeadline(pt, now, policy) {
    const d = this.resolve(pt, policy);
    if (!isOk(d)) return { status: d.status, state: null, remaining_seconds: null, deadline: d };
    const t = us(d);
    return { status: 'OK', state: now < t ? 'pending' : now === t ? 'reached' : 'passed', remaining_seconds: (t - now) / US_PER_SEC, deadline: d };
  }

  untilSince(kind, name, policy) {
    const tgt = this.occurrence(name, kind === 'until' ? +1 : -1, policy);
    if (!isOk(tgt)) return { kind, status: tgt.status, seconds: null, target: tgt };
    const t = us(tgt);
    return { kind, status: 'OK', seconds: kind === 'until' ? (t - this.A) / US_PER_SEC : (this.A - t) / US_PER_SEC, target: tgt };
  }

  dayInfo(d) { return { open: iso(d.open), close: iso(d.close), hijri_label: d.hijri_label }; }

  dayBounds() {
    const d = this.src.day(0);
    if (!d || d.status !== 'OK') return { status: 'EVENT_UNDEFINED', instant: iso(this.A), open: null, close: null, length_seconds: null, position: null, hijri_label: null, reason: d?.undefined_reason || UNDEF_MAGHRIB };
    const secs = (this.A - d.open) / US_PER_SEC;
    return { status: 'OK', instant: iso(this.A), open: iso(d.open), close: iso(d.close), length_seconds: (d.close - d.open) / US_PER_SEC, position: { seconds: secs, display: posDisplay(secs) }, hijri_label: d.hijri_label, reason: null };
  }

  nextEvent() {
    const d0 = this.src.day(0);
    const undefinedEvents = [];
    if (d0 && d0.status === 'OK') for (const n of EVENT_NAMES) if (d0.events[n] === null) undefinedEvents.push({ name: n, reason: `Event '${n}' does not occur on this Waqt day.`, cause: 'EVENT_UNDEFINED_ON_DAY' });
    let best = null;
    for (let k = -2; k <= 2; k++) {
      const d = this.src.day(k);
      if (!d || d.status !== 'OK') continue;
      for (const n of EVENT_NAMES) { const e = d.events[n]; if (e !== null && e > this.A && (!best || e < best.us)) best = { name: n, us: e }; }
    }
    if (!best) return { status: 'EVENT_UNDEFINED', name: null, instant: null, seconds_until: null, position: null, undefined_events: undefinedEvents, reason: 'no upcoming event found' };
    const kc = this.src.locate(best.us);
    const dc = typeof kc === 'number' ? this.src.day(kc) : null;
    const secs = dc ? (best.us - dc.open) / US_PER_SEC : null;
    return { status: 'OK', name: best.name, instant: iso(best.us), seconds_until: (best.us - this.A) / US_PER_SEC, position: dc ? { seconds: secs, display: posDisplay(secs) } : null, undefined_events: undefinedEvents, reason: null };
  }

  eventPosition(name, dayOpt) {
    const slot = dayOpt ?? (name === 'maghrib' || name === 'isha' ? -1 : 0);
    const r = this.eventOfSlot(name, slot);
    if (r.bad) return { status: 'EVENT_UNDEFINED', name, instant: null, listed: {}, containing: {}, reason: r.bad.reason };
    const dl = this.src.day(slot);
    const kc = this.src.locate(r.us);
    const listedSecs = (r.us - dl.open) / US_PER_SEC;
    const dc = typeof kc === 'number' ? this.src.day(kc) : null;
    return {
      status: 'OK', name, instant: iso(r.us), listed: { seconds: listedSecs, display: posDisplay(listedSecs) },
      containing: dc ? { day_relative_to_listed: kc - slot, seconds: (r.us - dc.open) / US_PER_SEC, display: posDisplay((r.us - dc.open) / US_PER_SEC) } : {},
      reason: null,
    };
  }

  classifySpan(start, end, endInclusive) {
    const last = endInclusive ? end : end - 1;
    const base = { start: iso(start), end: iso(end), end_inclusive: !!endInclusive, duration_seconds: (end - start) / US_PER_SEC };
    if (end < start || (end === start && !endInclusive)) {
      return { status: 'NO_VALID_WINDOW', ...base, duration_seconds: null, maghrib_boundaries: [], reason: end < start ? 'end is before start' : 'empty half-open span' };
    }
    const ks = this.src.locate(start), ke = this.src.locate(last);
    if (typeof ks !== 'number' || typeof ke !== 'number') {
      return { status: 'WINDOW_UNDEFINED', ...base, maghrib_boundaries: [], reason: UNDEF_MAGHRIB };
    }
    for (let k = ks; k <= ke; k++) { const d = this.src.day(k); if (!d || d.status !== 'OK') return { status: 'WINDOW_UNDEFINED', ...base, maghrib_boundaries: [], reason: UNDEF_MAGHRIB }; }
    const bounds = [];
    for (let k = ks + 1; k <= ke; k++) bounds.push(iso(this.src.day(k).open));
    const crosses = ks !== ke;
    const dS = this.src.day(ks), dE = this.src.day(ke);
    const cs = this.src.civilDate(start), ce = this.src.civilDate(last);
    return {
      status: 'OK', ...base, same_waqt_day: !crosses, crosses_maghrib: crosses, maghrib_boundaries: bounds, waqt_days_touched: ke - ks + 1,
      start_day: this.dayInfo(dS), end_day: this.dayInfo(dE), crosses_civil_midnight: cs !== ce,
      start_civil_date: dateStr(cs), end_civil_date: dateStr(ce), reason: null,
    };
  }
}
const range = (a, b) => { const r = []; for (let i = a; i <= b; i++) r.push(i); return r; };
import { formatDate } from './timeutil.mjs';
const dateStr = (n) => formatDate(n);

// ---------------------------------------------------------------- op dispatcher
export function runSchedule(input) {
  const ctx = input.context;
  const A = parseInstant(input.anchor);
  const src = ctx.days ? new TableSource(ctx) : new LiveSource(ctx, A);
  const eng = new Engine(src, A);
  const op = input.operation;
  const policy = op.on_undefined || 'strict';
  switch (op.op) {
    case 'resolve_point': return eng.resolve(op.point, policy);
    case 'resolve_interval': return eng.resolveInterval(op.interval, policy);
    case 'evaluate': return eng.evaluate(op.interval, parseInstant(op.instant), policy);
    case 'check_deadline': return eng.checkDeadline(op.point, op.now ? parseInstant(op.now) : A, policy);
    case 'until': return eng.untilSince('until', op.name, policy);
    case 'since': return eng.untilSince('since', op.name, policy);
    case 'event_position': return eng.eventPosition(op.name, op.day);
    case 'day_bounds': return eng.dayBounds();
    case 'next_event': return eng.nextEvent();
    case 'classify_span': return eng.classifySpan(parseInstant(op.start), parseInstant(op.end), !!op.end_inclusive);
    default: throw new WaqtError('INVALID_RULE', `unknown scheduling op: ${op.op}`);
  }
}
