from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_LOCAL_ROOT = _HERE.parent
_REPO_ROOT = _LOCAL_ROOT.parent

for p in (_REPO_ROOT, _LOCAL_ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
