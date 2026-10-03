# Open specification questions found by independent implementation

These are places where a developer working **only from the written specification** had to make a choice the
text does not determine. Each entry says what the independent implementation chose, what the reference does,
what the measured consequence is, and a **proposed** resolution. None of these is counted as a failure by the
harness (tier `open`), but every one is a place where two correct-by-the-text implementations can disagree.

Legend — *Shared?* is "yes" when both implementations made the **same** unstated choice. Those are the most
dangerous: no cross-implementation test can ever expose them, because the same assumption sits on both sides.

| ID | Topic | Independent chose | Reference does | Shared? | Measured consequence | Proposal |
|---|---|---|---|---|---|---|
| OQ-TIME-1 | Offset-less instant (`2026-09-19T15:42:00`) | reject `INVALID_INSTANT` | accepts, assumes UTC | no | silently different day if the caller meant local time | require an explicit offset (the doc already says "UTC"; say "must carry Z/offset") |
| OQ-TIME-2 | ISO basic date (`20260101`) accepted? | reject | accepts | no | harmless leniency | state "YYYY-MM-DD only" or "any ISO 8601" |
| OQ-TIME-3 | Sub-second precision of **output** instants | µs preserved | `/v1/waqt` truncates to whole seconds; `/v1/calendar/convert` keeps µs | no | exact-boundary behaviour cannot be probed through `/v1/waqt` (COP §4) | publish µs everywhere, or document the truncation |
| OQ-TAB-1 | Leap pattern of `arithmetic-tabular` | civil pattern 2,5,7,10,13,16,18,21,24,26,29 | same | **yes** | other published patterns (e.g. 2,5,7,10,13,15,18,21,24,26,29) differ in 1–2 of every 30 years by one day | name the pattern in CALENDARS.md; add all 30 year-lengths as vectors (done: CAL-002) |
| OQ-ASR-1 | Declination used for Asr altitude: at **transit** or at the Asr instant | transit | transit | **yes** | up to **5.9 s** (Makkah, 20 Mar) and −5.8 s (Quito) — larger than the proposed 5 s band | pick one; if "at transit", say so; widen low-latitude Asr band to 8 s or fix the convention |
| OQ-ASR-2 | Asr when the Sun is below the geometric horizon at noon (shadow length undefined) | undefined (changed after the sweep: first run produced an Asr at 67°N, 21 Dec) | undefined | **yes (now)** | one latitude step in the 141-point sweep | state the rule |
| OQ-DT-1 | ΔT model and decimal-year convention; UT1−UTC ignored? | Espenak–Meeus 2006, `y = year + (month−0.5)/12` | not inspected (black-box) | unknown | independent engine ≈0.1 s from DE421, reference ≈0.9 s (measured, Addis 20 Sep 2026) | declare the timescale and ΔT model in ASTRONOMY.md |
| OQ-DAY-1 | Which date labels a Waqt day when civil zone ≠ mean-solar zone | civil (IANA) date of the closing Maghrib **instant** | date in longitude-based solar time (see DIS-001) | no | label off by one day at Kiritimati, Apia, Chatham, Reykjavik (June) | spec text is already civil; add vectors (done) and fix the reference |
| OQ-DAY-2 | Event→date assignment | transit-anchored (Isha after midnight stays with its day) | same observable behaviour | likely | none observed in 300 random cases + 33 oracle places | state the rule: "events of a date are those around that date's upper transit" |
| OQ-DAY-3 | A day with exactly one undefined bounding Maghrib | whole day `UNDEFINED` | same | **yes** | e.g. last evening before polar day | state it (SEMANTICS §8 implies it) |
| OQ-EVT-1 | `next_event` of `waqt.compute`: occurrence or listing | by occurrence (tonight's Isha first) | by listing (tomorrow's Fajr) | no | after Maghrib the "next event" skips ~65 min of upcoming Isha | SCHEDULING §5 already uses occurrence; align API.md |
| OQ-UND-1 | Existence of a **grazing** event (sun within minutes of the threshold) | scan + ternary search | not inspected (black-box) | unknown | see sweep in `reports/differential-report.md` | declare a ±0.01° dead band and report `UNDEFINED_BORDERLINE`, or accept divergence |
| OQ-UAQ-1 | Origin of the Umm al-Qura chain ("29 days iff…, else 30") | seed + burn-in, block grid | cached chain | no | **none**: 6-month burn-in gives identical starts to 96-month for all 492 months of 1420–1460 | state that the chain is self-synchronising; give an anchor |
| OQ-UAQ-2 | Test inputs: Makkah elevation, limb vs centre, refraction, which sunset algorithm | elev 0, upper-limb convention (-34′), same Sun engine | PyEphem | no | 2 of 492 month starts differ; both are evenings where the Moon sets **3.7 s and 6.8 s before** the Sun (DE421 agrees: −3.7 s, −6.8 s) | state conventions; accept ±10 s indecision as inherent |
| OQ-UAQ-3 | Supported range of `umm-al-qura` and the error outside it | 1700–2300, `OUT_OF_RANGE` | returns a date for 1650…2300; fails at year 500 | no | different behaviour outside 1900–2100 | state range and code |
| OQ-ERR-1 | Valid range of `fajr_angle`, `isha_angle`, `asr_ratio` | reject ≤0 / ≥90 / ≤0 | accepts anything | no | 95° or −5° silently yield garbage | add ranges to API.md |
| OQ-ERR-2 | Error code for a non-existent Hijri day | `INVALID_HIJRI_DATE` | none (normalises) — see DIS-002 | no | `1448-02-30` → 15 Aug 2026 (a different month) | add the code |
| OQ-ERR-3 | Error for unknown IANA zone | `VALIDATION_ERROR` | `INTERNAL_ERROR` (HTTP 500) — see DIS-003 | no | client mistakes look like server faults | add to API.md |
| OQ-PRV-1 | Does a short `Retry-After` shorten the 30 s cooldown? | yes (replaces) | no (30 s floor) | no | circuit stays open 25 s longer | state it |
| OQ-PRV-2 | "Three consecutive soft failures open the circuit": does the 3rd failure itself open it for the next call | yes | yes | **yes** | — | state it |
| OQ-PRV-3 | Outbound budget refill (token bucket granularity) | continuous | continuous | **yes** | — | state it |
| OQ-SCH-1 | `next_event`/`prev_event` points have an `inclusive` flag (default true) | implemented from vectors | present | — | **not in SCHEDULING.md**; needed vector `point-next-maghrib-at-exact-maghrib-exclusive` | document |
| OQ-SCH-2 | Default slot of `event_position` (isha/maghrib → previous listing, others → day 0) | implemented from vectors | present | — | **not in prose**; first run failed until read from vectors | document |
| OQ-SCH-3 | `NO_VALID_WINDOW.duration_seconds = null`; `maghrib_boundaries: []` on `WINDOW_UNDEFINED` | implemented from vectors | present | — | 6 of the first 8 scheduling failures | document |
| OQ-SCH-4 | Which undefined slots are "relevant" (a slot whose day extends past the anchor) | derived from vectors | present | — | determines `skipped` lists | document the rule |
| OQ-SCH-5 | "Stepping **through** an undefined day" is `DAY_UNDEFINED` even when the target slot is beyond the table | derived from vectors | present | — | — | document |

## How to read "first-run" evidence

The scheduling engine of the independent implementation was written from `docs/SCHEDULING.md`, then run
against the 116 frozen vectors for the first time: **108 passed, 8 failed**. All 8 failures were gaps in the
prose (OQ-SCH-1…5), not algorithmic errors. After reading the vector expectations it passed 116/116. That is
the cleanest measurement we have of how much of the scheduling specification lives only in the vectors.
