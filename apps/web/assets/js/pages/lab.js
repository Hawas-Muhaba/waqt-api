/* Waqt Experience Lab. Five demonstrations; every number comes from the Waqt API (or the labelled demo sample).
   01 scrub     — a virtual view over the SAME model: position = slider × server day length; events/instants from the API.
   02 reset     — real API calls (/v1/waqt with lat/lon/instant) for a chosen place and date.
   03 playback  — accelerated passage of time over the API's own event instants (user-started, labelled SIMULATED).
   04 compare   — the shared widgets (same store).
   05 build     — example request text + a real call through the same client. */
(function () {
  "use strict";
  const W = window.Waqt, esc = W.esc, $ = (id) => document.getElementById(id);
  const store = W.createLive({});

  /* ---------- 01 scrub: a virtual store with the model's shape; the model object is reused so the clock does not rebuild */
  const scrubClock = W.createClock($("lab-clock"), { variant: "full", idPrefix: "lab", showList: false });
  const scrub = $("scrub"), scrubOut = $("scrub-out");
  let vmodel = null, vsrc = null;
  const virtual = {
    state: "success", isDemo: false, chipText: "SCRUB PREVIEW", model: null, anchor: null,
    snapshot() { return this.snap; }, snap: null
  };
  function updateScrub() {
    const m = store.model;
    if (!m) { virtual.state = store.state; virtual.model = null; scrubClock.update(virtual); scrubOut.textContent = ""; return; }
    if (vsrc !== m) { vsrc = m; vmodel = Object.assign({}, m); }            // stable object per fetched model
    const frac = Number(scrub.value) / 1000, len = m.day.lengthSeconds, seconds = frac * len;
    const virtualMs = m.day.openMs + seconds * 1000;
    const nx = W.nextEventAfter(m, virtualMs);
    vmodel.next = nx ? { name: nx.name, label: nx.label, instantIso: nx.instantIso, instantMs: nx.instantMs, countdownSeconds: (nx.instantMs - virtualMs) / 1000 } : null;
    virtual.state = "success"; virtual.model = vmodel;
    virtual.snap = { readingSeconds: seconds, readingDisplay: W.fmtHMS(seconds), dayFraction: frac,
      countdownSeconds: vmodel.next ? vmodel.next.countdownSeconds : null, countdownDisplay: vmodel.next ? W.fmtHMS(vmodel.next.countdownSeconds) : null, expired: false };
    scrubClock.update(virtual);
    const prev = m.events.filter((e) => e.defined && e.instantMs <= virtualMs).sort((a, b) => b.instantMs - a.instantMs)[0];
    scrubOut.innerHTML = `<div class="mono" style="font-size:1.6rem">Waqt ${esc(virtual.snap.readingDisplay)}</div>` +
      `<div>Local time at this position: <b class="mono">${esc(W.localClock(new Date(virtualMs).toISOString(), m.tzName))}</b>${store.isDemo ? " (demo sample)" : ""}</div>` +
      `<div>Last event: <b>${prev ? esc(prev.label) : "none yet this Waqt day"}</b> · Next: <b>${nx ? esc(nx.label) + " in " + esc(W.fmtHMS(vmodel.next.countdownSeconds)) : "none"}</b></div>`;
    scrub.setAttribute("aria-valuetext", `Waqt ${virtual.snap.readingDisplay}`);
  }
  scrub.addEventListener("input", updateScrub);

  /* ---------- 03 playback */
  const pb = { playing: false, virtualMs: null, handle: null, lastWall: 0, nextKey: "" };
  function pbReset() {
    const m = store.model; if (!m) return;
    pb.virtualMs = m.day.openMs; pb.nextKey = ""; drawPb();
  }
  function drawPb() {
    const m = store.model; if (!m || pb.virtualMs == null) return;
    const nx = W.nextEventAfter(m, pb.virtualMs), seconds = (pb.virtualMs - m.day.openMs) / 1000;
    $("pb-reading").textContent = "Waqt " + W.fmtHMS(Math.min(seconds, m.day.lengthSeconds));
    $("pb-next").textContent = nx ? `Next · ${nx.label}${nx.position === "after-close" ? " (after the next Maghrib)" : ""}` : "No further event in this Waqt day";
    $("pb-count").textContent = nx ? "in " + W.fmtHMS((nx.instantMs - pb.virtualMs) / 1000) : "";
    $("pb-chip").textContent = "SIMULATED PLAYBACK" + (store.isDemo ? " · DEMO SAMPLE" : "");
    const key = nx ? nx.name : "none";
    if (key !== pb.nextKey) { pb.nextKey = key; $("pb-sr").textContent = nx ? `Next event: ${nx.label}` : "No further event"; }
  }
  function pbStep() {
    const m = store.model; if (!m) return;
    const now = performance.now(), dt = (now - pb.lastWall) / 1000; pb.lastWall = now;
    pb.virtualMs += dt * Number($("pb-speed").value) * 1000;
    const end = m.day.closeMs + 1;
    if (pb.virtualMs >= end) { pb.virtualMs = end; pbPause(); }
    drawPb();
  }
  function pbPause() { pb.playing = false; clearInterval(pb.handle); $("pb-play").textContent = "Play"; }
  $("pb-play").addEventListener("click", () => {
    if (pb.playing) { pbPause(); return; }
    if (pb.virtualMs == null || pb.virtualMs > store.model.day.closeMs) pbReset();
    pb.playing = true; pb.lastWall = performance.now(); $("pb-play").textContent = "Pause"; pb.handle = setInterval(pbStep, 200);
  });
  $("pb-reset").addEventListener("click", () => { pbPause(); pbReset(); });

  /* ---------- 02 Maghrib reset: real API calls */
  $("reset-date").value = new Date().toISOString().slice(0, 10);
  const rows = []; 
  $("reset-go").addEventListener("click", async () => {
    const sel = $("reset-place"), [lat, lon] = sel.value.split(",").map(Number), date = $("reset-date").value;
    const name = sel.options[sel.selectedIndex].text, st = $("reset-status");
    if (!date) { st.textContent = "Choose a date first."; return; }
    st.textContent = `Asking the API for ${name}, ${date} …`;
    try {
      const data = await W.getJSON("/v1/waqt", { lat, lon, instant: `${date}T12:00:00Z` });
      const m = W.fromWaqtData(data);
      if (m.state !== "ok") { st.textContent = `Waqt is undefined for ${name} on ${date}: ${m.reason}`; return; }
      rows.unshift(`<tr><th scope="row">${esc(name)}</th><td class="mono">${esc(date)}</td><td class="mono">${esc(W.localClock(m.day.openIso, m.tzName))}</td><td class="mono">${esc(W.localClock(m.day.closeIso, m.tzName))}</td><td class="mono">${esc(W.fmtHMS(m.day.lengthSeconds))}</td></tr>`);
      rows.length = Math.min(rows.length, 8);
      $("reset-rows").innerHTML = rows.join(""); $("reset-table").hidden = false;
      st.textContent = `Maghrib opens the Waqt day at ${W.localClock(m.day.openIso, m.tzName)} local in ${name} (${m.tzName || "timezone unavailable"}).`;
    } catch (e) {
      st.innerHTML = `Live API unavailable (${esc(e.message)}). This step needs the real API — there is no demo sample for arbitrary places and dates.`;
    }
  });

  /* ---------- 04 compare, 05 build */
  const compare = W.createCompare($("lab-compare")), dayLen = W.createDayLength($("lab-day"));
  const base = W.apiBase(); let lang = "curl";
  const drawSnippet = () => { $("build-snippet").textContent = W.exampleSnippet(lang, base, store.place.lat, store.place.lon); $("build-loc").textContent = `${store.place.lat}, ${store.place.lon}`; };
  document.querySelectorAll("#build .tabs [data-tab]").forEach((b) => b.addEventListener("click", () => {
    lang = b.dataset.tab; document.querySelectorAll("#build .tabs [data-tab]").forEach((x) => x.setAttribute("aria-selected", String(x === b))); drawSnippet();
  }));
  drawSnippet();
  $("build-run").addEventListener("click", async () => {
    const out = $("build-out"); out.hidden = false; out.textContent = "Calling the API …";
    try {
      const d = await W.getJSON("/v1/waqt", { lat: store.place.lat, lon: store.place.lon });
      const m = W.fromWaqtData(d);
      out.innerHTML = m.state !== "ok" ? `Waqt undefined: ${esc(m.reason)}` :
        `<span class="badge live">LIVE RESPONSE</span><dl class="kv" style="margin-top:8px"><dt>status</dt><dd>${esc(d.status)}</dd><dt>day.maghrib_open</dt><dd class="mono">${esc(d.day.maghrib_open)}</dd><dt>day.maghrib_close</dt><dd class="mono">${esc(d.day.maghrib_close)}</dd><dt>waqt.reading.display</dt><dd class="mono">${esc(d.waqt.reading.display)}</dd><dt>next_event</dt><dd>${esc(d.next_event ? d.next_event.name + " in " + d.next_event.countdown.display : "none")}</dd></dl>`;
    } catch (e) { out.innerHTML = `<span class="badge demo">NOT REACHABLE</span> ${esc(e.message)}`; }
  });

  /* ---------- wire the shared store */
  W.bindLive(store, [{ update() { updateScrub(); } }, compare, dayLen, { update(s) { if (pb.virtualMs == null && s.model) pbReset(); } }], $("lab-banner"));
  store.subscribe((type) => { if (type === "state") { pbPause(); pb.virtualMs = null; if (store.model) pbReset(); } });
  store.start();
})();
