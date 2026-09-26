// waqt-client/errors — mirrors sdks/python/waqt_client/errors.py's shape
// exactly (same three classes, same fields), so a caller who has used
// either SDK recognizes the other immediately.

export class WaqtError extends Error {
  constructor(message) {
    super(message);
    this.name = "WaqtError";
  }
}

/** The server answered with a structured error envelope
 * (`{meta, data: null, error: {code, message, details}}`). */
export class WaqtApiError extends WaqtError {
  /**
   * @param {number} statusCode
   * @param {string} code
   * @param {string} message
   * @param {object} [details]
   */
  constructor(statusCode, code, message, details = {}) {
    super(`[${code}] ${message}`);
    this.name = "WaqtApiError";
    this.statusCode = statusCode;
    this.code = code;
    this.message = message;
    this.details = details;
  }

  static fromEnvelope(statusCode, body) {
    const err = (body && body.error) || {};
    return new WaqtApiError(
      statusCode,
      err.code || "UNKNOWN_ERROR",
      err.message || "The API returned an error with no message.",
      err.details || {}
    );
  }
}

/** Network-level failure, or a response that didn't match the documented
 * envelope at all. No server-issued error code to branch on. */
export class WaqtTransportError extends WaqtError {
  constructor(message, cause) {
    super(message);
    this.name = "WaqtTransportError";
    this.cause = cause;
  }
}

/** The server's `meta.api_version` is outside this SDK's supported range
 * (only thrown if `onVersionMismatch: "raise"` is configured). */
export class WaqtVersionMismatch extends WaqtError {
  constructor(serverVersion, supported) {
    super(
      `Server API version '${serverVersion}' is outside this SDK's supported ` +
        `range (${supported}). Upgrade/downgrade the SDK, or the server, to match.`
    );
    this.name = "WaqtVersionMismatch";
    this.serverVersion = serverVersion;
    this.supported = supported;
  }
}
