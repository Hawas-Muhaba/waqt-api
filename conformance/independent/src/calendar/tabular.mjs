// tabular.mjs -- 30-year-cycle arithmetic Hijri calendar (epoch JDN 1948440 = 1 Muharram 1 AH).
// Leap years are those whose position in the 30-year cycle is one of
//   2, 5, 7, 10, 13, 16, 18, 21, 24, 26, 29     (the common "Kuwaiti"/civil pattern).
// The spec says only "classical 30-year-cycle"; the exact pattern is spec question OQ-TAB-1.
import { WaqtError } from '../timeutil.mjs';

export const HIJRI_EPOCH_JDN = 1948440;
export const MONTH_NAMES = [
  'Muharram', 'Safar', 'Rabi al-Awwal', 'Rabi al-Thani', 'Jumada al-Awwal', 'Jumada al-Thani',
  'Rajab', 'Shaban', 'Ramadan', 'Shawwal', 'Dhu al-Qadah', 'Dhu al-Hijjah',
];
export const TABULAR_VERSION = '30-year-cycle-epoch-1948440';
const LEAP_POSITIONS = new Set([2, 5, 7, 10, 13, 16, 18, 21, 24, 26, 29]);

export const isHijriLeap = (y) => LEAP_POSITIONS.has(((y - 1) % 30 + 30) % 30 + 1);
export const tabularMonthLength = (y, m) => (m % 2 === 1 ? 30 : m === 12 && isHijriLeap(y) ? 30 : 29);

// day number (days since 1970-01-01) <-> JDN
const JDN_UNIX = 2440588;               // JDN of 1970-01-01
export const dayToJdn = (d) => d + JDN_UNIX;
export const jdnToDay = (j) => j - JDN_UNIX;

// Days from the epoch for 1 Muharram of year y (summing year lengths).
function yearStartOffset(y) {
  const n = y - 1;
  const cycles = Math.floor(n / 30);
  const rem = n - cycles * 30;
  let days = cycles * 10631;
  for (let i = 1; i <= rem; i++) days += LEAP_POSITIONS.has(i) ? 355 : 354;
  return days;
}
export function tabularToDay(y, m, d) {
  let off = yearStartOffset(y);
  for (let k = 1; k < m; k++) off += tabularMonthLength(y, k);
  return jdnToDay(HIJRI_EPOCH_JDN + off + d - 1);
}
export function tabularFromDay(day) {
  const off = dayToJdn(day) - HIJRI_EPOCH_JDN;
  let y = Math.floor((off * 30) / 10631) + 1;           // estimate, then correct
  while (yearStartOffset(y) > off) y--;
  while (yearStartOffset(y + 1) <= off) y++;
  let rest = off - yearStartOffset(y), m = 1;
  while (m < 12 && rest >= tabularMonthLength(y, m)) { rest -= tabularMonthLength(y, m); m++; }
  return { year: y, month: m, day: rest + 1 };
}
export function validateHijri(y, m, d, maxDay) {
  if (!Number.isInteger(y) || !Number.isInteger(m) || !Number.isInteger(d) || y < 1 || m < 1 || m > 12 || d < 1 || d > (maxDay ?? 30)) {
    throw new WaqtError('INVALID_HIJRI_DATE', `no such Hijri date: ${y}-${m}-${d}`);
  }
}
