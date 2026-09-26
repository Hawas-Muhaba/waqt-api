// waqt-client/requests — pure query-parameter builders, one per endpoint.
// Mirrors sdks/python/waqt_client/_requests.py's parameter names exactly
// against waqt/api/*_endpoint.py's FastAPI Query(...) names.

function fmtInstant(v) {
  if (v == null) return undefined;
  return v instanceof Date ? v.toISOString() : v;
}

function fmtDate(v) {
  if (v == null) return undefined;
  if (v instanceof Date) return v.toISOString().slice(0, 10);
  return v;
}

function dropUndefined(obj) {
  const out = {};
  for (const [k, v] of Object.entries(obj)) {
    if (v !== undefined && v !== null) out[k] = v;
  }
  return out;
}

export function waqtParams(lat, lon, opts = {}) {
  return dropUndefined({
    lat, lon, elevation_m: opts.elevationM ?? 0.0,
    instant: fmtInstant(opts.instant), timezone_override: opts.timezoneOverride,
    fajr_angle: opts.fajrAngle, isha_angle: opts.ishaAngle, asr_ratio: opts.asrRatio,
    calendar_provider: opts.calendarProvider, override_date: fmtDate(opts.overrideDate),
    declared_year: opts.declaredYear, declared_month: opts.declaredMonth, declared_day: opts.declaredDay,
    sighting_year: opts.sightingYear, sighting_month: opts.sightingMonth, sighting_day: opts.sightingDay,
    observed_at: opts.observedAt,
  });
}

export function dayParams(lat, lon, opts = {}) {
  return dropUndefined({
    lat, lon, elevation_m: opts.elevationM ?? 0.0,
    instant: fmtInstant(opts.instant), timezone_override: opts.timezoneOverride,
  });
}

export function eventsParams(lat, lon, opts = {}) {
  return dropUndefined({
    lat, lon, elevation_m: opts.elevationM ?? 0.0,
    instant: fmtInstant(opts.instant), timezone_override: opts.timezoneOverride,
    fajr_angle: opts.fajrAngle, isha_angle: opts.ishaAngle, asr_ratio: opts.asrRatio,
  });
}

export function hijriParams(opts = {}) {
  return dropUndefined({
    date: fmtDate(opts.date), calendar_provider: opts.calendarProvider,
    override_date: fmtDate(opts.overrideDate),
    declared_year: opts.declaredYear, declared_month: opts.declaredMonth, declared_day: opts.declaredDay,
    sighting_year: opts.sightingYear, sighting_month: opts.sightingMonth, sighting_day: opts.sightingDay,
    observed_at: opts.observedAt,
  });
}

export function locationParams(lat, lon, opts = {}) {
  return dropUndefined({
    lat, lon, instant: fmtInstant(opts.instant), timezone_override: opts.timezoneOverride,
  });
}

export function conversionsParams(direction, opts = {}) {
  return dropUndefined({
    direction, calendar_provider: opts.calendarProvider,
    date: fmtDate(opts.date), year: opts.year, month: opts.month, day: opts.day,
  });
}

export function calendarConvertParams(opts = {}) {
  return dropUndefined({
    direction: opts.direction || "instant-to-calendars",
    instant: fmtInstant(opts.instant), date: fmtDate(opts.date),
    lat: opts.lat, lon: opts.lon, elevation_m: opts.elevationM ?? 0.0,
    timezone_override: opts.timezoneOverride,
    fajr_angle: opts.fajrAngle, isha_angle: opts.ishaAngle, asr_ratio: opts.asrRatio,
    calendar_provider: opts.calendarProvider, override_date: fmtDate(opts.overrideDate),
    declared_year: opts.declaredYear, declared_month: opts.declaredMonth, declared_day: opts.declaredDay,
    sighting_year: opts.sightingYear, sighting_month: opts.sightingMonth, sighting_day: opts.sightingDay,
    observed_at: opts.observedAt,
  });
}

export function boundaryCrossingParams(start, end, lat, lon, opts = {}) {
  return dropUndefined({
    start: fmtInstant(start), end: fmtInstant(end), lat, lon,
    elevation_m: opts.elevationM ?? 0.0, timezone_override: opts.timezoneOverride,
  });
}

export function snapshotParams(lat, lon, opts = {}) {
  return dropUndefined({
    lat, lon, elevation_m: opts.elevationM ?? 0.0, instant: fmtInstant(opts.instant),
    timezone_override: opts.timezoneOverride, fajr_angle: opts.fajrAngle,
    isha_angle: opts.ishaAngle, asr_ratio: opts.asrRatio,
    calendar_provider: opts.calendarProvider, precision: opts.precision,
  });
}

export function spanParams(lat, lon, start, end, opts = {}) {
  return dropUndefined({
    lat, lon, start: fmtInstant(start), end: fmtInstant(end),
    end_inclusive: opts.endInclusive, elevation_m: opts.elevationM ?? 0.0,
    timezone_override: opts.timezoneOverride, calendar_provider: opts.calendarProvider,
    precision: opts.precision,
  });
}

export function institutionalWeekParams(lat, lon, opts = {}) {
  return dropUndefined({
    lat, lon, elevation_m: opts.elevationM ?? 0.0, instant: fmtInstant(opts.instant),
    first_day: opts.firstDay, jumuah_day: opts.jumuahDay, calendar_provider: opts.calendarProvider,
  });
}

export function institutionalProfileParams(opts = {}) {
  return dropUndefined({ calendar_provider: opts.calendarProvider });
}
