# Waqt Temporal Semantics

This is the specification `waqt/semantics.py` implements. Where `TIME-MODEL.md` explains *why* the numbers look the way they do, this document defines *how software is allowed to reason about them* — precisely enough that an independent implementation in another language could be checked against it using `tests/vectors/waqt_vectors.json`.

Every rule below has a corresponding test in `tests/test_semantics.py`, cited by name, so nothing here is aspirational.

---

## 1. Waqt Instant

A Waqt instant is an ordinary UTC `datetime` (equivalently, a Unix timestamp). Waqt does not define a new absolute time standard. TAI and leap seconds are out of scope — Waqt instants are civil UTC.

## 2. Waqt Day

```
WaqtDay(L, D) = [Maghrib(L, D), Maghrib(L, D+1))
```

A half-open interval. **The boundary rule, stated exactly:**

> An instant *t* belongs to `WaqtDay(L, D)` if and only if `Maghrib(L, D) <= t < Maghrib(L, D+1)`.

At the exact instant of Maghrib, the new day has **already** begun — the Waqt clock position at that instant is exactly `00:00:00`.

- `test_exact_maghrib_instant_is_start_of_new_day`
- `test_instant_one_second_before_maghrib_belongs_to_previous_day`
- `test_contains_is_half_open_closed_at_open_end`

A `WaqtDay`'s length is not guaranteed to be 86,400 seconds (see §4).

## 3. Waqt Date

The Hijri date and the weekday attached to `WaqtDay(L, D)` are those of the **label date**: the Gregorian *civil* date, in the IANA time zone of location `L`, on which the day's **closing** Maghrib *instant* falls. **[DAY-004, decision DR-0001]** The Hijri date is the calendar provider's date for the label date; the weekday is that date's weekday name. Before Maghrib the label is today's, at or after Maghrib it is tomorrow's. `core.compute_waqt` computes exactly `label_date = tz.local_date(closing_maghrib_instant)` and exposes it as `WaqtResult.label_date`.

Normative details:

1. **The zone is the location's IANA zone** (or the caller's `timezone_override`), never a longitude-derived "solar" zone. At Kiritimati (UTC+14) or Apia (UTC+13) the civil date at Maghrib differs from the mean-solar date; the civil date is the label.
2. **The label date is a civil date; the solar-date key used to compute events is not**, and the second must never be used to label a day. Events stay keyed by their own upper transit (EVT-004, DR-0002).
3. **Consequence: labels are not one-to-one with civil dates near local midnight (DAY-009).** Where the closing Maghrib itself crosses civil midnight (high latitude in summer; a UTC-offset change), one civil date may be the label of **no** Waqt day and another of **two**. Real instances, Reykjavik 2026: Maghrib closes at 23:58:53 on 14 June and next at 00:00:09 on 16 June, so *15 June labels no day*; it closes at 00:00:16 and again at 23:59:04 on 29 June, so *29 June labels two days*. The rules are:
   - labels never decrease from one Waqt day to the next;
   - `gregorian_date_to_waqt_day(g)` when no day closes on `g` is **unresolved** (`resolved = false`; the `reason` text is not normative);
   - when two days close on `g` it returns the one that contains `g`'s local noon (here the later);
   - the weekday and Hijri date of both days that share a label are equal.
4. **What this section does not decide.** It fixes the *default* labelling rule. It does not claim that no regional convention could label differently; none is provided. A different rule would be a new configurable profile option proposed through `conformance/GOVERNANCE.md`, never a silent change to this one.

- `test_hijri_date_before_and_after_maghrib_differ`
- conformance vectors `label/*`, `label/skip/*`, `label/repeat/*` (requirements DAY-004, DAY-009)

## 4. Waqt Clock Time

`WaqtPosition` = elapsed SI time since the containing day's opening Maghrib, rendered `HH:MM:SS`. Ordinary hours, minutes, seconds — only the epoch (Maghrib, not midnight) and the day length (not fixed at 86,400s) differ from a conventional clock.

Because the day length varies, `hour` can legitimately reach or exceed 24 in the last minutes before the next Maghrib on a day that runs long. **This is represented, not clamped.** `WaqtPosition.hour` has no enforced upper bound; `display` renders it exactly (`"24:03:17"`).

- `test_position_display_has_no_enforced_hour_ceiling`
- `test_day_length_not_assumed_86400`
- Vector `london-long-day-near-24h-boundary`: a real day where `length_si_seconds > 86400`, with an instant placed inside that overflow window so `hour == 24` in the frozen expected output.

## 5. Event Positions

`EventPosition` pairs an event's absolute instant with its `WaqtPosition` **on the specific day it belongs to**. It cannot be constructed, compared, or reasoned about independent of a `WaqtDay` — this is enforced structurally (§7), not left as a convention a caller could violate by accident.

## 6. Durations vs. Positions vs. Instants

Exactly three kinds of temporal value exist, and they are never interchangeable:

| Type | Meaning | Representation |
|---|---|---|
| `WaqtInstant` | An absolute point in physical time | `datetime.datetime` |
| `Duration` | Elapsed SI time | `datetime.timedelta` |
| `WaqtPosition` | A position *within one specific `WaqtDay`* | hour/minute/second, meaningless without that day |

Neither `WaqtInstant` nor `Duration` gets a wrapper type — `datetime` and `timedelta` already are exactly those things, correctly. What *is* enforced is that a `WaqtPosition` can never silently stand in for a `Duration` across two different days (§7).

## 7. Comparison and Arithmetic

| Operation | Result |
|---|---|
| `instant − instant` | `Duration` (ordinary `datetime` subtraction) |
| `instant + Duration` | `instant` (ordinary `datetime` addition) |
| `WaqtDay.position_of(instant)` | `WaqtPosition` |
| `WaqtPosition.to_instant(day)` | `instant` (requires the *same* day the position came from) |
| `WaqtDay.event(name)` | `EventPosition` |
| `EventPosition` ordering | `<`, `<=` — **same-day only** |
| `crosses_maghrib(a, b, lat, lon)` | `bool` — do two instants fall in different `WaqtDay`s |

**The rule that matters most:** `WaqtPosition` and `EventPosition` comparison (`<`, `<=`) is only defined between values belonging to the *same* `WaqtDay` (same location, same opening Maghrib instant). Comparing across days or locations raises `IncomparableWaqtValuesError` — this was identified as a requirement as far back as the earliest Waqt design review ("Waqt timestamps from different locations MUST NOT be compared") and this module is where that sentence becomes enforced code.

Equality (`==`) is more forgiving by design: two positions from different days are simply `False`, not an error — only *ordering* across incompatible days is nonsensical enough to warrant an exception; a caller asking "are these the same" gets a sensible answer either way.

- `test_event_position_lt_within_same_day`
- `test_event_position_comparison_across_days_raises`
- `test_waqt_position_comparison_across_locations_raises`
- `test_waqt_position_equality_across_days_is_false_not_an_error`
- `test_position_to_instant_round_trip`
- `test_position_to_instant_wrong_day_raises`
- `test_crosses_maghrib_true_across_boundary_false_within_day`
- `test_crosses_maghrib_is_order_independent`

## 8. Undefined Events

Sprint 4 established structured `status: "UNDEFINED"` at the HTTP layer (polar day/night). This module extends it: any operation requiring a day boundary or event that doesn't exist raises `WaqtUndefinedError`, carrying the same `undefined_reason` string the HTTP layer already reports — never a silent `None`, never a generic exception from deep inside arithmetic.

Two distinct levels:
- **Day-level**: the day itself is `UNDEFINED` (Maghrib doesn't occur) — `position_of()`, `events()`, `event()` all raise.
- **Event-level**: the day is fine, but one specific event doesn't occur (e.g. Fajr at high latitude in summer, even though Maghrib/sunrise are fine) — `event(name)` raises for that name specifically; `events()` simply omits it from the list rather than raising, since "give me whatever's defined" and "give me this one specific thing" are different requests with different correct failure behavior.

- `test_undefined_day_position_of_raises_with_reason`
- `test_undefined_day_event_list_raises`
- `test_single_undefined_event_raises_but_other_events_still_work`
- `test_events_list_silently_omits_undefined_events_rather_than_raising`
- `test_crosses_maghrib_undefined_at_pole_raises`
- Vector `tromso-midsummer-undefined`

---

## Portable conformance vectors

`tests/vectors/waqt_vectors.json` — ten cases, every expected value computed by the reference implementation itself (`tests/vectors/generate_vectors.py`), never hand-typed. Covers: an ordinary instant, the exact-Maghrib boundary, one second before it, Makkah itself, a day that runs long enough to produce an `hour == 24` reading, a polar `UNDEFINED` case, the hardest available International Date Line case (Kiritimati), two Asr conventions on the same instant (differing only in the Asr event), and an elevation comparison.

`tests/test_vectors.py` loads this file and re-derives every value through the live implementation, asserting an exact match — both a regression test and proof the file is actually reproducible, which is the property an independent implementation in another language would need it to have. If a vector needs to change, re-run the generator and review the diff; never hand-edit the JSON.

---

## Sprint 6 addendum

Scheduling and deadlines are specified in [`SCHEDULING.md`](SCHEDULING.md). Two clarifications from it apply here: the closing Maghrib and Isha both fall in the *next* Waqt day under §2's half-open rule (so `EventPosition` for them reads at or beyond the listing day's length), and `crosses_maghrib()` is unchanged — it compares *instants*; interval semantics live in `waqt.scheduling.SchedulingEngine.classify_span`.
