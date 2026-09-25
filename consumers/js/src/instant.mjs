// Instants as integer microseconds since the Unix epoch (a JS Number is exact
// up to 2^53 ~ 9.0e15 us, i.e. ~year 2255). Date only carries milliseconds, so
// it is used solely for calendar arithmetic; sub-second precision is handled here.

const RE = /^(-?\d{4,})-(\d\d)-(\d\d)T(\d\d):(\d\d):(\d\d)(?:\.(\d{1,6}))?(?:Z|\+00:00)$/;

export function parseInstant(s) {
  const m = RE.exec(s);
  if (!m) throw new Error(`Not an ISO 8601 UTC instant: ${JSON.stringify(s)}`);
  const [, y, mo, d, h, mi, se, frac] = m;
  const ms = Date.UTC(+y, +mo - 1, +d, +h, +mi, +se);
  const micro = frac ? Number(frac.padEnd(6, "0")) : 0;
  return ms * 1000 + micro;
}

// Same text Python's datetime.isoformat() produces for a UTC datetime:
// fractional part only when non-zero, always six digits, "+00:00" suffix.
export function formatInstant(us) {
  const secs = Math.floor(us / 1e6);
  const frac = us - secs * 1e6;
  const base = new Date(secs * 1000).toISOString().slice(0, 19);
  return base + (frac ? "." + String(frac).padStart(6, "0") : "") + "+00:00";
}

export function civilDate(us, utcOffsetSeconds) {
  const shifted = Math.floor((us + utcOffsetSeconds * 1e6) / 1e6);
  return new Date(shifted * 1000).toISOString().slice(0, 10);
}

// The one rounding rule of the derived-instant arithmetic (docs/SCHEDULING.md §9).
export const roundHalfUp = (x) => Math.floor(x + 0.5);

const pad2 = (n) => (n < 0 ? "-" + String(-n) : String(n).padStart(2, "0"));

// Waqt clock display for a signed microsecond offset from the day's opening Maghrib.
// Hours are NOT clamped: 24, 25, ... are legitimate (Sprint 1 / SEMANTICS.md §4).
export function formatPosition(offsetUs) {
  const secs = Math.floor(Math.abs(offsetUs) / 1e6);
  let h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = secs % 60;
  if (offsetUs < 0) h = -h;
  return `${pad2(h)}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}
