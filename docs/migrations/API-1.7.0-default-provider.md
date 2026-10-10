# Migration record: API 1.7.0 — default Hijri calendar provider is `umm-al-qura`

| | |
|---|---|
| **Applies from** | API contract **1.7.0** (`GET /v1/version` → `api_version`) |
| **Change** | When `calendar_provider` is omitted, provider-aware endpoints now use **`umm-al-qura`** (before 1.7.0: `arithmetic-tabular`). |
| **Decision** | "Option B", chosen by the project owners Dr. Salim Muhammed Redi and Mr. Hawas Muhaba Hussein. The Umm al-Qura default is a deliberate project decision, **not** a claim that every Muslim community follows one calendar convention. |
| **Ratification** | Recorded in [DR-0009](../../conformance/decisions/DR-0009.md): ratified by **Dr. Salim Muhammed Redi** (Maintainer, `conformance/MAINTAINERS.md`), recorded 2026-10-10 on the report of the change requester. DR-0001 to DR-0008 carry the same ratification. **The repository holds no signed artifact** for any of these; the contract itself is still an unreleased 2.0.0. |
| **Unchanged** | Canonical Waqt time: Maghrib-to-Maghrib days, instants, event positions, countdowns and `waqt.reading` do not depend on the Hijri provider. Only Hijri labels (and the values derived from them) can differ. |

## 1. What changes for a caller

| Request | Before 1.7.0 | From 1.7.0 |
|---|---|---|
| `calendar_provider` omitted | `arithmetic-tabular` | `umm-al-qura` |
| `calendar_provider=umm-al-qura` | `umm-al-qura` | `umm-al-qura` (identical) |
| `calendar_provider=arithmetic-tabular` | `arithmetic-tabular` | `arithmetic-tabular` (identical) |
| unknown provider name | `400 UNKNOWN_CALENDAR_PROVIDER` | `400 UNKNOWN_CALENDAR_PROVIDER` (identical) |

Affected endpoints (all route through `waqt.api.providers.DEFAULT_CALENDAR_PROVIDER`): `GET /v1/waqt`, `/v1/hijri`, `/v1/conversions`, `/v1/calendar/convert`, `/v1/schedule/snapshot`, `/v1/schedule/span`, `/v1/institutional/week`, `/v1/institutional/fiscal-year`, `/v1/institutional/academic-year`, `/v1/institutional/profile`; `POST /v1/schedule/resolve`, `/v1/institutional/fiscal-year/resolve`, `/v1/institutional/academic-year/resolve`.
Endpoints with **no** provider (unchanged): `/v1/day`, `/v1/events`, `/v1/location`, `/v1/calendar/boundary-crossing`, `/v1/calendar`, `/v1/version`, `/v1/health`.

**Additive response change (1.7.0).** Every provider-aware response now says which provider it used, as `calendar_provider: {name, version}` (or the existing `hijri.provider`). Added to the shapes that did not name it before: `/v1/institutional/week`, `/v1/institutional/fiscal-year` and `/academic-year` (GET and `/resolve`), and `/v1/conversions` (both directions). No field was removed or renamed.

Other defaults that follow the rule: the `waqt-local` offline facade (`waqt_local.DEFAULT_CALENDAR_PROVIDER`), the `waqt` CLI (`--provider`), and Waqt Web (which sends `calendar_provider=umm-al-qura` explicitly, so what it shows never depends on a server default).

## 2. Reproducible examples (run against the current API)

```bash
uvicorn waqt.api:app --port 8000 &
curl 'localhost:8000/v1/hijri?date=2026-09-19'                                          # 8 Rabi al-Thani 1448 AH  (umm-al-qura)
curl 'localhost:8000/v1/hijri?date=2026-09-19&calendar_provider=arithmetic-tabular'     # 6 Rabi al-Thani 1448 AH
curl 'localhost:8000/v1/conversions?direction=to-gregorian&year=1448&month=4&day=7'     # 2026-09-18  (umm-al-qura)
curl 'localhost:8000/v1/conversions?direction=to-gregorian&year=1448&month=4&day=7&calendar_provider=arithmetic-tabular'  # 2026-09-20
curl 'localhost:8000/v1/institutional/profile'                                          # name: demo-umm-al-qura
```

At Addis Ababa, 2026-09-19T15:42:00Z the Waqt reading is `00:19:02` and Maghrib opened at `2026-09-19T15:22:57+00:00` under **both** providers; only the Hijri label differs (`9 Rabi al-Thani 1448 AH` vs `7 Rabi al-Thani 1448 AH`).

## 3. How existing `arithmetic-tabular` consumers keep their previous results

Send the provider explicitly on every request: `calendar_provider=arithmetic-tabular`. The SDKs pass it through (`calendar_provider="arithmetic-tabular"` / `calendarProvider: "arithmetic-tabular"`); the CLI takes `--provider arithmetic-tabular`; `waqt_local` takes `calendar_provider="arithmetic-tabular"`. The 11 pre-1.7.0 recordings are replayed this way by `verification/vector_additivity_check.py` and reproduce **byte-for-byte**.

## 4. Compatibility and migration risks

| Risk | Where | Mitigation |
|---|---|---|
| **High — same input, different date.** `GET /v1/conversions?direction=to-gregorian&year=1448&month=4&day=7` returns 2026-09-18 instead of 2026-09-20. Hijri dates that were *stored* and converted later change meaning. | `/v1/conversions`, `/v1/calendar/convert` (date-to-Waqt), institutional rule resolution | Store the provider name with every stored Hijri date; pin `calendar_provider` on conversions. |
| Medium — profile name changes (`demo-arithmetic-tabular` → `demo-umm-al-qura`). | `/v1/institutional/profile` | Do not key logic on the demo profile's name; pin a provider. |
| Medium — month lengths differ: `1448-02-30` and `1448-12-30` exist under umm-al-qura but are `INVALID_HIJRI_DATE` under arithmetic-tabular. | conversions | Validate under the provider you store. |
| Low — display days differ by 1–2 days on many dates. | all Hijri labels | Expected; see `docs/CALENDARS.md`. |
| Range — umm-al-qura supports 1700-01-01..2300-12-31 (`OUT_OF_RANGE` outside). Callers that relied on arithmetic-tabular for dates beyond that range **must** now name it. | all | Pin `arithmetic-tabular` outside the range. |
| Fallback chains are unchanged: `declared`, `local-observation` and `aladhan` still fall back to `arithmetic-tabular` for dates they do not cover (documented provider behaviour, not the default). | providers | None required. |

## 5. Versioned vectors (historical evidence is not rewritten)

* `sdks/vectors/sdk_conformance_vectors.json` (vector set 2.0) is **unchanged**. Eleven of its requests omit the provider and were recorded under the old default.
* `verification/vector_migrations/api-1.6.0-to-1.7.0.json` declares those 11 vector ids, their historical provider and the reason. `vector_additivity_check.py` replays exactly those requests with `calendar_provider=arithmetic-tabular` made explicit and requires the **recorded response to be reproduced** (the checker is otherwise unchanged and strict; `--no-migration` shows the raw 88 differences). A listed vector that already names a provider is refused.
* `sdks/vectors/sdk_conformance_vectors_api_1_7.json` records the same 11 requests with the provider omitted, **under the 1.7.0 default** (`governing_api_version: 1.7.0`), regenerated by `sdks/vectors/generate_api_1_7_default_provider_vectors.py`.

| Historical vector | Endpoint | Provider before → after | Change | Class |
|---|---|---|---|---|
| waqt-addis-normal | /v1/waqt | arithmetic-tabular → umm-al-qura | Hijri label 7 → 9 Rabi al-Thani 1448; every instant unchanged | expected consequence of Option B |
| waqt-hanafi-asr | /v1/waqt | same | Hijri label 6 → 8; Hanafi Asr instants unchanged | expected |
| hijri-ordinary | /v1/hijri | same | 2026-09-19 reads 6 → 8 | expected |
| conversions-to-hijri | /v1/conversions | same | label only | expected |
| conversions-to-gregorian | /v1/conversions | same | **1448-04-07 → 2026-09-18 (was 2026-09-20)** | expected, **high migration risk** |
| calendar-convert-instant | /v1/calendar/convert | same | Hijri label/provider only | expected |
| calendar-convert-date-to-waqt | /v1/calendar/convert | same | Hijri label/provider only | expected |
| schedule-snapshot | /v1/schedule/snapshot | same | label + provider only | expected |
| schedule-span | /v1/schedule/span | same | labels + provider only | expected |
| institutional-week | /v1/institutional/week | same | per-day labels; week membership unchanged | expected |
| institutional-profile | /v1/institutional/profile | same | profile name follows the default | expected, medium risk |

All eleven are *expected consequences of the approved change*. No astronomy output moved (a test asserts that, after removing Hijri labels, old and new recordings are identical), and no value was rewritten to make a stale fixture pass.

## 6. Verification added

`tests/test_default_provider_option_b.py` (every provider-aware route: omitted / explicit / other / invalid / named / deterministic; canonical-time independence over a location grid; historical reproducibility; new-vector accuracy), `verification/live_stack_check.py` (documented-version assertions on a real socket), and `verification/browser/run_web_option_b.sh` (real Chrome, 58 assertions). Reverting `DEFAULT_CALENDAR_PROVIDER` makes 46 of those tests fail.

## 7. Open items (not decided by this change)

The ratification and the versioning rule are settled by DR-0009 (policy text in `docs/VERSIONING.md` section 4). What remains:

1. **Signed artifact.** The ratification is recorded in the decision records on the requester's report; attach or link whatever signed record the project keeps if one is wanted.
2. **`waqt-core` library default.** `core/waqt_core/calendar_interop._DEFAULT_PROVIDER` is still `ArithmeticTabularProvider`: it is used only when a *core* caller passes no provider (the HTTP API always passes one). It is tied to contract 2.0.0 and was deliberately not changed. Decide whether the library default should follow the API default (a `waqt-core` behaviour change).
3. **Package versions.** `waqt-local` (0.5.0) and `waqt-cli` (0.1.0) now default to `umm-al-qura`; their version bumps and changelog entries belong to the release step, which was not performed.
4. **External consumption of 1.7.0** is unknown (no tags or usage data in the repository); owners may wish to notify known consumers.
