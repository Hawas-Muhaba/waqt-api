/* Governance: project role information is read from WAQT_CONFIG.maintainers (demo, editable). It is deliberately
   separate from the decision records and the ratification status, which are not derived from this data. */
(function () {
  "use strict";
  const C = window.WAQT_CONFIG, m = C.maintainers;
  const esc = (v) => String(v).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  const el = document.getElementById("gov-roles");
  if (!el || !m) return;
  const tile = (label, name, text) => `<article class="bg-surface-container-low p-6"><p class="font-label-sm text-[11px] tracking-[0.12em] uppercase text-primary-container">${esc(label)}</p><h3 class="mt-3 font-headline-md text-[22px]">${name}</h3><p class="mt-2 text-body-md text-on-surface-variant">${esc(text)}</p></article>`;
  el.innerHTML = m.roles.map((r) => tile(r.role, esc(r.name), r.role.indexOf("Idea") >= 0 ? "Originator of the Waqt idea and its logical owner." : "Technical developer and maintainer of the Waqt software.")).join("")
    + tile("Project contact", `<a class="hover:underline" href="mailto:${esc(m.contact)}">${esc(m.contact)}</a>`, "Ideas, proposals, contribution requests and general questions.")
    + tile("Additional experts", "Open", m.experts);
  el.className = "grid md:grid-cols-2 lg:grid-cols-4 gap-6";
})();
