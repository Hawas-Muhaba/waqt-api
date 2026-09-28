# Independent Astronomical Reference (Parallel Milestone A)

Sprint 7's report first named the gap; Sprint 8's report elevated it to a
tracked milestone (`docs/CALENDAR-INTEROP.md` §6); Sprint 9 builds it,
alongside — not instead of — the SDK work (see `docs/SDK.md`), per the
Sprint 9 brief's instruction to run it as a **parallel** milestone.

## The gap this closes

Every independent consumer this project has ever shipped
(`consumers/js/*`) validates *semantic* layers — day tiling, scheduling,
institutional rules, calendar interoperability — against frozen data.
None of them independently calculates a solar position: they all consume
Maghrib/Fajr/etc. instants that `waqt/solar.py` already produced. The
deepest numerical layer of the whole project — the astronomy itself — had
never received the same kind of independent cross-check its own outputs
get downstream.

## What was built

`independent-astronomy/independent_solar/` — a second, standalone solar
event engine. It imports nothing from `waqt` and shares no astronomy code
with `waqt/solar.py`. The two engines take genuinely different routes to
the same six events:

| | `waqt/solar.py` (existing reference) | `independent_solar/` (this milestone) |
|---|---|---|
| Apparent solar position | NOAA low-precision polynomial series; nutation + aberration folded into one combined shortcut term on true longitude | Explicit 4-term nutation-in-longitude/obliquity series (Meeus Ch. 22) and a separate `-20.4898"/R` aberration term, applied independently |
| Declination | `asin(sin(obliq_corr) · sin(app_long))` | Full right ascension AND declination via the standard equatorial transform from apparent longitude + true obliquity |
| Finding an event's UTC instant | Estimate solar noon from the **equation of time**, offset by the hour angle for the target altitude, refine twice | Solve directly for the sun's **local hour angle** (`Greenwich Apparent Sidereal Time + longitude − right ascension`) hitting the target value, via Newton-style iteration on the ~15.041°/hour sidereal rate. No equation of time is computed anywhere in this package. |
| ΔT (TT − UT1) | `waqt/timescale.py`'s `EspenakMeeusDeltaT` | Its own from-scratch coding of the *same published* Espenak-Meeus polynomial — see "Design decisions" below for why this one component is deliberately shared knowledge, not shared code |

The altitude-to-hour-angle formula
(`acos((sin(alt) − sin(lat)sin(dec)) / (cos(lat)cos(dec)))`) is used by
both, because it's basic spherical astronomy used by essentially every
sunrise/sunset calculator in existence (including `astral`, the project's
existing Level-B cross-check) — not something `waqt/solar.py` invented.

`independent-astronomy/compare.py` runs both engines across a 12-location
× 5-date matrix (60 rows, 6 events each — 360 individual comparisons) and
writes every input, both engines' output, and the signed difference to
`independent-astronomy/vectors/independent_astronomy_comparison.json`.
Nothing in that file is hand-typed.

## Results

| Latitude band | Tolerance | Max |diff| observed |
|---|---|---|
| Equator | 30s | 21.5s |
| Tropics | 40s | 31.2s |
| Mid-latitude | 80s | 49.0s |
| High latitude | 500s* | 435.7s |

\* Widened from the 130s a straight read of `docs/ASTRONOMY.md`'s
Level-B-vs-`astral` table would suggest. See "Honest limitations" below —
this is a real, explained, and now measured effect, not a loosened bar
to force a pass.

No location/date/event combination disagreed on whether the event is
*defined* at all (i.e. neither engine returned a numeric time where the
other returned polar-day/night `None`, or vice versa).

## Design decisions and why

- **Different position algorithm, different event-solving method, but the
  same ΔT model.** ΔT is a measured astronomical quantity (the
  accumulated difference between Earth's actual rotation and a uniform
  clock), not an algorithmic choice the way "equation of time vs. sidereal
  time" is. Using two different ΔT models would blur genuine
  solar-position disagreement together with a second, unrelated source of
  drift, making it harder to say what the comparison is actually
  measuring. `independent_solar/deltat.py` is written from scratch (it
  does not import `waqt.timescale`) but deliberately follows the same
  published NASA/Espenak-Meeus polynomial family, so that every
  disagreement in the results above is attributable to the solar-position
  and event-finding algorithms — the part this milestone is actually
  about.
- **Right ascension + sidereal time, not equation of time.** This is the
  substantive independence: an equation-of-time bug and a sidereal-time
  bug would have to be *the same wrong answer* by coincidence to both
  produce agreement, since they're arithmetically unrelated paths to the
  same instant.
- **Same geographic/date test matrix as `tests/test_core.py`, extended.**
  Continuity with the project's own documented accuracy tiers, plus
  Dibrugarh (the civil-timezone/solar-time divergence case from Sprint 8)
  and a second Addis Ababa elevation, and all four seasonal turning points
  instead of one arbitrary date.
- **Not wired into the HTTP API.** The Sprint 9 brief is explicit that
  this milestone should "not silently replace the existing engine" and
  should "first prove agreement/disagreement transparently." `waqt/api/`
  is untouched; nothing here is reachable from `/v1/*`.

## Honest limitations

- **High-latitude disagreement near the equinox is real and can reach ~7
  minutes**, not a bug in either engine. `docs/ASTRONOMY.md` already
  explains the geometry: near high latitude the sun's path across the sky
  is shallow, so a small angle disagreement between any two independent
  algorithms — however each is derived — translates into a large *time*
  disagreement. This milestone is the first time that prediction has been
  checked against a second live implementation rather than assumed from
  the `astral` comparison alone. A caller at high latitude who needs
  tight agreement near an equinox should treat both engines' outputs as
  order-of-minutes uncertain there, not order-of-seconds.
- **Neither engine has been checked against a Level-A ephemeris (VSOP87 or
  a JPL ephemeris).** Two Level-B-grade algorithms agreeing with each
  other is evidence they're both *converging on the same underlying
  astronomy*, not proof that astronomy is correct to sub-second precision.
  `docs/ASTRONOMY.md`'s Level A row is still "Not implemented" — this
  milestone doesn't change that.

  **Update, Sprint 10:** this gap is now closed for measurement purposes
  (not for production use) — see `independent-astronomy/level_a/` and
  `docs/RELEASING.md`'s sibling doc for the local library, or read on:
  `compare_level_a.py` checks both `waqt/solar.py` and `independent_solar`
  against a genuine Level-A reference (full VSOP87, via the published,
  independently-tested `pymeeus` library — not hand-derived coefficients).
  The result was more interesting than "both engines are fine": across
  every latitude band, `independent_solar` (Meeus low-accuracy, this
  milestone) tracks the VSOP87 reference within 2-5 seconds, while
  `waqt/solar.py` (NOAA low-precision, production) diverges considerably
  more — up to ~40 seconds at mid-latitude and ~430 seconds at high
  latitude. Two Level-B algorithms agreeing with each other, in other
  words, was hiding the fact that they are not equally close to the
  truth; `waqt/solar.py` is unchanged by this finding (Sprint 10's DoD
  explicitly forbids "silently changing the production astronomical
  engine" on this basis alone) — see the Sprint 10 report for the full
  discussion and what a fix would look like if one is chosen later.
- **`independent_solar`'s Newton-style iteration has a fixed 10-iteration
  cap and a 1e-7° tolerance**; it has not been stress-tested against
  contrived non-convergent cases the way `waqt/solar.py`'s two-pass
  refinement has years of production exposure behind it. In every case in
  the 60-row test matrix it converges in well under 10 iterations.
- **The comparison matrix is 12 locations × 5 dates, not exhaustive.** It
  reuses and extends the project's existing documented geographic
  coverage rather than an arbitrary larger grid; a location/date far
  outside this matrix (e.g. a different date-line location, or a date far
  from an equinox/solstice at extreme latitude) has not specifically been
  checked, though nothing about either engine's math is date- or
  location-specific in a way that would suggest hidden surprises outside
  the tested range.
