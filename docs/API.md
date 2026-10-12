# Waqt API v1 Reference

Everything a caller needs to integrate Waqt without reading the Python source. If you want the *concepts* behind the numbers (why Maghrib is 00:00, why hours aren't always 60 minutes), read [`TIME-MODEL.md`](TIME-MODEL.md) first — this document is the wire contract.

Base URL: wherever you deployed it (e.g. `https://waqt-api.onrender.com`). Interactive docs are always at `/docs`.

---

## 1. Versioning

- The URL path carries the major version: every endpoint is under `/v1/`. A breaking change gets `/v2/`; `/v1/` never changes shape once released.
- Every response also carries `meta.api_version` (currently `1.8.0`, semver) for finer-grained tracking, and `meta.spec` (`waqt-core/0.1`) identifying which version of the underlying Core Time Model this deployment implements — these are two different things and can change independently.

- **1.6.0 (Sprint 16, conformance contract 2.0.0).** Additive: error codes `INVALID_HIJRI_DATE`, `UNKNOWN_TIMEZONE`, `OUT_OF_RANGE` (section 3). Two *corrections* to behaviour that contradicted the written specification, both recorded in `conformance/CHANGELOG.md`: the Hijri date / weekday of a Waqt day are those of the **civil** date of its closing Maghrib instant (SEMANTICS section 3, DAY-004), and `next_event` is the next event **by occurrence** (see `GET /v1/waqt`). No field was added, removed or renamed.
- **1.7.0.** The default `calendar_provider` for endpoints that accept it is now `umm-al-qura` (previously `arithmetic-tabular`) — a deliberate project default, not a claim that every community follows one convention. Callers that need the previous results send `calendar_provider=arithmetic-tabular`. Additive: `calendar_provider: {name, version}` is now present on `/v1/institutional/week`, `/fiscal-year`, `/academic-year` (and their `/resolve` forms) and `/v1/conversions`, so every provider-aware response names the provider used. `GET /v1/calendar/convert` no longer answers `500 INTERNAL_ERROR` for an instant or date outside `umm-al-qura`'s 1700..2300: it returns the Waqt day with `hijri: null` and a `calendar_error` (additive key, present only on failure). Canonical Waqt time never depends on the provider. Migration record, examples and risks: [`migrations/API-1.7.0-default-provider.md`](migrations/API-1.7.0-default-provider.md); provider caveats: [`CALENDARS.md`](CALENDARS.md).
- **1.8.0.** Two observable behaviour changes; **no field is removed or renamed and the `/v1` URL namespace is unchanged** (full record: [`migrations/API-1.8.0-validation-and-out-of-range.md`](migrations/API-1.8.0-validation-and-out-of-range.md)). (1) *Astronomy profile parameters are validated* (conformance ERR-004, DR-0011): `fajr_angle` and `isha_angle` must be finite numbers with `0 < x <= 90`, `asr_ratio` a finite number `> 0`; anything else (zero, negative, above range, `nan`, `inf`, non-numeric text) now returns `422 VALIDATION_ERROR` with `error.details {parameter, received, expected}` instead of a result. Nothing is clamped. (2) *Out-of-range calendar dates never fail a Waqt computation* (CAL-013, DR-0012): for a date outside the calendar provider's range (`umm-al-qura`: 1700-01-01..2300-12-31 — the **default** provider since 1.7.0) the Waqt day and every instant are returned unchanged, the Hijri label is `null` and `calendar_error` explains that the date is outside the provider's supported range (`/v1/waqt`: an object `{provider, message}`; `/v1/calendar/convert`: a string — the shapes are not unified in 1.8.0). `GET /v1/hijri` and `/v1/conversions`, which have no Waqt day to return, still answer `400 OUT_OF_RANGE`. No endpoint returns HTTP 500 for this condition.

## 2. The envelope

Every response, success or failure, has exactly this shape:

```json
{
  "meta": { "api_version": "1.8.0", "spec": "waqt-core/0.1", "generated_at": "2026-09-23T04:25:14Z" },
  "data": { ... or null on error ... },
  "error": { "code": "...", "message": "...", "details": {...} } // or null on success
}
```

`data` and `error` are mutually exclusive — exactly one is `null`. Never poll for success by checking HTTP status alone if you can check `error === null` instead; the shape is the same either way so your deserializer doesn't need two code paths.

## 3. Error codes

| Code | HTTP status | Meaning |
|---|---|---|
| `INVALID_INSTANT` | 400 | `instant` param isn't parseable ISO 8601 |
| `INVALID_DATE` | 400 | `date` param isn't parseable `YYYY-MM-DD` |
| `UNKNOWN_CALENDAR_PROVIDER` | 400 | `calendar_provider` isn't one of `GET /v1/calendar`'s list |
| `INVALID_RULE` | 400 | a `/v1/schedule/resolve` rule or operation is malformed (unknown event, wrong type, bad nesting). A caller mistake — distinct from a well-formed rule whose astronomy is undefined, which is a `200` with a `status` |
| `INVALID_HIJRI_DATE` | 400 | (1.6.0) a Hijri `year`/`month`/`day` that does not exist in the requested calendar: year < 1, or a day beyond that month's length (`1448-02-30` under `arithmetic-tabular`). It is never normalised into a neighbouring month. Month/day numerals outside 1-12 / 1-30 may instead be `VALIDATION_ERROR` (CAL-004). `details` carries `received`, `calendar_provider`, `reason`. |
| `UNKNOWN_TIMEZONE` | 400 | (1.6.0) `timezone_override` (query or body) is not an IANA zone name. Applies to every endpoint that accepts it. `details` carries `parameter`, `received`, `expected`. Before 1.6.0 this was an HTTP 500 `INTERNAL_ERROR`. |
| `OUT_OF_RANGE` | 400 | (1.6.0) a date outside the chosen calendar provider's supported range; `umm-al-qura` supports 1700-01-01..2300-12-31 only (CAL-011). `details` carries `calendar_provider`, `supported_range`, `received`. |
| `UNSUPPORTED_OPERATION` | 400 | e.g. asking `declared` or `local-observation` to reverse-convert, which they structurally can't |
| `VALIDATION_ERROR` | 422 | a query parameter's own constraints failed (e.g. `lat` out of ±90, `month` out of 1–12; (1.8.0) `fajr_angle` / `isha_angle` not a finite number in `(0, 90]`, `asr_ratio` not a finite number `> 0`; an unknown time zone is `UNKNOWN_TIMEZONE`, not this) — this is FastAPI/pydantic's own validation, reshaped into the same envelope |
| `RATE_LIMITED` | 429 | (1.5.0, only when the operator enabled `WAQT_RATE_LIMIT`) the caller exceeded its request budget. `Retry-After` and `details.retry_after_seconds` say when to retry. |
| `INTERNAL_ERROR` | 500 | anything unexpected. **Every** exception is caught here — you will never receive a raw stack trace or an empty connection reset. `details.exception_type` names the underlying Python exception for bug reports, nothing more. |

Every code above is exercised by a real test in `tests/test_api.py` (the three codes added in 1.6.0 in `tests/test_sprint16_api.py`) — none of this table is aspirational.

## 4. Units, precision, null behavior

- **Instants**: ISO 8601, UTC, explicit offset, rounded to the whole second at the response boundary (`2026-09-19T15:42:00+00:00`). Internal computation is not rounded until this point.
- **Durations / clock readings** (the Waqt reading, event positions, countdowns): never a bare string. Always `{"display": "HH:MM:SS", "seconds": <float>}`. `seconds` can exceed 86400 for a day that ran long — see `TIME-MODEL.md`. Use `seconds` for any arithmetic; `display` is for showing a human.
- **Angles**: degrees, floating point.
- **Elevation**: metres, floating point, ≥ 0.
- **Null-stable schema**: a given endpoint always returns the same top-level keys. When `status != "OK"` (e.g. `UNDEFINED` at a pole), fields that don't apply are `null`, never omitted. You can write one deserializer per endpoint and never check `if key in data`.

## 5. Timezone representation

Every block that has one:
```json
"timezone": { "name": "Africa/Addis_Ababa", "utc_offset_seconds": 10800 }
```
`name` is the real IANA zone (resolved from coordinates via `timezonefinder`, not guessed from longitude). `utc_offset_seconds` is the offset **actually in effect at the returned instant** — already resolved for DST, so you don't need your own timezone database just to render local time.

## 6. Provider and profile identification

Every Hijri date carries its source:
```json
"hijri": { "date": "1448-04-09", "provider": { "name": "umm-al-qura", "version": "astronomical-approx-2002-rules-v1" }, ... }
```
Every response using the solar engine carries:
```json
"computation": { "astronomy_engine": "waqt-noaa-low-precision", "accuracy_level": "B", "timescale_model": "espenak-meeus-2006", "delta_t_seconds": 75.5 }
```
`accuracy_level` is always `"B"` right now — see `ASTRONOMY.md` for what that means numerically and why Level A isn't implemented yet. A number without knowing which engine/profile produced it is not trustworthy; this block exists so you never have that problem.

---

## 7. Endpoints

### `GET /v1/waqt` — the full result
Everything: day boundary, clock reading, all six events, Hijri date, timezone.

| Param | Required | Default | Notes |
|---|---|---|---|
| `lat`, `lon` | yes | — | WGS84 degrees |
| `elevation_m` | no | `0` | metres |
| `instant` | no | now | ISO 8601 UTC |
| `timezone_override` | no | (looked up) | force an IANA zone, skip lookup |
| `fajr_angle`, `isha_angle` | no | `18.0`, `17.0` | degrees below horizon |
| `asr_ratio` | no | `1.0` | `1.0` standard, `2.0` Hanafi |
| `calendar_provider` | no | `umm-al-qura` | default since API 1.7.0; see `GET /v1/calendar` and section 6 |
| `override_date`, `declared_year/month/day` | no | — | see §8 below — **only take effect if `override_date` exactly matches the label date** |
| `sighting_year/month/day`, `observed_at` | no | — | same, for `local-observation` |

**`next_event` (clarified in 1.6.0, EVT-007).** `data.next_event` is the chronologically earliest event strictly after `instant`, taken over this day's listed events **and the previous solar day's Isha**. Right after Maghrib it is therefore tonight's Isha, not tomorrow's Fajr. `data.events` is unchanged: it is the listing of the current Waqt day. If no event after `instant` is defined, `next_event` is `null`.

### `GET /v1/day` — day boundary only
Same location/instant/timezone params as above. No astronomy profile, no calendar — Maghrib doesn't depend on either. Returns `status`, `location`, `timezone`, `day`, `computation`.

### `GET /v1/events` — the six events only
Same location/instant/timezone/profile params as `/v1/waqt`. **No `calendar_provider` param at all** — deliberately: the calendar cannot influence solar astronomy, and this endpoint's shape proves it.

### `GET /v1/hijri` — calendar lookup, no location
```
GET /v1/hijri?date=2026-09-20&calendar_provider=umm-al-qura
```
**Takes no `lat`/`lon`.** Per the Core Time Model, the Gregorian→Hijri mapping is location-independent — Makkah computes the date once, for everyone. See §8 for the one thing that trips people up here.
When omitted, `calendar_provider` defaults to `umm-al-qura`, as on the other API endpoints that accept a provider.

### `GET /v1/calendar` — provider discovery
No params. Lists every `calendar_provider` value, its description, whether it needs an override to do anything, and whether it supports reverse conversion.

### `GET /v1/location` — timezone/date resolution only
```
GET /v1/location?lat=1.8721&lon=-157.4278&instant=2026-09-19T23:00:00Z
```
Isolates the timezone lookup from everything else — useful for debugging a date that looks wrong elsewhere.

### `GET /v1/conversions` — Gregorian ↔ Hijri, standalone
```
GET /v1/conversions?direction=to-hijri&date=2026-09-20&calendar_provider=umm-al-qura
GET /v1/conversions?direction=to-gregorian&year=1448&month=4&day=10&calendar_provider=umm-al-qura
```
Only `arithmetic-tabular` and `umm-al-qura` support `to-gregorian` (they have a fixed rule to invert). `declared` and `local-observation` return `UNSUPPORTED_OPERATION` for that direction — a sparse override table has no general inverse, and this says so rather than guessing.

---

### Scheduling (added in 1.1.0 — additive; nothing in 1.0.0 changed)
Full semantics in [`SCHEDULING.md`](SCHEDULING.md).

- `GET /v1/schedule/snapshot` — `lat`, `lon`, `elevation_m`, `instant`, profile params, `calendar_provider` (labels only), `precision` (`second`|`microsecond`). Returns the Waqt day's bounds and position, the next event, and for each of the six events the time *until* the next and *since* the last occurrence.
- `GET /v1/schedule/span` — `start`, `end`, `end_inclusive`. Whether the span crosses a Maghrib boundary (every boundary listed), which Waqt days it touches, and, separately, whether it crosses civil midnight.
- `POST /v1/schedule/resolve` — body `{location, anchor, operation, profile?, calendar_provider?, timezone_override?, precision?}`; `operation` is the JSON format in `SCHEDULING.md` §8.

Undefined astronomy is a `200` with `status` `EVENT_UNDEFINED` / `WINDOW_UNDEFINED` / `NO_VALID_WINDOW`. Every response carries a `caveat`: Waqt provides temporal facts, not religious rulings. Durations are numeric SI seconds (`*_seconds`); positions are `{seconds, display}`.

---

### Calendar interoperability (added in 1.3.0 — additive; nothing earlier changed)
Full semantics in [`CALENDAR-INTEROP.md`](CALENDAR-INTEROP.md).

- `GET /v1/calendar/convert?direction=instant-to-calendars` (default) — `instant` (optional, defaults to now), `lat`/`lon`/`elevation_m` (optional), profile and `calendar_provider` params (all shared with `/v1/waqt`), `timezone_override`. Returns the instant rendered as UTC-Gregorian always, and — if a location was given — also as local civil-Gregorian and a Waqt day/position.
- `GET /v1/calendar/convert?direction=gregorian-date-to-waqt` — `date` (required), `lat`/`lon` (required). Returns the Waqt day whose closing Maghrib falls on that Gregorian civil date at that place.
- `GET /v1/calendar/boundary-crossing` — `start`, `end`, `lat`, `lon`, `elevation_m`, `timezone_override`. Whether the half-open span `[start, end)` crosses civil midnight and/or a Maghrib boundary, reported as two independent facts, plus the list of Maghrib instants strictly inside the span.

Undefined astronomy near a requested date/span is a `200` with `status`/`waqt.status` `"UNDEFINED"`, matching the rest of the API. An empty or reversed span (`end <= start`) is a `400 INVALID_SPAN`.

### Live integrations (added in 1.5.0 — additive; nothing earlier changed)

`calendar_provider=aladhan` (a live, cached Hijri date source with local fallback), `hijri.source` + `hijri.provenance` on
**every** Hijri block, `data.calendar_error` and `data.event_representations[]` on `/v1/waqt`, `integrations` in `/v1/health`
and `/v1/version`, `network` / `single_date_only` per provider in `/v1/calendar`, and `429 RATE_LIMITED`. A calendar
provider failing no longer fails `/v1/waqt`: `hijri` is `null` and `calendar_error` says why. Full contract, fallback reasons
and operations: **docs/LIVE-INTEGRATIONS.md**.

`GET /v1/health` remains `status:"ok"` when computation is available and reports separate `components.application`,
`components.computation`, and `components.optional_providers.aladhan` states (`unknown`, `available`, `degraded`, or
`disabled`). It performs no upstream request and returns `Cache-Control: no-store`. Cache policy is intentionally
bounded: `/v1/version` for 30 seconds, `/v1/calendar` for 5 minutes, and `/v1/waqt` for 30 seconds in a private cache
only when the request supplies an explicit `instant`; requests for the moving current time are `no-store`. The AlAdhan
provider separately caches Hijri answers by Gregorian date and method for 12 hours. Other computation results are not
shared-cached.

## 8. The one gotcha: which Gregorian date is "the" date

The Islamic day runs Maghrib-to-Maghrib, and per the Core Time Model, the Hijri label attached to a Waqt day is **the Gregorian date the *closing* Maghrib falls on** — not the date you'd naively read off the instant you queried.

Concretely: querying `/v1/waqt` for `2026-09-19T15:42:00Z` at Addis Ababa returns a Hijri date computed against **2026-09-20**, because that instant is already past that evening's Maghrib, and the day it's inside of closes at the *next* evening's Maghrib — whose Gregorian date is the 20th.

This matters directly for `override_date` on `/v1/waqt`, and for the `date` you pass to `/v1/hijri` if you're trying to match a specific `/v1/waqt` response: **use the date from that response's own `day.maghrib_close` (or, for `/v1/hijri`, whatever date you already know is the correct label)**, not the date of the instant you started from. If you don't already know it, call `/v1/day` or `/v1/waqt` first and read the label date off the result before calling `/v1/hijri` or setting `override_date`.

**Which date, exactly (1.6.0).** "The Gregorian date the closing Maghrib falls on" means the **civil date in the location's IANA zone** (or `timezone_override`), evaluated at the closing Maghrib *instant*. It does not mean the date in longitude-based solar time. Near local midnight this makes a few civil dates label no day or two days; see SEMANTICS section 3 (DAY-009).

## 9. A complete integration in under a minute

```bash
# 1. What calendars are available?
curl "$BASE/v1/calendar"

# 2. Where and when does today's Waqt day start/end?
curl "$BASE/v1/waqt?lat=9.0192&lon=38.7525" | jq '.data.day, .data.hijri, .data.waqt'

# 3. When's the next prayer, and how long until it?
curl "$BASE/v1/waqt?lat=9.0192&lon=38.7525" | jq '.data.next_event'
```
That's the whole integration for a typical wall-display or timetable use case — one call, three fields.


### The `hijri` object and provider identification (clarification)

`data.hijri` is the label of the *Waqt day* that contains `instant`, produced by the provider selected with
`calendar_provider` (default `umm-al-qura`). It always carries `year`, `month`, `month_name`, `day`, `display`
and `provider.{name,version}`, so a consumer can tell which calendar convention produced it. Different providers can
legitimately return different days for the same instant (see `docs/CALENDARS.md`, "Choosing a Hijri provider"); the
Waqt reading, day boundaries and events are identical across providers.
