/* Live Demo: choose a place and conventions; every number is a real API response (or the labelled demo sample). */
(function () {
  "use strict";
  const W = window.Waqt, esc = W.esc, $ = (id) => document.getElementById(id);
  const store = W.createLive({});
  const clock = W.createClock($("demo-clock"), { variant: "full", idPrefix: "demo" });
  const fields = W.bindFields(document), day = W.createDayLength($("demo-day"));
  const inspector = {
    update(s) {
      $("d-url").textContent = s.requestUrl || "—";
      const raw = s.raw ? JSON.stringify(s.raw, null, 2) : "—";
      $("d-json").textContent = (s.isDemo ? "// RECORDED DEMONSTRATION SAMPLE — not a response to your request\n" : "") + raw;
    }
  };
  let lastKey = "";
  W.bindLive(store, [clock, fields, day, { update(s) { const k = s.state + (s.requestUrl || "") + (s.latencyMs || ""); if (k !== lastKey) { lastKey = k; inspector.update(s); } } }], $("demo-banner"));

  /* providers: read from the API, fall back to the two known names */
  W.getJSON("/v1/calendar", {}).then((d) => {
    const list = (d.providers || []).map((p) => (typeof p === "string" ? p : p.name)).filter(Boolean);
    if (list.length) $("d-cal").innerHTML = list.map((n) => `<option value="${esc(n)}">${esc(n)}</option>`).join("");
  }).catch(() => {}).then(() => {
    // The picker must show the provider the page is ACTUALLY using (the configured default, umm-al-qura), never whichever
    // provider the API happens to list first; otherwise "Apply" would silently switch the user to another provider.
    const cfg = window.WAQT_CONFIG && window.WAQT_CONFIG.hijri, want = (store.params && store.params.calendar_provider) || (cfg && cfg.defaultProvider) || "umm-al-qura";
    const sel = $("d-cal"); if ([...sel.options].some((o) => o.value === want)) sel.value = want;
  });

  const place = $("d-place"), lat = $("d-lat"), lon = $("d-lon");
  place.addEventListener("change", () => { if (place.value !== "custom") { const [a, b] = place.value.split(","); lat.value = a; lon.value = b; } });
  [lat, lon].forEach((el) => el.addEventListener("input", () => { place.value = "custom"; }));
  function apply() {
    const la = parseFloat(lat.value), lo = parseFloat(lon.value), msg = $("d-msg");
    if (!(la >= -90 && la <= 90) || !(lo >= -180 && lo <= 180)) { msg.textContent = "Latitude must be −90…90 and longitude −180…180."; return; }
    msg.textContent = "";
    store.setQuery({ lat: la, lon: lo }, { fajr_angle: $("d-fajr").value, isha_angle: $("d-isha").value, asr_ratio: $("d-asr").value, calendar_provider: $("d-cal").value });
  }
  $("d-apply").addEventListener("click", apply);
  $("d-geo").addEventListener("click", () => {
    if (!navigator.geolocation) { $("d-msg").textContent = "This browser has no geolocation; enter coordinates."; return; }
    $("d-msg").textContent = "Requesting location…";
    navigator.geolocation.getCurrentPosition((p) => { lat.value = p.coords.latitude.toFixed(4); lon.value = p.coords.longitude.toFixed(4); place.value = "custom"; apply(); },
      (e) => { $("d-msg").textContent = `Location unavailable (${e.message}). Enter coordinates manually.`; }, { timeout: 10000 });
  });
  $("d-copy").addEventListener("click", () => { const t = $("d-url").textContent; if (navigator.clipboard && t && t !== "—") navigator.clipboard.writeText(t).then(() => { $("d-msg").textContent = "Request URL copied."; }); });
  store.start();
})();
