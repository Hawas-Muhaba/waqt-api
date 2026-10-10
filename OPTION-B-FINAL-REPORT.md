# Option B final report: `umm-al-qura` as the default Hijri calendar provider (API 1.7.0)

Branch `feature/umm-al-qura-default-option-b` (based on `febea91`), 2026-10-10. Every result below was produced **fresh in this session** after the last code change; nothing is carried over from an earlier report. No package was published, no release created, nothing merged into a protected branch.

**Recommendation: YELLOW.** Every runnable gate passes and the decision records are ratified, but the conformance contract is still an unreleased 2.0.0 (ERR-004 lacks normative vectors; 12 specification questions are open), the ratification has no signed artifact in the repository, and three owner decisions remain (section 11). GREEN is not claimed.

## 1. Files changed
Roughly 70 files (see `git diff --stat`). By area:
* **API** (`waqt/api/`): `providers.py` (`provider_identity()`), `conversions_endpoint.py`, `institutional_endpoint.py`.
* **Offline facade / CLI**: `local/waqt_local/providers.py` + `facade.py` (one `DEFAULT_CALENDAR_PROVIDER`, replacing 14 hard-coded literals; provider block mirrored), `apps/cli/waqt_cli/main.py` (+ README, tests).
* **Web** (`apps/web/`): `assets/js/pages/live-demo.js` (picker), `assets/css/components.css` (mobile overflow), `assets/js/config.js`, generator `tools/pages_{a,b,c}.py`, regenerated `governance.html`/`index.html`/`api.html`, web tests.
* **Verification**: `verification/expected_versions.py`, `vector_migrations.py` + `vector_migrations/api-1.6.0-to-1.7.0.json`, `live_stack_check.py`, `vector_additivity_check.py`, `browser/run_web_option_b.{mjs,sh}` (new), `browser/run_sprint14.mjs`, `browser/run_smoke.{mjs,sh}`.
* **Vectors / tests**: `sdks/vectors/sdk_conformance_vectors_api_1_7.json` + generator (new; the historical file is untouched), `tests/test_default_provider_option_b.py` (new, 152 tests), updated local / CLI / Python-SDK tests.
* **Governance / docs**: `conformance/decisions/DR-0001..0008` (ratification field), `DR-0009` (new), `MAINTAINERS.md`, `conformance/CHANGELOG.md`, `docs/migrations/API-1.7.0-default-provider.md` (new), `docs/{API,CALENDARS,VERSIONING}.md`, `SCOPE.md`, `CONTRIBUTING.md`.

## 2. Default-provider behaviour by endpoint
Omitted → `umm-al-qura`; explicit `umm-al-qura` → same; explicit `arithmetic-tabular` → that provider; unknown name → `400 UNKNOWN_CALENDAR_PROVIDER`; the response names the provider used. Every row is covered by `tests/test_default_provider_option_b.py` (omitted / explicit / other / invalid / named / deterministic) and a matrix test fails if a new provider-aware route is added without being listed.

| Endpoint | Omitted-provider result | Names provider in response |
|---|---|---|
| GET /v1/waqt, /v1/hijri | umm-al-qura | `hijri.provider` |
| GET /v1/conversions (both directions) | umm-al-qura | `calendar_provider` (**added in 1.7.0**; to-hijri also via `hijri.provider`) |
| GET /v1/calendar/convert | umm-al-qura | `calendar_provider` |
| GET /v1/schedule/snapshot, /span; POST /v1/schedule/resolve | umm-al-qura (labels only) | `calendar_provider` |
| GET /v1/institutional/week, /fiscal-year, /academic-year; POST …/fiscal-year/resolve, …/academic-year/resolve | umm-al-qura | `calendar_provider` (**added in 1.7.0**) |
| GET /v1/institutional/profile | umm-al-qura (`demo-umm-al-qura`) | profile name + `calendar_provider` |
| /v1/day, /v1/events, /v1/location, /v1/calendar/boundary-crossing, /v1/calendar, /v1/version, /v1/health | no provider (unchanged; tested provider-free) | n/a |

Canonical Waqt time is independent of the provider: a seven-location grid test (including either side of Maghrib, the date line, high latitude) shows day, instants, events and position identical after removing Hijri labels; the browser harness checks the same on screen.
Other defaults that follow the rule: `waqt_local`, the `waqt` CLI. Waqt Web sends `umm-al-qura` explicitly and shows the provider and Hijri date exactly as the response states them.

## 3. Versioning decision and rationale
**API 1.7.0 is kept**, as the owners agreed. Findings behind that: the versioning text that permits behaviour changes ("behavior changes are explicitly documented/versioned") was introduced in the same commit as the behaviour change; the repository has no git tags and `render.yaml` shows a deployed API, so external use of 1.7.0 cannot be ruled out. The owners' ratification (DR-0009) settles the rule: the `/v1` guarantee covers response shapes and explicitly selected behaviour; the omitted-provider default may change only by owner decision, in a new API version, with a migration record, versioned vectors and preservation instructions (`docs/VERSIONING.md` section 4). Callers that need stability pin `calendar_provider`. Contract 2.0.0 is unchanged: it defines no default provider.

## 4. Disposition of the 11 changed recorded responses
All eleven omit the provider and were recorded under the old default. All are **expected consequences of the approved change**; none is an implementation bug, serialization difference or regression. No astronomy output moved (tested: after removing Hijri labels, old and new recordings are identical). The historical file is not rewritten: a declared migration replays them with `calendar_provider=arithmetic-tabular` and requires the recorded responses to be reproduced exactly; new vectors record the 1.7.0 default. Per-vector table: `docs/migrations/API-1.7.0-default-provider.md` section 5. Highest risk: `conversions-to-gregorian` (1448-04-07 → 2026-09-18, was 2026-09-20); also `institutional-profile` (name follows the default).

## 5. Live-stack (`verification/live_stack_check.py`): **PASS, 35/35**
Includes: API version on `/v1/health`, `/v1/version`, `meta`, degraded health and error envelopes against the **documented** version (read from `docs/VERSIONING.md`, never from the code under test; a unit test proves 1.6.0 and 9.9.9 are rejected), historical vectors (11 replayed under their declared provider), new-default vectors, provider selection on a real socket, and canonical-time independence.

## 6. Vector additivity: **PASS**
"no recorded value changed or disappeared"; the migration is declared, listed and printed. `--no-migration` still shows the raw 88 differences, so the checker was not loosened. A listed vector that already names a provider is refused.

## 7. Browser verification (real HeadlessChrome 153; CORS enforced; assertions executed, not just launched)
| Harness | Result |
|---|---|
| `run_web_option_b.sh` (new; live-demo + Experience Lab, desktop 1280 and mobile 375) | **PASS 58/58** (stable on repeated runs; a minimum-assertion guard exits non-zero if too few ran) |
| `run_sprint14.sh` (retargeted to `reference-viewer.html`) | **PASS 16/16** |
| `run_smoke.sh` (retargeted; versions read from the docs) | **PASS 36/36** |

Option B harness covers: loading state; success with Hijri date and provider equal to the API response, checked independently at the same instant; explicit provider request; the deliberate-default note; provider switch moving no Waqt instant and restoring afterwards; server authority (tampered response shown as received); API failure and browser-offline fallback visibly labelled as a frozen recorded sample; recovery by retry; the Lab listing the opening Maghrib's following Isha before Fajr (checked against the API's own Isha instant, live and demo, desktop and mobile); no horizontal overflow on every site page at 375px. Screenshots are in `verification/browser/results/`.

## 8. Test results (all fresh)
| Suite | Result |
|---|---|
| Root `tests/` | PASS 785 passed, 2 skipped (the 2 skips are the conformance suite, which is env-gated and **was run separately: PASS 2/2** with `WAQT_RUN_CONFORMANCE=1`) |
| Core `core/tests` | PASS 394 |
| `local/tests` | PASS 193 passed, 1 skipped (declared-provider scenario, covered in the root suite by design) |
| CLI / web Python / API consumer | PASS 20 / 37 / 9 |
| Independent astronomy | PASS 36 |
| Python SDK | PASS 108 |
| JS: web / JS SDK / consumers | PASS 42 / 55 / 184 |
| Contract verify | PASS (0 problems; the 2 warnings below are deliberate and visible) |
| Reference vs independent conformance | PASS: reference 701/0, independent 704/0 normative; 17 informative verdict differences, identical to the committed baseline |
| Doc counts / portability | PASS ("counts are current") |
| Packaging and clean-install | PASS: core 2, root 1 (run separately: same-named test files collide in one pytest invocation) |
| Independent Hijri oracle (`hijridate==2.3.0`) and API-consumer-vs-live-API tests | PASS (previously skipped for missing prerequisites) |

Mutation check: reverting `DEFAULT_CALENDAR_PROVIDER` makes 46 of the new tests fail.

## 9. Remaining normative / governance issues (kept visible, not weakened)
* ERR-004 is a MUST without normative vectors (contract verify warning).
* 12 specification questions remain unresolved: OQ-TIME-1/2/3, OQ-TAB-2/3, OQ-DT-1, OQ-UND-1, OQ-UAQ-2, OQ-ERR-1, OQ-PRV-1/2/3. None was resolved by this change.
* The contract is **unreleased** (`"released": false`). Ratified decision records are not a release.
* DR-0001..0008 now record ratification by Dr. Salim Muhammed Redi (Maintainer) on 2026-10-10, and DR-0009 records Option B. **This is recorded on the requester's report; the repository holds no signed artifact.** The independent-implementation reviewer role is still unfilled.

## 10. Checks blocked by the environment
None. Nothing is BLOCKED or NOT RUN. Notes: the Hijri oracle and API-consumer tests needed `pip install hijridate==2.3.0` and `pip install -e apps/api-consumer`; browser runs need `npm install` in `verification/browser` (the harness uses the `@sparticuz/chromium` build).

## 11. Owner decisions still required
1. Whether `waqt-core`'s internal fallback (`calendar_interop._DEFAULT_PROVIDER`, still `ArithmeticTabularProvider`; used only when a core caller passes no provider) should follow the API default. Deliberately not changed: it is tied to contract 2.0.0.
2. Version bumps and changelog entries for `waqt-local` (0.5.0) and `waqt-cli` (0.1.0), whose defaults now follow the API (release step, not performed).
3. Whether to attach a signed ratification artifact, and whether to notify known external consumers of 1.7.0 (usage is unknown).

## Bugs found and fixed along the way
Provider picker showed `arithmetic-tabular` while `umm-al-qura` was in use (Apply would silently switch it) · mobile horizontal overflow on live-demo (872px) and Lab (687px) · offline facade defaulted to the old provider (19 local-vs-server tests failing at HEAD) · CLI default · six response shapes did not name the provider · stale `config.js` comment, `CALENDARS.md` "(default)" heading, SDK-version table row and web text · live-stack comparison too strict for additive keys · Sprint 13/14 harnesses: wrong target page, unshifted Node clock for boundary scenarios, `innerText` vs CSS uppercase, hard-coded stale versions (1.5.0 / 0.3.0 / 1.1) · stale expectations in local, CLI and Python-SDK tests.

## Reproduce
```
pip install -e . -e core -e local -e apps/cli -e apps/api-consumer -e sdks/python hijridate==2.3.0
(cd verification/browser && npm install) && (cd apps/web/tools && npm install)
python verification/live_stack_check.py && python verification/vector_additivity_check.py
python -m pytest tests core/tests local/tests apps/cli apps/web/tests -q          # run core/tests and tests/ separately if names collide
bash verification/browser/run_web_option_b.sh && bash verification/browser/run_sprint14.sh && bash verification/browser/run_smoke.sh
(cd conformance && sh run.sh) && python conformance/tools/contract.py verify
```
