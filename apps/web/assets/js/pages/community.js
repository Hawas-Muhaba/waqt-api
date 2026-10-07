/* Community page: render configured external links; empty lists say so honestly. */
(function () {
  "use strict";
  const L = (window.WAQT_CONFIG && window.WAQT_CONFIG.links) || {};
  const esc = (v) => String(v).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  function fill(id, items, emptyText) {
    const ul = document.getElementById(id); if (!ul) return;
    ul.innerHTML = items && items.length
      ? items.map((i) => `<li><a href="${esc(i.url)}" rel="noopener" target="_blank">${esc(i.name)}</a>${i.author ? " · " + esc(i.author) : ""}${i.note ? " — " + esc(i.note) : ""}</li>`).join("")
      : `<li><span class="link-pending" title="Not configured yet — see assets/js/config.js">${esc(emptyText)}</span></li>`;
  }
  fill("links-official", L.officialApps, "None listed yet");
  fill("links-community", L.communityApps, "None listed yet");
  fill("links-sdk", L.sdkRepos, "Repository links not configured yet");
  fill("links-pkg", L.packageRegistries, "Registry pages not configured yet");
})();
