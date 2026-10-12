// node --test test/   -- unit tests for the independent implementation (no dependencies)
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import * as T from '../src/timeutil.mjs';
import { hijriFromDay, hijriToDay, aladhanScenario } from '../src/calendar/providers.mjs';
import { solarDay } from '../src/astro/events.mjs';
import { sunState } from '../src/astro/sun.mjs';
import { conjunctionNear } from '../src/astro/moon.mjs';
import { runSchedule } from '../src/schedule.mjs';
import { runCase } from '../src/ops.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const PROF = { fajr_angle_deg: 18, isha_angle_deg: 17, asr_shadow_ratio: 1 };

test('civil-day arithmetic round-trips and weekdays', () => {
  assert.equal(T.daysFromCivil(1970, 1, 1), 0);
  for (const n of [-800000, -1, 0, 1, 11016, 20717, 2000000]) {
    const { y, m, d } = T.civilFromDays(n);
    assert.equal(T.daysFromCivil(y, m, d), n);
  }
  assert.equal(T.weekdaySun0(T.parseDate('1970-01-01')), 4);          // Thursday
  assert.equal(T.islamicWeekdayName(T.parseDate('2026-09-20')), 'al-Ahad');
  assert.equal(T.isLeapYear(1900), false); assert.equal(T.isLeapYear(2000), true);
});

test('instants: offsets normalise, naive and garbage are rejected', () => {
  assert.equal(T.formatInstant(T.parseInstant('2026-09-19T18:42:00+03:00')), '2026-09-19T15:42:00+00:00');
  assert.equal(T.formatInstant(T.parseInstant('2026-09-19T15:42:00.123456Z')), '2026-09-19T15:42:00.123456+00:00');
  for (const bad of ['2026-09-19T15:42:00', 'yesterday', '2026-02-30T00:00:00Z', '2026-09-19T25:00:00Z'])
    assert.throws(() => T.parseInstant(bad), (e) => e.code === 'INVALID_INSTANT');
});

test('time zones: date line, DST gap at midnight', () => {
  const t = T.parseInstant('2026-09-19T23:00:00Z');
  assert.equal(T.formatDate(T.localDateNum('Pacific/Kiritimati', t)), '2026-09-20');
  assert.equal(T.formatInstant(T.startOfLocalDate('America/Sao_Paulo', T.parseDate('2018-11-04'))), '2018-11-04T03:00:00+00:00'); // 00:00 does not exist
});

test('sun declination at J2000 noon is sane (loose bound; accuracy is covered by the oracle vectors)', () => {
  // loose sanity bound only; accuracy vs DE421 is measured by conformance/tools and the differential run
  const s = sunState(T.parseInstant('2000-01-01T12:00:00Z'));
  assert.ok(Math.abs(s.dec * 206264.806 - (-23.0250 * 3600)) < 60);     // ~ -23.02 deg, loose sanity bound
});

test('solar events at Addis Ababa 2026-09-20 match DE421 within 0.5 s', () => {
  const r = solarDay({ lat: 9.0192, lon: 38.7525, elev: 0 }, 'Africa/Addis_Ababa', T.parseDate('2026-09-20'), PROF);
  const want = { fajr: '2026-09-20T02:04:51.852', dhuhr: '2026-09-20T09:18:27.774' };
  for (const [n, iso] of Object.entries(want)) assert.ok(Math.abs(r.events[n] - T.parseInstant(iso + 'Z')) < 500_000, n);
});

test('polar day yields undefined events, not guesses', () => {
  const r = solarDay({ lat: 69.6492, lon: 18.9553, elev: 0 }, 'Europe/Oslo', T.parseDate('2026-06-21'), PROF);
  assert.equal(r.events.maghrib, null); assert.equal(r.events.sunrise, null); assert.ok(r.events.dhuhr);
});

test('tabular calendar: epoch and known dates', () => {
  assert.equal(hijriFromDay(T.parseDate('2026-09-20'), 'arithmetic-tabular').date, '1448-04-07');
  assert.equal(T.formatDate(hijriToDay(1, 1, 1, 'arithmetic-tabular')), '0622-07-19');      // 622-07-16 Julian == 622-07-19 proleptic Gregorian
  assert.throws(() => hijriToDay(1448, 2, 30, 'arithmetic-tabular'), (e) => e.code === 'INVALID_HIJRI_DATE');
});

test('umm-al-qura reproduces the four documented New Year anchors', () => {
  for (const [y, d] of [[1438, '2016-10-02'], [1440, '2018-09-11'], [1441, '2019-08-31'], [1447, '2025-06-26']])
    assert.equal(T.formatDate(hijriToDay(y, 1, 1, 'umm-al-qura')), d);
});

test('new moon of 2016-10-01 is at 00:11 UTC', () => {
  const c = conjunctionNear(T.parseInstant('2016-10-01T00:00:00Z'));
  assert.ok(Math.abs(c - T.parseInstant('2016-10-01T00:11:25Z')) < 90_000_000);
});

test('override providers fire on the exact date only; reverse conversion is unsupported', () => {
  const p = { override_date: '2026-09-20', declared: { year: 1448, month: 4, day: 10 } };
  assert.equal(hijriFromDay(T.parseDate('2026-09-20'), 'declared', p).date, '1448-04-10');
  assert.equal(hijriFromDay(T.parseDate('2026-09-21'), 'declared', p).date, '1448-04-08');
  assert.throws(() => hijriToDay(1448, 4, 7, 'declared'), (e) => e.code === 'UNSUPPORTED_OPERATION');
});

test('aladhan model: window, stale-if-error, circuit', () => {
  const D = '2026-09-20', ok = { kind: 'ok', hijri: { year: 1448, month: 4, day: 9 } };
  assert.equal(aladhanScenario({ steps: [{ at_seconds: 0, date: '1899-12-31', remote: ok }] })[0].fallback_reason, 'date-outside-remote-window');
  const r = aladhanScenario({ steps: [{ at_seconds: 0, date: D, remote: ok }, { at_seconds: 13 * 3600, date: D, remote: { kind: 'timeout' } }] });
  assert.equal(r[1].source, 'remote-stale');
  const c = aladhanScenario({ steps: [{ at_seconds: 0, date: D, remote: { kind: 'timeout' } }, { at_seconds: 5, date: D, remote: ok }] });
  assert.equal(c[1].fallback_reason, 'circuit-open');
});

test('all 116 frozen scheduling vectors (Sprint 6) pass in table mode', () => {
  const f = path.join(here, '..', '..', '..', 'tests', 'vectors', 'scheduling_vectors.json');
  if (!fs.existsSync(f)) return;                                       // stand-alone checkout: skip
  const IGN = new Set(['description', 'reason']);
  const norm = (x) => Array.isArray(x) ? x.map(norm) : x && typeof x === 'object'
    ? Object.fromEntries(Object.entries(x).filter(([k, v]) => !IGN.has(k) && v !== null).map(([k, v]) => [k, norm(v)])) : x;
  const vs = JSON.parse(fs.readFileSync(f, 'utf8')).vectors;
  for (const v of vs) assert.deepEqual(norm(runSchedule({ context: v.context, anchor: v.anchor, operation: v.operation })), norm(v.expected), v.id);
});

test('errors never escape as exceptions', () => {
  const r = runCase({ id: 'x', op: 'waqt.compute', input: { location: { lat: 95, lon: 0 }, instant: '2026-09-19T15:42:00Z', timezone: 'UTC' } });
  assert.equal(r.ok, false); assert.equal(r.error.code, 'VALIDATION_ERROR');
  assert.equal(runCase({ id: 'y', op: 'waqt.compute', input: { location: { lat: 0, lon: 0 }, instant: '2026-09-19T15:42:00Z', timezone: 'Mars/Base' } }).error.code, 'UNKNOWN_TIMEZONE');
});

// ---- ERR-004 / CAL-013 (DR-0011, DR-0012) -------------------------------------------------------------------------
const ADDIS = { lat: 9.0192, lon: 38.7525 };
const compute = (profile, instant = '2026-09-19T15:42:00+00:00') =>
  runCase({ id: 'x', op: 'waqt.compute', input: { location: ADDIS, instant, timezone: 'Africa/Addis_Ababa', profile } });

test('ERR-004: 90 degrees is valid (inclusive upper bound); just above, zero, negatives and non-finite values are rejected', () => {
  assert.equal(compute({ fajr_angle_deg: 90 }).ok, true);
  assert.equal(compute({ isha_angle_deg: 0.0001 }).ok, true);
  assert.equal(compute({ asr_shadow_ratio: 0.0001 }).ok, true);
  for (const p of [{ fajr_angle_deg: 90.0001 }, { fajr_angle_deg: 0 }, { isha_angle_deg: -1 }, { asr_shadow_ratio: 0 }, { asr_shadow_ratio: -2 },
    { fajr_angle_deg: NaN }, { isha_angle_deg: Infinity }, { asr_shadow_ratio: -Infinity }, { fajr_angle_deg: 'abc' }, { fajr_angle_deg: true }]) {
    const r = compute(p);
    assert.equal(r.ok, false, JSON.stringify(p));
    assert.equal(r.error.code, 'VALIDATION_ERROR', JSON.stringify(p));
  }
});

test('ERR-004: the COP $nonfinite wire convention decodes to real NaN / Infinity before validation', () => {
  for (const t of ['NaN', 'Infinity', '-Infinity']) {
    const r = compute({ fajr_angle_deg: { $nonfinite: t } });
    assert.equal(r.ok, false);
    assert.equal(r.error.code, 'VALIDATION_ERROR');
  }
});

test('CAL-013: a date outside the Umm al-Qura range returns the Waqt day with a null Hijri label and calendar_error OUT_OF_RANGE', () => {
  for (const date of ['1699-12-31', '2301-01-01']) {
    const r = runCase({ id: 'x', op: 'calendar.gregorian_date_to_waqt_day', input: { date, location: ADDIS, timezone: 'Africa/Addis_Ababa' } });
    assert.equal(r.ok, true);
    assert.equal(r.output.resolved, true);
    assert.equal(r.output.hijri_date, null);
    assert.deepEqual(r.output.calendar_error, { code: 'OUT_OF_RANGE' });
    assert.ok(r.output.open && r.output.close);
  }
  const inRange = runCase({ id: 'x', op: 'calendar.gregorian_date_to_waqt_day', input: { date: '1700-01-01', location: ADDIS, timezone: 'Africa/Addis_Ababa' } });
  assert.equal(inRange.output.hijri_date, '1111-07-11');
  assert.equal(inRange.output.calendar_error, undefined);
});

test('CAL-011 is unchanged: hijri.from_gregorian outside the range still refuses with OUT_OF_RANGE', () => {
  const r = runCase({ id: 'x', op: 'hijri.from_gregorian', input: { date: '1699-12-31' } });
  assert.equal(r.ok, false);
  assert.equal(r.error.code, 'OUT_OF_RANGE');
});
