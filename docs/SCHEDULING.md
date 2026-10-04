# Waqt Scheduling & Deadlines (Sprint 6)

The specification `waqt/scheduling/` implements. It sits **above** `SEMANTICS.md`: it adds no astronomy, no calendar dependence and no new clock. It lets an application *write down* an Islamic temporal rule precisely and evaluate it reproducibly.

## 1. What this layer does — and does not — claim

Everything here is temporal arithmetic over astronomical facts. **None of it is a religious ruling.** `Event("fajr")` means "the instant the configured profile's depression angle is reached", not "fasting begins now". Whether an application should use Fajr, Fajr minus a safety margin, or sunrise; what bounds "the night"; what "a third of the night" means — those are decisions for a scholar or institution. This layer lets them state the decision exactly. That is why there are **no presets** such as `suhoor()` or `iftar()`: the primitives compose into them, and the composition is the caller's to own.

Every HTTP response from `/v1/schedule/*` carries a `caveat` field saying so.

## 2. The four kinds of point

Resolving a point always reports its `basis`:

| basis | Point types | Meaning |
|---|---|---|
| `absolute_instant` | `instant`, `anchor` | A UTC instant supplied by the caller |
| `astronomical_event` | `event`, `next_event`, `prev_event` | An instant produced by the solar engine |
| `waqt_position` | `position` | *N* SI seconds after a Waqt day's opening Maghrib |
| `rule_derived` | `offset`, `fraction` | Computed from other points; `depends_on` lists the leaf bases |

## 3. Event slots — the one subtle thing

`Event(name, day=k)` is the event **as listed on** the Waqt day *k* places from the anchor's day (0 = the day containing the anchor). Containment follows the half-open rule `[open, close)` from `SEMANTICS.md` §2, which has a consequence worth stating outright:

| event | occurs in |
|---|---|
| `fajr`, `sunrise`, `dhuhr`, `asr` | its listed day |
| `maghrib` (= `day_end`) | the **next** day — the closing Maghrib is that day's `00:00:00` |
| `isha` | the **next** day (it follows that Maghrib) |
| `day_start` | its listed day (the opening Maghrib) |

Sprint 5's vectors already show this (Maghrib listed at `23:59:23`, Isha at `25:04:53` on a `23:59:23` day — figures as captured in Sprint 5 under engine revision 1 and not re-measured since; the example pinned by a passing test today is the next sentence's `25:04:55` / `01:05:31`). It matters for scheduling because `[Maghrib, Isha)` straddles a Waqt-day boundary by construction. `event_position` therefore reports **both** readings: `listed` (Sprint 5's `EventPosition`) and `containing` (the day that holds the instant). At Addis, Isha is `25:04:55` listed and `01:05:31` containing.

`next_event`/`prev_event` search occurrences (not slots) and are what you want for "the next Maghrib" — see §5.

## 4. Windows

An `interval` has a `start` and `end` point (either may be `null` = unbounded), and defaults to half-open `[start, end)` — the same convention as a Waqt day.

| Primitive | Meaning |
|---|---|
| `between(a, b)` | `[a, b)` |
| `before(p)` | `t < p` |
| `after(p)` | `t >= p` — at the exact instant of `p` the new period has begun |
| `within(p, seconds)` | `[p, p+seconds)` — "within N Waqt hours after an event" |
| `within_day(k)` | `[day_start, day_end)` — the Waqt day |
| `until_next(name)` | `[anchor, next occurrence of name)` |

A Waqt hour is an SI hour (`TIME-MODEL.md`), so N Waqt hours = `3600·N` seconds; the JSON `offset` accepts `waqt_hours` as sugar.

`Fraction(a, b, f)` is the point `f` of the way from `a` to `b`. "Last third of the night" is `Fraction(maghrib, fajr(+1), 2/3)` — *which* events bound the night is yours to choose.

**Anchor.** Day-relative and Next/Prev references resolve against an *anchor* instant. `evaluate(rule, t)` defaults the anchor to `t`; for rules built from `next_event`/`prev_event`/`anchor` pass a fixed anchor, or the window slides along with the instant you test. At the exact instant of Maghrib the anchor's day flips to the new day, so `Event("maghrib")` means the *following* Maghrib unless the anchor is held fixed.

## 5. Deadlines

`check_deadline(point, anchor, now)` returns `state`: `pending` (`now < deadline`), `reached` (`==`), `passed` (`>`), plus signed `remaining_seconds`. Deadlines may be an instant, an event, `Position`, `Offset(event, d)` or `day_end`.

`until(name, t)` / `since(name, t)`: inclusive occurrence search — `0` at the exact event. Looking back from 00:30 into a Waqt day, the last Isha is the *previous* evening's (slot −2 in listing terms); immediately after Maghrib the next Isha is *tonight's*, not tomorrow's.

## 6. Undefined astronomy — three distinct statuses

| Status | Applies to | Meaning |
|---|---|---|
| `EVENT_UNDEFINED` | a point | The event does not occur (`cause: EVENT_UNDEFINED_ON_DAY`), the Waqt day is undefined (`DAY_UNDEFINED`, polar day/night), or a search found none (`NO_OCCURRENCE_IN_RANGE`). `undefined_ref` names it, e.g. `fajr@day+0`. |
| `WINDOW_UNDEFINED` | an interval / span | ≥1 endpoint is `EVENT_UNDEFINED`; the failing endpoint results are attached as `causes`. |
| `NO_VALID_WINDOW` | an interval / span | Both endpoints exist but bound nothing: end before start, or `start == end` without both ends inclusive. |

`evaluate` reports `inside: null` — *unknown*, not `false` — whenever the window is not `OK`.

**Policy.** `on_undefined: "strict"` (default) reports `EVENT_UNDEFINED`. `"skip"` is an explicit opt-in that continues to the next day the event occurs and **reports every skipped slot** in `skipped`; it examines at most 8 day-slots. Nothing ever substitutes an "approximate" time (no 60°-latitude or angle-based fallbacks). An undefined event on an *irrelevant* day does not poison an answer: looking for the next Fajr ignores yesterday's.

Stepping from a defined day *into* an undefined one returns that day; stepping *through* one is `DAY_UNDEFINED`.

## 7. Spans across Maghrib

`classify_span(start, end, end_inclusive=false)` — for a half-open span:

- crosses Maghrib iff a Maghrib `M` satisfies `start < M < end`;
- ending exactly at Maghrib stays in one Waqt day; starting exactly at it lies wholly in the day it opens;
- `end_inclusive=true` is the *instant-pair* reading and agrees exactly with Sprint 5's `crosses_maghrib(a, b)`.

`crosses_maghrib()` itself is **unchanged**. It answers "do two *instants* belong to different days?", which is correct as it stands; the new function answers the different question a scheduler asks about an *interval*. The Sprint 5 report's follow-up — exposing which day each end falls in — is delivered: `start_day`, `end_day`, `maghrib_boundaries` (every boundary, for multi-day spans), `waqt_days_touched`.

**Civil midnight is not a Waqt boundary.** `crosses_civil_midnight` is reported independently: 23:30→00:30 local crosses civil midnight but is one Waqt day; 17:30→19:30 crosses Maghrib but not civil midnight.

## 8. Operations (HTTP and vectors share this format)

`{"op": …}` — `resolve_point`, `resolve_interval`, `evaluate`, `check_deadline`, `until`, `since`, `next_event`, `event_position`, `day_bounds`, `classify_span`. Point types: `instant`, `anchor`, `event`, `next_event`, `prev_event`, `position`, `offset`, `fraction`. See `waqt/scheduling/ops.py` and `tests/vectors/scheduling_vectors.json` for worked examples of each.

```json
{"op": "resolve_interval", "interval": {"type": "interval",
  "start": {"type": "event", "name": "maghrib", "day": 0},
  "end":   {"type": "offset", "base": {"type": "event", "name": "maghrib"}, "waqt_hours": 2}}}
```

*Illustrative compositions* (not rulings): `between(fajr, maghrib)` — a daytime window; `Offset(next maghrib, −30 min)` — a reminder 30 minutes before Maghrib.

## 9. Portable conformance (`tests/vectors/scheduling_vectors.json`)

116 vectors, each with a **day table**: consecutive Waqt days (open, close, six events or `null`) exactly as the Python solar engine produced them. An implementation reads the table and applies §2–§7 — no astronomy needed. Compare `expected` exactly, ignoring only the prose fields `description` and `reason`.

Exactness rules: instants are ISO 8601 UTC with ≤ microsecond precision. Derived instants are computed in **integer microseconds**; a real-valued amount `x` becomes `floor(x + 0.5)` (half-up). Durations are `(b_µs − a_µs) / 1e6`. Fraction: `a + floor((b−a)·f + 0.5)`.

`consumers/js/` is an independent, zero-dependency Node implementation. It passes all 116 scheduling vectors **and** verifies the ten Sprint 5 vectors' semantics (day membership, positions, display without an hour ceiling, event ordering, boundary tiling, Asr isolation). It does not recompute astronomy from latitude/longitude; doing so from a table of the engine's own answers would be circular. Run: `cd consumers/js && npm test`.

## 10. Calendar independence

The Hijri provider is passed through to `compute_waqt` only because it labels each Waqt day. Nothing in `waqt/scheduling` reads that label to decide anything; it is copied into results for display. Tests swap `arithmetic-tabular`, `umm-al-qura` and a shifted custom provider: labels change, no instant, window, span or status does — in Python, over HTTP, and in the JavaScript consumer. A structural test fails if scheduling code ever branches on a label.

## 11. Rules that previously lived only in the vectors (contract 2.0.0, DR-0008)

Sprint 15 measured that a clean-room implementation written from this document alone passed 108 of 116 scheduling vectors; the other 8 failures were rules stated nowhere in prose. They are now written down, each as a requirement bound to the existing vectors:

- **SCH-009 `inclusive`.** `next_event` and `prev_event` points carry `inclusive` (default `true`). At an anchor exactly equal to the event instant, inclusive resolves to that event; exclusive resolves to the next (for `prev_event`, the previous) one.
- **SCH-010 default slot of `event_position`.** For `isha` and `maghrib` the default slot is the *previous* listing; for every other event it is day 0. The result reports both the `listed` position and the `containing` position (`day_relative_to_listed`).
- **SCH-011 empty windows.** An empty or inverted window or span has status `NO_VALID_WINDOW` and `duration_seconds = null`. A window that touches an undefined day is `WINDOW_UNDEFINED` with `maghrib_boundaries = []`.
- **SCH-012 undefined slots.** A *strict* resolution (the default) that meets an undefined event slot ends as `EVENT_UNDEFINED` with cause `EVENT_UNDEFINED_ON_DAY` and names the slot in `undefined_ref`. With `on_undefined: "skip"` the slot is recorded in `skipped` and the scan continues over at most 8 day-slots, ending in `NO_OCCURRENCE_IN_RANGE` if nothing is found.
- **SCH-013 stepping through an undefined day.** An event point at a day offset whose Waqt day, or a day stepped across to reach it, has an undefined bounding Maghrib is `EVENT_UNDEFINED` with cause `DAY_UNDEFINED`, even when the target lies outside the context's day table.

`next_event` of `/v1/waqt` follows the same *occurrence* model as the scheduling layer (EVT-007, DR-0003): the earliest event strictly after the instant, including the previous solar day's Isha.

