# Waqt Web — Stitch design implementation report

Branch: `feature/stitch-web-design` (from `main` @ `1766ff3`). Scope: `apps/web/`, one CI step, this report.
Nothing was merged into `main`.

## 0. Read this first (things that differ from the brief's assumptions)

1. **The "existing Waqt Web" with the nav Overview / The Problem / How It Works / … did not exist in this repository.**
   `apps/web` was a single 23 KB `index.html` — the Sprint 12 reference viewer (dark dusk/ember/teal palette, no
   framework, no build). If a separate marketing site exists elsewhere, it was not reachable with the supplied token.
   I therefore treated the viewer as the existing architecture, preserved its identity and rules, and built the
   navigation from the brief.
2. **The viewer moved from `index.html` to `live-demo.html`** (its script is byte-for-byte unchanged); `index.html` is now
   the Overview page. The one existing test file was repointed to the new filename (one line). No test was removed.
3. **The Stitch MCP could not be used.** The sandbox only reaches an allow-list of hosts. The design was implemented from
   the 14 attached images. The Stitch key was not stored anywhere.
4. **Public API not reachable from the sandbox**, so everything was verified against a local run of this repo's own API
   (API 1.6.0). The Render deployment itself is untested.

## 1. Existing architecture preserved

Static, dependency-free site; no framework, no build; `render.yaml` unchanged (`staticPublishPath: ./apps/web`);
same API base rules (`?api=` override, localhost vs public default, `waqt:apiBase` key); same envelope handling;
same "consume Waqt, don't reimplement it" rule, now enforced across **all** site scripts by tests; same palette
(cyan added as one cool accent). The original viewer, its guard tests and the manual smoke checklist remain.

## 2. New components

| File | Purpose |
|---|---|
| `assets/js/waqt-api.js` | API client (timeouts, typed errors) + presentation model (`fromWaqtData`, snapshots, countdown) |
| `assets/js/waqt-live.js` | State machine: loading / success / empty / error / offline, boundary re-ask, demo fallback |
| `assets/js/waqt-clock.js` | **Reusable circular Waqt clock** (SVG), `variant: full | watch`, text equivalent, keyboard nav |
| `assets/js/waqt-widgets.js` | Mosque clock, smartwatch, day-length bar, midnight-vs-Waqt rings |
| `assets/js/config.js` | All external URLs/contact (null until supplied) |
| `assets/js/site.js`, `pages/*.js` | Nav toggle, config-driven links, page wiring |
| `assets/js/demo-data.js` | Recorded real response, used only as the labelled demo fallback |
| `assets/css/site.css`, `assets/img/*.webp` | Styles; 14 images optimised (total ≈ 660 KB, each ≤ 90 KB, lazy-loaded) |
| Pages | `index` (Overview/Problem/How It Works), `live-demo`, `api`, `applications`, `lab`, `governance`, `community`, `resources` |

## 3. Stitch concepts implemented

Circular clock · mosque wall clock · smartwatch face · mobile concept · Waqt vs midnight · API→applications ecosystem ·
institutional calendar · developer dashboard · location/travel · future concepts (smart home, public display,
research, wearables) · **Experience Lab** (01 drag through the day, 02 Maghrib reset, 03 next event, 04 Waqt vs midnight,
05 build an application).

## 4. Components using real API data

Home clock + day-length measurement; Applications live previews (circular clock, mosque clock, watch, day vs midnight);
Lab steps 01, 03, 04 (shared live store), 02 (real calls with chosen place/date), 05 (real call); API status panel;
the original Live Demo.

## 5. Visual concepts (no real data behind the *product*)

Gallery images are AI-generated concept renders and every one carries a visible "Concept art" tag. The mosque clock,
smartwatch, mobile app, institutional calendar, developer dashboard and location/travel apps are labelled
**CONCEPT** (the on-page previews are real software fed by real or labelled-demo data; no device/product exists).
Smart home, public displays, research and wearables are **FUTURE**. **REAL**: API, circular clock component, live
visualisations, reference viewer, CLI.

## 6. API endpoints actually used

`GET /v1/waqt` (all live components, Lab 02/05; with `instant` in Lab 02), `GET /v1/version`, `GET /v1/health`
(API status panel), plus the original viewer's `/v1/calendar`. Links to the API's own `/docs` and `/openapi.json`.
**No endpoint was invented.** A test fails if any script fetches a path outside the allow-list.

## 7. External links still configuration placeholders

`links.github`, `links.docs`, `links.spec`, `links.issues`, `links.buyMeACoffee`, `sdkRepos`, `packageRegistries`,
`officialApps`, `communityApps` — all `null`/`[]`. Unconfigured items render as visibly pending, non-clickable text
(GitHub, Buy Me a Coffee) or fall back to our own Resources page (Read Spec / Docs). **Decision needed:** the repo is
actually `Hawas-Muhaba/waqt-api` (private), while package metadata says `waqt-project/waqt-api`; a public GitHub link
should point at whichever is canonical *and public*.

## 8. Buy Me a Coffee

Placement done (footer on every page; Community page). Not a primary CTA. Dormant until `links.buyMeACoffee` is set.

## 9. Downloads / Resources

`resources.html`: Specifications, Documentation, SDKs, Conformance, Applications as repository paths with statuses
taken from the repo (SDKs are "packaged and release-ready", **registry publication not confirmed**). No packages copied;
no release-artifact links until canonical locations exist.

## 10. Tests

* `pytest apps/web/tests` — **26 passed** (10 original guards unchanged + 16 new structural tests).
* `apps/web/tests/js` (jsdom, `npm test`) — **31 passed**: model semantics, countdown/expiry, all five data states,
  boundary re-ask, clock rendering/next marker/overflow Isha, keyboard nav, demo labelling, banners, widgets,
  nav collapse, pending/configured links, mailto, API-base rules.
* Real headless Chromium against the real API: all 8 pages × desktop (1280) and mobile (390) — **no console errors,
  no failed requests, no horizontal overflow**; API-down case verified to show the "Live Waqt data unavailable /
  demonstration mode / DEMO · NOT LIVE" state.
* Existing suites: `tests/` 594 passed, **2 failed** (`test_conformance_contract.py`: stale `contract.json`
  manifest — **fails identically on an untouched checkout of `main`**, not caused by this work); `apps/cli` 19, `apps/api-consumer` 9 passed.
* CI: added a step running both web suites.

Not done: manual screen-reader pass, measured colour-contrast audit, Lighthouse, real-device testing, Render deploy check.

## 11. Remaining backend/API requirements

1. **`/v1/waqt` `events` omits the current Waqt day's own Isha.** It lists Isha at the *next* evening (reading ≈ 25:05).
   The clock draws it as a dashed "after next Maghrib" marker rather than inventing this evening's Isha. A complete
   day timeline (e.g. previous Isha with a reading) would let clocks draw the true Maghrib→Maghrib sequence.
2. `WAQT_CORS_ORIGINS` must be set to the static site's origin on Render (already documented in `render.yaml`).
3. Free-plan cold starts can exceed a minute; the UI says so, times out at 25 s and falls back to labelled demo with auto-retry.
4. `conformance/MAINTAINERS.md` is unfilled and DR-0001…0008 are "Ratification: PENDING"; the Governance page states this.

## 12. Preview

```
pip install -r requirements.txt
WAQT_CORS_ORIGINS=http://localhost:8080 uvicorn waqt.api:app --port 8000
python -m http.server 8080 --directory apps/web      # open http://localhost:8080
```

## Security note

A GitHub token and a Stitch key were pasted into the chat. Neither was written to any file or commit, and the clone's
remote URL was reset to the token-free URL. **Please revoke/rotate both** since they have been exposed in a conversation.
