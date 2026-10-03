// ummalqura.mjs -- Umm al-Qura as the rule stated in docs/CALENDARS.md:
//   a month is 29 days if, on the evening of its 29th day at Makkah, the astronomical conjunction
//   has occurred before Makkah sunset AND the Moon sets after the Sun that evening; otherwise 30.
// This is a CHAIN rule (the 29th evening depends on where the month started). The chain's origin
// is not specified (spec question OQ-UAQ-1); we use a canonical grid of burn-in seeds so the
// result is a deterministic function of the month index.
import { solarDay } from '../astro/events.mjs';
import { conjunctionNear, moonsetBetween, SYNODIC_DAYS } from '../astro/moon.mjs';
import { parseInstant, localDateNum, startOfLocalDate, US_PER_SEC, US_PER_DAY, WaqtError, daysFromCivil } from '../timeutil.mjs';

export const UAQ_VERSION = 'independent-chain-v1';
const MAKKAH = { lat: 21.4225, lon: 39.8262, elev: 0 };
const ZONE = 'Asia/Riyadh';
const PROFILE = { fajr_angle_deg: 18, isha_angle_deg: 17, asr_shadow_ratio: 1 };

const ANCHOR_CONJ = parseInstant('2016-10-01T00:11:25Z');   // new moon that opens 1 Muharram 1438
const ANCHOR_YEAR_MONTH0 = 1437 * 12;                       // month index 0 == 1438-01
export const UAQ_MIN_DAY = daysFromCivil(1700, 1, 1), UAQ_MAX_DAY = daysFromCivil(2300, 12, 31);
const BLOCK = 120, BURN = 48;

const conjCache = new Map();
function conj(n) {
  let c = conjCache.get(n);
  if (c === undefined) { c = conjunctionNear(ANCHOR_CONJ + Math.round(n * SYNODIC_DAYS * 86400 * US_PER_SEC)); conjCache.set(n, c); }
  return c;
}
const maghribMakkah = (day) => solarDay(MAKKAH, ZONE, day, PROFILE).events.maghrib;

const condCache = new Map();
// Evening-of-29th test on Makkah civil date E for the conjunction C.
function cond(E, C) {
  const key = E + ':' + C;
  let v = condCache.get(key);
  if (v === undefined) {
    const M = maghribMakkah(E);
    if (M === null || C > M) v = false;
    else {
      const ms = moonsetBetween(startOfLocalDate(ZONE, E), startOfLocalDate(ZONE, E + 1), MAKKAH.lat, MAKKAH.lon);
      v = ms !== null && ms > M;
    }
    condCache.set(key, v);
  }
  return v;
}

const startCache = new Map();    // month index -> start day number
function seedStart(n) {          // lunation n's first day by the simple per-lunation rule (burn-in seed)
  const C = conj(n);
  const G = localDateNum(ZONE, C);
  return cond(G, C) ? G + 1 : G + 2;
}
export function monthStart(j) {   // j = month index relative to 1438-01
  let s = startCache.get(j);
  if (s !== undefined) return s;
  const base = Math.floor(j / BLOCK) * BLOCK;
  let idx = base - BURN;
  let cur = startCache.get(idx);
  if (cur === undefined) { cur = seedStart(idx); startCache.set(idx, cur); }
  while (idx < j) {
    const next = cur + (cond(cur + 28, conj(idx + 1)) ? 29 : 30);
    idx++; cur = next; startCache.set(idx, cur);
  }
  return startCache.get(j);
}

function checkRange(day) {
  if (day < UAQ_MIN_DAY || day > UAQ_MAX_DAY) throw new WaqtError('OUT_OF_RANGE', 'umm-al-qura is supported for 1700-01-01..2300-12-31 only');
}
export function uaqFromDay(day) {
  checkRange(day);
  let j = Math.floor((day - monthStart(0)) / 29.530589);
  while (monthStart(j) > day) j--;
  while (monthStart(j + 1) <= day) j++;
  const M = ANCHOR_YEAR_MONTH0 + j;
  return { year: Math.floor(M / 12) + 1, month: (M % 12 + 12) % 12 + 1, day: day - monthStart(j) + 1 };
}
export function uaqMonthLength(y, m) {
  const j = (y - 1) * 12 + (m - 1) - ANCHOR_YEAR_MONTH0;
  const s = monthStart(j);
  checkRange(s);
  return monthStart(j + 1) - s;
}
export function uaqToDay(y, m, d) {
  const len = uaqMonthLength(y, m);
  if (!Number.isInteger(d) || d < 1 || d > len) throw new WaqtError('INVALID_HIJRI_DATE', `no such Hijri date in umm-al-qura: ${y}-${m}-${d}`);
  return monthStart((y - 1) * 12 + (m - 1) - ANCHOR_YEAR_MONTH0) + d - 1;
}
