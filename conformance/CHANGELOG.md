# Conformance contract changelog

Newest first. Every entry lists what changed in requirements, vectors and registry, the decision records
behind it, and whether it is breaking (GOVERNANCE.md section 2).

## 2.0.0 -- Sprint 16 -- PROPOSED (decision records await maintainer ratification, see MAINTAINERS.md)

**Breaking.** Narrowed accepted outcomes and changed expected values.

Defects resolved in the reference (all listed in `DISAGREEMENTS.md`; `known-failures.json` is now empty):
DIS-001 (DR-0001), DIS-002 and DIS-003 (DR-0006).

Requirements
- Promoted open -> MUST: EVT-007 (DR-0003), CAL-002 (DR-0005), CAL-004 (DR-0006), CAL-011 (DR-0007), ERR-002 (DR-0006).
- Clarified: DAY-004 and DAY-007 (DR-0001), EVT-004 and UND-001 (DR-0002).
- Added: AST-001, AST-002 (DR-0004); DAY-009 (DR-0001); SCH-009..SCH-013 (DR-0008).
- Kept open on purpose: CAL-007 (unresolved by design, DR-0007), UND-004, PRV-007, TIME-002.
- Every requirement now carries `since`, `status`, and where applicable `decision`/`changed`.

Vectors (breaking changes marked *)
- `errors`: err/tz-unknown accepts only UNKNOWN_TIMEZONE *; err/tz-malformed added.
- `calendar-core`: tab/invalid/1448-2-30 and 0-1-1 accept only INVALID_HIJRI_DATE *; the five numeral-range vectors accept
  INVALID_HIJRI_DATE or VALIDATION_ERROR (INVALID_DATE, a Gregorian code, removed *); tab/invalid/1448-12-30 and
  -1-1-1 added; the 30 tab/month12-length vectors open -> exact.
- `calendar-uaq`: uaq/range/{1650-01-01,1699-12-31,2301-01-01,2500-01-01} promoted to exact OUT_OF_RANGE *;
  boundary vectors 1700-01-01 and 2300-12-31 added (informative).
- `day-model`: next-event/tonights-isha and asr/degenerate-67N-solstice moved here from open-questions;
  label/skip/reykjavik/2026-06-15 and label/repeat/reykjavik/2026-06-29 added; 137 Asr vectors tagged AST-001.
- `legacy-waqt`: waqt/kiritimati-date-line label fields restored (1448-04-07, al-Ahad) *.
- `legacy-scheduling`: existing vectors tagged SCH-009..SCH-013 (no expectation changed).
- Project vectors (outside this contract, vector set 1.1 -> 2.0): `tests/vectors/waqt_vectors.json` kiritimati-date-line
  label corrected *; `sdks/vectors/sdk_conformance_vectors.json` recorded `next_event` of two responses corrected *.

Registry (`spec/open-questions.json`): 28 questions; 16 resolved, 11 deferred, 1 unresolved by design (OQ-UAQ-2).
New: OQ-TAB-2, OQ-TAB-3.

Protocol: COP 1.0 -> 1.1 (adds UNKNOWN_TIMEZONE; INVALID_HIJRI_DATE now required for non-existent dates).

Process: GOVERNANCE.md, VERSIONING.md, MAINTAINERS.md (unfilled), decisions/, proposals/, tools/contract.py,
contract.json. `tools/build_requirements.py` retired.

Known gaps at release (also in SPRINT-16-REPORT.md): the Umm al-Qura computation could not be executed in the
authoring sandbox, so reference results for Umm al-Qura-dependent vectors are unverified here and must be
confirmed by CI.

## 1.0.0 -- Sprint 15 (retroactive)

First independent implementation; 663 normative vectors; 56 MUST / 7 OPEN requirements; 28 reference failures
recorded (DIS-001..003); 26 open specification questions.
