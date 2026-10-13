# Sprint 7 Report — Institutional Islamic Calendar Semantics

## Summary

Sprint 7 adds `waqt/institutional/` — a formal, executable institutional
calendar layer (Islamic week, configurable fiscal year, configurable
academic year, calendar profiles) — over the Sprint 1–6 stack, plus an HTTP
surface (`/v1/institutional/*`), 22 portable conformance vectors with
embedded Hijri calendar tables (no astronomy needed to consume), and an
independent zero-dependency JavaScript consumer that validates them.
`waqt/core.py` and `waqt/solar.py` are byte-for-byte unchanged (`md5sum`
verified before and after), and so are `waqt/scheduling/`, `waqt/semantics.py`,
`waqt/hijri.py`, and `waqt/calendar_providers/` (confirmed by diffing against
the Sprint 6 delivery). 406 Python tests pass; 159 JavaScript tests pass.

```
waqt/core.py       af88c5fdc13e99390597598586db9d73   (before == after)
waqt/solar.py       8002b2fb03de49ba0784528b766cb3f2   (before == after)
```

## What was built

**`waqt/institutional/rules.py`** — the shared vocabulary every other module
is built from: `MonthDay` (the brief's "Muharram 1"), `MonthEnd` (the
brief's "Dhul Hijjah 29/30"), `NthWeekdayOfMonth` (the brief's "First Ahad
of Muharram" / "Last Khamis of Sha'ban", `n=1`/`n=-1`, but general enough for
any `n`). All three are small frozen dataclasses with `to_dict()`/
`rule_from_dict()`, JSON round-trip, and resolve through `month_days()`,
which probes days 1–30 of a Hijri month and keeps only the ones that
round-trip through the provider's own `from_gregorian(to_gregorian(...))` —
the same defensive check `waqt/calendar_providers/` already applies
elsewhere, so a provider that silently normalizes an out-of-range day can
never manufacture a 31st day. Resolving any rule needs nothing but a
`HijriProvider` — **no location, no astronomy** — because a calendar date is
the same fact for every observer on Earth, exactly like `weekday_name`
itself.

**`waqt/institutional/week.py`** — `WeekDefinition` (which day starts the
week, which slot is Jumu'ah, both configurable, defaulting to `al-Ahad` /
`al-Jumuah`) and `WeekView` (seven tiled `WaqtDay`s at a real location).
Answers every question the brief poses about the week explicitly in its
module docstring (reproduced in `docs/INSTITUTIONAL.md` §3), and states the
central claim as a tested contract rather than an implicit consequence:
`test_jumuah_waqtday_opens_at_thursday_evening_maghrib` proves, against real
solar output at a real location, that the WaqtDay labeled `al-Jumuah` opens
at the previous evening's — Thursday's — Maghrib. This was already true of
`core.compute_waqt` since Sprint 1 (the brief itself says prior sprints
"already explicitly handle the weekday shift"); Sprint 7 formalizes it,
names it, and tests it. `week_dates()` is pure Gregorian-civil-date
arithmetic needing no provider and no location at all — proven by the fact
that every `week` vector in `institutional_vectors.json` carries an empty
`context`.

**`waqt/institutional/fiscal_year.py`** — the brief's exact shape:
`FiscalCalendar(start_rule, end_rule, label, calendar_provider)`.
`default_islamic_fiscal_calendar()` is the brief's own worked example
(`1 Muharram` → `end of Dhu al-Hijjah`) offered as a convenience default,
never assumed elsewhere; any institution builds its own `FiscalCalendar`
with different rules (even a different provider) and gets identical
guarantees, including rejection (`RuleError`, HTTP 422) when a resolved end
precedes its resolved start.

**`waqt/institutional/academic_year.py`** — the brief's exact shape:
`AcademicCalendar(opening_rule, closing_rule, term_rules, holidays)`.
`default_islamic_academic_calendar()` is the brief's own example (first Ahad
of Muharram → last Khamis of Sha'ban) with **no** terms and **no** holidays —
deliberately, since the brief explicitly warns against baking in one
universal Muslim school calendar. `sample_two_term_academic_calendar()`
exists only in tests/docs, clearly labeled "illustrative only, not a
default", to demonstrate the `term_rules` shape without the library taking a
position on it.

**`waqt/institutional/binding.py`** — the one place this layer touches
`SchedulingContext`: `waqt_day_for_gregorian_date(ctx, g)` finds the real
`WaqtDay` a resolved calendar date labels, so a fiscal or academic year
boundary can carry a real Maghrib-anchored instant when a location is
supplied. Entirely optional — every calendar computation in this sprint
works with no location — and it recomputes no astronomy of its own; it
reuses `SchedulingContext.day_containing`, Sprint 6's already-proven
day-bracketing.

**`waqt/institutional/profile.py`** — `CalendarProfile`, the brief's exact
shape (`name`, `calendar_provider`, `week_definition`,
`fiscal_year_definition`, `academic_year_definition`, `timezone_policy`,
`labeling_rules`), a plain frozen dataclass, pure data — nothing in
`waqt/core.py`, `waqt/solar.py`, or `waqt/scheduling/` reads one. Round-trips
to/from JSON, and rejects (at construction time) a profile whose
fiscal/academic definitions use a different `calendar_provider` object than
the profile's own.

**`waqt/api/institutional_endpoint.py`** —
`GET /v1/institutional/week`, `GET`/`POST /v1/institutional/fiscal-year(/resolve)`,
`GET`/`POST /v1/institutional/academic-year(/resolve)`,
`GET /v1/institutional/profile`. Additive: API version moved `1.1.0` →
`1.2.0`; every Sprint 5/6 endpoint and its tests are unchanged. A new
`INVALID_CALENDAR_RULE` error code (422) covers both a malformed rule and a
well-formed rule whose location-binding cannot resolve (there is no partial
"calendar facts only" fallback here the way scheduling's snapshot endpoint
has one, since the binding was the entire reason a location was supplied).
Every response carries a `caveat` field, matching Sprint 6's convention:
Waqt states calendar facts, not institutional obligations.

**`tests/vectors/institutional_vectors.json`** (22 vectors, generated, not
hand-typed, by `tests/vectors/generate_institutional_vectors.py`) — each
vector freezes a **calendar table** (every day of every Hijri month its
operation touches, as `{day, gregorian, weekday}` triples) instead of a
solar day table, since this layer's arithmetic needs no astronomy at all. A
consumer needs zero Hijri arithmetic to validate a vector — only the rule
semantics in `docs/INSTITUTIONAL.md`.

**`consumers/js/src/institutional.mjs`** — a from-scratch, ~110-line,
zero-dependency JavaScript implementation of the rule/week/fiscal-year/
academic-year semantics, sharing no code with `waqt/institutional/`. It:
- reproduces all 22 institutional vectors exactly, from their own frozen
  calendar tables;
- computes the Islamic weekday of any date independently, using nothing but
  `Date.prototype.getUTCDay()` (which is already Sunday=0..Saturday=6, the
  same order `ISLAMIC_WEEKDAY_NAMES` uses) — no table, no Python-derived
  data;
- is checked against a deliberately corrupted vector to confirm the
  comparison is not vacuous.

`cd consumers/js && npm test` now runs 159 tests total (133 Sprint 5/6 +
26 Sprint 7); `tests/test_institutional_vectors.py` also invokes it as a
subprocess when Node is present, the same pattern Sprint 6 established.

## Design decisions and why

**Calendar arithmetic needs no astronomy, on purpose.** The brief's
architecture diagram places the institutional layer above scheduling
primitives, which are themselves built on astronomical events. It would
have been easy to route every week/fiscal-year/academic-year computation
through a `SchedulingContext` "for consistency." Instead, `rules.py` and the
core of `week.py`/`fiscal_year.py`/`academic_year.py` depend on nothing but
a `HijriProvider` — because a calendar convention like "1 Muharram" or "the
first Ahad of Muharram" is the same fact everywhere on Earth, exactly the
way `waqt.hijri.weekday_name` already is. Binding a resolved date to a real
Maghrib instant at a real place (`binding.py`) is kept as a clearly separate,
optional last step, which is also why every fiscal/academic-year result
distinguishes calendar-fact fields (always present) from `waqt_*` fields
(present only if a location was supplied).

**No universal fiscal or academic calendar is shipped as the default an
application quietly inherits.** `default_islamic_fiscal_calendar()` and
`default_islamic_academic_calendar()` exist only because the brief itself
gives worked examples and it would be perverse not to offer them — but
`sample_two_term_academic_calendar()`, the one example with `term_rules`
filled in, is explicitly named and documented as illustrative, and nothing
in the package imports it. A real institution is expected to build its own
`FiscalCalendar`/`AcademicCalendar` from `rules.py`'s primitives.

**Weeks are calendar-independent; fiscal/academic years are not — and that
asymmetry is deliberate, not an inconsistency.** Sprint 6 proved swapping a
`HijriProvider` changes only display labels, never a scheduling result.
Sprint 7's week module keeps that property (it needs no provider at all).
But a fiscal or academic year's *actual boundary dates* legitimately change
across providers, because two Hijri calendar providers can disagree about
which Gregorian date is "1 Muharram" in the first place — this is exactly
what the brief means by "the Hijri provider should determine the actual
date; the fiscal-calendar layer should determine the institutional
structure." `TestFiscalYear.test_calendar_provider_changes_the_actual_dates_not_just_a_label`
names this explicitly so it is never later mistaken for a Sprint 6-style
regression.

**`RuleError`, not a silent best guess, for every calendar mistake.** An
out-of-range month, an unknown weekday name, an `n` with no matching
occurrence, an end rule resolving before its start rule, a fiscal/academic
boundary falling on an undefined Waqt day at a supplied location — all raise
`RuleError` (400/422 over HTTP), the same posture Sprint 6 took toward
malformed scheduling rules. Nothing in this layer invents a date.

**`CalendarProfile` is inert.** It is deliberately not consulted by any
algorithm in this package or any prior sprint — it is a config object an
*application* holds and passes explicitly to `FiscalCalendar.year()` /
`AcademicCalendar.year()` / `week_containing()` itself. This matches the
brief's instruction that profiles "should be data/configuration, not buried
in the core algorithms" as literally as possible: there is no hidden global
"current profile" anywhere in `waqt/`.

## Test coverage

| Suite | Count |
|---|---|
| `tests/test_institutional.py` | 32 (unit-level: week, fiscal year, academic year, profile, architecture separation) |
| `tests/test_institutional_vectors.py` | 43 (22 vectors × regression + 18 month-table completeness checks + 3 structural, one of which invokes the JS suite as a subprocess when Node is present) |
| `tests/test_institutional_api.py` | 11 (HTTP surface, error codes, envelope shape) |
| **New Python total** | **86** (Sprint 6's 320 → **406** — note: 1 existing Sprint 6 assertion in `tests/test_api.py` was updated for the additive `1.1.0` → `1.2.0` API version bump, nothing else in the pre-existing suite changed) |
| `consumers/js` (`npm test`) | 159 (133 Sprint 5/6 + 26 Sprint 7 vectors, weekday checks, and a corrupted-vector self-check) |

## Definition of Done — checklist

- [x] Islamic week, formalized: first day, Jumu'ah slot, boundary rule, and
      the intrinsic-fact-vs-derived-convention distinction, all explicit
      (`waqt/institutional/week.py`, `docs/INSTITUTIONAL.md` §3)
- [x] Islamic fiscal year: generic `FiscalCalendar(start_rule, end_rule,
      label, calendar_provider)`, not hard-coded to Muharram→Dhu al-Hijjah
      (that is one named default among arbitrarily many)
- [x] Islamic academic year: generic `AcademicCalendar(opening_rule,
      closing_rule, term_rules, holidays)`, with exactly one clearly-labeled
      illustrative example, never a universal default
- [x] `CalendarProfile` as explicit, swappable, JSON-serializable
      configuration — never buried in core algorithms
- [x] Each calendar structure has executable semantics (Python), API
      representation (`/v1/institutional/*`), portable test vectors (22,
      generated), and an independently-validated consumer (JS)
- [x] Core Time Model / solar engine unmodified (md5-verified); `waqt/
      scheduling/`, `waqt/semantics.py`, `waqt/hijri.py`,
      `waqt/calendar_providers/` unmodified (diff-verified against the
      Sprint 6 delivery)
- [x] Second astronomy implementation put on the roadmap, not attempted
      here and not silently deferred — see Honest limitations

## Honest limitations

- **The "second, independent astronomy implementation" this sprint's brief
  says not to postpone forever is still not built.** It remains explicitly
  out of scope for Sprint 7 (which needs no astronomy at all — see Design
  decisions), and is carried forward as its own parallel milestone, not
  folded into either Sprint 7 or silently dropped.
- **`binding.py`'s location-to-WaqtDay lookup probes local noon (UTC).**
  This is safe for every non-polar location and every timezone offset up to
  +/-12h, since Maghrib never falls before local dawn or after local
  midnight — but it is a deliberate approximation, not a general "instant
  for civil date g" solver, and it is not proven for a jurisdiction using a
  timezone many hours removed from its actual geography. No such case
  exists in this project's test matrix.
- **`term_rules`/`holidays` resolve against the academic year's own Hijri
  year plus an integer `year_offset`,** not an arbitrary independent year
  per sub-rule. Every case in this sprint's tests and vectors fits that
  model; an institution whose term genuinely spans a Hijri year boundary in
  a way `year_offset` can't express would need to call `.year()` twice and
  splice the results itself.
- **`month_days()`/`gregorian_weekday_of()` are O(month length) per
  resolution** (a probe-and-round-trip over up to 30 days). Fast enough for
  interactive use; an application resolving many fiscal/academic years per
  request should cache `FiscalCalendar.year()`/`AcademicCalendar.year()`
  results itself, the same caching responsibility Sprint 6 placed on
  callers of the scheduling engine.
- **Calendar-provider disagreement in fiscal/academic-year boundary dates is
  real and by design** (see Design decisions) — not a defect, but worth
  restating here since it is the one place this sprint's guarantees are
  weaker than Sprint 6's calendar-independence property, and a caller
  comparing two providers' fiscal years should expect that difference.
