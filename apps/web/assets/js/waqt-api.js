/* Waqt Web — API client and presentation model.
 *
 * Same rule as the Sprint 12 viewer: this site CONSUMES Waqt, it does not reimplement it. Nothing in this file
 * (or any other file under assets/js) knows how to compute Maghrib, a Fajr angle, a Hijri date or a Waqt reading.
 * The only arithmetic is presentational: (a) interpolating a server reading by elapsed wall-clock time between
 * polls (identical to the viewer's tick), and (b) dividing server-supplied seconds by the server-supplied day
 * length to place a marker on a ring. Tests: tests/test_no_second_implementation.py, tests/js/*.test.mjs.
 */
(function (root) {
  "use strict";
  const W = (root.Waqt = root.Waqt || {});
  const CFG = root.WAQT_CONFIG && root.WAQT_CONFIG.api ? root.WAQT_CONFIG.api : {};

  /* ------------------------------------------------------------ API client */
  class WaqtApiError extends Error {
    constructor(kind, message, extra) {
      super(message);
      this.name = "WaqtApiError";
      this.kind = kind;                       // "network" | "timeout" | "http" | "envelope" | "api"
      Object.assign(this, extra || {});       // code, status, retryAfter
    }
  }

  function defaultApiBase(loc) {
    const l = loc || (root.location || { hostname: "", search: "" });
    const override = new URLSearchParams(l.search || "").get("api");
    if (override) return override;
    return ["localhost", "127.0.0.1", "[::1]"].includes(l.hostname) ? CFG.localBase : CFG.publicBase;
  }

  function apiBase(loc) {
    let saved = null;
    try { saved = root.localStorage && root.localStorage.getItem(CFG.storageKey); } catch (e) { /* storage may be blocked */ }
    return String(saved || defaultApiBase(loc)).replace(/\/+$/, "");
  }

  async function getJSON(path, params, opts) {
    const o = opts || {};
    const base = (o.base || apiBase()).replace(/\/+$/, "");
    const url = new URL(base + path);
    Object.entries(params || {}).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, v);
    });
    const fetchImpl = o.fetchImpl || root.fetch.bind(root);
    const ctl = typeof AbortController !== "undefined" ? new AbortController() : null;
    const timeoutMs = o.timeoutMs || CFG.requestTimeoutMs || 25000;
    const timer = ctl ? setTimeout(() => ctl.abort(), timeoutMs) : null;
    let res;
    try {
      res = await fetchImpl(url.toString(), ctl ? { signal: ctl.signal } : undefined);
    } catch (e) {
      const aborted = e && e.name === "AbortError";
      throw new WaqtApiError(aborted ? "timeout" : "network",
        aborted ? `No answer from ${base} within ${Math.round(timeoutMs / 1000)} s.`
                : `Could not reach ${base}. Is the server running, and does it allow this origin (WAQT_CORS_ORIGINS)?`);
    } finally { if (timer) clearTimeout(timer); }
    // docs/API.md §2: the envelope is always {meta, data, error}, exactly one of data/error non-null.
    const body = await res.json().catch(() => null);
    if (!body || (body.error === undefined && body.data === undefined)) {
      throw new WaqtApiError("envelope", `HTTP ${res.status}: response did not match the documented envelope.`, { status: res.status });
    }
    if (body.error !== null && body.error !== undefined) {
      const ra = body.error.details && body.error.details.retry_after_seconds;
      throw new WaqtApiError("api", `${body.error.code}: ${body.error.message}`,
        { code: body.error.code, status: res.status, retryAfter: ra || null });
    }
    return body.data;
  }

  /* ---------------------------------------------------- presentation model */
  const LABELS = { fajr: "Fajr", sunrise: "Sunrise", dhuhr: "Dhuhr", asr: "Asr", maghrib: "Maghrib", isha: "Isha" };
  const labelOf = (name) => LABELS[name] || String(name);

  function fmtHMS(totalSeconds) {
    const s = Math.max(0, Math.floor(totalSeconds));
    const pad = (n) => String(n).padStart(2, "0");
    return `${pad(Math.floor(s / 3600))}:${pad(Math.floor((s % 3600) / 60))}:${pad(s % 60)}`;
  }

  function localClock(iso, tzName) {
    if (!iso) return "—";
    try {
      return new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
        timeZone: tzName || undefined }).format(new Date(iso));
    } catch (e) { return new Date(iso).toISOString().slice(11, 19) + " UTC"; }
  }

  /* Turn one /v1/waqt `data` object into what the components draw. Every field is read, never computed.
     Returns {state:"empty", reason} when the API says Waqt is undefined here, so callers show that plainly. */
  function fromWaqtData(data) {
    if (!data) return { state: "empty", reason: "The API returned no data." };
    if (data.status !== "OK") return { state: "empty", reason: data.undefined_reason || "Waqt is undefined for this place and instant." };
    const day = data.day || {};
    const length = day.length_si_seconds;
    const tz = data.timezone ? data.timezone.name : null;
    const reps = {};
    (data.event_representations || []).forEach((r) => { reps[r.name] = r; });
    const events = (data.events || []).map((e) => {
      const base = { name: e.name, label: labelOf(e.name), defined: !!(e.instant && e.reading) };
      if (!base.defined) return base;
      const seconds = e.reading.seconds;
      // Where the event sits relative to THIS Waqt day, by the server's own numbers/strings:
      //   - the event whose instant equals day.maghrib_close IS the next Maghrib (the day's closing boundary);
      //   - an event whose reading exceeds the day length belongs to the evening after that boundary (the API
      //     reports e.g. Isha as "25:05:06"); we mark it, we never fold it silently into this day.
      const position = e.instant === day.maghrib_close ? "close" : seconds > length ? "after-close" : "in-day";
      const plot = position === "close" ? 1 : position === "after-close" ? (seconds - length) / length : seconds / length;
      const rep = reps[e.name];
      return Object.assign(base, {
        instantIso: e.instant, instantMs: Date.parse(e.instant), seconds, display: e.reading.display,
        position, plot, local: rep && rep.gregorian ? rep.gregorian.local_time : localClock(e.instant, tz)
      });
    });
    const ne = data.next_event;
    return {
      state: "ok",
      instantIso: data.instant, instantMs: Date.parse(data.instant),
      location: data.location || null, timezone: data.timezone || null, tzName: tz,
      day: { openIso: day.maghrib_open, closeIso: day.maghrib_close, openMs: Date.parse(day.maghrib_open),
             closeMs: Date.parse(day.maghrib_close), lengthSeconds: length, note: day.note || null },
      reading: { seconds: data.waqt.reading.seconds, display: data.waqt.reading.display },
      hijri: data.hijri ? { display: data.hijri.display, date: data.hijri.date, source: data.hijri.source,
                            provider: data.hijri.provider ? data.hijri.provider.name : null } : null,
      calendarError: data.calendar_error || null,
      weekday: data.weekday || null,
      events,
      next: ne && ne.instant ? { name: ne.name, label: labelOf(ne.name), instantIso: ne.instant, instantMs: Date.parse(ne.instant),
        countdownSeconds: ne.countdown.seconds } : null,
      computation: data.computation || null
    };
  }

  /* anchor = what the server said at fetch time. Everything live is anchor + elapsed wall-clock seconds. */
  function makeAnchor(model, fetchedAtMs) {
    return { fetchedAtMs, readingSeconds: model.reading.seconds, lengthSeconds: model.day.lengthSeconds,
             countdownSeconds: model.next ? model.next.countdownSeconds : null };
  }

  function snapshotAt(anchor, nowMs) {
    const elapsed = Math.max(0, (nowMs - anchor.fetchedAtMs) / 1000);
    const reading = anchor.readingSeconds + elapsed;
    const count = anchor.countdownSeconds == null ? null : anchor.countdownSeconds - elapsed;
    return {
      readingSeconds: reading, readingDisplay: fmtHMS(reading),
      dayFraction: Math.max(0, Math.min(1, reading / anchor.lengthSeconds)),
      countdownSeconds: count == null ? null : Math.max(0, count),
      countdownDisplay: count == null ? null : fmtHMS(count),
      // The page's data is stale once the server-reported day has run out or the next event has arrived.
      // It must RE-ASK the server; it never works out "what comes next" itself.
      expired: reading >= anchor.lengthSeconds || (count != null && count <= 0)
    };
  }

  /* Used by the Experience Lab's accelerated playback only: the next event after a virtual instant, chosen from the
     events the server already returned. */
  function nextEventAfter(model, virtualMs) {
    const later = model.events.filter((e) => e.defined && e.instantMs > virtualMs).sort((a, b) => a.instantMs - b.instantMs);
    return later[0] || null;
  }


  /* Example request text for docs/lab (documentation only; the page runs the request through getJSON, not through this text). */
  function exampleSnippet(lang, base, lat, lon) {
    const url = `${base}/v1/waqt?lat=${lat}&lon=${lon}`;
    if (lang === "js") return `const res = await fetch("${url}");\nconst { data, error } = await res.json();\nif (error) throw new Error(error.code + ": " + error.message);\nif (data.status !== "OK") console.log("Waqt undefined here:", data.undefined_reason);\nelse console.log(data.waqt.reading.display, data.next_event);`;
    if (lang === "py") return `import json, urllib.request\n\nwith urllib.request.urlopen("${url}") as r:\n    body = json.load(r)\nif body["error"]:\n    raise RuntimeError(body["error"]["message"])\ndata = body["data"]\nprint(data["waqt"]["reading"]["display"], data["next_event"])`;
    return `curl "${url}"`;
  }

  Object.assign(W, { exampleSnippet, WaqtApiError, defaultApiBase, apiBase, getJSON, LABELS, labelOf, fmtHMS, localClock,
                     fromWaqtData, makeAnchor, snapshotAt, nextEventAfter });
})(typeof window !== "undefined" ? window : globalThis);
