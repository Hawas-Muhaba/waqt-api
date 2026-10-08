"""Shared chrome and helpers for tools/build_pages.py.

The deployed site is static HTML. This generator exists only so the header/footer (identical on every page) are not
hand-copied eleven times; the generated .html files are committed, and tests/test_site_structure.py fails if the
navigation ever drifts. Run:  python3 tools/build_pages.py  &&  npm run build:css   (from apps/web/tools)."""
from __future__ import annotations
import html
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.dirname(HERE)
ICON_DIR = os.path.join(HERE, "node_modules", "@material-design-icons", "svg", "outlined")
_icon_cache: dict[str, str] = {}


def icon(name: str, cls: str = "") -> str:
    """Inline a Material icon (Apache-2.0) as <svg>; no icon font, no network."""
    if name not in _icon_cache:
        p = os.path.join(ICON_DIR, name + ".svg")
        if not os.path.exists(p):
            raise SystemExit(f"unknown icon {name!r}")
        svg = open(p, encoding="utf-8").read().strip()
        _icon_cache[name] = re.sub(r"<svg ", '<svg aria-hidden="true" focusable="false" ', svg, 1)
    s = _icon_cache[name]
    return s.replace('<svg ', f'<svg class="ic {cls}" ', 1)


NAV = [
    ("overview", "Overview", "index.html"),
    ("problem", "The Problem", "problem.html"),
    ("how", "How It Works", "how-it-works.html"),
    ("demo", "Live Demo", "live-demo.html"),
    ("api", "API", "api.html"),
    ("apps", "Applications", "applications.html"),
    ("gov", "Governance", "governance.html"),
    ("community", "Community", "community.html"),
]
LINK = "px-3 py-2 text-[13px] font-label-lg text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high rounded-sm whitespace-nowrap aria-[current=page]:bg-surface-container-high aria-[current=page]:text-primary-container"


def header() -> str:
    lis = []
    for key, label, href in NAV:
        lis.append(f'<li><a href="{href}" data-nav="{key}" class="{LINK} block">{label}</a></li>')
    lis.append(f'<li class="lg:ml-2"><a data-link="github" href="#" class="{LINK} flex items-center gap-2 border border-outline-variant">{icon("code")}GitHub</a></li>')
    lis.append('<li><a data-link="docs" href="resources.html#specifications" class="flex items-center gap-2 px-3 py-2 text-[12px] font-label-md uppercase tracking-wider bg-primary-container text-on-primary rounded-sm hover:brightness-110 whitespace-nowrap">'
               f'{icon("description")}Read Spec / Docs</a></li>')
    items = "\n        ".join(lis)
    return f'''<a class="skip" href="#main">Skip to content</a>
<header class="fixed top-0 inset-x-0 z-50 h-16 bg-background/90 backdrop-blur border-b border-outline-variant/50" role="banner">
  <div class="max-w-[1400px] mx-auto h-full flex items-center gap-4 px-4 lg:px-8">
    <a href="index.html" class="flex items-center gap-3 mr-auto" aria-label="Waqt — home">
      <span class="relative grid place-items-center w-9 h-9 border border-primary-container/60 rounded-full" aria-hidden="true"><span class="w-3 h-3 rounded-full bg-primary-container"></span></span>
      <span class="leading-none"><span class="block font-headline-md text-[18px] tracking-wide text-on-surface">WAQT</span><span class="block font-label-sm text-[10px] tracking-[0.2em] text-on-surface-variant uppercase">Time API</span></span>
    </a>
    <button class="nav-toggle items-center gap-2 border border-outline-variant px-3 py-2 font-label-md text-[12px] uppercase tracking-wider text-on-surface" type="button" aria-expanded="false" aria-controls="site-nav">Menu</button>
    <nav aria-label="Primary" class="contents">
      <ul id="site-nav" class="nav-list flex flex-wrap items-center gap-1 list-none m-0 p-0">
        {items}
      </ul>
    </nav>
  </div>
</header>'''


def col(title: str, links: list[str]) -> str:
    lis = "".join(f'<li>{l}</li>' for l in links)
    return f'<div><h2 class="font-label-md text-[11px] tracking-[0.14em] text-on-surface uppercase mb-4">{title}</h2><ul class="space-y-2 text-[13px] text-on-surface-variant">{lis}</ul></div>'


FA = 'class="hover:text-primary-container"'
FOOTER = f'''<footer class="mt-24 border-t border-outline-variant/50 bg-surface-container-lowest">
  <div class="max-w-[1400px] mx-auto px-4 lg:px-8 py-12">
    <div class="grid gap-10 sm:grid-cols-2 lg:grid-cols-6">
      <div class="lg:col-span-2">
        <div class="font-headline-md text-[18px] tracking-wide mb-3">WAQT</div>
        <p class="text-[13px] text-on-surface-variant max-w-sm">A Makkah-anchored, Maghrib-to-Maghrib civil time and Hijri calendar API. Open temporal infrastructure — it provides temporal facts, not religious rulings.</p>
        <p class="mt-4 text-[12px] text-on-surface-variant font-label-sm">Applications are labelled <span class="badge real">REAL</span> <span class="badge concept">CONCEPT</span> <span class="badge future">FUTURE</span></p>
      </div>
      {col("Platform", [f'<a {FA} href="index.html">Overview</a>', f'<a {FA} href="problem.html">The problem</a>', f'<a {FA} href="how-it-works.html">How it works</a>', f'<a {FA} href="live-demo.html">Live demo</a>', f'<a {FA} href="lab.html">Experience Lab</a>'])}
      {col("Developers", [f'<a {FA} href="api.html">API reference</a>', f'<a {FA} data-api-docs href="#">Interactive API docs</a>', f'<a {FA} href="resources.html#sdks">SDKs</a>', f'<a {FA} href="resources.html#conformance">Conformance</a>', f'<a {FA} href="reference-viewer.html">Reference viewer</a>'])}
      {col("Project", [f'<a {FA} href="applications.html">Applications</a>', f'<a {FA} href="governance.html">Governance</a>', f'<a {FA} href="community.html">Community</a>', f'<a {FA} href="resources.html">Resources</a>', f'<a {FA} data-link="github" href="#">GitHub</a>'])}
      <div>
        <h2 class="font-label-md text-[11px] tracking-[0.14em] text-on-surface uppercase mb-4">Support Waqt</h2>
        <div class="border border-outline-variant/60 p-4 bg-surface-container-low">
          <p class="text-[12px] text-on-surface-variant mb-3">Open work, kept going by contributors. Entirely optional.</p>
          <a data-link="buyMeACoffee" href="#" class="inline-flex items-center gap-2 px-3 py-2 text-[12px] font-label-md uppercase tracking-wider border border-secondary text-secondary hover:bg-secondary/10">☕️ Buy Me a Coffee</a>
        </div>
        <h2 class="font-label-md text-[11px] tracking-[0.14em] text-on-surface uppercase mt-6 mb-2">Contact</h2>
        <a data-email class="text-[13px] text-primary-container hover:underline" href="mailto:waqtapi@gmail.com">waqtapi@gmail.com</a>
      </div>
    </div>
    <div class="mt-10 pt-6 border-t border-outline-variant/40 flex flex-wrap gap-x-8 gap-y-2 justify-between text-[11px] font-label-sm text-on-surface-variant">
      <span>© Waqt project contributors · MIT License</span>
      <span>Idea / Logical Owner: Dr. Salim Muhammed Redi · Technical Developer / Maintainer: Mr. Hawas Muhaba Hussein</span>
      <span>Concept images are design renders, not photographs of deployed products.</span>
    </div>
  </div>
</footer>'''

CORE = ["config", "waqt-api"]
LIVE = CORE + ["demo-data", "waqt-live", "waqt-clock", "waqt-widgets"]


def page(fname: str, title: str, desc: str, current: str, body: str, scripts: list[str], extra: list[str] = ()) -> None:
    tags = "\n".join(f'<script defer src="assets/js/{s}.js"></script>' for s in list(scripts) + ["site"] + list(extra))
    out = f'''<!doctype html>
<html lang="en" class="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} — Waqt</title>
<meta name="description" content="{html.escape(desc)}">
<meta name="theme-color" content="#10131b">
<link rel="icon" href="data:,">
<link rel="preload" href="assets/fonts/inter-latin-wght-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="assets/css/stitch.css">
<link rel="stylesheet" href="assets/css/components.css">
</head>
<body class="bg-background text-on-surface font-body-md antialiased min-h-screen pt-16">
{header().replace(f'data-nav="{current}"', f'data-nav="{current}" aria-current="page"') if current else header()}
<main id="main">
{body}
</main>
{FOOTER}
{tags}
</body>
</html>
'''
    with open(os.path.join(WEB, fname), "w", encoding="utf-8") as f:
        f.write(out)
    print("wrote", fname, len(out))


# ---------------------------------------------------------------- Stitch-style building blocks
def img(name: str, alt: str, ratio: str = "aspect-video", eager: bool = False, extra: str = "") -> str:
    w, h = (900, 1117) if name in ("mobile-app", "smartwatch") else ((900, 900) if name == "circular-clock" else (1280, 714))
    load = "" if eager else ' loading="lazy" decoding="async"'
    pos = "" if "absolute" in ratio else "relative"
    return (f'<div class="{pos} overflow-hidden bg-surface-container {ratio} {extra}"><img class="w-full h-full object-cover" src="assets/img/{name}.webp" '
            f'width="{w}" height="{h}" alt="{html.escape(alt)}"{load}><span class="art-tag">Concept art</span></div>')


def eyebrow(text: str, tone: str = "text-primary-container") -> str:
    return f'<p class="font-label-sm text-[11px] tracking-[0.18em] uppercase {tone} mb-3">{text}</p>'


def h2(text: str, sub: str = "", eyebrow_text: str = "", hid: str = "") -> str:
    idattr = f' id="{hid}"' if hid else ""
    return (f'<div class="mb-10">{eyebrow(eyebrow_text) if eyebrow_text else ""}<h2{idattr} class="font-headline-lg text-headline-lg-mobile md:text-headline-lg">{text}</h2>'
            f'{f"<p class=\"mt-3 text-body-md text-on-surface-variant max-w-3xl\">{sub}</p>" if sub else ""}</div>')


def badge(kind: str) -> str:
    return f'<span class="badge {kind.lower()}">{kind.upper()}</span>'


def kv(label: str, bind: str, mono: bool = True) -> str:
    return (f'<div class="flex justify-between gap-4 py-1.5 border-b border-outline-variant/30 font-label-sm text-[12px]"><span class="text-on-surface-variant">{label}</span>'
            f'<span data-bind="{bind}" class="text-on-surface text-right {"mono" if mono else ""}">—</span></div>')


def wrap(inner: str, cls: str = "py-16 md:py-20", border: bool = True, sid: str = "", labelled: str = "") -> str:
    a = f' id="{sid}"' if sid else ""
    l = f' aria-labelledby="{labelled}"' if labelled else ""
    b = " border-t border-outline-variant/30" if border else ""
    return f'<section{a}{l} class="{cls}{b}"><div class="max-w-[1400px] mx-auto px-4 lg:px-8">{inner}</div></section>'


def card(inner: str, cls: str = "") -> str:
    return f'<article class="bg-surface-container-low p-6 {cls}">{inner}</article>'
