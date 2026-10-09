# waqt-client (JavaScript / TypeScript)

Official thin JavaScript/TypeScript SDK for the [Waqt API](../../../docs/API.md).

```
Waqt Specification
       |
   HTTP / JSON
       |
  waqt-client        <-- this package: ergonomic types + functions
       |                  over the wire contract, nothing more
Your application
```

**This is a remote API client, not a local reimplementation of Waqt's
rules.** Every value it returns came from a live `/v1/*` HTTP response.
See "What this SDK is / is not" below.

## Install

```bash
npm install ./sdks/js/waqt-client     # from a checkout
```

Requires Node.js >= 18 (built-in `fetch`). No runtime dependencies.

## Quick start

```js
import { WaqtClient } from "waqt-client";

const client = new WaqtClient({ baseUrl: "https://your-waqt-deployment.example.com" });

const resp = await client.getWaqt(9.0192, 38.7525);
console.log(resp.status);              // "OK"
console.log(resp.hijri.display);       // "7 Rabi al-Thani 1448 AH"
console.log(resp.waqt.display);        // "Waqt 00:19:21"
```

TypeScript consumers get full typing from `index.d.ts` with zero
configuration — `import { WaqtClient, WaqtResponse } from "waqt-client"`.

## Why async-only (no separate sync client)

The Python SDK ships both `WaqtClient` (sync) and `AsyncWaqtClient`,
because Python programs are commonly either. JavaScript's networking
primitives (`fetch`, Node's HTTP stack) are inherently non-blocking —
there is no idiomatic synchronous HTTP call to wrap. A single
promise-based `WaqtClient` **is** "synchronous/asynchronous requests
where appropriate" for this language.

## Configuration

```js
const client = new WaqtClient({
  baseUrl: "https://your-deployment.example.com",
  timeoutMs: 5000,
  defaultCalendarProvider: "umm-al-qura", // API 1.7.0 default; caller override still wins
  defaultAsrShadowRatio: 2.0,           // Hanafi, applied unless a call overrides it
  onVersionMismatch: "warn",            // "ignore" | "warn" | "raise"
});
```

Every method also accepts the endpoint's own query parameters as an
options object (camelCase — see docs/API.md for the underlying names);
a per-call option always overrides a config default.

## Error handling

```js
import { WaqtApiError, WaqtTransportError } from "waqt-client";

try {
  await client.getWaqt(999, 0);
} catch (err) {
  if (err instanceof WaqtApiError) {
    console.log(err.code, err.message, err.details); // "VALIDATION_ERROR", ...
  } else if (err instanceof WaqtTransportError) {
    console.log("network/parse problem:", err.message);
  }
}
```

`WaqtApiError.code` is exactly the `error.code` value documented in
docs/API.md — never a generic status-only exception. Codes are opaque
strings rather than a closed enum, including `INVALID_HIJRI_DATE`,
`UNKNOWN_TIMEZONE`, and `OUT_OF_RANGE` from API 1.6.0.

## What's covered

Methods for every `/v1/*` endpoint as of API version 1.6.0 — see
`src/client.mjs`. For anything not yet wrapped,
`client.request(method, path, { params, json })` is the same
envelope-aware call every typed method is built on.

API 1.6.0 / conformance contract 2.0.0 corrects the Waqt-day label to
the civil date of its closing Maghrib and defines `next_event` by
occurrence, including the previous solar day's Isha. The vector set is
2.0; the SDK preserves the responses and new error codes without a
closed enum.

## What this SDK is / is not

This package is a **remote Waqt API client**. It computes nothing itself
— no Maghrib instant, no Hijri date, no scheduling result. A **local
Waqt computation library** (no network round-trip) is a distinct,
separately-specified component this SDK deliberately does not pretend to
be. See `../../../docs/SDK.md`.

## Why plain JS, not a compiled TS build

This package's source is authored directly as JSDoc-annotated ESM
(`src/*.mjs`), with a hand-written `index.d.ts` alongside it, rather than
TypeScript source run through a compiler. That means: no build step, no
compiled-output drift, and the exact code a contributor edits is the
exact code Node runs — matching the zero-build style the existing
`consumers/js/` conformance consumer already established in this repo.
`tsconfig.json` (with `checkJs: true`) type-checks the JSDoc directly;
run `npx tsc --noEmit` to verify.

## Conformance

`test/conformance.test.mjs` parses
`sdks/vectors/sdk_conformance_vectors.json` — real, captured `/v1/*` HTTP
responses (success and error) — through this SDK's own parsing code and
checks the result. The Python SDK (`sdks/python/`) parses the exact same
file with its own, independent parser.

## Development

```bash
cd sdks/js/waqt-client
npm test              # runs both conformance and live-server integration tests
```

`test/client.test.mjs` spawns a real `python3 -m uvicorn waqt.api:app`
process and talks to it over an actual socket — not a mock.
