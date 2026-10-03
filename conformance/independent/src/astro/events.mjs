// events.mjs -- solar events by scanning the real altitude function and bisecting.
//
// DEFINITIONS (from docs/ASTRONOMY.md and the Waqt spec; see conformance SPEC.md S4):
//   sunrise / maghrib : Sun's geocentric centre crosses  -0.8333 deg - dip(elevation)
//   fajr  / isha      : Sun's centre crosses  -fajr_angle / -isha_angle
//   dhuhr             : upper meridian transit
//   asr               : Sun's centre descends through  atan(1 / (ratio + tan|phi - delta_transit|))
//   dip               : 1.76 arcmin * sqrt(elevation_m)   (sunrise/maghrib only)
//
// ASSIGNMENT OF EVENTS TO A CIVIL DATE ("transit-anchored solar day"):
//   The events of civil date X are those around the upper transit whose local civil date is X:
//     morning events (fajr, sunrise) = last ascending crossing in (T-12.25h, T)
//     evening events (asr, maghrib, isha) = first descending crossing in (T, T+12.25h)
//   so Isha that happens after local midnight still belongs to the date of its transit.
import { sunState, altitude, hourAngle, wrapPi, deltaTForUs } from './sun.mjs';
import { US_PER_SEC, US_PER_DAY, zoneOffsetAt, localDateNum } from '../timeutil.mjs';

const D2R = Math.PI / 180;
const H = 3600 * US_PER_SEC;
export const SUN_HORIZON_DEG = -0.8333;
export const dipDeg = (elev) => (elev > 0 ? (1.76 / 60) * Math.sqrt(elev) : 0);

// ---- upper transit nearest a guess ----------------------------------------------
export function transitNear(guessUs, lonDeg) {
  let t = guessUs;
  for (let i = 0; i < 8; i++) {
    const ha = hourAngle(t, lonDeg);                 // radians, wrapped
    t -= (ha / (2 * Math.PI)) * 86400 * US_PER_SEC;  // ~360 deg per solar day
  }
  return Math.round(t);
}

// ---- root finding on a monotone-bracketed scalar function ----------------------------
function bisect(f, a, b, fa) {
  // f(a) and f(b) have opposite signs; returns time (us) where f changes sign.
  let lo = a, hi = b, flo = fa;
  while (hi - lo > 500) {                             // 0.5 ms
    const mid = Math.floor((lo + hi) / 2);
    const fm = f(mid);
    if ((fm >= 0) === (flo >= 0)) { lo = mid; flo = fm; } else { hi = mid; }
  }
  return Math.round((lo + hi) / 2);
}

// First (dir='first') or last (dir='last') crossing of f through 0 in [t0, t1] with the
// requested sense (rising: f goes - to +). Returns null if none.
function crossing(f, t0, t1, rising, which) {
  const step = 240 * US_PER_SEC;
  const n = Math.max(1, Math.ceil((t1 - t0) / step));
  const dt = (t1 - t0) / n;
  let prevT = t0, prevV = f(t0);
  let found = null;
  for (let i = 1; i <= n; i++) {
    const t = Math.round(t0 + i * dt);
    const v = f(t);
    const up = prevV < 0 && v >= 0, down = prevV >= 0 && v < 0;
    if ((rising && up) || (!rising && down)) {
      const r = bisect(f, prevT, t, prevV);
      if (which === 'first') return r;
      found = r;
    }
    prevT = t; prevV = v;
  }
  return found;
}

// Does the altitude exceed/undershoot the target by touching it between scan points?
// (grazing crossings narrower than the scan step). Ternary-search the extremum.
function grazing(f, t0, t1, wantMax) {
  const step = 240 * US_PER_SEC;
  const n = Math.max(1, Math.ceil((t1 - t0) / step));
  let bestI = 0, bestV = wantMax ? -Infinity : Infinity;
  for (let i = 0; i <= n; i++) {
    const v = f(Math.round(t0 + (i * (t1 - t0)) / n));
    if (wantMax ? v > bestV : v < bestV) { bestV = v; bestI = i; }
  }
  let lo = Math.round(t0 + (Math.max(bestI - 1, 0) * (t1 - t0)) / n);
  let hi = Math.round(t0 + (Math.min(bestI + 1, n) * (t1 - t0)) / n);
  for (let k = 0; k < 40; k++) {
    const a = lo + (hi - lo) / 3, b = hi - (hi - lo) / 3;
    const fa = f(Math.round(a)), fb = f(Math.round(b));
    if (wantMax ? fa < fb : fa > fb) lo = a; else hi = b;
  }
  return Math.round((lo + hi) / 2);
}

export const EVENT_NAMES = ['fajr', 'sunrise', 'dhuhr', 'asr', 'maghrib', 'isha'];

// All six events around the transit T for a site. Returns {transit, events:{name: us|null},
// reasons:{name: string}}.
export function eventsAroundTransit(T, site, profile) {
  const { lat, lon, elev = 0 } = site;
  const phi = lat * D2R;
  const alt = (t) => altitude(t, lat, lon) / D2R;   // degrees
  const horizon = SUN_HORIZON_DEG - dipDeg(elev);
  const out = { transit: T, events: { dhuhr: T }, reasons: {} };

  const lo = T - Math.round(12.25 * H), hi = T + Math.round(12.25 * H);
  const solveMorning = (target) => {
    const g = (t) => alt(t) - target;
    return crossing(g, lo, T, true, 'last');
  };
  const solveEvening = (target) => {
    const g = (t) => alt(t) - target;
    return crossing(g, T, hi, false, 'first');
  };

  const noonAlt = alt(T);
  const nadirT = [lo, T, hi];

  // Morning: need nadir below target and noon above it
  const morning = (name, target, label) => {
    let t = solveMorning(target);
    if (t === null) {
      // grazing check: lowest point of the night before T might dip just below target
      const tm = grazing((x) => alt(x), lo, T, false);
      const v = alt(tm) - target;
      if (v < 0 && noonAlt >= target) t = solveMorning(target);   // numeric safety (edge)
    }
    out.events[name] = t;
    if (t === null) out.reasons[name] = noonAlt < target
      ? `${label}: the Sun never reaches ${target.toFixed(4)} deg on this date (polar night)`
      : `${label}: the Sun never falls to ${target.toFixed(4)} deg on this date (polar day / white night)`;
  };
  const evening = (name, target, label) => {
    const t = solveEvening(target);
    out.events[name] = t;
    if (t === null) out.reasons[name] = noonAlt < target
      ? `${label}: the Sun never reaches ${target.toFixed(4)} deg on this date (polar night)`
      : `${label}: the Sun never falls to ${target.toFixed(4)} deg on this date (polar day / white night)`;
  };

  morning('fajr', -profile.fajr_angle_deg, 'Fajr');
  morning('sunrise', horizon, 'Sunrise');
  // Asr: altitude from the declination at transit
  const dec = sunState(T).dec;
  const zen = Math.abs(phi - dec);
  const asrAlt = Math.atan(1 / (profile.asr_shadow_ratio + Math.tan(zen))) / D2R;
  if (!(asrAlt > 0)) {
    // The shadow-ratio definition needs a finite shadow: the Sun must be above the true horizon at noon.
    out.events.asr = null;
    out.reasons.asr = 'Asr: shadow length is undefined (the Sun is not above the geometric horizon at transit)';
  } else evening('asr', asrAlt, 'Asr');
  evening('maghrib', horizon, 'Maghrib');
  evening('isha', -profile.isha_angle_deg, 'Isha');
  return out;
}

// Transit whose local civil date (in `zone`) is dayNum.
export function transitOnCivilDate(site, zone, dayNum) {
  let guess = dayNum * US_PER_DAY + 12 * H - Math.round(site.lon * 240 * US_PER_SEC);
  guess -= zoneOffsetAt(zone, guess) * US_PER_SEC;
  let T = transitNear(guess, site.lon);
  for (let i = 0; i < 4; i++) {
    const d = localDateNum(zone, T);
    if (d === dayNum) return T;
    guess += d < dayNum ? US_PER_DAY : -US_PER_DAY;
    T = transitNear(guess, site.lon);
  }
  return T;   // pathological civil-offset mismatch; documented limitation (SPEC OQ-DAY-2)
}

const cache = new Map();
export function solarDay(site, zone, dayNum, profile) {
  const key = [site.lat, site.lon, site.elev || 0, zone, dayNum, profile.fajr_angle_deg, profile.isha_angle_deg, profile.asr_shadow_ratio].join('|');
  let r = cache.get(key);
  if (!r) {
    const T = transitOnCivilDate(site, zone, dayNum);
    r = eventsAroundTransit(T, site, profile);
    if (cache.size > 4000) cache.clear();
    cache.set(key, r);
  }
  return r;
}
