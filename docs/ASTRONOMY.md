# Astronomy Engine

What actually computes sunrise, sunset, Fajr, Dhuhr, Asr, and Isha — and, just as importantly, what its numbers are worth.

## The engine

`waqt/solar.py` implements the NOAA low-precision solar position algorithm (the same formulas behind NOAA's public Solar Calculator spreadsheet): solar declination and equation of time from a low-order polynomial series, refined by two iterations to account for how those quantities drift across the day. It is self-contained — no external ephemeris files, no network calls.

Every response that used this engine identifies it explicitly:
```json
"computation": { "astronomy_engine": "waqt-noaa-low-precision", "accuracy_level": "B", "timescale_model": "espenak-meeus-2006", "delta_t_seconds": 75.5 }
```

## Accuracy levels

Two levels are defined. Only one is implemented.

| Level | Definition | Status |
|---|---|---|
| **B — Operational** | Agreement with an independent reference solar calculator (`astral`), within latitude-tiered tolerances (below) | **Implemented and tested.** This is what the API delivers today, always. |
| **A — High-precision** | Sub-10-second agreement against a high-precision ephemeris (e.g. VSOP87 or a modern JPL ephemeris) across the full geographic matrix | **Not implemented.** Would require a different engine, not a tuning pass on this one. If you need this, don't rely on Waqt yet. |

### Measured Level-B accuracy, by latitude

| Latitude band | Agreement with reference |
|---|---|
| < 15° (equator/tropics) | ~20–30 seconds |
| 15°–40° (mid-latitude) | ~35–70 seconds |
| > 40° (high latitude) | ~55–120 seconds |

This gets looser toward the poles for a real geometric reason, not sloppiness: near the equator the sun's altitude changes quickly around rise/set, so a small angle disagreement between two independent algorithms barely shifts the *time*; near high latitude the sun's path is shallow, so the same angle disagreement amplifies. `tests/test_core.py` encodes these tolerances directly, tiered by latitude, rather than hiding the spread behind one number.

**Practical implication:** fine for a wall display, a timetable, or a scheduling system. Not yet verified precise enough for legal or liturgical use without independent confirmation, especially outside the tropics.

## Elevation

`elevation_m` applies to **sunrise/sunset only**, via the standard dip-of-horizon formula (`dip ≈ 1.76′ × √h`). It does **not** apply to Fajr, Isha, or Asr. Reasoning: elevation changes where the physical horizon sits relative to an observer, which is what sunrise/sunset are defined against; Fajr/Isha are twilight-*angle* events, and no mainstream prayer-time convention elevation-corrects them.

Verified two ways in `tests/test_core.py`: sunset gets monotonically later (and sunrise monotonically earlier) as elevation increases, and the magnitude at Addis Ababa's real altitude (~2,400 m) matches hand-calculation (~+5m49s to Maghrib).

## Time scale (ΔT)

Solar formulas are properly functions of Terrestrial Time, not UTC. The difference (ΔT = TT − UT1) is supplied by `waqt/timescale.py`'s `EspenakMeeusDeltaT` — the standard NASA-published polynomial, valid with documented accuracy across roughly 1900–2150. Current-era value is ~69–76 seconds and slowly increasing; every response reports the exact value used.

## Edge cases: polar day and polar night

Above roughly 66.6° latitude, the sun can fail to rise or set at all for weeks at a time. Waqt's rule, without exception: **return an explicit `UNDEFINED` status with a reason, never a guessed time.**

```json
{ "status": "UNDEFINED", "undefined_reason": "Maghrib (sunset) does not occur for this date/location — polar day or polar night...", "day": { "maghrib_open": null, "maghrib_close": null } }
```

There is no automatic fallback (nearest-latitude approximation, etc.) in v1 — a caller operating at extreme latitude needs to handle `UNDEFINED` explicitly. This is deliberate; a plausible-looking wrong number is worse than a clear "I don't know."

Tested at both poles' respective midsummers (Tromsø and McMurdo Station) in `tests/test_core.py`.

## What's validated, concretely

The geographic test matrix in `tests/test_core.py` covers: the equator (Quito), the tropics (Nairobi, Addis Ababa, Makkah), both hemispheres' mid-latitudes (Cairo, Cape Town), both hemispheres' high latitudes (Tromsø, Punta Arenas), both poles' polar day (Tromsø, McMurdo), the International Date Line (Fiji, Kiritimati — the most extreme real-world civil/solar offset available, ~24.5 hours), and four elevations at Addis Ababa. All six events are checked for correct internal ordering (`Fajr < sunrise < Dhuhr < Asr < Maghrib < Isha`) everywhere they're defined, in addition to the sunrise/sunset cross-validation against `astral`.
