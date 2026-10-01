// waqt-client — official thin JavaScript/TypeScript SDK for the Waqt API.
//
//   Waqt Specification
//          |
//      HTTP / JSON
//          |
//    waqt-client (this package)   <-- ergonomic types + functions,
//          |                          the wire contract preserved
//    Your application
//
// This package is a REMOTE API CLIENT, not a local reimplementation of
// Waqt's astronomical/calendar rules. See README.md's "What this SDK is
// / is not" section.

export { WaqtClient } from "./client.mjs";
export { makeConfig } from "./config.mjs";
export { WaqtApiError, WaqtError, WaqtTransportError, WaqtVersionMismatch } from "./errors.mjs";
export * as types from "./types.mjs";
export * as requests from "./requests_types.mjs";
export const VERSION = "0.3.1";
