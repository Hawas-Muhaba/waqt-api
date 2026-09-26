# Waqt Institutional Calendars (Sprint 7)

The specification `waqt/institutional/` implements. It sits **above** `SCHEDULING.md`, which sits above `SEMANTICS.md`, which sits above the Core Time Model:

```
Waqt Core            -> astronomical events -> Waqt dates -> temporal semantics
Scheduling            -> windows, deadlines, event-relative rules            (Sprint 6)
Institutional layer    -> week, fiscal year, academic year, terms, periods   (Sprint 7, this document)
```

Sprint 7 adds no astronomy and changes neither `waqt/core.py` nor `waqt/solar.py` (verified byte-for-byte in every test run — see `tests/test_institutional.py::TestArchitecture`). `waqt/scheduling/`, `waqt/semantics.py`, `waqt/hijri.py` and `waqt/calendar_providers/` are likewise unmodified.

## 1. What this layer does — and does not — claim

A calendar **rule** ("1 Muharram", "the last Khamis of Sha'ban", "start of the fiscal year") is calendar arithmetic: given a Hijri year and a `HijriProvider`, it resolves to one specific date, reproducibly, for every observer on Earth. **Whether an institution should adopt that rule is not this layer's decision.** There is no built-in "the" Islamic fiscal year or "the" Muslim school calendar — see §3 and §4. Every rule an application uses is one it (or its configuration) chose explicitly, in the open, as data.

Every HTTP response from `/v1/institutional/*` carries a `caveat` field saying so, matching Sprint 6's `/v1/schedule/*` convention.

## 2. Calendar rules — the shared vocabulary

Three primitives (`waqt/institutional/rules.py`), each a small JSON-serializable object:

| Rule | Meaning | Example |
|---|---|---|
| `month_day` | The Nth day of a Hijri month | `{month: 1, day: 1}` = 1 Muharram |
| `month_end` | The last day of a Hijri month (29 or 30, whichever the provider actually produces) | `{month: 12}` = end of Dhu al-Hijjah |
| `nth_weekday_of_month` | The n-th occurrence of an Islamic weekday in a Hijri month; `n=1` first, `n=-1` last | `{weekday: "al-Ahad", n: 1, month: 1}` = first Ahad of Muharram |

`month_days(provider, year, month)` — the function every rule resolves through — probes days 1..30 and keeps only the ones that **round-trip**: `from_gregorian(to_gregorian(y, m, d)) == (y, m, d)`. This means a provider whose `to_gregorian` silently normalizes an out-of-range day into the next month can never produce a phantom 31st day; the same defensive posture `waqt/calendar_providers/` already uses elsewhere in this project.

Resolving a rule requires an **invertible** `HijriProvider` (one with `to_gregorian`). Both providers this project ships (`ArithmeticTabularProvider`, `UmmAlQuraProvider`) qualify; a purely observational provider (moon-sighting reports with no forward table) would not, and `month_days` raises `RuleError` rather than guessing.

## 3. Islamic week

Formalized in `waqt/institutional/week.py`. Directly answering the brief's own questions:

- **What is a week?** Seven consecutive `WaqtDay`s — no more, no gap, no overlap, because it is built entirely from `SchedulingContext.neighbor()` stepping (Sprint 6), which already tiles the timeline exactly.
- **What is its first day?** Not a Waqt fact — an institutional choice (`WeekDefinition.first_day`). Default `"al-Ahad"` (Sunday), but a Monday-first `WeekDefinition` works identically.
- **How does it relate to Maghrib-based Waqt dates?** Each of the seven days IS a Waqt day, `[Maghrib(D), Maghrib(D+1))`, already labeled with an Islamic weekday name by `waqt.hijri.weekday_name` (unchanged since Sprint 1). A week is seven such labels in a row.
- **How is Jumu'ah represented?** `WeekDefinition.jumuah_day` (default `"al-Jumuah"`), resolved via `WeekView.jumuah`. Its opening Maghrib **is, provably**, the closing Maghrib of the WaqtDay labeled `al-Khamis` immediately before it — because the WaqtDay labeled "al-Jumuah" is (by definition of `weekday_name`) the one whose *closing* Gregorian date is a Friday, so its *opening* Maghrib is the previous evening: Thursday. `test_jumuah_waqtday_opens_at_thursday_evening_maghrib` checks this against real solar output at a real place, and `docs/CALENDARS.md`-style vectors are not needed because it follows from day tiling alone.
- **How are week boundaries determined?** The week's start is the WaqtDay labeled `first_day`'s opening Maghrib; the week's end is the closing Maghrib of the day before `first_day`, i.e. exactly seven WaqtDays later.
- **Is the week an intrinsic Waqt property or a derived calendar convention?** **Derived.** The only intrinsic fact is the single per-day weekday label the Core Time Model already produces. Grouping seven into a week, and choosing which one starts it, is institutional convention — kept entirely out of `waqt/core.py`.

Two entry points:

- `week_dates(date, defn) -> list[date]` — pure Gregorian-civil-date arithmetic, **no Hijri provider and no location needed at all**. This is why the week vectors in `institutional_vectors.json` carry an empty `context`.
- `week_containing(ctx, instant, defn) -> WeekView` — the same computation bound to a real `SchedulingContext`, giving seven actual `WaqtDay`s with real Maghrib instants.

## 4. Islamic fiscal year

`waqt/institutional/fiscal_year.py`. Per the brief:

```
FiscalCalendar:
    start_rule
    end_rule
    label
    calendar_provider
```

`FiscalCalendar(start_rule, end_rule, label, calendar_provider).year(hijri_year, provider=None, ctx=None)` resolves both rules against `hijri_year` and returns a `FiscalYear` with:

- `start_hijri` / `end_hijri` / `start_gregorian` / `end_gregorian` — always present, need no location.
- `waqt_start_open` / `waqt_end_close` — present only if a `SchedulingContext` (`ctx`) was supplied: the real opening/closing Maghrib instants at that location, via `waqt/institutional/binding.py`.

`default_islamic_fiscal_calendar()` gives exactly the brief's worked example — `start = month_day(1, 1)` (1 Muharram), `end = month_end(12)` (end of Dhu al-Hijjah) — as a convenience, never assumed elsewhere in the package. Building a completely different `FiscalCalendar` (a different start/end rule, even a different provider) works identically; `TestFiscalYear.test_fiscal_year_is_configurable_not_hardcoded` builds one starting at the first Ahad of Rajab.

An end rule that resolves **before** the start rule for the same year raises `RuleError` (a caller mistake — HTTP 422 `INVALID_CALENDAR_RULE`) rather than silently producing a negative-length fiscal year.

## 5. Islamic academic / school year

`waqt/institutional/academic_year.py`. Per the brief:

```
AcademicCalendar:
    opening_rule
    closing_rule
    term_rules
    holidays
```

`AcademicCalendar.year(hijri_year, ...)` returns an `AcademicYear` with resolved `opening`/`closing`, plus lists of resolved `terms` (`TermPeriod`) and `holidays` (`HolidayInstance`) — each a `(label, start_rule, end_rule)` or `(label, rule)` the caller supplied.

`default_islamic_academic_calendar()` is the brief's own example: `opening = nth_weekday_of_month(al-Ahad, n=1, month=1)` (first Ahad of Muharram), `closing = nth_weekday_of_month(al-Khamis, n=-1, month=8)` (last Khamis of Sha'ban) — **with no terms and no holidays**. That is deliberate: the brief explicitly says not to define one universal Muslim school calendar, so the shipped default only fixes the shape the brief names, and leaves everything else to the caller.

`sample_two_term_academic_calendar()` exists **only** in tests and docs to demonstrate the `term_rules` shape (two terms splitting the year around 29 Rabi al-Awwal / 1 Rabi al-Thani) — it is never imported by anything else in this package and its label says "illustrative only, not a default".

Because Sha'ban (month 8) falls before Ramadan (month 9) in the same Hijri year, the brief's opening/closing pair spans roughly eight lunar months within one Hijri year, leaving Ramadan through Dhu al-Hijjah (the Hajj season) outside the academic year — a structural consequence of the months' own ordering, not an assumption this module adds.

## 6. Calendar profiles

`waqt/institutional/profile.py`. Per the brief:

```
CalendarProfile
    name
    calendar_provider
    week_definition
    fiscal_year_definition
    academic_year_definition
    timezone_policy
    labeling_rules
```

`CalendarProfile` is a plain frozen dataclass composed of values already defined in this package, plus two free-form dicts (`timezone_policy`, `labeling_rules`) this sprint does not standardize the shape of. **Nothing in `waqt/core.py`, `waqt/solar.py`, or `waqt/scheduling/` reads a `CalendarProfile`** — it exists so an application can bundle one institution's choices into one named, swappable object, and it round-trips to/from JSON (`to_dict()` / `profile_from_dict()`) via `GET /v1/institutional/profile`. `CalendarProfile.__post_init__` rejects a profile whose `fiscal_year_definition`/`academic_year_definition` uses a *different* `calendar_provider` object than the profile's own — a profile is one institution's one coherent set of choices, not a place two providers' dates can silently mix.

## 7. Binding to real Waqt days (optional)

`waqt/institutional/binding.py` is the **only** place this layer touches `SchedulingContext` for fiscal/academic-year purposes, and it is entirely optional — §4 and §5 both work with no location at all. `waqt_day_for_gregorian_date(ctx, g)` finds the `WaqtDay` whose *closing* Maghrib falls on Gregorian date `g`, by probing local noon (UTC) — a deliberate approximation that is safe for every non-polar location and every timezone offset up to +/-12h (Maghrib never falls before local dawn or after local midnight), but is not a general "instant for civil date g" solver. See §9 for the one case it doesn't cover.

## 8. HTTP surface

| Endpoint | What it returns |
|---|---|
| `GET /v1/institutional/week` | The Islamic week containing an instant, at a location, under a `WeekDefinition` |
| `GET /v1/institutional/fiscal-year` | The default fiscal year (Muharram 1 -> end of Dhu al-Hijjah) for a Hijri year |
| `POST /v1/institutional/fiscal-year/resolve` | A caller-supplied `FiscalCalendar` (custom start_rule/end_rule) |
| `GET /v1/institutional/academic-year` | The default academic year (first Ahad Muharram -> last Khamis Sha'ban) |
| `POST /v1/institutional/academic-year/resolve` | A caller-supplied `AcademicCalendar` (terms, holidays) |
| `GET /v1/institutional/profile` | A demo `CalendarProfile` as pure JSON data |

A malformed or unresolvable rule is `422 UNPROCESSABLE` with `error.code = "INVALID_CALENDAR_RULE"` (a new error code alongside Sprint 6's `INVALID_RULE`, since the two are different rule vocabularies). Unlike scheduling's snapshot endpoint, there is no partial "here are the calendar facts, astronomy is undefined" fallback for fiscal/academic-year boundaries that fail to bind to a real Waqt day at a location — the binding was the whole point of supplying a location, so failure is reported as an error, not a degraded 200.

## 9. Honest limitations

- **`binding.py`'s noon-UTC probe** is an approximation, not a proof, for locations whose Maghrib can fall very close to local midnight under an extreme timezone offset far from the location's true solar longitude (a jurisdiction using a timezone many hours removed from its geography). No such combination exists in this project's test matrix; a caller working at that combination should verify their own case.
- **`gregorian_weekday_of` and `month_days` are O(month length)** per rule resolution — a probe-and-round-trip over up to 30 candidate days. Fine for interactive use (the reference implementation resolves a rule in well under a millisecond); an application resolving thousands of fiscal/academic years per request should cache `FiscalCalendar.year()` results itself, exactly as Sprint 6 asked callers to cache scheduling resolutions.
- **`AcademicCalendar.term_rules`/`holidays` resolve every sub-rule against the *same* Hijri year plus an optional integer `year_offset`.** This covers the common case (all terms inside one Hijri year, or explicitly shifted by whole years) but does not let a single term's start and end fall in different Hijri years without the caller doing that arithmetic themselves by supplying two `AcademicCalendar.year()` calls and splicing the results. No institution in this project's test matrix needed that; a real one might.
- **No second, independent astronomy implementation yet.** Sprint 6's report already noted the JS consumer deliberately does not recompute Maghrib from coordinates; Sprint 7 does not change that. It remains a parallel milestone, not a Sprint 7 blocker (this layer does not depend on astronomy at all — see §1).
- **Calendar-provider disagreement is real, not a bug.** `default_islamic_fiscal_calendar(TABULAR)` and `default_islamic_fiscal_calendar(UAQ)` can produce different Gregorian boundary dates for the *same* Hijri year, because the two providers disagree about the Hijri<->Gregorian mapping itself (documented in `docs/CALENDARS.md`). This is the opposite of Sprint 6's scheduling guarantee (where swapping providers changes only a display label) — deliberately: §4 states "the Hijri provider determines the actual date; the fiscal-calendar layer determines the institutional structure", and this is what that sentence means in practice. `TestFiscalYear.test_calendar_provider_changes_the_actual_dates_not_just_a_label` documents this explicitly so it is never mistaken for a regression.

## 10. Conformance vectors

`tests/vectors/institutional_vectors.json` (22 vectors, generated by `tests/vectors/generate_institutional_vectors.py`, never hand-edited). Because this layer's arithmetic is calendar-only (§1), each vector freezes a **calendar table** — every day of every Hijri month the vector's rule touches, as `{day, gregorian, weekday}` triples — instead of a solar day table. An implementation in another language needs no Hijri arithmetic and no astronomy to reproduce `expected`: it reads the table and applies this document's rule semantics. `consumers/js/src/institutional.mjs` is exactly that: a from-scratch JavaScript implementation sharing no code with `waqt/institutional/`, validated against all 22 vectors in `consumers/js/test/institutional_vectors.test.mjs` (`cd consumers/js && npm test`), and independently checked against a corrupted vector to confirm the check is not vacuous.
