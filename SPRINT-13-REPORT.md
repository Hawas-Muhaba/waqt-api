# Sprint 13 — Verification Closure, Astronomy Evidence & Release Hardening

**Base:** `waqt-api-sprint12-src.zip`. **Nature of the sprint:** verification and evidence. The astronomy
engine (`solar.py`, `timescale.py`), the HTTP contract (`waqt/api/common.py`, API 1.4.0) and `waqt-local`'s
facade are **byte-identical** to the upload (checked with `cmp`); engine revision stays `2`, accuracy level stays `B`.

Environment: Python 3.12, Node 22, ephem 4.2.1, timezonefinder 9.0.0, fastapi 0.141.1, pydantic 2.13.5,
uvicorn 0.54, pytest 9.1.1, httpx 0.28.1, PyMeeus 0.5.12, skyfield 1.55, jplephem 2.24, de421 2008.1,
headless Chrome 153. Sandbox clock: 2026-09-30.

## 0. Result at a glance

| Suite | Sprint 12 (as reported) | Sprint 13 |
|---|---|---|
| core | 122 failures / stubs | **282 passed** |
| local | — | **186 passed**, 1 skipped (by design) |
| root (API, packaging, version audit, live consumer) | 10 failures | **483 passed** |
| Python SDK (live uvicorn) | not run live | **103 passed** |
| JS SDK (live server) | not run live | **51 passed** |
| JS independent consumer | passed | **184 passed** |
| CLI / API consumer / web (structural) | passed | **19 / 9 / 7 passed** |
| independent-astronomy | — | **36 passed** |
| `verification/live_stack_check.py` (real sockets) | — | **17/17** |
| `verification/browser/run_smoke.mjs` (real Chrome) | not run | **34/34** |

Run against the tree as shipped. CI configuration was updated but not executed on GitHub.

## 1. Defects found by real execution (and fixed)

| # | Defect | Found by | Fix |
|---|---|---|---|
| D1 | Calendar-interop vector `non-leap-century-1900` used Addis Ababa; its 1900 civil offset is a local-mean-time value that differs between tz-database releases (9320 s here vs 8836 s in the Sprint 12 capture). Not reproducible across environments. | first real core/local/root run (3 failures) | Case moved to London (offset 0 in 1900); `VECTOR_SET_VERSION` 1.0 → **1.1**; `waqt-core` 0.2.0 → **0.2.1**. Recorded, not normalised silently (§3). |
| D2 | `tests/test_packaging_smoke.py`: both wheels were built into one directory and the helper returned `whls[0]`, so "the API wheel" could be the core wheel. The clean-install venv then lacked FastAPI. | root suite | Separate output dirs + name assertion. |
| D3 | Six vector-conformance tests read `summary["fail"]`; Node's TAP output omits the line when there are zero failures. | JS consumers under real Node | `summary.get("fail", 0)`. |
| D4 | **`apps/web` never left a finished Waqt day.** After Maghrib it made no request and kept the old day; the highlighted next event never advanced. (Reproduced in real Chrome: clock stuck at `23:59:32`, 1 `/v1/waqt` call.) | browser run, check 9b | `tick()` re-asks the server when the server-reported day length or next-event instant has passed (`refreshPlace()`); event-driven, no polling, no client-side computation. After fix: `23:59:18 100%` → `00:00:07 0%`, day range advanced, 2 calls. Pinned by a structural test that forbids arithmetic in the refresh path. |
| D5 | `apps/api-consumer/tests/test_against_fake_server.py` references `tests/test_api_consumer_against_live_api.py`, which did not exist. | audit | Created; runs the consumer + installed console script against real uvicorn. |
| D6 | `docs/PACKAGING.md` listed `waqt-core 0.1.0`, `waqt-api 0.1.0`, `waqt-local 0.2.0`; `docs/VERSIONING.md` had no notion of the `waqt-api` **package** version (0.2.0) as distinct from the **API** version (1.4.0). | new `test_version_consistency.py` | Corrected and documented. |
| D7 | CLI test tolerated `umm-al-qura` failing ("no ephem in this sandbox"). | audit | Now requires exit 0 and real output. |
| D8 (harness, mine) | The packaged Chromium starts with `--disable-web-security`, which made my first CORS "pass" meaningless. | noticed when response headers lacked `access-control-allow-origin` yet fetch succeeded | Flag stripped; check 1d is a negative control (disallowed origin is blocked); 1e is a positive control. |

## 2. Goal A — real stack

* Server: `uvicorn waqt.api:app`, real HTTP, no `TestClient`, no stubs in `live_stack_check.py`.
* `GET /v1/version`: envelope `{meta,data,error}`, `computation` equals `waqt_core.versioning.computation_identity()`; the axes come back as distinct values (core 0.2.1, API 1.4.0, engine revision 2, vector set 1.1); `waqt_local_version` is `null` from the server.
* CORS: absent by default; with `WAQT_CORS_ORIGINS` the allowed origin is echoed, a disallowed one is not, preflight `OPTIONS` returns 200, and CORS headers are present on error responses. Enforcement additionally proven in a browser (§6).
* Validation paths through real Pydantic/FastAPI: `lat=abc` and `lat=95` → 422 `VALIDATION_ERROR`; bad instant → 400 `INVALID_INSTANT`; missing params → 422; unknown route → 404.
* SDK live tests (Python 103, JS 51) use real servers. The in-repo fake-server tests are retained as *additional* HTTP-handling tests; they are not part of the verification claim.

## 3. Goal B — vector regeneration

Generators run unchanged (except D1's one case). `tests/vectors/diff_vectors.py` (new, committed) diffs by JSON path, keyed by case id, with numeric/timestamp deltas.

| File | Structural differences vs Sprint 12 | Explanation |
|---|---|---|
| `waqt_vectors.json` | `generated_at`, `vector_set_version` | timestamp; 1.0 → 1.1 |
| `scheduling_vectors.json` | same two | same. (Also byte-different: the upload used CRLF line endings, regeneration writes LF; content identical.) |
| `institutional_vectors.json` | `vector_set_version` | frozen tables; `astronomy_dependent: false`, `generated_at_computation: null` |
| `calendar_interop_vectors.json` | above + 3 leaves in `non-leap-century-1900` (`utc_offset_seconds`, `time_of_day`, context) | D1: **the only intentional content change**; new expected offset 0 for London |
| `sdk_conformance_vectors.json` | `generated_at` timestamps, `vector_set_version`, the `computation` blocks | Sprint 12 restamped this file by transformation; Sprint 13 re-captured it from the real app. Result: identical to the transformed file except the above. So the Sprint 12 transformation was correct. |

No astronomy-dependent expected value moved. `generated_at_computation` = `{engine: waqt-noaa-low-precision, revision: "2", accuracy_level: "B"}` in the four astronomy-dependent files; `astronomy_dependent` is `true` for those and `false` only for institutional (both asserted by `test_version_consistency.py`). The `core/tests/test_engine_revision.py` fingerprint pin passes unchanged. Conformance: live API ↔ 21 SDK vectors (real HTTP), local library ↔ vectors (core/local conformance tests), Python and JS SDKs ↔ live server, independent JS consumer ↔ vectors — all pass.

`sdks/vectors/restamp_sdk_vectors.py` is now historical (documented in `VERSIONING.md` §5).

## 4. Goal C — multi-year Level-A/Level-B study

`independent-astronomy/compare_sprint13.py` calls Sprint 12's `run()` unchanged: seven years (2019, 2022, 2023, 2026, 2027, 2030, 2033) × `NAMED_LOCATIONS` (16 sites) × 5 dates × 6 events = 560 rows, 3,045 defined event-instances. **Reproducibility: 0 of 16,170 compared fields differ from the committed Sprint 12 output.** Tolerances untouched; zero tolerance failures under the (stale) legacy tolerances.

| Comparison | max | mean | median | mean signed |
|---|---|---|---|---|
| Waqt − Level B | 1.710 | 1.083 | 1.342 | +0.252 |
| Waqt − Level A | 9.427 | 1.401 | 1.375 | +0.835 |
| Level B − Level A | 7.915 | 0.768 | 0.705 | +0.582 |

Per band and per event tables, high-latitude per-location breakdown and the polar breakdown are in `docs/ASTRONOMY-SPRINT13.md` §2–§3 and the JSON. Headlines: non-polar bands ≤ 3.39 s; high-latitude max 9.427 s (Tromsø Fajr 2019-09-19, all top-5 rows are Tromsø Fajr near the September equinox). Polar (Longyearbyen): 210 event-instances, all four engines agree on existence in every one.

## 5. Goal D — independent reference (JPL DE421 + Skyfield)

`independent-astronomy/skyfield_reference/` — Sun/Earth from JPL DE421; apparent place, aberration, IAU 2006/2000A sidereal time, UT1/TT from Skyfield; own root finder; shares with Waqt only the event *definitions*. Independence is a tested property (AST import check + no series constants). Because NAIF was unreachable, the `de421` PyPI package (JPL's DE421 in jplephem's legacy format, converted through small `VectorFunction` adapters, Earth = EMB − Moon/(1+EMRAT)) was used.

Matrix = the same 560 rows (equatorial, tropical, mid-lat N/S, high-lat N/S, Svalbard polar, 7 years, all seasons sampled, all six events), plus:

| Result | Value |
|---|---|
| **Level A − JPL**, max / mean | **0.259 s** / 0.081 s (0.17 s outside the high-lat band) |
| Level B − JPL, max | 7.831 s |
| **Waqt − JPL**, max / mean / median | **9.343 s** / 1.436 / 1.396 (bands: equator 2.78, tropics 3.07, mid-N 3.21, mid-S 3.25, high-lat 9.34) |
| Parallax sensitivity (topocentric − geocentric) | ≤ 1.02 s outside high-lat; up to 16.2 s at high latitude |
| Polar existence, 4 engines | 210/210 agree |

**Dense scans** (every day of a year, six events, Waqt vs JPL) — beyond the required matrix, added because the 5-dates-per-year matrix cannot see grazing-Sun days:

| Site | max | p95 |
|---|---|---|
| Reykjavik 2019 | 9.48 s | 2.88 |
| Tromsø 2019 | 22.02 s | 3.41 |
| Tromsø 2026 | 24.58 s | 3.87 |
| Longyearbyen 2026 | **43.50 s** | 5.01 |

Every large time error is a small angle over a flat curve: 0.1–17″ of Sun position (`worst_case_analysis_sprint13.json`), e.g. 43.5 s = 8.2″ ÷ 0.183″/s. Two existence disagreements in 8,760 scanned event-days (Tromsø 2026-09-17 Fajr, margin 0.55″; 2019-11-23 Asr, margin 0.06″) are sub-arcsecond knife-edges and Waqt errs closed.

## 6. Goal E — real browser

Headless Chrome 153 (`@sparticuz/chromium` + `puppeteer-core`, with its security-disabling flags removed), `apps/web/index.html` served from `localhost:8080`, real API on `localhost:8000` with `WAQT_CORS_ORIGINS=http://localhost:8080`. `manual_smoke.md` items 1–8 are covered; details: `verification/browser/results/browser_smoke_results.json` and screenshots.

| Requirement | Result |
|---|---|
| Manual coordinates: Addis Ababa, Makkah (second normal-latitude), Reykjavik (high-lat), lat 78 | pass; timeline of six events in order, no `NaN`/`undefined` text |
| Geolocation granted / **denied** | granted fills coordinates and loads; denied shows "Location denied … Enter coordinates manually", then manual entry still works, no page errors |
| Waqt clock ticks, zero extra network calls | `09:23:49 → 09:23:51`, calls 3 → 3 |
| Day-progress ring, Gregorian, Hijri, Waqt representation cards | present and consistent |
| Provider switch | Hijri changes (17 → 19 Rabi al-Thani 1448) with the provider name; event instants identical |
| Metadata | engine `waqt-noaa-low-precision` r2, accuracy B, ΔT 75.511 s, provider+version, core 0.2.1, API 1.4.0, vector set 1.1 (@ r2) |
| API errors | `VALIDATION_ERROR` shown, content hidden; wrong port → legible "Could not reach … WAQT_CORS_ORIGINS" |
| Loading | "Loading…" shown and stale content hidden while a request is held |
| Polar | with the page clock shifted to 21 June: "Waqt is undefined here … polar day or polar night", content hidden; a normal place afterwards renders fully. Today's date at 78°N is (correctly) *not* undefined. |
| Boundary transition | Maghrib: new Waqt day fetched (D4). Next event: highlight advanced Dhuhr → Asr with a re-request. |
| CORS | allowed origin works; **negative control** (`127.0.0.1:8080`) is blocked by the browser |
| Console | zero errors/page errors in all runs |
| Narrow (380 px) | no horizontal overflow |
| Consumer discipline | structural test unchanged in spirit and extended (D4); page calls only `/v1/waqt`, `/v1/calendar`, `/v1/version` |

CLI: `waqt` and `waqt-api-consumer` installed as real console scripts and exercised (`waqt --json now …`; consumer against real uvicorn).

**Limits of the browser evidence:** headless Chrome only (no Firefox/Safari, no real device geolocation prompt UI — permission states are driven through Chrome's permission override), and boundary tests shift the page's clock rather than waiting for real sunset.

## 7. Goal F — release/documentation consistency

* `core/CHANGELOG.md`: 0.2.1 (Sprint 13) and the missing 0.2.0 (Sprint 12) added. `local/CHANGELOG.md`: missing 0.3.0 added, plus a note that Sprint 13 made no `waqt-local` change. SDK changelogs already matched their versions (0.3.0 / 0.3.0); now checked mechanically.
* `tests/test_version_consistency.py` (7 tests): each version has its own literal source and none is derived; pyproject/package.json = in-code; changelog top entry = current; `waqt-core` dependency ranges contain the core version; docs quote current values; every vector file stamped with the running vector-set version and (if astronomy-dependent) engine identity; SDK `MAX_KNOWN_API_VERSION` ≤ API version.
* `VERSIONING.md` (values; Sprint 13 step in the flow diagram; API-contract vs `waqt-api` package distinction; restamp note superseded), `PACKAGING.md` (table), `ACCURACY-LEVEL-REVIEW.md` (§6 + decision record), `ASTRONOMY.md` (Sprint 13 note), new `ASTRONOMY-SPRINT13.md`.
* `LOCAL.md` and `SCHEDULING.md` audited against the implementation: every `waqt_local.*` / `waqt_core.*` symbol and `/v1/*` route they name resolves; "116 vectors" matches; the pinned `01:05:31` example is asserted by a passing test. One stale-risk sentence (Sprint 5's `23:59:23` / `25:04:53` figures, captured under engine revision 1) was labelled as historical rather than silently kept.

## 8. Accuracy-level decision

**Stays `B`; no code path changed it.** Criterion 2 (independent reference) is now met and validates Level A (≤ 0.26 s from JPL). But the `ASTRONOMY.md` definition of Level A — sub-10-second agreement across the full geographic matrix — holds only on the 5-date matrix (9.34–9.43 s, 0.6 s headroom) and fails under dense high-latitude sampling (up to 43.5 s at 78°N). Tolerance recalibration (the stale 450 s) is still open. `test_accuracy_promotion_criterion_is_not_met_by_committed_evidence` will fail if the evidence ever changes, forcing the review to be reopened. Reopening conditions are in `ACCURACY-LEVEL-REVIEW.md` §6.

## 9. Definition of Done

| Item | Status |
|---|---|
| Real dependencies installed / real FastAPI exercised / API tests pass / `/v1/version` and CORS over real HTTP / live SDK tests | ✅ |
| Four astronomy vector sets + SDK vectors regenerated, diffed, every difference explained, live/local/SDK conformance | ✅ |
| Seven-year Level-A comparison; high-lat and polar analysed; independent second reference; reproducible committed artifacts; accuracy decision documented without change | ✅ |
| Web app in an actual browser; `manual_smoke.md` completed; CLI on real installed packages; API consumer on real API | ✅ (headless Chrome only; see §6 limits) |
| `core`/`local` changelogs; versioning docs match implementation; accuracy review updated; report | ✅ |

## 10. Known limitations / open items (not acted on, by design)

1. **+0.86 s mean signed bias** (Waqt − JPL, all events) and the year-dependent drift (Addis Ababa +2.8 s in 2019 vs +0.9 s in 2026). Cause not diagnosed; fixing it would be an engine revision bump.
2. Stale `TOLERANCE_SECONDS_WAQT_VS_LEVEL_A["high-lat"] = 450` left as is so results stay comparable; a proposal is in `ASTRONOMY-SPRINT13.md` §7.
3. DE421 covers 1900–2050 only; reference is the pip-packaged copy of the JPL data, not a NAIF `.bsp`.
4. The dense high-latitude scans cover four site-years, not the whole matrix.
5. The Skyfield comparison takes ~15–20 minutes to run; the committed JSON is the artifact CI relies on (`--quick` exists for smoke use).
6. CI edits (dependency install, live check, apps job) are untested on GitHub itself.
7. D4 is a change to shipped application code inside a "verification" sprint. It is a defect fix, minimal, documented and test-pinned; it does not alter Waqt semantics.

## 11. Reproduce

```bash
pip install -r requirements.txt && pip install -e ./core -e . -e ./local -e sdks/python -e apps/cli -e apps/api-consumer
pytest core/tests; pytest local/tests; pytest tests; (cd sdks/python && pytest tests)
(cd sdks/js/waqt-client && npm test); (cd consumers/js && npm test)
(cd independent-astronomy && pytest tests && python compare_sprint13.py && python compare_skyfield_sprint13.py && python analyze_worst_cases_sprint13.py)
python verification/live_stack_check.py          # then see verification/README.md for the browser run
python tests/vectors/diff_vectors.py OLD.json NEW.json
```
