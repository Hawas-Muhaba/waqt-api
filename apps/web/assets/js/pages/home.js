/* Home: one live store drives the circular clock, the telemetry fields and the day-length measurement. */
(function () {
  "use strict";
  const W = window.Waqt, $ = (id) => document.getElementById(id);
  const store = W.createLive({});
  W.bindLive(store, [W.createClock($("home-clock"), { variant: "full", idPrefix: "home" }), W.createDayLength($("home-day")), W.bindFields(document)], $("home-banner"));
  store.start();
})();
