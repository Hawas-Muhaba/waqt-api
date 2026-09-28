from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_CORE_ROOT = _HERE.parent

# Fallback only -- normal use is `pip install -e core/` (see core/README.md),
# after which waqt_core is already importable and this is a no-op.
if str(_CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(_CORE_ROOT))
