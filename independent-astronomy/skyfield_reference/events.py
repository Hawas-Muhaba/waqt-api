"""Six daily solar events from DE421 + Skyfield.

Only the *definitions* are taken from the Waqt spec (docs/ASTRONOMY.md):
  Fajr / Isha: Sun's centre at -18 / -17 deg;  sunrise / Maghrib: -0.8333 deg
  (minus horizon dip 1.76' * sqrt(h)); Dhuhr: meridian transit; Asr: altitude
  atan(1 / (ratio + tan(zenith distance at transit))).
  A day's events are those bracketing the transit nearest 12:00 UTC - lon/15 h.
Altitudes are GEOCENTRIC apparent (the -0.8333 deg convention already accounts for
refraction and semidiameter for a geocentric Sun centre); `mode="topocentric"`
is a sensitivity variant adding diurnal parallax (<= 8.8 arcsec).
"""
from __future__ import annotations
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import numpy as np
from skyfield.api import load, wgs84
from .ephemeris import load_bodies

_ts = load.timescale()
_earth, _sun = load_bodies()
SUN_HORIZON_DEG = -0.8333
_GRID_S = 300.0      # coarse scan step

def _times(day0: datetime, seconds):
    return _ts.utc(day0.year, day0.month, day0.day, 0, 0, np.asarray(seconds, dtype=float))

def sun_geocentric_apparent(t):
    """(RA deg of date, Dec deg of date, GAST deg) for Skyfield Time t."""
    ra, dec, _ = _earth.at(t).observe(_sun).apparent().radec(epoch="date")
    return ra._degrees, dec.degrees, t.gast * 15.0

def _altitude_fn(lat, lon, mode, day0):
    if mode == "topocentric":
        site = _earth + wgs84.latlon(lat, lon)
        def f(sec):
            alt, _, _ = site.at(_times(day0, sec)).observe(_sun).apparent().altaz()
            return alt.degrees
        return f
    phi = math.radians(lat)
    def f(sec):
        ra, dec, gast = sun_geocentric_apparent(_times(day0, sec))
        h = np.radians(gast + lon - ra); d = np.radians(dec)
        return np.degrees(np.arcsin(np.sin(phi) * np.sin(d) + np.cos(phi) * np.cos(d) * np.cos(h)))
    return f

def _hour_angle_fn(lon, day0):
    def f(sec):
        ra, dec, gast = sun_geocentric_apparent(_times(day0, sec))
        return (gast + lon - ra + 180.0) % 360.0 - 180.0
    return f

def _refine(f, lo, hi, want_up, n=41, rounds=6):
    """Shrink a bracket [lo, hi] known to contain an up/down crossing of f."""
    for _ in range(rounds):
        s = np.linspace(lo, hi, n); v = f(s)
        idx = np.where((v[:-1] < 0) & (v[1:] >= 0))[0] if want_up else np.where((v[:-1] >= 0) & (v[1:] < 0))[0]
        if len(idx) == 0: return None
        i = idx[-1] if want_up else idx[0]
        lo, hi = s[i], s[i + 1]
    # linear interpolation inside the last (~0.01 s) bracket
    v0, v1 = f(np.array([lo, hi]))
    return lo + (hi - lo) * (0 - v0) / (v1 - v0) if v1 != v0 else lo

def _crossing(f, lo, hi, want_up):
    s = np.arange(lo, hi + _GRID_S, _GRID_S); v = f(s) - 0.0
    idx = np.where((v[:-1] < 0) & (v[1:] >= 0))[0] if want_up else np.where((v[:-1] >= 0) & (v[1:] < 0))[0]
    if len(idx) == 0: return None
    i = idx[-1] if want_up else idx[0]
    return _refine(f, s[i], s[i + 1], want_up)

def _dt(day0, sec):
    return None if sec is None else day0 + timedelta(seconds=float(sec))

def _dip_deg(elev):  # spec convention: dip ~ 1.76' * sqrt(h)
    return 0.0 if elev <= 0 else 1.76 * math.sqrt(elev) / 60.0

@dataclass
class SkyfieldDayEvents:
    date: date
    fajr: "datetime | None"; sunrise: "datetime | None"; dhuhr: datetime
    asr: "datetime | None"; maghrib: "datetime | None"; isha: "datetime | None"

def compute_day_events(d: date, lat: float, lon: float, elevation_m: float = 0.0,
                       fajr_angle_deg: float = 18.0, isha_angle_deg: float = 17.0,
                       asr_shadow_ratio: float = 1.0, mode: str = "geocentric") -> SkyfieldDayEvents:
    day0 = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    noon_guess = 12 * 3600.0 - lon / 15.0 * 3600.0
    # transit: hour angle crosses 0 upward
    h_fn = _hour_angle_fn(lon, day0)
    s = np.arange(noon_guess - 7200, noon_guess + 7200 + 60, 60.0); v = h_fn(s)
    idx = np.where((v[:-1] < 0) & (v[1:] >= 0) & (np.abs(v[:-1]) < 90))[0]
    if len(idx) == 0: raise RuntimeError("no transit found")
    tr = _refine(h_fn, s[idx[0]], s[idx[0] + 1], True)
    alt_fn = _altitude_fn(lat, lon, mode, day0)
    _, dec_tr, _ = sun_geocentric_apparent(_times(day0, [tr]))
    dec_tr = float(dec_tr[0])
    span = 13 * 3600.0
    def morning(target): return _crossing(lambda x: alt_fn(x) - target, tr - span, tr, True)
    def evening(target): return _crossing(lambda x: alt_fn(x) - target, tr, tr + span, False)
    horizon = SUN_HORIZON_DEG - _dip_deg(elevation_m)
    noon_alt = 90.0 - abs(lat - dec_tr)
    asr_alt = None if noon_alt <= 0 else math.degrees(math.atan(1.0 / (asr_shadow_ratio + math.tan(math.radians(90.0 - noon_alt)))))
    return SkyfieldDayEvents(
        date=d, fajr=_dt(day0, morning(-fajr_angle_deg)), sunrise=_dt(day0, morning(horizon)),
        dhuhr=_dt(day0, tr), asr=None if asr_alt is None else _dt(day0, evening(asr_alt)),
        maghrib=_dt(day0, evening(horizon)), isha=_dt(day0, evening(-isha_angle_deg)))
