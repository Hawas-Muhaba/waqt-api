import glob, json, re
from pages_common import *
from pages_a import PANEL, MICRO
from pages_b import hero

REPO = os.path.abspath(os.path.join(WEB, "..", ".."))

def clean(t):
    t = re.sub(r"[`*]", "", t)
    return html.escape(re.sub(r"\s+", " ", t).strip())

def load_drs():
    out = []
    for p in sorted(glob.glob(os.path.join(REPO, "conformance", "decisions", "DR-*.md"))):
        t = open(p, encoding="utf-8").read()
        title = re.match(r"# (DR-\d+): (.*)", t)
        date = re.search(r"\*\*Date\*\*\s*\|\s*([\d-]+)", t)
        reqs = re.search(r"\*\*Requirements\*\*\s*\|\s*(.*?)\s*\|", t)
        ctx = re.search(r"## Context\n(.*?)(?:\n\n|\n##)", t, re.S)
        ex = clean(ctx.group(1)) if ctx else ""
        if len(ex) > 330: ex = ex[:330].rsplit(" ", 1)[0] + " …"
        pend = "PENDING" in t.split("## Context")[0]
        out.append(dict(id=title.group(1), title=clean(title.group(2)), date=date.group(1) if date else "", reqs=clean(reqs.group(1)) if reqs else "", ctx=ex, pending=pend))
    return out

DRS = load_drs()
assert len(DRS) >= 8, DRS
OQ = json.load(open(os.path.join(REPO, "conformance", "spec", "open-questions.json"), encoding="utf-8"))["questions"]
CONTRACT = json.load(open(os.path.join(REPO, "conformance", "contract.json"), encoding="utf-8"))
npend = sum(d["pending"] for d in DRS)

# ============================================================== GOVERNANCE
def dr_card(d):
    st = badge("concept").replace("CONCEPT", "RATIFICATION PENDING") if d["pending"] else badge("real").replace("REAL", "RATIFIED")
    return f'''<article data-dr class="bg-surface-container-low p-5 flex flex-col gap-2"><div class="flex justify-between items-start gap-3"><span class="font-label-md text-[12px] text-primary-container">{d["id"]}</span>{st}</div><h3 class="font-headline-sm text-[16px] leading-snug">{d["title"]}</h3><p class="font-label-sm text-[11px] text-on-surface-variant">Accepted {d["date"]} · contract 2.0.0 · requirements: {d["reqs"]}</p><details class="mt-1"><summary class="cursor-pointer text-[12px] font-label-md uppercase tracking-wider text-primary-container">Context</summary><p class="mt-2 text-body-md text-on-surface-variant">{d["ctx"]}</p></details></article>'''

roles = f'''<div class="flex flex-wrap items-center gap-3 mb-5"><span class="badge concept">DEMO · EDITABLE PROJECT METADATA</span><span class="text-[13px] text-on-surface-variant" data-maint-notice>Demo metadata — editable before public release.</span></div>
<div id="gov-roles" class="grid md:grid-cols-3 gap-6"><noscript><p class="notice">Role information is loaded from <code>assets/js/config.js</code> and needs JavaScript.</p></noscript></div>
<p class="mt-5 text-body-md text-on-surface-variant">Role information says who currently fills which role. It is <b class="text-on-surface">not</b> a governance decision and does not ratify anything. Waqt welcomes qualified experts and contributors.</p>'''
def _ratifiers():
    names = set()
    for p in sorted(glob.glob(os.path.join(REPO, "conformance", "decisions", "DR-*.md"))):
        m = re.search(r"\*\*Ratified by ([^*]+)\*\*", open(p, encoding="utf-8").read().split("## Context")[0])
        if m: names.add(m.group(1).strip())
    return sorted(names)

_who = ", ".join(_ratifiers())
if CONTRACT["released"]:
    _label = "Conformance 2.0.0 released · independent review explicitly waived and not performed (DR-0015)"
    _text = ('Release authorized by Dr. Salim Muhammed Redi (Project Owner) and Mr. Hawas Muhaba Hussein (Technical Developer/Maintainer) in DR-0015. '
             '<b class="text-on-surface">Independent review was not performed</b>; the owners explicitly waived it for this release only. '
             'No signature was requested or collected. DR-0015 records this exception, and the independent instant-range limitation remains disclosed.')
    _third = "Release status — owner-approved; independent review not performed by explicit exception, as recorded in DR-0015."
elif npend == 0:
    _label = "Decision records ratified · contract not yet released"
    _text = (f'All {len(DRS)} decision records state ratification by a named owner ({_who}). The repository holds <b class="text-on-surface">no signed artifact</b> for it, '
             f'and ratifying decisions is not a release: the contract is version {CONTRACT["contract_version"]} (<b class="text-on-surface">draft — not released</b>), the independent-implementation reviewer role is unfilled, '
             'and open specification questions remain open.')
    _third = "Ratification status — read from the decision records; separate from the contract's release status."
elif npend < len(DRS):
    _pend_ids = ", ".join(d["id"] for d in DRS if d["pending"])
    _label = f"Decision records ratified except {_pend_ids} (pending) · contract not yet released"
    _text = (f'{len(DRS) - npend} of {len(DRS)} decision records state ratification by a named owner ({_who}); <b class="text-on-surface">{_pend_ids}</b> '
             f'{"is" if npend == 1 else "are"} marked <i>Ratification by a named maintainer: PENDING</i>. The repository holds <b class="text-on-surface">no signed artifact</b> for any ratification, '
             f'the contract is version {CONTRACT["contract_version"]} (<b class="text-on-surface">draft — not released</b>), and the independent-implementation reviewer role is unfilled. '
             'DR-0015 separately records the owners\u2019 release approval and the explicit exception: independent review was not performed; release verification is pending.')
    _third = "Ratification status — read from the decision records; separate from the contract's release status."
else:
    _label = "Pending project-owner approval"
    _text = (f'{npend} of {len(DRS)} decision records are marked <i>Ratification by a named maintainer: PENDING</i>, the contract is version {CONTRACT["contract_version"]} '
             '(<b class="text-on-surface">draft — not released</b>), and the maintainer register (<code>conformance/MAINTAINERS.md</code>) is not yet filled in. No signatures, approvals or ratification dates exist, and none are shown here.')
    _third = "Ratification status — pending until the project owner explicitly ratifies."

status = f'''<div class="grid md:grid-cols-2 gap-6"><div class="{PANEL}"><p class="{MICRO} mb-3">Ratification status</p><p class="font-headline-md text-[22px]" data-ratification>{_label}</p><p class="mt-3 text-body-md text-on-surface-variant">{_text}</p></div>
<div class="{PANEL}"><p class="{MICRO} mb-3">Three different things</p><ul class="space-y-2 text-body-md text-on-surface-variant list-disc pl-5"><li><b class="text-on-surface">Project role information</b> — demo, editable metadata (above).</li><li><b class="text-on-surface">Formal governance decisions</b> — the decision records below, read from the repository.</li><li><b class="text-on-surface">{_third.split(" — ")[0]}</b> — {_third.split(" — ")[1]}</li></ul></div></div>'''
life = '''<ol class="grid md:grid-cols-5 gap-px bg-outline-variant/30 list-none p-0 m-0" aria-label="How the specification changes">
<li class="bg-surface-container-low p-5"><p class="font-label-sm text-[11px] text-secondary">01</p><b class="block mt-1 font-headline-sm text-[15px]">Propose</b><span class="text-[13px] text-on-surface-variant">Anyone may open a change proposal: the question, evidence, proposed text and vectors.</span></li>
<li class="bg-surface-container-low p-5"><p class="font-label-sm text-[11px] text-secondary">02</p><b class="block mt-1 font-headline-sm text-[15px]">Evidence</b><span class="text-[13px] text-on-surface-variant">Measurements from independent implementations — or a stated reason only one exists.</span></li>
<li class="bg-surface-container-low p-5"><p class="font-label-sm text-[11px] text-secondary">03</p><b class="block mt-1 font-headline-sm text-[15px]">Review</b><span class="text-[13px] text-on-surface-variant">At least one reviewer who is not the author; open for a minimum period.</span></li>
<li class="bg-surface-container-low p-5"><p class="font-label-sm text-[11px] text-secondary">04</p><b class="block mt-1 font-headline-sm text-[15px]">Decide</b><span class="text-[13px] text-on-surface-variant">A decision record is written; dissent is recorded in the dissenter’s words; a named maintainer ratifies.</span></li>
<li class="bg-surface-container-low p-5"><p class="font-label-sm text-[11px] text-secondary">05</p><b class="block mt-1 font-headline-sm text-[15px]">Change</b><span class="text-[13px] text-on-surface-variant">Requirement, vectors and prose change together, with a changelog entry.</span></li></ol>'''
princ = f'''<div class="grid md:grid-cols-2 gap-6"><div class="{PANEL}"><ul class="space-y-3 text-body-md text-on-surface-variant list-disc pl-5"><li><b class="text-on-surface">Written requirements govern; test vectors illustrate.</b></li><li><b class="text-on-surface">Facts are normative; conventions are configurable</b> — astronomy is fixed; Hijri providers and Fajr/Isha angles are choices you pass in.</li><li><b class="text-on-surface">A clean report is not a goal.</b> Open questions stay open until genuinely settled.</li><li><b class="text-on-surface">Temporal facts, not religious rulings.</b></li></ul></div>
<div class="{PANEL}"><p class="{MICRO} mb-3">Contract status</p>{"".join(f'<div class="flex justify-between gap-4 py-1.5 border-b border-outline-variant/30 font-label-sm text-[12px]"><span class="text-on-surface-variant">{a}</span><span class="text-on-surface text-right">{b}</span></div>' for a, b in [("Contract version", CONTRACT["contract_version"]), ("Released", "yes (DR-0015)" if CONTRACT["released"] else "no (draft)"), ("Reference known failures", CONTRACT["status"]["reference_known_failures"]), ("Independent engine known failures", CONTRACT["status"]["independent_known_failures"]), ("Decision records", f"{len(DRS)} accepted · {len(DRS) - npend} ratified · {npend} awaiting ratification")])}</div></div>'''
gov = hero("Governance", "Open governance, written down.", "Waqt is a standard first and software second. Its rules are versioned, and every change to them goes through a proposal and a decision record. This page keeps project roles, formal decisions and ratification status clearly apart.") \
  + wrap(h2("Project role information", "", "People", hid="h-roles") + roles, border=False, cls="pb-12") \
  + wrap(h2("Ratification status", "", "Status", hid="h-status") + status) \
  + wrap(h2("Formal governance decisions", f"{len(DRS)} records, read from the repository’s <code>conformance/decisions/</code>.", "Records", hid="h-records") + '<div id="records" class="grid md:grid-cols-2 gap-4">' + "".join(dr_card(d) for d in DRS) + "</div>") \
  + wrap(h2("How the specification changes", "", "Lifecycle") + life) \
  + wrap(h2("Principles and status", "", "Standard") + princ) \
  + wrap(f'<div class="bg-surface-container-low border border-outline-variant/40 p-8"><h2 class="font-headline-md text-[24px]">Are you a qualified expert?</h2><p class="mt-2 text-body-md text-on-surface-variant max-w-3xl">Astronomers, Hijri-calendar scholars, standards engineers and independent implementers are especially welcome. <a data-idea class="text-primary-container hover:underline" href="mailto:waqtapi@gmail.com">Send an Idea</a> or write to <a data-email class="text-primary-container hover:underline" href="mailto:waqtapi@gmail.com">waqtapi@gmail.com</a>.</p></div>')
page("governance.html", "Governance", "Waqt governance: roles, decision records, how the specification changes, and how to contribute.", "gov", gov, CORE, ["pages/governance"])

# ============================================================== COMMUNITY
open_q = [q for q in OQ if q["status"] != "resolved"]
res_q = [q for q in OQ if q["status"] == "resolved"]
def qrow(q):
    tone = "concept" if q["status"] == "deferred" else "future"
    return f'<tr><td class="whitespace-nowrap text-primary-container">{q["id"]}</td><td style="font-family:Inter,sans-serif">{clean(q["topic"])}</td><td class="whitespace-nowrap">{q.get("requirement") or "—"}</td><td><span class="badge {tone}">{q["status"]}</span></td></tr>'
domains = f'''<div class="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
{card(f'<p class="{MICRO} text-primary-container">Independent implementation</p><h3 class="mt-3 font-headline-sm text-[16px]">Re-implement the contract</h3><p class="mt-2 text-body-md text-on-surface-variant">A second engine checked against the portable vectors is the strongest evidence a standard can have.</p>')}
{card(f'<p class="{MICRO} text-primary-container">Astronomy &amp; accuracy</p><h3 class="mt-3 font-headline-sm text-[16px]">Verify the engine</h3><p class="mt-2 text-body-md text-on-surface-variant">The engine is accuracy level B. Independent cross-checks, especially at high latitudes, are welcome.</p>')}
{card(f'<p class="{MICRO} text-primary-container">Calendars</p><h3 class="mt-3 font-headline-sm text-[16px]">Hijri providers</h3><p class="mt-2 text-body-md text-on-surface-variant">Scholarly review of provider behaviour, ranges and declared-calendar rules.</p>')}
{card(f'<p class="{MICRO} text-primary-container">Applications</p><h3 class="mt-3 font-headline-sm text-[16px]">Build on the API</h3><p class="mt-2 text-body-md text-on-surface-variant">Clocks, watches, mobile and institutional tools. Tell us what you make — we list confirmed applications below.</p>')}</div>'''
comm = hero("Community", "Build the standard together.", "Waqt gets better when people use it, break it and propose changes. Here is where help is genuinely needed — taken from the project’s own open-questions register.") \
  + wrap(h2("Active contribution domains", "", "Contribute", hid="h-domains") + domains + f'<div class="mt-8 flex flex-wrap gap-3"><a class="btn" data-idea href="mailto:waqtapi@gmail.com">Send an Idea</a><a class="btn ghost" href="governance.html">How decisions are made</a></div>', border=False, cls="pb-12") \
  + wrap(h2("Open questions", f"{len(open_q)} of {len(OQ)} questions in <code>conformance/spec/open-questions.json</code> are not resolved. Deferred questions are waiting for evidence or a decision.", "Register", hid="h-oq") + f'<div class="table-scroll bg-surface-container-low"><table class="data"><caption class="vh">Unresolved questions</caption><thead><tr><th scope="col">ID</th><th scope="col">Question</th><th scope="col">Requirement</th><th scope="col">Status</th></tr></thead><tbody>{"".join(qrow(q) for q in open_q)}</tbody></table></div><details class="mt-4"><summary class="cursor-pointer text-[12px] font-label-md uppercase tracking-wider text-primary-container">{len(res_q)} resolved questions</summary><div class="table-scroll bg-surface-container-low mt-3"><table class="data"><caption class="vh">Resolved questions</caption><tbody>{"".join(qrow(q) for q in res_q)}</tbody></table></div></details>') \
  + wrap(h2("Applications and links", "Official applications are built by the Waqt project; community applications are built by others and are not endorsed unless stated. Entries appear once confirmed.", "Ecosystem", hid="h-linked") + f'''<div class="grid md:grid-cols-2 gap-6"><div class="{PANEL}"><h3 class="font-headline-sm text-[16px] mb-3">Official applications {badge("real").replace("REAL","OFFICIAL")}</h3><ul id="links-official" class="space-y-1 text-body-md list-none p-0"></ul></div><div class="{PANEL}"><h3 class="font-headline-sm text-[16px] mb-3">Community applications {badge("future").replace("FUTURE","COMMUNITY")}</h3><ul id="links-community" class="space-y-1 text-body-md list-none p-0"></ul></div><div class="{PANEL}"><h3 class="font-headline-sm text-[16px] mb-3">SDK repositories</h3><ul id="links-sdk" class="space-y-1 text-body-md list-none p-0"></ul></div><div class="{PANEL}"><h3 class="font-headline-sm text-[16px] mb-3">Package registries</h3><ul id="links-pkg" class="space-y-1 text-body-md list-none p-0"></ul></div></div>''') \
  + wrap(f'<div class="border border-outline-variant/50 bg-surface-container-low p-8 max-w-3xl"><h2 id="h-support" class="font-headline-md text-[24px]">Support Waqt</h2><p class="mt-2 text-body-md text-on-surface-variant">Ideas, testing and expertise matter most. If you would also like to help cover costs, you can buy us a coffee — entirely optional.</p><a data-cfg="@support" href="#" class="mt-4 inline-flex items-center gap-2 px-4 py-2 border border-secondary text-secondary font-label-md text-[12px] uppercase tracking-wider hover:bg-secondary/10">☕️ Support on Ko-fi</a></div>')
page("community.html", "Community", "Join the Waqt community: contribution domains, the open-questions register, applications and support.", "community", comm, CORE, ["pages/community"])

# ============================================================== RESOURCES
res = hero("Resources", "Waqt resource hub", "Canonical sources first: the Git repository, then (when they exist) GitHub Releases and package registries. This site links to them; it never hosts archives or package files.") \
  + wrap(f'''<div class="notice" data-repo-note>Repository links come from the central configuration.</div>
<p class="mt-3 text-[12px] text-on-surface-variant font-label-sm">Source of truth: Git repository → GitHub Releases → package registries → this resource hub. Items that do not exist yet are shown disabled with their status — never as a working link.</p>''', border=False, cls="pb-6") \
  + wrap('<div id="hub" class="space-y-14"><noscript><p class="notice">The resource hub is built from <code>assets/js/config.js</code> and needs JavaScript. The repository\'s <code>docs/</code> folder holds the documentation as Markdown.</p></noscript></div>', border=False, cls="py-8") \
  + wrap(h2("Getting started", "From a clone of the repository to a first response.", "Quickstart") + f'''<div class="grid lg:grid-cols-2 gap-6"><ol class="space-y-4 list-none p-0 m-0"><li class="{PANEL}"><b class="font-label-md text-[12px] text-secondary">01</b> Install the packages from the repository root.</li><li class="{PANEL}"><b class="font-label-md text-[12px] text-secondary">02</b> Start the API with <code>uvicorn waqt.api:app --port 8000</code>.</li><li class="{PANEL}"><b class="font-label-md text-[12px] text-secondary">03</b> Ask for the current Waqt day, naming the Hijri provider you want.</li></ol><pre class="code" tabindex="0" aria-label="Quickstart commands">pip install -e ./core -e . -e ./local\nuvicorn waqt.api:app --port 8000\n\ncurl "http://localhost:8000/v1/waqt?lat=9.0192&amp;lon=38.7525&amp;calendar_provider=umm-al-qura"</pre></div>''') \
  + wrap(h2("Version axes of the running API", "Read live from <code>GET /v1/version</code>.", "Live", hid="h-ver") + f'<div class="{PANEL}" id="ver-panel"><div id="ver-body" class="text-body-md text-on-surface-variant" role="status">Checking…</div></div>')
page("resources.html", "Resources", "Waqt resource hub: source, specification, conformance, API, SDK locations, developer resources, community and support.", "", res, CORE, ["pages/resources"])
