/* Waqt Web — application visualisations. All of them read the SAME store/model as the circular clock
 * (Waqt.createLive → Waqt.fromWaqtData); none has its own event data or prayer calculation.
 * Mosque clock and smartwatch are CONCEPT applications: the data is real (or labelled demo), the devices are not products. */
(function (root) {
  "use strict";
  const W = root.Waqt, esc = W.esc;
  const CIVIL_DAY_SECONDS = 24 * 3600;   // definition of a midnight-to-midnight civil day, used only to contrast with the Waqt day

  const tag = (store, concept) =>
    (concept ? `<span class="badge concept">CONCEPT</span> ` : "") + (store.isDemo ? `<span class="badge demo">DEMO · NOT LIVE</span>` : store.state === "success" ? `<span class="badge live">LIVE DATA</span>` : "");

  /* ---------------------------------------------------------------- mosque */
  function createMosqueClock(container) {
    container.innerHTML = `<div class="mosque" role="group" aria-label="Mosque wall clock concept">
      <div class="state-tag" data-slot="tag"></div>
      <div class="m-brand">WAQT</div>
      <div class="m-row"><div class="k">WAQT</div><div class="v" data-slot="reading">––:––:––</div><div class="sub" data-slot="sub"></div></div>
      <div class="m-row"><div class="k">NEXT EVENT</div><div class="v sm" data-slot="next">—</div><div class="v" data-slot="count" style="font-size:clamp(1.6rem,6vw,2.4rem)"></div></div>
      <div class="m-row"><div class="k">MAGHRIB</div><div class="m-split"><div><div class="sub">opened</div><div class="v sm mono" data-slot="open">—</div></div><div><div class="sub">next Maghrib</div><div class="v sm mono" data-slot="close">—</div></div></div><div class="sub" data-slot="len"></div></div>
    </div>`;
    const q = (s) => container.querySelector(`[data-slot="${s}"]`);
    return { update(store) {
      q("tag").innerHTML = tag(store, true);
      const m = store.model;
      if (!m) { q("reading").textContent = store.state === "loading" ? "Loading…" : "No data"; return; }
      const s = store.snapshot();
      q("reading").textContent = s.readingDisplay;
      q("sub").textContent = [m.hijri ? `${m.hijri.display} (${m.hijri.provider})` : "Hijri date unavailable", m.weekday].filter(Boolean).join(" · ");
      q("next").textContent = m.next ? m.next.label : "No further event";
      q("count").textContent = m.next && s.countdownDisplay ? "in " + s.countdownDisplay : "";
      q("open").textContent = W.localClock(m.day.openIso, m.tzName); q("close").textContent = W.localClock(m.day.closeIso, m.tzName);
      q("len").textContent = `Waqt day length ${W.fmtHMS(m.day.lengthSeconds)} (as reported by the API)`;
    } };
  }

  /* ------------------------------------------------------------ smartwatch */
  function createWatch(container) {
    container.innerHTML = `<div class="watch-wrap"><div class="watch" role="group" aria-label="Smartwatch face concept"><div data-slot="face"></div></div></div><p class="muted" style="text-align:center;margin:0" data-slot="tag"></p>`;
    const clock = W.createClock(container.querySelector('[data-slot="face"]'), { variant: "watch", idPrefix: "watch" });
    const tagEl = container.querySelector('[data-slot="tag"]');
    return { update(store) { clock.update(store); tagEl.innerHTML = tag(store, true); } };
  }

  /* ------------------------------------------------------ day length (bar) */
  function createDayLength(container) {
    container.innerHTML = `<div class="daybar" role="img" data-slot="bar" aria-label="Position within the Waqt day"><div class="fill" data-slot="fill"></div><div class="pin" data-slot="pin"></div><div class="now" data-slot="nowlab"></div>
      <div class="lab" data-slot="l0">Maghrib · opens</div><div class="lab end" data-slot="l1">next Maghrib</div></div>
      <div class="compare">
        <div class="stat"><div class="k">Waqt day (opening → closing Maghrib instants)</div><div class="v" data-slot="waqtlen">—</div></div>
        <div class="stat"><div class="k">Midnight civil day (by definition)</div><div class="v">${W.fmtHMS(CIVIL_DAY_SECONDS)}</div></div>
        <div class="stat"><div class="k">Difference</div><div class="v" data-slot="diff">—</div></div>
        <div class="stat"><div class="k">API-reported <code>length_si_seconds</code></div><div class="v" data-slot="srv">—</div></div>
      </div><p class="muted" style="margin:10px 0 0" data-slot="note"></p>`;
    const q = (s) => container.querySelector(`[data-slot="${s}"]`);
    return { update(store) {
      const m = store.model; if (!m) return;
      const s = store.snapshot();
      const dur = (m.day.closeMs - m.day.openMs) / 1000;                 // from the two Maghrib instants, as the brief asks
      const pct = (s.dayFraction * 100).toFixed(2) + "%";
      q("fill").style.width = pct; q("pin").style.left = pct; q("nowlab").style.left = pct;
      q("nowlab").textContent = "now " + s.readingDisplay + (store.isDemo ? " (demo)" : "");
      q("l0").textContent = `Maghrib · ${W.localClock(m.day.openIso, m.tzName)}`; q("l1").textContent = `next Maghrib · ${W.localClock(m.day.closeIso, m.tzName)}`;
      q("waqtlen").textContent = W.fmtHMS(dur);
      const d = dur - CIVIL_DAY_SECONDS;
      q("diff").textContent = (d === 0 ? "" : d > 0 ? "+" : "−") + W.fmtHMS(Math.abs(d)) + (d < 0 ? " shorter" : d > 0 ? " longer" : "");
      q("srv").textContent = m.day.lengthSeconds + " s";
      q("note").textContent = (m.day.note || "") + (store.isDemo ? " (Recorded sample — not today's live value.)" : "");
      q("bar").setAttribute("aria-label", `Position within the Waqt day: Waqt ${s.readingDisplay} of ${W.fmtHMS(dur)}`);
    } };
  }

  /* -------------------------------- midnight model vs Waqt model (two rings) */
  const secOfDay = (hms) => { const p = String(hms).split(":").map(Number); return p[0] * 3600 + p[1] * 60 + (p[2] || 0); };
  function ringSvg(markers, nowFrac, origin) {
    const C = 110, R = 80, pt = (f, r) => { const a = f * 2 * Math.PI - Math.PI / 2; return [C + r * Math.cos(a), C + r * Math.sin(a)]; };
    const dots = markers.map((m) => { const [x, y] = pt(m.f, R), [lx, ly] = pt(m.f, R + 20); return `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="5" fill="#141a2e" stroke="#5cc8d4" stroke-width="2"/><text x="${lx.toFixed(1)}" y="${(ly + 3).toFixed(1)}" text-anchor="middle" font-size="9" fill="#b9b3a2">${esc(m.t)}</text>`; }).join("");
    const [nx, ny] = nowFrac == null ? [C, C - R] : pt(nowFrac, R);
    const [ox, oy] = pt(0, R + 20);
    return `<svg viewBox="0 0 220 220" width="100%" style="max-width:300px" aria-hidden="true"><circle cx="${C}" cy="${C}" r="${R}" fill="none" stroke="#262f52" stroke-width="8"/>${dots}<circle cx="${nx.toFixed(1)}" cy="${ny.toFixed(1)}" r="6" fill="#e2953f" stroke="#fff" stroke-width="1.5"/><text x="${C}" y="${C + 4}" text-anchor="middle" font-size="12" fill="#eee7d6">${esc(origin)}</text><text x="${ox.toFixed(1)}" y="${(oy - 4).toFixed(1)}" text-anchor="middle" font-size="9" fill="#e2953f">▲ origin</text></svg>`;
  }
  function createCompare(container) {
    container.innerHTML = `<div class="rings"><figure><div data-slot="mid"></div><figcaption><b>Midnight model</b> — the day starts at 00:00 local. Events sit at their civil clock time.</figcaption></figure>
      <figure><div data-slot="waq"></div><figcaption><b>Waqt model</b> — the day starts at Maghrib. Events sit at their position since Maghrib.</figcaption></figure></div>
      <div class="table-scroll"><table class="data" style="margin-top:18px"><caption class="vh">Event times in both models</caption><thead><tr><th scope="col">Event</th><th scope="col">Local clock (midnight model)</th><th scope="col">Waqt reading (since Maghrib)</th></tr></thead><tbody data-slot="rows"></tbody></table></div>`;
    const q = (s) => container.querySelector(`[data-slot="${s}"]`);
    let builtFor = null;
    return { update(store) {
      const m = store.model; if (!m) return;
      const s = store.snapshot();
      const nowMs = store.isDemo ? store.anchor.fetchedAtMs : Date.now();
      const nowLocal = secOfDay(W.localClock(new Date(nowMs).toISOString(), m.tzName)) / CIVIL_DAY_SECONDS;
      const evs = m.events.filter((e) => e.defined && e.position !== "close");
      const mid = [{ f: secOfDay(W.localClock(m.day.openIso, m.tzName)) / CIVIL_DAY_SECONDS, t: "Mgh" }].concat(evs.map((e) => ({ f: secOfDay(e.local) / CIVIL_DAY_SECONDS, t: e.label.slice(0, 3) })));
      const waq = evs.map((e) => ({ f: e.plot, t: e.label.slice(0, 3) }));
      q("mid").innerHTML = ringSvg(mid, nowLocal, "00:00");
      q("waq").innerHTML = ringSvg(waq, s.dayFraction, "Maghrib");
      if (builtFor !== m) {
        builtFor = m;
        q("rows").innerHTML = `<tr><th scope="row">Maghrib (opens the Waqt day)</th><td class="mono">${esc(W.localClock(m.day.openIso, m.tzName))}</td><td class="mono">00:00:00</td></tr>` +
          m.events.filter((e) => e.defined).map((e) => `<tr><th scope="row">${esc(e.position === "close" ? "Next Maghrib" : e.label)}</th><td class="mono">${esc(e.local)}</td><td class="mono">${esc(e.display)}${e.position === "after-close" ? " (after the next Maghrib)" : ""}</td></tr>`).join("");
      }
    } };
  }

  Object.assign(W, { createMosqueClock, createWatch, createDayLength, createCompare, CIVIL_DAY_SECONDS });
})(typeof window !== "undefined" ? window : globalThis);
