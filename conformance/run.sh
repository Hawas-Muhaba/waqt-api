#!/bin/sh
# One command: unit tests of the independent implementation, then the portable suite on both implementations.
set -e
cd "$(dirname "$0")"
( cd independent && node --test test/*.test.mjs )
python3 harness/waqt_conform.py \
  --adapter "python3 adapters/reference_adapter.py" --label reference \
  --adapter "node independent/src/cli.mjs"          --label independent \
  --name conformance-report
echo "see conformance/reports/conformance-report.md"
