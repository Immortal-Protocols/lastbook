#!/bin/bash
# Build phase: copy the desktop's web UI and guide topics into the app bundle, unchanged. Nothing else from the desktop tree.
# Also bundles the licence of the local AI runtime (llama.cpp, MIT) that the app links.
set -euo pipefail
SRC="${LASTBOOK_SOURCE:?}"
DST="${TARGET_BUILD_DIR}/${UNLOCALIZED_RESOURCES_FOLDER_PATH}"
mkdir -p "$DST/web" "$DST/content/topics" "$DST/licenses"
rsync -a --delete --exclude 'sw.js' --exclude '.DS_Store' "$SRC/web/" "$DST/web/"
rsync -a --delete --include '*.json' --exclude '*' "$SRC/content/topics/" "$DST/content/topics/"
cp "$SRC/content/gaps.json" "$DST/content/gaps.json"
LIC="${SRCROOT}/build/llama/${PLATFORM_NAME}/LICENSE-llama.cpp.txt"
[ -f "$LIC" ] || { echo "error: llama.cpp licence missing at $LIC (scripts/build_llama_ios.sh writes it)"; exit 1; }
cp "$LIC" "$DST/licenses/llama.cpp-LICENSE.txt"

cp "${SRCROOT}/build/llama/${PLATFORM_NAME}/LICENSE-jsonhpp.txt" "$DST/licenses/"
