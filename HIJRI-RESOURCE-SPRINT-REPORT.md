# Corrective sprint report — Hijri date, resource registry, maintainer demo config

Branch `fix/hijri-provider-resource-config` (from `feature/stitch-web-design`). Nothing merged. **This report does not
claim release readiness**; the independent audit stays authoritative until its blocked checks are run (§12–13).

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
* Left unchanged on purpose: the **API default** (`arithmetic-tabular`) — changing it would change the documented contract.

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
The API is unchanged (that is the point). `GET /v1/waqt?lat=9.0192&lon=38.7525&instant=2026-10-08T09:00:00Z`:
* default / `arithmetic-tabular` → `hijri: {day: 25, display: "25 Rabi al-Thani 1448 AH", provider: {name: "arithmetic-tabular", …}}`
* `calendar_provider=umm-al-qura` → `hijri: {day: 27, display: "27 Rabi al-Thani 1448 AH", provider: {name: "umm-al-qura", version: "astronomical-approx-2002-rules-v1"}}`
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

## 12. Tests — results
**PASS** — `tests/` 621 passed / 3 skipped (excluding the 3 below); `tests/test_hijri_regression.py` 25; `tests/test_conformance_doc_counts.py` 2;
`tests/test_packaging_smoke.py` 1 (after installing `build`); `apps/web/tests` 36; `apps/web/tests/js` 42; `apps/cli/tests` 19;
`apps/api-consumer/tests` 9; `sdks/js/waqt-client` 55; `conformance/independent` 13; headless Chromium over all 11 pages × desktop and mobile with no console errors.
Mutation check: swapping the provider for arithmetic-tabular makes 8 regression tests fail.
**FAIL** — `tests/test_conformance_contract.py` ×2: "contract.json is stale". **Fails identically on an untouched `main`**, so not caused here. I did **not**
regenerate `contract.json` (the manifest hashes may be line-ending sensitive on your Windows checkout — unverified hypothesis).
**ENVIRONMENT FAILURE (resolved)** — packaging smoke needed `pip install build`.
**NOT RUN** — Python 3.9-specific/CI matrix, mutation suite, dependency advisory audit, real-device/screen-reader/contrast testing, live Render deployment.

## 13. Commands to run in your IDE
```
pip install -e ./core -e . -e ./local pytest httpx hijridate==2.3.0 build astral
python -m pytest tests/ -q                                  # includes the Hijri regression + packaging smoke
python -m pytest tests/test_hijri_regression.py -v
python -m pytest apps/web/tests apps/cli/tests apps/api-consumer/tests -q   # run each directory separately if names collide
(cd apps/web/tests/js && npm install && npm test)
(cd sdks/js/waqt-client && npm test)
(cd conformance/independent && npm test)
python conformance/tools/contract.py verify                 # currently FAILS on main too
python conformance/tools/sync_doc_counts.py --check
TZ=America/Los_Angeles python -m pytest tests/test_hijri_regression.py -q   # repeat under any TZ
# mutation / advisory audit / normative vectors: use the project's own commands (docs/RELEASING.md, conformance/harness)
```
Rebuild the site after editing `config.js`-independent pages: `cd apps/web/tools && npm install && python3 build_pages.py && npm run build:css`.

## 14. Remaining risks
* `umm-al-qura` here is an astronomical **approximation** that matches the official table over the checked 913 days; it is not the table itself — keep the oracle test in CI.
* Repo links point at `main`; new docs/CONTRIBUTING exist only on this branch until merged. The repo is private, so links 404 for the public until it is opened.
* The API default is still `arithmetic-tabular`: other clients that omit `calendar_provider` will still see the older-convention date. Decide deliberately whether that default should change (a contract change).
* The contract/audit blocked checks (§12) remain unexecuted by me; contract.json staleness is unresolved.
* Rotate the previously shared GitHub token and Stitch key; no secret is in any file (tested).
