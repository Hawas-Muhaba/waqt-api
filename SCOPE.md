# Waqt — Stage 1 Scope

**Sprint 4 note:** the API surface described below (`GET /v1/waqt` and its query params) has since grown into a full seven-endpoint, versioned HTTP contract. This file's job is now the honest engineering-limitations record; for the actual API reference, start with `docs/API.md`, `docs/TIME-MODEL.md`, `docs/ASTRONOMY.md`, and `docs/CALENDARS.md`. Everything below is still accurate as a limitations list.

**Sprint 7 note:** `waqt/institutional/` (week, fiscal year, academic year, calendar profiles) and `docs/INSTITUTIONAL.md` now exist on top of everything below; see `SPRINT-7-REPORT.md` for what changed and its own honest-limitations section. One item carried forward on the roadmap rather than resolved by Sprint 7: a **second, independent astronomy implementation** (an implementation that recomputes sunrise/Maghrib from coordinates rather than validating against `astral` or reusing this project's own `waqt/solar.py`). Sprint 6 named this gap; Sprint 7 did not need to close it (the institutional calendar layer needs no astronomy at all) but it remains open and should not be allowed to drift indefinitely.

**Implements:** Core Time Model v0.1, §1–4 (Makkah reference, day boundary, hour, event positions), as a working HTTP API.
**Does not implement:** anything outside those four sections. See §"Explicitly out" below.

---

## What is implemented

**Sprint 2 update:** local civil-date handling, elevation, and ΔT are now real (see `SPRINT-2-REPORT.md` for what changed and why). The summary below reflects the current state; where Stage 1's original limitation has been fixed, it's marked as such rather than silently rewritten.

### `waqt/timezone_provider.py` — real civil dates (Sprint 2)
Resolves lat/lon to an IANA timezone and derives the local civil date from it, replacing Stage 1's UTC-date shortcut. Fixes the International Date Line failure mode — verified against Kiritimati (Kiribati), whose civil offset (UTC+14) is ~24.5 hours from its natural solar time, the most extreme real-world case available. See `SPRINT-2-REPORT.md` §1 for the bug this caught during development.

### `waqt/timescale.py` — ΔT provider (Sprint 2)
`TimeScaleProvider` protocol with one implementation, `EspenakMeeusDeltaT` (the standard NASA-published polynomial). Wired into every solar calculation. Named and versioned in every API response.

### `waqt/hijri.py` + `waqt/calendar_providers/` — calendar provider system (Sprint 3)
Five provider categories now exist, all satisfying the same `HijriProvider` protocol (`name`, `version`, `from_gregorian`):
- `ArithmeticTabularProvider` — Stage 1's classical 30-year arithmetic calendar, unchanged.
- **`UmmAlQuraProvider` (new)** — an astronomical approximation of the real current Umm al-Qura calculation rule (conjunction-before-Maghrib + moonset-after-Maghrib, both evaluated at Makkah). Validated against **four independently-known official Umm al-Qura New Year dates spanning 2016–2025, all four matching exactly**. See `SPRINT-3-REPORT.md` §3 for exactly what it does and doesn't guarantee — it has no channel for real UAQ's occasional sighting-based adjustments, and uses a high-quality-but-not-highest-precision lunar ephemeris (`ephem`/PyEphem).
- `DeclaredProvider` — institutional override, now versioned.
- **`LocalObservationProvider` (new)** — crowd-sourced sighting reports, distinct from Declared, carries the observation site via `source_note`.
- **`ExampleRegionalOffsetProvider` (new, demo)** — a deliberately trivial third-party provider proving the pluggability claim: it's written with zero access to `core.py`/`solar.py` and plugs in through the identical injection point as every built-in.

**Verified, not just designed:** swapping the calendar provider changes *only* the returned Hijri date — the Maghrib boundary, the Waqt clock reading, and every prayer event's instant are bit-for-bit identical regardless of which calendar is used. `waqt/core.py` and `waqt/solar.py` are md5-identical to their Sprint 2 state; no provider added this sprint touched either file.

### `waqt/solar.py` — solar event engine
- NOAA low-precision solar position algorithm (declination, equation of time), with one refinement pass on the hour-angle calculation.
- Generalized event finder: any depression angle, morning or evening → one function computes sunrise, sunset, Fajr, and Isha alike.
- Solar transit (Dhuhr) — always defined.
- Asr via the standard shadow-ratio formula (parametrized 1× / 2× — Shafi'i–Maliki–Hanbali vs. Hanafi).
- Returns `None` (never a guessed value) when an event does not occur at a given latitude/date — the polar day/night case.

**Validated against** the `astral` library across the full Sprint 2 geographic matrix (equator, tropics, mid-latitude N/S, high-latitude N/S, date-line, polar) — see `SPRINT-2-REPORT.md` for the complete table. Result, stated precisely rather than picking one flattering number:

- **Near the equator**: agreement within **~20–30 seconds**.
- **Mid-latitude**: within **~35–70 seconds**.
- **High latitude (>40°)**: within **~55–120 seconds** — looser, and this stays true after the iterative refinement fully converges (checked to 8 iterations). This is a real geometric effect, not a bug: near the equator the sun's altitude changes quickly around rise/set, so a small angle disagreement barely shifts the *time*; at high latitude the sun's path is shallow, so the same angle disagreement amplifies. The test suite encodes this directly via latitude-tiered tolerances rather than hiding it behind one number.

Polar-day non-existence (Tromsø and McMurdo Station, respective midsummers) correctly returns `None`/`UNDEFINED` rather than an invented time.

**Not yet done:** no comparison against a high-precision (Level-A, sub-second) ephemeris; no atmospheric-refraction modeling beyond the standard 34′ term; no elevation correction (see "Known limitations").

### `waqt/hijri.py` — calendar provider interface
- `HijriProvider` protocol, exactly as specified: a stateless map from a Gregorian civil date to a Hijri date, with no location dependence.
- One shipped provider, `ArithmeticTabularProvider` — the classical 30-year-cycle tabular Islamic calendar (JDN epoch 1948440). Deterministic, offline, well-published.
- One override mechanism, `DeclaredProvider` — lets an operating institution pin specific dates (e.g. from local moon sighting) and fall back to another provider otherwise.
- Weekday naming, correctly shifted: the Islamic weekday is derived from the *closing* Maghrib's Gregorian date, not the instant's own Gregorian weekday, so Jumu'ah correctly begins at Thursday-evening Maghrib.

**Named honestly:** the shipped provider is `arithmetic-tabular`, not `tabular-uaq`. It is **not** the official Saudi Umm al-Qura calendar — that calendar's current rule set is not purely arithmetic and requires the officially published tables to reproduce exactly. The arithmetic provider will typically agree with Umm al-Qura within a day, sometimes two. A true `tabular-uaq` provider is future work pending that dataset.

### `waqt/core.py` — the Core Time Model itself
Implements the four sections of the Core Time Model document exactly:

| Spec section | Implementation |
|---|---|
| §1 Makkah reference | `HijriProvider.from_gregorian()` — one global date, no location input |
| §2 Day boundary | `_bracket_maghrib()` — finds `[M(D), M(D+1))` containing the instant; returns `UNDEFINED` if either boundary doesn't exist |
| §3 The hour | SI time elapsed since the day's opening Maghrib; **not** clipped at 24:00:00 (shown to exceed it when the day runs long, exactly as specified) |
| §4 Event positions | Every prayer event reported as `t_e − M(D)`, on the *same* grid as §3 — proven, by direct test, to be unaffected by Fajr-angle/Asr-ratio choices anywhere except at its own marker |

### `waqt/api.py` — HTTP surface
One endpoint: `GET /v1/waqt?lat=&lon=&instant=&fajr_angle=&isha_angle=&asr_ratio=&calendar_provider=`.
Returns status, Hijri date + weekday, day boundaries, the Waqt reading, all six event positions, the next event with a countdown, and the profile used. Input validation (lat/lon range, unknown provider, malformed instant) returns proper 4xx errors rather than guessing.

Tested end-to-end (see `tests/`): normal case (Addis Ababa), high-latitude-but-defined case (London, midsummer), polar-undefined case (Tromsø, midsummer), and both `asr_ratio` conventions to confirm the events-as-positions property holds in practice, not just on paper.

---

## Explicitly out of Stage 1

Per your instruction to hold the line on scope — none of the following exist in this codebase, on purpose:

- Fiscal year, school year, week-as-a-module
- Wire format / compact string encoding
- Multiple calendar providers beyond the one reference + override
- Any notion of civil timezone or national offset
- OS/hardware clock integration
- A second, independent-language implementation (Stage 7 in the earlier build plan)
- Elevation correction (accepted nowhere as an input yet)

---

## Known limitations (read before relying on this for real prayer times)

1. **"Local Gregorian date" is now resolved via a real IANA timezone lookup (Sprint 2)** — fixed from Stage 1's UTC-date shortcut. Verified against the most extreme real-world case available (Kiritimati, Kiribati). The bracket search widens to a ±3-day window to handle large civil/solar offsets; this is a pragmatic bound, not a formal proof it handles every conceivable timezone.
2. **Elevation correction is now implemented (Sprint 2)**, applied to sunrise/sunset only, not Fajr/Isha/Asr — see `solar.py` for the reasoning. Off by default (elevation_m=0).
3. **Accuracy is *labelled* Level-B; measured, it now meets the Level-A number on the tested matrix** — definition in `SPRINT-2-REPORT.md` §6; Sprint 11 fixed three solver bugs and measured ~1 s (3.6 s high-latitude) against a VSOP87 reference (`docs/ASTRONOMY-ENGINE-EVALUATION.md`). The label is deliberately unchanged pending a decision to promote it (one reference, essentially one year). **Times published before Sprint 11 can be off by up to ~7 min at high latitude near an equinox.**
4. **The Hijri dates are approximate, on two different providers with two different caveats** — `arithmetic-tabular` is a pure arithmetic calendar (never claims to be UAQ); `umm-al-qura` is a real astronomical implementation of UAQ's rule, validated against four historical dates, but has no channel for real UAQ's occasional sighting-based overrides on the four liturgically significant months. **Do not use either for determining the start of Ramadan or any matter of religious obligation** without independent confirmation. The interface is built so an authoritative live-feed provider can be swapped in later without touching anything else.
5. **Single ΔT/ time-scale model:** now implemented (Sprint 2) — see `core/waqt_core/timescale.py`. `EspenakMeeusDeltaT` is wired into every calculation and named in every response.

---

## How to run it

```bash
cd waqt-api
pip install fastapi uvicorn --break-system-packages
uvicorn waqt.api:app --reload --port 8000
curl "http://localhost:8000/v1/waqt?lat=9.0192&lon=38.7525"
```

## How to verify it

```bash
python3 -m pytest tests/ -v
```

runs the checks described above: solar-engine agreement with an independent library, the polar-undefined case, and the events-as-positions invariant.
