/* Home page wiring: one live store drives the circular clock and the day-length measurement. */
(function () {
  "use strict";
  const W = window.Waqt;
  const store = W.createLive({});
  W.bindLive(store, [
    W.createClock(document.getElementById("home-clock"), { variant: "full", idPrefix: "home" }),
    W.createDayLength(document.getElementById("home-day"))
  ], document.getElementById("home-banner"));
  store.start();
})();
