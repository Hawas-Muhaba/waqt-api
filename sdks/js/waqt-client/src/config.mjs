// waqt-client/config — mirrors sdks/python/waqt_client/config.py.

export const SUPPORTED_API_MAJOR_VERSION = 1;
export const MIN_SUPPORTED_API_VERSION = "1.0.0";
export const MAX_KNOWN_API_VERSION = "1.3.0";

export const DEFAULT_BASE_URL = "https://waqt-api.onrender.com";
export const DEFAULT_TIMEOUT_MS = 10_000;

/**
 * @typedef {"ignore"|"warn"|"raise"} VersionMismatchPolicy
 */

/**
 * @typedef {object} WaqtClientConfig
 * @property {string} [baseUrl]
 * @property {number} [timeoutMs]
 * @property {string} [defaultCalendarProvider]
 * @property {number} [defaultFajrAngleDeg]
 * @property {number} [defaultIshaAngleDeg]
 * @property {number} [defaultAsrShadowRatio]
 * @property {string} [defaultTimezoneOverride]
 * @property {VersionMismatchPolicy} [onVersionMismatch]
 * @property {Record<string,string>} [extraHeaders]
 * @property {string} [userAgent]
 */

/** @param {Partial<WaqtClientConfig>} [overrides]
 *  @returns {WaqtClientConfig} */
export function makeConfig(overrides = {}) {
  return {
    baseUrl: DEFAULT_BASE_URL,
    timeoutMs: DEFAULT_TIMEOUT_MS,
    defaultCalendarProvider: undefined,
    defaultFajrAngleDeg: undefined,
    defaultIshaAngleDeg: undefined,
    defaultAsrShadowRatio: undefined,
    defaultTimezoneOverride: undefined,
    onVersionMismatch: "warn",
    extraHeaders: {},
    userAgent: "waqt-client-js/0.1.0",
    ...overrides,
  };
}
