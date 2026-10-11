// Real-browser verification of the CURRENT Waqt Web (apps/web/live-demo.html and lab.html) against the REAL API.
// Covers the Option B (API 1.7.0, umm-al-qura default) contract as seen from the browser:
//   * the Hijri date and provider on screen are the ones in the API response (and the page asks for the provider explicitly)
//   * loading -> success -> API failure / offline demo fallback (visibly labelled) -> recovery
//   * the server stays authoritative for Waqt time (tampered responses are shown as received; provider switch moves no Waqt instant)
//   * the Experience Lab lists the opening Maghrib's following Isha before Fajr
//   * desktop and mobile viewports
// Selectors are ids and [data-bind] attributes the pages already expose; nothing is restored for an old harness.
// Chrome is launched with --disable-web-security & friends REMOVED, so CORS is genuinely enforced.
// Expects: API on :8000 with WAQT_CORS_ORIGINS=http://localhost:8080, static apps/web on :8080 (run_web_option_b.sh does this).
import chromium from "@sparticuz/chromium";
import puppeteer from "puppeteer-core";
import fs from "node:fs";
import { fileURLToPath } from "node:url";

const SITE = "http://localhost:8080", API = "http://localhost:8000", MIN_ASSERTIONS = 30;
const OUT = fileURLToPath(new URL("./results/", import.meta.url)); fs.mkdirSync(OUT, { recursive: true });
const results = [];
const rec = (id, name, ok, detail = "") => { results.push({ id, name, ok: !!ok, detail: String(detail).slice(0, 400) }); console.log(`${ok ? "PASS" : "FAIL"} [${id}] ${name}${detail ? "  — " + String(detail).slice(0, 300) : ""}`); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const eq = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const hms = (s) => { const m = /(\d+):(\d\d):(\d\d)/.exec(s || ""); return m ? (+m[1]) * 3600 + (+m[2]) * 60 + (+m[3]) : NaN; };
const secs = (s) => Number(String(s || "").replace(/[^\d.]/g, ""));
const api = (path) => fetch(API + path).then((r) => r.json());

const executablePath = process.platform === "win32"
  ? [process.env.CHROME_PATH, "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe", "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe"].filter(Boolean).find((p) => fs.existsSync(p))
  : await chromium.executablePath();
if (!executablePath) throw new Error("No Chrome: set CHROME_PATH (Windows) or install @sparticuz/chromium.");
const browser = await puppeteer.launch({
  args: chromium.args.filter((a) => !/single-process|no-zygote|disable-web-security|allow-running-insecure|disable-site-isolation|disable-features=/.test(a)).concat(["--no-sandbox"]),
  executablePath, headless: process.platform === "win32" ? true : "shell",
});
console.log("Browser:", await browser.version());

/** mode: {kind: pass|abort|delay|tamper, ms, fn}. Applies to /v1/waqt only (the provider list /v1/calendar always passes). */
async function openPage(path, { viewport = { width: 1280, height: 900 }, mode = { kind: "pass" }, offline = false, waitUntil = "networkidle0" } = {}) {
  const ctx = await browser.createBrowserContext(), page = await ctx.newPage();
  await page.setViewport(viewport);
  Object.assign(page, { mode, errs: [], waqtReqs: [], waqt: [] });
  page.on("pageerror", (e) => page.errs.push("pageerror: " + e));
  page.on("console", (m) => { if (m.type() === "error" && !/Failed to load resource|ERR_FAILED|net::/.test(m.text())) page.errs.push(m.text()); });
  if (offline) await page.evaluateOnNewDocument(() => Object.defineProperty(navigator, "onLine", { get: () => false }));
  await page.setRequestInterception(true);
  page.on("request", async (req) => {
    const u = new URL(req.url());
    if (u.origin !== API || u.pathname !== "/v1/waqt") return req.continue();
    page.waqtReqs.push(u);
    const m = page.mode;
    if (m.kind === "abort") return req.abort("failed");
    if (m.kind === "delay") { await sleep(m.ms); return req.continue(); }
    if (m.kind === "tamper") {
      const real = await fetch(req.url()).then((r) => r.json()); m.fn(real);
      return req.respond({ status: 200, contentType: "application/json", headers: { "access-control-allow-origin": SITE }, body: JSON.stringify(real) });
    }
    return req.continue();
  });
  page.on("response", async (r) => {
    const u = new URL(r.url());
    if (u.origin === API && u.pathname === "/v1/waqt" && r.status() === 200) { try { page.waqt.push({ url: u, json: await r.json(), at: Date.now() }); } catch { /* aborted body */ } }
  });
  await page.goto(SITE + path, { waitUntil });
  return page;
}
const bind = (page, name) => page.evaluate((n) => { const e = document.querySelector(`#demo-live [data-bind="${n}"]`); return e ? e.textContent.trim() : null; }, name);
const banner = (page, id) => page.evaluate((i) => document.getElementById(i)?.innerText || "", id);
const waitFn = (page, fn, arg, timeout = 15000) => page.waitForFunction(fn, { timeout }, arg).then(() => true, () => false);
const waitState = (page, label, t) => waitFn(page, (l) => document.querySelector('#demo-live [data-bind="state"]')?.textContent.trim() === l, label, t);
const noOverflow = (page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);
const visible = (page, sel) => page.evaluate((s) => { const e = document.querySelector(s); if (!e) return false; const r = e.getBoundingClientRect(), cs = getComputedStyle(e); return r.width > 0 && r.height > 0 && cs.visibility !== "hidden" && cs.display !== "none"; }, sel);
const last = (page) => page.waqt[page.waqt.length - 1];
const demoField = (page) => page.evaluate(() => ({ hijri: window.WAQT_DEMO?.data?.hijri?.display, provider: window.WAQT_DEMO?.data?.hijri?.provider?.name, label: window.WAQT_DEMO?.label }));

// preflight: fail with a precise message if the pages and this harness disagree (never a bare TypeError)
async function requireElements(page, sels, where) {
  const missing = await page.evaluate((ss) => ss.filter((s) => !document.querySelector(s)), sels);
  if (missing.length) throw new Error(`${where}: required element(s) missing: ${missing.join(", ")} -- page markup and harness disagree`);
}
const DEMO_SEL = ["#demo-live", "#d-cal", "#d-apply", "#d-lat", "#d-lon", "#d-json", "#d-url", "#demo-banner", '[data-bind="state"]', '[data-bind="hijri"]', '[data-bind="provider"]', '[data-bind="reading"]', '[data-bind="readingSeconds"]', '[data-bind="open"]', '[data-bind="close"]', '[data-bind="length"]', '[data-bind="next"]'];
const LAB_SEL = ["#lab-banner", "#scrub", "#scrub-out", "#pb-next", "#pb-chip"];

// ===================================== LIVE DEMO: loading =====================================
let p = await openPage("/live-demo.html", { mode: { kind: "delay", ms: 2500 }, waitUntil: "domcontentloaded" });
await waitFn(p, () => !!document.getElementById("demo-banner"), null);
await requireElements(p, DEMO_SEL, "live-demo.html");
const loadingSeen = await waitFn(p, () => /Loading Waqt data/.test(document.getElementById("demo-banner").innerText), null, 2400);
rec("OB-L1", "loading: banner says Waqt data is loading and the state is LOADING before the API answers", loadingSeen && (await bind(p, "state")) === "LOADING", await banner(p, "demo-banner"));
rec("OB-L2", "loading: no Hijri date or provider is shown before data arrives", (await bind(p, "hijri")) === "—" && (await bind(p, "provider")) === "—");
rec("OB-L3", "loading -> success: the page reaches LIVE once the delayed API answers", await waitState(p, "LIVE", 15000));
await p.close();

// ===================================== LIVE DEMO: success, Hijri date + provider =====================================
p = await openPage("/live-demo.html");
rec("OB-S1", "success: state is LIVE and the live strip (not the demo notice) is shown", (await waitState(p, "LIVE", 10000)) && /LIVE/.test(await banner(p, "demo-banner")) && !/demonstration mode/.test(await banner(p, "demo-banner")), await banner(p, "demo-banner"));
const r0 = last(p), d0 = r0.json.data;
await waitFn(p, () => /calendar_provider=umm-al-qura/.test(document.getElementById("d-url").textContent), null, 5000);
rec("OB-S2", "the page asks for the provider EXPLICITLY (calendar_provider=umm-al-qura in the request and in the inspector URL)", p.waqtReqs.every((u) => u.searchParams.get("calendar_provider") === "umm-al-qura") && /calendar_provider=umm-al-qura/.test(await p.$eval("#d-url", (e) => e.textContent)) && (await p.$eval("#d-cal", (e) => e.value)) === "umm-al-qura", p.waqtReqs.map(String).join(" "));
const shownHijri = await bind(p, "hijri"), shownProv = await bind(p, "provider");
rec("OB-S3", "displayed Hijri date and provider label equal the API response (hijri.display / hijri.provider.name)", shownHijri === d0.hijri.display && shownProv === d0.hijri.provider.name && shownProv === "umm-al-qura", `${shownHijri} | ${shownProv} vs ${d0.hijri.display} | ${d0.hijri.provider.name}`);
const uq = await api(`/v1/waqt?lat=9.0192&lon=38.7525&instant=${encodeURIComponent(d0.instant)}&calendar_provider=umm-al-qura`);
const at = await api(`/v1/waqt?lat=9.0192&lon=38.7525&instant=${encodeURIComponent(d0.instant)}&calendar_provider=arithmetic-tabular`);
rec("OB-S4", "independent check at the same instant: screen == umm-al-qura and != arithmetic-tabular (the provider on the label is the one used)", shownHijri === uq.data.hijri.display && shownHijri !== at.data.hijri.display, `${shownHijri} / uq ${uq.data.hijri.display} / at ${at.data.hijri.display}`);
rec("OB-S5", "the deliberate-default caveat (calendar conventions differ; Waqt time does not change) is on the page", /Umm al-Qura by default: a deliberate project choice/.test(await p.$eval('[data-bind="hijriNote"]', (e) => e.textContent)) && /not a claim that every community follows it/.test(await p.$eval('[data-bind="hijriNote"]', (e) => e.textContent)), await p.$eval('[data-bind="hijriNote"]', (e) => e.textContent));
const shownSecs = secs(await bind(p, "readingSeconds")), expectSecs = d0.waqt.reading.seconds + (Date.now() - r0.at) / 1000;
rec("OB-S6", "canonical Waqt reading on screen = server reading + elapsed time (page does not compute its own)", Math.abs(shownSecs - expectSecs) <= 4, `shown ${shownSecs} expected ~${expectSecs.toFixed(1)}`);
rec("OB-S7", "no page errors / CORS failures on the live path", p.errs.length === 0, p.errs.join(" | "));
await p.screenshot({ path: OUT + "ob-live-desktop.png" });

// ----- provider switch: label moves, Waqt instants do not -----
const before = { open: await bind(p, "open"), close: await bind(p, "close"), length: await bind(p, "length") }, nBefore = p.waqt.length;
await p.select("#d-cal", "arithmetic-tabular"); await p.click("#d-apply");
const switched = await waitFn(p, () => document.querySelector('#demo-live [data-bind="provider"]')?.textContent.trim() === "arithmetic-tabular", null, 10000);
for (let i = 0; i < 30 && !(p.waqt.length > nBefore && last(p).url.searchParams.get("calendar_provider") === "arithmetic-tabular"); i++) await sleep(100);   // the response body is read asynchronously
const r1 = last(p), d1 = r1.json.data;
rec("OB-P1", "switching to arithmetic-tabular: request names it, label + date follow the response", switched && p.waqt.length > nBefore && r1.url.searchParams.get("calendar_provider") === "arithmetic-tabular" && (await bind(p, "hijri")) === d1.hijri.display && d1.hijri.provider.name === "arithmetic-tabular", `${await bind(p, "hijri")}`);
rec("OB-P2", "the two providers give different Hijri days for the same moment (the label differs, as documented)", (await bind(p, "hijri")) !== shownHijri, `${shownHijri} -> ${await bind(p, "hijri")}`);
rec("OB-P3", "provider choice moves NO Waqt instant: maghrib open/close, day length and every event instant are identical", eq(before, { open: await bind(p, "open"), close: await bind(p, "close"), length: await bind(p, "length") }) && eq(d0.day, d1.day) && eq(d0.events.map((e) => [e.name, e.instant]), d1.events.map((e) => [e.name, e.instant])), JSON.stringify(before));
await p.select("#d-cal", "umm-al-qura"); await p.click("#d-apply");
rec("OB-P4", "switching back restores umm-al-qura and the original Hijri date", await waitFn(p, (h) => document.querySelector('#demo-live [data-bind="hijri"]')?.textContent.trim() === h, shownHijri, 10000) && (await bind(p, "provider")) === "umm-al-qura");
await p.close();

// ----- server authority: tampered responses are displayed as received (no recomputation, no hard-coded date/provider) -----
p = await openPage("/live-demo.html", { mode: { kind: "tamper", fn: (j) => { j.data.waqt.reading.seconds = 1000; j.data.hijri.display = "99 Test al-Thani 9999 AH"; j.data.hijri.provider.name = "test-provider"; } } });
await waitState(p, "LIVE", 10000);
const t = secs(await bind(p, "readingSeconds"));
rec("OB-A1", "server authority: a response saying reading=1000 s is shown as ~1000 s (+elapsed), not recomputed from instants", t >= 1000 && t <= 1010, `shown ${t}`);
rec("OB-A2", "server authority: Hijri date and provider text come from the response, not from page code or config", (await bind(p, "hijri")) === "99 Test al-Thani 9999 AH" && (await bind(p, "provider")) === "test-provider", `${await bind(p, "hijri")} | ${await bind(p, "provider")}`);
await p.close();

// ===================================== LIVE DEMO: failure, offline, recovery =====================================
p = await openPage("/live-demo.html", { mode: { kind: "abort" }, waitUntil: "domcontentloaded" });
const demoUp = await waitState(p, "DEMO · NOT LIVE", 15000), bn = await banner(p, "demo-banner"), dm = await demoField(p);
rec("OB-F1", "API failure: banner announces demonstration mode and a frozen recorded sample that is NOT live", demoUp && /viewing demonstration mode/.test(bn) && /recorded sample/.test(bn) && /not live/i.test(bn), bn.replace(/\n/g, " "));
rec("OB-F2", "API failure: state badge says DEMO · NOT LIVE and the inspector marks the JSON as a recorded sample", (await bind(p, "state")) === "DEMO · NOT LIVE" && /^\/\/ RECORDED DEMONSTRATION SAMPLE/.test(await p.$eval("#d-json", (e) => e.textContent)));
rec("OB-F3", "API failure: the Hijri date shown is the recorded sample's own, with its provider (umm-al-qura), not invented", (await bind(p, "hijri")) === dm.hijri && (await bind(p, "provider")) === dm.provider && dm.provider === "umm-al-qura", `${await bind(p, "hijri")} | ${dm.label}`);
const f1 = await bind(p, "reading"); await sleep(2300);
rec("OB-F4", "API failure: demo clock is frozen (does not tick, so it cannot pass for a live clock)", f1 === (await bind(p, "reading")) && f1 !== "—", f1);
await p.screenshot({ path: OUT + "ob-demo-fallback.png" });
// recovery
p.mode = { kind: "pass" };
await p.click("#demo-banner [data-retry]");
const recovered = await waitState(p, "LIVE", 15000);
rec("OB-F5", "recovery: after the API returns, 'Retry now' brings live data back and the demo notice disappears", recovered && !/demonstration mode/.test(await banner(p, "demo-banner")) && !/^\/\/ RECORDED/.test(await p.$eval("#d-json", (e) => e.textContent)), await banner(p, "demo-banner"));
rec("OB-F6", "recovery: Hijri date/provider again equal the live response", recovered && (await bind(p, "hijri")) === last(p).json.data.hijri.display && (await bind(p, "provider")) === last(p).json.data.hijri.provider.name);
rec("OB-F7", "no uncaught page errors through failure and recovery", p.errs.length === 0, p.errs.join(" | "));
await p.close();

p = await openPage("/live-demo.html", { offline: true, waitUntil: "domcontentloaded" });
const offUp = await waitState(p, "DEMO · NOT LIVE", 10000);
rec("OB-F8", "offline: the browser-offline case also shows the labelled demo sample and says the browser is offline", offUp && /appears to be offline/.test(await banner(p, "demo-banner")) && /recorded sample/.test(await banner(p, "demo-banner")));
rec("OB-F9", "offline: no /v1/waqt request is even attempted", p.waqtReqs.length === 0, `${p.waqtReqs.length} requests`);
await p.close();

// ===================================== LIVE DEMO: mobile =====================================
p = await openPage("/live-demo.html", { viewport: { width: 375, height: 740 } });
const mobLive = await waitState(p, "LIVE", 10000);
rec("OB-M1", "mobile 375px: LIVE, Hijri date and provider are visible and equal the response", mobLive && (await visible(p, '#demo-live [data-bind="hijri"]')) && (await visible(p, '#demo-live [data-bind="provider"]')) && (await bind(p, "hijri")) === last(p).json.data.hijri.display && (await bind(p, "provider")) === "umm-al-qura");
rec("OB-M2", "mobile 375px: no horizontal page scroll; the Apply control is reachable", (await noOverflow(p)) && (await visible(p, "#d-apply")), `scrollWidth vs ${375}`);
await p.screenshot({ path: OUT + "ob-live-mobile.png", fullPage: false });
await p.close();

// every page of the site at mobile width (the overflow bug fixed in components.css would have been caught here)
for (const f of fs.readdirSync(fileURLToPath(new URL("../../apps/web/", import.meta.url))).filter((n) => n.endsWith(".html")).sort()) {
  const q = await openPage("/" + f, { viewport: { width: 375, height: 740 } }); await sleep(600);
  rec("OB-M3:" + f, `mobile 375px: ${f} has no horizontal page scroll`, await noOverflow(q), await q.evaluate(() => document.documentElement.scrollWidth + "px"));
  await q.close();
}

// ===================================== EXPERIENCE LAB =====================================
// Independent truth from the API: the Isha that follows the OPENING Maghrib is the first event of the Waqt day.
const first = await api("/v1/waqt?lat=9.0192&lon=38.7525&calendar_provider=umm-al-qura");
const openMs = Date.parse(first.data.day.maghrib_open), lenS = first.data.day.length_si_seconds;
const atOpen = await api(`/v1/waqt?lat=9.0192&lon=38.7525&calendar_provider=umm-al-qura&instant=${encodeURIComponent(new Date(openMs + 1000).toISOString().replace(/\.\d{3}Z$/, "Z"))}`);
const ishaS = (Date.parse(atOpen.data.next_event.instant) - openMs) / 1000, fajrE = first.data.events.find((e) => e.name === "fajr");
rec("OB-X0", "API ground truth: at the opening Maghrib the next event is Isha, and it falls before Fajr", atOpen.data.next_event.name === "isha" && ishaS > 0 && ishaS < (Date.parse(fajrE.instant) - openMs) / 1000, `isha at +${ishaS.toFixed(0)} s`);

const scrubTo = async (page, v) => { await page.$eval("#scrub", (s, v) => { s.value = v; s.dispatchEvent(new Event("input", { bubbles: true })); }, v); await sleep(120); return page.$eval("#scrub-out", (e) => e.innerText.replace(/\n/g, " | ")); };
async function labOrder(page, tag, demo) {
  await requireElements(page, LAB_SEL, "lab.html");
  // the occurrence-aware model is merged asynchronously: wait until the scrub at the day opening names Isha
  const ok = await waitFn(page, () => { const s = document.getElementById("scrub"); s.value = 0; s.dispatchEvent(new Event("input", { bubbles: true })); return /Next: Isha in/.test(document.getElementById("scrub-out").innerText); }, null, 15000);
  const o0 = await scrubTo(page, 0);
  rec(`${tag}1`, "lab: at the opening Maghrib nothing has happened yet and the NEXT event is Isha (not Fajr)", ok && /Last event: none yet this Waqt day/.test(o0) && /Next: Isha in/.test(o0), o0);
  if (!demo) { const cd = hms((/Next: Isha in (\d\d:\d\d:\d\d)/.exec(o0) || [])[1]); rec(`${tag}2`, "lab: the Isha countdown at the opening equals the API's own Isha instant (not computed by the page)", Math.abs(cd - ishaS) <= 3, `page ${cd}s vs API ${ishaS.toFixed(0)}s`); }
  const seq = []; let prev = "";
  for (let v = 0; v <= 1000; v += 20) { const m = /Next: (.+?) in /.exec(await scrubTo(page, v)); const n = m ? m[1] : "none"; if (n !== prev) { seq.push(n); prev = n; } }
  rec(`${tag}3`, "lab: sweeping the whole Waqt day, the event order starts Isha, then Fajr, then Sunrise", eq(seq.slice(0, 3), ["Isha", "Fajr", "Sunrise"]), seq.join(" → "));
  const after = await scrubTo(page, 1000 * ((demo ? 8000 : ishaS + 300) / (demo ? 86368 : lenS)));
  rec(`${tag}4`, "lab: just after Isha, the last event is Isha and the next is Fajr", /Last event: Isha/.test(after) && /Next: Fajr in/.test(after), after);
  await page.$eval("#scrub", (s) => { s.value = 0; s.dispatchEvent(new Event("input", { bubbles: true })); });
  rec(`${tag}5`, "lab: the playback panel starts at Waqt 00:00:00 with Isha as the next event", /Waqt 00:00:00/.test(await page.$eval("#pb-reading", (e) => e.textContent)) && /Isha/.test(await page.$eval("#pb-next", (e) => e.textContent)), await page.$eval("#pb-next", (e) => e.textContent));
}
p = await openPage("/lab.html");
rec("OB-X1", "lab (desktop): live data, banner shows LIVE and no demonstration notice", await waitFn(p, () => /LIVE/.test(document.getElementById("lab-banner").innerText), null, 10000) && !/demonstration mode/.test(await banner(p, "lab-banner")), await banner(p, "lab-banner"));
await labOrder(p, "OB-X", false);
rec("OB-X6", "lab (desktop): playback chip is not marked as demo while live", !/DEMO/.test(await p.$eval("#pb-chip", (e) => e.textContent)), await p.$eval("#pb-chip", (e) => e.textContent));
rec("OB-X7", "lab (desktop): no page errors", p.errs.length === 0, p.errs.join(" | "));
await p.screenshot({ path: OUT + "ob-lab-desktop.png" }); await p.close();

p = await openPage("/lab.html", { mode: { kind: "abort" }, waitUntil: "domcontentloaded" });
rec("OB-Y0", "lab (API down): demonstration notice is shown and the playback chip says DEMO SAMPLE", await waitFn(p, () => /demonstration mode/.test(document.getElementById("lab-banner").innerText), null, 15000) && /DEMO SAMPLE/.test(await p.$eval("#pb-chip", (e) => e.textContent)) && /\(demo sample\)/.test(await scrubTo(p, 100)), await banner(p, "lab-banner"));
await labOrder(p, "OB-Y", true);
await p.close();

p = await openPage("/lab.html", { viewport: { width: 375, height: 740 } });
await waitFn(p, () => /LIVE/.test(document.getElementById("lab-banner").innerText), null, 10000);
rec("OB-Z0", "lab (mobile 375px): no horizontal scroll and the scrubber is visible", (await noOverflow(p)) && (await visible(p, "#scrub")));
await labOrder(p, "OB-Z", false);
await p.screenshot({ path: OUT + "ob-lab-mobile.png" }); await p.close();

await browser.close();
const failed = results.filter((r) => !r.ok);
fs.writeFileSync(OUT + "web-option-b-browser-results.json", JSON.stringify({ browser: "HeadlessChrome (see run log)", ran_at: new Date().toISOString(), assertions: results.length, failed: failed.length, results }, null, 2));
console.log(`\n${results.length - failed.length}/${results.length} passed`);
if (results.length < MIN_ASSERTIONS) { console.log(`BLOCKED/INVALID: only ${results.length} assertions executed (< ${MIN_ASSERTIONS}); a launch without assertions is not a pass`); process.exit(2); }
process.exit(failed.length ? 1 : 0);
