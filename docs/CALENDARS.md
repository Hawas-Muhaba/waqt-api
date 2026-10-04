# Calendar Providers

Waqt does not hard-code one religious authority into the clock engine. The Gregorian↔Hijri mapping is a pluggable interface (`HijriProvider`: `name`, `version`, `from_gregorian`, optionally `to_gregorian`), and `waqt/core.py` and `waqt/solar.py` never change to accept a new one — verified directly by `md5sum` on every sprint that's touched this system, not just asserted.

Query `GET /v1/calendar` for the live, authoritative list. This document explains what each one actually promises.

## `arithmetic-tabular` (default)

The classical 30-year-cycle tabular Islamic calendar (epoch JDN 1948440 = 1 Muharram, 1 AH). A pure, deterministic, closed-form arithmetic formula — no astronomy, no external data, works offline for any date instantly, and **inverts exactly** (`to-gregorian` is exact, not approximate, since the forward direction is closed-form).

**Important:** this is *not* an approximation of the official Umm al-Qura calendar specifically. It typically agrees with Umm al-Qura to within 1–2 days, sometimes more. Use `umm-al-qura` (below) if you specifically want to approximate the Saudi civil calendar.

**Normative definition (contract 2.0.0, DR-0005).** The provider named `arithmetic-tabular`, version `30-year-cycle-epoch-1948440`, is exactly this:

- Epoch: JDN 1948440 = 1 Muharram 1 AH = Friday, proleptic Gregorian 0622-07-19.
- Months alternate 30 and 29 days (odd months 30); Dhu al-Hijjah has 30 days in a leap year.
- **Leap years are positions 2, 5, 7, 10, 13, 16, 18, 21, 24, 26, 29 of the 30-year cycle**, i.e. `(11 * year + 14) mod 30 < 11` (CAL-002). All 30 year-lengths are conformance vectors.
- Domain: AH years start at 1. A date that does not exist (year < 1, or a day beyond the month's length) is `INVALID_HIJRI_DATE`, never normalised (CAL-004).

This pins the *identity* of the provider so results are reproducible. It does not say the pattern is the correct Islamic calendar: other published tabular patterns (for example a variant with leap positions 2, 5, 7, 10, 13, 15, 18, 21, 24, 26, 29) differ from this one by a day in some years, and an astronomical epoch (Thursday) is also in use. **Which calendar to follow is the caller's choice via `calendar_provider`**; a variant would be a *new provider* with its own name and version, never a silent substitution (GOVERNANCE.md section 6). No variant is provided today.

Not decided here (OQ-TAB-2): a Gregorian date before the epoch currently converts to an AH year <= 0 that cannot be converted back. This is outside the supported domain and stays open.

## `umm-al-qura`

An astronomical implementation of the *actual current Umm al-Qura calculation rule* (in force since 1423 AH / 2002 CE): a lunar month is 29 days if the astronomical conjunction occurs before Maghrib at Makkah **and** the moon sets after the sun that same evening at Makkah; otherwise it's 30 days. Built from Waqt's own validated solar engine (for Maghrib at Makkah) plus `ephem`/PyEphem (for the lunar conjunction and moonset — the one piece of astronomy nothing else in Waqt needs).

**Validated** against four independently-known official Umm al-Qura New Year dates spanning nine years (1 Muharram 1438 → 2 Oct 2016, 1440 → 11 Sep 2018, 1441 → 31 Aug 2019, 1447 → 26 Jun 2025). All four reproduce exactly.

**What this is not**, stated as plainly as the validation above:
1. **No channel for real-world sighting overrides.** The actual Umm al-Qura calendar occasionally adjusts 1 Muharram, 1 Ramadan, 1 Shawwal, and 1 Dhu al-Hijjah specifically after real crescent-sighting reports, layered on top of the calculation. This provider always returns the pure calculation — it cannot know about or apply such an adjustment. For exactly those four liturgically significant months, that's a real, unresolved gap.
2. **Not the highest-precision lunar ephemeris available.** PyEphem's built-in lunar theory is solid but not a modern high-precision ephemeris. For a conjunction or moonset within a few seconds of Maghrib, a better ephemeris could in principle flip a single month's 29/30 decision. None of the four validated months happened to be that close — future months could be.
3. **Bounded date range (CAL-011, DR-0007).** The provider is supported for civil dates **1700-01-01 through 2300-12-31 only**; outside that range it refuses with `OUT_OF_RANGE` instead of guessing (HTTP 400). Accuracy is only characterised for roughly 1900-2100; between 1700 and 1900 and between 2100 and 2300 the provider answers but no accuracy claim is made.

**Conventions and what is, and is not, settled (contract 2.0.0).**

- *Settled (OQ-UAQ-1, DR-0007):* the month chain ("29 days iff the criterion holds, else 30") is self-synchronising. Measured in Sprint 15 with two independent implementations: a 6-month burn-in gives identical month starts to a 96-month burn-in for all 492 months of 1420-1460 AH. That is evidence over that range, not a proof for all years.
- *Settled (OQ-UAQ-3, DR-0007):* the supported range and the `OUT_OF_RANGE` error (above).
- **Unresolved by design (OQ-UAQ-2, CAL-007):** which Moon and Sun algorithms, which limb, how much refraction, and which observer elevation define "the Moon sets after the Sun" at Makkah. The reference uses PyEphem's defaults; the independent implementation uses elevation 0 and an upper-limb convention. They disagree on 2 of 492 month starts, both evenings on which the Moon sets 3.7 s and 6.8 s *before* the Sun. The official table is an institutional product; this document does not pick a winner. Those vectors stay `informative`. Callers who need the official table should use a `declared` provider fed from it.

Given all of the above, treat this as "a rigorous, honestly-labeled astronomical approximation of Umm al-Qura" — a real improvement over `arithmetic-tabular` for this specific purpose, not a certified reproduction of the official calendar.

## `declared`

An institution's adopted date for one specific Gregorian date — supplied at request time via `override_date` + `declared_year`/`declared_month`/`declared_day`. Falls back to `arithmetic-tabular` for every other date, and if no override is supplied at all.

**The one thing that trips people up:** `override_date` must equal the *label date* the request will actually look up — the Gregorian date the relevant Waqt day's *closing* Maghrib falls on (see `API.md` §8 and `TIME-MODEL.md`), not the date you'd naively read off an `instant`. If they don't match, your override silently never fires and you'll see `arithmetic-tabular` in the response instead of `declared` — not an error, just a no-op, so check the response's `hijri.provider.name` to confirm it took effect.

Does not support reverse conversion (`to-gregorian`) — a single-date override has no general inverse.

## `local-observation`

Structurally identical to `declared`, but semantically distinct on purpose: it represents a raw, reported moon sighting (`sighting_year`/`month`/`day` + optional `observed_at` naming where it was seen from) rather than an institutional decision. The distinction matters because sightings from different places can genuinely conflict, and `source_note` in the response says which one a given date rests on — something a bare override doesn't represent.

Same override-date gotcha as `declared` applies. Same non-invertibility.

## `aladhan` (live, Sprint 14)

A *remote* provider: asks AlAdhan for the date, caches it 12 h, and falls back to `umm-al-qura` when it cannot deliver — always
saying which happened (`hijri.source`: `remote` / `remote-stale` / `local-fallback`). It is a Hijri **date** source only and never
affects event times. Single-date endpoints only. See **LIVE-INTEGRATIONS.md**.

## Writing your own provider

Anything satisfying the `HijriProvider` shape works, with zero changes to `waqt/core.py` or `waqt/solar.py`:

```python
class MyProvider:
    name = "my-provider"
    version = "1.0"
    def from_gregorian(self, d: date) -> HijriDate:
        ...
    def to_gregorian(self, year: int, month: int, day: int) -> date:  # optional
        ...
```

`waqt/calendar_providers/registry.py`'s `ExampleRegionalOffsetProvider` is a deliberately trivial worked example (wraps another provider, shifts by a fixed day offset) proving this claim with a passing test (`test_custom_provider_plugs_in_untouched`) rather than just asserting it.

## Reverse conversion (`GET /v1/conversions?direction=to-gregorian`)

Only providers with a fixed, invertible rule support this: `arithmetic-tabular` (exact, closed-form) and `umm-al-qura` (exact against *this provider's own* computed boundaries — walks its cached real-conjunction chain to the requested month rather than approximating). Both directions round-trip exactly for every date tested — see `tests/test_api.py::test_conversions_round_trip_*`.

**Existence is checked (CAL-004).** After converting, the result is converted back; if it does not return the requested year, month and day, the date does not exist in that provider's calendar and `INVALID_HIJRI_DATE` is returned (for example day 30 of a 29-day Umm al-Qura month). Year < 1 is rejected before any conversion.

`declared` and `local-observation` return `UNSUPPORTED_OPERATION` for this direction, honestly, rather than guessing at an inverse a sparse override table doesn't have.
