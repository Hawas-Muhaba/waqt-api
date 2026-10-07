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
    doc.querySelectorAll("[data-api-docs]").forEach((a) => { a.setAttribute("href", W.apiBase() + "/docs"); });
    doc.querySelectorAll("[data-openapi]").forEach((a) => { a.setAttribute("href", W.apiBase() + "/openapi.json"); });
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

  function init() { applyLinks(); navToggle(); }
  if (doc.readyState === "loading") doc.addEventListener("DOMContentLoaded", init); else init();
})(typeof window !== "undefined" ? window : globalThis);
