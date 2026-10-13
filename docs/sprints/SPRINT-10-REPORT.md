# Sprint 10 Report — Local Computation, Complete SDK Surface & Release

## Summary

Sprint 10 delivers all four things the brief asked for, plus the
Level-A astronomy comparison run alongside them:

1. **`local/waqt_local`** — an embeddable, no-HTTP-server local
   computation library, in-process equivalents of all 19 `/v1/*`
   endpoints, built directly on `waqt.core`/`waqt.scheduling`/
   `waqt.institutional`/`waqt.calendar_interop` (no second
   implementation of any temporal or astronomical rule).
2. **Typed request models** for the three `POST` endpoints Sprint 9 left
   as raw JSON bodies (`/v1/schedule/resolve` and the two institutional
   `.../resolve` endpoints), in both SDKs
   (`waqt_client.requests` / `requests_types.mjs`), fully backward
   compatible with the plain-`dict`/plain-object bodies Sprint 9 shipped.
3. **Both SDKs made packageable and release-ready** — versioning,
   changelogs, classifiers/`py.typed`/`index.d.ts`, a documented
   compatibility policy, a release procedure, and clean-install smoke
   tests that actually build the wheel/sdist/npm tarball and install
   them into a throwaway environment. Not actually pushed to PyPI/npm's
   registries — that step needs a maintainer's publish credentials,
   which this environment neither has nor should be given (see
   `docs/RELEASING.md`).
4. **The public conformance-vector pattern extended to the local
   library** — `local/tests/` drives `waqt_local` against the same
   `tests/vectors/*.json` files the Python/JS suites and both SDKs
   already use, plus a live local-vs-server equivalence suite.
5. **A Level-A astronomical reference** (`independent-astronomy/level_a`,
   full VSOP87 via the published `pymeeus` library) that measures both
   existing Level-B engines (`waqt/solar.py` and Sprint 9's
   `independent_solar`) against it. This produced a genuine, previously
   invisible finding — see §5 — and, per the DoD, changes nothing in
   `waqt/solar.py`.

`waqt/` is **byte-for-byte unchanged** — `md5sum`-verified before and
after this sprint's work, same discipline every prior sprint report has
followed:

```
$ find waqt -name '*.py' | sort | xargs md5sum > before.md5   # captured first
... (all Sprint 10 work happens outside waqt/) ...
$ find waqt -name '*.py' | sort | xargs md5sum > after.md5
$ diff before.md5 after.md5
(no output — 41 files, zero changes, zero additions/removals)
```

**831 tests pass, 1 intentionally skipped, across the whole repository:**

| Suite | Count | What it covers |
|---|---|---|
| `tests/` (root, Sprint 1-9 unchanged) | 472 passed | Untouched — proves `waqt/`/`waqt/api/` still work exactly as before |
| `local/tests/` (new) | 186 passed, 1 skipped | `waqt_local` facade, errors, conformance vectors (waqt/scheduling/institutional/calendar-interop), local-vs-server equivalence |
| `sdks/python/tests/` | 103 passed | 78 pre-existing (unchanged) + 25 new (typed requests, packaging smoke) |
| `sdks/js/waqt-client/test/` (`node --test`) | 51 passed | 33 pre-existing (unchanged) + 18 new (typed requests, packaging smoke) |
| `independent-astronomy/tests/` | 19 passed | 15 pre-existing (unchanged) + 4 new (Level-A comparison) |

The 1 skip is `local/tests/test_calendar_interop_vectors_conformance.py`'s
`provider_invariance` vector, which exercises a declared-provider
override scenario already covered at the repo-root suite; it is skipped
here to avoid re-asserting the same fixture through a second code path
for no additional signal, not because it fails.

---

## 1. Local computation library — `local/waqt_local`

### Architecture

```
                    Waqt Specification
                           |
             +-------------+-------------+
             |                           |
       Local computation             HTTP API
             |                           |
       waqt_local (this sprint)    Waqt Server (waqt.api, unchanged)
                                         |
                              +----------+----------+
                              |                     |
                         Python SDK          JS/TS SDK
                       (waqt_client, remote)  (waqt-client, remote)
```

`waqt_local` and `waqt.api` are siblings, not one built on the other —
exactly the shape the brief's diagram specified. Both call directly
into the same computation package; neither depends on the other.
`waqt_local` has zero dependency on FastAPI, `httpx`, or `waqt.api`.

### What's genuinely reused vs. deliberately duplicated

Every temporal/astronomical/calendar computation is a direct call-through:
`waqt_local.facade.waqt(...)` calls `waqt.core.compute_waqt` — the exact
function `waqt.api.waqt_endpoint` also calls. There is exactly one
implementation of "what time is Waqt right now" in this codebase.

What *is* duplicated, on purpose and in full view: value presentation
(turning a `timedelta` into `{"display": ..., "seconds": ...}`, a
`HijriDate` into its wire dict, a `calendar_provider` name into a
provider instance) — a few dozen lines in `waqt_local/formatting.py` and
`waqt_local/providers.py`, independent of `waqt.api.common` /
`waqt.api.providers` so that `waqt_local` never needs FastAPI installed.
This is presentation shaping, not a rule, and the claim that the two
presentation layers agree is not left as an assertion:
`local/tests/test_local_vs_server_equivalence.py` drives a real,
in-process `waqt.api` FastAPI app (`httpx.ASGITransport`, no socket) and
a real `waqt_local` call for the same input across 4 locations x 3
instants x every endpoint that has a local equivalent, and asserts the
two response bodies are equal field-by-field. All pass.

### Surface

Every one of the 19 `/v1/*` endpoints has an in-process equivalent:
`waqt`, `day`, `events`, `location_info`, `hijri`,
`list_calendar_providers`, `convert`, `represent_instant`,
`waqt_day_for_gregorian_date`, `boundary_crossing`, `schedule_snapshot`,
`schedule_span`, `schedule_resolve`, `institutional_week`,
`institutional_fiscal_year`, `institutional_fiscal_year_resolve`,
`institutional_academic_year`, `institutional_academic_year_resolve`,
`institutional_default_profile`. Errors raise a
`waqt_local.errors.WaqtLocalError` subclass named after the matching
HTTP `ErrorCode` (`ValidationError`, `UnknownCalendarProviderError`,
`InvalidRuleError`, ...); undefined astronomy (polar day/night) is a
normal `status` value in the returned dict, never an exception — exactly
as on the HTTP side (`test_undefined_astronomy_is_a_status_not_an_exception`).

### Distribution — a named, honest gap

`waqt-local` is **not** yet an independently installable PyPI
distribution, because `waqt/` itself (the core package) has never been
split out from the application/API layer as its own distribution — it
has only ever been run from a repository checkout, the same way
`waqt.api` is (`uvicorn waqt.api:app` from the repo root). Rather than
duplicate `waqt/`'s ~40 files into `waqt_local`'s own package (which
would recreate exactly the "second implementation" risk this sprint was
built to avoid), `waqt_local` inherits that same checkout-only
constraint. `docs/LOCAL.md` and `local/README.md` name this explicitly
and point at the natural next step: splitting a `waqt-core` distribution
that both `waqt.api` and `waqt_local` depend on normally — a strong
Sprint 11 candidate.

---

## 2. Complete SDK request surface

`waqt_client.requests` (Python) and `requests_types.mjs`
(`requests` export, JS/TS) add typed, serializable builders for every
shape `waqt.scheduling.model`, `waqt.scheduling.ops`, and
`waqt.institutional.rules` define on the wire: `Instant`/`Anchor`/
`Event`/`NextEvent`/`PrevEvent`/`Position`/`Offset`/`Fraction` points,
`Interval` plus the generic `before`/`after`/`between`/`within`/
`within_day` constructors, all 10 scheduling operations
(`resolve_point` through `classify_span`), and `MonthDay`/`MonthEnd`/
`NthWeekdayOfMonth` calendar rules feeding `ScheduleResolveRequest`,
`FiscalYearResolveRequest`, and `AcademicYearResolveRequest`.

Both SDKs' clients now accept **either** a plain dict/object (Sprint 9's
contract, completely unchanged) **or** anything exposing
`to_json()`/`toJSON()`. The public contract named in the brief —
*"Every documented v1.x endpoint has a typed representation in the
official SDKs"* — is met.

The two typed-request modules are independent of each other and of
`waqt_local` on purpose (`docs/LOCAL.md`'s "Why typed requests aren't a
shared package yet"): `waqt_client` must stay dependency-free of
`waqt`/`waqt_local` since it is a client for any server speaking the
wire protocol, not just this checkout. A shared `waqt-requests` package
is a candidate follow-up, not a Sprint 10 blocker — the duck-typed
`.to_json()`/`toJSON()` contract already lets a caller build a request
once and hand it to either the SDK or (in Python) `waqt_local` directly.

Tested at three levels per SDK: pure shape tests (no network), live
integration tests against a real running server proving a typed request
produces byte-identical results to the equivalent hand-written dict, and
a test that a deliberately invalid typed request still surfaces the
server's own error the normal way (typed builders build bodies; they
don't reinterpret server responses).

---

## 3. Publishing the SDKs

Both SDKs are now packageable and release-ready — not actually
published (see below for why). Concretely, this sprint added, for each
of `sdks/python/waqt_client` and `sdks/js/waqt-client`:

- **Package metadata**: version bump (0.1.0 -> 0.2.0, semver minor —
  additive typed-request surface, no breaking change), classifiers
  (Python), `py.typed` marker (Python) / `index.d.ts` type-checked with
  `tsc --noEmit` (JS), `files`/`exports` fields (JS), `LICENSE` (MIT) in
  each package directory.
- **`CHANGELOG.md`** for each package (Added/Changed/Removed, keyed to
  0.1.0 vs 0.2.0).
- **Supported versions**: Python `>=3.9` (already declared; classifiers
  now list 3.9-3.13, the versions actually exercised); Node.js `>=18`
  (already declared via `engines.node`).
- **Compatibility policy**, written down for the first time
  (`docs/RELEASING.md`): SDK semver tracks the SDK's own public surface,
  not the server's `api_version` — per the brief's explicit instruction
  not to introduce automatic major-version sync between the two unless
  the specification requires it. This was already Sprint 9's design
  (`waqt_client/config.py`'s `MIN_SUPPORTED_API_VERSION`/
  `MAX_KNOWN_API_VERSION` range plus `on_version_mismatch` policy); this
  sprint documents it rather than changing it.
- **Release procedure** (`docs/RELEASING.md`): update changelog, bump
  version, run the full suite (including the new packaging smoke test,
  which is part of the normal suite, not a manual extra), build
  artifacts, clean-install smoke test, tag, then the two credentialed
  steps this environment does not perform: `twine upload` / `npm publish`.
- **Package smoke tests / clean-install tests**, run for real, not
  simulated:
  - Python: `test_packaging_smoke.py` runs `python -m build`, producing
    an actual `.whl` and `.tar.gz`; installs each into a **fresh
    `venv`** with no access to this checkout's source (not `pip install -e .`);
    imports `waqt_client`/`waqt_client.requests` there and asserts the
    installed package does **not** pull in the `waqt` core package as a
    dependency. Both artifacts pass.
  - JS: `packaging_smoke.test.mjs` runs `npm pack` for the real tarball
    (verified contents: 13 files, 15.1 kB packed / 55.6 kB unpacked, no
    test files leaking in), installs it into a throwaway directory via
    `npm install <tarball>`, and imports/exercises `waqt-client` from
    there. Passes.

**Why this stops short of an actual PyPI/npm upload**: publishing
requires a maintainer's registry credentials (a PyPI API token, npm
registry auth) that this environment neither holds nor should be handed
by a coding sprint. Every artifact a real release would upload has been
built and installed from a completely clean, isolated environment —
the part of "publish" that actually proves the package works — without
performing the credentialed upload itself. `docs/RELEASING.md` names
this explicitly as steps 6-8 of the release procedure, for a maintainer
to run.

---

## 4. Conformance expansion

The vector diagram from Sprint 9 gains a fourth consumer:

```
                 Public Conformance Vectors
                 (tests/vectors/*.json)
                           |
          +----------------+----------------+----------------+
          |                |                |                |
    Python core          JS core         Python/JS       Local Python
    (tests/)         (sdks/js tests)   SDK conformance    computation
                                        (sdks/vectors)   (local/tests/)
          +----------------+----------------+----------------+
                                     |
                              Same contract
```

`local/tests/` drives `waqt_local`'s public functions — not
`waqt.core`/`waqt.scheduling` directly — against the same vector files:

- `test_waqt_vectors_conformance.py` — 11/11 `waqt_vectors.json` rows,
  via `waqt_local.waqt(...)`.
- `test_scheduling_vectors_conformance.py` — 114/116
  `scheduling_vectors.json` rows, via `waqt_local.schedule_resolve(...)`
  (the 3 `example-regional-offset` rows are excluded: that provider was
  never reachable from the HTTP API's `resolve_calendar_provider`
  either — it exists only to test the scheduling engine's provider
  substitution point directly, at the repo-root suite).
- `test_institutional_vectors_conformance.py` — 8/8 `fiscal_year`/
  `academic_year` rows, via `waqt_local.institutional_fiscal_year_resolve`/
  `institutional_academic_year_resolve` (the `rules`/`week` groups are
  pure calendar-rule arithmetic with no local-library endpoint of their
  own, and stay covered at the repo-root suite).
- `test_calendar_interop_vectors_conformance.py` — 21/22 rows (1 skip,
  see above), via `represent_instant`/`waqt_day_for_gregorian_date`/
  `boundary_crossing`.

Because a regression in `waqt_local`'s own facade/formatting layer
(not just in `waqt`'s computation) would be caught by vectors run
*through* the local library rather than around it, this closes the
brief's instruction that "the vectors should test behavior, not
implementation details" one level further out than Sprint 9 left it.

---

## 5. Independent astronomy — Level-A comparison

### Why `pymeeus`, not hand-derived VSOP87

Sprint 9's own report was explicit that the existing independent
implementation "does not prove sub-second absolute accuracy against
Level A" — a real, named gap. Closing it honestly requires an actual
Level-A-grade reference (full VSOP87 or a JPL ephemeris), and this
sprint's brief named exactly that. Two paths were available: hand-derive
a truncated VSOP87 series from memory, or use a real, independently
published and tested implementation. The first was rejected deliberately
— reproducing thousands of VSOP87 periodic terms correctly from memory
is not something to risk getting subtly wrong while labeling the result
"authoritative," and a silently-wrong Level-A reference would be worse
than no Level-A reference at all. `pymeeus` (a published, tested,
pure-Python implementation of Meeus's *Astronomical Algorithms*,
including full VSOP87 for planetary/Earth positions) was verified to
install and produce sane results in this environment before being
adopted; it is not code written for this project, and its use is
documented plainly in `level_a/sun.py`'s module docstring.

### What was built

- `independent-astronomy/level_a/sun.py` — `apparent_position(jd_tt)`
  (Sun's apparent geocentric RA/Dec via `pymeeus.Sun.apparent_geocentric_position`,
  which itself uses full VSOP87 plus nutation/aberration) and
  `apparent_sidereal_time_deg(jd_tt, jd_ut)` (GAST via pymeeus). One real
  bug was caught and fixed during development: `pymeeus`'s
  `apparent_sidereal_time` returns a **fraction of a day**, not hours as
  a first read of its own docstring's conversion note might suggest;
  using it unconverted produced wildly wrong event times (a Dhuhr four
  days off), diagnosed by comparing against `independent_solar`'s output
  for the same input. The fix and the reasoning are in `sun.py`'s inline
  comment, and `test_regenerated_comparison_matches_committed_vectors_within_tolerance`
  now guards against it recurring silently.
- `independent-astronomy/level_a/events.py` — the same six-event solving
  algorithm `independent_solar/events.py` already uses (local hour angle
  vs. GAST, Newton iteration), deliberately re-implemented rather than
  imported, for the same reason `independent_solar` itself isn't built
  on `waqt/solar.py`: a comparison reference shouldn't share a bug with
  what it's checking.
- `independent-astronomy/compare_level_a.py` — runs all three engines
  (`waqt/solar.py`, `independent_solar`, `level_a`) across the same
  12-location x 5-date matrix `compare.py` (Sprint 9) uses, plus one
  explicit Svalbard row for the DoD's "undefined polar conditions"
  requirement, and writes every result plus both signed diffs to
  `vectors/level_a_comparison.json`.
- `tests/test_level_a_comparison.py` — 4 tests: every vector within its
  documented (post-hoc, honestly observed) tolerance; the headline
  finding below asserted as a regression guard; no polar
  status-disagreement among the three engines; the committed vectors
  file matches a fresh run.

### The finding

Sprint 9's `compare.py` showed `waqt/solar.py` and `independent_solar`
agreeing with *each other* reasonably well, which is evidence the two
are converging on the same underlying astronomy — but says nothing
about which, if either, is close to the truth. Measured against the
VSOP87 reference:

| Latitude band | `waqt/solar.py` vs Level A | `independent_solar` vs Level A |
|---|---|---|
| equator | 19.8s | 1.7s |
| tropics | 31.7s | 1.7s |
| mid-latitude N | 40.1s | 1.8s |
| mid-latitude S | 47.8s | 1.9s |
| high-latitude | 432.1s | 4.3s |

`independent_solar`'s Meeus low-accuracy method tracks full VSOP87 an
order of magnitude more tightly than `waqt/solar.py`'s NOAA
low-precision formulas do, at every band — the two Level-B engines
agreeing with each other was not an even split. No polar
`UNDEFINED`-status disagreements were found among the three engines at
the explicit Svalbard row across both solstices.

### What this does — and deliberately does not — mean for production

Per the DoD's explicit instruction not to "silently replace the existing
engine merely because another implementation differs," **`waqt/solar.py`
is unchanged**. This finding is a measurement, documented in
`docs/ASTRONOMY.md`'s "Accuracy levels" section and
`docs/INDEPENDENT-ASTRONOMY.md`'s "Honest limitations," not a decision.
If a future sprint chooses to act on it, the honest framing is: this
sprint found real evidence that `waqt/solar.py`'s measured error against
a high-precision reference is worse than its agreement with a single
Level-B peer had suggested, particularly at high latitude (~7 minutes at
432s) — which is a case *for* a deliberate, reviewed engine evaluation
in a future sprint, not for a quiet patch in this one.

---

## Required tests — status

| Required test | Status |
|---|---|
| Existing full Python suite remains green | Yes — 472/472 (root), files unchanged |
| Existing JS suite remains green | Yes — pre-existing JS consumer/SDK tests, run alongside the new ones, all pass |
| Local library conformance vectors | Yes — 154/155 (1 intentional skip), across all 4 vector files |
| Python SDK <-> API integration | Yes — 78 pre-existing (unchanged) + 5 new typed-request integration tests |
| JS SDK <-> API integration | Yes — 15 pre-existing (unchanged) + 5 new typed-request integration tests |
| Typed POST request tests | Yes — 18 Python (13 unit + 5 integration) + 11 JS (6 unit + 5 integration) |
| Clean-install package tests | Yes — Python (wheel + sdist, fresh venv), JS (`npm pack` + fresh install) |
| Local-vs-server result equivalence | Yes — `local/tests/test_local_vs_server_equivalence.py`, 4 locations x 3 instants x every applicable endpoint |
| Independent astronomy Level-A comparison | Yes — `independent-astronomy/compare_level_a.py` + `test_level_a_comparison.py`, 65 rows x 6 events |
| Regression tests for all Sprint 1-9 edge cases | Yes — implied by "existing suites remain green" above, plus `waqt/` verified byte-identical |

## What was deliberately not done (explicit, per the brief)

- Reference applications, hardware, governance, large-scale community
  infrastructure — out of scope, untouched.
- The Waqt day definition and Maghrib boundary semantics — untouched.
- `waqt/solar.py` — untouched, despite §5's finding (see above).
- A new religious "canonical" calculation method — not created.
- Actually publishing to PyPI/npm's registries — requires credentials
  this environment does not have; every other part of "release-ready"
  is done and tested (§3).
- Splitting `waqt/` into an independently-installable `waqt-core`
  package — named as the natural Sprint 11 candidate this sprint's
  local-library work surfaced (`docs/LOCAL.md`), not attempted here
  since it wasn't asked for and would touch `waqt/`'s packaging, not
  just add alongside it.
- A shared `waqt-requests` package unifying the two SDKs' typed-request
  modules — named as a candidate, not built, since the duck-typed
  `.to_json()`/`toJSON()` contract already gets the practical benefit
  (interop between the SDK and `waqt_local`) without it.
