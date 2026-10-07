/* API page: real status check (/v1/health, /v1/version) + example request text. No demo data here: either the API
   answers or we say it did not. */
(function () {
  "use strict";
  const W = window.Waqt, esc = (v) => String(v).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const base = W.apiBase();
  const pre = document.getElementById("api-snippet");
  let lang = "curl";
  const draw = () => { pre.textContent = W.exampleSnippet(lang, base, 9.0192, 38.7525); };
  document.querySelectorAll(".tabs [data-tab]").forEach((b) => b.addEventListener("click", () => {
    lang = b.dataset.tab; document.querySelectorAll(".tabs [data-tab]").forEach((x) => x.setAttribute("aria-selected", String(x === b))); draw();
  }));
  draw();

  const out = document.getElementById("api-status");
  async function check() {
    out.textContent = `Checking ${base} … (a free host can take up to a minute to wake)`;
    try {
      const [health, version] = await Promise.all([W.getJSON("/v1/health", {}).catch((e) => { throw e; }), W.getJSON("/v1/version", {}).catch(() => null)]);
      const h = health || {};
      out.innerHTML = `<span class="badge live">REACHABLE</span> <code>${esc(base)}</code> · status <b>${esc(h.status || "?")}</b>` +
        (version ? ` · API ${esc(version.api_version)} · waqt-core ${esc(version.waqt_core_version)}` : "") +
        (h.computation ? ` · engine ${esc(h.computation.engine)} (accuracy ${esc(h.computation.accuracy_level)})` : "");
    } catch (e) {
      out.innerHTML = `<span class="badge demo">NOT REACHABLE</span> ${esc(e.message)} <button type="button" class="btn ghost small" id="api-retry">Check again</button>`;
      const r = document.getElementById("api-retry"); if (r) r.addEventListener("click", check);
    }
  }
  check();
})();
