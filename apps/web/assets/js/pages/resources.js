/* Resources hub: rendered entirely from WAQT_CONFIG (the same object the footer and nav use). Nothing here knows a URL.
   Items whose reference has no real URL (status planned / not_published / unavailable) are rendered DISABLED. */
(function () {
  "use strict";
  const W = window.Waqt, C = window.WAQT_CONFIG;
  const esc = (v) => String(v).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  const KIND = { source: "Source", spec: "Specification", conformance: "Conformance", docs: "Documentation", issues: "Issues", tool: "Tool", example: "Example",
                 "app-real": "Application", "app-concept": "Application", "app-future": "Application", page: "Page", contact: "Contact", support: "Support", releases: "Releases", registry: "Package registry" };
  const STATUS = { planned: "PLANNED", not_published: "NOT PUBLISHED", unavailable: "NOT AVAILABLE" };

  function link(label, r, extra) {
    if (r.kind === "disabled") return `<span class="res-off" aria-disabled="true" title="${esc(STATUS[r.status] || r.status)}">${esc(label)}</span> <span class="badge future">${esc(STATUS[r.status] || r.status)}</span>`;
    const ext = r.kind === "link" ? ' target="_blank" rel="noopener"' : "";
    return `<a class="text-primary-container hover:underline" href="${esc(r.url)}"${ext}>${esc(label)}</a>${r.private ? ` <span class="badge concept" title="${esc(C.project.repository.note)}">PRIVATE REPO</span>` : ""}${extra || ""}`;
  }
  const badgeFor = (b) => (b ? ` <span class="badge ${esc(b)}">${esc(b.toUpperCase())}</span>` : "");

  function itemRow(it) {
    const r = W.resolveRef(it.ref, C);
    return `<li class="flex flex-wrap items-baseline gap-x-3 gap-y-1 py-3 border-b border-outline-variant/30"><span class="font-label-sm text-[11px] uppercase tracking-wider text-on-surface-variant w-28 shrink-0">${esc(KIND[it.kind] || it.kind)}</span><span class="flex-1 min-w-[220px]">${link(it.label, r, badgeFor(it.badge))}${it.note ? `<span class="block text-[12px] text-on-surface-variant">${esc(it.note)}</span>` : ""}</span></li>`;
  }

  function sdkTable() {
    return C.sdks.map((s) => {
      const row = (k, label, ref, name) => { const r = W.resolveRef(ref, C); return `<tr><th scope="row" class="whitespace-nowrap">${esc(k)}</th><td>${link(label, r)}${name ? ` <span class="text-on-surface-variant">${esc(name)}</span>` : ""}</td></tr>`; };
      return `<article class="bg-surface-container-low p-5"><div class="flex flex-wrap items-baseline justify-between gap-2"><h3 class="font-headline-sm text-[16px]">${esc(s.name)}</h3><span class="font-label-sm text-[11px] text-on-surface-variant">package <b class="text-on-surface">${esc(s.package)}</b> · source version ${esc(s.version)}</span></div>
        <div class="table-scroll mt-3"><table class="data"><caption class="vh">${esc(s.name)} locations</caption><tbody>
        ${row("Source", "Repository folder", s.source)}${row("Releases", "GitHub Releases", s.releases)}${row("Package registry", s.registry.name || "Registry", s.registry)}${row("Documentation", "SDK README", s.docs)}
        </tbody></table></div></article>`;
    }).join("");
  }

  function section(sec, i) {
    const body = sec.sdk ? `<div class="grid md:grid-cols-2 gap-6">${sdkTable()}</div>` : `<ul class="list-none p-0 m-0 bg-surface-container-low px-5">${sec.items.map(itemRow).join("")}</ul>`;
    return `<section aria-labelledby="hub-${esc(sec.id)}"><p class="font-label-sm text-[11px] tracking-[0.18em] uppercase text-primary-container mb-2">${String(i + 1).padStart(2, "0")}</p><h2 id="hub-${esc(sec.id)}" class="font-headline-md text-[26px]">${esc(sec.title)}</h2>${sec.intro ? `<p class="mt-2 mb-4 text-body-md text-on-surface-variant max-w-3xl">${esc(sec.intro)}</p>` : '<div class="mb-4"></div>'}${body}</section>`;
  }

  const hub = document.getElementById("hub");
  if (hub) hub.innerHTML = C.resources.map(section).join("");
  const note = document.querySelector("[data-repo-note]");
  if (note) { if (C.project.repository.visibility === "private") note.textContent = C.project.repository.note; else note.hidden = true; }

  /* live version axes from GET /v1/version (no demo data: either the API answers or we say it did not) */
  const body = document.getElementById("ver-body");
  async function load() {
    body.textContent = "Checking the API …";
    try {
      const v = await W.getJSON("/v1/version", {});
      body.innerHTML = `<span class="badge live">LIVE</span><dl class="kv mt-3">` + Object.entries(v).filter(([, x]) => typeof x !== "object").map(([k, x]) => `<dt>${esc(k)}</dt><dd class="mono">${esc(x)}</dd>`).join("") + `</dl>`;
    } catch (e) { body.innerHTML = `<span class="badge demo">NOT REACHABLE</span> ${esc(e.message)} <button class="btn ghost small" id="ver-retry" type="button">Retry</button>`; const r = document.getElementById("ver-retry"); if (r) r.addEventListener("click", load); }
  }
  if (body) load();
})();
