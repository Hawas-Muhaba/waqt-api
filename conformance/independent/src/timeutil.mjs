// timeutil.mjs -- instants, civil dates, time zones.
//
// Representation choices (independent of the reference implementation):
//   * An INSTANT is an integer count of microseconds since the Unix epoch (a JS
//     Number; exact for |value| < 2^53 us, i.e. years ~1685..2255; outside that the
//     implementation reports RANGE_ERROR rather than silently losing precision).
//   * A CIVIL DATE is a "day number": integer days since 1970-01-01 in the
//     proleptic Gregorian calendar (Hinnant's algorithm).
//   * A ZONE is an IANA name resolved through the platform's ICU tz database
//     (Intl.DateTimeFormat) -- a different tz data source from the reference.

export class WaqtError extends Error {
  constructor(code, message, details) {
    super(message);
    this.code = code;
    this.details = details || {};
  }
}

export const US_PER_SEC = 1_000_000;
export const US_PER_DAY = 86_400 * US_PER_SEC;
export const MAX_SAFE_US = Number.MAX_SAFE_INTEGER;

// ---- Gregorian day numbers (Howard Hinnant, "days_from_civil") --------------
export function daysFromCivil(y, m, d) {
  y -= m <= 2 ? 1 : 0;
  const era = Math.floor(y / 400);
  const yoe = y - era * 400;
  const doy = Math.floor((153 * (m + (m > 2 ? -3 : 9)) + 2) / 5) + d - 1;
  const doe = yoe * 365 + Math.floor(yoe / 4) - Math.floor(yoe / 100) + doy;
  return era * 146097 + doe - 719468;
}

export function civilFromDays(z) {
  z += 719468;
  const era = Math.floor(z / 146097);
  const doe = z - era * 146097;
  const yoe = Math.floor((doe - Math.floor(doe / 1460) + Math.floor(doe / 36524) - Math.floor(doe / 146096)) / 365);
  const y = yoe + era * 400;
  const doy = doe - (365 * yoe + Math.floor(yoe / 4) - Math.floor(yoe / 100));
  const mp = Math.floor((5 * doy + 2) / 153);
  const d = doy - Math.floor((153 * mp + 2) / 5) + 1;
  const m = mp + (mp < 10 ? 3 : -9);
  return { y: y + (m <= 2 ? 1 : 0), m, d };
}

export function isLeapYear(y) {
  return (y % 4 === 0 && y % 100 !== 0) || y % 400 === 0;
}
export function daysInMonth(y, m) {
  return [31, isLeapYear(y) ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1];
}

// Weekday of a day number. 0 = Sunday ... 6 = Saturday. (1970-01-01 was a Thursday.)
export function weekdaySun0(dayNum) {
  return (((dayNum + 4) % 7) + 7) % 7;
}
// ISO weekday: Monday=1 .. Sunday=7
export function weekdayIso(dayNum) {
  const w = weekdaySun0(dayNum);
  return w === 0 ? 7 : w;
}

// Islamic weekday names, Sunday-first (this is the naming used on the wire).
export const ISLAMIC_WEEKDAYS = [
  'al-Ahad', 'al-Ithnayn', 'ath-Thulatha', 'al-Arbiaa', 'al-Khamis', 'al-Jumuah', 'as-Sabt',
];
export function islamicWeekdayName(dayNum) {
  return ISLAMIC_WEEKDAYS[weekdaySun0(dayNum)];
}

// ---- Dates as strings ----------------------------------------------------------
const DATE_RE = /^(\d{4})-(\d{2})-(\d{2})$/;
export function parseDate(s) {
  if (typeof s !== 'string') throw new WaqtError('INVALID_DATE', 'date must be a string YYYY-MM-DD');
  const m = DATE_RE.exec(s);
  if (!m) throw new WaqtError('INVALID_DATE', `not a YYYY-MM-DD date: ${JSON.stringify(s)}`);
  const y = +m[1], mo = +m[2], d = +m[3];
  if (y < 1 || mo < 1 || mo > 12 || d < 1 || d > daysInMonth(y, mo)) {
    throw new WaqtError('INVALID_DATE', `no such calendar date: ${s}`);
  }
  return daysFromCivil(y, mo, d);
}
const p2 = (n) => String(n).padStart(2, '0');
export function formatDate(dayNum) {
  const { y, m, d } = civilFromDays(dayNum);
  return `${String(y).padStart(4, '0')}-${p2(m)}-${p2(d)}`;
}

// ---- Instants ----------------------------------------------------------------------
// Accepts ISO 8601 date-time with an explicit offset ('Z' or +hh:mm / -hh:mm), optional
// fractional seconds (any number of digits; truncated to microseconds).
const INSTANT_RE = /^(\d{4})-(\d{2})-(\d{2})[Tt ](\d{2}):(\d{2}):(\d{2})(?:[.,](\d+))?(Z|z|[+-]\d{2}:?\d{2})$/;
export function parseInstant(s) {
  if (typeof s !== 'string') throw new WaqtError('INVALID_INSTANT', 'instant must be an ISO 8601 string');
  const m = INSTANT_RE.exec(s.trim());
  if (!m) throw new WaqtError('INVALID_INSTANT', `not an ISO 8601 instant with explicit offset: ${JSON.stringify(s)}`);
  const y = +m[1], mo = +m[2], d = +m[3], hh = +m[4], mi = +m[5], ss = +m[6];
  if (mo < 1 || mo > 12 || d < 1 || d > daysInMonth(y, mo) || hh > 23 || mi > 59 || ss > 59) {
    throw new WaqtError('INVALID_INSTANT', `no such instant: ${s}`);
  }
  let frac = m[7] ? m[7].slice(0, 6).padEnd(6, '0') : '000000';
  let off = 0;
  const z = m[8];
  if (z !== 'Z' && z !== 'z') {
    const sign = z[0] === '-' ? -1 : 1;
    const digits = z.slice(1).replace(':', '');
    off = sign * (+digits.slice(0, 2) * 3600 + +digits.slice(2, 4) * 60);
  }
  const secs = daysFromCivil(y, mo, d) * 86400 + hh * 3600 + mi * 60 + ss - off;
  const us = secs * US_PER_SEC + +frac;
  if (Math.abs(us) > MAX_SAFE_US) throw new WaqtError('RANGE_ERROR', 'instant outside representable range');
  return us;
}

// Format as ISO-8601 UTC with '+00:00'. precision: 'second' (floor) | 'microsecond' (trim zeros)
export function formatInstant(us, precision = 'microsecond') {
  const dayNum = Math.floor(us / US_PER_DAY);
  const rem = us - dayNum * US_PER_DAY;
  const secOfDay = Math.floor(rem / US_PER_SEC);
  const micro = rem - secOfDay * US_PER_SEC;
  const { y, m, d } = civilFromDays(dayNum);
  const hh = Math.floor(secOfDay / 3600), mi = Math.floor((secOfDay % 3600) / 60), ss = secOfDay % 60;
  let out = `${String(y).padStart(4, '0')}-${p2(m)}-${p2(d)}T${p2(hh)}:${p2(mi)}:${p2(ss)}`;
  if (precision === 'microsecond' && micro !== 0) out += '.' + String(micro).padStart(6, '0');
  return out + '+00:00';
}

export const secondsToUs = (s) => Math.floor(s * US_PER_SEC + 0.5); // half-up, per SCHEDULING.md section 9

// ---- Time zones (ICU) -----------------------------------------------------------------
const fmtCache = new Map();
function formatterFor(zone) {
  let f = fmtCache.get(zone);
  if (!f) {
    try {
      f = new Intl.DateTimeFormat('en-US', {
        timeZone: zone, hourCycle: 'h23',
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
      });
    } catch (e) {
      throw new WaqtError('UNKNOWN_TIMEZONE', `unknown IANA time zone: ${zone}`);
    }
    fmtCache.set(zone, f);
  }
  return f;
}

// UTC offset (seconds east of UTC) in force at an instant.
export function zoneOffsetAt(zone, us) {
  if (zone === 'UTC' || zone === 'Etc/UTC') return 0;
  const ms = Math.floor(us / 1000);
  const parts = formatterFor(zone).formatToParts(new Date(ms));
  const g = {};
  for (const p of parts) if (p.type !== 'literal') g[p.type] = +p.value;
  const asUtc = Date.UTC(g.year, g.month - 1, g.day, g.hour, g.minute, g.second);
  return Math.round((asUtc - Math.floor(ms / 1000) * 1000) / 1000);
}

export function localDateNum(zone, us) {
  const off = zoneOffsetAt(zone, us);
  return Math.floor((us + off * US_PER_SEC) / US_PER_DAY);
}
export function localSecondsOfDay(zone, us) {
  const off = zoneOffsetAt(zone, us);
  const loc = us + off * US_PER_SEC;
  return (loc - Math.floor(loc / US_PER_DAY) * US_PER_DAY) / US_PER_SEC;
}

// First instant of local civil date `dayNum` in `zone` (handles DST gaps by taking the
// earliest instant whose local date >= dayNum).
export function startOfLocalDate(zone, dayNum) {
  const nominal = dayNum * US_PER_DAY;
  // offset candidates around the date
  let lo = nominal - 15 * 3600 * US_PER_SEC, hi = nominal + 15 * 3600 * US_PER_SEC;
  // lo has local date < dayNum (offset <= 14h => lo+off < nominal), hi has local date >= dayNum.
  // bisect on predicate localDateNum(t) >= dayNum (monotone for sane tz data).
  while (hi - lo > US_PER_SEC) {
    const mid = Math.floor((lo + hi) / 2);
    if (localDateNum(zone, mid) >= dayNum) hi = mid; else lo = mid;
  }
  // hi is within 1 s above the transition; transitions occur on whole seconds
  return Math.ceil(hi / US_PER_SEC) * US_PER_SEC - (localDateNum(zone, Math.ceil(hi / US_PER_SEC) * US_PER_SEC - US_PER_SEC) >= dayNum ? US_PER_SEC : 0);
}

export function isKnownZone(zone) {
  try { formatterFor(zone); return true; } catch { return false; }
}
