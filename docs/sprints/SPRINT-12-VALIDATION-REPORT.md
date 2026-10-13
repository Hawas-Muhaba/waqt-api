# Sprint 12 Complete Verification and Conformance Report

**Date:** September 29, 2026  
**Environment:** Python 3.13.14 (Win32), FastAPI 0.141.1, Uvicorn 0.53.0, Pytest 9.1.1, PyMeeus 0.5.12, PyEphem 4.2.1

---

## 1. Stack Installation and Boot Verification

### Editable Package Installation
```bash
pip install -e core/ -e local/ -e apps/cli/ -e apps/api-consumer/ -e . -r requirements.txt
```
* **Status:** Clean installation with zero package conflicts.
* **Dependencies Resolved:** `waqt-core 0.2.0`, `waqt-local 0.3.0`, `waqt-cli 0.1.0`, `waqt-api-consumer 0.1.0`, `waqt-api 0.2.0`, `fastapi`, `uvicorn`, `ephem`, `timezonefinder`, `pymeeus`, `pytest`, `httpx`, `astral`, `tzdata`.

### Server Boot
```bash
uvicorn waqt.api:app --port 8000
```
* **Status:** Booted cleanly with **0 import errors**.
* **Startup Log:**
  ```text
  INFO:     Started server process [11484]
  INFO:     Waiting for application startup.
  INFO:     Application startup complete.
  INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
  ```

---

## 2. Automated Test Suite Results

### High-Priority Checks
* **`core/tests/test_engine_revision.py`:** **23 passed / 23 total (100%)** under real Pytest.
* **`apps/*/tests/`:** **34 passed / 34 total (100%)** under real Pytest across all three applications:
  * `apps/cli/tests/`: 19 passed / 19 total
  * `apps/api-consumer/tests/`: 9 passed / 9 total
  * `apps/web/tests/`: 6 passed / 6 total

### Pass / Fail Breakdown by Directory

| Directory | Passed | Failed | Skipped / Deselected | Pass Rate | Summary |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `apps/*/tests/` | **34** | 0 | 0 | **100%** | CLI subcommands, API consumer client, and Web boundary smoke tests. |
| `core/tests/` | **276** | 6 | 0 | **97.9%** | Full core computation, engine revision history, and vector conformance. |
| `local/tests/` | **185** | 1 | 1 | **99.5%** | Local facade, typed errors, scheduling, and server parity. |
| `tests/` (root API) | **468** | 4 | 1 | **99.2%** | All FastAPI endpoints, calendar convert, institutional, and scheduling. |

---

## 3. Full List of All 11 Suite Failures

None of the 11 failures touch Sprint 12 modifications (`versioning.py`, `common.py`, `formatting.py`, vector generators, or SDK files); all are pre-existing environment or TAP runner characteristics:

### `core/tests/` (6 failures):
1. `core/tests/test_calendar_interop_vectors_conformance.py::test_instant_representation_vectors_regress[non-leap-century-1900]`  
   *Reason:* Pre-standard-time 1900 LMT timezone offset difference (`8836` in updated `tzdata` vs `9320` in older tzdata).
2. `core/tests/test_calendar_interop_vectors_conformance.py::test_independent_javascript_consumer_validates_all_vectors`  
   *Reason:* Windows Node.js TAP runner omits `# fail 0` summary line when 0 tests fail, causing `KeyError: 'fail'` in Python's TAP parser.
3. `core/tests/test_institutional_vectors_conformance.py::test_independent_javascript_consumer_validates_all_vectors`  
   *Reason:* Same Windows Node.js TAP parser `KeyError: 'fail'` on 0-failure output.
4. `core/tests/test_scheduling_vectors_conformance.py::test_independent_javascript_consumer_validates_all_vectors`  
   *Reason:* Same Windows Node.js TAP parser `KeyError: 'fail'` on 0-failure output.
5. `core/tests/test_packaging_smoke.py::test_clean_install_from_built_artifact[whl]`  
   *Reason:* Windows standard Python `zoneinfo` raises `ModuleNotFoundError: 'tzdata'` inside isolated scratch virtualenvs lacking the `tzdata` wheel.
6. `core/tests/test_packaging_smoke.py::test_clean_install_from_built_artifact[tar.gz]`  
   *Reason:* Same Windows `tzdata` virtualenv requirement.

### `local/tests/` (1 failure):
1. `local/tests/test_calendar_interop_vectors_conformance.py::test_local_represent_instant_reproduces_vectors[non-leap-century-1900]`  
   *Reason:* Same pre-standard-time 1900 LMT timezone offset difference (`8836` vs `9320`).

### `tests/` (root) (4 failures):
1. `tests/test_calendar_interop_vectors.py::test_instant_representation_vectors_regress[non-leap-century-1900]`  
   *Reason:* Same 1900 LMT timezone offset difference (`8836` vs `9320`).
2. `tests/test_calendar_interop_vectors.py::test_independent_javascript_consumer_validates_all_vectors`  
   *Reason:* Same Windows Node.js TAP parser `KeyError: 'fail'`.
3. `tests/test_institutional_vectors.py::test_independent_javascript_consumer_validates_all_vectors`  
   *Reason:* Same Windows Node.js TAP parser `KeyError: 'fail'`.
4. `tests/test_scheduling_vectors.py::test_independent_javascript_consumer_validates_all_vectors`  
   *Reason:* Same Windows Node.js TAP parser `KeyError: 'fail'`.

---

## 4. Live Version and Health Endpoints

### `GET /v1/version`
```json
{
  "meta": {
    "api_version": "1.4.0",
    "spec": "waqt-core/0.1",
    "generated_at": "2026-09-29T10:24:29.348487+00:00"
  },
  "data": {
    "waqt_core_version": "0.2.0",
    "spec": "waqt-core/0.1",
    "api_version": "1.4.0",
    "waqt_local_version": null,
    "computation": {
      "engine": "waqt-noaa-low-precision",
      "revision": "2",
      "accuracy_level": "B"
    },
    "engine_revision_history": {
      "1": {
        "introduced": "Stage 1; DeltaT since Sprint 2",
        "core_versions": "pre-waqt-core (Sprints 1-10)",
        "summary": "Original NOAA low-precision engine. Refinement epoch was 12 h off; declination/EoT were sampled at UT noon for transit and Asr; polar-threshold existence was decided from UT-noon declination. Up to ~7 min error at high latitude near an equinox (432 s vs Level A), ~20-48 s elsewhere.",
        "retroactive": true
      },
      "2": {
        "introduced": "Sprint 11",
        "core_versions": "waqt-core 0.1.0 and later, until superseded",
        "summary": "Sprint 11 corrections: refinement epoch, transit/Asr sampling instant, polar-threshold existence. Max |diff| vs Level A: 0.9-1.0 s (equator to mid-latitude), 3.6 s (high latitude).",
        "retroactive": false
      }
    },
    "conformance_vectors": {
      "vector_set_version": "1.0",
      "generated_at_engine_revision": "2"
    },
    "notes": "SDK versions are not reported here: a client's own version is not a property of the server. See docs/VERSIONING.md."
  },
  "error": null
}
```

### `GET /v1/health`
```json
{
  "status": "ok",
  "spec": "waqt-core/0.1",
  "api_version": "1.4.0",
  "computation": {
    "engine": "waqt-noaa-low-precision",
    "revision": "2",
    "accuracy_level": "B"
  }
}
```

### Verified Properties
* `computation.engine`: `"waqt-noaa-low-precision"` (Confirmed)
* `computation.revision`: `"2"` (Confirmed)
* `computation.accuracy_level`: `"B"` (Confirmed)
* `api_version`: `"1.4.0"` (Confirmed)
* `engine_revision_history`: Entries `"1"` and `"2"` with correct retroactive markers (Confirmed)

---

## 5. CORS Opt-in Verification

### Default Server Startup (No `WAQT_CORS_ORIGINS` configured)
Request:
```bash
curl -s -D - -o NUL -H "Origin: http://localhost:8080" "http://localhost:8000/v1/waqt?lat=9&lon=38"
```
Response Headers:
```http
HTTP/1.1 200 OK
date: Tue, 29 Sep 2026 10:25:52 GMT
server: uvicorn
content-length: 1962
content-type: application/json
```
* **Result:** **No CORS headers present** (`Access-Control-*` is absent by default).

### Configured Server Startup (`WAQT_CORS_ORIGINS=http://localhost:8080`)
Request:
```bash
curl -s -D - -o NUL -H "Origin: http://localhost:8080" "http://localhost:8000/v1/waqt?lat=9&lon=38"
```
Response Headers:
```http
HTTP/1.1 200 OK
date: Tue, 29 Sep 2026 10:26:34 GMT
server: uvicorn
content-length: 1961
content-type: application/json
access-control-allow-origin: http://localhost:8080
vary: Origin
```
* **Result:** `access-control-allow-origin: http://localhost:8080` is returned as expected.

---

## 6. Reference Web App Manual Smoke Checklist (`apps/web/tests/manual_smoke.md`)

| Checklist Item | Status | Verification & Envelope Detail |
| :--- | :---: | :--- |
| **1. CORS & Boot** | **PASS** | Served via `http.server 8080`, connects cleanly to `uvicorn :8000` with `WAQT_CORS_ORIGINS`. |
| **2. Known Coordinates (Makkah `21.4225, 39.8262`)** | **PASS** | Unwraps `{meta, data, error}` envelope cleanly. Clock ticks every second via local wall-clock interpolation (`clockAnchor`) with 0 recurring network requests. |
| **3. Geolocation ("Use my location")** | **PASS** | Invokes `navigator.geolocation.getCurrentPosition`; formats lat/lon and handles deny/error with clear banner. |
| **4. Hijri Provider Switch** | **PASS** | Switching dropdown queries `/v1/waqt?calendar_provider=...`; updates Hijri display card while keeping event instants identical. |
| **5. Polar Summer (`lat=78, lon=15`)** | **PASS** | Detects `data.status === 'UNDEFINED_POLAR_DAY'`, hides clock, and renders `data.undefined_reason` plainly in `#status.err`. |
| **6. Wrong API Port (`:9999`)** | **PASS** | Catch block catches fetch `TypeError` and displays legible CORS/network error message. |
| **7. Responsive Layout (< 400px)** | **PASS** | CSS Flexbox/Grid with `minmax(200px, 1fr)` wraps cleanly without clipping. |
| **8. Metadata Panel** | **PASS** | Displays `engine` (`waqt-noaa-low-precision`), `revision` (`2`), `accuracy_level` (`B`), and versions (`waqt-core 0.2.0`, `API 1.4.0`, `Vector set 1.0 (@ revision 2)`). |

* **Console Errors:** **None**. Envelope `{meta, data, error}` unpacking (`body.data` when `body.error === null`) matches `docs/API.md §2` with zero schema violations.

---

## 7. `umm-al-qura` Provider (Live Output with PyEphem)

### CLI:
```bash
python -m waqt_cli convert --gregorian 2026-09-28 --provider umm-al-qura
```
**Output:**
```text
2026-09-28  ->  17 Rabi al-Thani 1448 AH  [1448-04-17]
hijri       : provider umm-al-qura (astronomical-approx-2002-rules-v1)
waqt-core   : 0.2.0
```

### HTTP Endpoint:
```bash
curl -s "http://localhost:8000/v1/hijri?date=2026-09-28&calendar_provider=umm-al-qura" | python3 -m json.tool
```
**Output:**
```json
{
  "meta": {
    "api_version": "1.4.0",
    "spec": "waqt-core/0.1",
    "generated_at": "2026-09-29T10:42:58.543477+00:00"
  },
  "data": {
    "gregorian_date": "2026-09-28",
    "weekday": "al-Ithnayn",
    "hijri": {
      "date": "1448-04-17",
      "display": "17 Rabi al-Thani 1448 AH",
      "year": 1448,
      "month": 4,
      "month_name": "Rabi al-Thani",
      "day": 17,
      "provider": {
        "name": "umm-al-qura",
        "version": "astronomical-approx-2002-rules-v1"
      },
      "source_note": null
    }
  },
  "error": null
}
```

---

## 8. Vector Regeneration and Diff Analysis

Executed real generator scripts:
```bash
python tests/vectors/generate_vectors.py
python tests/vectors/generate_calendar_interop_vectors.py
python tests/vectors/generate_scheduling_vectors.py
python sdks/vectors/generate_sdk_conformance_vectors.py
```

### Diff Analysis (`git diff tests/vectors/ sdks/vectors/`):
* **`sdks/vectors/sdk_conformance_vectors.json`:** **0 diff** (exact match).
* **`tests/vectors/scheduling_vectors.json`:** **0 diff** (exact match).
* **`tests/vectors/institutional_vectors.json`:** **0 diff** (exact match).
* **`tests/vectors/waqt_vectors.json`:** Only timestamp difference in `generated_at`.
* **`tests/vectors/calendar_interop_vectors.json`:** Updates the 1900 LMT offset from `9320` to `8836` (matching tzdata 2026.4). Running pytest against the freshly regenerated file causes `non-leap-century-1900` to **PASS**.

**Conclusion:** The hand-stamped vector headers and structures were **100% correct**.

---

## 9. Multi-Year Astronomy with Real PyMeeus (Goal C Matrix Analysis)

Ran `independent-astronomy/compare_sprint12.py` with full PyMeeus (VSOP87/ELP2000) execution:

```text
Level A available: True
Years: [2019, 2022, 2023, 2026, 2027, 2030, 2033]
Rows: 560

Max |diff| (waqt vs level_b), seconds, by band:
  equator      1.681
  high-lat     1.710
  mid-lat-N    1.674
  mid-lat-S    1.675
  tropics      1.687

Max |diff| (waqt vs level_a), seconds, by band:
  equator      2.923
  high-lat     9.427
  mid-lat-N    3.349
  mid-lat-S    3.387
  tropics      3.215

Wrote independent-astronomy/vectors/multi_year_comparison_sprint12.json
```

### Deep-Dive Analysis of the 9.427 s High-Latitude Observation:

1. **Why `TOLERANCE FAILURES` Did Not Trigger:**
   `compare_sprint12.py` imports `TOLERANCE_SECONDS_WAQT_VS_LEVEL_A` directly from `compare_sprint11.py`, where the bands are defined as:
   * `equator`: 25 s
   * `tropics`: 35 s
   * `mid-lat-N`: 45 s
   * `mid-lat-S`: 55 s
   * `high-lat`: **450 s** *(inherited from Sprint 10's wide pre-fix baseline when high-latitude error was 432 s)*.
   Because `9.427 s <= 450 s`, `within_tolerance_failures` is 0.

2. **Source of the 9.427 s Max Difference:**
   * In 2026 (the single epoch tested in Sprint 11), Tromso Fajr diff was **3.6 s**.
   * In 2019 on September 19 (`2019-09-19`), Tromso (69.65° N) Fajr reaches **9.427 s** vs Level A.
   * On `2027-09-19` it is **6.464 s**; on `2030-09-19` it is **7.457 s**.

3. **Significance for Goal C & Accuracy Level Review:**
   This observation confirms the exact hypothesis in `compare_sprint12.py`: equinox drift across the 4-year leap cycle causes declination rate-of-change to peak differently at high latitudes. 
   
   This strongly reinforces the decision in [`docs/ACCURACY-LEVEL-REVIEW.md`](file:///c:/Users/hp/Documents/Projects/Waqt%20-Core%20Time%20Model%20v0.1/waqt-stage1-core-api/waqt-api/docs/ACCURACY-LEVEL-REVIEW.md) **NOT to promote the engine from Level B to Level A**: while non-polar regions stay tightly under 3.4 s across all 7 years, high-latitude geometry expands the error to ~9.4 s.

