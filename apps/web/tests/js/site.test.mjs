import test from "node:test";
import fs from "node:fs";
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
  assert.equal(by.isha.position, "after-close");           // API reports Isha past the day length
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
  assert.equal(el.querySelector('[data-slot="cnext"]').textContent, `Next · ${store.model.next.label}`);
  assert.match(el.querySelector('[data-slot="ccount"]').textContent, /^\d\d:\d\d:\d\d$/);
  assert.equal(el.querySelector(".mk.next").dataset.key, store.model.next.name);
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
  assert.equal(rows.length, 7); assert.match(rows[0], /Maghrib opens/); assert.match(rows.join("|"), /Isha.*25\:05\:09/);
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
  assert.match(el.querySelector('[data-slot="srv"]').textContent, /86368\.364 s/);
  assert.match(el.querySelector('[data-slot="note"]').textContent, /not today's live value/);
});

test("mosque clock: WAQT / NEXT EVENT / MAGHRIB blocks, CONCEPT badge, DEMO flag", () => {
  const w = loadPage().window, el = w.document.createElement("div"), mc = w.Waqt.createMosqueClock(el);
  mc.update(fakeStore(w, { isDemo: true, state: "error" }));
  const t = el.textContent;
  const nextLabel = w.Waqt.fromWaqtData(demo().data).next.label;
  for (const k of ["WAQT", "NEXT EVENT", "MAGHRIB", "CONCEPT", "DEMO · NOT LIVE", nextLabel, "(umm-al-qura)"]) assert.ok(t.includes(k), k);
});

test("midnight vs Waqt: both models listed with the API's local times and readings", () => {
  const w = loadPage().window, el = w.document.createElement("div"), c = w.Waqt.createCompare(el);
  c.update(fakeStore(w));
  assert.equal(el.querySelectorAll("svg").length, 2);
  assert.match(el.querySelector("tbody").textContent, /05:03:13.*10:50:40/s);
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

test("links: nav/footer resolve from the central configuration (repository, docs folder, Ko-fi)", () => {
  const w = loadPage().window, d = w.document, C = w.WAQT_CONFIG;
  const repo = C.project.repository.url;
  const gh = d.querySelector('[data-cfg="@repo"]');
  assert.equal(gh.getAttribute("href"), repo); assert.equal(gh.getAttribute("rel"), "noopener"); assert.match(gh.title, /Private repository/);
  assert.equal(d.querySelector('[data-cfg="docs.index"]').getAttribute("href"), `${repo}/tree/main/docs`);
  assert.equal(d.querySelector('[data-cfg="@support"]').getAttribute("href"), "https://ko-fi.com/ummatidawah");
});

test("links: references without a real URL are DISABLED, never guessed", () => {
  const w = loadPage().window, d = w.document;
  const a = d.createElement("a"); a.setAttribute("data-cfg", "docs.releaseNotes"); a.setAttribute("href", "#"); d.body.appendChild(a);
  const b = d.createElement("a"); b.setAttribute("data-cfg", "sdks.0.registry"); b.setAttribute("href", "#"); d.body.appendChild(b);
  w.eval(read("assets/js/site.js")); w.document.dispatchEvent(new w.Event("DOMContentLoaded"));
  for (const x of [a, b]) { assert.equal(x.getAttribute("href"), null); assert.equal(x.getAttribute("aria-disabled"), "true"); assert.match(x.title, /Planned|Not published/); }
  assert.equal(w.Waqt.resolveRef({ status: "not_published" }).kind, "disabled");
  assert.equal(w.Waqt.resolveRef({ path: "docs/API.md" }, { project: { repository: { url: "https://x.test/r/", branch: "dev", visibility: "public" } } }).url, "https://x.test/r/blob/dev/docs/API.md");
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


/* ======================================================================= Hijri provider (the 25-vs-27 report) */
test("hijri: the web REQUESTS the configured provider (umm-al-qura) by default, never a hard-coded arithmetic one", async () => {
  const w = loadPage().window, urls = [];
  assert.equal(w.WAQT_CONFIG.hijri.defaultProvider, "umm-al-qura");
  const store = w.Waqt.createLive({ base: "https://api.test", autoRetry: false, tickMs: 3_600_000, fetchImpl: async (u) => { urls.push(u); return okEnvelope(demo().data); } });
  store.start(); await tick(20); store.stop();
  assert.match(urls[0], /calendar_provider=umm-al-qura/);
  assert.doesNotMatch(urls[0], /arithmetic-tabular/);
});

test("hijri: the page shows the API's authoritative date WITH its provider — no hard-coded date", async () => {
  const dom = loadPage("index.html"), w = dom.window, d = w.document;
  const store = w.Waqt.createLive({ base: "https://api.test", autoRetry: false, tickMs: 3_600_000, fetchImpl: async () => okEnvelope(demo().data) });
  const fields = w.Waqt.bindFields(d); store.subscribe(() => fields.update(store)); store.start(); await tick(20); store.stop();
  const t = (k) => d.querySelector(`[data-bind="${k}"]`).textContent;
  assert.equal(t("hijri"), "27 Rabi al-Thani 1448 AH"); assert.equal(t("provider"), "umm-al-qura");
  assert.match(t("hijriNote"), /depend on the calendar convention/);
  // the static HTML itself contains no Hijri date
  assert.doesNotMatch(read("index.html"), /\d{1,2} (Rabi|Muharram|Safar|Jumada|Rajab|Sha|Ramadan|Shawwal|Dhu)/);
});

test("hijri: if the API says arithmetic-tabular (day 25) the UI shows THAT and names the provider", async () => {
  const w = loadPage().window, data = demo().data;
  data.hijri = Object.assign({}, data.hijri, { day: 25, date: "1448-04-25", display: "25 Rabi al-Thani 1448 AH", provider: { name: "arithmetic-tabular", version: "x" } });
  const m = w.Waqt.fromWaqtData(data);
  assert.equal(m.hijri.display, "25 Rabi al-Thani 1448 AH"); assert.equal(m.hijri.provider, "arithmetic-tabular");
  const mc = w.Waqt.createMosqueClock(w.document.createElement("div")); const el = w.document.createElement("div"); const c2 = w.Waqt.createMosqueClock(el);
  const model = m, anchor = w.Waqt.makeAnchor(model, 1);
  c2.update({ state: "success", model, anchor, isDemo: false, snapshot: () => w.Waqt.snapshotAt(anchor, 1) });
  assert.match(el.textContent, /25 Rabi al-Thani 1448 AH \(arithmetic-tabular\)/);
});

test("hijri: the API tester always sends an explicit provider for /v1/waqt", () => {
  const src = read("assets/js/pages/api.js");
  assert.match(src, /params\.calendar_provider = document\.getElementById\("t-prov"\)\.value/);
  assert.match(read("api.html"), /id="t-prov"/);
  assert.match(read("assets/js/waqt-api.js"), /calendar_provider=\$\{prov\}/);
});

/* ============================================================== occurrence-aware events (Codex finding) */
test("lab: occurrence-aware — tonight's Isha is the next event after Maghrib opens, then Fajr (not skipped)", async () => {
  const w = loadPage().window, W = w.Waqt, data = demo().data, m = W.fromWaqtData(data);
  assert.equal(W.nextEventAfter(m, m.day.openMs).name, "fajr", "the plain API list skips tonight's Isha (this is the bug)");
  const store = { model: m, isDemo: true, place: { lat: 9.0192, lon: 38.7525 }, params: {} };
  const extra = await W.ownDayOccurrences(store);
  assert.equal(extra.length, 1); assert.equal(extra[0].name, "isha"); assert.equal(extra[0].position, "in-day");
  const full = W.withOccurrences(m, extra);
  assert.equal(W.nextEventAfter(full, m.day.openMs).name, "isha");
  assert.equal(W.nextEventAfter(full, extra[0].instantMs + 1).name, "fajr");
  assert.ok(extra[0].instantMs < m.day.closeMs && extra[0].instantMs > m.day.openMs);
  assert.ok(full.events.filter((e) => e.name === "isha").length === 2, "tonight's and next evening's Isha are distinct occurrences");
});

test("lab: live path asks the API (open+1s, then the event instant) and never computes the occurrence", async () => {
  const w = loadPage().window, W = w.Waqt, data = demo().data, m = W.fromWaqtData(data), rec = demo().own_day_isha, calls = [];
  w.fetch = async (u) => { calls.push(new URL(u).searchParams.get("instant")); const d = JSON.parse(JSON.stringify(data)); if (calls.length === 1) d.next_event = rec.next_event_after_open; else d.waqt.reading = rec.reading_at_event; return okEnvelope(d); };
  const store = { model: m, isDemo: false, place: { lat: 9.0192, lon: 38.7525 }, params: { calendar_provider: "umm-al-qura" } };
  const extra = await W.ownDayOccurrences(store);
  assert.equal(calls.length, 2); assert.equal(Date.parse(calls[0]), m.day.openMs + 1000); assert.equal(calls[1], rec.next_event_after_open.instant);
  assert.equal(extra[0].display, rec.reading_at_event.display);
});

/* ============================================================== central configuration drives Resources/Governance */
const hubOf = () => {
  const dom = loadPage("resources.html", { extra: ["pages/resources"], fetchImpl: async () => okEnvelope({ api_version: "t" }) });
  return dom.window;
};

test("resources: hub has the seven sections in order; support is last", async () => {
  const w = hubOf(); await tick(10);
  const titles = [...w.document.querySelectorAll("#hub h2")].map((h) => h.textContent);
  assert.deepEqual(titles, ["Waqt Core", "API", "SDKs", "Developer resources", "Applications", "Community", "Support"]);
});

test("resources: documentation links are repository-relative Markdown on the configured (private) repository", async () => {
  const w = hubOf(); await tick(10); const d = w.document, repo = w.WAQT_CONFIG.project.repository.url;
  const api = [...d.querySelectorAll("#hub a")].find((a) => a.textContent === "API documentation (Markdown)");
  assert.equal(api.getAttribute("href"), `${repo}/blob/main/docs/API.md`);
  assert.ok(d.querySelector("#hub .badge.concept") && /PRIVATE REPO/.test(d.querySelector("#hub").textContent));
  assert.match(d.querySelector("[data-repo-note]").textContent, /Private repository until public release/);
});

test("resources: SDKs separate Source / Releases / Package registry / Documentation; unpublished items are disabled", async () => {
  const w = hubOf(); await tick(10); const d = w.document, hub = d.getElementById("hub");
  const sdks = [...hub.querySelectorAll("#hub-sdks")].length; assert.equal(sdks, 1);
  const tables = [...hub.querySelectorAll("section[aria-labelledby=hub-sdks] table")];
  assert.equal(tables.length, 2);
  for (const t of tables) {
    const heads = [...t.querySelectorAll("th[scope=row]")].map((x) => x.textContent);
    assert.deepEqual(heads, ["Source", "Releases", "Package registry", "Documentation"]);
    const rows = [...t.querySelectorAll("tr")];
    assert.ok(rows[1].querySelector(".res-off") && /PLANNED/.test(rows[1].textContent), "releases planned");
    assert.ok(rows[2].querySelector(".res-off") && /NOT PUBLISHED/.test(rows[2].textContent), "registry not published");
    assert.equal(rows[1].querySelector("a"), null); assert.equal(rows[2].querySelector("a"), null);
  }
  const hrefs = [...hub.querySelectorAll("a")].map((a) => a.getAttribute("href")).join(" ");
  assert.doesNotMatch(hrefs, /pypi\.org|npmjs\.com|drive\.google|releases\/download/);
});

test("resources: Ko-fi support appears only in the last section and only because a real URL is configured", async () => {
  const w = hubOf(); await tick(10); const secs = [...w.document.querySelectorAll("#hub section")];
  const last = secs[secs.length - 1];
  assert.equal(last.querySelector("a").getAttribute("href"), "https://ko-fi.com/ummatidawah");
  assert.ok(!secs.slice(0, -1).some((s) => s.innerHTML.includes("ko-fi.com")));
});

test("governance: role metadata comes from config, is marked DEMO/EDITABLE, and the ratification label mirrors the decision records", () => {
  const dom = loadPage("governance.html", { extra: ["pages/governance"] }), d = dom.window.document;
  const t = d.getElementById("gov-roles").textContent;
  for (const x of ["Dr. Salim Muhammed Redi", "Mr. Hawas Muhaba Hussein", "Logical / Idea Owner", "Technical Developer / Maintainer", "waqtapi@gmail.com", "Open to expert contributors and reviewers."]) assert.ok(t.includes(x), x);
  assert.match(d.body.textContent, /DEMO · EDITABLE PROJECT METADATA/);
  const decDir = new URL("../../../../conformance/decisions/", import.meta.url);
  const heads = fs.readdirSync(decDir).filter((f) => /^DR-\d+\.md$/.test(f)).map((f) => [f.replace(".md", ""), fs.readFileSync(new URL(f, decDir), "utf8").split("## Context")[0].includes("PENDING")]);
  const pendingIds = heads.filter(([, p]) => p).map(([id]) => id);
  const cfg = dom.window.WAQT_CONFIG.governance;
  const expectedLabel = "Conformance 2.0.0 released · independent review explicitly waived and not performed (DR-0015)";
  assert.equal(d.querySelector("[data-ratification]").textContent, expectedLabel);
  assert.equal(cfg.ratificationLabel, expectedLabel);
  assert.equal(cfg.contractReleased, true);
  assert.equal(cfg.ratification, "owner-approved-release");
  assert.equal(cfg.releaseApprovalRecord, "DR-0015");
  assert.deepEqual(pendingIds, ["DR-0010", "DR-0011", "DR-0012", "DR-0013", "DR-0014"]);
  for (const article of d.querySelectorAll("[data-dr]")) {
    const drId = article.querySelector(".font-label-md")?.textContent?.trim();
    const badge = article.querySelector(".badge")?.textContent?.trim();
    if (pendingIds.includes(drId)) {
      assert.equal(badge, "RATIFICATION PENDING", `${drId} should be visibly pending ratification`);
    } else {
      assert.equal(badge, "RATIFIED", `${drId} should be ratified`);
    }
  }
  assert.match(d.querySelector("[data-maint-notice]").textContent, /not a governance approval or ratification/);
  assert.doesNotMatch(d.body.textContent, /ratified on|signed by/i);
  assert.match(d.querySelector("footer [data-maintainers]").textContent, /demo metadata/);
});
