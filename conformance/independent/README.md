# waqt-independent — a clean-room implementation of the Waqt conformance operations

Zero-dependency Node.js (≥ 20) implementation of every operation in `../spec/COP.md`. It exists to test
whether the **written** Waqt specification is sufficient to implement Waqt, and to expose assumptions the
reference implementation (`waqt-core`) makes without saying so.

```
node src/cli.mjs --describe                    # descriptor + supported operations
echo '{"cases":[...]}' | node src/cli.mjs      # COP adapter
npm test                                       # 13 unit tests (incl. the 116 frozen scheduling vectors)
```

## Deliberate architectural differences from `waqt-core`

| concern | `waqt-core` (reference) | `waqt-independent` |
|---|---|---|
| language / runtime | Python | JavaScript (Node) |
| Sun | NOAA-style low-precision position | truncated **VSOP87D** Earth + FK5 + nutation + aberration, ΔT (Espenak–Meeus) — ≈0.1 s from DE421 |
| event solving | closed-form hour angles | **scan-and-bisect on the true altitude function**, anchored at the upper transit; ternary search for grazing events |
| instants | `datetime` | integer **microseconds** since the epoch |
| time zones | Python `zoneinfo` | ICU via `Intl.DateTimeFormat` |
| day bracketing | by civil date | by the **Maghrib instants** that bracket the instant; label = civil date of the closing Maghrib *instant* |
| Umm al-Qura | PyEphem conjunction/moonset, cached chain | own ELP2000-82-truncated Moon (≈10″ from DE421), conjunction by root finding, 29/30 **chain rule** with burn-in blocks |
| scheduling | reference engine | a `DaySource` abstraction (frozen table **or** live astronomy) under one engine |
| remote providers | transport + clock objects | pure **behavioural model** (no I/O of any kind) |

## Layout

```
src/timeutil.mjs         civil days (Hinnant), instants, ICU zones
src/astro/sun.mjs        apparent Sun            src/astro/vsop_earth.mjs   series      src/astro/deltat.mjs  ΔT
src/astro/events.mjs     transit, crossings, Asr, polar logic
src/astro/moon.mjs       Moon, conjunction, moonset
src/calendar/{tabular,ummalqura,providers}.mjs
src/waqtday.mjs         day model + waqt.compute        src/schedule.mjs   scheduling engine
src/institutional.mjs   src/interop.mjs   src/ops.mjs (COP dispatcher)   src/cli.mjs (adapter)
```

## What "independent" does and does not mean here — read this before citing it

* **No code** is shared with `waqt-core`, `waqt`, or `consumers/js`; there is no import of either.
* The specification it was built from is `docs/*.md` **plus the frozen vectors** (which are normative). The
  scheduling layer is the clearest case: written from `SCHEDULING.md` alone it passed 108 of 116 vectors;
  the other 8 were prose gaps (see `../spec/OPEN-QUESTIONS.md`, OQ-SCH-1…5).
* The author is the same agent/session that wrote the harness and the reference adapter, and therefore
  **had read** parts of `waqt-core` (the provider transport interface in `aladhan.py`, public entry points,
  and reference *outputs*) while building the adapter. The Waqt-day model, astronomy, calendars and scheduling
  were written without consulting reference source; the remote-provider *model* was written after reading
  `LIVE-INTEGRATIONS.md` **and** having seen the reference provider's constants, so its independence is the weakest.
* Expected values for normative astronomy vectors come from JPL DE421, never from either implementation.
* The Node runtime is the only second language available in the build environment; a Go/Rust/Java port is the
  natural next test of language-level independence.

## Instant range and conformance claim

Instants are integer microseconds stored as JavaScript `Number`. Integer microseconds are exact only while their
magnitude is at most `Number.MAX_SAFE_INTEGER`, which limits this implementation to roughly years 1685–2255.
It returns `RANGE_ERROR` outside that representable range rather than silently rounding. Gregorian calendar
operations use integer day numbers and can cover dates through 2300, but those date-only vectors do **not**
verify upper-range instants. The current conformance report makes no full-range instant-conformance claim. A
second independent method must verify upper-range instants before any such claim is made.
