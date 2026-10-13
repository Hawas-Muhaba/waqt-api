/* Waqt — redesign.js
   Scroll-reveal, enhanced interactions, AT/BT slider, and nav enhancements.
   Loaded after site.js. Does NOT compute any Waqt logic — purely presentation. */
(function () {
  "use strict";

  /* ── 1. Scroll-reveal ── */
  function initReveal() {
    var els = document.querySelectorAll(".r-reveal");
    if (!els.length) return;
    if (!window.IntersectionObserver) {
      els.forEach(function (el) { el.classList.add("r-revealed"); });
      return;
    }
    var obs = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add("r-revealed"); obs.unobserve(e.target); }
      });
    }, { threshold: 0.12, rootMargin: "0px 0px -40px 0px" });
    els.forEach(function (el) { obs.observe(el); });
  }

  /* ── 2. AT/BT interactive slider ── */
  function pad2(n) { return n < 10 ? "0" + n : "" + n; }

  function toAtBt(totalMinutes) {
    var totalHours = Math.floor(totalMinutes / 60);
    var m = totalMinutes % 60;
    var dayOffset = Math.floor(totalHours / 24);
    var hourInDay = ((totalHours % 24) + 24) % 24;
    var period = hourInDay < 12 ? "BT" : "AT";
    var dispH = hourInDay % 12;
    if (dispH === 0) dispH = 12;
    var suffix = dayOffset > 0 ? " (+" + dayOffset + " day" + (dayOffset > 1 ? "s" : "") + ")" : dayOffset < 0 ? " (" + dayOffset + " day)" : "";
    var canonical = pad2(totalHours) + ":" + pad2(m);
    var display = dispH + ":" + pad2(m) + " " + period + suffix;
    return { canonical: canonical, display: display, period: period, dayOffset: dayOffset, totalHours: totalHours, m: m };
  }

  /* ── 2. AT/BT interactive sliders (overview + live demo) ── */
  function initAtBtSlider() {
    // 2a. Overview hero / section slider if present
    var slider   = document.getElementById("r-atbt-slider");
    var outCanon = document.getElementById("r-atbt-out-canon");
    var outDisp  = document.getElementById("r-atbt-out-disp");
    var outPer   = document.getElementById("r-atbt-out-period");
    if (slider && outCanon && outDisp && outPer) {
      var updateOverview = function () {
        var val = parseInt(slider.value, 10);
        var result = toAtBt(val);
        outCanon.textContent = result.canonical;
        outDisp.textContent  = result.display;
        outPer.textContent   = result.period;
        outPer.className     = result.period === "BT" ? "r-atbt-period-badge r-atbt-bt" : "r-atbt-period-badge r-atbt-at";
      };
      slider.addEventListener("input", updateOverview);
      updateOverview();
    }

    // 2b. Live Demo AT/BT interactive demonstration component
    var demoSlider = document.getElementById("demo-atbt-slider");
    var demoCanon  = document.getElementById("demo-atbt-canonical-display");
    var demoDisp   = document.getElementById("demo-atbt-formatted-display");
    var demoPill   = document.getElementById("demo-atbt-period-pill");
    var demoBadge  = document.getElementById("demo-atbt-day-badge");
    var demoMinVal = document.getElementById("demo-atbt-minutes-val");
    var demoCustom = document.getElementById("demo-atbt-custom-input");
    var demoApply  = document.getElementById("demo-atbt-custom-apply");
    var demoSync   = document.getElementById("demo-atbt-sync-btn");

    if (demoSlider && demoCanon && demoDisp) {
      var updateLiveDemo = function (minutes) {
        if (minutes == null) minutes = parseInt(demoSlider.value, 10);
        if (isNaN(minutes)) minutes = 0;
        demoSlider.value = minutes;
        if (demoMinVal) demoMinVal.textContent = minutes + " min (" + Math.floor(minutes / 60) + "h " + (minutes % 60) + "m)";
        var res = toAtBt(minutes);
        demoCanon.textContent = res.canonical;
        demoDisp.textContent  = res.display;
        if (demoPill) {
          demoPill.textContent = res.period === "BT" ? "Before Twelve (BT)" : "After Twelve (AT)";
          demoPill.style.background = res.period === "BT" ? "rgba(0,240,255,0.15)" : "rgba(255,185,95,0.15)";
          demoPill.style.color = res.period === "BT" ? "var(--r-cyan,#00f0ff)" : "var(--r-amber,#ffb95f)";
          demoPill.style.borderColor = res.period === "BT" ? "rgba(0,240,255,0.4)" : "rgba(255,185,95,0.4)";
        }
        if (demoBadge) {
          demoBadge.textContent = res.dayOffset > 0 ? "+" + res.dayOffset + " DAY EXTENDED" : "STANDARD RANGE";
          demoBadge.className = res.dayOffset > 0 ? "badge concept" : "badge live";
        }
      };

      demoSlider.addEventListener("input", function () { updateLiveDemo(); });

      // Presets
      document.querySelectorAll(".demo-atbt-preset").forEach(function (btn) {
        btn.addEventListener("click", function () {
          var m = parseInt(btn.getAttribute("data-min"), 10);
          updateLiveDemo(m);
        });
      });

      // Custom time input
      if (demoApply && demoCustom) {
        demoApply.addEventListener("click", function () {
          var val = demoCustom.value.trim();
          var p = val.split(":");
          if (p.length >= 2) {
            var h = parseInt(p[0], 10), m = parseInt(p[1], 10);
            if (!isNaN(h) && !isNaN(m)) updateLiveDemo(h * 60 + m);
          }
        });
        demoCustom.addEventListener("keydown", function (e) {
          if (e.key === "Enter") demoApply.click();
        });
      }

      // Sync from live dial reading
      if (demoSync) {
        demoSync.addEventListener("click", function () {
          var readingEl = document.querySelector("[data-bind='reading']");
          if (readingEl) {
            var txt = readingEl.textContent.trim();
            var p = txt.split(":");
            if (p.length >= 2) {
              var h = parseInt(p[0], 10), m = parseInt(p[1], 10);
              if (!isNaN(h) && !isNaN(m)) updateLiveDemo(h * 60 + m);
            }
          }
        });
      }

      updateLiveDemo(0);
    }
  }

  /* ── 2c. Send an Idea: navigate directly to Gmail with default recipient ── */
  function initSendAnIdea() {
    document.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-idea]");
      if (btn) {
        e.preventDefault();
        var to = "waqtapi@gmail.com";
        var subject = encodeURIComponent("Waqt Idea / Proposal");
        var body = encodeURIComponent("Assalamu alaykum / Greetings Waqt team,\n\nI would like to share the following idea or proposal for Waqt:\n\n");
        var gmailUrl = "https://mail.google.com/mail/?view=cm&fs=1&to=" + to + "&su=" + subject + "&body=" + body;
        window.open(gmailUrl, "_blank", "noopener,noreferrer");
      }
    });
  }

  /* ── 3. API endpoint expand/collapse ── */
  function initEndpoints() {
    var btns = document.querySelectorAll(".r-endpoint[data-panel]");
    btns.forEach(function (btn) {
      btn.addEventListener("click", function () {
        var id    = btn.getAttribute("data-panel");
        var panel = document.getElementById(id);
        if (!panel) return;
        var open = panel.style.display !== "none" && panel.style.display !== "";
        panel.style.display = open ? "none" : "block";
        btn.setAttribute("aria-expanded", open ? "false" : "true");
      });
    });
  }

  /* ── 4. Live "Now" ticker in hero (if element exists) ── */
  function initHeroTicker() {
    var el = document.getElementById("r-hero-time");
    if (!el) return;
    function tick() {
      var now = new Date();
      var h = now.getUTCHours(), m = now.getUTCMinutes(), s = now.getUTCSeconds();
      el.textContent = pad2(h) + ":" + pad2(m) + ":" + pad2(s) + " UTC";
    }
    function pad2(n) { return n < 10 ? "0" + n : "" + n; }
    tick();
    setInterval(tick, 1000);
  }

  /* ── 5. Section progress indicator ── */
  function initSectionProgress() {
    var bar = document.getElementById("r-progress-bar");
    if (!bar) return;
    function onScroll() {
      var scrolled = window.scrollY;
      var total    = document.body.scrollHeight - window.innerHeight;
      var pct      = total > 0 ? Math.min(100, (scrolled / total) * 100) : 0;
      bar.style.width = pct + "%";
    }
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  }

  /* ── 6. Smooth active nav highlight on scroll ── */
  function initScrollSpy() {
    var sections = document.querySelectorAll("[data-section-id]");
    var navLinks = document.querySelectorAll("#site-nav a[data-section-link]");
    if (!sections.length || !navLinks.length) return;

    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        var id = e.target.getAttribute("data-section-id");
        navLinks.forEach(function (a) {
          if (a.getAttribute("data-section-link") === id) {
            a.style.color = "var(--r-cyan)";
          } else {
            a.style.color = "";
          }
        });
      });
    }, { rootMargin: "-30% 0px -60% 0px" });

    sections.forEach(function (s) { observer.observe(s); });
  }

  /* ── 7. Copy-to-clipboard for code blocks ── */
  function initCopyButtons() {
    var blocks = document.querySelectorAll(".r-terminal-body[data-copy]");
    blocks.forEach(function (block) {
      var btn = document.createElement("button");
      btn.textContent = "Copy";
      btn.className   = "r-badge r-badge-dim";
      btn.style.cssText = "position:absolute;top:10px;right:12px;cursor:pointer;border:none;background:var(--r-bg-4)";
      var wrap = block.closest(".r-terminal");
      if (!wrap) return;
      var bar = wrap.querySelector(".r-terminal-bar");
      if (bar) { bar.style.position = "relative"; bar.appendChild(btn); }
      btn.addEventListener("click", function () {
        navigator.clipboard && navigator.clipboard.writeText(block.textContent.trim()).then(function () {
          btn.textContent = "Copied!";
          setTimeout(function () { btn.textContent = "Copy"; }, 2000);
        });
      });
    });
  }

  /* ── 8. Header background on scroll ── */
  function initHeaderScroll() {
    var header = document.querySelector("header[role='banner']");
    if (!header) return;
    window.addEventListener("scroll", function () {
      if (window.scrollY > 20) {
        header.style.boxShadow = "0 2px 40px rgba(0,0,0,.4), 0 0 0 1px rgba(0,240,255,.05)";
      } else {
        header.style.boxShadow = "";
      }
    }, { passive: true });
  }

  /* ── Init ── */
  document.addEventListener("DOMContentLoaded", function () {
    initReveal();
    initAtBtSlider();
    initSendAnIdea();
    initEndpoints();
    initHeroTicker();
    initSectionProgress();
    initScrollSpy();
    initCopyButtons();
    initHeaderScroll();
  });
}());
