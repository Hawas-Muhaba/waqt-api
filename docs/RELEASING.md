# Releasing the Waqt SDKs

This sprint's publishing goal is `sdks/python/waqt_client` (PyPI, as
`waqt-client`) and `sdks/js/waqt-client` (npm, as `waqt-client`). This
document is what Sprint 10 asked to "establish before publication":
package metadata, versioning, changelog, supported versions,
installation, release procedure, compatibility policy, and the tests
that gate a release.

Actually pushing to PyPI/npm's registries is a credentialed, human step
(an API token / npm login this environment does not have and should
not be handed), so this sprint stops at "packageable and release-ready"
— every artifact a release would publish has been built and
clean-install-tested from a fresh, isolated environment (see below) —
rather than performing the upload itself.

## Package metadata

| | Python (`waqt-client`) | JS (`waqt-client`) |
|---|---|---|
| Manifest | `sdks/python/pyproject.toml` | `sdks/js/waqt-client/package.json` |
| Version | `0.3.0` | `0.3.0` |
| License | MIT (`LICENSE` in each package dir) | MIT |
| Typed | `py.typed` marker, full type hints | `index.d.ts`, checked with `tsc --noEmit -p tsconfig.json` |
| Changelog | `sdks/python/CHANGELOG.md` | `sdks/js/waqt-client/CHANGELOG.md` |

## Supported runtime versions

- Python: `>=3.9` (`pyproject.toml`'s `requires-python`; classifiers
  list 3.9 through 3.13, the versions this sprint's CI-equivalent test
  run actually used).
- Node.js: `>=18` (`package.json`'s `engines.node`; Node's own
  `node --test` runner, used throughout this SDK's test suite, requires
  it).

## Versioning

Both SDKs use [Semantic Versioning](https://semver.org/), and — per the
Sprint 10 brief's explicit instruction — their version number is **not**
automatically synchronized with the Waqt HTTP API's own `api_version`
(`waqt.api.common.API_VERSION`, currently `1.3.0`). Instead, each SDK
declares the `api_version` range it was built and tested against
(`waqt_client/config.py`'s `MIN_SUPPORTED_API_VERSION` /
`MAX_KNOWN_API_VERSION` on the Python side; the JS SDK checks the same
`meta.api_version` field via `envelope.mjs`) and reacts to a server
outside that range according to `on_version_mismatch` (`"warn"` by
default) — this was already Sprint 9's design and is unchanged.
Bumping the SDK's own semver version is a decision made when the SDK's
*own* public surface changes (like this sprint's new `requests` module,
a minor bump: 0.1.0 -> 0.2.0), not when the server's `api_version` ticks.

## Compatibility policy

- **Within a major SDK version**: no breaking changes to any existing
  method's signature, return type, or accepted body shape. Sprint 10 is
  a worked example: `schedule_resolve(body)` still accepts a plain
  `dict` exactly as it did in 0.1.0 — the new typed builders
  (`waqt_client.requests` / `requests_types.mjs`) are strictly additive.
- **Across a major SDK version**: reserved for a breaking change to the
  SDK's own API (not the server's) — none has happened yet.
- **Server `api_version` range**: an SDK release documents the
  `api_version` range it was tested against (see table above's pointer
  to `config.py`); a server reporting a version outside that range
  triggers the configured `on_version_mismatch` policy rather than a
  silent, possibly-wrong parse.

## Release procedure

1. Update the package's `CHANGELOG.md` (Added / Changed / Removed).
2. Bump the version in the package manifest (`pyproject.toml` /
   `package.json`) and, for Python, `waqt_client/_version.py`.
3. Run the full test suite for that package (`pytest tests/` /
   `node --test`), including the packaging smoke test
   (`test_packaging_smoke.py` / `packaging_smoke.test.mjs`) — both are
   part of the normal suite, not a separate manual step.
4. Build the release artifacts:
   - Python: `python3 -m build` from `sdks/python/` -> `dist/*.whl`,
     `dist/*.tar.gz`.
   - JS: `npm pack` from `sdks/js/waqt-client/` -> `waqt-client-<version>.tgz`.
5. Clean-install smoke test the built artifacts in a throwaway
   environment (exactly what step 3's packaging smoke tests already
   automate: a fresh `venv`/temp directory with no access to this
   checkout's source, installing only the built wheel/sdist/tarball).
6. Tag the release (`waqt-client-py-v<version>` / `waqt-client-js-v<version>`,
   since the two SDKs version independently of each other too).
7. Publish:
   - Python: `twine upload dist/*` (requires a PyPI API token — a
     credential this repository does not hold and this environment
     cannot acquire; a maintainer with publish rights runs this step).
   - JS: `npm publish` (requires npm registry auth, same constraint).
8. Verify the published package installs from the real registry
   (`pip install waqt-client==<version>` / `npm install waqt-client@<version>`)
   in a scratch environment, one last time, against the network.

Steps 1-5 are exactly what this sprint did and verified; steps 6-8 are
the credentialed continuation a maintainer performs.

## Package smoke tests / clean-install tests

- Python: `sdks/python/tests/test_packaging_smoke.py` builds both the
  wheel and the sdist with `python -m build`, installs each into a
  fresh `venv` (no `-e .`, no access to this checkout except the built
  artifact), and imports/exercises `waqt_client` and
  `waqt_client.requests` there — including an explicit assertion that
  the installed package does **not** pull in the `waqt` core package as
  a dependency.
- JS: `sdks/js/waqt-client/test/packaging_smoke.test.mjs` runs
  `npm pack` for the real tarball, `npm install`s it into a throwaway
  directory, and imports/exercises `waqt-client` from there.

Both are part of each package's normal test run (`pytest tests/` /
`node --test`), not an opt-in extra — a change that breaks packaging
(a missing file in `include`/`files`, an accidentally-required dev
dependency, ...) fails the same test run a code change would.

## `waqt-core`, `waqt-api`, `waqt-local` (Sprint 11)

Three more distributions are now packageable (see `docs/PACKAGING.md`):
`core/` → `waqt-core` 0.1.0, repo root → `waqt-api` 0.1.0, `local/` →
`waqt-local` 0.3.0 (Sprint 12: additive `computation.engine`/`.revision`, `version()`). Same policy as above: built and clean-install-tested,
not uploaded (credentials).

**Release order matters:** `waqt-core` first, then `waqt-api` and
`waqt-local` (both declare `waqt-core>=0.1.0,<0.2`).

**Versioning `waqt-core`.** SemVer. Unlike the SDKs, `waqt-core`'s version
*is* about computed values: any change to `solar.py` that moves an output
time is a behavior change and needs at least a minor bump plus a
`CHANGELOG.md` entry stating the measured effect (Sprint 11's two epoch
fixes are the template — before/after tables in
`SPRINT-11-REPORT.md`). Pure refactors/packaging: patch.

**Gate a `waqt-core` release on:** `pytest core/tests` (incl. both
packaging smoke tests, run separately), `pytest tests/`, `pytest
local/tests`, `cd independent-astronomy && pytest tests/`, `consumers/js`
`npm test`, and — if `solar.py` changed — regenerated vectors
(`tests/vectors/generate_*.py`, `sdks/vectors/generate_*.py`) reviewed as a
diff, never hand-edited.
