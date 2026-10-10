from pages_common import *

PANEL = "bg-surface-container-low p-6"
MICRO = "font-label-sm text-[11px] tracking-[0.12em] uppercase text-on-surface-variant"
CODE_CURL = '<pre class="code" tabindex="0" aria-label="Example request and response">curl "https://&lt;your-waqt-api&gt;/v1/waqt?lat=9.0192&amp;lon=38.7525"\n\n{ "meta":  { "api_version": "…", "spec": "waqt-core/0.1" },\n  "data":  { "status": "OK",\n             "day":   { "maghrib_open": "…", "maghrib_close": "…", "length_si_seconds": … },\n             "waqt":  { "reading": { "display": "04:22:28", "seconds": … } },\n             "events": [ … ], "next_event": { … }, "hijri": { … } },\n  "error": null }</pre>'

# ============================================================== OVERVIEW
hero = f'''
<section class="relative overflow-hidden" aria-labelledby="h-home">
  <div class="absolute inset-0 opacity-60" aria-hidden="true" style="background-image:linear-gradient(rgba(0,240,255,.05) 1px,transparent 1px),linear-gradient(90deg,rgba(0,240,255,.05) 1px,transparent 1px);background-size:48px 48px;mask-image:linear-gradient(#000 30%,transparent);-webkit-mask-image:linear-gradient(#000 30%,transparent)"></div>
  <div class="relative max-w-[1400px] mx-auto px-4 lg:px-8 pt-16 pb-10 text-center">
    <p class="inline-flex items-center gap-2 border border-outline-variant/60 bg-surface-container-low px-3 py-1 font-label-sm text-[11px] tracking-[0.14em] uppercase text-on-surface-variant"><span class="w-1.5 h-1.5 rounded-full bg-primary-container"></span>Open temporal infrastructure · Maghrib-to-Maghrib civil time</p>
    <h1 id="h-home" class="mt-6 font-headline-xl text-headline-xl-mobile md:text-headline-xl max-w-4xl mx-auto">Islamic Time Infrastructure for the Open Web</h1>
    <p class="mt-5 text-body-lg text-on-surface-variant max-w-2xl mx-auto">Waqt is an open technical standard and API for computing, representing and interoperating with Islamic time — Maghrib-based day boundaries, astronomical events, Hijri dates and scheduling.</p>
    <div class="mt-8 flex flex-wrap justify-center gap-3">
      <a href="live-demo.html" class="inline-flex items-center gap-2 px-5 py-3 bg-primary-container text-on-primary font-label-md text-[12px] uppercase tracking-wider hover:brightness-110">Try Waqt {icon("arrow_forward")}</a>
      <a data-cfg="docs.spec" href="resources.html" class="inline-flex items-center gap-2 px-5 py-3 border border-outline-variant text-on-surface font-label-md text-[12px] uppercase tracking-wider hover:bg-surface-container-high">{icon("description")}Read the specification</a>
    </div>
  </div>
  <div class="relative max-w-[1400px] mx-auto px-4 lg:px-8 pb-16">
    <div class="border border-outline-variant/50 bg-surface-container-lowest" id="home-live">
      <div class="flex flex-wrap items-center justify-between gap-2 px-4 py-2 border-b border-outline-variant/40 font-label-sm text-[11px] text-on-surface-variant">
        <span class="flex items-center gap-2"><span class="w-2 h-2 rounded-full bg-secondary"></span><span class="w-2 h-2 rounded-full bg-tertiary"></span><span class="w-2 h-2 rounded-full bg-primary-container"></span><span class="ml-2 tracking-wider">WAQT-VIEWPORT // LIVE CLOCK</span></span>
        <span class="flex flex-wrap gap-x-4 gap-y-1">ENGINE <b class="text-on-surface" data-bind="engine">—</b> <span>ACCURACY <b class="text-on-surface" data-bind="accuracy">—</b></span> <b data-bind="state" data-bind-state class="tracking-wider">LOADING</b></span>
      </div>
      <div class="grid lg:grid-cols-[1.15fr_1fr]">
        <div class="relative min-h-[260px] lg:min-h-[480px]">{img("hero-astronomy", "Concept render: observatory-style celestial grid over a desert horizon at dusk", ratio="absolute inset-0", eager=True)}
          <div class="absolute left-4 top-4 bg-background/80 border border-outline-variant/50 p-3 font-label-sm text-[11px] w-56 hidden sm:block">
            <div class="text-secondary tracking-wider mb-1">OBSERVER HORIZON</div>
            {kv("LATITUDE", "lat")}{kv("LONGITUDE", "lon")}{kv("TIMEZONE", "tz")}{kv("ELEVATION", "elevation")}</div></div>
        <div class="p-5 md:p-8 flex flex-col justify-center gap-4"><div id="home-banner"></div><div id="home-clock"></div></div>
      </div>
      <div class="grid grid-cols-2 md:grid-cols-5 gap-px bg-outline-variant/30 font-label-sm text-[11px] text-center text-on-surface-variant">
        <div class="bg-surface-container-low px-3 py-3"><span class="text-secondary">T₀</span> MAGHRIB (opens)</div><div class="bg-surface-container-low px-3 py-3">[T₀, T₁) WAQT DAY</div>
        <div class="bg-surface-container-low px-3 py-3">SOLAR EVENTS ON THE DAY</div><div class="bg-surface-container-low px-3 py-3"><span class="text-secondary">T₁</span> NEXT MAGHRIB</div><div class="bg-surface-container-low px-3 py-3 col-span-2 md:col-span-1">HALF-OPEN INTERVAL</div>
      </div>
    </div>
    <p class="mt-3 text-[12px] text-on-surface-variant font-label-sm">Every value in this viewport comes from the Waqt API. If the API cannot be reached the viewport switches to a recorded, frozen sample and says so on the face of the clock.</p>
  </div>
</section>'''

arc = '''<svg viewBox="0 0 260 120" role="img" aria-label="Diagram: the day is the interval from one Maghrib to the next, with the solar transit between them" class="w-full"><path d="M16 86 Q130 -34 244 86" fill="none" stroke="#00f0ff" stroke-width="2"/><line x1="10" y1="86" x2="250" y2="86" stroke="#ffb95f" stroke-dasharray="3 4" opacity=".6"/><circle cx="16" cy="86" r="5" fill="#ffb95f"/><circle cx="244" cy="86" r="5" fill="#ffb95f"/><circle cx="130" cy="26" r="4" fill="#00f0ff"/><g font-family="JetBrains Mono,monospace" font-size="9" fill="#b9cacb"><text x="4" y="106">Maghrib(L, D)</text><text x="256" y="106" text-anchor="end">Maghrib(L, D+1)</text><text x="130" y="14" text-anchor="middle">solar transit (Dhuhr)</text></g></svg>'''

f1 = f'''
<div class="grid md:grid-cols-3 gap-6">
  {card(f'<div class="flex justify-between {MICRO}"><span>01 // Interval model</span><span class="text-secondary">continuous</span></div><h3 class="mt-4 font-headline-sm text-[16px] uppercase tracking-wide">One temporal model</h3><p class="mt-2 text-body-md text-on-surface-variant">A Waqt day begins at local sunset (Maghrib) and ends at the next one. The reading is ordinary SI time elapsed since Maghrib, so an hour is always 60 minutes.</p><div class="mt-5 bg-surface-container-lowest p-4">{arc}<p class="mt-2 text-center font-label-sm text-[11px] bg-surface-container px-2 py-1">[Maghrib(L, D), Maghrib(L, D+1))</p></div>')}
  {card(f'<div class="flex justify-between {MICRO}"><span>02 // Conventions</span><span class="text-secondary">parameters</span></div><h3 class="mt-4 font-headline-sm text-[16px] uppercase tracking-wide">Configurable, never hidden</h3><p class="mt-2 text-body-md text-on-surface-variant">Astronomy and the day boundary are fixed. Conventions are explicit request parameters, and changing one moves only the event it governs.</p><div class="mt-5 bg-surface-container-lowest p-4 font-label-sm text-[12px] space-y-2"><div class="flex justify-between"><span class="text-on-surface-variant">fajr_angle</span><span>18.0° default</span></div><div class="flex justify-between"><span class="text-on-surface-variant">isha_angle</span><span>17.0° default</span></div><div class="flex justify-between"><span class="text-on-surface-variant">asr_ratio</span><span>1.0 · 2.0 (Hanafi)</span></div><div class="flex justify-between gap-3"><span class="text-on-surface-variant">calendar_provider</span><span class="text-right">umm-al-qura (default)</span></div><p class="pt-2 text-[11px] text-on-surface-variant">Providers are listed by <code>GET /v1/calendar</code>.</p></div>')}
  {card(f'<div class="flex justify-between {MICRO}"><span>03 // Clients</span><span class="text-secondary">one contract</span></div><h3 class="mt-4 font-headline-sm text-[16px] uppercase tracking-wide">One envelope, many clients</h3><p class="mt-2 text-body-md text-on-surface-variant">Every response is the same documented envelope. The web viewer, CLI and the Python and JavaScript client libraries read it; none recompute it.</p><div class="mt-5 bg-surface-container-lowest p-4 font-label-sm text-[12px]"><div class="grid grid-cols-4 gap-2 text-center text-on-surface-variant mb-4"><span>{icon("language")}<br>Web</span><span>{icon("terminal")}<br>CLI</span><span>{icon("code")}<br>Python</span><span>{icon("data_object")}<br>JS</span></div><div class="bg-surface-container p-3 text-primary-container">{{ meta, data, error }}</div></div>')}
</div>'''

live = f'''
<div class="grid lg:grid-cols-[1.1fr_1fr] gap-6" id="home-coord">
  <div class="{PANEL}">
    <div class="flex justify-between items-center {MICRO}"><span>Waqt coordinate · right now</span><b data-bind="state" data-bind-state>LOADING</b></div>
    <div class="mt-5 mono text-[56px] md:text-[72px] leading-none text-on-surface" data-bind="reading">––:––:––</div>
    <div class="mt-2 font-label-sm text-[13px] text-on-surface-variant">T₀ + <span data-bind="readingSeconds" class="text-primary-container">—</span> since Maghrib opened</div>
    <div class="mt-6" id="home-day"></div>
  </div>
  <div class="{PANEL}">
    <div class="{MICRO} mb-3">Telemetry</div>
    {kv("Maghrib opened", "open")}{kv("Next Maghrib", "close")}{kv("Day length", "length")}{kv("Next event", "next", False)}{kv("Countdown", "countdown")}{kv("Hijri date", "hijri", False)}{kv("Hijri provider", "provider", False)}{kv("Weekday", "weekday", False)}{kv("Engine", "engine")}{kv("ΔT", "deltaT")}{kv("Timescale", "timescale")}{kv("Last request", "latency")}
    <p class="mt-4 text-[12px] text-on-surface-variant">A Waqt day is not 24 hours; the length above is measured, not assumed.</p><p class="mt-2 text-[12px] text-on-surface-variant" data-bind="hijriNote"></p>
  </div>
</div>'''

def eco_card(image, title, kind, text, foot, tall=False):
    return f'''<article class="bg-surface-container-low flex flex-col">{img(image, title + " (concept art)", ratio="aspect-[4/3]")}<div class="p-5 flex flex-col gap-2 flex-1"><div class="flex justify-between items-start gap-2"><h3 class="font-headline-sm text-[16px]">{title}</h3>{badge(kind)}</div><p class="text-body-md text-on-surface-variant">{text}</p><p class="mt-auto pt-2 font-label-sm text-[11px] text-on-surface-variant">{foot}</p></div></article>'''

eco = f'''
<div class="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
  {eco_card("mosque-wall-clock", "Mosque Waqt clock", "concept", "A wall display with the Waqt reading, the next event and the Maghrib boundary.", "Data: /v1/waqt · no device deployed")}
  {eco_card("smartwatch", "Waqt smartwatch", "concept", "The same event timeline on a wrist, drawn from the same response as the web clock.", "Data: /v1/waqt · no watch app exists")}
  {eco_card("mobile-app", "Waqt mobile app", "concept", "A phone-first day ring, next event and Hijri date.", "Data: /v1/waqt · no mobile app published")}
  {eco_card("institutional-calendar", "Institutional calendars", "concept", "Islamic week, fiscal and academic years for schools, offices and mosques.", "Backend: /v1/institutional/* exist · no calendar product")}
  {eco_card("developer-api", "Developer tooling", "real", "The HTTP API, an offline CLI, the reference viewer and Python/JS client libraries exist today.", "See API and Resources")}
  <article class="bg-surface-container-low p-6 flex flex-col justify-center gap-3"><p class="{MICRO}">All applications</p><p class="text-body-md text-on-surface-variant">Ten applications, each labelled REAL, CONCEPT or FUTURE — plus five interactive demonstrations in the Experience Lab.</p><a class="inline-flex items-center gap-2 text-primary-container font-label-md text-[12px] uppercase tracking-wider hover:underline" href="applications.html">See applications {icon("arrow_forward")}</a><a class="inline-flex items-center gap-2 text-primary-container font-label-md text-[12px] uppercase tracking-wider hover:underline" href="lab.html">Open the Experience Lab {icon("arrow_forward")}</a></article>
</div>'''

arch = f'''
<div class="grid lg:grid-cols-2 gap-8 items-center">
  {img("api-ecosystem", "Concept render: devices connected to a central Waqt clock")}
  <div>{CODE_CURL}<div class="mt-4 flex flex-wrap gap-3"><a class="inline-flex items-center gap-2 px-4 py-2 bg-primary-container text-on-primary font-label-md text-[12px] uppercase tracking-wider" href="api.html">API reference {icon("arrow_forward")}</a><a class="inline-flex items-center gap-2 px-4 py-2 border border-outline-variant font-label-md text-[12px] uppercase tracking-wider hover:bg-surface-container-high" href="lab.html#build">Build an application</a></div></div>
</div>'''

idea = f'''<div class="bg-surface-container-low border border-outline-variant/40 p-8 md:p-10 grid md:grid-cols-[1fr_auto] gap-6 items-center">
  <div>{eyebrow("Have an idea?")}<h2 class="font-headline-lg text-headline-lg-mobile md:text-headline-lg">Help shape Waqt.</h2><p class="mt-3 text-body-md text-on-surface-variant max-w-2xl">Project ideas, proposals, contribution requests, or a question — write to <a data-email class="text-primary-container hover:underline" href="mailto:waqtapi@gmail.com">waqtapi@gmail.com</a>. Qualified experts and contributors are welcome.</p></div>
  <a data-idea href="mailto:waqtapi@gmail.com" class="inline-flex items-center gap-2 px-6 py-3 bg-primary-container text-on-primary font-label-md text-[12px] uppercase tracking-wider hover:brightness-110">{icon("mail")}Send an Idea</a></div>'''

home = hero + wrap(h2("Time is more than a timestamp.", "A single coordinate frame replacing fragmented calculators, static timetables and midnight-based assumptions.", "Foundational formalisation") + f1, labelled="") \
    + wrap(h2("The Waqt temporal coordinate", "Where you are in the Maghrib-to-Maghrib day, live.", "Live data") + live) \
    + wrap(h2("What happens when Islamic time becomes infrastructure?", "Most of these are design concepts. The infrastructure under them is real.", "Ecosystem") + eco) \
    + wrap(h2("One temporal infrastructure. Many experiences.", "", "Build with it") + arch) + wrap(idea)
page("index.html", "Overview", "Waqt: open Maghrib-to-Maghrib civil time and Hijri calendar API — Islamic time infrastructure for the open web.", "overview", home, LIVE, ["pages/home"])

# ============================================================== THE PROBLEM
ph = wrap(f'''<p class="inline-flex border border-outline-variant/60 bg-surface-container-low px-3 py-1 font-label-sm text-[11px] tracking-[0.14em] uppercase text-on-surface-variant">The problem</p>
<h1 class="mt-5 font-headline-xl text-headline-xl-mobile md:text-headline-xl max-w-4xl">Islamic time is widely computed, but rarely interoperable.</h1>
<p class="mt-5 text-body-lg text-on-surface-variant max-w-3xl">Prayer-time apps, Hijri calendars and institutional schedules each define the day, the date and the events a little differently. There is no shared, testable, language-independent contract to build against — so every product rebuilds it.</p>''', border=False, cls="pt-16 pb-10")
boundary = f'''<div id="problem-live"><div id="problem-banner" class="mb-4"></div><div id="problem-compare"></div></div>
<div class="mt-10 grid md:grid-cols-2 gap-6">
  <div class="{PANEL} border-l-2 border-outline-variant"><p class="{MICRO}">Midnight-based software</p><ul class="mt-3 space-y-2 text-body-md text-on-surface-variant list-disc pl-5"><li>The date changes at 00:00 local time.</li><li>A day is assumed to be exactly 24 hours.</li><li>The evening after sunset still belongs to the previous weekday.</li></ul></div>
  <div class="{PANEL} border-l-2 border-primary-container"><p class="{MICRO} text-primary-container">Waqt</p><ul class="mt-3 space-y-2 text-body-md text-on-surface-variant list-disc pl-5"><li>The day opens at Maghrib at the observer’s location.</li><li>Its length is whatever the API measures — it varies by place and season.</li><li>The weekday changes at Maghrib, so Friday’s evening before dawn is already Friday.</li></ul></div>
</div>
<div class="mt-8 grid lg:grid-cols-2 gap-8 items-center">{img("vs-midnight", "Concept render comparing a midnight-based clock with a Maghrib-based Waqt clock")}<div><p class="{MICRO}">Measured now</p><div id="problem-day" class="mt-2"></div></div></div>'''

def frag(n, title, text, tone="text-on_surface"):
    return card(f'<p class="{MICRO}">{n} // fragmentation</p><h3 class="mt-3 font-headline-sm text-[16px] uppercase tracking-wide">{title}</h3><p class="mt-2 text-body-md text-on-surface-variant">{text}</p>')

fm = f'''<div class="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
{frag("01", "Different day boundaries", "Some software rolls the day at midnight, some at sunset, some at a fixed clock time — and rarely says which.")}
{frag("02", "Different angle conventions", "Fajr and Isha are defined by sun depression angles that differ between authorities (Fajr angles in common use span roughly 15° to 19.5°). Waqt makes them explicit parameters.")}
{frag("03", "Different calendars", "Arithmetic and observation-based Hijri calendars can start a month on different days. Waqt names the provider in every response and never lets the calendar influence solar astronomy.")}
{frag("04", "Calendar tooling can’t express it", "Standard recurrence rules have no primitive for “30 minutes before Maghrib”. Waqt’s scheduling endpoints resolve such rules against the real day.")}
{frag("05", "Silent approximation at the edges", "Where the sun does not set, many tools quietly substitute an invented time. Waqt returns an explicit UNDEFINED with the reason, and applies no automatic fallback.")}
{frag("06", "No machine-checkable standard", "Without shared test vectors two implementations cannot prove they agree. Waqt ships a portable conformance contract (2.0.0, draft) with an independent implementation checked against it.")}
</div>'''

ba = f'''<div class="grid md:grid-cols-2 gap-6">
<div class="{PANEL}"><p class="{MICRO} text-error">Without a shared standard</p><ul class="mt-3 space-y-2 text-body-md text-on-surface-variant list-disc pl-5"><li>Each product re-implements astronomy, calendars and rollover.</li><li>Two apps disagree and nobody can say which is right.</li><li>Edge cases are guessed, silently.</li></ul></div>
<div class="{PANEL}"><p class="{MICRO} text-primary-container">With Waqt</p><ul class="mt-3 space-y-2 text-body-md text-on-surface-variant list-disc pl-5"><li>Applications consume one documented contract and display it.</li><li>Conventions are parameters; provenance travels in the response.</li><li>Undefined cases are explicit, and conformance is testable.</li></ul></div></div>
<div class="mt-8 flex flex-wrap gap-3"><a class="inline-flex items-center gap-2 px-5 py-3 bg-primary-container text-on-primary font-label-md text-[12px] uppercase tracking-wider" href="how-it-works.html">How it works {icon("arrow_forward")}</a><a class="inline-flex items-center gap-2 px-5 py-3 border border-outline-variant font-label-md text-[12px] uppercase tracking-wider hover:bg-surface-container-high" href="live-demo.html">See it live</a></div>'''
problem = ph + wrap(h2("The irreconcilable boundary problem", "The same events, the same moment — two different notions of “the day”.", "Boundary", hid="h-boundary") + boundary) \
    + wrap(h2("The fragmentation matrix", "Six ways Islamic time breaks between systems.", "Fragmentation") + fm) \
    + wrap(h2("Before and after standardisation", "", "Outcome") + ba)
page("problem.html", "The Problem", "Why Islamic time is widely computed but rarely interoperable: day boundaries, conventions, calendars and edge cases.", "problem", problem, LIVE, ["pages/problem"])

# ============================================================== HOW IT WORKS
hh = wrap(f'''<p class="inline-flex border border-outline-variant/60 bg-surface-container-low px-3 py-1 font-label-sm text-[11px] tracking-[0.14em] uppercase text-on-surface-variant">How it works</p>
<h1 class="mt-5 font-headline-xl text-headline-xl-mobile md:text-headline-xl max-w-4xl">How Waqt computes time across continuous solar horizons.</h1>
<p class="mt-5 text-body-lg text-on-surface-variant max-w-3xl">A location and an instant go in. A day boundary, a reading, the day’s events and a Hijri date come out — each computed once, by the API, and returned in one envelope.</p>''', border=False, cls="pt-16 pb-10")
model = f'''<div class="grid lg:grid-cols-[1fr_1fr] gap-6">
  <div class="{PANEL}"><p class="{MICRO}">Formal definition</p>
    <dl class="mt-4 space-y-4 text-body-md">
      <div><dt class="font-label-md text-[12px] text-primary-container">DAY</dt><dd class="text-on-surface-variant">Day(L, D) = [ Maghrib(L, D) , Maghrib(L, D+1) ) — half-open, so every instant belongs to exactly one day.</dd></div>
      <div><dt class="font-label-md text-[12px] text-primary-container">READING</dt><dd class="text-on-surface-variant">reading(t) = t − Maghrib(L, D), in SI seconds. Hours are 60 minutes; the reading resets at the next Maghrib.</dd></div>
      <div><dt class="font-label-md text-[12px] text-primary-container">LENGTH</dt><dd class="text-on-surface-variant">The day’s length is measured from the two boundaries. It is not assumed to be 24 hours and can differ by place and season.</dd></div>
      <div><dt class="font-label-md text-[12px] text-primary-container">EVENTS</dt><dd class="text-on-surface-variant">Fajr, sunrise, Dhuhr, Asr, Maghrib and Isha are instants, each also given as a reading on the day. An event after the closing Maghrib reads past the day length (Isha usually does).</dd></div>
    </dl></div>
  <div class="{PANEL}" id="how-live"><div id="how-banner" class="mb-3"></div><div class="flex justify-between {MICRO}"><span>Live day measurement</span><b data-bind="state" data-bind-state>LOADING</b></div><div class="mt-3" id="how-day"></div>
    <div class="mt-2">{kv("Reading", "reading")}{kv("Maghrib opened", "open")}{kv("Next Maghrib", "close")}{kv("Length (API)", "lengthSeconds")}</div></div>
</div>'''
acc = f'''<div class="grid md:grid-cols-2 gap-6">
  <div class="{PANEL}"><p class="{MICRO}">Production engine</p><div class="mt-3">{kv("Engine", "engine")}{kv("Accuracy level", "accuracy")}{kv("ΔT now", "deltaT")}{kv("Timescale model", "timescale")}</div>
    <p class="mt-4 text-body-md text-on-surface-variant">The production engine is a NOAA-style low-precision solar model, accuracy <b class="text-on-surface">level B</b>. Level A (sub-10-second against a high-precision ephemeris) is <b class="text-on-surface">not claimed</b>.</p></div>
  <div class="{PANEL}"><p class="{MICRO}">Independent verification</p><p class="mt-3 text-body-md text-on-surface-variant">The project verifies its engine against separate references — a VSOP87-based solar model and an independent JPL DE421 + Skyfield reference. In the project’s own measurements the engine agrees to about a second at low and mid latitudes; in a five-date high-latitude check the error reached 9.3 seconds (see <code>docs/ASTRONOMY.md</code>).</p>
    <p class="mt-3 text-body-md text-on-surface-variant">That is good for a wall display, a timetable or a scheduler; it is not yet verified for legal or liturgical use without independent confirmation.</p></div>
</div>'''
latitude = f'''<div class="grid lg:grid-cols-2 gap-6 items-start">
  <div class="{PANEL}"><p class="{MICRO}">When the sun does not set</p><p class="mt-3 text-body-md text-on-surface-variant">Near the poles around the solstices Maghrib does not occur. Waqt does not invent a time: the response is <code>status: "UNDEFINED"</code> with the reason, and no high-latitude fallback is applied automatically. Choosing a fallback is a human, jurisdictional decision.</p>
    <div class="mt-5 field-row"><div class="field"><label for="probe-case">Probe</label><select id="probe-case"><option value="69.6492,18.9553,2026-06-21T12:00:00Z">Tromsø, 21 June 2026</option><option value="69.6492,18.9553,2026-10-07T12:00:00Z">Tromsø, 7 October 2026</option><option value="21.4225,39.8262,2026-06-21T12:00:00Z">Makkah, 21 June 2026</option></select></div><button id="probe-go" class="btn" type="button">Ask the API</button></div></div>
  <div class="{PANEL}"><p class="{MICRO}">Response</p><div id="probe-out" class="mt-3 text-body-md text-on-surface-variant" role="status" aria-live="polite">Choose a probe and ask the API.</div></div>
</div>'''
pipe = '''<ol class="grid md:grid-cols-5 gap-px bg-outline-variant/30 list-none p-0 m-0" aria-label="Request pipeline">
  <li class="bg-surface-container-low p-5"><p class="font-label-sm text-[11px] text-secondary">01</p><b class="block mt-1 font-headline-sm text-[15px]">Request</b><span class="text-[13px] text-on-surface-variant">lat, lon and optionally an instant and conventions.</span></li>
  <li class="bg-surface-container-low p-5"><p class="font-label-sm text-[11px] text-secondary">02</p><b class="block mt-1 font-headline-sm text-[15px]">Place &amp; timezone</b><span class="text-[13px] text-on-surface-variant">Timezone and local civil date are resolved.</span></li>
  <li class="bg-surface-container-low p-5"><p class="font-label-sm text-[11px] text-secondary">03</p><b class="block mt-1 font-headline-sm text-[15px]">Astronomy</b><span class="text-[13px] text-on-surface-variant">Solar position in Terrestrial Time gives sunset, sunrise, transit and the angle events.</span></li>
  <li class="bg-surface-container-low p-5"><p class="font-label-sm text-[11px] text-secondary">04</p><b class="block mt-1 font-headline-sm text-[15px]">Day &amp; events</b><span class="text-[13px] text-on-surface-variant">Maghrib-to-Maghrib day, reading, events and the next event.</span></li>
  <li class="bg-surface-container-low p-5"><p class="font-label-sm text-[11px] text-secondary">05</p><b class="block mt-1 font-headline-sm text-[15px]">Calendar &amp; envelope</b><span class="text-[13px] text-on-surface-variant">A named Hijri provider adds the date; everything returns in <code>{meta, data, error}</code>.</span></li></ol>'''
inv = f'''<p class="text-body-md text-on-surface-variant max-w-3xl mb-6">Change the Fajr angle and ask the API again. Fajr moves; the Maghrib boundaries do not — because conventions govern only their own event.</p>
<div class="{PANEL}"><div class="field-row"><div class="field"><label for="inv-angle">Fajr angle (degrees below horizon)</label><select id="inv-angle"><option>15</option><option>16</option><option>17</option><option selected>18</option><option>19</option><option>19.5</option></select></div><button id="inv-go" class="btn" type="button">Ask the API</button></div>
<div id="inv-status" class="mt-3 text-[13px] text-on-surface-variant" role="status"></div>
<div class="table-scroll mt-3"><table class="data" id="inv-table" hidden><caption class="vh">Fajr angle versus event readings</caption><thead><tr><th scope="col">Fajr angle</th><th scope="col">Fajr (local)</th><th scope="col">Fajr reading</th><th scope="col">Maghrib opens</th><th scope="col">Next Maghrib</th></tr></thead><tbody id="inv-rows"></tbody></table></div></div>'''
how = hh + wrap(h2("The continuous timeline", "", "Model", hid="h-model") + model) + wrap(h2("Astronomy and honest accuracy", "", "Engine") + acc) \
    + wrap(h2("Determinacy at extreme latitudes", "", "Edge cases") + latitude) + wrap(h2("The end-to-end pipeline", "", "Pipeline") + pipe) \
    + wrap(h2("Convention invariance, live", "", "Method") + inv)
page("how-it-works.html", "How It Works", "How Waqt computes the Maghrib-to-Maghrib day: the model, the engine and its accuracy, extreme latitudes, and the request pipeline.", "how", how, LIVE, ["pages/how"])
