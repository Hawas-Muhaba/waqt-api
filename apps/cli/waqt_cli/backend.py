"""The single seam between the CLI and Waqt: everything the CLI knows about
computation goes through this module, which only re-exports `waqt_local`.
Tests replace `backend.lib` to prove the CLI does no computing of its own."""

import waqt_local as lib  # noqa: F401  (the one and only Waqt import)
from waqt_local import WaqtLocalError  # noqa: F401
