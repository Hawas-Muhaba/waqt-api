/* Waqt Web — live data controller shared by every live component.
 *
 * States:  loading | success | empty | error | offline
 *   success  real API data; ticks once a second between polls; re-asks the server at the day boundary / next event.
 *   empty    the API answered but Waqt is undefined here/now (e.g. polar); we say so, we do not substitute data.
 *   error    the API could not be reached / answered with an error  -> shows the recorded DEMO sample, frozen, labelled.
 *   offline  the browser reports no network                          -> same demo fallback, labelled.
 * `store.isDemo` is true whenever the numbers on screen are the recorded sample, so components can say so.
 */
(function (root) {
  "use strict";
  const W = root.Waqt;

  function createLive(opts) {
    const o = Object.assign({ lat: 9.0192, lon: 38.7525, provider: "arithmetic-tabular", autoRetry: true, tickMs: 1000 }, opts || {});
    const now = o.now || (() => Date.now());
    const listeners = new Set();
    const store = {
      state: "loading", model: null, anchor: null, isDemo: false, error: null, place: { lat: o.lat, lon: o.lon }, lastOkAt: null,
      subscribe(fn) { listeners.add(fn); return () => listeners.delete(fn); },
      snapshot() { return store.model && store.anchor ? W.snapshotAt(store.anchor, store.isDemo ? store.anchor.fetchedAtMs : now()) : null; },
      start() { load(false); tickHandle = setInterval(tick, o.tickMs); return store; },
      stop() { clearInterval(tickHandle); clearTimeout(retryHandle); },
      retryNow() { clearTimeout(retryHandle); return load(false); },
      setPlace(lat, lon) { store.place = { lat, lon }; return load(false); },
      forceDemo() { useDemo("error", new W.WaqtApiError("network", "Demonstration requested.")); }
    };
    let tickHandle = null, retryHandle = null, refreshing = false, backoffUntil = 0, retryDelay = 30000;

    function emit(type) { listeners.forEach((fn) => { try { fn(type, store); } catch (e) { console.error(e); } }); }

    function useDemo(state, err) {
      const demo = root.WAQT_DEMO;
      store.error = err;
      if (!demo) { store.state = state; store.model = null; store.anchor = null; store.isDemo = false; emit("state"); return; }
      store.model = W.fromWaqtData(demo.data);
      store.anchor = W.makeAnchor(store.model, store.model.instantMs);      // frozen at the recorded instant
      store.isDemo = true; store.state = state;
      emit("state");
    }

    async function load(silent) {
      if (!silent) { store.state = "loading"; emit("state"); }
      if (root.navigator && root.navigator.onLine === false) { useDemo("offline", new W.WaqtApiError("network", "This browser reports it is offline.")); scheduleRetry(); return; }
      try {
        const data = await W.getJSON("/v1/waqt", { lat: store.place.lat, lon: store.place.lon, calendar_provider: o.provider }, { fetchImpl: o.fetchImpl, base: o.base });
        const model = W.fromWaqtData(data);
        store.error = null; retryDelay = 30000;
        if (model.state !== "ok") { store.state = "empty"; store.model = null; store.anchor = null; store.isDemo = false; store.emptyReason = model.reason; emit("state"); return; }
        store.model = model; store.anchor = W.makeAnchor(model, now()); store.isDemo = false; store.state = "success"; store.lastOkAt = now();
        emit("state");
      } catch (e) {
        if (silent && store.state === "success") {      // boundary refresh failed: keep the last good answer, retry later
          backoffUntil = now() + (e.retryAfter || 15) * 1000; store.error = e; emit("refresh-failed"); return;
        }
        useDemo(e.kind === "network" && root.navigator && root.navigator.onLine === false ? "offline" : "error", e);
        scheduleRetry();
      }
    }

    function scheduleRetry() {
      clearTimeout(retryHandle);
      if (!o.autoRetry) return;
      retryHandle = setTimeout(() => load(true).then(() => { if (store.state !== "success" && store.state !== "empty") scheduleRetry(); }), retryDelay);
      retryDelay = Math.min(retryDelay * 2, 240000);
    }

    async function refresh() { refreshing = true; try { await load(true); } finally { refreshing = false; } }

    function tick() {
      if (store.state === "success") {
        const snap = store.snapshot();
        if (snap && snap.expired && !refreshing && now() >= backoffUntil) refresh();   // re-ask the server; never compute the next day
        emit("tick");
      } else if (store.state === "error" || store.state === "offline") {
        // demo is frozen; if the browser came back online, try the live API right away
        if (root.navigator && root.navigator.onLine !== false && store.state === "offline") load(true);
      }
    }
    return store;
  }

  W.createLive = createLive;
})(typeof window !== "undefined" ? window : globalThis);
