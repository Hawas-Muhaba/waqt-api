import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from requirements_catalog import R
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "spec", "requirements.json")
json.dump({"cop_version": "1.0", "requirements": R}, open(out, "w"), indent=1)
print(len(R), "requirements")
