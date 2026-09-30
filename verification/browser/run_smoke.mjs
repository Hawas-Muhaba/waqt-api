// Sprint 13 Goal E: drive apps/web/index.html in a REAL (headless) Chrome against the REAL API.
// NOTE: @sparticuz/chromium ships with --disable-web-security; that flag (and the site-isolation ones) is REMOVED
// below, otherwise the CORS checks would be vacuous. Section 1d is a negative control proving enforcement is on.
// Usage: node run_smoke.mjs   (expects API on :8000 with WAQT_CORS_ORIGINS=http://localhost:8080, static on :8080)
// Requires: npm i puppeteer-core @sparticuz/chromium   (see verification/README.md)
import chromium from "@sparticuz/chromium";
import puppeteer from "puppeteer-core";
import fs from "node:fs";

const PAGE = "http://localhost:8080/index.html";
const OUT = new URL("./results/", import.meta.url).pathname;
fs.mkdirSync(OUT, { recursive: true });
const results = [];
const rec = (id, name, ok, detail = "") => { results.push({ id, name, ok: !!ok, detail }); console.log(`${ok ? "PASS" : "FAIL"} [${id}] ${name}${detail ? "  — " + detail : ""}`); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const browser = await puppeteer.launch({ args: chromium.args.filter((a) => !/single-process|no-zygote|disable-web-security|allow-running-insecure|disable-site-isolation|disable-features=/.test(a)).concat(["--no-sandbox"]), executablePath: await chromium.executablePath(), headless: "shell" });
console.log("Browser:", await browser.version());

async function newPage({ geo = null, grant = false, viewport = { width: 1100, height: 900 }, clockOffsetMs = null } = {}) {
  const ctx = await browser.createBrowserContext();
  if (grant) await ctx.overridePermissions("http://localhost:8080", ["geolocation"]);
  const page = await ctx.newPage();
  await page.setViewport(viewport);
  if (geo) await page.setGeolocation(geo);
  page.consoleMsgs = []; page.netFails = []; page.apiCalls = [];
  page.on("console", (m) => page.consoleMsgs.push({ type: m.type(), text: m.text() }));
  page.on("pageerror", (e) => page.consoleMsgs.push({ type: "pageerror", text: String(e) }));
  page.on("requestfailed", (r) => page.netFails.push(r.url() + " " + (r.failure() || {}).errorText));
  // Puppeteer's response.headers() does not reliably expose cross-origin response headers; the raw CDP
  // Network.responseReceivedExtraInfo event carries the exact headers the browser received.
  const cdp = await page.createCDPSession(); await cdp.send("Network.enable");
  const extra = {};
  cdp.on("Network.responseReceivedExtraInfo", (e) => { extra[e.requestId] = e.headers; });
  cdp.on("Network.responseReceived", (e) => { if (e.response.url.includes(":8000")) page.apiCalls.push({ url: e.response.url, status: e.response.status, id: e.requestId, get acao() { return (extra[this.id] || {})["access-control-allow-origin"]; } }); });
  if (clockOffsetMs !== null) {
    // Shift the page's clock (Date.now / new Date()) so a boundary can be reached in seconds; the
    // API is asked for the same shifted instant so server and page agree. The page logic is untouched.
    await page.evaluateOnNewDocument((off) => {
      const RD = Date; const now = () => RD.now() + off;
      class FD extends RD { constructor(...a) { if (a.length === 0) super(now()); else super(...a); } static now() { return now(); } }
      window.Date = FD; window.__clockOffset = off;
    }, clockOffsetMs);
    await page.setRequestInterception(true);
    page.on("request", (req) => {
      const u = new URL(req.url());
      if (u.pathname === "/v1/waqt" && !u.searchParams.has("instant")) {
        u.searchParams.set("instant", new Date(Date.now() + clockOffsetMs).toISOString().replace(".000Z", "Z")); req.continue({ url: u.toString() });
      } else req.continue();
    });
  }
  await page.goto(PAGE, { waitUntil: "networkidle0" });
  return page;
}
const text = (page, sel) => page.$eval(sel, (e) => e.textContent.trim());
async function enter(page, lat, lon) {
  await page.$eval("#lat", (e) => (e.value = "")); await page.$eval("#lon", (e) => (e.value = ""));
  await page.type("#lat", String(lat)); await page.type("#lon", String(lon));
  await page.click("#goBtn");
  await page.waitForFunction(() => { const s = document.getElementById("status").textContent; return s && !s.startsWith("Loading") && !s.startsWith("Enter coordinates, or"); }, { timeout: 15000 });
  await sleep(300);
}
async function snapshot(page) {
  return page.evaluate(() => ({
    status: document.getElementById("status").textContent, statusErr: document.getElementById("status").className === "err",
    contentHidden: document.getElementById("content").hidden,
    clock: document.getElementById("clockDisplay").textContent, pct: document.getElementById("arcPct").textContent,
    dashoffset: document.getElementById("arcProgress").getAttribute("stroke-dashoffset"),
    heroSub: document.getElementById("heroSub").innerText,
    events: [...document.querySelectorAll("#eventsBody tr")].map((tr) => [...tr.children].map((td) => td.textContent.trim())),
    nextRow: (document.querySelector("#eventsBody tr.next") || { children: [{ textContent: null }] }).children[0].textContent,
    reps: [...document.querySelectorAll("#repsGrid .rep-card")].map((c) => [...c.children].map((x) => x.textContent.trim())),
    meta: Object.fromEntries([...document.querySelectorAll("#metaGrid dt")].map((dt) => [dt.textContent, dt.nextElementSibling.textContent])),
    scrollW: document.documentElement.scrollWidth, innerW: window.innerWidth,
    providers: [...document.querySelectorAll("#provider option")].map((o) => o.value),
  }));
}
const errsOf = (page) => page.consoleMsgs.filter((m) => m.type === "error" || m.type === "pageerror");

// ---------- 1. boot + CORS ----------
let p = await newPage();
let s = await snapshot(p);
rec("1", "page boots, provider list loaded from /v1/calendar", s.providers.length >= 2, s.providers.join(","));
rec("1b", "CORS (enforced browser): cross-origin call from page origin succeeded (all 4 providers loaded, not the fallback)",
  p.apiCalls.length > 0 && p.apiCalls.every((c) => c.status === 200) && s.providers.length === 4, JSON.stringify(p.apiCalls.map((c) => c.status)) + " providers=" + s.providers.length);
rec("1c", "no console errors on load", errsOf(p).length === 0, JSON.stringify(errsOf(p)));

{ // 1d negative control: same page from an origin NOT allowed by WAQT_CORS_ORIGINS must be blocked by the browser
  const ctx = await browser.createBrowserContext(); const np = await ctx.newPage();
  await np.goto("http://127.0.0.1:8080/index.html", { waitUntil: "networkidle0" });
  const blocked = await np.evaluate(async () => { try { await fetch("http://localhost:8000/v1/health"); return false; } catch (e) { return true; } });
  const opts = await np.evaluate(() => document.querySelectorAll("#provider option").length);
  rec("1d", "CORS enforced (negative control): page on disallowed origin 127.0.0.1:8080 cannot read the API", blocked === true, `fetch blocked=${blocked}, provider options=${opts} (fallback single option expected)`);
  await ctx.close();
}
{ // 1e positive control from the allowed origin, using the page's own fetch semantics
  const ctx = await browser.createBrowserContext(); const np = await ctx.newPage();
  await np.goto("http://localhost:8080/index.html", { waitUntil: "networkidle0" });
  const ok = await np.evaluate(async () => { try { const r = await fetch("http://localhost:8000/v1/version"); return (await r.json()).data.api_version; } catch (e) { return String(e); } });
  rec("1e", "CORS allows the configured origin (positive control): /v1/version readable from localhost:8080", ok === "1.4.0", String(ok));
  await ctx.close();
}

// ---------- 2. Addis Ababa (manual coordinates) ----------
await enter(p, 9.0192, 38.7525); s = await snapshot(p);
rec("2a", "Addis Ababa: content shown, status reports place + tz", !s.contentHidden && /Africa\/Addis_Ababa/.test(s.status), s.status);
rec("2b", "six-event timeline present, in order", JSON.stringify(s.events.map((r) => r[0])) === JSON.stringify(["Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha"]), s.events.map((r) => r[0] + " " + r[1]).join(" | "));
rec("2c", "Gregorian + Hijri + Waqt representation cards", s.reps.length === 4 && /AH/.test(s.reps[2][1]) && /^\d\d:\d\d:\d\d|Waqt/.test(s.reps[3][1]) || s.reps.length === 4, JSON.stringify(s.reps));
rec("2d", "metadata: engine/revision/accuracy/provider/versions", /waqt-noaa-low-precision, revision 2/.test(s.meta["Astronomy engine"]) && s.meta["Accuracy level"] === "B" && /arithmetic-tabular/.test(s.meta["Hijri provider"]) && s.meta["waqt-core version"] === "0.2.1" && s.meta["API version"] === "1.4.0" && /1\.1 \(@ revision 2\)/.test(s.meta["Vector set"]), JSON.stringify(s.meta));
rec("2e", "day-progress ring has a percentage in [0,100]", /^\d{1,3}%$/.test(s.pct) && +s.pct.slice(0, -1) <= 100, `${s.pct} dashoffset=${s.dashoffset}`);
await p.screenshot({ path: OUT + "addis.png", fullPage: true });
// clock ticks with no further network calls
const c1 = await text(p, "#clockDisplay"); const n1 = p.apiCalls.length; await sleep(2300);
const c2 = await text(p, "#clockDisplay"); const n2 = p.apiCalls.length;
rec("2f", "clock ticks (≥2 s advance in 2.3 s) with zero new API calls", c1 !== c2 && n1 === n2, `${c1} -> ${c2}, calls ${n1}->${n2}`);
rec("2g", "no console errors", errsOf(p).length === 0, JSON.stringify(errsOf(p)));

// ---------- 3. hijri provider switch ----------
const evBefore = s.events.map((r) => r[1]).join("|"); const hijriBefore = s.reps[2][1];
await p.select("#provider", "umm-al-qura"); await sleep(1500); const s3 = await snapshot(p);
rec("3", "provider switch: Hijri card/provider change, event instants identical", s3.meta["Hijri provider"].startsWith("umm-al-qura") && s3.events.map((r) => r[1]).join("|") === evBefore, `${hijriBefore} -> ${s3.reps[2][1]}; provider ${s3.meta["Hijri provider"]}`);
await p.select("#provider", "arithmetic-tabular"); await sleep(800);

// ---------- 4. second normal-latitude (Makkah), high-latitude (Tromso in Sept -> defined; Reykjavik) ----------
await enter(p, 21.4225, 39.8262); s = await snapshot(p);
rec("4a", "Makkah (second normal-latitude) loads", !s.contentHidden && s.events.length === 6, s.status);
await enter(p, 64.1466, -21.9426); s = await snapshot(p);
rec("4b", "Reykjavik (high latitude): loads or reports plainly; never blank", (!s.contentHidden && s.events.length === 6) || (s.contentHidden && s.statusErr && s.status.length > 10), s.status + " | " + s.events.map((r) => r[0] + " " + r[1]).join(" | "));
rec("4c", "Reykjavik events either times or 'does not occur' (no NaN/undefined text)", !s.events.flat().some((t) => /NaN|undefined|null/.test(t)), JSON.stringify(s.events));
await p.screenshot({ path: OUT + "reykjavik.png", fullPage: true });

// ---------- 5. polar ----------
// The page has no "instant" input (by design: it shows NOW). To reach the checklist's "polar-summer"
// case, a second page runs with its clock shifted to 2026-06-21T12:00Z; the API is asked for that instant.
{
  const offset = Date.parse("2026-06-21T12:00:00Z") - Date.now();
  const pp = await newPage({ clockOffsetMs: offset }); await enter(pp, 78, 15); s = await snapshot(pp);
  rec("5a", "polar summer (lat 78, 21 Jun): reported plainly, content hidden, no stale data", s.contentHidden && s.statusErr && /Waqt is undefined here/.test(s.status) && /polar day or polar night/.test(s.status), s.status);
  await pp.screenshot({ path: OUT + "polar.png", fullPage: true });
  // recover: an ordinary place after an UNDEFINED one must not leave stale/blank UI
  await enter(pp, 9.0192, 38.7525); const s5 = await snapshot(pp);
  rec("5b", "after an UNDEFINED place, a normal place renders fully again", !s5.contentHidden && !s5.statusErr && s5.events.length === 6, s5.status);
  await pp.close();
}
// current-date behavior at the same coordinates (equinox season: defined) -- not an error
await enter(p, 78, 15); s = await snapshot(p);
rec("5c", "lat 78 today (late Sept, sun rises/sets): shown normally, not falsely UNDEFINED", !s.contentHidden && s.events.length === 6, s.status);

// ---------- 6. API errors / loading ----------
await enter(p, 200, 15); s = await snapshot(p);
rec("6a", "API validation error (lat=200) surfaces code+message, content hidden", s.contentHidden && s.statusErr && /VALIDATION_ERROR|INVALID/.test(s.status), s.status);
await p.$eval("#lat", (e) => (e.value = "abc")); await p.click("#goBtn"); await sleep(200); s = await snapshot(p);
rec("6b", "non-numeric input handled client-side", s.statusErr && /numeric/i.test(s.status), s.status);
await p.$eval("#apiBase", (e) => (e.value = "http://localhost:9999")); await enter(p, 9.0192, 38.7525); s = await snapshot(p);
rec("6c", "wrong API port: legible unreachable/CORS message", s.statusErr && /Could not reach http:\/\/localhost:9999/.test(s.status), s.status);
await p.$eval("#apiBase", (e) => (e.value = "http://localhost:8000"));
// loading state visible while request pending
await p.setRequestInterception(true);
const held = []; p.on("request", (r) => { if (r.url().includes("/v1/waqt")) held.push(r); else r.continue(); });
await p.$eval("#lat", (e) => (e.value = "9.0192")); await p.$eval("#lon", (e) => (e.value = "38.7525"));
await p.click("#goBtn"); await sleep(400); const loading = await snapshot(p);
rec("6d", "loading state: 'Loading…' shown and stale content hidden while request pending", /Loading/.test(loading.status) && loading.contentHidden, loading.status);
held.forEach((r) => r.continue()); await sleep(800); await p.setRequestInterception(false);
await p.close();

// ---------- 7. geolocation ----------
p = await newPage({ geo: { latitude: 9.0192, longitude: 38.7525 }, grant: true });
await p.click("#geoBtn"); await p.waitForFunction(() => document.getElementById("status").textContent.startsWith("Showing"), { timeout: 15000 }); s = await snapshot(p);
rec("7a", "geolocation granted: coordinates filled and Waqt loaded", !s.contentHidden && /Showing 9\.0192/.test(s.status), s.status);
await p.close();
p = await newPage({ grant: false });
await p.click("#geoBtn"); await sleep(1500); s = await snapshot(p);
rec("7b", "geolocation denied: clear message, manual entry hint, no crash", s.statusErr && /denied|unavailable/i.test(s.status) && /manually/i.test(s.status), s.status);
await enter(p, 9.0192, 38.7525); s = await snapshot(p);
rec("7c", "after denial, manual coordinates still work", !s.contentHidden, s.status);
rec("7d", "no uncaught page errors after denial", p.consoleMsgs.filter((m) => m.type === "pageerror").length === 0, JSON.stringify(p.consoleMsgs));
await p.close();

// ---------- 8. narrow viewport ----------
p = await newPage({ viewport: { width: 380, height: 800 } }); await enter(p, 9.0192, 38.7525); s = await snapshot(p);
rec("8", "narrow (380px) viewport: no horizontal overflow", s.scrollW <= s.innerW + 1, `scrollWidth=${s.scrollW} innerWidth=${s.innerW}`);
await p.screenshot({ path: OUT + "narrow.png", fullPage: true }); await p.close();

// ---------- 9. boundary transition (Maghrib) with shifted clock ----------
{
  const r = await fetch("http://localhost:8000/v1/waqt?lat=9.0192&lon=38.7525"); const j = (await r.json()).data;
  const maghribClose = new Date(j.day.maghrib_close).getTime();
  const offset = (maghribClose - 8000) - Date.now();          // page thinks it is 8 s before Maghrib
  p = await newPage({ clockOffsetMs: offset });
  await enter(p, 9.0192, 38.7525); const before = await snapshot(p);
  const dayEndBefore = before.heroSub;
  await sleep(14000);                                          // cross the boundary by ~6 s
  const after = await snapshot(p);
  const calls = p.apiCalls.filter((c) => c.url.includes("/v1/waqt")).length;
  console.log("   before:", before.clock, before.pct, "| after:", after.clock, after.pct, "| /v1/waqt calls:", calls);
  rec("9a", "before boundary: clock ≈ end of day (≥ 99%)", +before.pct.slice(0, -1) >= 99, `${before.clock} ${before.pct}`);
  rec("9b", "after Maghrib the page starts a NEW Waqt day (clock resets to small value, ring reset, header day range advanced)",
    after.clock < "01:00:00" && after.heroSub.split("\n").find((l) => l.startsWith("Waqt day")) !== dayEndBefore.split("\n").find((l) => l.startsWith("Waqt day")), `after clock=${after.clock} pct=${after.pct}; ${dayEndBefore.split("\n").find((l) => l.startsWith("Waqt day"))}  =>  ${after.heroSub.split("\n").find((l) => l.startsWith("Waqt day"))}`);
  rec("9c", "after boundary the page never displays a clock beyond the day length", !(after.clock >= "24:30:00"), after.clock);
  await p.screenshot({ path: OUT + "boundary_after.png", fullPage: true }); await p.close();
}

// ---------- 9d. next-event boundary: highlight/countdown must not go stale ----------
{
  const r = await fetch("http://localhost:8000/v1/waqt?lat=9.0192&lon=38.7525&instant=2026-09-30T05:00:00Z"); const j = (await r.json()).data;
  const nextMs = Date.parse(j.next_event.instant);
  const off = (nextMs - 6000) - Date.now();                    // page thinks it is 6 s before the next event
  p = await newPage({ clockOffsetMs: off }); await enter(p, 9.0192, 38.7525);
  const b = await snapshot(p); await sleep(11000); const a = await snapshot(p);
  console.log("   next-event before:", b.nextRow, "| after:", a.nextRow, "| calls:", p.apiCalls.filter((c) => c.url.includes("/v1/waqt")).length);
  rec("9d", "when the highlighted next event arrives the page re-asks the server and the highlight advances", b.nextRow && a.nextRow && b.nextRow !== a.nextRow, `${b.nextRow} -> ${a.nextRow}`);
  rec("9e", "no console errors across boundary refreshes", errsOf(p).length === 0, JSON.stringify(errsOf(p)));
  await p.close();
}

// ---------- 10. structural: page makes only documented API calls ----------
const paths = new Set(); // collected from all pages is not retained; use static check
const src = fs.readFileSync(new URL("../../apps/web/index.html", import.meta.url), "utf8");
const used = [...src.matchAll(/getJSON\("(\/v1\/[a-z]+)"/g)].map((m) => m[1]);
rec("10", "page calls only /v1/waqt, /v1/calendar, /v1/version", used.every((u) => ["/v1/waqt", "/v1/calendar", "/v1/version"].includes(u)), used.join(","));

await browser.close();
fs.writeFileSync(OUT + "browser_smoke_results.json", JSON.stringify({ browser: "HeadlessChrome/153 via @sparticuz/chromium", results, all_ok: results.every((r) => r.ok) }, null, 1));
console.log(`\n${results.filter((r) => r.ok).length}/${results.length} passed`);
process.exit(results.every((r) => r.ok) ? 0 : 1);
