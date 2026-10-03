// institutional.mjs -- calendar rules, Islamic week, fiscal and academic years (docs/INSTITUTIONAL.md).
// Calendar CONTENT comes from the named provider (computed here) unless the caller freezes it as a
// month_table, in which case the table is authoritative (so rule semantics can be tested alone).
import { WaqtError, parseDate, formatDate, islamicWeekdayName, ISLAMIC_WEEKDAYS, weekdaySun0 } from './timeutil.mjs';
import { hijriToDay, hijriFromDay } from './calendar/providers.mjs';

const fmtH = (y, m, d) => `${String(y).padStart(4, '0')}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
const bad = (msg) => new WaqtError('INVALID_CALENDAR_RULE', msg);

function monthDays(ctx, y, m) {
  if (ctx.month_table) {
    const rows = ctx.month_table[String(m)];
    if (!rows) throw bad(`month ${m} not present in supplied month_table`);
    return rows.map((r) => ({ day: r.day, dayNum: parseDate(r.gregorian), weekday: r.weekday }));
  }
  const out = [];
  for (let d = 1; d <= 30; d++) {
    let dn;
    try { dn = hijriToDay(y, m, d, ctx.provider); } catch (e) { if (e.code === 'INVALID_HIJRI_DATE') continue; throw e; }
    const back = hijriFromDay(dn, ctx.provider);          // keep only days that round-trip
    if (back.year === y && back.month === m && back.day === d) out.push({ day: d, dayNum: dn, weekday: islamicWeekdayName(dn) });
  }
  if (!out.length) throw bad(`provider ${ctx.provider} produced no days for ${y}-${m}`);
  return out;
}
const pack = (y, m, r) => ({ hijri: fmtH(y, m, r.day), gregorian: formatDate(r.dayNum), _n: r.dayNum });

export function resolveRule(rule, ctx, year) {
  const y = year + (rule.year_offset || 0);
  if (!Number.isInteger(rule.month) || rule.month < 1 || rule.month > 12) throw bad('month must be 1..12');
  const days = monthDays(ctx, y, rule.month);
  switch (rule.type ?? rule.op) {
    case 'month_day': {
      const r = days.find((x) => x.day === rule.day);
      if (!r) throw bad(`day ${rule.day} does not exist in month ${rule.month} of ${y}`);
      return pack(y, rule.month, r);
    }
    case 'month_end': return pack(y, rule.month, days[days.length - 1]);
    case 'nth_weekday_of_month': {
      if (!ISLAMIC_WEEKDAYS.includes(rule.weekday)) throw bad(`unknown weekday ${rule.weekday}`);
      if (!Number.isInteger(rule.n) || rule.n === 0) throw bad('n must be a non-zero integer');
      const hits = days.filter((x) => x.weekday === rule.weekday);
      const r = rule.n > 0 ? hits[rule.n - 1] : hits[hits.length + rule.n];
      if (!r) throw bad(`no ${rule.n}-th ${rule.weekday} in month ${rule.month} of ${y}`);
      return pack(y, rule.month, r);
    }
    default: throw bad(`unknown rule type ${rule.type}`);
  }
}
const clean = ({ hijri, gregorian }) => ({ hijri, gregorian });

export function weekDates(dateStr, firstDay = 'al-Ahad') {
  if (!ISLAMIC_WEEKDAYS.includes(firstDay)) throw bad(`unknown first_day ${firstDay}`);
  const n = parseDate(dateStr);
  const back = (weekdaySun0(n) - ISLAMIC_WEEKDAYS.indexOf(firstDay) + 7) % 7;
  const start = n - back;
  const dates = Array.from({ length: 7 }, (_, i) => start + i);
  return { week_dates: dates.map(formatDate), weekdays: dates.map(islamicWeekdayName) };
}

export function runInstitutional(input) {
  const op = input.operation, c = input.context || {};
  const ctx = { provider: c.calendar_provider || 'arithmetic-tabular', month_table: c.month_table };
  const year = op.year ?? c.hijri_year;
  switch (op.op) {
    case 'month_day': case 'month_end': case 'nth_weekday_of_month':
      return clean(resolveRule({ ...op, type: op.op }, ctx, year));
    case 'week_dates': return weekDates(op.date, op.first_day);
    case 'fiscal_year': {
      const s = resolveRule(op.start_rule, ctx, year), e = resolveRule(op.end_rule, ctx, year);
      if (e._n < s._n) throw bad('end rule resolves before start rule');
      return { start: clean(s), end: clean(e) };
    }
    case 'academic_year': {
      const o = resolveRule(op.opening_rule, ctx, year), cl = resolveRule(op.closing_rule, ctx, year);
      if (cl._n < o._n) throw bad('closing rule resolves before opening rule');
      const terms = (op.term_rules || []).map((t) => {
        const s = resolveRule(t.start_rule, ctx, year), e = resolveRule(t.end_rule, ctx, year);
        if (e._n < s._n) throw bad(`term ${t.label}: end before start`);
        return { label: t.label, start: clean(s), end: clean(e) };
      });
      const out = { opening: clean(o), closing: clean(cl), terms };
      if (op.holidays) out.holidays = op.holidays.map((h) => ({ label: h.label, ...clean(resolveRule(h.rule, ctx, year)) }));
      return out;
    }
    default: throw bad(`unknown institutional op ${op.op}`);
  }
}
