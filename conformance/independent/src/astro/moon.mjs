// moon.mjs -- geocentric Moon (truncated Meeus ch. 47 / ELP2000-82 principal terms),
// conjunction finder and moonset finder.  Used ONLY by the Umm al-Qura provider.
import { sunState, deltaTForUs, jdUtFromUs, J2000, wrapPi } from './sun.mjs';
import { US_PER_SEC } from '../timeutil.mjs';

const D2R = Math.PI / 180, AS2R = D2R / 3600;
const TWO_PI = 2 * Math.PI;
const norm360 = (x) => ((x % 360) + 360) % 360;

// [D, M, M', F, sigma_l (1e-6 deg), sigma_r (1e-3 km)]
const LR = [
  [0,0,1,0,6288774,-20905355],[2,0,-1,0,1274027,-3699111],[2,0,0,0,658314,-2955968],[0,0,2,0,213618,-569925],
  [0,1,0,0,-185116,48888],[0,0,0,2,-114332,-3149],[2,0,-2,0,58793,246158],[2,-1,-1,0,57066,-152138],
  [2,0,1,0,53322,-170733],[2,-1,0,0,45758,-204586],[0,1,-1,0,-40923,-129620],[1,0,0,0,-34720,108743],
  [0,1,1,0,-30383,104755],[2,0,0,-2,15327,10321],[0,0,1,2,-12528,0],[0,0,1,-2,10980,79661],
  [4,0,-1,0,10675,-34782],[0,0,3,0,10034,-23210],[4,0,-2,0,8548,-21636],[2,1,-1,0,-7888,24208],
  [2,1,0,0,-6766,30824],[1,0,-1,0,-5163,-8379],[1,1,0,0,4987,-16675],[2,-1,1,0,4036,-12831],
  [2,0,2,0,3994,-10445],[4,0,0,0,3861,-11650],[2,0,-3,0,3665,14403],[0,1,-2,0,-2689,-7003],
  [2,0,-1,2,-2602,0],[2,-1,-2,0,2390,10056],[1,0,1,0,-2348,6322],[2,-2,0,0,2236,-9884],
  [0,1,2,0,-2120,5751],[0,2,0,0,-2069,0],[2,-2,-1,0,2048,-4950],[2,0,1,-2,-1773,4130],
  [2,0,0,2,-1595,0],[4,-1,-1,0,1215,-3958],[0,0,2,2,-1110,0],[3,0,-1,0,-892,3258],
  [2,1,1,0,-810,2616],[4,-1,-2,0,759,-1897],[0,2,-1,0,-713,-2117],[2,2,-1,0,-700,2354],
  [2,1,-2,0,691,0],[2,-1,0,-2,596,0],[4,0,1,0,549,-1423],[0,0,4,0,537,-1117],
  [4,-1,0,0,520,-1571],[1,0,-2,0,-487,-1739],[2,1,0,-2,-399,0],[0,0,2,-2,-381,-4421],
  [1,1,1,0,351,0],[3,0,-2,0,-340,0],[4,0,-3,0,330,0],[2,-1,2,0,327,0],
  [0,2,1,0,-323,1165],[1,1,-1,0,299,0],[2,0,3,0,294,0],[2,0,-1,-2,0,8752],
];
// [D, M, M', F, sigma_b (1e-6 deg)]
const B = [
  [0,0,0,1,5128122],[0,0,1,1,280602],[0,0,1,-1,277693],[2,0,0,-1,173237],[2,0,-1,1,55413],
  [2,0,-1,-1,46271],[2,0,0,1,32573],[0,0,2,1,17198],[2,0,1,-1,9266],[0,0,2,-1,8822],
  [2,-1,0,-1,8216],[2,0,-2,-1,4324],[2,0,1,1,4200],[2,1,0,-1,-3359],[2,-1,-1,1,2463],
  [2,-1,0,1,2211],[2,-1,-1,-1,2065],[0,1,-1,-1,-1870],[4,0,-1,-1,1828],[0,1,0,1,-1794],
  [0,0,0,3,-1749],[0,1,-1,1,-1565],[1,0,0,1,-1491],[0,1,1,1,-1475],[0,1,1,-1,-1410],
  [0,1,0,-1,-1344],[1,0,0,-1,-1335],[0,0,3,1,1107],[4,0,0,-1,1021],[4,0,-1,1,833],
];

export function moonState(us, deltaT) {
  const dT = deltaT === undefined ? deltaTForUs(us) : deltaT;
  const jde = jdUtFromUs(us) + dT / 86400;
  const T = (jde - J2000) / 36525;
  const Lp = norm360(218.3164477 + 481267.88123421 * T - 0.0015786 * T * T + T ** 3 / 538841);
  const D = norm360(297.8501921 + 445267.1114034 * T - 0.0018819 * T * T + T ** 3 / 545868);
  const M = norm360(357.5291092 + 35999.0502909 * T - 0.0001536 * T * T);
  const Mp = norm360(134.9633964 + 477198.8675055 * T + 0.0087414 * T * T + T ** 3 / 69699);
  const F = norm360(93.2720950 + 483202.0175233 * T - 0.0036539 * T * T);
  const A1 = norm360(119.75 + 131.849 * T), A2 = norm360(53.09 + 479264.290 * T), A3 = norm360(313.45 + 481266.484 * T);
  const E = 1 - 0.002516 * T - 0.0000074 * T * T;
  const ef = (m) => (Math.abs(m) === 1 ? E : Math.abs(m) === 2 ? E * E : 1);
  let sl = 0, sr = 0, sb = 0;
  for (const [d, m, mp, f, l, r] of LR) {
    const arg = (d * D + m * M + mp * Mp + f * F) * D2R;
    sl += l * ef(m) * Math.sin(arg); sr += r * ef(m) * Math.cos(arg);
  }
  for (const [d, m, mp, f, b] of B) {
    const arg = (d * D + m * M + mp * Mp + f * F) * D2R;
    sb += b * ef(m) * Math.sin(arg);
  }
  sl += 3958 * Math.sin(A1 * D2R) + 1962 * Math.sin((Lp - F) * D2R) + 318 * Math.sin(A2 * D2R);
  sb += -2235 * Math.sin(Lp * D2R) + 382 * Math.sin(A3 * D2R) + 175 * Math.sin((A1 - F) * D2R)
      + 175 * Math.sin((A1 + F) * D2R) + 127 * Math.sin((Lp - Mp) * D2R) - 115 * Math.sin((Lp + Mp) * D2R);

  const om = (125.04452 - 1934.136261 * T) * D2R;
  const Ls = (280.4665 + 36000.7698 * T) * D2R, Lm = (218.3165 + 481267.8813 * T) * D2R;
  const dpsi = (-17.20 * Math.sin(om) - 1.32 * Math.sin(2 * Ls) - 0.23 * Math.sin(2 * Lm) + 0.21 * Math.sin(2 * om)) * AS2R;
  const deps = (9.20 * Math.cos(om) + 0.57 * Math.cos(2 * Ls) + 0.10 * Math.cos(2 * Lm) - 0.09 * Math.cos(2 * om)) * AS2R;
  const eps = (84381.448 - 46.8150 * T - 0.00059 * T * T + 0.001813 * T ** 3) * AS2R + deps;

  const lambda = (Lp + sl / 1e6) * D2R + dpsi;        // apparent ecliptic longitude
  const beta = (sb / 1e6) * D2R;
  const dist = 385000.56 + sr / 1000;                 // km
  const ra = Math.atan2(Math.sin(lambda) * Math.cos(eps) - Math.tan(beta) * Math.sin(eps), Math.cos(lambda));
  const dec = Math.asin(Math.sin(beta) * Math.cos(eps) + Math.cos(beta) * Math.sin(eps) * Math.sin(lambda));
  const gmst = norm360(280.46061837 + 360.98564736629 * (jdUtFromUs(us) - J2000)) * D2R + dpsi * Math.cos(eps);
  return { lambda, beta, ra: (ra + TWO_PI) % TWO_PI, dec, dist, gast: ((gmst % TWO_PI) + TWO_PI) % TWO_PI, parallax: Math.asin(6378.14 / dist) };
}

// Elongation of the Moon from the Sun in ecliptic longitude, wrapped to (-pi, pi].
export const elongation = (us) => wrapPi(moonState(us).lambda - sunState(us).lambda);

// Mean synodic month (days) -- used only to seed searches.
export const SYNODIC_DAYS = 29.530588861;

// Conjunction (ecliptic-longitude equality) nearest to a seed instant.
export function conjunctionNear(seedUs) {
  let t = seedUs;
  for (let i = 0; i < 12; i++) {
    const e = elongation(t);
    t -= Math.round((e / TWO_PI) * SYNODIC_DAYS * 86400 * US_PER_SEC);
  }
  return t;
}

// Geocentric altitude of the Moon's centre (radians) at a site.
export function moonAltitude(us, latDeg, lonDeg) {
  const s = moonState(us);
  const H = s.gast + lonDeg * D2R - s.ra;
  const phi = latDeg * D2R;
  return Math.asin(Math.sin(phi) * Math.sin(s.dec) + Math.cos(phi) * Math.cos(s.dec) * Math.cos(H));
}
// Moonset-threshold altitude for the geocentric centre: 0.7275*parallax - 34' (Meeus ch. 15).
export const moonHorizon = (us) => 0.7275 * moonState(us).parallax - (34 / 60) * D2R;

// First moonset (descending crossing) in [t0, t1]; null if none.
export function moonsetBetween(t0, t1, latDeg, lonDeg) {
  const f = (t) => moonAltitude(t, latDeg, lonDeg) - moonHorizon(t);
  const step = 300 * US_PER_SEC;
  let pt = t0, pv = f(t0);
  for (let t = t0 + step; ; t += step) {
    const tt = Math.min(t, t1), v = f(tt);
    if (pv >= 0 && v < 0) {
      let lo = pt, hi = tt;
      while (hi - lo > 500) { const m = Math.floor((lo + hi) / 2); if (f(m) >= 0) lo = m; else hi = m; }
      return Math.round((lo + hi) / 2);
    }
    if (tt >= t1) return null;
    pt = tt; pv = v;
  }
}
