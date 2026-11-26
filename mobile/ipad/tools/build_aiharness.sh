#!/bin/bash
# Builds the Mac test harness for the local AI from the app's own engine, route and AI files, linked to the macOS build of
# the same llama.cpp bridge (scripts/build_llama_ios.sh macosx). Output: build/aiharness
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
bash "$HERE/scripts/build_llama_ios.sh" macosx
SRC=("$HERE"/Lastbook/Engine/*.swift "$HERE"/Lastbook/Engine/Install/*.swift "$HERE"/Lastbook/Engine/AI/*.swift "$HERE"/Lastbook/API/*.swift
     "$HERE/tools/aiharness/main.swift")
xcrun swiftc -O -target arm64-apple-macos14.0 -I "$HERE/llm/include" -L "$HERE/build/llama/macosx" -llastbook_llm -lc++ \
  -framework Metal -framework MetalKit -framework Accelerate -o "$HERE/build/aiharness" "${SRC[@]}"
echo "$HERE/build/aiharness"
