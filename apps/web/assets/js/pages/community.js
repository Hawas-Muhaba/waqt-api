/* Community page: lists come from WAQT_CONFIG (officialApps, communityApps, sdks, packages); empty lists say so honestly. */
(function () {
  "use strict";
  const W = window.Waqt, C = window.WAQT_CONFIG;
  const esc = (v) => String(v).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  const pending = (t) => `<li><span class="link-pending" title="Nothing to list yet">${esc(t)}</span></li>`;
  function apps(id, items, empty) {
    const ul = document.getElementById(id); if (!ul) return;
    ul.innerHTML = items.length ? items.map((i) => { const r = W.resolveRef(i.ref, C); return `<li>${r.kind === "disabled" ? esc(i.name) : `<a class="text-primary-container hover:underline" href="${esc(r.url)}" target="_blank" rel="noopener">${esc(i.name)}</a>`}${i.author ? " · " + esc(i.author) : ""}${i.note ? " — " + esc(i.note) : ""}</li>`; }).join("") : pending(empty);
  }
  apps("links-official", C.officialApps, "None listed yet");
  apps("links-community", C.communityApps, "None listed yet");
  const sdk = document.getElementById("links-sdk");
  if (sdk) sdk.innerHTML = C.sdks.map((s) => { const r = W.resolveRef(s.source, C); return `<li>${r.kind === "disabled" ? esc(s.name) : `<a class="text-primary-container hover:underline" href="${esc(r.url)}" target="_blank" rel="noopener">${esc(s.name)} — source</a>`}</li>`; }).join("");
  const pkg = document.getElementById("links-pkg");
  if (pkg) {
    const pkgs = C.packages || [];
    if (pkgs.length) {
      pkg.innerHTML = pkgs.map((p) =>
        `<li><span class="text-on-surface-variant font-label-sm">${esc(p.registry)}</span> &middot; <a class="text-primary-container hover:underline" href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.name)}</a></li>`
      ).join("");
    } else {
      pkg.innerHTML = pending("None published yet");
    }
  }
})();
