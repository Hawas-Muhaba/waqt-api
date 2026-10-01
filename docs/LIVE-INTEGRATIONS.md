# Live integrations & production hardening (Sprint 14, API 1.5.0)

Waqt's computation engine is `waqt_core.solar` + `timescale`. **Nothing in this document can change a
prayer or solar event time.** A live integration may only influence the *label* shown next to the result
(the Hijri date), and every such label says where it came from.

```
HijriProvider (protocol)
 ├── arithmetic-tabular   local, offline
 ├── umm-al-qura          local, offline (astronomical approximation)
 ├── declared             an institution's override
 ├── local-observation    a reported sighting
 └── aladhan              REMOTE → cached 12 h → local umm-al-qura fallback        ← new
```

## 1. The `aladhan` provider

`calendar_provider=aladhan` asks AlAdhan's public API (`GET {base}/gToH/DD-MM-YYYY`) for the Hijri date
of a Gregorian date. Its calendar method is AlAdhan's default (Umm al-Qura per their documentation);
set `WAQT_ALADHAN_METHOD` to request another (sent as `?calendarMethod=`).

| Behaviour | Value |
|---|---|
| Cache | 12 hours, per Gregorian date (and method); bounded LRU (4096 entries) |
| Timeout | 3 s (socket) — it is called inline while a request is being served |
| Stale-if-error | after the TTL, if the service fails, the last good remote value is served for up to 7 days, labelled `remote-stale` (so the date does not flip between two calendars during an outage) |
| Fallback | local `umm-al-qura`; if that also fails, `arithmetic-tabular`. The provider **never raises** |
| Circuit breaker | after a hard failure (timeout, network error, 5xx, 429) no request is made for 30 s (or AlAdhan's `Retry-After`, capped at 10 min); three consecutive soft failures (4xx, malformed) also open it |
| Outbound budget | 30 requests/minute (token bucket) |
| Date window | 1900-01-01 … 2076-12-31; dates outside it never leave the process |
| Response checks | ≤ 64 KiB; no redirects followed; must echo the requested Gregorian date; fields in range; within 3 days of the arithmetic calendar — otherwise rejected as `malformed-response` / `date-mismatch` / `implausible-response` |
| Single-date only | refused (`400 UNSUPPORTED_OPERATION`) on `/v1/schedule/resolve` and `/v1/institutional/*`, where one request resolves many dates and results would mix remote and fallback values. Allowed on `/v1/waqt`, `/v1/hijri`, `/v1/conversions` (to-hijri), `/v1/calendar/convert`, `/v1/schedule/snapshot|span` |
| Reverse conversion | not supported (`UNSUPPORTED_OPERATION`) |

### Provenance in every response

`hijri.source` is always present:

| `source` | meaning |
|---|---|
| `local` | computed in-process |
| `declared` / `observation` | an institution's override / a reported sighting |
| `remote` | from the service (fresh, or a cache hit younger than the TTL) |
| `remote-stale` | the service failed; last known remote value, older than the TTL |
| `local-fallback` | the service could not deliver; `hijri.provider` names the provider that did |

`hijri.provenance` (null for purely local providers):

```jsonc
// success
{ "date": "1448-04-19", "provider": {"name": "aladhan", "version": "aladhan-gToH-v1"}, "source": "remote",
  "provenance": { "requested_provider": "aladhan", "cache": "miss", "fetched_at": "2026-09-30T09:00:01+00:00",
                  "age_seconds": 0.0, "ttl_seconds": 43200, "upstream_method": "UAQ",
                  "fallback_reason": null, "fallback_detail": null,
                  "cross_check": {"provider": "umm-al-qura", "date": "1448-04-19", "agrees": true, "delta_days": 0} } }
// fallback
{ "date": "1448-04-19", "provider": {"name": "umm-al-qura", "version": "…"}, "source": "local-fallback",
  "provenance": { "requested_provider": "aladhan", "fallback_reason": "upstream-server-error",
                  "fallback_detail": "HTTP 500", "cache": null, … } }
```

**Disagreement is visible, not resolved.** When the service answers, the local reference is also computed and
reported in `cross_check` (`agrees`, `delta_days`). The remote value is returned; it is not silently replaced
by the local one, and the local one is not hidden.

`fallback_reason` is one of: `disabled`, `date-outside-remote-window`, `circuit-open`, `outbound-rate-limited`,
`busy`, `timeout`, `network-error`, `upstream-rate-limited`, `upstream-server-error`, `upstream-rejected`,
`malformed-response`, `date-mismatch`, `implausible-response`, `internal-error`.

### Calendar failure never removes the prayer times

`compute_waqt` isolates the calendar: if *any* provider raises, the events are still computed, `hijri` is `null`,
and `data.calendar_error = {"provider", "message"}` says why (before Sprint 14 this was a 500 for, e.g.,
`umm-al-qura` outside its ephemeris range). For polar/`UNDEFINED` results there is no Waqt day, so the provider is not
consulted at all.

### Events in three vocabularies

`data.events[]` is unchanged (and stays identical to `/v1/events`). `data.event_representations[]` is a sibling, same
order, joined on `name`: `{ name, gregorian:{utc, local, local_date, local_time, timezone}, hijri:{date, provider,
version, source, basis:"waqt-day-label"}, waqt:{display, seconds} }`. `gregorian.local_date` can differ from the Waqt day
label (Isha is often on the next civil date). `hijri` is the label of the Waqt day the event belongs to; Maghrib and Isha
read at or beyond the day length rather than rolling to the next label. Events with no instant (high latitude Fajr/Isha)
have `gregorian` and `waqt` null.

## 2. Operations

| Variable | Default | Effect |
|---|---|---|
| `WAQT_ALADHAN_ENABLED` | `1` | `0` → never call out; `aladhan` answers from the local fallback (`fallback_reason: disabled`) |
| `WAQT_ALADHAN_BASE_URL` | `https://api.aladhan.com/v1` | http(s) only |
| `WAQT_ALADHAN_METHOD` | unset | AlAdhan `calendarMethod` |
| `WAQT_ALADHAN_TIMEOUT` / `_CACHE_TTL` / `_RPM` | `3` / `43200` / `30` | seconds / seconds / outbound requests per minute |
| `WAQT_RATE_LIMIT` | unset (off) | `N/second\|minute\|hour`; malformed → startup error |
| `WAQT_TRUST_PROXY`, `WAQT_TRUSTED_PROXY_HOPS` | off, `1` | key the limiter on `X-Forwarded-For`, counted from the **right** (forged leading entries are ignored). Only enable behind a real proxy |
| `WAQT_RATE_LIMIT_EXEMPT` | `/v1/health` | path prefixes not limited |
| `WAQT_CORS_ORIGINS` | unset (off) | unchanged from Sprint 12 |

**Rate limiting** is a sliding window per client, in memory, per process (bounded at 10 000 tracked clients). Several
worker processes each keep their own budget. Rejections are ordinary envelopes (`429 RATE_LIMITED`, `Retry-After`,
`X-RateLimit-Limit/Remaining/Reset`) and carry CORS headers so browser apps can read them.

**`GET /v1/health`** never performs network I/O. It returns `status:"ok"` whenever the engine can serve, plus
`integrations.hijri_aladhan` (circuit state, cache size, counters, last failure reason). A degraded integration is reported,
not treated as downtime. **`GET /v1/version`** gains `integrations` (`calendar_providers`, the provider's identity,
`affects_astronomy: false`).

## 3. What was and was not verified

Verified (no internet needed): provider behaviour with injected transports and a fake clock; the real `urllib`
transport against a local fake AlAdhan on real sockets (`verification/fake_aladhan.py`); the API end to end over real HTTP
(`verification/live_stack_check.py`); a real headless Chrome with CORS enforced (`verification/browser/run_sprint14.sh`).

**Not verified: the real `api.aladhan.com`.** It was unreachable from the build environment. The response shape that is
parsed comes from AlAdhan's public documentation and is exercised only against the fake. The 1900–2076 window is a
conservative choice, not a documented AlAdhan limit. Run once against the real service before relying on it:

```bash
curl -s https://api.aladhan.com/v1/gToH/30-09-2026
python -c "from waqt_core.calendar_providers import AlAdhanHijriProvider as A; from datetime import date; h=A().from_gregorian(date(2026,9,30)); print(h.source, h)"
```

`source` should be `remote`. If it prints `local-fallback`, `h.provenance.fallback_reason` says why.
