/* Waqt Web — configuration.
   Every external URL lives here and nowhere else. A value of null means "not supplied yet": the UI then renders a
   visibly pending, non-clickable placeholder rather than a guessed link. Fill these in when the real URLs exist.
   (Static site, no build step: edit this file and redeploy.) */
window.WAQT_CONFIG = Object.freeze({
  /* API base: unchanged from the Sprint 12/14 viewer (same defaults, same ?api= override, same localStorage key). */
  api: Object.freeze({
    localBase: "http://localhost:8000",
    publicBase: "https://waqt-api-r6e0.onrender.com",
    storageKey: "waqt:apiBase",
    requestTimeoutMs: 25000          // the free Render plan can take a while to wake
  }),

  contactEmail: "waqtapi@gmail.com",
  ideaSubject: "Waqt idea / proposal",

  links: Object.freeze({
    github: null,                    // e.g. "https://github.com/<owner>/<repo>" — repository URL not confirmed yet
    docs: null,                      // canonical docs/specification location (falls back to the Resources page)
    spec: null,
    issues: null,
    buyMeACoffee: null,              // Buy Me a Coffee page URL — not supplied yet
    sdkRepos: [],                    // [{ name, url, note }]
    packageRegistries: [],           // [{ name, url, note }]  (PyPI / npm pages once SDKs are actually published)
    officialApps: [],                // [{ name, url, note }]
    communityApps: []                // [{ name, url, note, author }]
  })
});
