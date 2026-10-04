# Conformance Operation Protocol (COP) v1.1

COP is how an implementation of Waqt is exercised without sharing any code, language, or HTTP surface with
any other implementation. An implementation provides one **adapter**: a command-line program that is given
a batch of cases on standard input and answers on standard output. Everything else (the vectors, the
comparison rules, the report) lives in the harness and is language-neutral.

COP deliberately describes *observable behaviour*, not an architecture. Nothing here requires an HTTP
server, a particular module layout, or a particular astronomy method.

## 1. Adapter protocol

```
adapter                       reads  {"cases": [ {"id": "...", "op": "<operation>", "input": {...}} , ... ]}
adapter                       writes {"implementation": {...descriptor...},
                                      "results": [ {"id": "...", "ok": true,  "output": {...}} |
                                                   {"id": "...", "ok": false, "error": {"code": "...", "message": "..."}} ]}
adapter --describe            writes {"implementation": {...}, "operations": ["op", ...]}
```

* One result per case, matched by `id`, in any order.
* A case the adapter does not implement MUST return `ok:false, error.code = "UNSUPPORTED_OPERATION"`
  (the harness then reports the vector as *n.a.*, not as a failure).
* An adapter MUST NOT throw out of a case: an unexpected failure is reported as `INTERNAL_ERROR`, which
  is itself a conformance failure for any vector that expected a defined error.
* Descriptor fields: `name`, `version`, `language`, `cop_version`, `shares_code_with_reference` (honest
  self-declaration; the report prints it), and optionally `instant_precision_us` (see 4).

## 2. Wire conventions

| thing | rule |
|---|---|
| Instant | ISO 8601 date-time **with an explicit offset** (`Z` or `±hh:mm`); outputs are UTC with `+00:00`. Fractional seconds are kept to the microsecond; an all-zero fraction is omitted. |
| Date | `YYYY-MM-DD`, proleptic Gregorian. |
| Hijri date | `YYYY-MM-DD` (zero padded year/month/day). |
| Seconds | JSON numbers. Positions are SI seconds since the opening Maghrib. |
| Weekday names | Sunday-first Islamic names: `al-Ahad, al-Ithnayn, ath-Thulatha, al-Arbiaa, al-Khamis, al-Jumuah, as-Sabt`. |
| Hijri month names | `Muharram, Safar, Rabi al-Awwal, Rabi al-Thani, Jumada al-Awwal, Jumada al-Thani, Rajab, Shaban, Ramadan, Shawwal, Dhu al-Qadah, Dhu al-Hijjah`. |
| Absent vs null | A missing key and `null` are equivalent. A vector's `expect` is a **subset**: extra keys in an output are ignored; lists must have equal length. |
| Time zone | Every location-dependent case supplies the IANA zone in `timezone`. Zone lookup from coordinates is **out of scope** (it depends on third-party boundary data). |

## 3. Error vocabulary

Implementations map their native failures onto these codes. A vector may accept several (`error.code` is
a list) where the written specification does not choose one.

| code | meaning |
|---|---|
| `INVALID_INSTANT`, `INVALID_DATE` | malformed or non-existent instant / date |
| `VALIDATION_ERROR` | parameter outside its allowed range (latitude, longitude, …) |
| `UNKNOWN_CALENDAR_PROVIDER` | provider name not recognised |
| `UNSUPPORTED_OPERATION` | the provider/adapter cannot do this (reverse conversion for override providers; operation not implemented) |
| `UNKNOWN_TIMEZONE` | the named IANA zone does not exist (contract 2.0.0; no other code is acceptable) |
| `INVALID_HIJRI_DATE` | no such day in that Hijri month, or year < 1 (contract 2.0.0: required for well-formed non-existent dates) |
| `INVALID_CALENDAR_RULE` | an institutional rule cannot be resolved |
| `OUT_OF_RANGE` | outside a provider's supported range |
| `INTERNAL_ERROR` | **never** an acceptable answer to bad input |

`VALIDATION_ERROR`, `INVALID_INSTANT`, `INVALID_DATE`, `UNKNOWN_CALENDAR_PROVIDER`, `UNSUPPORTED_OPERATION`
and `INTERNAL_ERROR` are the codes already documented in `docs/API.md`. The rest are COP additions and are
listed as open questions where the written spec is silent.

## 4. Instant precision

Core semantics are defined on instants with microsecond resolution (`docs/SCHEDULING.md` §9). An
implementation whose output instants are truncated (the reference's `/v1/waqt` rounds to whole seconds)
declares `instant_precision_us` in its descriptor. The harness then probes day boundaries **one precision
unit either side** instead of ±1 µs and says so in the report. Exact-boundary conformance (DAY-002/003 at
1 µs) can therefore only be *demonstrated* by an implementation that publishes full-precision instants.

## 5. Operations

### `gregorian.weekday` — `{date}` → `{weekday_iso, weekday_name_islamic, is_leap_year, days_in_month}`
### `instant.parse` — `{value}` → `{instant}` (normalised to UTC) · errors `INVALID_INSTANT`
### `hijri.from_gregorian` — `{date, provider, params?}` → `{year, month, day, date, month_name, display, provider, source, fallback_reason}`
`provider` ∈ `arithmetic-tabular | umm-al-qura | declared | local-observation | aladhan`. `params` carries
`override_date` plus `declared:{year,month,day}` or `sighting:{year,month,day}`, `observed_at`.
`provider` in the output names the provider that **actually produced** the answer (`arithmetic-tabular`
when an override provider has no override for that date).
### `hijri.to_gregorian` — `{year, month, day, provider}` → `{date}`; `INVALID_HIJRI_DATE` for a day that does not exist.
### `hijri.month_length` — `{year, month, provider}` → `{days}`
### `hijri.year_table` — `{year, provider}` → `{months:[{month, start, length}]}`
### `hijri.provider_scenario` — scripted remote calendar provider
`{config?, steps:[{at_seconds, date, remote}]}` → `{steps:[{date, provider, source, fallback_reason}]}`.
`remote.kind` ∈ `ok{hijri}`, `timeout`, `network-error`, `http{status, retry_after?, hijri?}`, `malformed`,
`oversize`, `echo-mismatch{hijri}`. `config` keys: `enabled`, `ttl_seconds`, `max_stale_seconds`,
`cooldown_seconds`, `max_retry_after_seconds`, `max_plausible_delta_days`, `requests_per_minute`.
No network is ever touched: the remote is a model. Fallback reason vocabulary: `timeout, network-error,
upstream-rate-limited, upstream-server-error, upstream-rejected, malformed-response, date-mismatch,
implausible-response, date-outside-remote-window, disabled, circuit-open, outbound-rate-limited`.
### `waqt.compute`
Input: `{location:{lat,lon,elevation_m?}, instant, timezone, profile?:{fajr_angle_deg,isha_angle_deg,asr_shadow_ratio}, calendar?:{provider, params?}}`
Output: `{status: OK|UNDEFINED, undefined_reason, instant, timezone, profile, day:{open, close, length_seconds}, position:{seconds, display},
hijri:{date,…}, weekday, events:[{name, instant, reading_seconds, reading_display, local_date}], undefined_events:[{name}], next_event}`
* `events` lists only events that exist, in the order fajr, sunrise, dhuhr, asr, maghrib, isha. Absent events appear in `undefined_events`.
* `reading_seconds` = event instant − `day.open`. The closing Maghrib's reading equals `length_seconds`.
* When `status` is `UNDEFINED` all of `day, position, hijri, weekday, next_event` are null and `events` is empty.
### `schedule.run` — `{context, anchor, operation}` → the result object of `docs/SCHEDULING.md`
`context` is either **table mode** (`days[]`, `anchor_index`, `civil_utc_offset_seconds`: a frozen day table, answers must be exact) or **live mode**
(`location, timezone, profile, calendar`: the implementation computes its own days, answers compared within astronomy tolerance).
Operations: `resolve_point, resolve_interval, evaluate, check_deadline, until, since, event_position, day_bounds, next_event, classify_span`.
### `institutional.run` — `{operation, context}` → rule/week/fiscal/academic results
`context.calendar_provider` + `hijri_year`; an optional `month_table` freezes the calendar content (then it is authoritative).
### `calendar.represent_instant`, `calendar.gregorian_date_to_waqt_day`, `calendar.boundary_crossing`
As in `docs/CALENDAR-INTEROP.md`. `gregorian_date_to_waqt_day` additionally returns `hijri_date` and `weekday` of the resolved day. A civil date on which no Waqt day closes (DAY-009) is **not an error in the COP**: the operation succeeds with `resolved = false` (`reason` is free text). An HTTP implementation may report the same situation as an error response (the reference uses 422 `CALENDAR_DATE_UNRESOLVABLE`); its adapter must translate it.

## 6. Versioning

COP and the requirement catalogue (`spec/requirements.json`) are versioned together. Adding an operation,
a requirement or a vector is a minor change; changing an expected value of a `MUST` vector is a major change
and requires an entry in `OPEN-QUESTIONS.md` or `DISAGREEMENTS.md` explaining why.
