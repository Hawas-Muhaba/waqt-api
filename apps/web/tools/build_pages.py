"""Generate all pages: python3 tools/build_pages.py"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pages_a  # noqa: F401  overview, problem, how-it-works
for m in ("pages_b", "pages_c"):
    if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), m + ".py")):
        __import__(m)

# The reference viewer keeps its own inline script/styles; only its header/footer chrome is regenerated here.
def rechrome_viewer():
    import pages_common as c
    p = os.path.join(c.WEB, "reference-viewer.html")
    s = open(p, encoding="utf-8").read()
    i = s.index("<body"); j = s.index('<main id="main">')
    s = s[:i] + '<body class="bg-background text-on-surface font-body-md antialiased min-h-screen pt-16">\n' + c.header() + "\n" + s[j:]
    e1 = s.index("</main>"); e2 = s.index('<script defer src="assets/js/config.js"></script>')
    s = s[:e1] + "</main>\n" + c.FOOTER + "\n" + s[e2:]
    open(p, "w", encoding="utf-8").write(s)
    print("re-chromed reference-viewer.html")

rechrome_viewer()
