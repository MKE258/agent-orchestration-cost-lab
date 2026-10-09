#!/usr/bin/env bash
# Offline self-test: no model calls. Builds a one-file fixture in a temp copy of this kit,
# checks that gate.py fails the original and passes a fixed version, and that review.py
# puts the full TASK.md into the reviewer packet.
set -euo pipefail
KIT="$(cd "$(dirname "$0")" && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
cp "$KIT"/*.py "$KIT"/TASK.md "$KIT"/rubric.md "$TMP"/
cd "$TMP"
mkdir -p base/tools run1/tools
cat > base/tools/demo.py <<'PY'
from pathlib import Path
DATA = Path(r"C:\Users\YOURNAME\data\in.csv")
PY
cat > run1/tools/demo.py <<'PY'
from pathlib import Path
DATA = Path.home() / "data" / "in.csv"
PY
echo "tools/demo.py" > targets.txt
(cd base && sha256sum tools/demo.py) > base.sha256

py=python3; command -v python3 >/dev/null 2>&1 && python3 -c "" 2>/dev/null || py=python
export PYTHONIOENCODING=utf-8

"$py" gate.py base | tail -1 | grep -q "GATE FAIL" && echo "ok  gate fails the original"
"$py" gate.py run1 | tail -1 | grep -q "GATE PASS" && echo "ok  gate passes the fixed file"
"$py" - <<'PY'
import importlib.util, pathlib, sys
spec = importlib.util.spec_from_file_location("review", "review.py")
review = importlib.util.module_from_spec(spec); spec.loader.exec_module(review)
text = review.packet(pathlib.Path("run1"))
assert "or the location the original clearly intended" in text, "TASK.md missing from packet"
assert "Path.home()" in text, "diff missing from packet"
print("ok  review packet carries the full TASK.md and the diff")
PY
echo "selftest passed"
