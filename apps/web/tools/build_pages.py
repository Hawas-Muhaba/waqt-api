"""Generate all pages: python3 tools/build_pages.py"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pages_a  # noqa: F401  overview, problem, how-it-works
for m in ("pages_b", "pages_c"):
    if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), m + ".py")):
        __import__(m)
