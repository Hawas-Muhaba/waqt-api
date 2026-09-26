// waqt-client/envelope — mirrors sdks/python/waqt_client/_envelope.py.
// Pure functions: turn a parsed JSON body + status code into either the
// unwrapped `data` object or a thrown WaqtApiError/WaqtTransportError,
// plus the version-negotiation check.

import { MAX_KNOWN_API_VERSION, MIN_SUPPORTED_API_VERSION } from "./config.mjs";
import { WaqtApiError, WaqtTransportError, WaqtVersionMismatch } from "./errors.mjs";

function versionTuple(v) {
  const parts = String(v).split(".").slice(0, 3).map((p) => parseInt(p, 10));
  while (parts.length < 3) parts.push(0);
  return parts.every((n) => Number.isFinite(n)) ? parts : [0, 0, 0];
}

function lessOrEqual(a, b) {
  for (let i = 0; i < 3; i++) {
    if (a[i] !== b[i]) return a[i] < b[i];
  }
  return true;
}

/** @param {string|undefined} serverVersion
 *  @param {import("./config.mjs").VersionMismatchPolicy} policy */
export function checkVersion(serverVersion, policy) {
  if (policy === "ignore" || !serverVersion) return;
  const lo = versionTuple(MIN_SUPPORTED_API_VERSION);
  const hiMajor = versionTuple(MAX_KNOWN_API_VERSION)[0];
  const sv = versionTuple(serverVersion);
  const inRange = lessOrEqual(lo, sv) && sv[0] === hiMajor;
  if (inRange) return;

  const supported = `>= ${MIN_SUPPORTED_API_VERSION}, major version ${hiMajor}`;
  if (policy === "raise") {
    throw new WaqtVersionMismatch(serverVersion, supported);
  }
  // eslint-disable-next-line no-console
  console.warn(
    `waqt-client: server api_version '${serverVersion}' is outside this SDK's ` +
      `tested range (${supported}). Responses may not parse as expected.`
  );
}

/**
 * @param {number} statusCode
 * @param {any} body
 * @param {import("./config.mjs").VersionMismatchPolicy} versionPolicy
 * @returns {object}
 */
export function unwrap(statusCode, body, versionPolicy) {
  if (body === null || typeof body !== "object" || !("meta" in body)) {
    throw new WaqtTransportError(
      `Response (status ${statusCode}) did not match the documented Waqt API ` +
        `envelope (expected an object with 'meta'/'data'/'error' keys).`
    );
  }

  const meta = body.meta || {};
  checkVersion(meta.api_version, versionPolicy);

  if (statusCode >= 400 || body.error != null) {
    throw WaqtApiError.fromEnvelope(statusCode, body);
  }

  return body.data || {};
}
