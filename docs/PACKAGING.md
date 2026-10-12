# Packaging architecture (Sprint 11)

Until Sprint 10 the repository shipped one combined `waqt/` package that mixed
the *computation layer* (astronomy, Hijri calendars, scheduling, institutional
calendars) with the *HTTP layer* (FastAPI). `waqt_local` (Sprint 10) sat
beside it but still reached into `waqt.*` from a repository checkout with no
declared dependency (`dependencies = []`), and nothing in the repo could be
`pip install`ed except the SDKs and `waqt_local` itself. Sprint 11 closes that.

```
                Waqt Specification
                       |
                 waqt-core  (core/waqt_core)      <- computation only
                 deps: ephem, timezonefinder
                  /                \
        waqt-api (waqt.api)      waqt-local (waqt_local)
        + fastapi, uvicorn        no other deps
              |
        Python SDK / JS SDK  (remote HTTP clients, unchanged)
```

| Distribution | Import name | Directory | Depends on |
|---|---|---|---|
| `waqt-core` 0.6.0 | `waqt_core` | `core/` | `ephem`, `timezonefinder` (the live Hijri provider uses only the standard library) |
| `waqt-api` 0.6.0 | `waqt` (only `waqt.api` is real code) | repo root | `waqt-core>=0.6.0,<0.7`, `fastapi`, `uvicorn` |
| `waqt-local` 0.7.0 | `waqt_local` | `local/` | `waqt-core>=0.6.0,<0.7` |
| `waqt-cli` 0.3.0 | `waqt_cli` | `apps/cli/` | `waqt-local>=0.7.0,<0.8` |
| `waqt-client` (SDKs) | `waqt_client` / npm | `sdks/` | unchanged (HTTP only) |

## What moved, and how it was verified

Every computation module moved **unchanged** from `waqt/` to `core/waqt_core/`
(`core`, `hijri`, `semantics`, `solar`, `timescale`, `timezone_provider`,
`calendar_interop`, and the `calendar_providers`, `institutional`,
`scheduling` subpackages). Internal imports were already relative, so none
needed editing. The move was checked with `diff` (empty) *before* any other
change was made; the only later change to a moved file is the deliberate,
separately measured `solar.py` work in
[`ASTRONOMY-ENGINE-EVALUATION.md`](ASTRONOMY-ENGINE-EVALUATION.md).

## Preserved public imports, without duplication

`import waqt.core`, `from waqt.scheduling.model import DAY_SHIFT`, etc. still
work, including deep submodule imports. `waqt/__init__.py` registers each old
name in `sys.modules` as **the same module object** as its `waqt_core`
counterpart; nothing is re-implemented or re-executed. There is no
`waqt/core.py` file left to shadow the alias.

"No duplicated computation" is a test, not a claim:
`core/tests/test_shim_identity.py` asserts `waqt.X is waqt_core.X` for all 23
aliased modules, for representative symbols, for literal deep-import
statements, and for attribute access.

Why aliasing every submodule explicitly matters: aliasing only the package
would let Python re-find `model.py` via the package `__path__` and execute a
second copy under the `waqt.scheduling.model` name — two classes with the same
name and different identity. The test above is what catches that.

**Guidance:** new code should import from `waqt_core`. The `waqt.*` names are a
compatibility layer; `waqt_local` and the new core tests use `waqt_core`
directly.

## Installing

```bash
pip install -r requirements.txt     # editable: core/, repo root, local/ + dev tools
# or individually:
pip install -e core/                # waqt-core only: no FastAPI anywhere
pip install -e .                    # waqt-api (pulls waqt-core)
pip install -e local/               # waqt-local (pulls waqt-core)
```

Until `waqt-core` is published to an index, install it before `waqt-api` /
`waqt-local` (as `requirements.txt` does), or pass all paths to one `pip`
invocation. Publishing is a credentialed human step, as for the SDKs.

## Tests that gate this architecture

| Suite | Proves |
|---|---|
| `core/tests/test_*_vectors_conformance.py` | `waqt-core` alone (no `waqt`, no FastAPI needed) reproduces all four public vector files |
| `core/tests/test_shim_identity.py` | `waqt.*` **is** `waqt_core.*` (no duplication) |
| `core/tests/test_packaging_smoke.py` | wheel **and** sdist build, install into a fresh venv away from the checkout, run a real computation, and `fastapi`/`waqt`/`waqt_local` are **not** importable there |
| `tests/test_packaging_smoke.py` | `waqt-api` + `waqt-core` wheels install together in a fresh venv and serve a real `/v1/waqt` request |
| `local/tests`, `tests/`, `consumers/js`, both SDKs | behavior preserved end to end |

Run `core/tests`, `tests/` and `local/tests` as **separate** `pytest`
invocations: none of these test directories has an `__init__.py` except
`tests/`, so same-named files (`test_waqt_vectors_conformance.py` exists in
both `core/tests` and `local/tests`) collide under pytest's basename import if
collected in one command. CI already runs them as separate steps.

## Not done / next

- `waqt-core` is not published to PyPI (needs credentials).
- The API's `computation` block still reports the engine as
  `waqt-noaa-low-precision` / accuracy level `B`; see the evaluation doc for why
  that label was deliberately not changed and why an engine *revision* field
  is recommended.
- `local/README.md` still shows the pre-Sprint-11 dev flow in places; the
  install section was updated, prose elsewhere was left.
