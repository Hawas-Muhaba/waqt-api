# Astronomy Engine

What actually computes sunrise, sunset, Fajr, Dhuhr, Asr, and Isha — and, just as importantly, what its numbers are worth.

## The engine

`waqt/solar.py` implements the NOAA low-precision solar position algorithm (the same formulas behind NOAA's public Solar Calculator spreadsheet): solar declination and equation of time from a low-order polynomial series, refined by two iterations to account for how those quantities drift across the day. It is self-contained — no external ephemeris files, no network calls.

Every response that used this engine identifies it explicitly:
```json
"computation": { "astronomy_engine": "waqt-noaa-low-precision", "accuracy_level": "B", "timescale_model": "espenak-meeus-2006", "delta_t_seconds": 75.5 }
```

## Accuracy levels

Two levels are defined.

| Level | Definition | Status |
|---|---|---|
| **B — Operational** | Agreement with an independent reference solar calculator (`astral`), within latitude-tiered tolerances (below) | **Implemented and tested.** This is what the API delivers today, always. |
| **A — High-precision** | Sub-10-second agreement against a high-precision ephemeris (e.g. VSOP87 or a modern JPL ephemeris) across the full geographic matrix | **Numerically met on the tested matrix, not yet claimed.** After Sprint 11's three fixes `core/waqt_core/solar.py` agrees with a full-VSOP87 reference within ~1.0 s (3.6 s at high latitude) on an 80-row matrix, a dense latitude sweep and an equinox sweep. The API still reports Level B / `waqt-noaa-low-precision`: promotion is an open decision (one reference, essentially one year) — see [`ASTRONOMY-ENGINE-EVALUATION.md`](ASTRONOMY-ENGINE-EVALUATION.md) §5. |

### What Level-A measurement found (Sprint 10) — and what it turned out to mean (Sprint 11)

Sprint 10's comparison of the production engine against a VSOP87 reference:

| Latitude band | production vs Level A, Sprint 10 | production vs Level A, after Sprint 11 | `independent_solar` (Level B) vs Level A |
|---|---|---|---|
| equator | ~20s | ~0.9s | ~1.7s |
| tropics | ~32s | ~1.0s | ~1.7s |
| mid-latitude N | ~40s | ~1.0s | ~1.8s |
| mid-latitude S | ~48s | ~1.0s | ~1.9s |
| high-latitude | ~432s | ~3.6s | ~4.3s |

Sprint 10 read the gap as NOAA low-precision formulas being an order of
magnitude less accurate than Meeus-with-nutation, and (in the earlier version
of this document) called the high-latitude figure "a real geometric effect".
**That was wrong, or at best a third of the story.** Sprint 11 traced it to
three defects in the event solver — a missing `− 0.5` in the Julian Day of the
refinement loop (sampling the sun 12 h off), declination/equation-of-time
sampled at UT noon instead of the transit instant, and the same UT-noon start
deciding whether a marginal polar-threshold event exists. Geometry did amplify
them at high latitude (hour angle is ~865× more sensitive to declination there
than at the equator), but the input error was ours. With the fixes, the
production engine is at or better than Level B in every band. Full
investigation, before/after tables and reproduction commands:
[`ASTRONOMY-ENGINE-EVALUATION.md`](ASTRONOMY-ENGINE-EVALUATION.md).

### Historical: agreement with `astral`, by latitude (not re-measured in Sprint 11)

These figures are `tests/test_core.py`'s tolerances against the third-party `astral` calculator. The suite still passes against them after Sprint 11, so they stand as **upper bounds**; the Level-A numbers above are the current measurement.

| Latitude band | Agreement with reference |
|---|---|
| < 15° (equator/tropics) | ~20–30 seconds |
| 15°–40° (mid-latitude) | ~35–70 seconds |
| > 40° (high latitude) | ~55–120 seconds |

This gets looser toward the poles for a real geometric reason, not sloppiness: near the equator the sun's altitude changes quickly around rise/set, so a small angle disagreement between two independent algorithms barely shifts the *time*; near high latitude the sun's path is shallow, so the same angle disagreement amplifies. `tests/test_core.py` encodes these tolerances directly, tiered by latitude, rather than hiding the spread behind one number.

**Practical implication:** fine for a wall display, a timetable, or a scheduling system. Not yet verified precise enough for legal or liturgical use without independent confirmation, especially outside the tropics. The Level-A comparison above supersedes this for accuracy claims: after Sprint 11, measured error against a high-precision reference is about a second on the tested matrix. Not yet verified for legal or liturgical use — one reference, essentially one year.

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
