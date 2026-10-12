// waqtday.mjs -- the Waqt day model computed from coordinates.
//   Maghrib(X)   : the evening-horizon crossing in the transit-anchored solar day of civil date X
//   WaqtDay      : [Maghrib(X-1), Maghrib(X)) labelled with civil date X (its CLOSING Maghrib's date)
//   listing(X)   : the six events of civil date X, positioned relative to Maghrib(X-1)
import { solarDay, EVENT_NAMES } from './astro/events.mjs';
import { US_PER_SEC, localDateNum, formatDate, islamicWeekdayName, WaqtError } from './timeutil.mjs';
import { hijriFromDay } from './calendar/providers.mjs';
import { DEFAULT_PROVIDER } from './defaults.mjs';

export const UNDEF_MAGHRIB = 'Maghrib (sunset) does not occur for this date/location \u2014 polar day or polar night. No high-latitude fallback is applied automatically; see SCOPE.md.';

export function normalizeProfile(p = {}) {
  if (!p || typeof p !== 'object' || Array.isArray(p)) throw new WaqtError('VALIDATION_ERROR', 'profile must be a JSON object');
  const prof = {
    fajr_angle_deg: p.fajr_angle_deg === undefined ? 18.0 : p.fajr_angle_deg,
    isha_angle_deg: p.isha_angle_deg === undefined ? 17.0 : p.isha_angle_deg,
    asr_shadow_ratio: p.asr_shadow_ratio === undefined ? 1.0 : p.asr_shadow_ratio,
  };
  for (const k of ['fajr_angle_deg', 'isha_angle_deg']) {
    if (typeof prof[k] !== 'number' || !isFinite(prof[k]) || prof[k] <= 0 || prof[k] > 90) throw new WaqtError('VALIDATION_ERROR', `${k} must be a finite number with 0 < value <= 90`);
  }
  if (typeof prof.asr_shadow_ratio !== 'number' || !isFinite(prof.asr_shadow_ratio) || prof.asr_shadow_ratio <= 0) throw new WaqtError('VALIDATION_ERROR', 'asr_shadow_ratio must be a positive number');
  return prof;
}
export function normalizeSite(loc) {
  if (!loc || typeof loc.lat !== 'number' || typeof loc.lon !== 'number' || !isFinite(loc.lat) || !isFinite(loc.lon) || loc.lat < -90 || loc.lat > 90 || loc.lon < -180 || loc.lon > 180) {
    throw new WaqtError('VALIDATION_ERROR', 'lat must be in [-90, 90] and lon in [-180, 180]');
  }
  const elev = loc.elevation_m ?? 0;
  if (typeof elev !== 'number' || !isFinite(elev)) throw new WaqtError('VALIDATION_ERROR', 'elevation_m must be a finite number');
  return { lat: loc.lat, lon: loc.lon, elev };
}

export class Site {
  constructor(location, zone, profile, calendar) {
    this.site = normalizeSite(location);
    this.zone = zone;
    this.profile = normalizeProfile(profile);
    this.calendar = calendar || { provider: DEFAULT_PROVIDER };
  }
  listing(X) { return solarDay(this.site, this.zone, X, this.profile); }
  maghrib(X) { return this.listing(X).events.maghrib; }

  // The Waqt day indexed by transit date k: [Maghrib(k-1), Maghrib(k)), listing = events around transit k.
  // Its LABEL is the civil date of the CLOSING Maghrib INSTANT (which is k, or k+1 when Maghrib falls after
  // local midnight).
  dayByIndex(k) {
    const open = this.maghrib(k - 1), close = this.maghrib(k);
    if (open === null || close === null) return { status: 'UNDEFINED', idx: k, label_day: k, open, close, events: null, undefined_reason: UNDEF_MAGHRIB };
    const l = this.listing(k);
    return { status: 'OK', idx: k, label_day: localDateNum(this.zone, close), open, close, events: l.events, reasons: l.reasons, undefined_reason: null };
  }
  // The Waqt day containing instant t: the consecutive Maghrib pair that brackets t.
  dayContaining(us) {
    const X = localDateNum(this.zone, us);
    let j = null;
    for (let k = X + 1; k >= X - 2; k--) {
      const m = this.maghrib(k);
      if (m !== null && m <= us) { j = k; break; }
    }
    if (j === null) return { status: 'UNDEFINED', idx: X, label_day: X, open: null, close: null, events: null, undefined_reason: UNDEF_MAGHRIB };
    return this.dayByIndex(j + 1);
  }
  // The Waqt day whose closing Maghrib falls (civil) on date X.
  dayByLabel(X) {
    for (const k of [X, X + 1, X - 1, X + 2]) {
      const c = this.maghrib(k);
      if (c !== null && localDateNum(this.zone, c) === X) return this.dayByIndex(k);
    }
    return { status: 'UNDEFINED', idx: X, label_day: X, open: null, close: null, events: null, undefined_reason: UNDEF_MAGHRIB };
  }
  hijriLabel(day) {
    return hijriFromDay(day.label_day, this.calendar.provider, this.calendar.params || {});
  }
  // OQ-CAL-1 / DR-0012 (CAL-013): a calendar provider that cannot label a date never fails a Waqt computation.
  // Only the provider's range refusal (OUT_OF_RANGE, CAL-011) is absorbed here; every other error propagates.
  hijriLabelSafe(day) {
    try {
      return { hijri: this.hijriLabel(day), calendar_error: null };
    } catch (e) {
      if (e instanceof WaqtError && e.code === 'OUT_OF_RANGE') return { hijri: null, calendar_error: { code: 'OUT_OF_RANGE' } };
      throw e;
    }
  }
}
export const posDisplay = (seconds) => {
  const s = Math.floor(seconds + 1e-9);
  const sign = s < 0 ? '-' : '';
  const a = Math.abs(s);
  return `${sign}${String(Math.floor(a / 3600)).padStart(2, '0')}:${String(Math.floor((a % 3600) / 60)).padStart(2, '0')}:${String(a % 60).padStart(2, '0')}`;
};

// ---- the 'waqt.compute' operation ---------------------------------------------------------
export function computeWaqt(input, toInstantStr, parseInst, zone) {
  const ctx = new Site(input.location, zone, input.profile, input.calendar);
  const us = parseInst(input.instant);
  const day = ctx.dayContaining(us);
  const base = { instant: toInstantStr(us), timezone: zone, label_date: formatDate(day.label_day), profile: ctx.profile };
  if (day.status !== 'OK') {
    return { status: 'UNDEFINED', undefined_reason: day.undefined_reason, ...base, day: null, position: null, hijri: null, weekday: null, events: [], undefined_events: [], next_event: null };
  }
  const len = (day.close - day.open) / US_PER_SEC;
  const rd = (e) => (e - day.open) / US_PER_SEC;
  const events = [], undef = [];
  for (const n of EVENT_NAMES) {
    const e = day.events[n];
    if (e === null || e === undefined) undef.push({ name: n, reason: day.reasons[n] });
    else events.push({ name: n, instant: toInstantStr(e), reading_seconds: rd(e), reading_display: posDisplay(rd(e)), local_date: formatDate(localDateNum(zone, e)) });
  }
  // next event by OCCURRENCE: earliest event instant strictly after t among neighbouring listings
  let next = null;
  for (let k = day.idx - 2; k <= day.idx + 1; k++) {
    const l = ctx.listing(k);
    for (const n of EVENT_NAMES) {
      const e = l.events[n];
      if (e !== null && e !== undefined && e > us && (next === null || e < next.us)) next = { name: n, us: e };
    }
  }
  const { hijri: h, calendar_error } = ctx.hijriLabelSafe(day);
  return {
    status: 'OK', undefined_reason: null, ...base,
    day: { open: toInstantStr(day.open), close: toInstantStr(day.close), length_seconds: len },
    position: { seconds: (us - day.open) / US_PER_SEC, display: posDisplay((us - day.open) / US_PER_SEC) },
    hijri: h, ...(calendar_error ? { calendar_error } : {}), weekday: islamicWeekdayName(day.label_day),
    events, undefined_events: undef,
    next_event: next && { name: next.name, instant: toInstantStr(next.us), seconds_until: (next.us - us) / US_PER_SEC },
  };
}
