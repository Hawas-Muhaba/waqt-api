# Waqt — Stage 1 Scope

**Implements:** Core Time Model v0.1, §1–4 (Makkah reference, day boundary, hour, event positions), as a working HTTP API.
**Does not implement:** anything outside those four sections. See §"Explicitly out" below.

---

## What is implemented

### `waqt/solar.py` — solar event engine
- NOAA low-precision solar position algorithm (declination, equation of time), with one refinement pass on the hour-angle calculation.
- Generalized event finder: any depression angle, morning or evening → one function computes sunrise, sunset, Fajr, and Isha alike.
- Solar transit (Dhuhr) — always defined.
- Asr via the standard shadow-ratio formula (parametrized 1× / 2× — Shafi'i–Maliki–Hanbali vs. Hanafi).
- Returns `None` (never a guessed value) when an event does not occur at a given latitude/date — the polar day/night case.

**Validated against** the `astral` library (an independent, widely-used implementation) at Addis Ababa, Makkah, and London across two seasons. Result — and this is worth stating precisely rather than picking one flattering number:

- **Near the equator** (Addis Ababa, Makkah): agreement within **~10–20 seconds**, comfortably inside the ±30 s Level-B tolerance proposed earlier.
- **At higher latitude** (London, both seasons tested): agreement within **~30–55 seconds** — looser, and it stays looser even after the iterative refinement fully converges (checked to 8 iterations; the gap doesn't close further). This is a real geometric effect, not a bug: near the equator the sun's altitude changes quickly around rise/set, so a small angle disagreement between the two algorithms barely shifts the *time*; at higher latitude the sun's path is shallower, so the same angle disagreement amplifies into a larger time disagreement. The test suite encodes this directly — a 20 s tolerance at low latitude, 60 s at high latitude — rather than hiding it behind one number.

Polar-day non-existence (Tromsø, midsummer) correctly returns `None`/`UNDEFINED` rather than an invented time.

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

1. **"Local Gregorian date" is resolved as the UTC calendar date.** The Core Time Model brackets a day using "the local Gregorian date of the instant," which is a civil-timezone concept the model doesn't itself define. This implementation substitutes the UTC date — exact near Greenwich, and safe for Addis Ababa and Makkah (both close to UTC, far from the date line), but **not yet correct near the International Date Line** (e.g. the Americas or the Pacific). This was flagged as a deferred edge case in the original proposal review and remains one.
2. **No elevation correction.** Sunset from a hilltop is earlier than sunset at the base; this engine doesn't know the difference. Matters for Addis Ababa specifically (~2,400 m).
3. **Accuracy is Level-B, not Level-A, and gets looser at higher latitude.** ~10–20 s near the equator, up to ~55 s tested at 51.5°N — see the measured numbers above. Fine for a wall display or timetable; not yet fine for legal/liturgical precision without independent verification, especially outside the tropics.
4. **The Hijri dates are approximate**, per the honesty note above — do not use for determining the start of Ramadan or any matter of religious obligation. The interface is built to swap in an authoritative provider later without touching anything else.
5. **Single ΔT/ time-scale model:** none. Input and computation are both treated as UTC directly to Julian Day, without a formal ΔT (TT−UT1) conversion. For all dates in practical use (within a few decades of now) this introduces well under a second of error and is not currently a real-world concern — but it means the "pin a named ΔT model" requirement from the original review is not yet done.

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
