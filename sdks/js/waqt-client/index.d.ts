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
  astronomyEngine: string | null; accuracyLevel: string | null;
  timescaleModel: string | null; deltaTSeconds: number | null;
}
export interface HijriDate {
  date: string; display: string; year: number; month: number; monthName: string; day: number;
  providerName: string | null; providerVersion: string | null; sourceNote: string | null;
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
  convert(direction: "to-hijri" | "to-gregorian", opts?: Record<string, unknown>): Promise<ConversionResult>;
  representInstant(opts?: Record<string, unknown>): Promise<InstantRepresentation>;
  waqtDayForGregorianDate(date: string, lat: number, lon: number, opts?: Record<string, unknown>): Promise<InstantRepresentation>;
  boundaryCrossing(start: string, end: string, lat: number, lon: number, opts?: Record<string, unknown>): Promise<BoundaryCrossingResult>;

  scheduleSnapshot(lat: number, lon: number, opts?: Record<string, unknown>): Promise<SchedulingResult>;
  scheduleSpan(lat: number, lon: number, start: string, end: string, opts?: Record<string, unknown>): Promise<SchedulingResult>;
  scheduleResolve(body: Record<string, unknown>): Promise<SchedulingResult>;

  institutionalWeek(lat: number, lon: number, opts?: Record<string, unknown>): Promise<InstitutionalResult>;
  institutionalFiscalYear(opts?: Record<string, unknown>): Promise<InstitutionalResult>;
  institutionalAcademicYear(opts?: Record<string, unknown>): Promise<InstitutionalResult>;
  institutionalDefaultProfile(opts?: Record<string, unknown>): Promise<InstitutionalResult>;
  institutionalFiscalYearResolve(body: Record<string, unknown>): Promise<InstitutionalResult>;
  institutionalAcademicYearResolve(body: Record<string, unknown>): Promise<InstitutionalResult>;

  health(): Promise<Record<string, unknown>>;
}

export declare function makeConfig(overrides?: Partial<WaqtClientConfig>): Required<WaqtClientConfig>;
export declare const VERSION: string;
