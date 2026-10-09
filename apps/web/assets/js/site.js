/* Waqt Web — site chrome behaviour. Markup for nav/footer is in each page (so it works without JS); this file
 *  - collapses the nav on small screens (progressive enhancement: html.js),
 *  - resolves every configured link from WAQT_CONFIG (via Waqt.resolveCfg): unconfigured/planned ones are rendered
 *    DISABLED, never as guessed links,
 *  - fills maintainer metadata and mailto links from the same configuration,
 *  - offers Waqt.bindLive / Waqt.bindFields so pages wire live data in one line.
 */
(function (root) {
  "use strict";
  const W = (root.Waqt = root.Waqt || {});
  const CFG = root.WAQT_CONFIG || {};
  const doc = root.document;
  if (!doc) return;
  doc.documentElement.classList.add("js");

  const LEGACY = { github: "@repo", docs: "docs.index", spec: "docs.spec", issues: "@issues", support: "@support", buyMeACoffee: "@support" };

  function disable(a, why) {
    a.removeAttribute("href"); a.setAttribute("aria-disabled", "true"); a.setAttribute("role", "link");
    a.setAttribute("title", why || "Not available yet"); a.classList.add("pending");
  }

  function applyLinks() {
    doc.querySelectorAll("[data-cfg], [data-link]").forEach((a) => {
      const key = a.getAttribute("data-cfg") || LEGACY[a.getAttribute("data-link")];
      const r = key && W.resolveCfg ? W.resolveCfg(key, CFG) : { kind: "disabled", status: "unavailable" };
      if (r.kind === "disabled") { disable(a, r.status === "planned" ? "Planned — not available yet" : r.status === "not_published" ? "Not published yet" : "Not configured yet — see assets/js/config.js"); return; }
      a.setAttribute("href", r.url); a.removeAttribute("aria-disabled"); a.classList.remove("pending");
      if (r.kind === "link") { a.setAttribute("rel", "noopener"); a.setAttribute("target", "_blank"); }
      if (r.private) a.setAttribute("title", CFG.project.repository.note);
    });
    const mail = `mailto:${CFG.contactEmail}?subject=${encodeURIComponent(CFG.ideaSubject || "Waqt idea")}`;
    doc.querySelectorAll("[data-idea]").forEach((a) => a.setAttribute("href", mail));
    doc.querySelectorAll("[data-email]").forEach((a) => { a.textContent = CFG.contactEmail; a.setAttribute("href", "mailto:" + CFG.contactEmail); });
    const m = CFG.maintainers;
    if (m) {
      doc.querySelectorAll("[data-maintainers]").forEach((el) => { el.textContent = m.roles.map((r) => `${r.role}: ${r.name}`).join(" · ") + " (demo metadata)"; });
      doc.querySelectorAll("[data-maint-notice]").forEach((el) => { el.textContent = m.notice; });
    }
    const g = CFG.governance;
    if (g) doc.querySelectorAll("[data-ratification]").forEach((el) => { el.textContent = g.ratificationLabel; });
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

  /* Generic field binder: any element with data-bind="key" shows a live value from the store. Values are read from the
     API model; nothing is computed here. The Hijri date is ALWAYS shown with its provider (never a bare date). */
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
      set("provider", m.hijri ? m.hijri.provider : "—");
      set("hijriWithProvider", m.hijri ? `${m.hijri.display} · ${m.hijri.provider}` : "unavailable");
      set("tz", m.tzName); set("lat", m.location && m.location.lat); set("lon", m.location && m.location.lon);
      set("elevation", m.location && m.location.elevation_m != null ? m.location.elevation_m + " m" : "—");
      set("engine", c.engine); set("accuracy", c.accuracy_level); set("deltaT", c.delta_t_seconds != null ? c.delta_t_seconds + " s" : "—");
      set("timescale", c.timescale_model);
      set("hijriNote", CFG.hijri ? CFG.hijri.ambiguityNote : "");
    } };
  };

  function init() { applyLinks(); navToggle(); }
  if (doc.readyState === "loading") doc.addEventListener("DOMContentLoaded", init); else init();
})(typeof window !== "undefined" ? window : globalThis);
