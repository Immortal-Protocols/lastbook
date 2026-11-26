#!/bin/bash
# Builds the Mac parity tool from the app's own engine and route files (no UI files). Output: build/apidump
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$HERE/build"
SRC=("$HERE"/Lastbook/Engine/*.swift "$HERE"/Lastbook/Engine/Install/*.swift "$HERE"/Lastbook/Engine/AI/*.swift "$HERE"/Lastbook/API/*.swift "$HERE/tools/apidump/main.swift")
OUT="${APIDUMP_OUT:-$HERE/build/apidump}"   # parallel workers each set their own
xcrun swiftc -O -o "$OUT" "${SRC[@]}"
echo "$OUT"
