"""Structural guards for the multi-page Waqt site (the Stitch implementation). Plain Python, no browser.
Rules enforced: no second implementation of Waqt anywhere in assets/js; no invented endpoints/URLs/data;
identical navigation on every page; honest REAL/CONCEPT/FUTURE labelling; asset budget; accessibility basics."""
from __future__ import annotations
import json
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
    assert {"index.html", "problem.html", "how-it-works.html", "live-demo.html", "reference-viewer.html", "api.html", "applications.html", "lab.html", "governance.html", "community.html", "resources.html"} <= names


def test_navigation_identical_on_every_page_and_in_spec_order():
    navs = []
    for p in PAGES:
        m = re.search(r'<ul id="site-nav"[^>]*>(.*?)</ul>', read(p), re.S)
        assert m, f"{p.name}: no primary nav"
        navs.append(re.sub(r' aria-current="page"', "", m.group(1)))
        assert m.group(1).count('aria-current="page"') <= 1, p.name
        labels = re.findall(r">([^<>]+)</a>", m.group(1))
        assert labels == NAV_LABELS, f"{p.name}: nav labels {labels}"
    assert len(set(navs)) == 1, "navigation markup differs between pages"


def test_each_page_has_one_h1_skip_link_main_and_lang():
    for p in PAGES:
        h = read(p)
        assert '<html lang="en"' in h and 'class="skip"' in h and '<main id="main">' in h, p.name
        assert len(re.findall(r"<h1[ >]", h)) == 1, f"{p.name}: expected exactly one h1"


def test_mobile_nav_toggle_is_accessible():
    h = read(WEB / "index.html")
    assert "nav-toggle" in h and 'aria-expanded="false"' in h and 'aria-controls="site-nav"' in h


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


def test_applications_page_labels_every_card_real_concept_or_future():
    h = read(WEB / "applications.html")
    for title in ["Mosque Waqt Clock", "Waqt Smartwatch", "Waqt Mobile App", "Circular Waqt Clock", "Waqt Day vs Midnight Day",
                  "API → Applications", "Institutional Calendar", "Developer Dashboard", "Location / Travel", "Future concepts"]:
        assert title in h, title
    gallery = h[h.index('id="h-gallery"'):h.index('id="h-future"')]
    cards = re.findall(r"<article data-app-card.*?</article>", gallery, re.S)
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
    assert "prefers-reduced-motion" in read(WEB / "assets/css/components.css")


def test_demo_fixture_is_recorded_and_labelled_not_live():
    d = read(WEB / "assets/js/demo-data.js")
    assert "NOT live" in d and '"source"' in d and '"api_version"' in d


def test_render_blueprint_still_publishes_apps_web():
    bp = (WEB.parents[1] / "render.yaml").read_text()
    assert "staticPublishPath: ./apps/web" in bp and 'buildCommand: "true"' in bp


# ----------------------------------------------------------------------------------------------------------------
# Stitch implementation guards: the design was ported faithfully, but its invented content was NOT.
UNSUPPORTED = ["VSOP87D", "RFC-0024", "ld+json", "/v1/telemetry", "GraphQL", "protobuf", "WebSocket", "wss://", "Aqrab", "Rust",
               "watchOS", "Wear OS", "Diyanet", "RS-485", "MQTT", "0.12ms", "99.9", "SLA", "Steward", "Working Group", "waqt-project/rfcs"]


def test_no_unsupported_stitch_claims_survive():
    for p in PAGES:
        h = read(p)
        for bad in UNSUPPORTED:
            assert bad not in h, f"{p.name} contains unsupported claim {bad!r}"


def test_design_system_assets_are_self_hosted():
    css = WEB / "assets" / "css"
    assert (css / "stitch.css").stat().st_size > 8_000 and (css / "components.css").exists()
    fonts = list((WEB / "assets" / "fonts").glob("*.woff2"))
    assert len(fonts) == 3 and sum(f.stat().st_size for f in fonts) < 200_000
    for p in PAGES:
        h = read(p)
        assert "cdn.tailwindcss.com" not in h and "fonts.googleapis.com" not in h and "material-symbols" not in h.lower(), p.name
        assert 'href="assets/css/stitch.css"' in h and 'href="assets/css/components.css"' in h, p.name


def test_decision_records_page_matches_the_repository():
    repo = WEB.parents[1] / "conformance" / "decisions"
    drs = sorted(repo.glob("DR-*.md"))
    g = read(WEB / "governance.html")
    assert g.count("data-dr") == len(drs) >= 8
    for p in drs:
        assert p.stem in g, p.stem
    for dr_text in (p.read_text(encoding="utf-8") for p in drs):
        if "PENDING" in dr_text.split("## Context")[0]:
            assert "RATIFICATION PENDING" in g
        else:   # a record that states ratification is shown as RATIFIED, never as pending
            assert "Ratified by" in dr_text.split("## Context")[0]
    pending = [p for p in drs if "PENDING" in p.read_text(encoding="utf-8").split("## Context")[0]]
    assert g.count("RATIFICATION PENDING") == len(pending) and g.count(">RATIFIED<") == len(drs) - len(pending)


def test_open_questions_listed_are_the_real_unresolved_ones():
    import json
    q = json.loads((WEB.parents[1] / "conformance" / "spec" / "open-questions.json").read_text(encoding="utf-8"))["questions"]
    c = read(WEB / "community.html")
    for item in q:
        if item["status"] != "resolved":
            assert item["id"] in c, item["id"]


def test_reference_viewer_remains_api_backed_with_an_explicit_hijri_provider():
    pat = re.compile(r'<script>\s*"use strict";.*?</script>', re.S)
    match = pat.search(read(WEB / "reference-viewer.html"))
    assert match
    script = match.group(0)
    assert 'getJSON("/v1/waqt", { lat, lon, calendar_provider: provider })' in script
    assert 'const provider = $("provider").value || "umm-al-qura";' in script
    for forbidden in ("computeWaqt(", "solveHourAngle", "equation_of_time", "declination"):
        assert forbidden not in script


# ----------------------------------------------------------------------------------------------------------------
# Central configuration (assets/js/config.js is the ONE place for URLs, SDK locations, maintainers, governance state)
import json as _json
import shutil as _shutil
import subprocess as _subprocess

NODE = _shutil.which("node")
REPO = WEB.parents[1]


def config():
    if not NODE:
        import pytest
        pytest.skip("node not installed: cannot evaluate config.js")
    out = _subprocess.run([NODE, "-e", 'global.window={};require(process.argv[1]);console.log(JSON.stringify(window.WAQT_CONFIG))', str(WEB / "assets/js/config.js")],
                          capture_output=True, text=True, check=True).stdout
    return _json.loads(out)


def refs(node, trail=""):
    if isinstance(node, dict):
        if any(k in node for k in ("path", "tree")) and not any(isinstance(v, dict) for v in node.values()):
            yield trail, node
        for k, v in node.items():
            yield from refs(v, f"{trail}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from refs(v, f"{trail}[{i}]")


def test_every_repository_path_in_the_config_exists():
    cfg = config()
    found = list(refs({"docs": cfg["docs"], "sdks": cfg["sdks"], "resources": cfg["resources"], "governance": cfg["governance"]}))
    ref_nodes = [r for t, r in found] + [i["ref"] for sec in cfg["resources"] for i in sec["items"] if "ref" in i]
    paths = {r.get("path") or r.get("tree") for r in ref_nodes if isinstance(r, dict) and (r.get("path") or r.get("tree"))}
    assert len(paths) >= 15, paths
    for p in sorted(paths):
        assert (REPO / p).exists(), f"config.js points at a repository path that does not exist: {p}"


def test_repository_support_and_contact_come_from_the_config():
    cfg = config()
    assert cfg["project"]["repository"]["url"] == "https://github.com/Hawas-Muhaba/waqt-api"
    assert cfg["project"]["repository"]["visibility"] == "private" and cfg["project"]["repository"]["branch"] == "main"
    assert cfg["project"]["support"]["url"] == "https://ko-fi.com/ummatidawah"
    assert cfg["contactEmail"] == "waqtapi@gmail.com"
    for p in PAGES:
        h = read(p)
        for host in ("github.com", "ko-fi.com", "pypi.org", "npmjs.com", "drive.google"):
            assert host not in h, f"{p.name} hard-codes {host}: URLs belong in config.js"
    for p in JS:
        if p.name in ("config.js", "demo-data.js"):
            continue
        s = read(p)
        for host in ("github.com", "ko-fi.com", "pypi.org/", "npmjs.com/", "drive.google"):
            assert host not in s, f"{p.name} hard-codes {host}"


def test_sdk_locations_are_structured_and_nothing_unpublished_is_a_link():
    cfg = config()
    assert [s["id"] for s in cfg["sdks"]] == ["python", "javascript"]
    for s in cfg["sdks"]:
        assert set(s) >= {"source", "docs", "releases", "registry", "package", "version"}
        assert "tree" in s["source"] and "path" in s["docs"]
        assert s["releases"]["status"] in ("planned", "not_published") and "url" not in s["releases"]
        assert s["registry"]["status"] in ("planned", "not_published") and "url" not in s["registry"]
    assert [s["registry"]["name"] for s in cfg["sdks"]] == ["PyPI", "npm"]
    assert cfg["docs"]["releaseNotes"]["status"] == "planned"
    for sec in cfg["resources"]:
        for it in sec["items"]:
            assert "url" not in it.get("ref", {}), f"{it['label']}: absolute URLs only when a canonical public URL exists"


def test_documentation_links_cover_the_required_fields():
    cfg = config()
    for k in ("api", "openapi", "interactive", "spec", "conformance", "sdk", "changelog", "releaseNotes", "contributing", "index"):
        assert k in cfg["docs"], k
    assert cfg["docs"]["openapi"] == {"api": "/openapi.json"} and cfg["docs"]["interactive"] == {"api": "/docs"}


def test_maintainer_metadata_is_demo_editable_and_separate_from_governance_state():
    cfg = config()
    m, g = cfg["maintainers"], cfg["governance"]
    assert m["status"] == "demo" and m["editable"] is True and "not a governance approval" in m["notice"]
    assert [(r["role"], r["name"]) for r in m["roles"]] == [("Logical / Idea Owner", "Dr. Salim Muhammed Redi"), ("Technical Developer / Maintainer", "Mr. Hawas Muhaba Hussein")]
    assert m["contact"] == "waqtapi@gmail.com" and "expert" in m["experts"].lower()
    drs = list((WEB.parents[1] / "conformance" / "decisions").glob("DR-*.md"))
    n_pending = sum("PENDING" in p.read_text(encoding="utf-8").split("## Context")[0] for p in drs)
    contract = json.loads((WEB.parents[1] / "conformance" / "contract.json").read_text(encoding="utf-8"))
    assert g["contractReleased"] is False and contract["released"] is False     # ratified records are not a release
    if n_pending == len(drs):
        assert g["ratification"] == "pending-project-owner-approval" and "ratified" not in g["ratificationLabel"].lower()
    elif n_pending == 0:
        assert g["ratification"] == "decision-records-ratified" and "not yet released" in g["ratificationLabel"]
    else:   # mixed: the site mirrors the repository and names the pending records
        pend_ids = [p.stem for p in drs if "PENDING" in p.read_text(encoding="utf-8").split("## Context")[0]]
        assert g["ratification"] == "decision-records-partly-ratified" and "not yet released" in g["ratificationLabel"]
        assert all(i in g["ratificationLabel"] for i in pend_ids) and "pending" in g["ratificationLabel"]


def test_governance_page_keeps_roles_decisions_and_ratification_apart():
    g = read(WEB / "governance.html")
    assert "DEMO · EDITABLE PROJECT METADATA" in g and "Formal governance decisions" in g and "Ratification status" in g
    assert json.loads(json.dumps(config()["governance"]["ratificationLabel"])) in g and 'id="gov-roles"' in g
    assert "draft — not released" in g and "no signed artifact" in g
    assert not re.search(r"ratified on \d|signed by|ratification date:", g, re.I)


def test_support_link_is_in_footer_and_community_only_never_primary():
    for p in PAGES:
        assert 'data-cfg="@support"' in read(p), p.name          # footer on every page
    hero = re.search(r"<main id=\"main\">.*?</section>", read(WEB / "index.html"), re.S).group(0)
    assert "@support" not in hero
    main = read(WEB / "resources.html").split("<main")[1].split("</main>")[0]
    assert "@support" not in main, "support must not be hard-wired above the technical resources (the hub renders it last, from config)"


def test_no_secrets_anywhere_in_the_web_app():
    pattern = re.compile(r"github_pat_[A-Za-z0-9_]{20,}|ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|\bAQ\.[A-Za-z0-9_-]{30,}|sk-[A-Za-z0-9]{20,}|api[_-]?key\s*[:=]\s*[\"'][A-Za-z0-9]{16,}", re.I)
    for p in list(WEB.rglob("*")):
        if p.is_file() and "node_modules" not in p.parts and p.suffix in (".html", ".js", ".mjs", ".css", ".md", ".json", ".py", ".txt", ".yml"):
            assert not pattern.search(p.read_text(encoding="utf-8", errors="ignore")), f"possible secret in {p}"


def test_no_hard_coded_hijri_date_and_no_hard_coded_arithmetic_default_in_the_web_app():
    months = r"(Muharram|Safar|Rabi|Jumada|Rajab|Sha.?ban|Ramadan|Shawwal|Dhu)"
    for p in PAGES:
        assert not re.search(r"\b\d{1,2} " + months, read(p)), f"{p.name} contains a hard-coded Hijri date"
    for p in JS:
        if p.name == "demo-data.js":
            continue
        assert not re.search(r"\b\d{1,2} " + months, read(p)), p.name
    live = read(WEB / "assets/js/waqt-live.js")
    assert 'provider: "arithmetic-tabular"' not in live and "defaultProvider" in live
    viewer = read(WEB / "reference-viewer.html")
    assert "umm-al-qura" in viewer and "arithmetic-tabular" in viewer      # both offered, Umm al-Qura preferred


def test_docs_new_section_and_contributing_guide_exist():
    assert (REPO / "CONTRIBUTING.md").exists()
    assert "Choosing a Hijri provider" in (REPO / "docs" / "CALENDARS.md").read_text(encoding="utf-8")
