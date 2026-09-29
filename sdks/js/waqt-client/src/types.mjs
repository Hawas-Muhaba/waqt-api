// waqt-client/types — mirrors sdks/python/waqt_client/types.py: the same
// typed representations (Waqt response, Waqt instant/position, Hijri
// date, Gregorian representation, astronomical event, scheduling
// result, institutional calendar result), parsed from the exact same
// wire JSON. Plain frozen objects + parse functions (not classes) --
// the idiomatic shape for a thin JS SDK -- each keeps the original
// parsed JSON on `.raw` for forward compatibility, same as the Python
// side. None of these functions compute or validate a Waqt rule; they
// only reshape what the server already said (see this package's
// README "What this SDK is / is not").

function parseInstant(s) {
  return s == null ? null : new Date(s);
}

/** @param {any} d */
export function parseLocation(d) {
  if (d == null) return null;
  return { lat: d.lat, lon: d.lon, elevationM: d.elevation_m ?? null };
}

export function parseTimezoneInfo(d) {
  if (d == null) return null;
  return { name: d.name, utcOffsetSeconds: d.utc_offset_seconds ?? null };
}

/** A duration/position on the Waqt hour grid: display string + machine
 * seconds (can exceed 24:00:00 -- reflected as-is, never clamped). */
export function parseReading(d) {
  if (d == null) return null;
  return { display: d.display, seconds: d.seconds };
}

export function parseAstronomyProfile(d) {
  if (d == null) return null;
  return {
    name: d.name,
    fajrAngleDeg: d.fajr_angle_deg,
    ishaAngleDeg: d.isha_angle_deg,
    asrShadowRatio: d.asr_shadow_ratio,
  };
}

export function parseComputationInfo(d) {
  if (d == null) return null;
  const engine = d.engine ?? d.astronomy_engine ?? null;
  return {
    // Pre-1.4.0 name of `engine`; kept (same value) for compatibility.
    astronomyEngine: d.astronomy_engine ?? engine,
    // Sprint 12 (API 1.4.0): the reproducibility identity. `revision` is
    // null against an older server.
    engine,
    revision: d.revision ?? null,
    accuracyLevel: d.accuracy_level ?? null,
    timescaleModel: d.timescale_model ?? null,
    deltaTSeconds: d.delta_t_seconds ?? null,
  };
}

/** `GET /v1/version` — every version axis of the server (Sprint 12). */
export function parseVersionInfo(d) {
  const comp = d.computation || {};
  const vecs = d.conformance_vectors || {};
  return {
    waqtCoreVersion: d.waqt_core_version ?? null,
    apiVersion: d.api_version ?? null,
    spec: d.spec ?? null,
    engine: comp.engine ?? null,
    revision: comp.revision ?? null,
    accuracyLevel: comp.accuracy_level ?? null,
    vectorSetVersion: vecs.vector_set_version ?? null,
    engineRevisionHistory: d.engine_revision_history || {},
    raw: d,
  };
}

export function parseHijriDate(d) {
  if (d == null) return null;
  const provider = d.provider || {};
  return {
    date: d.date,
    display: d.display,
    year: d.year,
    month: d.month,
    monthName: d.month_name,
    day: d.day,
    providerName: provider.name ?? null,
    providerVersion: provider.version ?? null,
    sourceNote: d.source_note ?? null,
  };
}

/** One Gregorian civil rendering of an instant -- UTC (`timezoneName ===
 * null`) or a place's local civil time. Mirrors
 * `waqt.calendar_interop.GregorianRepresentation`. */
export function parseGregorianRepresentation(d) {
  if (d == null) return null;
  return {
    date: d.date,
    timeOfDay: d.time_of_day,
    weekdayIso: d.weekday_iso,
    weekdayNameIslamic: d.weekday_name_islamic,
    isLeapYear: d.is_leap_year,
    timezoneName: d.timezone_name ?? null,
    utcOffsetSeconds: d.utc_offset_seconds ?? null,
  };
}

/** One of the six solar/prayer events, from `events[]` (has `reading`)
 * or `next_event` (has `countdown` instead). */
export function parseAstronomicalEvent(d) {
  if (d == null) return null;
  return {
    name: d.name,
    instant: parseInstant(d.instant),
    reading: parseReading(d.reading),
    countdown: parseReading(d.countdown),
  };
}

export function parseWaqtPosition(d) {
  if (d == null) return null;
  return { display: d.display, reading: parseReading(d.reading) };
}

export function parseDayBoundary(d) {
  if (d == null) return null;
  return {
    maghribOpen: parseInstant(d.maghrib_open),
    maghribClose: parseInstant(d.maghrib_close),
    lengthSiSeconds: d.length_si_seconds ?? null,
    note: d.note ?? null,
  };
}

/**
 * The full `/v1/waqt` result (day boundary, Waqt clock, all six events,
 * Hijri date, timezone, computation). `/v1/day` and `/v1/events` return
 * subsets of this same shape -- this parser tolerates missing keys, so
 * one function models all three.
 */
export function parseWaqtResponse(d) {
  return {
    status: d.status,
    instant: parseInstant(d.instant),
    location: parseLocation(d.location),
    timezone: parseTimezoneInfo(d.timezone),
    undefinedReason: d.undefined_reason ?? null,
    day: parseDayBoundary(d.day),
    hijri: parseHijriDate(d.hijri),
    weekday: d.weekday ?? null,
    waqt: parseWaqtPosition(d.waqt),
    events: (d.events || []).map(parseAstronomicalEvent),
    nextEvent: parseAstronomicalEvent(d.next_event),
    profile: parseAstronomyProfile(d.profile),
    computation: parseComputationInfo(d.computation),
    raw: d,
  };
}

/** Convenience accessor: `findEvent(resp, "maghrib")` instead of
 * scanning `resp.events` by hand -- mirrors `WaqtResponse.event()` on
 * the Python side. */
export function findEvent(waqtResponse, name) {
  return (waqtResponse.events || []).find((e) => e.name === name) || null;
}

/** `/v1/calendar/convert?direction=instant-to-calendars` -- one instant
 * as UTC-Gregorian always, plus local-civil-Gregorian and a Waqt
 * day/position if a location was supplied. */
export function parseInstantRepresentation(d) {
  const greg = d.gregorian || {};
  const waqtBlock = d.waqt || {};
  return {
    direction: d.direction,
    instant: parseInstant((d.source || {}).instant),
    location: parseLocation(d.location),
    gregorianUtc: parseGregorianRepresentation(greg.utc),
    gregorianCivil: parseGregorianRepresentation(greg.civil),
    waqtStatus: waqtBlock.status ?? null,
    waqtUndefinedReason: waqtBlock.undefined_reason ?? null,
    waqtDay: parseDayBoundary(waqtBlock.day),
    profile: parseAstronomyProfile(d.profile),
    computation: parseComputationInfo(d.computation),
    caveat: d.caveat ?? null,
    raw: d,
  };
}

/** `/v1/schedule/{snapshot,span}` and `POST /v1/schedule/resolve`.
 * These endpoints' shapes vary by which one was called
 * (docs/SCHEDULING.md); `.raw` is the full response and `location` is
 * the one field every variant shares. */
export function parseSchedulingResult(d) {
  return { location: parseLocation(d.location), raw: d };
}

/** `/v1/institutional/*`. Same reasoning as `parseSchedulingResult`. */
export function parseInstitutionalResult(d) {
  const provider = d.calendar_provider || {};
  return { calendarProviderName: provider.name ?? null, raw: d };
}

export function parseCalendarProviderInfo(d) {
  return {
    name: d.name,
    description: d.description,
    requiresOverride: d.requires_override,
    supportsReverseConversion: d.supports_reverse_conversion,
  };
}

export function parseConversionResult(d) {
  return { direction: d.direction, input: d.input || {}, output: d.output || {}, raw: d };
}

export function parseBoundaryCrossingResult(d) {
  return {
    status: d.status,
    crossesCivilMidnight: d.crosses_civil_midnight ?? null,
    crossesMaghrib: d.crosses_maghrib ?? null,
    startCivilDate: d.start_civil_date ?? null,
    endCivilDate: d.end_civil_date ?? null,
    undefinedReason: d.undefined_reason ?? null,
    raw: d,
  };
}

export function parseLocationInfo(d) {
  return {
    location: parseLocation(d.location),
    instant: parseInstant(d.instant),
    timezone: parseTimezoneInfo(d.timezone),
    localCivilDate: d.local_civil_date,
    raw: d,
  };
}
