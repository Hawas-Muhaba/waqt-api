// Sprint 14: drive apps/web in REAL headless Chrome against the REAL API, with the API's AlAdhan provider
// pointed at verification/fake_aladhan.py (the live service is unreachable from CI/sandbox).
// Like Sprint 13's harness, --disable-web-security & friends are stripped so CORS is genuinely enforced.
// Usage: node run_sprint14.mjs   (expects: API :8000 [WAQT_CORS_ORIGINS=http://localhost:8080,
//        WAQT_ALADHAN_BASE_URL=<fake>], static :8080, fake AlAdhan control on :8099 -- see run_sprint14.sh)
import chromium from "@sparticuz/chromium";
import puppeteer from "puppeteer-core";
import fs from "node:fs";
import { fileURLToPath } from "node:url";

const PAGE = "http://localhost:8080/index.html", API = "http://localhost:8000", CTL = "http://localhost:8099";
const OUT = fileURLToPath(new URL("./results/", import.meta.url)); fs.mkdirSync(OUT, { recursive: true });
const executablePath = process.platform === "win32"
  ? [process.env.CHROME_PATH, "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
      "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
      "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe"]
      .filter(Boolean).find((path) => fs.existsSync(path))
  : await chromium.executablePath();
if (!executablePath) throw new Error("Set CHROME_PATH to a Windows Chrome or Edge executable.");
const results = [];
const rec = (id, name, ok, detail = "") => { results.push({ id, name, ok: !!ok, detail }); console.log(`${ok ? "PASS" : "FAIL"} [${id}] ${name}${detail ? "  — " + detail : ""}`); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const ctl = (mode, extra = "") => fetch(`${CTL}/mode/${mode}${extra}`).then((r) => r.text());

const browser = await puppeteer.launch({ args: chromium.args.filter((a) => !/single-process|no-zygote|disable-web-security|allow-running-insecure|disable-site-isolation|disable-features=/.test(a)).concat(["--no-sandbox"]), executablePath, headless: process.platform === "win32" ? true : "shell" });
console.log("Browser:", await browser.version());

async function newPage({ clockOffsetMs = null, intercept = null } = {}) {
  const ctx = await browser.createBrowserContext(); const page = await ctx.newPage();
  await page.setViewport({ width: 1100, height: 900 });
  page.errs = []; page.waqtCalls = [];
  page.on("pageerror", (e) => page.errs.push(String(e)));
  page.on("console", (m) => { if (m.type() === "error") page.errs.push(m.text()); });
  if (clockOffsetMs !== null) {
    await page.evaluateOnNewDocument((off) => { const RD = Date; const now = () => RD.now() + off;
      class FD extends RD { constructor(...a) { if (a.length === 0) super(now()); else super(...a); } static now() { return now(); } }
      window.Date = FD; }, clockOffsetMs);
  }
  await page.setRequestInterception(true);
  page.on("request", async (req) => {
    const u = new URL(req.url());
    if (u.pathname === "/v1/waqt") {
      page.waqtCalls.push(Date.now());
      if (clockOffsetMs !== null && !u.searchParams.has("instant")) u.searchParams.set("instant", new Date(Date.now() + clockOffsetMs).toISOString().replace(".000Z", "Z"));
      if (intercept) { const r = await intercept(req, page.waqtCalls.length); if (r) return req.respond(r); }
      return req.continue({ url: u.toString() });
    }
    req.continue();
  });
  await page.goto(PAGE, { waitUntil: "networkidle0" });
  return page;
}
async function go(page, lat, lon, provider) {
  if (provider) await page.select("#provider", provider);
  await page.$eval("#lat", (e) => (e.value = "")); await page.$eval("#lon", (e) => (e.value = ""));
  await page.type("#lat", String(lat)); await page.type("#lon", String(lon)); await page.click("#goBtn");
  await page.waitForFunction(() => { const s = document.getElementById("status").textContent; return s && !s.startsWith("Loading") && !s.startsWith("Enter coordinates, or"); }, { timeout: 15000 });
  await sleep(400);
}
const snap = (page) => page.evaluate(() => ({
  status: document.getElementById("status").textContent, statusErr: document.getElementById("status").className === "err",
  hidden: document.getElementById("content").hidden, hero: document.getElementById("heroSub").innerText,
  badge: (document.querySelector("#heroSub .badge") || {}).textContent || null, badgeClass: (document.querySelector("#heroSub .badge") || {}).className || null,
  meta: Object.fromEntries([...document.querySelectorAll("#metaGrid dt")].map((dt) => [dt.textContent, dt.nextElementSibling.textContent])),
  providers: [...document.querySelectorAll("#provider option")].map((o) => o.value), clock: document.getElementById("clockDisplay").textContent,
  reps: [...document.querySelectorAll("#repsGrid .rep-card")].map((c) => c.innerText.replace(/\n+/g, " | ")),
}));

// ---- 1. provider list + live provider shows provenance, CORS enforced ----
await ctl("ok");
let p = await newPage();
let s = await snap(p);
rec("S14-1a", "aladhan is offered in the provider picker (from /v1/calendar)", s.providers.includes("aladhan"), s.providers.join(","));
await go(p, 9.0192, 38.7525, "aladhan"); s = await snap(p);
rec("S14-1b", "live date shows a 'live · aladhan' badge and source=remote in metadata", s.badge === "live · aladhan" && s.meta["Hijri source"] === "remote" && !s.hidden, `${s.badge} / ${s.meta["Hijri source"]}`);
rec("S14-1c", "metadata shows provider version, fetch time, cache state and local cross-check", /aladhan-gToH-v1/.test(s.meta["Hijri provider"]) && /cache (miss|hit)/.test(s.meta["Fetched"] || "") && !!s.meta["Local cross-check"], JSON.stringify([s.meta["Fetched"], s.meta["Local cross-check"]]));
await p.screenshot({ path: OUT + "s14-1-live.png" });
rec("S14-1d", "no page errors / CORS failures on the live path", p.errs.length === 0, p.errs.join(" | "));
await p.close();

// ---- 3. hijri:null + calendar_error must not blank the page (response is a stub: documented) ----
p = await newPage({ intercept: async (req) => {
  const real = await fetch(req.url().replace("http://localhost:8000", API)).then((r) => r.json());
  real.data.hijri = null; real.data.calendar_error = { provider: "umm-al-qura", message: "ValueError: ephemeris range exceeded" };
  return { status: 200, contentType: "application/json", headers: { "access-control-allow-origin": "http://localhost:8080" }, body: JSON.stringify(real) };
} });
await go(p, 9.0192, 38.7525); s = await snap(p);
rec("S14-3a", "hijri:null: page still renders, says Hijri unavailable and why", !s.hidden && /Hijri date unavailable/.test(s.hero) && /ephemeris range exceeded/.test(s.hero) && p.errs.length === 0, s.hero.replace(/\n/g, " / ") + " errs=" + p.errs.join("|"));
rec("S14-3b", "hijri:null: Representations card says unavailable instead of throwing", s.reps.some((r) => /^Hijri \| unavailable/.test(r)), JSON.stringify(s.reps));
await p.close();

// ---- 4. HTML in server-supplied provenance text is not injected into the page ----
p = await newPage({ intercept: async (req) => {
  const real = await fetch(req.url().replace("http://localhost:8000", API)).then((r) => r.json());
  real.data.hijri.source = "local-fallback";
  real.data.hijri.provenance = { requested_provider: "aladhan", fallback_reason: "network-error", fallback_detail: "<img src=x onerror=window.__pwned=1>", cache: null };
  return { status: 200, contentType: "application/json", headers: { "access-control-allow-origin": "http://localhost:8080" }, body: JSON.stringify(real) };
} });
await go(p, 9.0192, 38.7525); await sleep(500);
const pwned = await p.evaluate(() => window.__pwned === 1 || !!document.querySelector("#heroSub img, #metaGrid img"));
rec("S14-4", "markup inside fallback_detail is escaped, not executed", !pwned);
await p.close();

// ---- 5. day transition (real Maghrib crossing) with the live provider ----
const now0 = await fetch(`${API}/v1/waqt?lat=9.0192&lon=38.7525&calendar_provider=aladhan`).then((r) => r.json());
const close = Date.parse(now0.data.day.maghrib_close); const off = close - 9000 - Date.now();
const before = now0.data.hijri;
p = await newPage({ clockOffsetMs: off });
await go(p, 9.0192, 38.7525, "aladhan"); const sBefore = await snap(p);
const callsBefore = p.waqtCalls.length;
await sleep(14000); const sAfter = await snap(p);
rec("S14-5a", "page refreshed itself across Maghrib (extra /v1/waqt call, no polling storm)", p.waqtCalls.length > callsBefore && p.waqtCalls.length - callsBefore <= 3, `calls ${callsBefore} -> ${p.waqtCalls.length}`);
const dayOf = (h) => (h.match(/\d+/) || [])[0];
rec("S14-5b", "Hijri day label stepped at Maghrib and is still a live (remote) value", dayOf(sBefore.hero) !== dayOf(sAfter.hero) && sAfter.badge === "live · aladhan", `${dayOf(sBefore.hero)} -> ${dayOf(sAfter.hero)}; ${sAfter.badge}`);
rec("S14-5c", "clock restarted near 00:00 in the new Waqt day", /^00:00:\d\d$/.test(sAfter.clock), sAfter.clock);
await p.screenshot({ path: OUT + "s14-5-transition.png" }); await p.close();

// ---- 6. day transition while the API rate-limits the refresh: keep last view, back off ----
const off2 = close - 9000 - Date.now();
p = await newPage({ clockOffsetMs: off2, intercept: async (req, n) => {
  if (n >= 2) return { status: 429, contentType: "application/json", headers: { "access-control-allow-origin": "http://localhost:8080", "retry-after": "20" },
    body: JSON.stringify({ meta: {}, data: null, error: { code: "RATE_LIMITED", message: "Rate limit exceeded.", details: { retry_after_seconds: 20 } } }) };
  return null; } });
await go(p, 9.0192, 38.7525, "aladhan"); const c0 = p.waqtCalls.length;
await sleep(14000); s = await snap(p);
rec("S14-6a", "429 on boundary refresh: last good view stays visible with a retry message", !s.hidden && /retrying in 20 s/.test(s.status), s.status);
rec("S14-6b", "429 backoff: no request storm (<=2 retries in 14 s)", p.waqtCalls.length - c0 <= 2, `calls after load: ${p.waqtCalls.length - c0}`);
await p.close();

// (run last: a failure opens the API's circuit breaker for 30 s, which would turn the live scenarios into fallbacks)
// ---- 2. provider failure -> visible fallback, page still fully works ----
await ctl("500");
// 3 days ahead: a date the cache has never seen (cache is per date), so the upstream failure is actually hit
p = await newPage({ clockOffsetMs: 3 * 86400000 }); await go(p, 9.0192, 38.7525, "aladhan"); s = await snap(p);
rec("S14-2a", "upstream 500: fallback is VISIBLE in the headline badge", /^fallback: umm-al-qura instead of aladhan \(upstream-server-error\)$/.test(s.badge || ""), s.badge);
rec("S14-2b", "page still renders events and clock (astronomy unaffected)", !s.hidden && /^\d\d:\d\d:\d\d$/.test(s.clock), s.clock);
rec("S14-2c", "metadata names the fallback reason and requested provider", /upstream-server-error/.test(s.meta["Fallback reason"] || "") && s.meta["Requested provider"] === "aladhan", JSON.stringify([s.meta["Fallback reason"], s.meta["Requested provider"]]));
const evFallback = await p.$$eval("#eventsBody tr", (r) => r.map((x) => x.innerText));
await p.screenshot({ path: OUT + "s14-2-fallback.png" });
// switching provider back and forth keeps the same astronomy
await go(p, 9.0192, 38.7525, "umm-al-qura"); const evLocal = await p.$$eval("#eventsBody tr", (r) => r.map((x) => x.innerText));
rec("S14-2d", "provider switching: event table identical for aladhan(fallback) vs umm-al-qura", JSON.stringify(evFallback.map(t => t.replace(/in \d\d:\d\d:\d\d/, ""))) === JSON.stringify(evLocal.map(t => t.replace(/in \d\d:\d\d:\d\d/, ""))));
await p.close(); await ctl("ok");


await browser.close();
const failed = results.filter((r) => !r.ok);
fs.writeFileSync(OUT + "sprint14-browser-results.json", JSON.stringify({ browser: "HeadlessChrome/153", results }, null, 2));
console.log(`\n${results.length - failed.length}/${results.length} passed`);
process.exit(failed.length ? 1 : 0);
