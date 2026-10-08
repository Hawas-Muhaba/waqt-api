/* The Problem: the same live events placed on a midnight ring and on a Waqt ring, plus the measured day length. */
(function () {
  "use strict";
  const W = window.Waqt, $ = (id) => document.getElementById(id);
  const store = W.createLive({});
  W.bindLive(store, [W.createCompare($("problem-compare")), W.createDayLength($("problem-day"))], $("problem-banner"));
  store.start();
})();
