// waqt-client/client — WaqtClient, the (async) Waqt API client.
//
// Thin over the `/v1/*` HTTP/JSON contract: every method builds query
// parameters (requests.mjs), makes exactly one HTTP call via the
// platform `fetch`, unwraps the response envelope (envelope.mjs), and
// returns a typed object (types.mjs). Async is the "synchronous vs
// asynchronous requests where appropriate" choice for JavaScript --
// `fetch` and Node's HTTP stack are inherently non-blocking, so a
// promise-based API is what "appropriate" means in this language,
// mirroring the Python SDK's separate sync/async classes with the one
// idiom JS actually has.
//
// No method here recomputes a Waqt rule or second-guesses the server --
// this SDK is a thin, spec-driven client, not another implementation of
// Waqt's astronomical/calendar rules. See ../README.md.

import { unwrap } from "./envelope.mjs";
import { makeConfig } from "./config.mjs";
import { WaqtTransportError } from "./errors.mjs";
import * as R from "./requests.mjs";
import * as T from "./types.mjs";

export class WaqtClient {
  /** @param {Partial<import("./config.mjs").WaqtClientConfig>} [config] */
  constructor(config = {}) {
    this.config = makeConfig(config);
  }

  /**
   * Escape hatch: raw call to any `/v1/*` path, returning the unwrapped
   * `data` object. Every typed method below is built on this -- so an
   * endpoint this SDK hasn't grown a typed wrapper for yet is still
   * reachable without waiting for a new release.
   * @param {string} method
   * @param {string} path
   * @param {{params?: object, json?: object}} [opts]
   */
  async request(method, path, { params, json } = {}) {
    const url = new URL(path, this.config.baseUrl);
    if (params) {
      for (const [k, v] of Object.entries(params)) {
        if (v !== undefined && v !== null) url.searchParams.set(k, String(v));
      }
    }

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.config.timeoutMs);

    let response;
    try {
      response = await fetch(url, {
        method,
        headers: {
          "User-Agent": this.config.userAgent,
          ...(json ? { "Content-Type": "application/json" } : {}),
          ...this.config.extraHeaders,
        },
        body: json ? JSON.stringify(json) : undefined,
        signal: controller.signal,
      });
    } catch (cause) {
      if (cause.name === "AbortError") {
        throw new WaqtTransportError(`Request to ${path} timed out.`, cause);
      }
      throw new WaqtTransportError(`Request to ${path} failed: ${cause.message}`, cause);
    } finally {
      clearTimeout(timer);
    }

    let body = null;
    try {
      body = await response.json();
    } catch {
      body = null;
    }
    return unwrap(response.status, body, this.config.onVersionMismatch);
  }

  async #get(path, params) {
    return this.request("GET", path, { params });
  }

  // -- core time model ----------------------------------------------------

  /** `GET /v1/waqt` — full result: day boundary, Waqt clock position,
   * all six events, Hijri date, timezone, computation. */
  async getWaqt(lat, lon, opts = {}) {
    const merged = {
      calendarProvider: this.config.defaultCalendarProvider,
      fajrAngle: this.config.defaultFajrAngleDeg,
      ishaAngle: this.config.defaultIshaAngleDeg,
      asrRatio: this.config.defaultAsrShadowRatio,
      timezoneOverride: this.config.defaultTimezoneOverride,
      ...opts,
    };
    const data = await this.#get("/v1/waqt", R.waqtParams(lat, lon, merged));
    return T.parseWaqtResponse(data);
  }

  /** `GET /v1/day` — just the day boundary. */
  async getDay(lat, lon, opts = {}) {
    const data = await this.#get("/v1/day", R.dayParams(lat, lon, opts));
    return T.parseWaqtResponse(data);
  }

  /** `GET /v1/events` — just the six solar/prayer events. */
  async getEvents(lat, lon, opts = {}) {
    const data = await this.#get("/v1/events", R.eventsParams(lat, lon, opts));
    return T.parseWaqtResponse(data);
  }

  /** `GET /v1/location` — timezone + local civil date for a place. */
  async getLocation(lat, lon, opts = {}) {
    const data = await this.#get("/v1/location", R.locationParams(lat, lon, opts));
    return T.parseLocationInfo(data);
  }

  // -- calendars ------------------------------------------------------------

  /** `GET /v1/hijri` — Gregorian date -> Hijri date. Location-independent. */
  async getHijri(opts = {}) {
    const data = await this.#get("/v1/hijri", R.hijriParams(opts));
    return T.parseWaqtResponse({
      status: "OK", hijri: data.hijri, weekday: data.weekday,
    });
  }

  /** `GET /v1/calendar` — every registered calendar provider. */
  async listCalendarProviders() {
    const data = await this.#get("/v1/calendar", {});
    return (data.providers || []).map(T.parseCalendarProviderInfo);
  }

  /** `GET /v1/conversions` — bidirectional Gregorian <-> Hijri,
   * independent of instant/location/astronomy. `direction` is
   * `"to-hijri"` or `"to-gregorian"`. */
  async convert(direction, opts = {}) {
    const data = await this.#get("/v1/conversions", R.conversionsParams(direction, opts));
    return T.parseConversionResult(data);
  }

  /** `GET /v1/calendar/convert?direction=instant-to-calendars` — an
   * instant as UTC-Gregorian always, plus local-civil-Gregorian and a
   * Waqt day/position if `lat`/`lon` are given. */
  async representInstant(opts = {}) {
    const data = await this.#get(
      "/v1/calendar/convert",
      R.calendarConvertParams({ direction: "instant-to-calendars", ...opts })
    );
    return T.parseInstantRepresentation(data);
  }

  /** `GET /v1/calendar/convert?direction=gregorian-date-to-waqt` — the
   * reverse: a Gregorian civil date + place -> the Waqt day whose
   * closing Maghrib falls on that date. */
  async waqtDayForGregorianDate(date, lat, lon, opts = {}) {
    const data = await this.#get(
      "/v1/calendar/convert",
      R.calendarConvertParams({ direction: "gregorian-date-to-waqt", date, lat, lon, ...opts })
    );
    return T.parseInstantRepresentation(data);
  }

  /** `GET /v1/calendar/boundary-crossing` — does the half-open span
   * `[start, end)` cross civil midnight, Maghrib, both, or neither. */
  async boundaryCrossing(start, end, lat, lon, opts = {}) {
    const data = await this.#get(
      "/v1/calendar/boundary-crossing",
      R.boundaryCrossingParams(start, end, lat, lon, opts)
    );
    return T.parseBoundaryCrossingResult(data);
  }

  // -- scheduling (Sprint 6) ------------------------------------------------

  /** `GET /v1/schedule/snapshot`. */
  async scheduleSnapshot(lat, lon, opts = {}) {
    const data = await this.#get("/v1/schedule/snapshot", R.snapshotParams(lat, lon, opts));
    return T.parseSchedulingResult(data);
  }

  /** `GET /v1/schedule/span`. */
  async scheduleSpan(lat, lon, start, end, opts = {}) {
    const data = await this.#get("/v1/schedule/span", R.spanParams(lat, lon, start, end, opts));
    return T.parseSchedulingResult(data);
  }

  /** `POST /v1/schedule/resolve`. `body` is the same JSON shape
   * docs/SCHEDULING.md documents; this SDK does not model every
   * operation type, since the request body itself is the wire
   * contract. */
  async scheduleResolve(body) {
    const data = await this.request("POST", "/v1/schedule/resolve", { json: body });
    return T.parseSchedulingResult(data);
  }

  // -- institutional calendars (Sprint 7) ------------------------------------

  async institutionalWeek(lat, lon, opts = {}) {
    const data = await this.#get("/v1/institutional/week", R.institutionalWeekParams(lat, lon, opts));
    return T.parseInstitutionalResult(data);
  }

  async institutionalFiscalYear(opts = {}) {
    const data = await this.#get("/v1/institutional/fiscal-year", opts);
    return T.parseInstitutionalResult(data);
  }

  async institutionalAcademicYear(opts = {}) {
    const data = await this.#get("/v1/institutional/academic-year", opts);
    return T.parseInstitutionalResult(data);
  }

  async institutionalDefaultProfile(opts = {}) {
    const data = await this.#get("/v1/institutional/profile", R.institutionalProfileParams(opts));
    return T.parseInstitutionalResult(data);
  }

  async institutionalFiscalYearResolve(body) {
    const data = await this.request("POST", "/v1/institutional/fiscal-year/resolve", { json: body });
    return T.parseInstitutionalResult(data);
  }

  async institutionalAcademicYearResolve(body) {
    const data = await this.request("POST", "/v1/institutional/academic-year/resolve", { json: body });
    return T.parseInstitutionalResult(data);
  }

  // -- misc -----------------------------------------------------------------

  /** `GET /v1/health`. */
  async health() {
    const url = new URL("/v1/health", this.config.baseUrl);
    const response = await fetch(url);
    return response.json();
  }
}
