"""Structural guards for the multi-page Waqt site (the Stitch implementation). Plain Python, no browser.
Rules enforced: no second implementation of Waqt anywhere in assets/js; no invented endpoints/URLs/data;
identical navigation on every page; honest REAL/CONCEPT/FUTURE labelling; asset budget; accessibility basics."""
from __future__ import annotations
import re
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent
PAGES = sorted(WEB.glob("*.html"))
JS = sorted((WEB / "assets" / "js").rglob("*.js"))
NAV_LABELS = ["Overview", "The Problem", "How It Works", "Live Demo", "API", "Applications", "Governance", "Community", "GitHub", "Read Spec / Docs"]
BANNED = ["18.0", "17.0", "1948440", "julian_century", "declination", "equation_of_time", "delta_t_seconds =",
          "solveHourAngle", "computeWaqt(", "waqt-noaa", "getSolar", "computeEvents"]
# (Math.sin/cos are legitimate here: they only place markers on an SVG ring. They are banned inside the live-demo tick().)
ALLOWED_PATHS = {"/v1/waqt", "/v1/events", "/v1/calendar", "/v1/version", "/v1/health"}


def read(p): return p.read_text(encoding="utf-8")


def test_expected_pages_exist():
    names = {p.name for p in PAGES}
    assert {"index.html", "live-demo.html", "api.html", "applications.html", "lab.html", "governance.html", "community.html", "resources.html"} <= names


def test_navigation_identical_on_every_page_and_in_spec_order():
    navs = []
    for p in PAGES:
        m = re.search(r'<ul class="nav-list" id="site-nav">(.*?)</ul>', read(p), re.S)
        assert m, f"{p.name}: no primary nav"
        navs.append(re.sub(r' aria-current="page"', "", m.group(1)))
        labels = re.findall(r">([^<>]+)</a>", m.group(1))
        assert labels == NAV_LABELS, f"{p.name}: nav labels {labels}"
    assert len(set(navs)) == 1, "navigation markup differs between pages"


def test_each_page_has_one_h1_skip_link_main_and_lang():
    for p in PAGES:
        h = read(p)
        assert '<html lang="en">' in h and 'class="skip"' in h and '<main id="main">' in h, p.name
        assert len(re.findall(r"<h1[ >]", h)) == 1, f"{p.name}: expected exactly one h1"


def test_mobile_nav_toggle_is_accessible():
    h = read(WEB / "index.html")
    assert 'class="nav-toggle"' in h and 'aria-expanded="false"' in h and 'aria-controls="site-nav"' in h


def test_no_second_implementation_in_any_site_script():
    assert JS
    for p in JS:
        if p.name == "demo-data.js":
            continue  # recorded API output (data)
        s = read(p)
        for bad in BANNED:
            assert bad not in s, f"{p.name} contains {bad!r}"


def test_only_known_endpoints_are_fetched():
    found = set()
    for p in JS:
        found |= set(re.findall(r'getJSON\(\s*"(/[^"]+)"', read(p)))
    assert found and found <= ALLOWED_PATHS, found - ALLOWED_PATHS
    assert "/v1/waqt" in found


def test_no_external_scripts_styles_or_images_in_pages():
    for p in PAGES:
        h = read(p)
        assert not re.search(r'<script[^>]+src="https?:', h), p.name
        assert not re.search(r'<link[^>]+href="https?:', h), p.name
        assert not re.search(r'<img[^>]+src="https?:', h), p.name


def test_external_urls_are_configuration_not_hardcoded():
    cfg = read(WEB / "assets/js/config.js")
    for key in ("github", "docs", "spec", "issues", "buyMeACoffee"):
        assert re.search(rf"{key}:\s*null", cfg), f"links.{key} must stay null until the real URL is supplied"
    for key in ("sdkRepos", "packageRegistries", "officialApps", "communityApps"):
        assert re.search(rf"{key}:\s*\[\]", cfg), key
    for p in PAGES:
        h = read(p)
        for host in ("buymeacoffee.com", "github.com", "pypi.org", "npmjs.com"):
            assert host not in h, f"{p.name} hard-codes {host}"


def test_buy_me_a_coffee_is_footer_and_community_not_primary_cta():
    for name in ("index.html", "applications.html", "community.html"):
        assert 'data-link="buyMeACoffee"' in read(WEB / name), name
    hero = re.search(r'id="overview".*?</section>', read(WEB / "index.html"), re.S).group(0)
    assert "buyMeACoffee" not in hero


def test_contact_email_and_idea_cta():
    assert 'contactEmail: "waqtapi@gmail.com"' in read(WEB / "assets/js/config.js")
    for name in ("index.html", "governance.html", "community.html"):
        h = read(WEB / name)
        assert "data-idea" in h and "waqtapi@gmail.com" in h
    home = read(WEB / "index.html")
    assert "Have an idea?" in home and "Help shape Waqt." in home and "Send an Idea" in home


def test_governance_roles_exact_and_no_invented_maintainers():
    g = read(WEB / "governance.html")
    assert "Dr. Salim Muhammed Redi" in g and "Mr. Hawas Muhaba Hussein" in g
    assert "Idea / Logical Owner" in g and "Technical Developer / Maintainer" in g
    assert "welcomes qualified experts" in g
    assert "PENDING" in g


def test_applications_page_labels_every_card_real_concept_or_future():
    h = read(WEB / "applications.html")
    for title in ["Mosque Waqt Clock", "Waqt Smartwatch", "Waqt Mobile App", "Circular Waqt Clock", "Waqt Day vs Midnight Day",
                  "API → Applications", "Institutional Calendar", "Developer Dashboard", "Location / Travel", "Future concepts"]:
        assert title in h, title
    gallery = h[h.index('id="h-gallery"'):h.index('id="h-future"')]
    cards = re.findall(r'<article class="card">.*?</article>', gallery, re.S)
    assert len(cards) == 9
    for art in cards:
        assert re.search(r'class="badge (real|concept|future)"', art), art[:120]
    for concept in ("Mosque Waqt Clock", "Waqt Smartwatch", "Waqt Mobile App", "Institutional Calendar", "Developer Dashboard", "Location / Travel"):
        art = next(a for a in cards if concept in a)
        assert "badge concept" in art, concept + " must be labelled CONCEPT"
    assert "badge future" in h


def test_every_image_is_concept_art_labelled_dimensioned_and_small():
    total = 0
    for p in (WEB / "assets/img").glob("*.webp"):
        total += p.stat().st_size
        assert p.stat().st_size < 120_000, p.name
    assert total < 1_000_000
    for p in PAGES:
        h = read(p)
        for tag in re.findall(r"<img [^>]*>", h):
            assert 'alt="' in tag and 'width="' in tag and 'height="' in tag, tag
        assert h.count("<img ") == h.count("art-tag"), f"{p.name}: every image needs a concept-art tag"


def test_live_components_ship_textual_equivalents_and_demo_labels():
    clock = read(WEB / "assets/js/waqt-clock.js")
    for needle in ('role="img"', "<title", "<desc", 'role="list"', 'tabindex="0"', "ArrowRight", "DEMO · NOT LIVE",
                   "Live Waqt data unavailable", "demonstration mode", "wc-events"):
        assert needle in clock, needle
    assert "prefers-reduced-motion" in read(WEB / "assets/css/site.css")


def test_demo_fixture_is_recorded_and_labelled_not_live():
    d = read(WEB / "assets/js/demo-data.js")
    assert "NOT live" in d and '"source"' in d and '"api_version"' in d


def test_render_blueprint_still_publishes_apps_web():
    bp = (WEB.parents[1] / "render.yaml").read_text()
    assert "staticPublishPath: ./apps/web" in bp and 'buildCommand: "true"' in bp
