# Corrective sprint report — Hijri date, resource registry, maintainer demo config

Branch `fix/hijri-provider-resource-config` was merged to `main` as `8343180`. This report records the original
corrective sprint plus follow-up validation and the API-default decision below; it does not claim release readiness.

## 1. Root cause of "25 vs 27"
There is **no calculation defect and no offset** in the Waqt-day → civil-date → provider → API → web path. Traced
and pinned by tests:
* `compute_waqt` labels a day with the civil date of its **closing Maghrib in the location's timezone** (DR-0001) and passes
  that date to the selected provider. No UTC or server-local leakage (verified under 4 machine timezones, and at
  Los Angeles/Honolulu where the closing Maghrib falls on the next UTC date).
* The value **25 is the correct `arithmetic-tabular` output for 2026-10-08**; the repo's `umm-al-qura` provider returns
  **27**. The conventions differ by two days (arithmetic-tabular starts 1 Rabi al-Thani on 2026-09-14, Umm al-Qura on
  2026-09-12). The repo's docs already say the two can differ by 1–2 days.
* The **web app hard-coded `calendar_provider = "arithmetic-tabular"`** (`waqt-live.js`; the reference viewer preselected the
  first listed provider), and displayed the result as a bare "Hijri" date with the provider only in a minor telemetry row.
* Evidence the `umm-al-qura` provider itself is right: it matches the official Umm al-Qura table (independent `hijridate`
  package) on **all 913 days** 2025-06-01…2027-11-30; `arithmetic-tabular` differs on 590 of them.
* Follow-up decision: the API default is now `umm-al-qura`, matching the website. `arithmetic-tabular` remains available
  by explicitly passing `calendar_provider=arithmetic-tabular`; the behavior change is identified as API 1.7.0.

## 2. Files changed
Tests/tools: `tests/test_hijri_regression.py` (new, 25 tests), `tests/test_conformance_doc_counts.py` (new),
`conformance/tools/sync_doc_counts.py` (new), `conformance/spec/CONFORMANCE.md` (count now generated).
Docs: `docs/CALENDARS.md`, `docs/API.md`, `CONTRIBUTING.md` (new).
Web: `apps/web/assets/js/{config,waqt-api,waqt-live,waqt-clock,waqt-widgets,site,demo-data}.js`, `assets/js/pages/{lab,api,resources,governance,community}.js`,
`apps/web/tools/{pages_common,pages_a,pages_b,pages_c,build_pages,record_demo}.py`, all generated `apps/web/*.html`,
`apps/web/tests/{test_site_structure.py,js/site.test.mjs,js/helpers.mjs}`, `apps/web/README.md`.

## 3. Calendar-provider fix
The web now requests `WAQT_CONFIG.hijri.defaultProvider` (`umm-al-qura`), shows **date + provider** together on every
surface, and states that other providers can differ. The provider is user-selectable (Live Demo, API tester, reference
viewer). Provider choice never changes Waqt time (test: day/reading/events/next_event identical across providers).
No manual offset exists (a test scans the data flow for one).

## 4. API response before / after
`GET /v1/waqt?lat=9.0192&lon=38.7525&instant=2026-10-08T09:00:00Z` now defaults to:
* `umm-al-qura` → `hijri: {day: 27, display: "27 Rabi al-Thani 1448 AH", provider: {name: "umm-al-qura", version: "astronomical-approx-2002-rules-v1"}}`
* Explicit `calendar_provider=arithmetic-tabular` → `hijri: {day: 25, display: "25 Rabi al-Thani 1448 AH", provider: {name: "arithmetic-tabular", …}}`
Year/month/month_name/day/display/provider{name,version} are all present; documentation clarified in `docs/API.md`.

## 5. Web before / after
Before: requested `arithmetic-tabular`, showed "25 Rabi al-Thani 1448 AH" with the provider easy to miss.
After (live check in headless Chromium): "27/28 Rabi al-Thani 1448 AH · umm-al-qura" with the ambiguity note;
choosing arithmetic-tabular in the Live Demo shows the 2-day-earlier date and names that provider. No Hijri date is
hard-coded anywhere (tested; only the labelled demo fixture contains one).

## 6. Resource configuration (`apps/web/assets/js/config.js`)
One object: `api`, `hijri`, `project.repository` (`https://github.com/Hawas-Muhaba/waqt-api`, branch `main`, **private**),
`project.support` (Ko-fi), `maintainers`, `governance`, `docs`, `sdks`, `officialApps`, `communityApps`, `resources`
(the hub, in display order, support last). References are `{path}`/`{tree}` (repository-relative, resolved against the repo
URL), `{api}`, `{page}`, `{mailto}`, `{url}` only when canonical, or `{status}` (rendered **disabled**). Footer, nav, Resources,
Governance and Community all read it. A test verifies every `path`/`tree` exists in the repository.
Note: the support link is **Ko-fi** (`https://ko-fi.com/ummatidawah`) and is labelled "Support on Ko-fi", not "Buy Me a Coffee".

## 7. SDK locations
Python and JavaScript SDKs, each with four separate facts: **Source** (repo folder), **Releases** (`planned`), **Package
registry** (PyPI / npm: `not_published`), **Documentation** (SDK README). Releases/registry render disabled with status; no
package or download URL exists anywhere (tested). Hierarchy documented: repository → GitHub Releases → registries → hub.

## 8. Documentation links
`docs.{index,api,openapi,interactive,spec,semantics,calendars,astronomy,conformance,sdk,changelog,releaseNotes,contributing}`.
Markdown in the repository's `docs/` folder; OpenAPI and interactive docs are served by the running API. `releaseNotes` is `planned`
(none exist); `changelog` is the conformance-contract changelog. Links to the private repo are badged "PRIVATE REPO".

## 9. Maintainer demo metadata
Logical / Idea Owner — Dr. Salim Muhammed Redi; Technical Developer / Maintainer — Mr. Hawas Muhaba Hussein; contact
waqtapi@gmail.com; "Open to expert contributors and reviewers." Marked **DEMO · EDITABLE PROJECT METADATA** and "not a governance
approval or ratification".

## 10. Governance status (not ratified)
Governance page separates **project role information**, **formal governance decisions** (DR-0001…0008 read from the repo) and
**ratification status: "Pending project-owner approval"**. 8/8 records pending, contract 2.0.0 draft/unreleased, maintainer register unfilled.
No signature, approval or date is shown or stored.

## 11. Codex findings
* Lab next-event skipped tonight's Isha — **fixed, occurrence-aware**: `/v1/waqt` lists each event's next occurrence; the Lab now asks
  the API (day-open instant, then the event instant) and merges it; the demo fixture records those answers. Tests prove Isha → Fajr order.
* Stale requirement count — **fixed**: now generated (`conformance/tools/sync_doc_counts.py`), 71 IDs (67 MUST, 4 OPEN), guarded by a test.
* ERR-004 (MUST, no normative vector) — **tracked, not weakened**: stays MUST; a test pins that it is covered by an unresolved open question and fails if a
  normative vector appears without closing the tracking entry. A real vector is a contract change for the owner.
* Governance unratified — kept truthful (§10).

## 12. Tests — original and follow-up results
**Original sprint results (historical):** `tests/` 621 passed / 3 skipped; `apps/web/tests` 36; `apps/web/tests/js` 42;
`apps/cli/tests` 19; `apps/api-consumer/tests` 9; `sdks/js/waqt-client` 55; `conformance/independent` 13; Chromium over
all 11 pages × desktop and mobile with no console errors. The packaging smoke required `build`, which was installed.

**Follow-up PASS:** `tests/` 632 passed / 3 skipped; `tests/test_hijri_regression.py` 27 passed (including the official-table
oracle after installing `hijridate==2.3.0`), also 27 passed with `TZ=America/Los_Angeles`; `apps/web/tests` 37,
`apps/cli/tests` 19, `apps/api-consumer/tests` 9; web JS 42, JS SDK 55, independent conformance 13. The SDK integration
server used the configured Windows venv through `PYTHON`.

**Resolved blocker:** the two `tests/test_conformance_contract.py` failures reported earlier were due to the Windows-generated
manifest using backslash paths and raw CRLF-sensitive hashes. The generator now writes POSIX paths and normalizes text
line endings; all 9 contract tests pass, `contract.py verify` reports 0 problems, and generated documentation counts pass.

**Not run:** Python 3.9/CI matrix, mutation suite, dependency advisory audit, real-device/screen-reader/contrast testing.
Render was checked in the follow-up; see the deployment status below.

### Follow-up validation and default decision

The manifest staleness was caused by two Windows portability bugs in `conformance/tools/contract.py`: paths were serialized
with platform-native separators (`spec\\requirements.json` on Windows versus `spec/requirements.json` on POSIX), and source
hashes covered raw bytes, so CRLF and LF checkouts produced different digests. Manifest paths now use POSIX separators and
text hashes normalize newlines. A regression test verifies the manifest against LF-normalized inputs.

The API default change is documented as API 1.7.0. A live check before deployment of this follow-up found Render healthy
on API 1.6.0, returning `arithmetic-tabular` when omitted and `umm-al-qura` when explicitly requested; the new default
therefore requires a deployment before it is live.

## 13. Commands to run in your IDE
```
pip install -e ./core -e . -e ./local pytest httpx hijridate==2.3.0 build astral
python -m pytest tests/ -q                                  # includes the Hijri regression + packaging smoke
python -m pytest tests/test_hijri_regression.py -v
python -m pytest apps/web/tests apps/cli/tests apps/api-consumer/tests -q   # run each directory separately if names collide
(cd apps/web/tests/js && npm install && npm test)
(cd sdks/js/waqt-client && npm test)
(cd conformance/independent && npm test)
python conformance/tools/contract.py verify
python conformance/tools/sync_doc_counts.py --check
TZ=America/Los_Angeles python -m pytest tests/test_hijri_regression.py -q   # repeat under any TZ
# mutation / advisory audit / normative vectors: use the project's own commands (docs/RELEASING.md, conformance/harness)
```
Rebuild the site after editing `config.js`-independent pages: `cd apps/web/tools && npm install && python3 build_pages.py && npm run build:css`.

## 14. Remaining risks
* `umm-al-qura` here is an astronomical **approximation** that matches the official table over the checked 913 days; it is not the table itself — keep the oracle test in CI.
* API 1.7.0 deliberately defaults provider-aware endpoints to `umm-al-qura`; `arithmetic-tabular` remains available explicitly.
* The Render deployment checked above still runs API 1.6.0; deploy the updated API before expecting omitted-provider requests to switch to Umm al-Qura.
* Rotate the previously shared GitHub token and Stitch key; no secret is in any file (tested).
