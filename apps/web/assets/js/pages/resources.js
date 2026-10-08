/* Resources: live version axes from GET /v1/version (no demo data: either the API answers or we say it did not). */
(function () {
  "use strict";
  const W = window.Waqt, esc = (v) => String(v).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"), body = document.getElementById("ver-body");
  async function load() {
    body.textContent = "Checking the API …";
    try {
      const v = await W.getJSON("/v1/version", {});
      body.innerHTML = `<span class="badge live">LIVE</span><dl class="kv mt-3">` + Object.entries(v).filter(([, x]) => typeof x !== "object").map(([k, x]) => `<dt>${esc(k)}</dt><dd class="mono">${esc(x)}</dd>`).join("") + `</dl>`;
    } catch (e) { body.innerHTML = `<span class="badge demo">NOT REACHABLE</span> ${esc(e.message)} <button class="btn ghost small" id="ver-retry" type="button">Retry</button>`; const r = document.getElementById("ver-retry"); if (r) r.addEventListener("click", load); }
  }
  load();
})();
