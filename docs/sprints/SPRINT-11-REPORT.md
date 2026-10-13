# Sprint 11 — Waqt Core Distribution & Astronomical Engine Evaluation

**Purpose:** make the computation layer independently distributable, and make the
astronomical foundation strong enough to build on.

**Headline:** Goal A is done as specified. Goal B found that most of what Sprint 10
called an inherent high-latitude accuracy limit was three bugs in the production
solver. They are fixed; the engine now agrees with a VSOP87 reference to ~1 s
(3.6 s at high latitude, was 432 s). **Published times before this sprint can be
wrong by up to ~7 minutes at high latitude near an equinox.**

Test status at close: root 473 (incl. 1 packaging smoke), `core/tests` 261 (incl. 2
packaging smoke), `local` 186 (+1 skipped), Python SDK 103, JS SDK 51, JS
consumer 184, `independent-astronomy` 26. All pass.

---

## 1. Goal A — package architecture

| Requirement | Result |
|---|---|
| Extract/install `waqt-core` | `core/` → distribution `waqt-core` 0.1.0, import `waqt_core`, deps `ephem`, `timezonefinder` only. Builds wheel + sdist. |
| `waqt.api` depends on it | Root `pyproject.toml` (new): distribution `waqt-api` 0.1.0 depends on `waqt-core`, `fastapi`, `uvicorn`. |
| `waqt_local` depends on it | `waqt-local` 0.2.0: imports `waqt_core` directly; `dependencies = ["waqt-core>=0.1.0,<0.2"]` (was `[]` — an undeclared checkout-only coupling). |
| Preserve behavior | Move verified byte-identical with `diff` before any other edit. Behavior changes are only the three `solar.py` fixes (§2), made afterwards and measured separately. |
| Preserve public imports | `waqt.core`, `waqt.scheduling.model`, etc. all still import, including deep imports. |
| No duplicated computation | `waqt/__init__.py` registers every old name in `sys.modules` as the **same module object**; no `waqt/core.py` exists to shadow it. `core/tests/test_shim_identity.py` asserts `waqt.X is waqt_core.X` for 23 modules, symbols, literal deep-import statements and attribute access (26 tests). |
| Clean-install tests | `core/tests/test_packaging_smoke.py`: wheel **and** sdist install into a fresh venv away from the checkout, run a real computation, and `fastapi`/`waqt`/`waqt_local` are not importable there. `tests/test_packaging_smoke.py`: `waqt-api` + `waqt-core` wheels install together and serve a real `/v1/waqt`. |
| Conformance tests | The four public vector suites (waqt, scheduling, institutional, calendar-interop) run against `waqt_core` alone in `core/tests`. |

Design note: aliasing only the *package* would let Python re-find `model.py` via the
package `__path__` and execute a second copy under the old name — two classes,
same name, different identity. Every submodule is therefore aliased explicitly.

Also changed: `requirements.txt` (editable `core/`, `.`, `local/`), CI (separate steps
for root, `core`, `local`, `independent-astronomy`, packaging), `docs/PACKAGING.md`
(new), `docs/RELEASING.md`, `README.md` tree (was stale back to Sprint 7),
`docs/LOCAL.md`, `local/README.md`, `local/CHANGELOG.md`, `core/README.md`,
`core/CHANGELOG.md`.

**Consequence you should know:** the "core.py/solar.py hashes unchanged for N
consecutive sprints" discipline ends here. Both files moved, and `solar.py`
changed content on purpose. `tests/test_institutional.py::TestArchitecture` was
re-pointed to `core/waqt_core/` (it only ever asserted readability, not a pinned hash).

## 2. Goal B — astronomy evaluation

Full write-up, tables and reproduction: `docs/ASTRONOMY-ENGINE-EVALUATION.md`.
Summary:

**Bug 1 — refinement epoch.** `_event_time` used `_jdn(d) + fraction`, but `_jdn`
is JD at *noon*; the `− 0.5` was missing, so the sun was sampled 12 h from the
instant being solved. Confirmed against a known JD (2000‑01‑01 12:00Z = 2451545.0).
At Tromsø near the equinox this gave a 694″ declination error (Level B: 4.4″);
hour angle is ~865× more sensitive to declination there than at the equator.

**Bug 2 — transit/Asr sampling.** Declination and equation of time were sampled at
UT noon, not the transit instant (up to 12 h off at extreme longitudes). Found
because the residual after Bug 1 was concentrated in Dhuhr (15.5 s) and Asr
(52.5 s) at extreme-longitude rows. *Correction to my own mid-sprint reasoning:* I
first attributed that residual to NOAA's inherent precision; it wasn't.

**Bug 3 — polar-threshold existence.** Whether a marginal event exists was decided
from UT-noon declination, flipping defined↔undefined on threshold days. Checked
against physical truth (`threshold_truth.py`: scan of the sun's true altitude), not
against Levels A/B, because their solving loops give up early and are not a
trustworthy oracle there. Scan of 19,125 event-days: of 8 sunrise/Maghrib
disagreements, the production engine matches physics on **8/8**; A and B are wrong
on 8/8. The 6 Asr disagreements are ill-conditioned tangencies (sun's peak within
0.0001–0.0023° of the Asr altitude).

**Result** (production vs Level A, matrix max, seconds):

| Band | Sprint 10 | Now | Level B |
|---|---|---|---|
| equator | 19.8 | 0.9 | 1.7 |
| tropics | 31.7 | 1.0 | 1.7 |
| mid‑lat N | 40.1 | 1.0 | 1.8 |
| mid‑lat S | 47.8 | 1.0 | 1.9 |
| high‑lat | 432.1 | 3.6 | 4.3 |

Latitude sweep 0–80° (19 Sep): 260.9 s → 0.95 s. Equinox sweep ±60 days at Tromsø:
253.9 s → 3.05 s. I had predicted the old error would peak at the equinox; the
sweep showed a ~116 s plateau growing toward the seasonal extremes instead.

**Expanded matrix:** 16 locations (added Reykjavik, Anchorage, Punta Arenas,
Ushuaia, Suva, Kiritimati, Svalbard) × 5 dates, plus the two sweeps and the
threshold scan. Committed before/after snapshots are in `independent-astronomy/vectors/`.

### Production-engine decision (for your review)

- **Keep `waqt_core.solar`, corrected. Do not swap to Level B.** It's now equal or
  better in every band, ~2× faster (0.12 vs 0.26 ms/day), right on threshold days
  where B is wrong, and already wired into the API, local library and all vectors.
  Level A stays a reference only (~60 ms/day).
- **API label unchanged** (`waqt-noaa-low-precision`, accuracy level `B`). The
  measured ~1 s meets the numeric Level‑A definition, but relabelling changes
  every response's public contract, and the evidence is one reference and
  essentially one year. **Open question for you: promote to Level A now, or first
  extend to other years / a JPL reference?**
- **Recommended next:** an engine *revision* field in the API `computation` block.
  Output times moved by up to minutes under an unchanged engine string.

## 3. Changes to existing tests and artifacts (all deliberate)

- `tests/test_institutional.py`: 3 structural checks re-pointed to `core/waqt_core/`.
- `tests/test_scheduling.py`, `tests/test_schedule_api.py`: hard-coded expected
  `"00:19:21"` → `"00:19:02"` (it encoded the Bug 1 value; matches regenerated vectors).
- All vector generators re-run: `waqt`, `scheduling`, `calendar_interop`, SDK
  conformance vectors changed; `institutional` did not (no solar dependence).
  Diffs reviewed, none hand-edited. JS consumer/SDKs pick them up from the shared files.
- `independent-astronomy`: committed comparison outputs regenerated; tolerances
  tightened twice (e.g. high‑lat 450 → 8 s, others 15–55 → 3 s), each after
  measuring. Sprint 10's test `…level_b_agrees…much_more_tightly_than_waqt_does`
  was **inverted** (now: production ≤ Level B), with the reason in its docstring.
- Sprint 9/10 docs that called the high-latitude gap "a real geometric effect" /
  "not a bug" carry correction notes (`ASTRONOMY.md`, `INDEPENDENT-ASTRONOMY.md`,
  `independent-astronomy/README.md`, `SCOPE.md`). I did not edit the Sprint 9/10
  reports themselves.
- New tests: `core/tests/test_solar_epoch_regression.py` (29; I confirmed the
  epoch tests fail when Bug 1 or Bug 2 is reintroduced), `test_sprint11_matrix.py`,
  `test_threshold_truth.py`.

## 4. Honest limitations

- One reference (VSOP87 via `pymeeus`), essentially one year; ΔT is the project's
  own provider. No JPL comparison.
- A ~1 s floor against Level A appears in both Level B and production. I did not
  investigate its source.
- Production and Level B share the same mean-element series, so their agreement is
  weaker independence evidence than it looked; Level A is the only fully
  independent check.
- Threshold scan covers latitudes 60–85° in four lon/season configurations, not
  all longitudes/years. Fajr/Isha threshold days were compared between engines
  but have no truth scan.
- The `astral` comparison table in `docs/ASTRONOMY.md` was not re-measured (tests
  still pass against its looser tolerances).
- Nothing is published to PyPI/npm (credentials). Install `waqt-core` before
  `waqt-api`/`waqt-local`.
- Environment gotchas, not regressions: JS SDK tests spawn `python3`, so run them
  with the environment that has `waqt-core` installed first on `PATH`; run
  `core/tests`, `tests/` and `local/tests` as **separate** pytest invocations
  (same-named files collide; CI already does); Python SDK async tests need
  `pytest-asyncio`; the `slow` marker is unregistered (as in Sprint 10).

## 5. Verify

```bash
pip install -r requirements.txt pytest-asyncio
pytest tests/ --deselect tests/test_packaging_smoke.py
pytest core/tests/ --deselect core/tests/test_packaging_smoke.py
pytest local/tests/
pytest core/tests/test_packaging_smoke.py && pytest tests/test_packaging_smoke.py
(cd independent-astronomy && pytest tests/)
(cd consumers/js && npm test)
pytest sdks/python/tests && (cd sdks/js/waqt-client && npm test)
```
