import test from "node:test";
import assert from "node:assert/strict";
import { loadPage, demo, okEnvelope, errEnvelope, tick, read } from "./helpers.mjs";

/* ------------------------------------------------------------------ model: Waqt semantics are read, not assumed */
test("model: day boundaries, reading and events come straight from the response", () => {
  const w = loadPage().window, d = demo().data, m = w.Waqt.fromWaqtData(d);
  assert.equal(m.state, "ok");
  assert.equal(m.day.openIso, d.day.maghrib_open);
  assert.equal(m.day.lengthSeconds, d.day.length_si_seconds);
  assert.notEqual(m.day.lengthSeconds, 86400, "day length must not be assumed to be 24 h");
  assert.equal(m.reading.display, d.waqt.reading.display);
  assert.equal(m.events.length, 6);
  assert.equal(m.next.name, d.next_event.name);
});

test("model: the closing Maghrib and an after-close Isha are marked, never silently folded into the day", () => {
  const w = loadPage().window, m = w.Waqt.fromWaqtData(demo().data);
  const by = Object.fromEntries(m.events.map((e) => [e.name, e]));
  assert.equal(by.maghrib.position, "close");
  assert.equal(by.maghrib.plot, 1);
  assert.equal(by.isha.position, "after-close");           // API reports Isha as 25:05:06 > day length
  assert.ok(by.isha.seconds > m.day.lengthSeconds);
  assert.ok(by.isha.plot > 0 && by.isha.plot < 0.2);
  for (const n of ["fajr", "sunrise", "dhuhr", "asr"]) { assert.equal(by[n].position, "in-day"); assert.ok(by[n].plot > 0 && by[n].plot < 1); }
  assert.ok(by.fajr.plot < by.sunrise.plot && by.sunrise.plot < by.dhuhr.plot && by.dhuhr.plot < by.asr.plot);
});

test("model: an UNDEFINED response becomes an explicit empty state with the server's reason", () => {
  const w = loadPage().window;
  const m = w.Waqt.fromWaqtData({ status: "UNDEFINED", undefined_reason: "sun does not set" });
  assert.equal(m.state, "empty"); assert.equal(m.reason, "sun does not set");
  assert.equal(w.Waqt.fromWaqtData(null).state, "empty");
});

test("model: an event that does not occur is kept as undefined, not invented", () => {
  const w = loadPage().window, d = demo().data;
  d.events[0] = { name: "fajr", instant: null, reading: null };
  const m = w.Waqt.fromWaqtData(d);
  assert.equal(m.events[0].defined, false);
});

/* ------------------------------------------------------------------------ countdown / ticking */
test("countdown: server value minus elapsed wall time; reading advances; expiry triggers a re-ask", () => {
  const w = loadPage().window, W = w.Waqt, m = W.fromWaqtData(demo().data);
  const a = W.makeAnchor(m, 1_000_000);
  let s = W.snapshotAt(a, 1_000_000 + 10_000);
  assert.ok(Math.abs(s.readingSeconds - (m.reading.seconds + 10)) < 1e-6);
  assert.ok(Math.abs(s.countdownSeconds - (m.next.countdownSeconds - 10)) < 1e-6);
  assert.equal(s.expired, false);
  s = W.snapshotAt(a, 1_000_000 + (m.next.countdownSeconds + 1) * 1000);
  assert.equal(s.countdownSeconds, 0); assert.equal(s.expired, true);
  s = W.snapshotAt(a, 1_000_000 + (m.day.lengthSeconds - m.reading.seconds + 1) * 1000);
  assert.equal(s.expired, true);
  assert.equal(W.fmtHMS(3661), "01:01:01"); assert.equal(W.fmtHMS(-5), "00:00:00");
});

test("playback helper: next event after a virtual instant is chosen from the API's own events", () => {
  const w = loadPage().window, W = w.Waqt, m = W.fromWaqtData(demo().data);
  assert.equal(W.nextEventAfter(m, m.day.openMs).name, "fajr");
  const afterAsr = m.events.find((e) => e.name === "asr").instantMs + 1;
  assert.equal(W.nextEventAfter(m, afterAsr).name, "maghrib");
  assert.equal(W.nextEventAfter(m, m.events.find((e) => e.name === "isha").instantMs + 1), null);
});

/* ------------------------------------------------------------------- API loading/error states */
function liveWith(w, fetchImpl, extra = {}) {
  return w.Waqt.createLive(Object.assign({ fetchImpl, base: "https://api.test", autoRetry: false, tickMs: 3_600_000 }, extra));
}

test("states: loading -> success with real data, not marked demo", async () => {
  const w = loadPage().window, seen = [];
  const store = liveWith(w, async () => okEnvelope(demo().data));
  store.subscribe(() => seen.push(store.state));
  store.start(); assert.equal(store.state, "loading");
  await tick(20);
  assert.equal(store.state, "success"); assert.equal(store.isDemo, false); assert.ok(seen.includes("loading") && seen.includes("success"));
  store.stop();
});

test("states: API error -> clearly labelled demo fallback (never passes as live)", async () => {
  const w = loadPage().window;
  const store = liveWith(w, async () => { throw new TypeError("Failed to fetch"); });
  store.start(); await tick(20);
  assert.equal(store.state, "error"); assert.equal(store.isDemo, true); assert.ok(store.model);
  assert.equal(store.snapshot().readingDisplay, store.model.reading.display, "demo is frozen, it must not tick");
  store.stop();
});

test("states: HTTP error envelope surfaces the server's code and message", async () => {
  const w = loadPage().window;
  const store = liveWith(w, async () => errEnvelope("RATE_LIMITED", "slow down", 429));
  store.start(); await tick(20);
  assert.equal(store.state, "error"); assert.match(store.error.message, /RATE_LIMITED: slow down/); store.stop();
});

test("states: UNDEFINED place -> empty (no demo substitution)", async () => {
  const w = loadPage().window;
  const store = liveWith(w, async () => okEnvelope({ status: "UNDEFINED", undefined_reason: "polar day" }));
  store.start(); await tick(20);
  assert.equal(store.state, "empty"); assert.equal(store.isDemo, false); assert.equal(store.model, null); assert.equal(store.emptyReason, "polar day");
  store.stop();
});

test("states: offline browser -> offline state with demo fallback and no network call", async () => {
  const w = loadPage("index.html", { online: false }).window; let calls = 0;
  const store = liveWith(w, async () => { calls++; return okEnvelope(demo().data); });
  store.start(); await tick(20);
  assert.equal(store.state, "offline"); assert.equal(store.isDemo, true); assert.equal(calls, 0); store.stop();
});

test("states: malformed response (not the documented envelope) is an error, not a crash", async () => {
  const w = loadPage().window;
  const store = liveWith(w, async () => ({ ok: true, status: 200, json: async () => ({ hello: 1 }) }));
  store.start(); await tick(20);
  assert.equal(store.state, "error"); assert.match(store.error.message, /envelope/); store.stop();
});

test("states: when the day boundary has passed the store re-asks the server (and keeps the old view on failure)", async () => {
  const w = loadPage().window; let calls = 0, t = 1_000_000, fail = false;
  const store = w.Waqt.createLive({ base: "https://api.test", autoRetry: false, tickMs: 5, now: () => t,
    fetchImpl: async () => { calls++; if (fail) throw new TypeError("x"); return okEnvelope(demo().data); } });
  store.start(); await tick(20); assert.equal(calls, 1);
  t += 90_000_000; fail = true; await tick(40);
  assert.ok(calls >= 2, "expired day must trigger a re-request");
  assert.equal(store.state, "success", "failed boundary refresh keeps the last good answer"); store.stop();
});

/* --------------------------------------------------------------------- circular clock rendering */
function mountClock(store, opts) {
  const dom = loadPage(), w = dom.window, el = w.document.createElement("div"); w.document.body.appendChild(el);
  const clock = w.Waqt.createClock(el, Object.assign({ variant: "full", idPrefix: "t" }, opts));
  clock.update(store); return { dom, w, el, clock };
}
function fakeStore(w, { isDemo = false, state = "success" } = {}) {
  const model = w.Waqt.fromWaqtData(demo().data), anchor = w.Waqt.makeAnchor(model, 5_000);
  return { state, model, anchor, isDemo, snapshot: () => w.Waqt.snapshotAt(anchor, 5_000), error: null };
}

test("clock: renders opening Maghrib, Isha, Fajr, Sunrise, Dhuhr, Asr and next Maghrib as markers", () => {
  const w = loadPage().window, { el } = mountClock(fakeStore(w));
  const labels = [...el.querySelectorAll(".mk text")].map((t) => t.textContent);
  for (const l of ["Maghrib opens", "Isha", "Fajr", "Sunrise", "Dhuhr", "Asr", "Next Maghrib"]) assert.ok(labels.includes(l), l);
  assert.equal(el.querySelectorAll(".mk").length, 7);
});

test("clock: centre shows the Waqt reading, next event and countdown; next marker is highlighted", () => {
  const w = loadPage().window, store = fakeStore(w), { el } = mountClock(store);
  assert.equal(el.querySelector('[data-slot="ctime"]').textContent, store.model.reading.display);
  assert.match(el.querySelector('[data-slot="cnext"]').textContent, /Next · Fajr/);
  assert.match(el.querySelector('[data-slot="ccount"]').textContent, /^\d\d:\d\d:\d\d$/);
  assert.equal(el.querySelector(".mk.next").dataset.key, "fajr");
  assert.ok(el.querySelector(".mk.overflow"), "after-close Isha is styled distinctly");
});

test("clock: demo data is labelled on the face itself", () => {
  const w = loadPage().window, { el } = mountClock(fakeStore(w, { isDemo: true, state: "error" }));
  assert.equal(el.querySelector('[data-slot="cchip"]').textContent, "DEMO · NOT LIVE");
  const live = mountClock(fakeStore(w)); assert.equal(live.el.querySelector('[data-slot="cchip"]').textContent, "");
});

test("clock: textual equivalent — accessible name, description, ordered event list, status text", () => {
  const w = loadPage().window, { el } = mountClock(fakeStore(w));
  const svg = el.querySelector("svg");
  assert.equal(svg.getAttribute("role"), "img"); assert.ok(svg.getAttribute("aria-labelledby"));
  assert.match(el.querySelector("desc").textContent, /Waqt \d\d:\d\d:\d\d/);
  const rows = [...el.querySelectorAll(".wc-events li")].map((li) => li.textContent);
  assert.equal(rows.length, 7); assert.match(rows[0], /Maghrib opens/); assert.match(rows.join("|"), /Isha.*25:05:06/);
  assert.ok(el.querySelector(".wc-events li.next"));
  for (const g of el.querySelectorAll(".mk")) { assert.equal(g.getAttribute("tabindex"), "0"); assert.ok(g.getAttribute("aria-label").includes("Waqt")); }
});

test("clock: keyboard — arrow keys move focus between markers, Home/End jump", () => {
  const w0 = loadPage().window, { el, w } = mountClock(fakeStore(w0));
  const items = [...el.querySelectorAll(".mk")]; items[0].focus();
  const key = (k) => el.querySelector('[role="list"]').dispatchEvent(new w.KeyboardEvent("keydown", { key: k, bubbles: true }));
  key("ArrowRight"); assert.equal(w.document.activeElement, items[1]);
  key("ArrowLeft"); assert.equal(w.document.activeElement, items[0]);
  key("End"); assert.equal(w.document.activeElement, items[items.length - 1]);
  key("Home"); assert.equal(w.document.activeElement, items[0]);
});

test("clock: loading and empty states render a message, never a blank area", () => {
  const w = loadPage().window, el = w.document.createElement("div"), c = w.Waqt.createClock(el, {});
  c.update({ state: "loading", model: null }); assert.match(el.textContent, /Loading Waqt/);
  c.update({ state: "empty", model: null, emptyReason: "polar day" }); assert.match(el.textContent, /undefined here.*polar day/);
});

test("clock: watch variant reuses the same event data (no labels, same markers)", () => {
  const w = loadPage().window, { el } = mountClock(fakeStore(w), { variant: "watch" });
  assert.equal(el.querySelectorAll(".mk").length, 7); assert.equal(el.querySelectorAll(".mk text").length, 0);
  assert.equal(el.querySelector(".wc-events"), null);
});

test("banner: success shows LIVE; error/offline say 'demonstration mode' and 'not live'; empty explains", async () => {
  const w = loadPage().window, B = w.Waqt.bannerHtml;
  assert.match(B({ state: "success", model: w.Waqt.fromWaqtData(demo().data), isDemo: false }), /LIVE/);
  const err = B({ state: "error", model: w.Waqt.fromWaqtData(demo().data), isDemo: true, error: { message: "boom" } });
  assert.match(err, /Live Waqt data unavailable/); assert.match(err, /demonstration mode/); assert.match(err, /not live/); assert.match(err, /data-retry/);
  assert.match(B({ state: "offline", model: null, error: null }), /offline/);
  assert.match(B({ state: "empty", emptyReason: "polar day" }), /polar day/);
});

/* ------------------------------------------------------------------------------- widgets */
test("day length: duration is computed from the two Maghrib instants and compared with 24:00:00 without hard-coded claims", () => {
  const w = loadPage().window, el = w.document.createElement("div"), dl = w.Waqt.createDayLength(el), store = fakeStore(w, { isDemo: true, state: "error" });
  dl.update(store);
  const m = store.model, dur = (m.day.closeMs - m.day.openMs) / 1000;
  assert.equal(el.querySelector('[data-slot="waqtlen"]').textContent, w.Waqt.fmtHMS(dur));
  assert.match(el.querySelector('[data-slot="diff"]').textContent, /shorter|longer/);
  assert.match(el.querySelector('[data-slot="srv"]').textContent, /86367\.918 s/);
  assert.match(el.querySelector('[data-slot="note"]').textContent, /not today's live value/);
});

test("mosque clock: WAQT / NEXT EVENT / MAGHRIB blocks, CONCEPT badge, DEMO flag", () => {
  const w = loadPage().window, el = w.document.createElement("div"), mc = w.Waqt.createMosqueClock(el);
  mc.update(fakeStore(w, { isDemo: true, state: "error" }));
  const t = el.textContent;
  for (const k of ["WAQT", "NEXT EVENT", "MAGHRIB", "CONCEPT", "DEMO · NOT LIVE", "Fajr"]) assert.ok(t.includes(k), k);
});

test("midnight vs Waqt: both models listed with the API's local times and readings", () => {
  const w = loadPage().window, el = w.document.createElement("div"), c = w.Waqt.createCompare(el);
  c.update(fakeStore(w));
  assert.equal(el.querySelectorAll("svg").length, 2);
  assert.match(el.querySelector("tbody").textContent, /05:03:18.*10:50:12/s);
});

/* ------------------------------------------------------- navigation, links, responsive critical bits */
test("navigation: collapses behind a Menu button; toggles aria-expanded; Escape closes", () => {
  const w = loadPage().window, d = w.document, btn = d.querySelector(".nav-toggle"), list = d.getElementById("site-nav");
  assert.ok(d.documentElement.classList.contains("js"));
  btn.click(); assert.equal(btn.getAttribute("aria-expanded"), "true"); assert.ok(list.classList.contains("open"));
  d.dispatchEvent(new w.KeyboardEvent("keydown", { key: "Escape" })); assert.equal(btn.getAttribute("aria-expanded"), "false");
});

test("navigation: spec labels in order, current page marked", () => {
  const d = loadPage("applications.html").window.document;
  const labels = [...d.querySelectorAll("#site-nav a, #site-nav .nav-pending")].map((a) => a.textContent.trim());
  assert.deepEqual(labels, ["Overview", "The Problem", "How It Works", "Live Demo", "API", "Applications", "Governance", "Community", "GitHub", "Read Spec / Docs"]);
  assert.equal(d.querySelector('#site-nav a[aria-current="page"]').textContent, "Applications");
});

test("external links: unconfigured URLs render as pending, non-clickable — never guessed", () => {
  const d = loadPage().window.document;
  for (const key of ["github", "buyMeACoffee"]) {
    const a = d.querySelector(`[data-link="${key}"]`);
    assert.equal(a.getAttribute("href"), null, key); assert.equal(a.getAttribute("aria-disabled"), "true"); assert.match(a.title, /not configured/i);
  }
  const docs = d.querySelector('[data-link="docs"]'); assert.equal(docs.getAttribute("href"), "resources.html#specifications");
});

test("external links: when configured, they are applied with rel=noopener", () => {
  const dom = loadPage(), w = dom.window;
  w.WAQT_CONFIG = { links: { github: "https://example.invalid/repo", buyMeACoffee: "https://example.invalid/coffee" }, contactEmail: "waqtapi@gmail.com", ideaSubject: "x" };
  w.eval(read("assets/js/site.js")); w.document.dispatchEvent(new w.Event("DOMContentLoaded"));
  const a = w.document.querySelector('[data-link="github"]');
  assert.equal(a.getAttribute("href"), "https://example.invalid/repo"); assert.equal(a.getAttribute("rel"), "noopener");
});

test("contact: Send an Idea is a mailto to waqtapi@gmail.com (no fake backend form)", () => {
  const d = loadPage().window.document, a = d.querySelector("[data-idea]");
  assert.match(a.getAttribute("href"), /^mailto:waqtapi@gmail\.com\?subject=/);
  assert.equal(d.querySelectorAll("form").length, 0);
});

test("responsive: pages declare a viewport and the stylesheet has the mobile nav breakpoint and reduced-motion rule", () => {
  const html = read("index.html"), css = read("assets/css/components.css");
  assert.match(html, /name="viewport" content="width=device-width, initial-scale=1"/);
  assert.match(css, /@media \(max-width:1100px\)/); assert.match(css, /prefers-reduced-motion:reduce/);
});

test("api base: ?api= override, localhost vs public default (same rules as the original viewer)", () => {
  const W = loadPage().window.Waqt;
  assert.equal(W.defaultApiBase({ hostname: "localhost", search: "" }), "http://localhost:8000");
  assert.equal(W.defaultApiBase({ hostname: "waqt.example", search: "" }), "https://waqt-api-r6e0.onrender.com");
  assert.equal(W.defaultApiBase({ hostname: "x", search: "?api=https://a.test" }), "https://a.test");
});
