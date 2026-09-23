# Sprint 5 Report — Waqt Time & Calendar Semantics

**Sprint goal:** formalize how software *reasons* about Waqt values — instants, days, dates, clock positions, durations, comparison, event relations, undefined behavior — as executable semantics with portable conformance vectors, not just prose.
**Status:** done. 106/106 tests passing (37 new: 22 semantics + 15 vector). `waqt/core.py` and `waqt/solar.py` remain **byte-identical** to their Sprint 2 state — the fourth consecutive sprint this has held, verified by md5sum, not asserted.

---

## 1. The eight things the brief asked to be settled — all eight, with a test each

| # | Concept | Where | Proof, not just claim |
|---|---|---|---|
| 1 | Waqt instant | `WaqtInstant` type alias (= `datetime`) | No new runtime type — deliberately; see §2 below for why that's the right call, not a shortcut |
| 2 | Waqt day, boundary at exact equality | `WaqtDay`, half-open `[open, close)` | `test_exact_maghrib_instant_is_start_of_new_day`: position at the exact Maghrib instant is exactly `00:00:00`, checked, not assumed |
| 3 | Waqt date assignment | `WaqtDay.hijri_date`, read from `WaqtResult` | `test_hijri_date_before_and_after_maghrib_differ` |
| 4 | Waqt clock time, non-24h day | `WaqtDay.position_of()` → `WaqtPosition` | `test_position_display_has_no_enforced_hour_ceiling`, plus a **real** day (London, Feb 2026) engineered into a conformance vector specifically because it runs long enough to produce `hour == 24` |
| 5 | Event positions never an independent clock | `EventPosition`, cannot exist without a `WaqtDay` | Structurally enforced (§4 below), not a docstring promise |
| 6 | Duration vs. Position vs. Instant | Three distinct concepts, two reuse existing types on purpose | `test_instant_minus_instant_is_ordinary_timedelta`, `test_position_to_instant_round_trip` |
| 7 | Comparison and arithmetic | `<`, `<=`, `to_instant()`, `crosses_maghrib()` | 8 tests, including order-independence and undefined-input handling |
| 8 | Undefined-event behavior | `WaqtUndefinedError`, two distinct levels (day vs. single event) | 5 tests, including the subtle case where Maghrib is fine but Fajr alone isn't |

## 2. The design decision most worth explaining: what did NOT get a new type

`WaqtInstant` and `Duration` are type aliases for `datetime.datetime` and `datetime.timedelta` — not new classes. This was a deliberate choice, not an oversight: those two stdlib types already have correct arithmetic and comparison for exactly what they represent, and wrapping them would add ceremony (constructors, unwrapping, `__eq__` boilerplate) without adding any meaning that wasn't already there. The place a new type earns its keep is `WaqtPosition` — because unlike an instant or a duration, *a position within a Waqt day is meaningless without knowing which day*, and that's precisely the fact ordinary numeric comparison can't express. Reaching for a new type everywhere would have obscured that distinction instead of sharpening it.

## 3. The rule that mattered most to get right: same-day-only comparison

This sprint's single highest-value piece of code is `WaqtPosition.__lt__`/`__le__` (and the equivalent on `EventPosition`) raising `IncomparableWaqtValuesError` when the two values don't share a day. This isn't a new idea — "Waqt timestamps from different locations MUST NOT be compared" has been a stated design principle since the very first proposal review, long before any code existed. What Sprint 5 does is turn that sentence into something a caller literally cannot get wrong silently: comparing two `WaqtPosition`s from different days doesn't return a misleading number, it raises, immediately, at the point of the mistake.

One deliberate asymmetry, called out explicitly in `docs/SEMANTICS.md` rather than left as an inconsistency someone would have to notice on their own: `==` across different days returns `False` rather than raising. Equality has a sensible answer either way ("are these the same thing" — no, obviously, they're from different days); *ordering* across incompatible days doesn't, so only ordering is treated as an error.

## 4. Event positions structurally cannot become an independent clock

The brief specifically asked that "an event can never accidentally be interpreted as an independent clock system." `EventPosition` enforces this by construction: it holds a `WaqtPosition`, and a `WaqtPosition` carries its owning day's identity internally (`_day_id`) whether or not the caller ever looks at it. There is no code path that produces an `EventPosition` without going through `WaqtDay.event()`/`WaqtDay.events()`, and no way to compare or resolve one to an instant without its day cooperating (`to_instant()` checks day identity and raises if it doesn't match). This isn't a convention documented for callers to follow — it's the only way the API can be used at all.

## 5. Portable conformance vectors — generated, not typed

Per the sprint's own addendum ("don't postpone conformance work"), `tests/vectors/waqt_vectors.json` holds ten cases, and every expected value in it was computed by *running* the Python reference implementation (`tests/vectors/generate_vectors.py`), never hand-typed into the JSON. `tests/test_vectors.py` then loads the same file and re-derives every value through the live code, asserting an exact match — which is both a regression test and, more importantly, proof that the file has the property an independent implementation in another language would actually need: reproducibility from a documented spec, not just internal consistency with itself.

The ten cases were chosen to force real coverage rather than pad a number:
- An ordinary instant (baseline).
- The **exact** Maghrib instant — `00:00:00`, checked to the second.
- One second before it — proves the previous day's boundary independently.
- Makkah itself.
- **A real day that runs long enough to produce `hour == 24`** — found by scanning actual dates/locations for one where `day_length_si_seconds > 86400` (London, mid-February), then placing the vector's instant inside that specific overflow window. Not a synthetic example; a real astronomical outcome.
- Polar `UNDEFINED` (Tromsø midsummer) — the vector correctly has no `waqt_position` or `events` key at all, tested directly (`test_undefined_vector_has_no_position_or_events`).
- Kiritimati — reusing Sprint 2's hardest-known date-line case rather than a fresh, easier one.
- Two Asr-convention vectors on the *same* instant, checked (`test_asr_vectors_differ_only_in_asr_event`) to differ in exactly one field and nothing else — the events-as-positions claim, proven again at the vector level, not just the unit-test level.
- An elevation comparison, checked to shift Maghrib later, not just differently.

## 6. What's still out of scope

- **No vectors in a second language yet** — the file is built to make that possible (documented tolerances, exact expected values, a generator script showing exactly how each was produced), but nothing outside Python has actually consumed it. That remains the real "independent implementation" milestone the project has been building toward since Sprint 1.
- **`crosses_maghrib()` doesn't expose *which* day each instant falls in** — only whether they differ. A caller wanting both days' full detail still needs to call `compute_waqt` twice. This was a deliberate scope cut for this sprint (the boolean answers exactly what the brief asked for) rather than an oversight; a richer version is an easy, obvious follow-up if wanted.
- **`WaqtPosition`'s negative-hour case** (an instant before a day's own Maghrib, which `position_of()` allows and signs correctly) has code but no dedicated test yet — it's exercised incidentally by `test_instant_one_second_before_maghrib_belongs_to_previous_day` via a *different* day's `position_of`, but the negative-position path on a day's *own* `position_of` for a before-its-Maghrib instant isn't directly asserted. Worth a follow-up test, not a design gap.

## Test suite

37 new tests (`test_semantics.py`: 22, `test_vectors.py`: 15) on top of the prior 69 — **106 total, all passing.** `core.py`/`solar.py` unchanged for the fourth sprint running. Run with `python3 -m pytest tests/ -v`; regenerate vectors (only if behavior intentionally changes) with `python3 tests/vectors/generate_vectors.py`.
