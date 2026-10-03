// sun.mjs -- apparent geocentric position of the Sun and Earth rotation.
//
// Method (deliberately different from the NOAA low-precision method):
//   Earth's heliocentric position from truncated VSOP87D  ->  geocentric Sun (Theta = L + 180 deg)
//   -> FK5 correction -> nutation in longitude (short series) -> aberration (-20.4898"/R)
//   -> apparent RA/Dec with true obliquity;  hour angle from apparent sidereal time.
import * as V from './vsop_earth.mjs';
import { deltaTSeconds } from './deltat.mjs';

const D2R = Math.PI / 180;
const AS2R = D2R / 3600;
const TWO_PI = 2 * Math.PI;

function series(terms, tau) {
  let s = 0;
  for (const [a, b, c] of terms) s += a * Math.cos(b + c * tau);
  return s;
}
function poly(tables, tau) {
  let total = 0, p = 1;
  for (const t of tables) { total += series(t, tau) * p; p *= tau; }
  return total / 1e8;
}

export const J2000 = 2451545.0;
export const jdUtFromUs = (us) => us / 86400e6 + 2440587.5;

export function deltaTForUs(us) {
  const d = new Date(Math.floor(us / 1000));
  const y = d.getUTCFullYear() + (d.getUTCMonth() + 1 - 0.5) / 12;
  return deltaTSeconds(y);
}

const norm2pi = (x) => { x %= TWO_PI; return x < 0 ? x + TWO_PI : x; };
export const wrapPi = (x) => { x = norm2pi(x); return x > Math.PI ? x - TWO_PI : x; };

// Returns { ra, dec, gast, r, lambda, eps, deltaT } with angles in radians.
export function sunState(us, deltaT) {
  const dT = deltaT === undefined ? deltaTForUs(us) : deltaT;
  const jdUT = jdUtFromUs(us);
  const jde = jdUT + dT / 86400;
  const T = (jde - J2000) / 36525;
  const tau = T / 10;

  const L = poly([V.L0, V.L1, V.L2, V.L3, V.L4, V.L5], tau);
  const B = poly([V.B0, V.B1], tau);
  const R = poly([V.R0, V.R1, V.R2, V.R3, V.R4], tau);

  let theta = L + Math.PI;           // geocentric longitude (mean equinox of date)
  let beta = -B;
  // FK5 correction (Meeus ch. 25/32)
  const Lp = theta - (1.397 * T + 0.00031 * T * T) * D2R;
  theta += -0.09033 * AS2R;
  beta += 0.03916 * (Math.cos(Lp) - Math.sin(Lp)) * AS2R;

  // Nutation (Meeus ch. 22, abbreviated)
  const om = (125.04452 - 1934.136261 * T) * D2R;
  const Ls = (280.4665 + 36000.7698 * T) * D2R;
  const Lm = (218.3165 + 481267.8813 * T) * D2R;
  const dpsi = (-17.20 * Math.sin(om) - 1.32 * Math.sin(2 * Ls) - 0.23 * Math.sin(2 * Lm) + 0.21 * Math.sin(2 * om)) * AS2R;
  const deps = (9.20 * Math.cos(om) + 0.57 * Math.cos(2 * Ls) + 0.10 * Math.cos(2 * Lm) - 0.09 * Math.cos(2 * om)) * AS2R;
  const eps0 = (84381.448 - 46.8150 * T - 0.00059 * T * T + 0.001813 * T * T * T) * AS2R;
  const eps = eps0 + deps;

  const lambda = theta + dpsi - 20.4898 * AS2R / R;   // apparent longitude

  const sl = Math.sin(lambda), cl = Math.cos(lambda);
  const ra = norm2pi(Math.atan2(sl * Math.cos(eps) - Math.tan(beta) * Math.sin(eps), cl));
  const dec = Math.asin(Math.sin(beta) * Math.cos(eps) + Math.cos(beta) * Math.sin(eps) * sl);

  // Apparent sidereal time at Greenwich (Meeus 12.4 + equation of the equinoxes)
  const Tu = (jdUT - J2000) / 36525;
  const gmstDeg = 280.46061837 + 360.98564736629 * (jdUT - J2000) + 0.000387933 * Tu * Tu - Tu * Tu * Tu / 38710000;
  const gast = norm2pi(gmstDeg * D2R + dpsi * Math.cos(eps));
  return { ra, dec, gast, r: R, lambda, eps, deltaT: dT };
}

// Local hour angle (radians, wrapped to (-pi, pi]); lonEastDeg east-positive.
export function hourAngle(us, lonEastDeg, deltaT) {
  const s = sunState(us, deltaT);
  return wrapPi(s.gast + lonEastDeg * D2R - s.ra);
}

// Geometric altitude (radians) of the Sun's centre (no refraction, no parallax).
export function altitude(us, latDeg, lonEastDeg, deltaT) {
  const s = sunState(us, deltaT);
  const H = s.gast + lonEastDeg * D2R - s.ra;
  const phi = latDeg * D2R;
  return Math.asin(Math.sin(phi) * Math.sin(s.dec) + Math.cos(phi) * Math.cos(s.dec) * Math.cos(H));
}
