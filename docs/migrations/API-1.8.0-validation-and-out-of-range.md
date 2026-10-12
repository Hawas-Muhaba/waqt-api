# Migration record: API 1.8.0 — profile validation and out-of-range calendar dates

| | |
|---|---|
| **Applies from** | API contract **1.8.0** (`GET /v1/version` → `api_version`). **Not released:** no tag, package or manifest has been published. |
| **URL namespace** | Unchanged: `/v1`. A route change would be needed only for a response-shape break; none is made. |
| **Decision** | Project owner instruction of 2026-10-11, recorded in [DR-0011](../../conformance/decisions/DR-0011.md), [DR-0012](../../conformance/decisions/DR-0012.md) and [DR-0013](../../conformance/decisions/DR-0013.md). **No independent review and no signed ratification artifact is held.** |
| **Why 1.8.0** | The service is deployed and external use of 1.7.0 is **unknown** (the repository has no tags, no usage data). This project does **not** claim that 1.7.0 had no consumers; the observable behaviour changes below are given a new contract number as the conservative choice. |
| **Preserved** | The 1.7.0 vector recordings (`sdks/vectors/sdk_conformance_vectors_api_1_7.json`, `verification/vector_migrations/api-1.6.0-to-1.7.0.json`) and `docs/migrations/API-1.7.0-default-provider.md` are unchanged. |

## What changes

### 1. Astronomy profile parameters are validated (ERR-004)
| parameter | valid | before 1.8.0 | from 1.8.0 |
|---|---|---|---|
| `fajr_angle` (`profile.fajr_angle_deg`) | finite number, `0 < x <= 90` | `95`, `-5`, `nan` accepted (HTTP 200, meaningless times) | `422 VALIDATION_ERROR` |
| `isha_angle` | finite number, `0 < x <= 90` | `0` accepted | `422 VALIDATION_ERROR` |
| `asr_ratio` (`profile.asr_shadow_ratio`) | finite number, `x > 0` | `0` accepted | `422 VALIDATION_ERROR` |

The error is the standard envelope with `error.details = {parameter, received, expected}`. Nothing is clamped or defaulted; an *omitted* parameter keeps its default (18, 17, 1).
Applies to `/v1/waqt`, `/v1/events`, `/v1/calendar/convert` and `POST /v1/schedule/*`, and equally to `waqt-core`, `waqt-local` and the CLI. The SDKs do not validate (by design); the server's answer is relayed.
**Risk:** a client that sent an out-of-range value used to receive a (wrong) result and now receives 422.

### 2. Dates outside the calendar provider's range never fail a Waqt computation (CAL-013)
The default provider is **`umm-al-qura`** (since 1.7.0), supported range 1700-01-01..2300-12-31. Outside it, `/v1/waqt`, `/v1/day`-style Waqt results and `/v1/calendar/convert` return **HTTP 200** with the Waqt day and every instant unchanged, a `null` Hijri label, and `calendar_error` saying the date is outside the provider's supported range. Both routes also return additive `calendar_error_code: "OUT_OF_RANGE"` (or `"CALENDAR_ERROR"` for another label-provider failure).
`GET /v1/hijri` and `/v1/conversions` have no Waqt day to return and still answer `400 OUT_OF_RANGE`. HTTP 500 is never returned for this condition. Pass `calendar_provider=arithmetic-tabular` to have such dates labelled.
**Shape caveat (unchanged in 1.8.0):** `calendar_error` is an object `{provider, message}` on `/v1/waqt` and a plain string on `/v1/calendar/convert`. The additive sibling `calendar_error_code` resolves the machine-code mapping without changing those display fields. Any future normalization still requires a separate consumer compatibility review and appropriate versioning.

### 3. JSON request input types (DR-0014)
JSON body values are validated by JSON type and are not coerced. ERR-004 profile values must be finite JSON numbers: JSON `null`, numeric strings such as `"18"`, booleans and other strings are rejected with `422 VALIDATION_ERROR`. Omit an optional profile field to use its default. Integer fields such as `hijri_year`, calendar-rule `month`/`day`/`n`, and `year_offset` must be JSON integers. `hijri_year` must be positive. Optional body fields use their documented default only when omitted; explicit `null` is rejected unless a field is explicitly nullable (for example, `interval.start` and `interval.end` in an open scheduling interval).

HTTP query parameters remain textual on the wire, so well-formed numeric query strings such as `"18"` are parsed according to the endpoint's declared type; malformed text including literal `"null"` is rejected with `422`. This decision tightens malformed JSON-body inputs to `422` and specifies ERR-004 null/string behavior for both transports.

## What a consumer should do
1. Treat `hijri: null` / `hijri_date: null` as a normal answer and read `calendar_error`; do not assume a label exists.
2. Handle `422 VALIDATION_ERROR` for profile values; validate angles to `(0, 90]` and the ratio to `> 0` before sending if you accept user input.
3. If you need 1.7.0's exact behaviour for out-of-range profile values: there is no flag; the values were not physical.
4. Check `GET /v1/version` → `api_version`; the SDKs treat 1.8.0 as their newest tested version.
5. Send JSON numbers in request bodies and omit unused optional fields instead of sending `null`.

## Open items (not decided by this change)
1. Signed ratification artifacts for DR-0011, DR-0012, DR-0013 and the independent-review role (CCP-0001) remain unfilled.
2. Whether 1.7.0 was consumed externally: the owner states there is no registry publication and no public deployment (not independently verified); private or local use is unknown.
3. Unifying the shape of `calendar_error` would be a response-shape change; do not make it without compatibility review and appropriate versioning.
4. The independent Node implementation represents instants as Number microseconds and cannot exactly represent them after about 2255. Upper-range date vectors do not establish full-range instant conformance; no full-range instant claim is made. A second independent verification method is required before making such a claim.
