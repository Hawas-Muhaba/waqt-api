# Known disagreements — register

Every place where the reference (`waqt-core` / `waqt-api`) and the independent implementation
(`conformance/independent`) give different answers, or where a result is decided by something other than
the specification. Each entry is classified:

| class | meaning | counts as a failure? |
|---|---|---|
| **DEFECT-REF** | the reference contradicts the written specification | yes (normative vector fails; listed in `baselines/known-failures.json`) |
| **DEFECT-IND** | the independent implementation contradicts the written specification | yes — none open at the end of Sprint 15 |
| **SPEC-Q** | the specification does not determine the answer (see `spec/OPEN-QUESTIONS.md`) | no — tier `open` |
| **CONFIG** | intentionally configurable / convention-dependent behaviour | no |
| **NUMERIC** | inherent numerical sensitivity; no tolerance can remove it | no — tier `informative` |

> **Status at contract 2.0.0 (Sprint 16): DIS-001, DIS-002 and DIS-003 are RESOLVED in the reference** (`waqt-core` 0.4.0,
> API 1.6.0). `baselines/known-failures.json` is empty. The text below is the Sprint 15 finding, kept for the
> record; its "documented, not fixed" statements describe Sprint 15.
>
> | Defect | Ruling | Fix |
> |---|---|---|
> | DIS-001 label | `decisions/DR-0001.md`: option (A), civil date of the closing Maghrib instant | `core.py`: label from `tz.local_date(closing_maghrib)`; frozen vector corrected |
> | DIS-002 Hijri normalisation | `decisions/DR-0006.md`: `INVALID_HIJRI_DATE` | `hijri.py` validation + `checked_to_gregorian`; API/local mapping |
> | DIS-003 unknown zone | `decisions/DR-0006.md`: `UNKNOWN_TIMEZONE`, HTTP 400 | validation in `ManualTimezoneProvider`; global handler |
>
> Not a defect, still a disagreement (kept visible): **OQ-UAQ-2** - the reference and the independent implementation differ
> on 2 of 492 Umm al-Qura month starts (Moon sets 3.7 s and 6.8 s before the Sun). Class NUMERIC/CONFIG; deliberately unresolved.
> Verification caveat: the Sprint 16 sandbox could not execute the Umm al-Qura provider, so this has not been re-measured.

Evidence for every entry is reproducible: the vector IDs name entries in `vectors/*.json` and the numbers
come from `reports/conformance-report.*` and `reports/differential-report.*`.

Nothing in `waqt-core`, `waqt-api` or the frozen Sprint 5–8 vector files was modified in Sprint 15. The
defects below are **documented, not fixed**: each changes observable behaviour and deserves a maintainer decision
(and, for DIS-001, an update to a frozen vector).

---

## Reference defects

### DIS-001 — Day label uses a longitude-based solar date, not the civil date  · DEFECT-REF (high confidence; maintainer ruling requested)
**Rule (SEMANTICS §3, CALENDAR-INTEROP §1):** a Waqt day carries the Hijri date and weekday of the **civil
(IANA-zone) Gregorian date on which its closing Maghrib falls**.

**Observed.** `calendar/convert?direction=gregorian-date-to-waqt` resolves civil date **Sunday 2026-09-20** at
Kiritimati to the day closing at 18:26 local on 2026-09-20 — and labels it **1448-04-06 / as-Sabt (Saturday)**.
Tabular 2026-09-20 is 1448-04-07. The label is the same when the time zone is `UTC`, so it does not depend on
the zone at all; every case is consistent with *"date of the closing Maghrib in local **mean solar** time"*.

| place | zone | why civil ≠ solar date at Maghrib | vectors failing |
|---|---|---|---|
| Kiritimati | UTC+14, lon −157° | solar time ≈ UTC−10.5 | `label/kiritimati/*`, `label/date-to-waqt-day/kiritimati/*`, `label/compute-midday/kiritimati/*` |
| Apia | UTC+13, lon −172° | same | `label/apia/*`, … |
| Chatham | UTC+13:45, lon −176.5° | same | `label/chatham/*` |
| Reykjavik (June) | UTC+0, lon −22° | Maghrib 00:04 civil, ≈22:37 solar | `label/reykjavik/*`, `label/after-midnight-maghrib/reykjavik` |

**Prevalence:** 21 of 200 random (place, instant) draws over 24 places had a wrong weekday
(`reports/differential-report.md`); the four affected places are exactly the ones above. Addis Ababa,
Makkah, London, New York, … are unaffected, which is why Sprints 2–14 never saw it.

**Internal inconsistency.** Within the reference, `gregorian_date_to_waqt_day(2026-06-15, Kiritimati)` returns a
day closing on civil 2026-06-15 (matching the spec and the Sprint 8 vector) while that same day carries the
*previous* date's Hijri label.

**Why not simply fixed.** The frozen Sprint 5 vector `kiritimati-date-line` records the current label
(`1448-04-06`, `as-Sabt`). The adopted copy in `vectors/legacy-waqt.json` has those two fields removed with a
note; the question is covered by the `label/*` vectors. Changing it is a behaviour change.
**Options:** (A) fix the reference to use the civil date of the closing Maghrib instant and update the frozen
vector (recommended: matches the text, matches `gregorian_date_to_waqt_day`); (B) amend the specification to say
"mean-solar date" and say so in CALENDAR-INTEROP (then `gregorian_date_to_waqt_day` must change).

### DIS-002 — `to-gregorian` silently normalises non-existent Hijri days  · DEFECT-REF
`/v1/conversions?direction=to-gregorian&year=1448&month=2&day=30` (Safar 1448 has 29 days under
`arithmetic-tabular`) returns **2026-08-15**, which is 1 Rabi al-Awwal — a different month. `year=0` returns
`0621-07-30`. Vectors `tab/invalid/1448-2-30`, `tab/invalid/0-1-1`. The institutional layer is *not* affected
(it validates by round-trip, INSTITUTIONAL §2) — the hole is the raw conversion. Day 31, month 13 and day 0 are
correctly rejected. Fix: round-trip check, error `INVALID_HIJRI_DATE`/`VALIDATION_ERROR` (OQ-ERR-2).

### DIS-003 — Unknown IANA time zone returns HTTP 500 `INTERNAL_ERROR`  · DEFECT-REF
`timezone_override=Mars/Base` raises `ZoneInfoNotFoundError`, surfaced as `INTERNAL_ERROR`. A client mistake must
be a 4xx `VALIDATION_ERROR` (COP §3: `INTERNAL_ERROR` is never an acceptable answer to bad input).
Vector `err/tz-unknown`.

---

## Unresolved specification questions (not failures)

| ID | Divergence | See |
|---|---|---|
| DIS-004 | `waqt.compute.next_event`: reference lists only the new day's events, so right after Maghrib it reports tomorrow's Fajr and skips tonight's Isha (46 min away in the Addis example, 65 min after Maghrib); independent reports tonight's Isha. SCHEDULING §5 already specifies *occurrence* semantics for the scheduling layer, so the two documents disagree. Vector `next-event/tonights-isha` (open). | OQ-EVT-1 |
| DIS-005 | Naive (offset-less) instants: reference assumes UTC, independent rejects. | OQ-TIME-1 |
| DIS-006 | Output precision: `/v1/waqt` truncates instants to whole seconds; independent keeps µs. Consequence: exact-boundary behaviour (half-open interval at the microsecond) can only be demonstrated through endpoints that publish µs (`/v1/calendar/convert` does). The harness probes ±1 precision-unit for the reference and says so. | OQ-TIME-3, COP §4 |
| DIS-007 | Non-physical profile parameters (`fajr_angle=95`, `asr_ratio=0`, negative angles): reference accepts silently, independent rejects with `VALIDATION_ERROR`. Five `open` vectors. | OQ-ERR-1 |
| DIS-008 | A short `Retry-After` (5 s) on 429: independent shortens the 30 s cooldown, reference keeps 30 s. | OQ-PRV-1 |
| DIS-009 | ISO basic date `20260101` and sub-second echo: reference accepts / truncates. | OQ-TIME-2/3 |
| DIS-010 | Umm al-Qura outside 1900–2100: reference answers for 1650–2300, independent for 1700–2300 (`OUT_OF_RANGE` outside). | OQ-UAQ-3 |

## Convention-dependent / numerical (not failures)

### DIS-011 — Umm al-Qura: 2 of 492 month starts differ (1420–1460)  · NUMERIC / SPEC-Q (OQ-UAQ-2)
490 of 492 month starts agree. The two differences are the start of Dhu al-Qadah 1420 (reference 2000-02-06 / independent 2000-02-07) and of
Jumada al-Thani 1446 (2024-12-02 / 2024-12-03). Both follow from the evening of the 29th of the preceding month (Shawwal 1420, 5 Feb 2000; Jumada al-Awwal 1446, 1 Dec 2024), on which **the Moon sets 6.8 s and 3.7 s before the Sun**.
JPL DE421 gives −6.8 s and −3.7 s as well (a hand evaluation with the same limb convention), i.e. the
independent engine is numerically right *for the stated convention*, but the written rule does not fix the
convention (upper limb vs centre, refraction, observer elevation, sunset algorithm), and a 4–7 s margin is
below any plausible implementation tolerance. These months are tier `informative` (`uaq/year-table/*`).
The chain's origin does **not** matter: burn-in of 6, 12, 24, 48 and 96 months give identical starts for
all 492 months (OQ-UAQ-1).

### DIS-012 — Astronomy accuracy of the reference  · CONFIG / documented
Against DE421 over 200 random (place, instant) draws the day-boundary error is **median 1.10 s, p95 3.20 s,
max 4.26 s** for the reference and **median 0.09 s, p95 0.13 s, max 0.17 s** for the independent engine.
Within the proposed bands (CONFORMANCE §5) and consistent with the documented "about one second", but it is the
dominant systematic difference between the two implementations. It is also why legacy vectors that place an instant
*exactly on the reference's Maghrib* (`exact-maghrib`, `one-second-before-maghrib`, …) cannot be compared across
engines; they are tier `informative` and replaced by metamorphic checks DAY-002/003 that need no exact instant.

### DIS-013 — Asr declination convention moves Asr by up to ~6 s  · SPEC-Q, **shared assumption** (OQ-ASR-1)
Using the declination at *transit* (all implementations here, and the oracle) vs at the *Asr instant* changes
Asr by +5.9 s (Makkah, 20 Mar) and −5.8 s (Quito, 23 Sep). The proposed 5 s band is tighter than the convention
sensitivity, so a third implementation choosing the other convention would fail Asr vectors at low latitude.

### DIS-014 — Asr when the Sun is below the true horizon at noon  · SPEC-Q (OQ-ASR-2)
At 67°N on 21 Dec the Asr target altitude is degenerate (−0.44°). The independent implementation first
returned an Asr there; the 141-point latitude sweep showed the oracle and reference return none, and the
implementation was changed. The change is recorded because it was made *after* seeing a disagreement.

---

## The independent implementation's own limitations (not hidden)

* **No time-zone lookup from coordinates.** Every location-dependent COP case supplies `timezone`. This is a
  scope decision, not a capability claim: coordinate→zone depends on third-party boundary data.
* **Same language family as `consumers/js`.** Node.js was the only runtime available besides Python, so
  language-level independence from the reference is real, but there is no second non-Python language.
  The codebase shares no code with `consumers/js` (which only evaluates frozen day tables).
* **Umm al-Qura uses the written chain rule**, not the official Saudi table; it reproduces the four documented
  anchors and 490/492 months of the reference but cannot be called "the" Umm al-Qura calendar.
* **ICU zone data** (Node's Intl) is a different source from Python's `zoneinfo`; the two agreed on every
  zone tested, but a future tzdata skew would surface as a disagreement here.
* **Independence is partial in process, not only in code** — see `SPRINT-15-REPORT.md` §4 for exactly what the
  author had read before writing each module.

## What cross-implementation agreement cannot tell us

Agreement is only evidence where the two implementations made *different* choices. The entries marked
**shared assumption** (OQ-TAB-1 leap pattern, OQ-ASR-1, OQ-DAY-3, OQ-PRV-2/3, and now OQ-ASR-2) are places where
both sides chose the same thing without the text requiring it; no vector in this suite can detect an error
there. They are exactly the items the specification should state next.
