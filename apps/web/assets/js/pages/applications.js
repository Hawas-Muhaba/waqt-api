/* Applications page: ONE store feeds four different presentations of the same data. */
(function () {
  "use strict";
  const W = window.Waqt;
  const store = W.createLive({});
  W.bindLive(store, [
    W.createClock(document.getElementById("apps-clock"), { variant: "full", idPrefix: "apps" }),
    W.createMosqueClock(document.getElementById("apps-mosque")),
    W.createWatch(document.getElementById("apps-watch")),
    W.createDayLength(document.getElementById("apps-day"))
  ], document.getElementById("apps-banner"));
  store.start();
})();
