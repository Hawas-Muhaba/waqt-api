/* How it works: live measurement + two real-API probes (undefined at the poles; convention invariance). */
(function () {
  "use strict";
  const W = window.Waqt, esc = W.esc, $ = (id) => document.getElementById(id);
  const store = W.createLive({});
  W.bindLive(store, [W.createDayLength($("how-day")), W.bindFields(document)], $("how-banner"));
  store.start();

  $("probe-go").addEventListener("click", async () => {
    const [lat, lon, instant] = $("probe-case").value.split(","), out = $("probe-out");
    out.textContent = "Asking the API …";
    try {
      const d = await W.getJSON("/v1/waqt", { lat, lon, instant });
      const m = W.fromWaqtData(d);
      out.innerHTML = m.state === "ok"
        ? `<span class="badge live">status OK</span> Maghrib opens at <b class="mono">${esc(W.localClock(m.day.openIso, m.tzName))}</b> local; the Waqt day is <b class="mono">${esc(W.fmtHMS(m.day.lengthSeconds))}</b> long.`
        : `<span class="badge concept">status UNDEFINED</span> ${esc(m.reason)}`;
    } catch (e) { out.innerHTML = `<span class="badge demo">API NOT REACHABLE</span> ${esc(e.message)} — this probe needs the live API; there is no demonstration sample for it.`; }
  });

  const rows = [];
  $("inv-go").addEventListener("click", async () => {
    const angle = $("inv-angle").value, st = $("inv-status");
    st.textContent = `Asking the API with fajr_angle=${angle} …`;
    try {
      const d = await W.getJSON("/v1/waqt", { lat: store.place.lat, lon: store.place.lon, instant: store.model ? store.model.instantIso : undefined, fajr_angle: angle });
      const m = W.fromWaqtData(d), f = m.state === "ok" && m.events.find((e) => e.name === "fajr");
      if (!f || !f.defined) { st.textContent = "Fajr is undefined for these parameters."; return; }
      rows.unshift(`<tr><td>${esc(angle)}°</td><td>${esc(f.local)}</td><td>${esc(f.display)}</td><td>${esc(W.localClock(m.day.openIso, m.tzName))}</td><td>${esc(W.localClock(m.day.closeIso, m.tzName))}</td></tr>`);
      rows.length = Math.min(rows.length, 8); $("inv-rows").innerHTML = rows.join(""); $("inv-table").hidden = false;
      st.textContent = "Done. Try another angle and compare the last two columns.";
    } catch (e) { st.innerHTML = `API not reachable (${esc(e.message)}). This demonstration needs the live API.`; }
  });
})();
