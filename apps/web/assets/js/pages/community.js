/* Community page: lists come from WAQT_CONFIG (officialApps, communityApps, sdks); empty lists say so honestly. */
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
  const pkg = document.getElementById("links-pkg");
  if (pkg) {
    const livePackages = [
      { name: "PyPI", pkg: "waqt-core", ver: "0.7.0", url: "https://pypi.org/project/waqt-core/0.7.0/", desc: "Core time model & vector engine" },
      { name: "PyPI", pkg: "waqt-local", ver: "0.7.0", url: "https://pypi.org/project/waqt-local/0.7.0/", desc: "Offline local engine" },
      { name: "PyPI", pkg: "waqt-api", ver: "0.6.0", url: "https://pypi.org/project/waqt-api/0.6.0/", desc: "FastAPI HTTP service" },
      { name: "PyPI", pkg: "waqt-client", ver: "0.3.1", url: "https://pypi.org/project/waqt-client/0.3.1/", desc: "Python SDK" },
      { name: "PyPI", pkg: "waqt-cli", ver: "0.3.1", status: "publishing next", desc: "Command-line tool" },
      { name: "npm", pkg: "waqt-client", ver: "0.3.1", status: "publishing next", desc: "JavaScript SDK" }
    ];
    pkg.innerHTML = livePackages.map((p) => {
      const linkHtml = p.url
        ? `<a class="text-primary-container hover:underline" href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.name)}: <b>${esc(p.pkg)} ${esc(p.ver)}</b></a>`
        : `<span class="text-on-surface">${esc(p.name)}: <b>${esc(p.pkg)} ${esc(p.ver)}</b></span> <span class="badge future">${esc(p.status)}</span>`;
      return `<li class="py-1">${linkHtml}${p.desc ? ` <span class="text-[12px] text-on-surface-variant block sm:inline sm:ml-2">— ${esc(p.desc)}</span>` : ""}</li>`;
    }).join("");
  }
})();
