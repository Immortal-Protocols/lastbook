#!/bin/bash
# Builds build/mediumalltest: the Medium/All installer checks (tools/mediumalltest/main.swift) against the engine sources,
# like tools/build_installtest.sh. Run: build/mediumalltest [FIXTURE_DIR, default build/medium-all/test]
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$HERE/build"
SRC=()
while IFS= read -r f; do SRC+=("$f"); done < <(find "$HERE/Lastbook/Engine" "$HERE/Lastbook/API" -name "*.swift" | sort)
SRC+=("$HERE/tools/mediumalltest/main.swift")
xcrun swiftc -O -o "$HERE/build/mediumalltest" "${SRC[@]}"
echo "$HERE/build/mediumalltest"
