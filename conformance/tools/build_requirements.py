"""SUPERSEDED in contract 2.0.0 (Sprint 16). This script produced the contract 1.0.0 baseline only.

`spec/requirements.json` is now the source of truth and is changed through the process in GOVERNANCE.md
(proposal -> decision record -> CHANGELOG entry). Re-running this script would silently overwrite every 2.0.0
requirement with its 1.0.0 text, so it refuses to run unless you pass --rebuild-1.0-baseline."""
import sys
if "--rebuild-1.0-baseline" not in sys.argv:
    sys.exit("build_requirements.py is superseded (contract 2.0.0): edit spec/requirements.json via GOVERNANCE.md, "
             "or pass --rebuild-1.0-baseline to regenerate the historical 1.0.0 file.")
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from requirements_catalog import R
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "spec", "requirements.json")
json.dump({"cop_version": "1.0", "requirements": R}, open(out, "w"), indent=1)
print(len(R), "requirements")
