# Sprint 14 — Live Integrations & Production Hardening

**Base:** `waqt-api-sprint13-src.zip`. **Nature of the sprint:** the first integration with something outside the
repository (a live Hijri date source) plus the hardening a public deployment needs. The astronomy engine is untouched:
`solar.py`, `timescale.py`, `versioning.py`, `timezone_provider.py` are **byte-identical** to the upload (`cmp`); engine
revision stays `2`, accuracy level `B`, vector set `1.1`. Contract: **API 1.4.0 → 1.5.0 (additive only)**.

Environment: Python 3.12, Node 22, ephem 4.2.1, timezonefinder 9.0.0, fastapi 0.142.1, pydantic 2.13.5, uvicorn 0.54,
pytest 9.1.1, headless Chrome 153. Sandbox clock: 2026-09-30/10-01.

> **Live-service verification scope.** The build sandbox could not reach `api.aladhan.com` (egress proxy:
> `403 x-deny-reason: host_not_allowed`), so the original CI/browser evidence uses a local fake server. A later check from
> the networked Windows development environment on **2026-10-01** did reach the real service: `GET
> https://api.aladhan.com/v1/gToH/01-10-2026` returned HTTP 200 with Hijri date `20-04-1448` and method `HJCoSA`.
> The project's default `AlAdhanHijriProvider` transport also returned `source=remote`, provider `aladhan`, upstream
> method `HJCoSA`, and an agreeing Umm al-Qura cross-check (`delta_days=0`); one upstream request was recorded and no
> fallback occurred. This verifies one live request and the observed response shape, not sustained availability or all
> dates/methods. See §9 for the repeatable check.

## 0. Result at a glance

| Suite | Sprint 13 | Sprint 14 |
|---|---|---|
| core | 282 | **354 passed** (+51 provider, +21 isolation) |
| root (API, packaging, version audit, live consumer) | 483 | **564 passed** (+81 Sprint 14 API tests) |
| local | 186 (+1 skipped) | **186 passed**, 1 skipped (by design) |
| Python SDK | 103 | **105 passed** |
| JS SDK | 51 | **52 passed** |
| JS independent consumer | 184 | **184 passed** |
| CLI / API consumer / web (structural) | 19 / 9 / 7 | **19 / 9 / 7 passed** |
| independent-astronomy (JPL DE421 reference) | 36 | **36 passed** |
| `verification/live_stack_check.py` (real uvicorn, real sockets) | 17/17 | **29/29** (12 new Sprint 14 checks) |
| `verification/browser/run_sprint14.sh` (real Chrome, new) | — | **16/16** |
| `verification/browser/run_smoke.mjs` (Sprint 13 browser suite) | 34/34 | **34/34** (3 stale expectations updated, §2) |
| `verification/vector_additivity_check.py` (new) | — | **OK: 21/21 recorded responses preserved** |
| `pip check` | — | no broken requirements |

Mutation checks (provider tests): removing the plausibility gate, the cache expiry, the single-flight guard, or mislabelling
fallbacks as `remote` each made tests fail (1, 3, 37, 29 failures respectively). Browser negative controls: disabling HTML escaping
fails S14-4; configuring the wrong CORS origin fails the page's own calls (CORS is genuinely enforced, `--disable-web-security`
stripped as in Sprint 13).

## 1. Goal A — `AlAdhanHijriProvider`

`core/waqt_core/calendar_providers/aladhan.py`, behind the unchanged `HijriProvider` protocol; selectable as
`calendar_provider=aladhan`. The existing four providers are untouched in behaviour.

| Requirement | Implementation |
|---|---|
| Live Gregorian→Hijri | `GET {base}/gToH/DD-MM-YYYY` (stdlib `urllib`; **no new dependency**); optional `?calendarMethod=` |
| Cache | 12 h per (date, method), thread-safe, bounded LRU (4096), single-flight (8 concurrent requests → 1 upstream call) |
| Safe fallback | local `umm-al-qura`; if that fails, `arithmetic-tabular`. **Never raises** (an arbitrary `RuntimeError` from the transport is converted to a labelled fallback) |
| Identity/version | `provider = {"name":"aladhan","version":"aladhan-gToH-v1[+method=X]"}`; upstream's reported method in `provenance.upstream_method` |
| Never affects astronomy | §3 |

Production safety beyond the brief (a public API's outbound call must not be an amplifier or a hang):
3 s timeout; circuit breaker (30 s, or upstream `Retry-After` capped at 10 min); outbound budget 30 req/min; date window
1900–2076 (outside it nothing leaves the process); response ≤ 64 KiB, redirects refused, must echo the requested date, fields in
range, within 3 days of the arithmetic calendar; stale-if-error (§5).

## 2. Defects and findings from real execution

| # | Finding | Found by | Resolution |
|---|---|---|---|
| F1 | **Latent since Sprint 3:** `compute_waqt` called the Hijri provider *inline*; any provider exception destroyed the whole result including all prayer times (`umm-al-qura` at year 1500 → opaque 500). A network provider would have made this a live risk. | reading `core.py` before designing | `compute_waqt` now contains the failure: events still computed, `hijri: null`, `data.calendar_error`. **Behaviour change** (below). |
| F2 | `apps/web` read `waqt.hijri.display` unguarded; the new `hijri:null` state would throw and blank the page. Also: a failed boundary refresh hid the view, and `tick()` would retry every second. | code review; reproduced in Chrome (S14-3a) | null-safe rendering, visible source badge, refresh backoff that keeps the last good view (S14-6). |
| F3 | **My own first rate limiter was bypassable:** with `WAQT_TRUST_PROXY` it keyed on the *first* `X-Forwarded-For` entry, which a client controls when the proxy appends. | self-review before wiring into `render.yaml` | key = entry `hops` from the **right** (`WAQT_TRUSTED_PROXY_HOPS`, default 1); 2 regression tests. |
| F4 | `waqt-cli` pinned `waqt-local<0.4`. | `pip check` after the local bump | CLI → 0.1.1, pin `>=0.4.0,<0.5`. |
| F5 | `waqt-local` must emit payloads identical to the server (equivalence test). 16 tests failed when only the API gained fields. | local suite | mirrored the additions into `waqt_local` (0.4.0). |
| F6 | Both SDK typed models silently **dropped** `source`/`provenance` (JS kept only `raw`), hiding provenance from SDK users. | reading `types.py`/`types.mjs` | optional fields added (Python/JS 0.3.1) + tests; older servers give `None`/`null`. |
| F7 | `/v1/events` must equal `/v1/waqt` `events[]` (existing test). Nesting per-event representations broke that contract. | API suite | kept `events[]` byte-identical; representations are a sibling `event_representations[]` (§4). |
| F8 | Hard-coded old values: SDK/core packaging smoke (`"0.2.1"`, `"0.3.0"`), 3 Sprint 13 browser checks (`4 providers`, `1.4.0`, `0.2.1`). | full-suite run | updated to current truth; page behaviour verified correct. |
| F9 (mine) | First draft of the Sprint 14 browser script: stale boundary offset, cache masking the failure scenario (cache is per date), open circuit poisoning later live scenarios; API test fixture used an arithmetic fallback unlike production. | first runs / reading | reordered, date-shifted clock for the failure case, fixture mirrors production wiring. |

**Intentional behaviour changes to existing contracts** (everything else is purely additive):
1. A failing calendar provider no longer fails `/v1/waqt` (was a 500). One Sprint 13 test (`test_internal_error_never_leaks_a_raw_traceback`)
   was rewritten: its 500 trigger moved to `/v1/hijri` (where the calendar *is* the answer), and a true internal error on `/v1/waqt` is tested separately.
2. `GET /v1/calendar` lists a fifth provider; `meta.api_version` is `1.5.0`.

## 3. No effect on astronomical computation — three independent guarantees

1. **Structural** (AST import graph): `solar`, `timescale`, `versioning`, `core`, `hijri` do not import the provider; the provider imports nothing from the
   engine; **only** `aladhan.py` in all of `waqt_core` may import a network library.
2. **Behavioural**: events, day boundaries, readings, ΔT, next event are compared as exact `repr` strings across **8 provider/failure configurations**
   (arithmetic, umm-al-qura, aladhan agreeing / disagreeing by 2 days / down / raising transport / garbage / disabled) for 5 inputs: normal (Addis Ababa),
   **high latitude** (Reykjavik, June: status `OK`, Fajr/Isha have no instant), and **polar** (Tromsø June, Svalbard December, North Pole: `UNDEFINED`).
   All identical. Also asserted over real HTTP, and through the API for provider switching.
3. **Containment**: a calendar provider that raises cannot remove the events (`calendar_error`).

Polar `UNDEFINED` results make **zero** upstream requests (asserted) — there is no Waqt day to label.

## 4. Goal B — provenance and visible disagreement

Every Hijri block gains `source` ∈ `local | declared | observation | remote | remote-stale | local-fallback` and `provenance`
(null for purely local providers). Shapes are in `docs/LIVE-INTEGRATIONS.md §1`. Mapping to your examples:

```jsonc
{ "date":"1448-04-19", "provider":{"name":"aladhan","version":"aladhan-gToH-v1"}, "source":"remote",
  "provenance":{"cache":"miss","fetched_at":"…","upstream_method":"UAQ","fallback_reason":null,
                "cross_check":{"provider":"umm-al-qura","date":"1448-04-19","agrees":true,"delta_days":0}} }
{ "date":"1448-04-19", "provider":{"name":"umm-al-qura","version":"…"}, "source":"local-fallback",
  "provenance":{"requested_provider":"aladhan","fallback_reason":"upstream-server-error","fallback_detail":"HTTP 500"} }
```

* **Disagreement is made visible, not hidden or resolved.** When the service answers, the local reference is also computed and reported in `cross_check`
  (`agrees`, `delta_days`); the remote value is what is returned (tested: remote day = local + 1 is returned as-is with `delta_days` reported).
* **Where I differ from your example:** the provider is named `aladhan`, not `umm-al-qura-live`. The brief's own class name is `AlAdhanHijriProvider`, and
  calling it "umm-al-qura" would assert a method the service chooses, not us. The fallback case matches your example exactly (`provider: umm-al-qura`, `source: local-fallback`).
* **"Provider version" is our adapter's label** (`aladhan-gToH-v1`), not an AlAdhan version — the service does not expose one. What the service says about its method is recorded as `upstream_method`.

**Events — Gregorian / Hijri / Waqt.** `data.event_representations[]` (sibling of `events[]`, same order, join on `name`): `gregorian {utc, local, local_date,
local_time, timezone}`, `hijri {date, provider, version, source, basis:"waqt-day-label"}`, `waqt {display, seconds}`. Events with no instant (high-latitude Fajr/Isha)
have `gregorian`/`waqt` null. Design choices to review: the Hijri value is the **Waqt-day label** (Maghrib/Isha read at or beyond the day length rather than rolling to
the next label, matching how `reading` already works); `gregorian.local_date` is shown beside it because Isha is often on the next civil date.

## 5. Behaviours you did not ask for (review these)

* **Stale-if-error (`remote-stale`)** — after the 12 h TTL, if the service fails, the last good remote value is served for ≤ 7 days, labelled. Reason: without it a flapping
  service makes one date flip between two calendars within a day. Easy to remove (`max_stale_seconds=0`).
* **`aladhan` is refused (`400 UNSUPPORTED_OPERATION`) on `/v1/schedule/resolve` and `/v1/institutional/*`** — one request resolves many dates there, which would burn the
  outbound budget and mix `remote` and `local-fallback` days in one result. Allowed on `/v1/waqt`, `/v1/hijri`, `/v1/conversions` (to-hijri), `/v1/calendar/convert`,
  `/v1/schedule/snapshot|span`. Flagged in `/v1/calendar` as `single_date_only`.
* **`waqt-local` deliberately does not offer `aladhan`** (an offline library should not call out). The equivalence test now states that single difference explicitly.

## 6. Hardening

| Item | Result |
|---|---|
| Rate limiting | opt-in `WAQT_RATE_LIMIT=N/second\|minute\|hour`; sliding window per client, memory-bounded; `429 RATE_LIMITED` envelope + `Retry-After` + `X-RateLimit-*`; `/v1/health` and preflights exempt; 429 carries CORS headers (browser-readable). Enabled in `render.yaml` (120/min). **Per-process**: multiple workers each keep their own budget. |
| CORS | unchanged semantics (off by default); verified incl. preflight, error and fallback responses, 429s, in a real browser with the enforcement flag on |
| `/v1/health` | network-free; `status:"ok"` while the engine can serve; `integrations.hijri_aladhan` shows circuit/cache/counters/last failure reason. Degraded integration ≠ downtime. |
| `/v1/version` | gains `integrations` (provider list, aladhan identity, `affects_astronomy:false`); engine identity unchanged and identical across health/version/`/v1/waqt` |
| Invalid input | coordinates (±91, ±181, NaN, text, missing, negative elevation) → 422 envelope; instants/dates (`2026-02-30`, month 13, empty, garbage) → 400; **none reach the provider** (asserted: 0 upstream calls) |
| Browser day transition | real Maghrib crossing in Chrome with the live provider: extra `/v1/waqt` call (1→3, no polling storm), Hijri day 18→19, still `live · aladhan`, clock restarts at `00:00:05` |
| App factory | `waqt.api.create_app(cors_origins, rate_limit, trust_proxy)`; module-level `app` unchanged |

## 7. Version axes

| Axis | Sprint 13 | Sprint 14 |
|---|---|---|
| API contract | 1.4.0 | **1.5.0** (additive) |
| waqt-core | 0.2.1 | **0.3.0** (new public provider; `HijriDate.source/.provenance`; `compute_waqt` failure containment) |
| waqt-api package | 0.2.0 | **0.3.0** |
| waqt-local | 0.3.0 | **0.4.0** (mirrors the additions; pins core `>=0.3.0,<0.4`) |
| SDKs (py / js) | 0.3.0 / 0.3.0 | **0.3.1 / 0.3.1**; `MAX_KNOWN_API_VERSION` 1.5.0 |
| waqt-cli | 0.1.0 | 0.1.1 |
| Engine revision / vector set | 2 / 1.1 | **2 / 1.1 (unchanged)** |

**Vectors.** `tests/vectors/*` are untouched and pass. `sdks/vectors/sdk_conformance_vectors.json` embeds whole envelopes (incl. `meta.api_version`), so all 21 differed from the
1.5.0 app. Before regenerating, `verification/vector_additivity_check.py` proved that for all 21 responses every recorded value is still present and equal; the only differences
are the added keys (`hijri.source`, `hijri.provenance`, `calendar_error`, `event_representations`, provider-catalog `network`/`single_date_only`, and one appended catalog entry).
The checker was validated with a mutated file (it flags a changed value and a removed key). It is now a CI step.

## 8. Known limitations (honest list)

1. **Live AlAdhan checked once** (top of report); sustained availability and other dates/methods remain unverified. The 1900–2076 window is my conservative choice, not a documented limit; an out-of-range date simply falls back.
2. The circuit breaker is global: three consecutive *soft* failures (e.g. upstream rejecting three unsupported dates) open it for **all** dates for 30 s. Fails safe (to local) but coarse.
3. Rate limiter and cache are in-process; multi-worker deployments multiply budgets. No shared store.
4. **No logging/metrics** of fallbacks yet — they are visible in responses and `/v1/health` counters, but nothing is emitted for an operator to alert on.
5. Tested on Python 3.12; `render.yaml` pins 3.13.2 (not exercised here). The Render deployment itself was not performed.
6. `aladhan` provider's `version` is our adapter label (see §4).

## 9. Definition of Done

| | |
|---|---|
| **Hijri** | ☑ AlAdhanHijriProvider ☑ Cache (12 h) ☑ Local fallback ☑ Provider provenance ☑ Failure tests (17 failure modes, parametrised; real-socket) ☑ No effect on astronomical computation (§3) |
| **Events** | ☑ Gregorian/Hijri/Waqt representations ☑ Computation metadata (unchanged block, identical across endpoints) ☑ Provider metadata ☑ Error/fallback visibility (`source`, `provenance`, `calendar_error`, `/v1/health`) |
| **Verification** | ☑ High-latitude test ☑ Polar test ☑ No regression in existing vectors (§7) ☑ Full suite passes (§0) ☑ **Live AlAdhan smoke check** (one date, 2026-10-01; broader uptime/coverage not claimed) |
| **Your test list** | normal location ☑ · high latitude ☑ · polar/undefined ☑ · provider switching ☑ · provider failure/fallback ☑ · invalid coordinates ☑ · invalid dates ☑ · rate limiting ☑ · CORS ☑ · API health ☑ · version reporting ☑ · browser day transition ☑ |

### Repeatable live check

```bash
curl -fsS https://api.aladhan.com/v1/gToH/01-10-2026
python -c "from waqt_core.calendar_providers import AlAdhanHijriProvider as A; from datetime import date; h=A().from_gregorian(date(2026,10,1)); print(h.source, h, h.provenance)"
```
`source` should print `remote`. If `local-fallback`, `h.provenance.fallback_reason` names why (e.g. `malformed-response` would mean the real shape differs from the documented one).

## 10. Files

New: `core/waqt_core/calendar_providers/aladhan.py`, `waqt/api/ratelimit.py`, `docs/LIVE-INTEGRATIONS.md`, `core/tests/test_aladhan_provider.py`,
`core/tests/test_aladhan_isolation.py`, `tests/test_sprint14_live_integrations.py`, `verification/fake_aladhan.py`, `verification/vector_additivity_check.py`,
`verification/browser/run_sprint14.{mjs,sh}`, `verification/browser/fake_control.py`.
Changed: `core.py`, `hijri.py`, `local_observation.py` (core); `waqt/api/{__init__,common,providers,waqt_endpoint,calendar_endpoint,version_endpoint,schedule_endpoint,institutional_endpoint}.py`;
`local/waqt_local/{facade,formatting}.py`; both SDKs' types/config/typings; `apps/web/index.html`; `apps/cli/render.py`; `render.yaml`; `.github/workflows/ci.yml`; docs; version files and changelogs;
`sdks/vectors/sdk_conformance_vectors.json` (regenerated, additive); `verification/live_stack_check.py`, `run_smoke.mjs`, README.
Existing tests changed (all for the contract changes in §2): `tests/test_api.py` (3), `tests/test_api_consumer_against_live_api.py`, `tests/test_calendar_convert_api.py`,
`local/tests/test_local_vs_server_equivalence.py`, packaging smoke tests (core, Python SDK, JS SDK).
