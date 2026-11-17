#!/bin/bash
# Builds the Mac test tool for the map installer (Engine/Install) and, with --fresh, makes the test library:
# build/install-test/LastbookData, an APFS clone (cp -cR) of build/LastbookData. Tests run on that copy only; the
# original clone is used by the reference server and the simulator and is never touched.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$HERE/build"
SRC=()   # every engine and route file, in any subfolder
while IFS= read -r f; do SRC+=("$f"); done < <(find "$HERE/Lastbook/Engine" "$HERE/Lastbook/API" -name "*.swift" | sort)
SRC+=("$HERE/tools/installtest/main.swift")
OUT="${INSTALLTEST_OUT:-$HERE/build/installtest}"
xcrun swiftc -O -o "$OUT" "${SRC[@]}"
if [ "${1:-}" = "--fresh" ]; then
  rm -rf "$HERE/build/install-test"
  mkdir -p "$HERE/build/install-test"
  cp -cR "$HERE/build/LastbookData" "$HERE/build/install-test/LastbookData"
  echo "fresh copy: $HERE/build/install-test/LastbookData"
fi
echo "$OUT"
