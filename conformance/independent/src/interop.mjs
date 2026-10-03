// interop.mjs -- Gregorian <-> Waqt conversion views (docs/CALENDAR-INTEROP.md)
import { parseInstant, formatInstant, parseDate, formatDate, isLeapYear, weekdayIso, islamicWeekdayName, zoneOffsetAt, localDateNum, localSecondsOfDay, civilFromDays, US_PER_DAY, US_PER_SEC } from './timeutil.mjs';
import { Site, posDisplay } from './waqtday.mjs';
import { Engine, LiveSource } from './schedule.mjs';

const hms = (sec) => { const s = Math.floor(sec); return `${String(Math.floor(s / 3600)).padStart(2, '0')}:${String(Math.floor((s % 3600) / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`; };
function gview(dayNum, secOfDay, zone, offset) {
  return { date: formatDate(dayNum), time_of_day: hms(secOfDay), weekday_iso: weekdayIso(dayNum), weekday_name_islamic: islamicWeekdayName(dayNum), is_leap_year: isLeapYear(civilFromDays(dayNum).y), timezone_name: zone, utc_offset_seconds: offset };
}
export function representInstant(input) {
  const t = parseInstant(input.instant);
  const dn = Math.floor(t / US_PER_DAY);
  const out = { gregorian_utc: gview(dn, (t - dn * US_PER_DAY) / US_PER_SEC, null, 0) };
  if (input.timezone) {
    const off = zoneOffsetAt(input.timezone, t);
    out.gregorian_civil = gview(localDateNum(input.timezone, t), localSecondsOfDay(input.timezone, t), input.timezone, off);
    if (input.location) {
      const site = new Site(input.location, input.timezone, input.profile, input.calendar);
      const d = site.dayContaining(t);
      out.waqt_status = d.status === 'OK' ? 'OK' : 'UNDEFINED';
      out.waqt_position_seconds = d.status === 'OK' ? (t - d.open) / US_PER_SEC : null;
    }
  }
  return out;
}
export function gregorianDateToWaqtDay(input) {
  const X = parseDate(input.date);
  const site = new Site(input.location, input.timezone, input.profile, input.calendar);
  const d = site.dayByLabel(X);
  if (d.status !== 'OK') return { resolved: false, close_civil_date: null, open: null, close: null, reason: d.undefined_reason };
  const h = site.hijriLabel(d);
  return { resolved: true, close_civil_date: formatDate(localDateNum(input.timezone, d.close)), open: formatInstant(d.open), close: formatInstant(d.close), hijri_date: h.date, weekday: islamicWeekdayName(d.label_day), reason: null };
}
export function boundaryCrossing(input) {
  const a = parseInstant(input.start), b = parseInstant(input.end);
  const src = new LiveSource({ location: input.location, timezone: input.timezone, profile: input.profile, calendar: input.calendar }, a);
  const r = new Engine(src, a).classifySpan(a, b, false);
  if (r.status !== 'OK') return { status: r.status, reason: r.reason };
  return { status: 'OK', crosses_civil_midnight: r.crosses_civil_midnight, crosses_maghrib: r.crosses_maghrib, maghrib_boundaries: r.maghrib_boundaries, start_civil_date: r.start_civil_date, end_civil_date: r.end_civil_date };
}
