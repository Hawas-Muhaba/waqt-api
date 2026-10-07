/* Waqt Web — reusable circular Waqt clock.
 *
 *   const clock = Waqt.createClock(containerEl, { variant: "full" | "watch", idPrefix: "home" });
 *   store.subscribe(() => clock.update(store));          // store = Waqt.createLive(...) (or any object with the same shape)
 *
 * Geometry: 12 o'clock is the opening Maghrib; the ring spans [Maghrib(D), Maghrib(D+1)) and its length is whatever the
 * API says it is (never 24 h by assumption). Marker position = server seconds / server day length. The component is
 * pure presentation: inputs are the model from Waqt.fromWaqtData (day open/close, events, next event) and a snapshot.
 * Every drawing is paired with a textual equivalent (an ordered list), labelled markers, and keyboard navigation.
 */
(function (root) {
  "use strict";
  const W = root.Waqt;
  const NS = "http://www.w3.org/2000/svg";
  const C = 220, R = 150, CIRC = 2 * Math.PI * R;

  const esc = (v) => String(v).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  const pt = (frac, r) => { const a = frac * 2 * Math.PI - Math.PI / 2; return [C + r * Math.cos(a), C + r * Math.sin(a)]; };
  const f1 = (n) => n.toFixed(1);

  function humanDuration(seconds) {
    const s = Math.max(0, Math.round(seconds)), h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
    return h ? `${h} h ${m} min` : m ? `${m} min` : `${s} s`;
  }

  /* Banner text shared by every live component. Never lets demo data pass for live data. */
  function bannerHtml(store) {
    const m = store.model;
    if (store.state === "loading") return `<div class="notice info" role="status"><b>Loading Waqt data…</b> The public API runs on a free host and can take up to a minute to wake.</div>`;
    if (store.state === "empty") return `<div class="notice" role="status"><b>Waqt is undefined here right now.</b> ${esc(store.emptyReason || "")}</div>`;
    if (store.state === "error" || store.state === "offline") {
      const why = store.state === "offline" ? "This browser appears to be offline." : (store.error ? store.error.message : "The API did not answer.");
      return `<div class="notice err" role="status"><b>Live Waqt data unavailable</b> — viewing demonstration mode.` +
        ` ${m ? "The numbers below are a <b>recorded sample</b> (" + esc(root.WAQT_DEMO ? root.WAQT_DEMO.recorded : "") + "), frozen and <b>not live</b>." : "No demonstration sample is loaded."}` +
        `<br><span class="muted">${esc(why)}</span> <button type="button" class="btn ghost small" data-retry>Retry now</button></div>`;
    }
    const c = m && m.computation ? m.computation : {};
    return `<div class="live-strip"><span class="badge live">LIVE</span><span>${esc(m.location.lat)}, ${esc(m.location.lon)}${m.tzName ? " · " + esc(m.tzName) : ""}</span>` +
      `<span>${esc(c.engine || "")}${c.accuracy_level ? " · accuracy " + esc(c.accuracy_level) : ""}</span></div>`;
  }

  function createClock(container, options) {
    const o = Object.assign({ variant: "full", idPrefix: "wc" + Math.random().toString(36).slice(2, 7), showList: true }, options || {});
    const watch = o.variant === "watch";
    const id = (s) => `${o.idPrefix}-${s}`;
    container.innerHTML = `<figure class="wc ${watch ? "watch" : ""}" data-variant="${o.variant}">
        <div data-slot="state" class="state-box" hidden></div>
        <div data-slot="face" hidden>
          <svg viewBox="0 0 440 440" role="img" aria-labelledby="${id("t")} ${id("d")}">
            <title id="${id("t")}">Waqt day clock</title><desc id="${id("d")}" data-slot="desc"></desc>
            <circle class="ring-glow" cx="${C}" cy="${C}" r="${R + 14}"/>
            <circle class="ring-track" cx="${C}" cy="${C}" r="${R}"/>
            <g data-slot="ticks"></g>
            <circle class="ring-elapsed" data-slot="elapsed" cx="${C}" cy="${C}" r="${R}" transform="rotate(-90 ${C} ${C})" stroke-dasharray="${CIRC}" stroke-dashoffset="${CIRC}"/>
            <g data-slot="markers" role="list" aria-label="Waqt events around the day"></g>
            <circle class="now-dot" data-slot="now" r="${watch ? 9 : 8}" cx="${C}" cy="${C - R}"/>
            <text class="c-label" x="${C}" y="${C - 40}" data-slot="clabel">WAQT</text>
            <text class="c-time" x="${C}" y="${C + 8}" data-slot="ctime" ${watch ? 'style="font-size:52px"' : ""}>–</text>
            <text class="c-next" x="${C}" y="${C + 36}" data-slot="cnext"></text>
            <text class="c-count" x="${C}" y="${C + 62}" data-slot="ccount"></text>
            <text class="c-chip" x="${C}" y="${C + 90}" data-slot="cchip"></text>
          </svg>
          ${watch ? "" : `<div class="detail" data-slot="detail" aria-live="polite">Focus or hover an event marker for details.</div>`}
        </div>
        <p class="vh" data-slot="status" role="status"></p>
        ${watch || !o.showList ? "" : `<ol class="wc-events" data-slot="list" aria-label="Waqt events in order of the day" hidden></ol>`}
      </figure>`;
    const q = (s) => container.querySelector(`[data-slot="${s}"]`);
    const el = { state: q("state"), face: q("face"), desc: q("desc"), ticks: q("ticks"), elapsed: q("elapsed"), markers: q("markers"), now: q("now"),
                 clabel: q("clabel"), ctime: q("ctime"), cnext: q("cnext"), ccount: q("ccount"), cchip: q("cchip"), detail: q("detail"), list: q("list"), status: q("status") };
    let builtFor = null, lastNextKey = null, lastMinute = -1;
    // keyboard: arrow keys / Home / End move between event markers (registered once; markers are rebuilt per model)
    el.markers.addEventListener("keydown", (ev) => {
      const items = Array.from(el.markers.querySelectorAll(".mk")); const i = items.indexOf(document.activeElement);
      if (i < 0) return;
      const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[ev.key];
      if (step) { ev.preventDefault(); items[(i + step + items.length) % items.length].focus(); }
      else if (ev.key === "Home") { ev.preventDefault(); items[0].focus(); } else if (ev.key === "End") { ev.preventDefault(); items[items.length - 1].focus(); }
    });

    function build(model, store) {
      builtFor = model;
      const len = model.day.lengthSeconds;
      // SI-hour grid (the model's hour is a real hour counted from Maghrib): ticks every 3600 s of the server-reported day.
      let ticks = "";
      for (let h = 0; h * 3600 < len; h++) { const [x1, y1] = pt(h * 3600 / len, R - 12), [x2, y2] = pt(h * 3600 / len, R - (h % 6 === 0 ? 26 : 19)); ticks += `<line class="tick" x1="${f1(x1)}" y1="${f1(y1)}" x2="${f1(x2)}" y2="${f1(y2)}"/>`; }
      el.ticks.innerHTML = ticks;

      // Markers (the opening Maghrib is the day's boundary, not an entry of data.events, so it is drawn separately).
      const marks = [{ key: "open", label: "Maghrib opens", plot: 0, local: W.localClock(model.day.openIso, model.tzName), display: "00:00:00", position: "open", aria: `Maghrib opens the Waqt day at ${W.localClock(model.day.openIso, model.tzName)} local, Waqt 00:00:00` }]
        .concat(model.events.filter((e) => e.defined).map((e) => ({ key: e.name, label: e.position === "close" ? "Next Maghrib" : e.label, plot: e.plot, local: e.local, display: e.display, position: e.position, name: e.name,
          aria: `${e.label}${e.position === "after-close" ? " (the evening after the next Maghrib)" : e.position === "close" ? " (closes this Waqt day)" : ""}, ${e.local} local, Waqt ${e.display}` })));
      const ordered = marks.map((m, i) => ({ m, i })).sort((a, b) => a.m.plot - b.m.plot);
      let prevAngle = -999, bump = 0;
      const html = ordered.map(({ m, i }) => {
        const ang = m.plot * 360;
        bump = ang - prevAngle < 26 ? (bump + 1) % 3 : 0; prevAngle = ang;
        const [x, y] = pt(m.plot, R);
        let lx, ly, anchor = "middle";
        if (m.position === "open") { lx = x + 14; ly = y - 22; anchor = "start"; }
        else if (m.position === "close") { lx = x - 14; ly = y - 22; anchor = "end"; }
        else { [lx, ly] = pt(m.plot, R + 30 + bump * 17); ly += 4; anchor = m.plot > 0.5 ? "end" : "start"; if (m.plot > 0.46 && m.plot < 0.54) anchor = "middle"; }
        return `<g class="mk" role="listitem" tabindex="0" data-key="${esc(m.key)}" data-i="${i}" aria-label="${esc(m.aria)}">
            <circle cx="${f1(x)}" cy="${f1(y)}" r="${watch ? 7 : 9}"/>
            ${watch ? "" : `<text x="${f1(lx)}" y="${f1(ly)}" text-anchor="${anchor}">${esc(m.label)}</text>`}</g>`;
      }).join("");
      el.markers.innerHTML = html;
      el.markers._marks = marks;
      el.markers.querySelectorAll(".mk").forEach((g) => {
        const show = () => { if (el.detail) { const m = marks[+g.dataset.i]; el.detail.textContent = `${m.label} · ${m.local} local · Waqt ${m.display}${m.position === "after-close" ? " (after the next Maghrib)" : ""}`; } };
        g.addEventListener("focus", show); g.addEventListener("mouseenter", show);
      });
    }

    function renderList(model) {
      if (!el.list) return;
      const nx = model.next;
      const rows = [`<li><b>Maghrib opens</b><span class="t">${esc(W.localClock(model.day.openIso, model.tzName))}</span><span class="t">00:00:00</span></li>`]
        .concat(model.events.map((e) => {
          if (!e.defined) return `<li><b>${esc(e.label)}</b><span class="t">does not occur</span><span class="t">—</span></li>`;
          const isNext = nx && nx.name === e.name;
          const tonight = isNext && nx.instantIso !== e.instantIso;
          return `<li class="${isNext ? "next" : ""}"><b>${esc(e.position === "close" ? "Next Maghrib" : e.label)}</b>` +
            `<span class="t">${esc(isNext ? W.localClock(nx.instantIso, model.tzName) : e.local)}${tonight ? " (tonight)" : ""}</span><span class="t">${esc(e.display)}${e.position === "after-close" ? " ›" : ""}</span></li>`;
        }));
      el.list.innerHTML = rows.join(""); el.list.hidden = false;
    }

    function update(store) {
      const model = store.model, st = store.state;
      if (st === "loading" && !model) { el.state.hidden = false; el.face.hidden = true; if (el.list) el.list.hidden = true; el.state.innerHTML = `<div><div class="spinner" aria-hidden="true"></div>Loading Waqt…</div>`; return; }
      if (st === "empty" || !model) { el.state.hidden = false; el.face.hidden = true; if (el.list) el.list.hidden = true; el.state.textContent = st === "empty" ? `Waqt is undefined here right now. ${store.emptyReason || ""}` : "No data to show."; return; }
      el.state.hidden = true; el.face.hidden = false;
      if (builtFor !== model) { build(model, store); renderList(model); lastNextKey = null; }
      const snap = store.snapshot();
      const demo = store.isDemo;
      el.elapsed.setAttribute("stroke-dashoffset", String(CIRC * (1 - snap.dayFraction)));
      const [nx, ny] = pt(snap.dayFraction, R); el.now.setAttribute("cx", f1(nx)); el.now.setAttribute("cy", f1(ny));
      el.ctime.textContent = snap.readingDisplay;
      const next = model.next;
      el.cnext.textContent = next ? `Next · ${next.label}` : "No further event";
      el.ccount.textContent = next && snap.countdownDisplay ? snap.countdownDisplay : "";
      el.cchip.textContent = store.chipText || (demo ? "DEMO · NOT LIVE" : "");
      el.clabel.textContent = watch ? "WAQT" : "WAQT DAY";
      // next / passed styling from server values only
      el.markers.querySelectorAll(".mk").forEach((g) => {
        const m = el.markers._marks[+g.dataset.i];
        g.classList.toggle("next", !!(next && m.name === next.name));
        g.classList.toggle("overflow", m.position === "after-close");
        g.classList.toggle("passed", m.position === "in-day" && m.name !== undefined && model.events.some((e) => e.name === m.name && e.seconds <= snap.readingSeconds));
      });
      // textual equivalents: refreshed once a minute (not every second) so assistive tech is not flooded
      const minute = Math.floor(snap.readingSeconds / 60), nextKey = (next ? next.name : "none") + st;
      if (minute !== lastMinute || nextKey !== lastNextKey) {
        const summary = `Waqt ${snap.readingDisplay}${demo ? ", demonstration data, not live" : ""}. ` +
          (next ? `Next event: ${next.label}, in ${humanDuration(snap.countdownSeconds)}. ` : "") +
          `The Waqt day opened at Maghrib, ${W.localClock(model.day.openIso, model.tzName)} local, and closes at the next Maghrib, ${W.localClock(model.day.closeIso, model.tzName)} local.`;
        el.desc.textContent = summary;
        if (nextKey !== lastNextKey) el.status.textContent = summary;
        lastMinute = minute; lastNextKey = nextKey;
      }
    }
    return { update, el, destroy() { container.innerHTML = ""; } };
  }

  W.createClock = createClock; W.bannerHtml = bannerHtml; W.humanDuration = humanDuration; W.esc = esc;
})(typeof window !== "undefined" ? window : globalThis);
