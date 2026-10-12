# Waqt API distribution changelog

## 0.6.0 — API 1.8.0 / conformance 2.0.0

- Strictly validate JSON-body numeric profile inputs; reject null, booleans and numeric strings. Query parameters are parsed from HTTP text according to their declared types.
- Add `calendar_error_code` to Waqt/calendar conversion responses while preserving the existing route-specific `calendar_error` display fields.
- Require `waqt-core>=0.6.0,<0.7`.

## 0.5.0

See the repository history and [`docs/API.md`](docs/API.md) for the API 1.8.0 and earlier behavior.
