# Waqt — Sprint 17: Real-Environment Verification and Release Readiness Report

Builds on `SPRINT-16-REPORT.md`. Sprint 16 introduced Conformance Contract 2.0.0 (draft), resolved reference defects DIS-001/002/003, codified high-impact semantic rules (DR-0001 through DR-0008), and established governance frameworks. 

Sprint 17 provides authoritative verification across the entire Waqt codebase using a real runtime environment with real dependencies (PyEphem, FastAPI, Starlette, timezonefinder, httpx, pytest, Skyfield, JPL DE421, Node.js).

---

## 1. Executive Summary & Outcome

| Verification Dimension | Sprint 16 Baseline (Constrained Stand-in) | Sprint 17 Result (Real Environment) | Status | Evidence |
|---|---|---|---|---|
| **Reference Conformance** | 646 pass / 55 fail (PyEphem missing) | **701 normative pass / 0 fail** | **VERIFIED & PASSED** | `WAQT_RUN_CONFORMANCE=1 pytest tests/test_conformance_suite.py` |
| **Independent Conformance** | 704 pass / 0 fail | **704 normative pass / 0 fail** | **VERIFIED & PASSED** | `waqt_conform.py` (Node clean-room engine) |
| **Known-Failures Baseline** | 0 expected | **0 failures** | **VERIFIED & PASSED** | `conformance/baselines/known-failures.json` is empty |
| **Umm al-Qura Provider** | Guard tested, provider skipped | **All range & month-chain tests pass** | **VERIFIED & PASSED** | Real PyEphem 4.2.1, 1700–2300 boundaries |
| **Real FastAPI / Starlette** | Mocked in `/tmp` | **Real HTTP sockets, uvicorn, exception handlers** | **VERIFIED & PASSED** | `test_sprint16_api.py`, `live_stack_check.py` (29/29) |
| **Python SDK Suite** | Not run | **108 pass / 0 fail** | **VERIFIED & PASSED** | `pytest sdks/python/tests/` |
| **JavaScript SDK Suite** | 32 pass / 22 fail (unverified) | **55 pass / 0 fail** | **VERIFIED & PASSED** | `node --test sdks/js/waqt-client/test/*.test.mjs` |
| **Differential Run (DE421)** | Not run in S16 | **500 cases + 141-pt sweep: 0 disagreements** | **VERIFIED & PASSED** | Skyfield 1.55 + JPL DE421 ephemeris |
| **Mutation Testing** | Not re-run | **14 / 14 mutations CAUGHT** | **VERIFIED & PASSED** | `conformance/tools/mutation_check.py` |
| **Contract Integrity** | Draft verified | **0 problems, 2 expected warnings** | **VERIFIED & PASSED** | `python conformance/tools/contract.py verify` |
| **Release State** | Draft (`"released": false`) | **Draft (`"released": false`) preserved** | **PENDING HUMAN RATIFICATION** | DR-0001..DR-0008 awaiting maintainer signature |

---

## 2. Verification Environment Details

| Component | Specification / Version |
|---|---|
| **Operating System** | Windows 11 / PowerShell |
| **Python Runtime** | Python 3.13.14 |
| **Node.js Runtime** | Node v24.11.0 |
| **Ephemeris Engine** | `ephem` 4.2.1 |
| **HTTP Runtime** | `fastapi` 0.141.1, `starlette` 1.6.0, `uvicorn` 0.38.0 |
| **HTTP Client & Testing** | `httpx` 0.28.1, `pytest` 9.1.1, `pytest-asyncio` 1.4.0 |
| **Timezone Resolution** | `timezonefinder` 9.0.0, `timezonefinder-data` 3.2026.3.post1 |
| **Astrometry Oracle** | `skyfield` 1.55, `jplephem` 2.24, `sgp4` 2.27, `de421` 2008.1 |
| **Waqt Distributions** | `waqt-core` 0.4.0, `waqt-api` 0.4.0 (API 1.6.0), `waqt-local` 0.5.0, `waqt-client` 0.2.0 |

---

## 3. Verification of Sprint 16 Reference Defect Fixes

Authoritative real-dependency verification confirmed all Sprint 16 resolutions:

### 3.1 DIS-001: Day-Label Convention (DR-0001)
- **Verified Behavior**: The Hijri date and weekday of a Waqt day correspond to the civil date in the location's IANA timezone on which the closing Maghrib instant falls.
- **Date-Line & Extreme Longitude Cases**:
  - Kiritimati (`2026-09-19T22:00Z`): Evaluated to `1448-04-07 al-Ahad` (civil date `2026-09-20`), passing all conformance assertions.
  - Apia (`2026-03-20T12:00Z`): Evaluated to `1447-10-02 as-Sabt`.
- **Reykjavik Near-Midnight Anomalies (DAY-009)**:
  - Reykjavik `2026-06-15` (no closing Maghrib): Correctly returns `resolved=false` without exception.
  - Reykjavik `2026-06-29` (two closing Maghribs): Resolves to the day containing local solar noon.

### 3.2 DIS-002: Invalid Hijri Date Handling (DR-0006)
- **Verified Behavior**: Non-existent dates such as `1448-02-30`, Year 0, and negative years raise `INVALID_HIJRI_DATE` with HTTP 400.
- **Provider-Independent Validation**: `checked_to_gregorian` ensures neither Umm al-Qura nor AlAdhan silently normalizes invalid dates into neighboring months.

### 3.3 DIS-003: Unknown & Malformed Timezones (DR-0006)
- **Verified Behavior**: `timezone_override=Mars/Base` or malformed path attempts (e.g. `../etc/passwd`) consistently trigger `UNKNOWN_TIMEZONE` with HTTP 400 and detailed parameter diagnosis (`details.parameter`, `details.received`, `details.expected`).
- **Consistency**: `ManualTimezoneProvider` enforces this across GET endpoints, batch/POST schedules, and `waqt_local`.

### 3.4 Additional Contract Semantics (DR-0003, DR-0004, DR-0005, DR-0007, DR-0008)
- **Next-Event Semantics**: `next_event` immediately after Maghrib correctly returns that evening's Isha (by occurrence), rather than tomorrow's Fajr.
- **Asr Declination**: Declination calculated at upper transit (geometric noon). Tested across 137 Asr vectors (`AST-001`).
- **Tabular Leap Years**: Enforces the 30-year leap cycle (positions 2, 5, 7, 10, 13, 16, 18, 21, 24, 26, 29).
- **Scheduling Rules**: Promoted rules SCH-009 through SCH-013 fully verified across span and window evaluations.

---

## 4. Umm al-Qura & Calendar Provider Resolution

In Sprint 16, 55 reference conformance failures were reported under the constrained environment. 

### Finding:
- **Root Cause**: In Sprint 16's sandbox, PyEphem was absent, causing all provider instantiations depending on astronomical moon calculations to fail.
- **Sprint 17 Verification**: With real PyEphem 4.2.1 installed:
  - **All 55 failures disappear**. The reference implementation achieves **0 normative failures**.
  - Boundary range enforcement: Supported range `1700-01-01` to `2300-12-31` correctly rejects `1650-01-01`, `1699-12-31`, and `2301-01-01` with `OUT_OF_RANGE` (HTTP 400).
  - Month-chain and historical / contemporary dates resolve accurately.
  - Institutional convention variations between reference and independent implementations on 2 edge month-start instants remain properly categorized as `informative` vectors (preserving religious neutrality per GOVERNANCE §6).

---

## 5. HTTP Runtime & API Integration Verification

Real FastAPI, Starlette, and Uvicorn runtime execution confirmed:
- **Dedicated Exception Dispatchers**: `WaqtUnknownTimezoneError`, `WaqtInvalidHijriDateError`, and `WaqtOutOfRangeError` cleanly map to HTTP 400.
- **Envelope Structure**: All responses maintain `meta`, `data`, and `error` keys without schema drift.
- **Live Stack Sockets Test (`verification/live_stack_check.py`)**: 29 of 29 checks PASSED under real uvicorn socket execution (CORS preflight, origin filtering, rate limiting 429 + Retry-After, AlAdhan fallback circuit breaker).

---

## 6. Comprehensive Test Suite Results

| Test Suite | Commands Executed | Passed | Failed | Skipped | Notes |
|---|---|---|---|---|---|
| **Root Tests** | `pytest tests` | **597** | **0** | 3 | Full HTTP API, providers, scheduling, semantics |
| **Core Library Tests** | `pytest core/tests` | **394** | **0** | 0 | Solar engine, timescale, calendar, shims |
| **Local Embeddable Tests** | `pytest local/tests` | **191** | **0** | 1 | `waqt_local` serverless execution & parity |
| **Python SDK Tests** | `pytest sdks/python/tests` | **108** | **0** | 0 | Sync/async client, typed requests, errors |
| **JavaScript SDK Tests** | `node --test test/*.test.mjs` | **55** | **0** | 0 | Typed builders, packaging smoke, client |
| **Independent Node Tests** | `node --test test/*.test.mjs` | **13** | **0** | 0 | Zero-dependency reference implementation |
| **Consumer JS Tests** | `npm test` in `consumers/js` | **184** | **0** | 0 | Downstream integration tests |
| **App Tests (CLI, Consumer, Web)** | `pytest apps/*/tests` | **38** | **0** | 0 | CLI (19), Consumer (9), Web (10) |
| **Independent Astronomy Tests** | `pytest independent-astronomy/tests` | **36** | **0** | 0 | VSOP87D, ELP2000, Skyfield DE421 matrix |
| **Conformance Harness Suite** | `WAQT_RUN_CONFORMANCE=1 pytest tests/test_conformance_suite.py` | **2** | **0** | 0 | Full DE421-derived vector suite (2 adapters) |
| **Version Consistency Tests** | `pytest tests/test_version_consistency.py` | **7** | **0** | 0 | Cross-axis version decoupling |
| **Packaging Smoke Tests** | `pytest */tests/test_packaging_smoke.py` | **5** | **0** | 0 | Clean venv build and installation |
| **Total Test Executions** | — | **1,630** | **0** | **4** | **100% Pass Rate across all runnable tests** |

---

## 7. Conformance Evidence & Differential Analysis

### 7.1 Normative Conformance Matrix (Contract 2.0.0)
- **Independent Clean-Room Implementation**: 704 normative vectors PASS / 0 FAIL / 43 metamorphic PASS.
- **Reference Implementation**: 701 normative vectors PASS / 0 FAIL / 43 metamorphic PASS.
- **Verdict Agreement**: Complete agreement on all normative vectors. 17 differences on non-normative (`informative` / `open`) tiers representing intentional institutional boundary conventions.

### 7.2 Differential Oracle Run (JPL DE421 via Skyfield)
Executed 500 uniform random cases across 24 global coordinates, 3 calendar years, and all times of day, plus a 141-point high-latitude existence sweep (45.0°N to 68.0°N):
- **Day-boundary error vs DE421 (|open|, |close| worst-case)**:
  - Reference: Median = 0.93 s, P95 = 3.18 s, Max = 4.26 s.
  - Independent: Median = 0.09 s, P95 = 0.13 s, Max = 0.17 s.
- **Disagreements with Oracle**: **0** (None).
- **High-Latitude Sweep Disagreements**: **0 of 141 points**.

### 7.3 Conformance Suite Mutation Check
14 distinct semantic mutations evaluated against the suite:
- **All 14 mutations were CAUGHT** by normative test vectors and reported failing requirements.

---

## 8. Contract Integrity & Version Audit

```
python conformance/tools/contract.py verify
warning: ERR-004 is MUST but has no normative vector (declared, not enforced)
warning: 12 unresolved question(s): OQ-TIME-1, OQ-TIME-2, OQ-TIME-3, OQ-TAB-2, OQ-TAB-3, OQ-DT-1, OQ-UND-1, OQ-UAQ-2, OQ-ERR-1, OQ-PRV-1, OQ-PRV-2, OQ-PRV-3
contract verify: ok (0 problem(s), 2 warning(s))
```

- **Manifest Hash**: Hashed and consistent across all requirement files, vector sets, and COP definitions.
- **Draft Status**: `contract.json` maintains `"released": false`. Conformance contract 2.0.0 will only be frozen into `conformance/releases/` upon human maintainer ratification.
- **Version Axes Audit**:
  - Conformance Contract: `2.0.0` (Draft)
  - Vector Set: `2.0`
  - Core Library (`waqt-core`): `0.4.0`
  - Local Engine (`waqt-local`): `0.5.0`
  - API Version: `1.6.0`
  - Python SDK (`waqt-client`): `0.2.0`
  - JS SDK (`waqt-client`): `0.2.0`
  - Solar Engine Revision: `2` (Low Precision / Level B)

---

## 9. Human Ratification Checklist

Sprint 17 confirms technical readiness. The following items require formal human maintainer review and ratification before marking Conformance Contract 2.0.0 as released:

| Decision Record | Topic | Key Proposed Rule | Technical Consequence | Ratification Status |
|---|---|---|---|---|
| **DR-0001** | Day Label | Civil date of closing Maghrib instant | Resolves date-line day naming (Kiritimati/Apia); introduces `resolved=false` on rare polar dates without closing Maghrib | **PENDING** |
| **DR-0002** | Event Assignment | Events assigned by own transit date | Solar events remain tied to astronomical noon interval | **PENDING** |
| **DR-0003** | Next-Event Semantics | Next event evaluated strictly by occurrence | Request immediately post-Maghrib returns tonight's Isha | **PENDING** |
| **DR-0004** | Asr Convention | Declination at geometric upper transit | Fixes noon shadow length benchmark across latitudes | **PENDING** |
| **DR-0005** | Tabular Leap Rule | 30-year cycle (positions 2,5,7,10,13,16,18,21,24,26,29) | Unifies arithmetic tabular leap calendar | **PENDING** |
| **DR-0006** | Dedicated Error Codes | `INVALID_HIJRI_DATE`, `UNKNOWN_TIMEZONE` (HTTP 400) | Distinct, actionable client error codes | **PENDING** |
| **DR-0007** | Umm al-Qura Range | Supported range `1700-01-01` .. `2300-12-31` | Explicit out-of-range errors outside valid span | **PENDING** |
| **DR-0008** | Scheduling Rules | Codify SCH-009 through SCH-013 | Normalizes schedule span and boundary evaluations | **PENDING** |
| **MAINTAINERS.md** | Maintainer Roster | Fill active project maintainer records | Required by `GOVERNANCE.md` §4 before contract release | **PENDING** |

---

## 10. Repeatability & CI Configuration

`.github/workflows/ci.yml` has been updated to include:
1. **Contract Integrity Checks**: `contract.py verify` and `migrate_contract_2_0.py --check`.
2. **Independent Implementation Suite**: Execution of clean-room Node tests.
3. **Full Conformance Suite Gate**: `WAQT_RUN_CONFORMANCE=1 pytest tests/test_conformance_suite.py` on real CI runners.
4. **SDK & Multi-Package Verification**: Comprehensive Python, JavaScript, Core, and Local test jobs.

---

## 11. Conclusion & Recommendation

All verification gates for Sprint 17 have passed with zero normative failures under real dependencies.

### Recommendation:
1. The codebase and test infrastructure are **Ready for Human Ratification**.
2. Project maintainers should review and sign off on Decision Records DR-0001 through DR-0008 and populate `MAINTAINERS.md`.
3. Once ratified, execute `python conformance/tools/contract.py build --release` to freeze and release Conformance Contract 2.0.0.
