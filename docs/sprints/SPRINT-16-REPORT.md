# Sprint 16 — Resolving the reference defects and governing the conformance contract

Builds on `SPRINT-15-REPORT.md`. Sprint 15 measured where the reference and a clean-room implementation disagree;
Sprint 16 decides what is right, fixes the reference, writes the rules down, and sets up the process that keeps them
true.

> **Read section 2 first.** This sprint was implemented in an offline sandbox that could not run the real
> dependencies (PyEphem, FastAPI, timezonefinder, pytest). Section 2 says exactly what that means for every claim.

## 1. Outcome in one table

| Sprint 16 item | Status | Evidence |
|---|---|---|
| Resolve the three reference defects | **Done** | DIS-001/002/003 fixed in `waqt-core`, `waqt-api`, `waqt_local`; all 28 Sprint 15 known failures now pass |
| Decide intended behaviour for DIS-001 | **Done**, ratification pending | DR-0001: civil date of the closing Maghrib instant |
| Resolve high-impact specification questions | **Done for 16 of 28**; the rest stay visible | day labels, event semantics, Asr, tabular leap years, UAQ range and chain, scheduling rules |
| Update the normative specification | **Done** | `docs/SEMANTICS, SCHEDULING, ASTRONOMY, CALENDARS, API, CALENDAR-INTEROP`, `COP.md`; 13 new or promoted requirements |
| Version the conformance contract | **Done** (draft) | contract 2.0.0, `contract.json`, `tools/contract.py`, `VERSIONING.md`, `CHANGELOG.md` |
| Create governance rules | **Done**, unstaffed | `GOVERNANCE.md`, decision records, proposal template; **`MAINTAINERS.md` is blank** |
| Keep unresolved questions visible | **Done** | 12 unresolved questions printed in every report; Umm al-Qura conventions deliberately left open |

Three things I could not do and you should not assume: **ratify** the decisions (they need a named maintainer),
**run Umm al-Qura**, and **run the suite with real FastAPI/pytest**. See sections 2 and 10.

## 2. Verification environment and what it limits

No network. `ephem`, `fastapi`, `pytest`, `timezonefinder`, `httpx` were not installable. I therefore built
**verification-only stand-ins in `/tmp` (not shipped)**: a minimal fake FastAPI and `TestClient` that drive the *real*
`waqt.api` code, a stub `ephem`, a stub `timezonefinder` (answers from the place/zone pairs in the vectors), and a
mini test runner standing in for pytest.

**Fidelity test, done before trusting any of it.** On the untouched Sprint 15 tree the stand-ins reproduced **all 28**
of Sprint 15's known reference failures, exactly. Every other failure on that tree was Umm al-Qura/AlAdhan-related.

What this means:

| Claim | Basis |
|---|---|
| Core logic, error mapping, vectors, contract tooling | **Executed**, through the stand-ins where HTTP is involved |
| Anything touching the Umm al-Qura computation | **Not executed.** The range guard was tested directly (guard runs before any ephemeris call); the provider itself was not |
| Real FastAPI/Starlette behaviour (exception-handler dispatch for a `ValueError` subclass, 422 shape) | **Not executed.** I rely on standard MRO-based dispatch; CI is the confirmation |
| Real timezone lookup | **Not executed** |
| Existing test suites | Run under a **stand-in runner, not real pytest**, and compared against the untouched tree (section 8) |
| Python SDK tests | **Not run** (needs `httpx`) |
| Differential report, mutation check | **Not re-run** |

## 3. The three reference defects

### DIS-001 — day label (decision DR-0001)
**Ruling.** The Hijri date and weekday of a Waqt day are those of the **civil date, in the location's IANA zone, on
which the closing Maghrib *instant* falls**. This is what SEMANTICS §3 and CALENDAR-INTEROP §1 already said; the
reference had taken the label from the solar-date key given to its solver.

**Fix.** `core.py`: `label_date = tz_provider.local_date(closing_maghrib)`; Hijri and weekday derive from it; new
additive `WaqtResult.label_date`. Events remain keyed by solar date (DR-0002), so nothing else moves.

| Place (instant) | Before | After |
|---|---|---|
| Kiritimati 2026-09-19T22:00Z | 1448-04-06 as-Sabt | **1448-04-07 al-Ahad** |
| Apia 2026-03-20T12:00Z | 1447-10-01 al-Jumuah | **1447-10-02 as-Sabt** |
| Reykjavik 2026-06-21T12:00Z | 1448-01-05 al-Ahad | **1448-01-06 al-Ithnayn** |
| Addis Ababa 2026-09-19T15:42Z | 1448-04-07 al-Ahad | unchanged |

**A consequence I found and wrote down rather than hid (DAY-009).** Civil-date labels are not one-to-one near local
midnight. Reykjavik 2026: **15 June has no closing Maghrib** (23:58:53 on the 14th, next 00:00:09 on the 16th) and
**29 June has two** (00:00:16 and 23:59:04). Rules: labels never decrease; a date with none is unresolved
(`resolved=false`); a date with two resolves to the day containing its local noon. Reference and independent
implementation agree on both dates. This is a property of the rule, not a bug, but a reader may disagree with it, so
DR-0001 records the alternatives and what would reopen it.

### DIS-002 — non-existent Hijri dates (DR-0006)
`1448-02-30`, year 0 and negative years returned a date in another month. Now `INVALID_HIJRI_DATE`, HTTP 400.
`hijri.py` validates (year ≥ 1, month 1–12, day within the month's length); `checked_to_gregorian` adds a
provider-independent round-trip check so Umm al-Qura/AlAdhan cannot normalise either. Out-of-range *numerals*
(month 13, day 31) may stay `VALIDATION_ERROR` (shape validation precedes calendar validation). The institutional
`month_days` helper relied on the old normalisation and was adapted.

### DIS-003 — unknown time zones (DR-0006)
`timezone_override=Mars/Base` was HTTP 500 `INTERNAL_ERROR`. Now `UNKNOWN_TIMEZONE`, HTTP 400, with
`details.parameter/received/expected`. `ManualTimezoneProvider` validates at construction, so **every** endpoint, the
POST/batch schedule path, and `waqt_local` behave the same. Malformed names such as `../etc/passwd` are also unknown
zones.

## 4. Specification questions

Sprint 15 listed 26 questions; Sprint 16 adds two (OQ-TAB-2, OQ-TAB-3). **16 resolved, 11 deferred, 1 unresolved by
design.**

| Question | Ruling | Record |
|---|---|---|
| OQ-DAY-1 day label | civil date of the closing Maghrib instant | DR-0001 |
| OQ-DAY-2/3 event assignment; one undefined Maghrib | events follow their own transit; the whole day is UNDEFINED | DR-0002 |
| OQ-EVT-1 `next_event` | **by occurrence**, includes the previous solar day's Isha | DR-0003 |
| OQ-ASR-1/2 Asr | declination **at upper transit** (the literal noon shadow); undefined iff geometric noon altitude ≤ 0° | DR-0004 |
| OQ-TAB-1 tabular leap years | positions 2,5,7,10,13,16,18,21,24,26,29; the pattern is part of the provider's identity | DR-0005 |
| OQ-ERR-2/3 errors | `INVALID_HIJRI_DATE`, `UNKNOWN_TIMEZONE` (dedicated codes, HTTP 400) | DR-0006 |
| OQ-UAQ-1/3 chain, range | chain is self-synchronising (measured); supported **1700-01-01..2300-12-31**, `OUT_OF_RANGE` outside | DR-0007 |
| OQ-SCH-1…5 scheduling | five rules that lived only in vectors are now prose + requirements SCH-009…013 | DR-0008 |

**Deliberately not resolved**

| Question | Why |
|---|---|
| **OQ-UAQ-2** Umm al-Qura conventions (limb, refraction, elevation, algorithms) | Institutional, not technical. The two implementations differ on 2 of 492 month starts (Moon sets 3.7 s and 6.8 s *before* the Sun). Picking a winner would present an institutional convention as fact and produce a cleaner report for the wrong reason. Those vectors stay `informative`. |
| OQ-TAB-3 tabular variants | No demand recorded; a variant would be a new provider, never a substitution |
| OQ-TAB-2 pre-epoch Gregorian dates | Outside the asked scope |
| OQ-TIME-1/2/3, OQ-DT-1, OQ-UND-1, OQ-ERR-1, OQ-PRV-1/2/3 | Not prioritised this sprint; no position taken |

One inconsistency is now visible instead of latent: **ERR-004 is a MUST that no normative vector enforces** (its
vectors are `open`). Every report lists it.

## 5. Normative specification

Rules moved out of implicit vector behaviour into written, testable requirements:
`SEMANTICS §3` (label rule and its consequences), `ASTRONOMY` ("Asr: the declination convention"),
`CALENDARS` (tabular definition with epoch and leap rule; UAQ range, chain, and what is unresolved; existence checking),
`SCHEDULING §11` (the five rules), `API` (three error codes, `next_event`, which date exactly), `CALENDAR-INTEROP`,
`COP` (1.1: `UNKNOWN_TIMEZONE`; unresolved date is `resolved=false`).
`requirements.json`: 71 requirements, each now with `since`, `status`, and `decision`.
Promoted open→MUST: EVT-007, CAL-002, CAL-004, CAL-011, ERR-002. Added: AST-001/002, DAY-009, SCH-009…013.
137 Asr vectors are tagged AST-001.

The Asr 5.9 s sensitivity figure is **Sprint 15's measurement; I did not re-measure it.**

## 6. Versioning the contract

Contract **2.0.0**, separate from every other version axis. `VERSIONING.md` defines MAJOR/MINOR/PATCH,
what a conformance claim means, and the release procedure. `contract.json` hashes requirements + vectors + registry +
COP (not the known-failures baseline, which is status, not contract). `tools/contract.py verify` checks the manifest,
every cross-reference, decision records, changelog and COP version; a **released** manifest is immutable.

**Why MAJOR.** `err/tz-unknown` accepted three codes and now accepts one. Narrowing an accepted set is breaking, and the
independent implementation really did have to change. This is the process catching a "small" edit.

2.0.0 is currently a **draft** (`"released": false`): nothing is ratified, so no immutable `releases/` copy exists yet.
Run `python3 conformance/tools/contract.py build --release` after ratification.

Other axes: `waqt-core` 0.3.0→0.4.0, `waqt-local` 0.4.0→0.5.0, `waqt-api` 0.3.0→0.4.0, **API 1.5.0→1.6.0** (additive
error codes plus two behaviour corrections), **vector set 1.1→2.0** (MAJOR by the project's own rule: expected values
changed), COP 1.0→1.1, engine revision **unchanged** (`solar.py`/`timescale.py` untouched).
`tests/test_version_consistency.py` passes 7/7.

## 7. Governance

`conformance/GOVERNANCE.md`: change classes and a precise definition of **breaking**; the proposal → evidence → review →
decision-record → changelog → release path; which source governs when they disagree; how dissent is recorded (in the
record, in the dissenter's words, never deleted); a **forced-consensus test** of four questions; and a rule for religious
and regional conventions (a convention is a named parameter, provider or profile; the spec fixes what each option *means*,
not which is right; a new option is a new name; a convention that cannot be written as a rule is served by a `declared`
source). It also lists what is configurable today and what is unresolved.

`decisions/DR-0001…0008` follow a template with sections for **Configurability**, **Dissent**, and **Reopen when**.
Retired because re-running them would silently overwrite 2.0.0: `build_requirements.py`, `build_vectors.py`,
`import_legacy.py` (they now refuse without `--rebuild-1.0-baseline`).

## 8. Results

**Independent implementation vs contract 2.0.0 (full run):** 733 vectors + 43 metamorphic, **704 normative pass / 0 fail**
(Sprint 15: 663). Node unit tests 13/13.

**Reference vs contract 2.0.0 (sandbox, no PyEphem):** 646 normative pass / 55 fail (43 vectors + 12 metamorphic).
- **None of the 28 Sprint 15 known failures remain.**
- **Every one of the 55 failures is a vector that explicitly uses `umm-al-qura` or `aladhan`** (AlAdhan falls back to UAQ);
  this was checked programmatically against the vector inputs, not inferred.
- All Sprint 16 targets pass: all 148 `label/*`, `label/skip` and `label/repeat`, 30 `tab/month12`, `tab/invalid/*`,
  `err/tz-unknown`, `err/tz-malformed`, `next-event/tonights-isha`, `asr/degenerate-67N-solstice`,
  `waqt/kiritimati-date-line`.
- 4 of the 55 are the new `uaq/range/*` vectors: the sandbox cannot construct the provider. The guard was tested directly
  (1650, 1699-12-31, 2301, 2500 and year 500 all raise `OUT_OF_RANGE`; in-range dates pass the guard).

**Regression differential, original Sprint 15 tree vs this tree, same stand-ins:**

| Suite | Original | Now | Notes |
|---|---|---|---|
| root + `local/` tests | 443 pass | **483 pass** | +40 new; the 175 failures and 4 errors are the same on both trees (missing PyEphem, stub limits, packaging tooling) |
| `core/` tests | 161 pass | **200 pass** | +39 new; one new failure is my UAQ test, which needs real PyEphem |
| JS SDK | 32 pass / 22 fail | identical | the 22 are unchanged; not diagnosed |
| `test_version_consistency` | — | 7/7 | |

The frozen Sprint 5 Kiritimati vector failed after the fix, as expected, and was corrected (below).

## 9. Behaviour changes to know about

These are corrections, but they are visible to consumers:

1. **Day label** differs from before at places where civil and mean-solar dates disagree at Maghrib (4 of 24 places in
   the Sprint 15 survey) — DR-0001.
2. **`next_event`** right after Maghrib is now that evening's Isha, not tomorrow's Fajr — DR-0003. **Two recorded SDK
   vectors had captured the old value** (`/v1/waqt` and `/v1/events` at 2026-09-19T15:42Z); only their `next_event`
   fields were updated.
3. **Frozen vector `kiritimati-date-line`** (Sprint 5) recorded the defect and was corrected. Vector set 1.1→2.0.
4. **Umm al-Qura** now refuses 1650–1699 (previously answered) — DR-0007.
5. **New HTTP 400 codes**: `INVALID_HIJRI_DATE`, `UNKNOWN_TIMEZONE`, `OUT_OF_RANGE`. SDKs do not enumerate codes by name
   (no references found), but I did not run the Python SDK tests.

## 10. What I did not verify, and what to run

Run these in CI with real dependencies before trusting this release:

1. `WAQT_RUN_CONFORMANCE=1 pytest tests/test_conformance_suite.py` — the gate now expects an **empty** reference baseline.
   If a Umm al-Qura vector fails there, it is a real finding, not noise.
2. `pytest core/tests tests local/tests sdks/python/tests` and the JS SDK tests, with real FastAPI.
3. `./run.sh` to regenerate the reports, including the differential report and mutation check I could not run.
4. `python3 conformance/tools/contract.py verify`.
5. Confirm on real Starlette that a `ValueError` subclass is dispatched to its registered handler (standard behaviour,
   unverified here).
6. Confirm Umm al-Qura at the range boundaries (`uaq/range/1700-01-01`, `2300-12-31` are `informative`; their values
   come from the independent implementation).

Smaller caveats: the COP-level `resolved=false` for an unresolvable date is a translation in the reference *adapter*
(the HTTP API still returns 422 `CALENDAR_DATE_UNRESOLVABLE`); `tab/invalid` accepts `VALIDATION_ERROR` for numeral-range
cases; the `.git` directory is untouched and nothing is committed.

## 11. Decisions that need a human

- **Ratify DR-0001…0008** and fill `MAINTAINERS.md`. Until then every record says `Ratification: PENDING` and the
  contract is a draft.
- Choices I made under the brief that you may want to overturn: dedicated codes rather than reusing `VALIDATION_ERROR`;
  HTTP 400 for them; the UAQ range 1700–2300; occurrence semantics for `next_event`.
- Whether to schedule the deferred questions, in particular **ERR-004** (a MUST nothing enforces) and OQ-ERR-1
  (garbage-in for angles).

## 12. Files

60 modified, 19 added, none removed (full list: `diff -r` against the Sprint 15 zip). Added: `conformance/{GOVERNANCE,
VERSIONING,CHANGELOG,MAINTAINERS}.md`, `contract.json`, `decisions/` (8 records, index, template), `proposals/TEMPLATE.md`,
`spec/open-questions.json`, `tools/contract.py`, `tools/migrate_contract_2_0.py` (the audit trail for every 2.0.0 vector
change; idempotent), `reports/sprint16-*`, and tests `core/tests/test_sprint16_contract_rules.py`,
`tests/test_sprint16_api.py`, `tests/test_conformance_contract.py`, `local/tests/test_sprint16_local.py`.

## 13. Reproduce

```
python3 conformance/tools/contract.py verify
python3 conformance/tools/migrate_contract_2_0.py --check
python3 conformance/harness/waqt_conform.py --adapter "node conformance/independent/src/cli.mjs" --label independent
cd conformance/independent && node --test test/*.test.mjs
pytest core/tests tests local/tests          # needs real dependencies
```
