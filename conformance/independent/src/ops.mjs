// ops.mjs -- Conformance Operation Protocol (COP v1) dispatcher.
import { WaqtError, parseInstant, formatInstant, parseDate, formatDate, isLeapYear, daysInMonth, weekdayIso, islamicWeekdayName, civilFromDays, isKnownZone } from './timeutil.mjs';
import { hijriFromDay, hijriToDay, monthLength, aladhanScenario, PROVIDERS } from './calendar/providers.mjs';
import { computeWaqt } from './waqtday.mjs';
import { runSchedule } from './schedule.mjs';
import { runInstitutional } from './institutional.mjs';
import { representInstant, gregorianDateToWaqtDay, boundaryCrossing } from './interop.mjs';
import { DEFAULT_PROVIDER } from './defaults.mjs';

function needZone(input) {
  if (!input.timezone) throw new WaqtError('VALIDATION_ERROR', 'timezone (IANA name) is required');
  if (!isKnownZone(input.timezone)) throw new WaqtError('UNKNOWN_TIMEZONE', `unknown IANA time zone: ${input.timezone}`);
  return input.timezone;
}

export const OPS = {
  'gregorian.weekday': (i) => {
    const n = parseDate(i.date); const { y, m } = civilFromDays(n);
    return { weekday_iso: weekdayIso(n), weekday_name_islamic: islamicWeekdayName(n), is_leap_year: isLeapYear(y), days_in_month: daysInMonth(y, m) };
  },
  'hijri.from_gregorian': (i) => hijriFromDay(parseDate(i.date), i.provider || DEFAULT_PROVIDER, i.params || {}),
  'hijri.to_gregorian': (i) => ({ date: formatDate(hijriToDay(i.year, i.month, i.day, i.provider || DEFAULT_PROVIDER)) }),
  'hijri.month_length': (i) => ({ days: monthLength(i.year, i.month, i.provider || DEFAULT_PROVIDER) }),
  'hijri.year_table': (i) => {
    const months = [];
    for (let m = 1; m <= 12; m++) { const len = monthLength(i.year, m, i.provider); months.push({ month: m, start: formatDate(hijriToDay(i.year, m, 1, i.provider)), length: len }); }
    return { months };
  },
  'hijri.provider_scenario': (i) => ({ steps: aladhanScenario(i).map((r, n) => ({ date: i.steps[n].date, hijri_date: r.date, provider: r.provider, source: r.source, fallback_reason: r.fallback_reason })) }),
  'calendar.represent_instant': (i) => { if (i.timezone) needZone(i); return representInstant(i); },
  'calendar.gregorian_date_to_waqt_day': (i) => { needZone(i); return gregorianDateToWaqtDay(i); },
  'calendar.boundary_crossing': (i) => { needZone(i); return boundaryCrossing(i); },
  'waqt.compute': (i) => computeWaqt(i, (u) => formatInstant(u), parseInstant, needZone(i)),
  'schedule.run': (i) => { if (i.context && !i.context.days) { i = { ...i, context: { ...i.context } }; needZone(i.context); } return runSchedule(i); },
  'institutional.run': (i) => runInstitutional(i),
  'instant.parse': (i) => ({ instant: formatInstant(parseInstant(i.value)) }),
  'date.parse': (i) => ({ date: formatDate(parseDate(i.value)) }),
};

export function runCase(c) {
  const fn = OPS[c.op];
  if (!fn) return { id: c.id, ok: false, error: { code: 'UNSUPPORTED_OPERATION', message: `operation not implemented: ${c.op}` } };
  try { return { id: c.id, ok: true, output: fn(c.input || {}) }; }
  catch (e) {
    if (e instanceof WaqtError) return { id: c.id, ok: false, error: { code: e.code, message: e.message } };
    return { id: c.id, ok: false, error: { code: 'INTERNAL_ERROR', message: String(e && e.message || e) } };
  }
}
export const CAPABILITIES = Object.keys(OPS);
export { PROVIDERS };
