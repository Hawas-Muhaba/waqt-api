import { JSDOM } from "jsdom";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
const WEB = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
export const read = (rel) => fs.readFileSync(path.join(WEB, rel), "utf8");
const SCRIPTS = ["config", "waqt-api", "demo-data", "waqt-live", "waqt-clock", "waqt-widgets", "site"];

/* Load a real page's HTML with the real site scripts into jsdom (no network: fetch is injected per test). */
export function loadPage(file = "index.html", { url = "https://example.test/" + file, online = true, extra = [], fetchImpl = null } = {}) {
  const html = read(file).replace(/<script[^>]*src="[^"]*"[^>]*><\/script>/g, "");
  const dom = new JSDOM(html, { url, runScripts: "outside-only", pretendToBeVisual: true });
  const w = dom.window;
  if (!online) Object.defineProperty(w.navigator, "onLine", { value: false, configurable: true });
  if (fetchImpl) w.fetch = fetchImpl;
  for (const s of SCRIPTS.concat(extra)) w.eval(read(`assets/js/${s}.js`));
  w.document.dispatchEvent(new w.Event("DOMContentLoaded"));
  return dom;
}

const DEMO = () => { const w = new JSDOM("", { runScripts: "outside-only" }).window; w.eval(read("assets/js/demo-data.js")); return JSON.parse(JSON.stringify(w.WAQT_DEMO)); };
export const demo = DEMO;

export const okEnvelope = (data) => ({ ok: true, status: 200, json: async () => ({ meta: { api_version: "test" }, data, error: null }) });
export const errEnvelope = (code, message, status = 400) => ({ ok: false, status, json: async () => ({ meta: {}, data: null, error: { code, message, details: {} } }) });
export const tick = (ms = 0) => new Promise((r) => setTimeout(r, ms));
