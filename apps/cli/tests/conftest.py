import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for p in (_HERE.parent, _HERE.parent.parent.parent / "core", _HERE.parent.parent.parent / "local"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
