# Option B final report: `umm-al-qura` is the default everywhere (API 1.7.0, waqt-core 0.5.0, contract CAL-012)

Branch `feature/umm-al-qura-default-option-b`, report of 2026-10-10 (after commit `37016c1`). Every result below was produced **fresh in this session** after the last change. Nothing was published, released or merged into a protected branch.

**Recommendation: YELLOW.** Every runnable gate passes. It is not GREEN because: the conformance contract is still an unreleased 2.0.0 draft (13 open questions; ERR-004 is a MUST without normative vectors), DR-0010 and CCP-0001 are not yet ratified/reviewed, and no signed ratification artifact exists. The full list is the last section.

## 1. This change set (second Option B pass)
| Request | Done |
|---|---|
| Maintainer is Mr. Hawas Muhaba Hussein | `MAINTAINERS.md`: Maintainer = Mr. Hawas Muhaba Hussein; Project owner = Dr. Salim Muhammed Redi (DR-0001..0009 were ratified by him; their text now says "project owner", not "Maintainer") |
| API default and the lower-level library default must be identical | **One definition**: `waqt_core.calendar_providers.default` (`DEFAULT_CALENDAR_PROVIDER = "umm-al-qura"`). The API, `waqt-local` and the CLI **import** it; a test fails if any layer re-types the literal. `waqt-core`'s own fallbacks (`calendar_interop`, `SchedulingContext`) use it too (they were `arithmetic-tabular`) |
| The core contract adopts the same default | Contract 2.0.0 (draft) gains **CAL-012** (MUST): omitted provider = `umm-al-qura`, explicit provider honoured. COP text, 7 `exact` vectors (expected values copied from normative Umm al-Qura vectors), CCP-0001, DR-0010. Both implementations pass all normative vectors (reference 708/0, independent 711/0). No expected value of any existing vector changed |
| Version bumps and changelogs | `waqt-core` 0.4.0 -> **0.5.0**, `waqt-api` package 0.4.0 -> **0.5.0**, `waqt-local` 0.5.0 -> **0.6.0**, `waqt-cli` 0.1.1 -> **0.2.0**; pins `waqt-core>=0.5.0,<0.6`, `waqt-local>=0.6.0,<0.7`. Changelogs: `core/`, `local/`, `apps/cli/CHANGELOG.md` (new). Lineage in `docs/VERSIONING.md`. API contract stays 1.7.0, engine revision `"2"`, vector set 2.0 |
| Package tests and clean-install checks | New `tests/test_packaging_default_provider_chain.py`: builds all four wheels, installs them in a throwaway venv that cannot see the checkout, `pip check`, installed versions == source, pins in wheel metadata, one default in every layer, `waqt` CLI default and explicit results, out-of-range call. The core and Python-SDK packaging smoke tests now derive the expected version from source (they hard-coded `0.4.0` / `0.3.1`) and the core smoke test proves the shipped default |
| Unaddressed questions in the report | Last section |

### Bugs found and fixed in this pass
1. **HTTP 500 from `/v1/calendar/convert`** (and `AttributeError: 'NoneType' ... 'iso_like'` in `waqt-core`) for an instant or date outside umm-al-qura's 1700..2300. It was reachable with an explicit `umm-al-qura` and became common with the new default. Now: the Waqt day and instants are returned, `hijri` is empty and `calendar_error` says why (additive, same policy as `/v1/waqt`; carried through `WaqtDay.calendar_error`; mirrored in `waqt-local`).
2. **Contract/adapters silently disagreed with the API**: the COP was silent and both conformance adapters defaulted to `arithmetic-tabular`. Three normative DAY-004 vectors only passed because of that; they now name the provider they always meant (expected values untouched).
3. **A mutation check gap**: the tool ran a fixed suite list, so a regression of CAL-012 "survived". Fixed; all 15 mutations are now caught (CAL-012: 7 normative vectors fail when the default is reverted).
4. **Stale literals** in tests: a hard-coded `0.4.0` (core packaging smoke), `0.3.1` (SDK packaging smoke), `28` questions (contract test).
5. **Web governance page** could only show "all pending" or "all ratified"; it now reflects a mixed state read from the decision files (and its tests follow the files instead of hard-coding).

## 2. Results (all fresh)
| Check | Result |
|---|---|
| Root `tests/` | PASS 794 passed, 2 skipped (the 2 skips are the env-gated conformance suite, **run separately: PASS 2/2**) |
| Core `core/tests` (includes packaging smoke) | PASS 401 |
| `local/tests` / CLI / web Python / API consumer | PASS 193 (+1 skipped by design) / 21 / 37 / 9 |
| Independent astronomy / Python SDK | PASS 36 / 108 |
| JS: web / JS SDK / consumers | PASS 42 / 55 / 184 |
| Live-stack | PASS 35/35 |
| Vector additivity | PASS (no recorded value changed or disappeared; migration declared) |
| Contract verify / doc counts | PASS (0 problems; 2 visible warnings: ERR-004, 13 unresolved questions) / counts current |
| Reference vs independent conformance | PASS: 742 vectors + 43 metamorphic; normative reference 708/0, independent 711/0; 19 verdict differences (17 already at the committed baseline + the 2 new `open` vectors for OQ-CAL-1) |
| Mutation check of the suite | PASS 15/15 caught |
| Packaging and clean install | PASS: core, API, whole chain (core+api+local+cli) |
| Browser, real HeadlessChrome | PASS 58/58 (Option B), 16/16 (Sprint 14), 36/36 (Sprint 13 smoke) |

Nothing is BLOCKED or NOT RUN. Environment notes: browser runs need `npm install` in `verification/browser`; page regeneration needs `npm install` in `apps/web/tools`; `hijridate==2.3.0` and `pip install -e apps/api-consumer` enable the tests that skip without them.

## 3. Default behaviour (unchanged contract with callers)
Omitted -> `umm-al-qura`; explicit `umm-al-qura` -> same; explicit `arithmetic-tabular` -> previous results; unknown name -> `400 UNKNOWN_CALENDAR_PROVIDER`; the response names the provider used. Canonical Waqt time never depends on the provider (grid test; browser test). Umm al-Qura is a deliberate project default, not a claim that every community follows one convention; every provider stays selectable. The 13 provider-aware API routes, `waqt-core`, `waqt-local`, the CLI, Waqt Web (explicit request) and the contract all agree.

### Corrections to the earlier version of this report
`waqt-cli` was at **0.1.1**, not 0.1.0. The web page generator was **not broken**; it needed `npm install` in `apps/web/tools`.

## 4. Governance state
* DR-0001..DR-0009: ratified by **Dr. Salim Muhammed Redi** (project owner), recorded 2026-10-10 on the requester's report.
* **DR-0010** (core/contract default, CAL-012): **ratification PENDING** (Mr. Hawas Muhaba Hussein, Maintainer). I did not mark it ratified: you named him as Maintainer but did not state that he ratified.
* **CCP-0001**: independent review pending (the reviewer role is unfilled).
* No signed artifact for any ratification is in the repository. The contract is not released.

## 5. Questions not yet addressed

### 5.1 Open specification questions (13 in the registry; none resolved by this work)
| ID | Status | Requirement | Question |
|---|---|---|---|
| OQ-TIME-1 | deferred | TIME-002 | Offset-less instant: reject or assume UTC |
| OQ-TIME-2 | deferred | - | ISO basic date (`20260101`) accepted? |
| OQ-TIME-3 | deferred | - | Sub-second precision of output instants |
| OQ-TAB-2 | deferred | - | Gregorian dates before the tabular epoch convert to AH year <= 0 |
| OQ-TAB-3 | deferred | - | Tabular variants (other leap patterns, astronomical epoch) are not provided |
| OQ-DT-1 | deferred | - | Delta-T model and decimal-year convention |
| OQ-UND-1 | deferred | UND-004 | Existence of grazing events |
| OQ-UAQ-2 | unresolved by design | CAL-007 | Umm al-Qura computational conventions (limb, refraction, elevation, algorithms): institutional, not technical |
| OQ-ERR-1 | deferred | ERR-004 | Valid ranges of `fajr_angle`, `isha_angle`, `asr_ratio` |
| OQ-PRV-1 | deferred | PRV-007 | Does a short `Retry-After` shorten the 30 s cooldown |
| OQ-PRV-2 | deferred | PRV-007 | Circuit breaker: does the 3rd soft failure open it for the next call |
| OQ-PRV-3 | deferred | PRV-007 | Outbound budget refill granularity |
| **OQ-CAL-1 (new)** | deferred | CAL-012 | With the default provider and a date outside 1700..2300, must `waqt.compute` / `calendar.*` refuse with `OUT_OF_RANGE` (independent implementation) or return the Waqt day with an empty Hijri label (reference, API 1.5.0 policy)? Two `open` vectors record the disagreement; my proposal is the empty label, but no consensus was forced |

### 5.2 Contract and governance
1. **ERR-004** is a MUST with no normative vectors (blocked on OQ-ERR-1).
2. **DR-0010 ratification** by the Maintainer, and **CCP-0001 independent review** (role unfilled), are outstanding. Until then CAL-012 is a draft amendment.
3. **Who may ratify:** GOVERNANCE.md says a "named maintainer" ratifies; DR-0001..0009 were ratified by the project owner. `MAINTAINERS.md` now lists both roles as able to ratify; the owners should confirm that is intended.
4. **Signed artifact** for the ratifications (none exists in the repository).
5. **Contract release** (`contract.py build --release`, tag `conformance-2.0.0`) is not done and needs the items above; it needs your approval.

### 5.3 Versioning and operations
1. **API contract number.** This change set added a `calendar_error` key and fixed a 500 inside contract 1.7.0. If 1.7.0 was already consumed externally (the repository has no tags and no usage data; `render.yaml` shows a deployment), the owners may want 1.8.0. I kept 1.7.0 to avoid rewriting immutable recorded SDK vectors.
2. **External consumption of 1.7.0 is unknown**; notifying known consumers is the owners' call.
3. **Packages are built, not published.** No registry upload, tag or GitHub release was made; SDK, `waqt-api-consumer` and docs do not claim a published package.
4. **Core callers outside 1700..2300** now get an empty Hijri label (with `calendar_error`) where they previously got an arithmetic-tabular label (documented in the changelog and migration record).

### 5.4 Known differences that remain visible, not caused by this work
Of the 19 reference-vs-independent verdict differences, 17 are in the committed baseline (informative/open tiers, for example `uaq/year-table/1420` and `/1446` month lengths, `interop/instant/one-second-before-maghrib`, `interop/boundary/ends-exactly-at-maghrib`, `waqt/london-long-day-near-24h-boundary`, `live/15-kiritimati-day_bounds`, `aladhan/retry-after-short`); 2 are the new OQ-CAL-1 vectors. None is normative.

### 5.5 Design questions I noticed and did not decide
* Whether the **fallback chains** of `aladhan`, `declared` and `local-observation` (they fall back to `arithmetic-tabular` outside their coverage, a documented provider behaviour) should follow the new default.
* Whether `GET /v1/calendar` should advertise the default provider so clients can discover it.

## 6. Reproduce
```
pip install -e . -e core -e local -e apps/cli -e apps/api-consumer -e sdks/python hijridate==2.3.0 build httpx
(cd verification/browser && npm install) && (cd apps/web/tools && npm install)
python verification/live_stack_check.py && python verification/vector_additivity_check.py
python -m pytest tests -q ; python -m pytest core/tests -q ; python -m pytest local/tests apps/cli apps/web/tests -q
(cd sdks/python && python -m pytest tests -q) ; WAQT_RUN_CONFORMANCE=1 python -m pytest tests/test_conformance_suite.py -q
(cd conformance && sh run.sh && python tools/contract.py verify && python tools/mutation_check.py)
bash verification/browser/run_web_option_b.sh && bash verification/browser/run_sprint14.sh && bash verification/browser/run_smoke.sh
```
