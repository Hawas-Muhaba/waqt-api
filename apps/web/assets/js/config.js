/* Waqt Web — the ONE configuration file. Every external URL, repository path, SDK location, maintainer record and
 * support link used by the site is defined here and nowhere else (the footer, nav, Resources hub and Governance page
 * all read this object). Nothing in HTML or other scripts hard-codes a URL.
 *
 * How references work (resolved by Waqt.resolveRef in waqt-api.js):
 *   { path: "docs/API.md" }       a file in the repository  -> <repo>/blob/<branch>/docs/API.md
 *   { tree: "sdks/python" }       a folder in the repository -> <repo>/tree/<branch>/sdks/python
 *   { repo: true } / { issues: true }   the repository root / its issue tracker
 *   { page: "governance.html" }   a page of this site
 *   { api: "/openapi.json" }      served by the running API (base URL chosen at runtime)
 *   { url: "https://…" }          an external canonical URL (only when it actually exists)
 *   { status: "planned" | "not_published" | "unavailable" }   no URL yet: rendered DISABLED, never as a link
 * Owner-edit workflow: change values here and redeploy; tests/test_site_structure.py verifies that every `path`/`tree`
 * exists in the repository, so a typo cannot ship a dead link. Secrets must never be placed in this file. */
(function () {
  "use strict";
  var contact = "waqtapi@gmail.com";
  window.WAQT_CONFIG = Object.freeze({
    api: Object.freeze({
      localBase: "http://localhost:8000",
      publicBase: "https://waqt-api-r6e0.onrender.com",
      storageKey: "waqt:apiBase",
      requestTimeoutMs: 25000
    }),

    /* Hijri display. The API default is umm-al-qura (since API 1.7.0; arithmetic-tabular stays selectable). The WEB still sends the provider EXPLICITLY, so what it shows never depends on a server default, and it chooses which provider to
       REQUEST and always shows the provider name next to the date; it never hard-codes a date. */
    hijri: Object.freeze({
      defaultProvider: "umm-al-qura",
      ambiguityNote: "Hijri dates depend on the calendar convention. Waqt shows Umm al-Qura by default: a deliberate project choice, not a claim that every community follows it. Another provider (for example arithmetic-tabular) can legitimately show a different day for the same moment; the Waqt time itself does not change."
    }),

    contactEmail: contact,
    ideaSubject: "Waqt idea / proposal",

    project: Object.freeze({
      repository: Object.freeze({
        url: "https://github.com/Hawas-Muhaba/waqt-api",   // PRIVATE for now; becomes public later. Same URL, no change needed.
        branch: "main",
        visibility: "private",
        note: "Private repository until public release: these links open only for authorised GitHub users."
      }),
      support: Object.freeze({ name: "Ko-fi", url: "https://ko-fi.com/ummatidawah" })
    }),

    /* DEMO / EDITABLE project metadata. This is role information, NOT governance ratification. */
    maintainers: Object.freeze({
      status: "demo",
      editable: true,
      notice: "Demo metadata — editable before public release. Listing a role here is not a governance approval or ratification.",
      roles: Object.freeze([
        Object.freeze({ role: "Logical / Idea Owner", name: "Dr. Salim Muhammed Redi" }),
        Object.freeze({ role: "Technical Developer / Maintainer", name: "Mr. Hawas Muhaba Hussein" })
      ]),
      contact: contact,
      experts: "Open to expert contributors and reviewers."
    }),

    /* Formal governance state — kept separate from the role metadata above. It mirrors the decision records in
       conformance/decisions (DR-0001..DR-0009 record ratification by the named Maintainer, 2026-10-10; no signed
       artifact is held in the repository). The CONTRACT is still an unreleased 2.0.0: ratified records are not a release. */
    governance: Object.freeze({
      ratification: "decision-records-ratified",
      ratificationLabel: "Decision records ratified · contract not yet released",
      contractReleased: false,
      decisionRecords: Object.freeze({ tree: "conformance/decisions" }),
      process: Object.freeze({ path: "conformance/GOVERNANCE.md" }),
      maintainerRegister: Object.freeze({ path: "conformance/MAINTAINERS.md" })
    }),

    docs: Object.freeze({
      index:       Object.freeze({ tree: "docs" }),
      api:         Object.freeze({ path: "docs/API.md" }),
      openapi:     Object.freeze({ api: "/openapi.json" }),
      interactive: Object.freeze({ api: "/docs" }),
      spec:        Object.freeze({ path: "docs/TIME-MODEL.md" }),
      semantics:   Object.freeze({ path: "docs/SEMANTICS.md" }),
      calendars:   Object.freeze({ path: "docs/CALENDARS.md" }),
      astronomy:   Object.freeze({ path: "docs/ASTRONOMY.md" }),
      conformance: Object.freeze({ path: "conformance/spec/CONFORMANCE.md" }),
      sdk:         Object.freeze({ path: "docs/SDK.md" }),
      changelog:   Object.freeze({ path: "conformance/CHANGELOG.md" }),   // the conformance-contract changelog
      releaseNotes: Object.freeze({ status: "planned" }),                  // no API/SDK release notes exist yet
      contributing: Object.freeze({ path: "CONTRIBUTING.md" })
    }),

    /* SDK locations. Source / Releases / Package registry / Documentation are described SEPARATELY. Nothing is
       published yet, so releases and registries are not links. When publication happens, replace the status object
       with { url: "<real canonical URL>" } — never before. Canonical hierarchy: repository → GitHub Releases →
       package registries → this site (which links, and never hosts archives). */
    sdks: Object.freeze([
      Object.freeze({
        id: "python", name: "Python SDK", package: "waqt-client", version: "0.3.1",
        source: Object.freeze({ tree: "sdks/python" }),
        docs: Object.freeze({ path: "sdks/python/README.md" }),
        releases: Object.freeze({ status: "planned" }),               // intended: GitHub Releases of the repository
        registry: Object.freeze({ name: "PyPI", status: "not_published" })
      }),
      Object.freeze({
        id: "javascript", name: "JavaScript SDK", package: "waqt-client", version: "0.3.1",
        source: Object.freeze({ tree: "sdks/js/waqt-client" }),
        docs: Object.freeze({ path: "sdks/js/waqt-client/README.md" }),
        releases: Object.freeze({ status: "planned" }),
        registry: Object.freeze({ name: "npm", status: "not_published" })
      })
    ]),

    officialApps: Object.freeze([]),     // [{ name, ref, note }] — add only when a real application exists
    communityApps: Object.freeze([]),    // [{ name, ref, note, author }]

    /* The Resources hub, in display order. Buy-me-a-coffee style support is deliberately last. */
    resources: Object.freeze([
      Object.freeze({ id: "core", title: "Waqt Core", intro: "The computation layer, the specification and the conformance contract.", items: Object.freeze([
        Object.freeze({ kind: "source", label: "Source repository", ref: { repo: true }, note: "core/, local/, waqt/ and the web app" }),
        Object.freeze({ kind: "spec", label: "Specification — the Waqt time model", ref: { path: "docs/TIME-MODEL.md" } }),
        Object.freeze({ kind: "spec", label: "Time and calendar semantics", ref: { path: "docs/SEMANTICS.md" } }),
        Object.freeze({ kind: "conformance", label: "Conformance specification", ref: { path: "conformance/spec/CONFORMANCE.md" }, note: "contract 2.0.0 — draft, not released" }),
        Object.freeze({ kind: "conformance", label: "Conformance vectors", ref: { tree: "conformance/vectors" } })
      ]) }),
      Object.freeze({ id: "api", title: "API", intro: "The HTTP contract.", items: Object.freeze([
        Object.freeze({ kind: "docs", label: "API documentation (Markdown)", ref: { path: "docs/API.md" } }),
        Object.freeze({ kind: "docs", label: "Interactive API docs (running API)", ref: { api: "/docs" } }),
        Object.freeze({ kind: "docs", label: "OpenAPI document (running API)", ref: { api: "/openapi.json" } }),
        Object.freeze({ kind: "source", label: "API repository", ref: { repo: true } }),
        Object.freeze({ kind: "issues", label: "Issue tracker", ref: { issues: true } })
      ]) }),
      Object.freeze({ id: "sdks", title: "SDKs", intro: "Source, releases, package registries and documentation are separate things. Nothing is published yet.", sdk: true, items: Object.freeze([]) }),
      Object.freeze({ id: "developer", title: "Developer resources", intro: "Tools and consumers that exist in the repository.", items: Object.freeze([
        Object.freeze({ kind: "tool", label: "Command-line tool (offline)", ref: { tree: "apps/cli" } }),
        Object.freeze({ kind: "example", label: "API consumer (Python)", ref: { tree: "apps/api-consumer" } }),
        Object.freeze({ kind: "example", label: "JavaScript consumers", ref: { tree: "consumers/js" } }),
        Object.freeze({ kind: "conformance", label: "Conformance vectors", ref: { tree: "conformance/vectors" } }),
        Object.freeze({ kind: "docs", label: "Hijri provider guide", ref: { path: "docs/CALENDARS.md" } })
      ]) }),
      Object.freeze({ id: "applications", title: "Applications", intro: "Only the reference viewer is a working application. Everything else is labelled.", items: Object.freeze([
        Object.freeze({ kind: "app-real", label: "Reference viewer (minimal API proof page)", ref: { page: "reference-viewer.html" }, badge: "real" }),
        Object.freeze({ kind: "app-real", label: "Live demo", ref: { page: "live-demo.html" }, badge: "real" }),
        Object.freeze({ kind: "app-concept", label: "Mosque clock, watch, mobile, institutional calendar, dashboard", ref: { page: "applications.html" }, badge: "concept" }),
        Object.freeze({ kind: "app-future", label: "Smart home, public displays, research, wearables", ref: { page: "applications.html" }, badge: "future" })
      ]) }),
      Object.freeze({ id: "community", title: "Community", intro: "", items: Object.freeze([
        Object.freeze({ kind: "source", label: "GitHub", ref: { repo: true } }),
        Object.freeze({ kind: "docs", label: "Contribution guide", ref: { path: "CONTRIBUTING.md" } }),
        Object.freeze({ kind: "page", label: "Governance", ref: { page: "governance.html" } }),
        Object.freeze({ kind: "contact", label: "Contact", ref: { mailto: contact } })
      ]) }),
      Object.freeze({ id: "support", title: "Support", intro: "Optional. Never the primary call to action.", items: Object.freeze([
        Object.freeze({ kind: "support", label: "Support Waqt on Ko-fi", ref: { support: true } })
      ]) })
    ]),

    /* Kept for page scripts that list externally-built apps. */
    links: Object.freeze({ officialApps: [], communityApps: [], sdkRepos: [], packageRegistries: [] })
  });
})();
