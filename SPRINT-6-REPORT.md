# Sprint 6 Report — Islamic Scheduling & Deadline Engine

## Summary

Sprint 6 adds `waqt/scheduling/`, a temporal windows/deadlines layer over the
Sprint 1–5 stack, plus an HTTP surface (`/v1/schedule/*`), 116 portable
conformance vectors with embedded day tables, and an independent
zero-dependency JavaScript consumer that validates **both** the Sprint 5 and
Sprint 6 vector files. `waqt/core.py` and `waqt/solar.py` are byte-for-byte
unchanged (`md5sum` verified before and after). 320 Python tests pass; 133
JavaScript tests pass.

```
waqt/core.py       af88c5fdc13e99390597598586db9d73   (before == after)
waqt/solar.py       8002b2fb03de49ba0784528b766cb3f2   (before == after)
```

## What was built

**`waqt/scheduling/model.py`** — the declarative vocabulary. Eight point
types (`Instant`, `Anchor`, `Event`, `NextEvent`, `PrevEvent`, `Position`,
`Offset`, `Fraction`) and `Interval`, each carrying a `basis`
(`absolute_instant` / `astronomical_event` / `waqt_position` / `rule_derived`)
so the four kinds of deadline the brief distinguishes are explicit in every
result, not just in the code that builds them. A JSON parser
(`point_from_dict` / `interval_from_dict`) with a depth cap and a
`RuleError` for malformed input, so the same rule format drives Python
callers, the HTTP API, and the conformance vectors.

**`waqt/scheduling/context.py`** — `SchedulingContext` wraps `compute_waqt`
and never recomputes astronomy. `neighbor(day, k)` steps by instant (the next
day is the day containing this day's own close), so adjacent days tile the
timeline with no gap or overlap — proved in `test_days_tile_the_timeline`.
`day_to_table_entry` serializes a day to the flat structure the vector
generator and the HTTP layer both use.

**`waqt/scheduling/engine.py`** — `SchedulingEngine` resolves points and
intervals and answers the brief's questions directly: `day_bounds`, `until`,
`since`, `next_event`, `event_position`, `resolve_point`, `resolve_interval`,
`evaluate`, `check_deadline`, `classify_span`, `snapshot`. All derived
arithmetic is integer microseconds with one documented rounding rule
(`floor(x + 0.5)`), so Python and JavaScript agree exactly rather than "to
within a tolerance."

**`waqt/scheduling/ops.py`** — one JSON operation dispatcher
(`run_operation`) shared by the HTTP endpoint, the vector generator, and the
vector-consuming tests, so the three cannot drift apart.

**`waqt/api/schedule_endpoint.py`** — `GET /v1/schedule/snapshot`,
`GET /v1/schedule/span`, `POST /v1/schedule/resolve`. Additive: API version
moved `1.0.0` → `1.1.0`, all seven Sprint 5 endpoints and their tests are
unchanged. A new `INVALID_RULE` error code (400) is for a malformed
rule — distinct from a well-formed rule whose astronomy is undefined, which
is always a 200 with a structured `status`. Every response carries a
`caveat` field stating that Waqt provides temporal facts, not rulings.

**`tests/vectors/scheduling_vectors.json`** (116 vectors, generated, not
hand-typed, by `tests/vectors/generate_scheduling_vectors.py`) — each vector
embeds a **day table**: consecutive Waqt days with their events, frozen as
data. A consumer needs zero astronomy to validate a vector.

**`consumers/js/`** — the sprint's headline acceptance item. A ~600-line
zero-dependency Node package, written from `docs/SCHEDULING.md`, not
translated from the Python source (verified by mutation-testing the harness:
reverting the Maghrib day-shift, an inclusivity flag, or the span
end-treatment each breaks exactly the vectors that exercise it — 3, 3, and
1 respectively — and nothing else). It:
- reproduces all 116 scheduling vectors exactly;
- independently re-derives the *semantic* content of all 10 Sprint 5
  vectors (half-open membership, position arithmetic, `HH:MM:SS` display
  with no 24 h ceiling, event ordering, boundary tiling, Asr isolation,
  elevation effect, UNDEFINED shape) from their own frozen astronomical
  output, deliberately **not** recomputing sunrise/Maghrib from
  coordinates, since checking a table against its own answers would be
  circular.

This directly closes the gap the Sprint 5 report named: *"no implementation
outside Python has yet consumed the vectors."*

## Design decisions and why

**No presets for `suhoor()`/`iftar()`/etc.** The brief is explicit that Waqt
supplies primitives, not rulings. Every "application" example in the brief
(fasting, Suhoor, Iftar, prayer reminders, Ramadan schedules) is expressible
by composing `before`/`after`/`between`/`within`/`Offset`/`Fraction` — e.g. a
reminder "30 minutes before Maghrib" is `Offset(NextEvent("maghrib"), -1800)`
— without the library taking a position on which composition is correct.

**Maghrib and Isha both live in the next Waqt day.** Under the half-open
rule `[open, close)`, the closing Maghrib *is* the next day's `00:00:00`.
This was not obvious going in — a first draft treated only Isha as
day-shifted — but Sprint 5's own vectors already show it (Maghrib listed at
`23:59:23`, a length-`23:59:23` day) and 12-location/full-year property
tests confirmed it. `event_position` reports both the `listed` reading
(Sprint 5's convention) and the `containing` reading, since a scheduler
usually wants the latter but a UI displaying "today's five prayer times"
wants the former.

**Three undefined statuses, not one.** `EVENT_UNDEFINED` (a single point has
no answer), `WINDOW_UNDEFINED` (an interval has an undefined endpoint —
`causes` names it), `NO_VALID_WINDOW` (both endpoints exist but the interval
is empty or backwards). Collapsing these would have hidden the distinction
the brief explicitly asks for. `evaluate()` returns `inside: null` — not
`false` — when the window is undefined, so "we don't know" is never silently
read as "no."

**`on_undefined: "skip"` is opt-in and self-reporting.** The default
(`strict`) never invents a time. `skip` exists because some applications
legitimately want "the next Fajr that occurs, whenever that is" at high
latitude, but it must say what it skipped (`skipped: [...]`) rather than
quietly jumping weeks ahead.

**`crosses_maghrib()` is untouched; `classify_span()` is new.** The Sprint 5
function answers "do two *instants* belong to different Waqt days?", which
remains the right question for its callers. A scheduler asks a related but
different question about an *interval*: does it *cross* a boundary. The two
disagree exactly at the boundary instant (ending *at* Maghrib crosses under
the instant-pair reading, but a half-open span never reaches its own end) —
`classify_span(..., end_inclusive=True)` reproduces `crosses_maghrib()`
exactly (tested), and the default half-open reading is what "an interval
crossing Maghrib" in the brief's test-target list actually needs. Civil
midnight is reported as a separate, independent fact
(`crosses_civil_midnight`), since the brief's own `23:30 → 00:30` example
crosses civil midnight without necessarily crossing Maghrib.

**Calendar independence is structurally enforced, not just tested.** Beyond
the substitution test (three providers, one asserted-identical day table
modulo the label, one asserted-identical set of results), a test walks
`waqt/scheduling/*.py` and fails if any file outside the one designated
display helper ever branches on `hijri_label`/`hijri_date`.

## Test coverage

| Suite | Count |
|---|---|
| `tests/test_scheduling.py` | 83 (unit-level: windows, deadlines, undefined statuses, spans, profiles, calendar substitution, rule parsing) |
| `tests/test_scheduling_vectors.py` | 119 (116 vectors × regression + 3 structural, plus invokes the JS suite as a subprocess when Node is present) |
| `tests/test_schedule_api.py` | 10 (HTTP surface, error codes, envelope shape) |
| **New Python total** | **212** (Sprint 5's 106 → **320**) |
| `consumers/js` (`npm test`) | 133 (10 Sprint 5 + 116 Sprint 6 vectors + 4 cross-vector properties + 3 harness self-checks) |

All of the brief's named test targets are covered by name in
`tests/test_scheduling.py` and by id in `scheduling_vectors.json` (e.g.
`window-before-next-maghrib`, `window-maghrib-to-isha`,
`span-crosses-maghrib`, `span-ends-exactly-at-maghrib`,
`profile-asr-hanafi-*`, `calendar-umm-al-qura-*`).

## Definition of Done — checklist

- [x] Temporal windows with explicit start/end and/or event references
- [x] Deadline semantics distinguishing the four bases
- [x] Generic relative-rule primitives (`before`/`after`/`between`/`within`/`until_next`), no hard-coded applications
- [x] Scheduling across Maghrib (`classify_span`), `crosses_maghrib()` re-examined and left as-is with rationale
- [x] Explicit `EVENT_UNDEFINED` / `WINDOW_UNDEFINED` / `NO_VALID_WINDOW`, never an invented time
- [x] Calendar-independent: provider swap changes labels only (tested + structurally enforced)
- [x] Portable test vectors (116, generated, with embedded day tables)
- [x] Independent non-Python consumer validating the *existing* Waqt conformance vectors — **and** the new scheduling vectors
- [x] Core Time Model / solar engine unmodified (md5-verified)

## Honest limitations

- The JS consumer checks Sprint 5's *semantic* claims from the vectors'
  own frozen astronomical output; it does not recompute sunrise/Maghrib
  from coordinates. Doing so would need an independent solar-position
  implementation, which is a larger undertaking the Sprint 5 report
  scoped as future work, not this sprint's ask.
- `on_undefined="skip"`'s lookahead is capped at 8 day-slots — enough for
  every real high-latitude transition tested, but it is a documented,
  finite bound rather than "search forever."
- `classify_span` caps at 400 Waqt days for the same reason; nothing in
  the brief calls for open-ended spans.
