// Type declarations for waqt-client. Hand-written against src/*.mjs's
// JSDoc, so TypeScript consumers get full typing without a build step --
// the package ships as plain, directly-runnable ESM (see README.md
// "Why plain JS, not a compiled TS build").

export type VersionMismatchPolicy = "ignore" | "warn" | "raise";

export interface WaqtClientConfig {
  baseUrl?: string;
  timeoutMs?: number;
  defaultCalendarProvider?: string;
  defaultFajrAngleDeg?: number;
  defaultIshaAngleDeg?: number;
  defaultAsrShadowRatio?: number;
  defaultTimezoneOverride?: string;
  onVersionMismatch?: VersionMismatchPolicy;
  extraHeaders?: Record<string, string>;
  userAgent?: string;
}

export interface Location { lat: number; lon: number; elevationM: number | null }
export interface TimezoneInfo { name: string; utcOffsetSeconds: number | null }
export interface Reading { display: string; seconds: number }
export interface AstronomyProfile {
  name: string; fajrAngleDeg: number; ishaAngleDeg: number; asrShadowRatio: number;
}
export interface ComputationInfo {
  /** Pre-1.4.0 name of `engine`; same value, kept for compatibility. */
  astronomyEngine: string | null;
  /** Sprint 12 (API 1.4.0): `(engine, revision, accuracyLevel)` is the reproducibility identity. */
  engine: string | null; revision: string | null;
  accuracyLevel: string | null;
  timescaleModel: string | null; deltaTSeconds: number | null;
}
export interface VersionInfo {
  waqtCoreVersion: string | null; apiVersion: string | null; spec: string | null;
  engine: string | null; revision: string | null; accuracyLevel: string | null;
  vectorSetVersion: string | null;
  engineRevisionHistory: Record<string, Record<string, unknown>>;
  raw: Record<string, unknown>;
}
export interface HijriDate {
  date: string; display: string; year: number; month: number; monthName: string; day: number;
  providerName: string | null; providerVersion: string | null; sourceNote: string | null;
  /** API 1.5.0: "local" | "declared" | "observation" | "remote" | "remote-stale" | "local-fallback"; null on older servers. */
  source: string | null;
  /** API 1.5.0: fallback reason, cache state, cross-check -- as returned. null for purely local providers. */
  provenance: Record<string, unknown> | null;
  isFallback: boolean;
}
export interface GregorianRepresentation {
  date: string; timeOfDay: string; weekdayIso: number; weekdayNameIslamic: string;
  isLeapYear: boolean; timezoneName: string | null; utcOffsetSeconds: number | null;
}
export interface AstronomicalEvent {
  name: string; instant: Date | null; reading: Reading | null; countdown: Reading | null;
}
export interface WaqtPosition { display: string; reading: Reading | null }
export interface DayBoundary {
  maghribOpen: Date | null; maghribClose: Date | null;
  lengthSiSeconds: number | null; note: string | null;
}
export interface WaqtResponse {
  status: string; instant: Date | null; location: Location | null; timezone: TimezoneInfo | null;
  undefinedReason: string | null; day: DayBoundary | null; hijri: HijriDate | null;
  weekday: string | null; waqt: WaqtPosition | null; events: AstronomicalEvent[];
  /** API 1.5.0: set (with hijri null) when the calendar provider failed; the astronomy is still valid. */
  calendarError: { provider: string; message: string } | null;
  nextEvent: AstronomicalEvent | null; profile: AstronomyProfile | null;
  computation: ComputationInfo | null; raw: Record<string, unknown>;
}
export interface InstantRepresentation {
  direction: string; instant: Date | null; location: Location | null;
  gregorianUtc: GregorianRepresentation | null; gregorianCivil: GregorianRepresentation | null;
  waqtStatus: string | null; waqtUndefinedReason: string | null; waqtDay: DayBoundary | null;
  profile: AstronomyProfile | null; computation: ComputationInfo | null; caveat: string | null;
  raw: Record<string, unknown>;
}
export interface SchedulingResult { location: Location | null; raw: Record<string, unknown> }
export interface InstitutionalResult { calendarProviderName: string | null; raw: Record<string, unknown> }
export interface CalendarProviderInfo {
  name: string; description: string; requiresOverride: boolean; supportsReverseConversion: boolean;
}
export interface ConversionResult {
  direction: string; input: Record<string, unknown>; output: Record<string, unknown>;
  raw: Record<string, unknown>;
}
export interface BoundaryCrossingResult {
  status: string; crossesCivilMidnight: boolean | null; crossesMaghrib: boolean | null;
  startCivilDate: string | null; endCivilDate: string | null; undefinedReason: string | null;
  raw: Record<string, unknown>;
}
export interface LocationInfo {
  location: Location | null; instant: Date | null; timezone: TimezoneInfo | null;
  localCivilDate: string; raw: Record<string, unknown>;
}

export declare class WaqtError extends Error {}
export declare class WaqtApiError extends WaqtError {
  statusCode: number; code: string; message: string; details: Record<string, unknown>;
}
export declare class WaqtTransportError extends WaqtError { cause?: unknown }
export declare class WaqtVersionMismatch extends WaqtError { serverVersion: string; supported: string }

export declare class WaqtClient {
  config: Required<WaqtClientConfig>;
  constructor(config?: WaqtClientConfig);
  request(method: string, path: string, opts?: { params?: Record<string, unknown>; json?: unknown }): Promise<Record<string, unknown>>;

  getWaqt(lat: number, lon: number, opts?: Record<string, unknown>): Promise<WaqtResponse>;
  getDay(lat: number, lon: number, opts?: Record<string, unknown>): Promise<WaqtResponse>;
  getEvents(lat: number, lon: number, opts?: Record<string, unknown>): Promise<WaqtResponse>;
  getLocation(lat: number, lon: number, opts?: Record<string, unknown>): Promise<LocationInfo>;

  getHijri(opts?: Record<string, unknown>): Promise<WaqtResponse>;
  listCalendarProviders(): Promise<CalendarProviderInfo[]>;
  getVersion(): Promise<VersionInfo>;
  convert(direction: "to-hijri" | "to-gregorian", opts?: Record<string, unknown>): Promise<ConversionResult>;
  representInstant(opts?: Record<string, unknown>): Promise<InstantRepresentation>;
  waqtDayForGregorianDate(date: string, lat: number, lon: number, opts?: Record<string, unknown>): Promise<InstantRepresentation>;
  boundaryCrossing(start: string, end: string, lat: number, lon: number, opts?: Record<string, unknown>): Promise<BoundaryCrossingResult>;

  scheduleSnapshot(lat: number, lon: number, opts?: Record<string, unknown>): Promise<SchedulingResult>;
  scheduleSpan(lat: number, lon: number, start: string, end: string, opts?: Record<string, unknown>): Promise<SchedulingResult>;
  /** Accepts a plain JSON body (Sprint 9 wire format, unchanged) or any
   * typed request from `./requests_types` (Sprint 10). */
  scheduleResolve(body: JsonRequestBody): Promise<SchedulingResult>;

  institutionalWeek(lat: number, lon: number, opts?: Record<string, unknown>): Promise<InstitutionalResult>;
  institutionalFiscalYear(opts?: Record<string, unknown>): Promise<InstitutionalResult>;
  institutionalAcademicYear(opts?: Record<string, unknown>): Promise<InstitutionalResult>;
  institutionalDefaultProfile(opts?: Record<string, unknown>): Promise<InstitutionalResult>;
  institutionalFiscalYearResolve(body: JsonRequestBody): Promise<InstitutionalResult>;
  institutionalAcademicYearResolve(body: JsonRequestBody): Promise<InstitutionalResult>;

  health(): Promise<Record<string, unknown>>;
}

/** A plain JSON-shaped object, or anything exposing `toJSON()` -- what
 * every builder in `./requests_types` returns. */
export type JsonRequestBody = Record<string, unknown> | { toJSON(): Record<string, unknown> };

export declare function makeConfig(overrides?: Partial<WaqtClientConfig>): Required<WaqtClientConfig>;
export declare const VERSION: string;

// ---------------------------------------------------------------------------
// Sprint 10: typed request builders (./requests_types.mjs)
// ---------------------------------------------------------------------------

export declare namespace requests {
  class RequestValidationError extends Error {}

  interface JsonNode { toJSON(): Record<string, unknown>; }

  function instant(value: string | Date): JsonNode;
  function anchor(): JsonNode;
  function event(name: string, day?: number): JsonNode;
  function nextEvent(name: string, opts?: { inclusive?: boolean; onUndefined?: string }): JsonNode;
  function prevEvent(name: string, opts?: { inclusive?: boolean; onUndefined?: string }): JsonNode;
  function position(seconds: number, day?: number): JsonNode;
  function offset(base: JsonNode, seconds: number): JsonNode;
  function fraction(start: JsonNode, end: JsonNode, fraction: number): JsonNode;
  function interval(start?: JsonNode | null, end?: JsonNode | null, opts?: { startInclusive?: boolean; endInclusive?: boolean }): JsonNode;
  function before(point: JsonNode, inclusive?: boolean): JsonNode;
  function after(point: JsonNode, inclusive?: boolean): JsonNode;
  function between(a: JsonNode, b: JsonNode): JsonNode;
  function within(point: JsonNode, seconds: number): JsonNode;
  function withinDay(day?: number): JsonNode;

  function resolvePoint(point: JsonNode): JsonNode;
  function resolveInterval(interval: JsonNode): JsonNode;
  function evaluate(interval: JsonNode, at: string | Date): JsonNode;
  function checkDeadline(point: JsonNode, now?: string | Date | null): JsonNode;
  function until(name: string, opts?: { onUndefined?: string; instant?: string | Date | null }): JsonNode;
  function since(name: string, opts?: { onUndefined?: string; instant?: string | Date | null }): JsonNode;
  function nextEventOp(opts?: { instant?: string | Date | null }): JsonNode;
  function eventPosition(name: string, day?: number | null): JsonNode;
  function dayBounds(opts?: { instant?: string | Date | null }): JsonNode;
  function classifySpan(start: string | Date, end: string | Date, endInclusive?: boolean): JsonNode;

  function profile(opts?: { fajrAngleDeg?: number; ishaAngleDeg?: number; asrShadowRatio?: number }): JsonNode;
  function scheduleResolveRequest(opts: {
    lat: number; lon: number; operation: JsonNode; elevationM?: number;
    anchor?: string | Date | null; profile?: JsonNode | null; calendarProvider?: string | null;
    timezoneOverride?: string | null; precision?: "second" | "microsecond" | null;
  }): JsonNode;

  function monthDay(month: number, day?: number): JsonNode;
  function monthEnd(month: number): JsonNode;
  function nthWeekdayOfMonth(weekday: string, n: number, month: number): JsonNode;
  function location(lat: number, lon: number, elevationM?: number): JsonNode;
  function fiscalYearResolveRequest(opts: {
    hijriYear: number; startRule: JsonNode; endRule: JsonNode; label?: string | null;
    calendarProvider?: string | null; location?: JsonNode | null;
  }): JsonNode;
  function termRule(label: string, startRule: JsonNode, endRule: JsonNode, yearOffset?: number): JsonNode;
  function holidayRule(label: string, rule: JsonNode, yearOffset?: number): JsonNode;
  function academicYearResolveRequest(opts: {
    hijriYear: number; openingRule: JsonNode; closingRule: JsonNode; termRules?: JsonNode[]; holidays?: JsonNode[];
    label?: string | null; calendarProvider?: string | null; location?: JsonNode | null;
  }): JsonNode;
}
