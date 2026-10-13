# Sprint 3 Report — Calendar Provider System

**Sprint goal:** turn Hijri dates from one implementation into genuine pluggable infrastructure, and build a real Umm al-Qura provider that stops apologizing for not existing.
**Status:** done. 45/45 tests passing (13 new). `waqt/core.py` and `waqt/solar.py` are **byte-for-byte unchanged** from Sprint 2 — verified by md5sum, not just claimed.

---

## 1. The provider interface — formalized, not just present

Stage 1 already had `HijriProvider` (a `Protocol`: `name`, `from_gregorian`). This sprint adds the piece the brief specifically asked for — every provider and every returned date now carries a **version**, not just a name:

```json
{ "provider": "umm-al-qura", "version": "astronomical-approx-2002-rules-v1", "date": "1448-04-09" }
```

`HijriDate` gained a `version` field (default `"unversioned"` for anything that predates this) and an optional `source_note`, used by `LocalObservationProvider` to say *which* sighting report a date rests on.

## 2. Five provider categories — all five actually exist now

| Category | Class | What it is |
|---|---|---|
| ArithmeticTabular | `ArithmeticTabularProvider` (Stage 1, unchanged) | Classical 30-year arithmetic calendar |
| **UmmAlQura** | `UmmAlQuraProvider` (**new**) | Astronomical approximation of the real UAQ calculation rule — see §3 |
| Declared | `DeclaredProvider` (Stage 1, now versioned) | Institutional override, one date at a time |
| LocalObservation | `LocalObservationProvider` (**new**) | Crowd-sourced sighting reports, distinct from Declared, carries the observation site |
| Custom | `ExampleRegionalOffsetProvider` (**new**, demo) | Proof that a third party can write a provider with zero access to `core.py`/`solar.py` and it just works |

Declared vs. LocalObservation is a genuine distinction, not two names for one class: Declared answers "what date has this institution adopted" (an administrative decision, however it was reached); LocalObservation answers "what did someone report seeing, from where" (a raw, potentially-conflicting observation). Both fall back to another provider for any date they don't have an entry for — tested.

## 3. The Umm al-Qura provider — built for real, not stubbed

This is the piece of Sprint 3 that mattered most, since Stage 1's `SCOPE.md` explicitly flagged the gap: *"the shipped provider is not the official Umm al-Qura calendar... a true `tabular-uaq` provider is future work pending that dataset."* No official dataset was available, so instead of stubbing this out, I implemented the **actual current UAQ rule**, astronomically:

> On the evening of a month's 29th day, if the astronomical conjunction occurs before Maghrib **and** the moon sets after the sun that evening, the new month begins at that Maghrib (a 29-day month). Otherwise, it begins one day later (a 30-day month).

Built from:
- **`waqt.solar`** for Maghrib at Makkah — the same engine, same validated accuracy, as the rest of Waqt. Deliberately reused rather than reimplemented, so a Ramadan boundary and an ordinary Tuesday's sunset are never computed two different ways.
- **`ephem`** (PyEphem) for the lunar conjunction and moonset — the one piece of astronomy Waqt didn't already have, since nothing else in the system needs the moon.

**Validation, stated precisely:** I checked this against four independently-known official Umm al-Qura New Year dates, spanning nine years and pulled from a published Umm al-Qura calendar site (not derived from this code):

| Hijri year | Expected (official UAQ) | This provider | Match |
|---|---|---|---|
| 1438 | 2 Oct 2016 | 2 Oct 2016 | ✅ |
| 1440 | 11 Sep 2018 | 11 Sep 2018 | ✅ |
| 1441 | 31 Aug 2019 | 31 Aug 2019 | ✅ |
| 1447 | 26 Jun 2025 | 26 Jun 2025 | ✅ |

4 for 4, across nine years and no shared code path with the source I checked against. That's a real result, and I want to be equally clear about what it doesn't prove — see below.

**What this provider is *not*, stated as plainly as the honesty note that flagged its absence:**

1. **Real UAQ sometimes overrides the calculation.** The reference calendar I validated against says explicitly that 1 Muharram, 1 Ramadan, 1 Shawwal, and 1 Dhu al-Hijjah are occasionally *adjusted* after real crescent-sighting reports, layered on top of the pure calculation. This provider has no channel for that — it always returns the calculation, never an announced adjustment. For the four months that matter most liturgically, that's a real gap.
2. **The lunar ephemeris is a high-quality approximation, not a modern high-precision one.** PyEphem's built-in lunar theory is solid, but for a conjunction or moonset landing within seconds of Maghrib, a more precise ephemeris could in principle flip a single month's 29/30 decision. None of the four validated months happened to be that close, but future months could be.

Named accordingly: `umm-al-qura`, version `astronomical-approx-2002-rules-v1` — not `tabular-uaq`, and not presented as a drop-in replacement for the official source. This is the same discipline Stage 1 applied to `arithmetic-tabular`, extended to a provider that's actually trying to be the real thing and still isn't quite it.

## 4. Registry — a name-based lookup, plus proof of pluggability

`CalendarProviderRegistry` (`register`, `get`, `names`) holds the stateless built-ins (`arithmetic-tabular`, `umm-al-qura`); `DeclaredProvider` and `LocalObservationProvider` aren't pre-registered since they need per-deployment data (override dictionaries) to construct.

`ExampleRegionalOffsetProvider` is the sprint's proof-of-claim: a deliberately trivial third-party provider (wraps another one, shifts by a fixed day offset), written entirely in `waqt/calendar_providers/registry.py`, that plugs into `compute_waqt()` through the *exact same* injection point as every built-in — and does, per `test_custom_provider_plugs_in_untouched`.

## 5. The deliverable, checked directly rather than assumed

> Developers can replace the Hijri calendar calculation without modifying Waqt's astronomical or clock engine.

```
$ md5sum waqt/core.py waqt/solar.py
af88c5fdc13e99390597598586db9d73  waqt/core.py
8002b2fb03de49ba0784528b766cb3f2  waqt/solar.py
```

Identical to their Sprint 2 state. Every provider added this sprint — including the astronomically real one — plugs in through the same `HijriProvider` parameter `compute_waqt()` already accepted in Stage 1. `test_swapping_calendar_provider_does_not_change_astronomy` confirms the flip side of that: switching providers changes *only* `r.hijri_date`; the Maghrib boundaries, the Waqt clock reading, and every prayer event's instant are bit-for-bit identical regardless of which calendar is plugged in.

## 6. What's still out of scope

- **No channel for real UAQ's sighting-based adjustments** (§3.1) — would need either a live feed of announcements or manual entries via `DeclaredProvider`/`LocalObservationProvider` on the four relevant months each year.
- **No higher-precision lunar ephemeris** — PyEphem is good, not the best available; a Level-A calendar provider (mirroring the Level A/B split from Sprint 2) is future work.
- **Registry has no persistence or dynamic (runtime-added) discovery mechanism** beyond in-process `register()` calls — fine for this sprint's scope, would need real thought (versioning, conflicts) before being exposed for arbitrary third parties to register against a running deployment.

## Test suite

13 new tests in `tests/test_calendar_providers.py`, on top of the 32 from Sprint 2 — 45 total, all passing. Run with `python3 -m pytest tests/ -v`.
