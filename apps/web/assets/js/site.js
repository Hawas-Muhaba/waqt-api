/* Waqt Web — site chrome behaviour. Markup for nav/footer is in each page (so it works without JS); this file only
 *  - collapses the nav on small screens (progressive enhancement: html.js),
 *  - fills in config-driven external links (WAQT_CONFIG.links) — null means a visibly pending placeholder, never a guess,
 *  - builds the mailto links for "Send an Idea",
 *  - offers Waqt.bindLive(store, [components]) so pages wire live data in one line.
 */
(function (root) {
  "use strict";
  const W = (root.Waqt = root.Waqt || {});
  const CFG = root.WAQT_CONFIG || { links: {} };
  const doc = root.document;
  if (!doc) return;
  doc.documentElement.classList.add("js");

  function applyLinks() {
    doc.querySelectorAll("[data-link]").forEach((a) => {
      const key = a.getAttribute("data-link");
      const url = CFG.links ? CFG.links[key] : null;
      if (url) { a.setAttribute("href", url); a.removeAttribute("aria-disabled"); a.removeAttribute("title"); a.setAttribute("rel", "noopener"); a.setAttribute("target", "_blank"); }
      else if (key === "docs") {                       // no canonical docs URL configured: fall back to our own Resources page
        a.setAttribute("href", a.getAttribute("data-fallback") || "resources.html#specifications");
        a.removeAttribute("target");
      } else {
        a.removeAttribute("href"); a.setAttribute("aria-disabled", "true"); a.setAttribute("role", "link");
        a.setAttribute("title", "URL not configured yet — set it in assets/js/config.js");
        a.classList.add("pending");
        if (a.closest(".nav-list")) a.parentElement.classList.add("nav-pending-item");
      }
    });
    const mail = `mailto:${CFG.contactEmail}?subject=${encodeURIComponent(CFG.ideaSubject || "Waqt idea")}`;
    doc.querySelectorAll("[data-idea]").forEach((a) => a.setAttribute("href", mail));
    doc.querySelectorAll("[data-email]").forEach((a) => { a.textContent = CFG.contactEmail; a.setAttribute("href", "mailto:" + CFG.contactEmail); });
    const base = W.apiBase ? W.apiBase() : null;   // pages without the API client (e.g. the reference viewer) leave these links as-is
    if (base) doc.querySelectorAll("[data-api-docs]").forEach((a) => { a.setAttribute("href", base + "/docs"); });
    if (base) doc.querySelectorAll("[data-openapi]").forEach((a) => { a.setAttribute("href", base + "/openapi.json"); });
  }

  function navToggle() {
    const btn = doc.querySelector(".nav-toggle"), list = doc.getElementById("site-nav");
    if (!btn || !list) return;
    const set = (open) => { list.classList.toggle("open", open); btn.setAttribute("aria-expanded", String(open)); btn.textContent = open ? "Close" : "Menu"; };
    btn.addEventListener("click", () => set(!list.classList.contains("open")));
    doc.addEventListener("keydown", (e) => { if (e.key === "Escape" && list.classList.contains("open")) { set(false); btn.focus(); } });
    list.addEventListener("click", (e) => { if (e.target.closest("a[href]")) set(false); });
  }

  /* Wire a live store to components: re-render on every state change/tick; banner + retry button in `bannerEl`. */
  W.bindLive = function (store, components, bannerEl) {
    const render = (type) => {
      components.forEach((c) => c.update(store));
      if (bannerEl && type !== "tick") {
        bannerEl.innerHTML = W.bannerHtml(store);
        const r = bannerEl.querySelector("[data-retry]"); if (r) r.addEventListener("click", () => store.retryNow());
      }
    };
    store.subscribe(render); render("state"); return store;
  };


  /* Generic field binder: any element with data-bind="key" shows a live value from the store. Used by the Tailwind
     pages so telemetry panels need no bespoke JS. Values are read from the API model; nothing is computed here. */
  W.bindFields = function (rootEl) {
    const set = (k, v) => rootEl.querySelectorAll(`[data-bind="${k}"]`).forEach((el) => { el.textContent = v == null ? "—" : v; });
    return { update(store) {
      const m = store.model, s = m ? store.snapshot() : null, c = m && m.computation ? m.computation : {};
      const badge = store.state === "success" ? "LIVE" : store.state === "loading" ? "LOADING" : store.state === "empty" ? "UNDEFINED" : store.isDemo ? "DEMO · NOT LIVE" : "NO DATA";
      set("state", badge);
      rootEl.querySelectorAll("[data-bind-state]").forEach((el) => el.setAttribute("data-state", store.isDemo ? "demo" : store.state));
      set("latency", store.latencyMs != null && !store.isDemo ? store.latencyMs + " ms" : "—");
      if (!m) return;
      set("reading", s.readingDisplay); set("readingSeconds", Math.floor(s.readingSeconds).toLocaleString("en-US") + " s");
      set("next", m.next ? m.next.label : "—"); set("countdown", s.countdownDisplay || "—");
      set("progress", (s.dayFraction * 100).toFixed(1) + "%");
      set("open", W.localClock(m.day.openIso, m.tzName)); set("close", W.localClock(m.day.closeIso, m.tzName));
      set("length", W.fmtHMS(m.day.lengthSeconds)); set("lengthSeconds", m.day.lengthSeconds + " s");
      set("hijri", m.hijri ? m.hijri.display : "unavailable"); set("weekday", m.weekday);
      set("tz", m.tzName); set("lat", m.location && m.location.lat); set("lon", m.location && m.location.lon);
      set("elevation", m.location && m.location.elevation_m != null ? m.location.elevation_m + " m" : "—");
      set("engine", c.engine); set("accuracy", c.accuracy_level); set("deltaT", c.delta_t_seconds != null ? c.delta_t_seconds + " s" : "—");
      set("timescale", c.timescale_model); set("provider", m.hijri ? m.hijri.provider : "—");
    } };
  };

  function init() { applyLinks(); navToggle(); }
  if (doc.readyState === "loading") doc.addEventListener("DOMContentLoaded", init); else init();
})(typeof window !== "undefined" ? window : globalThis);
