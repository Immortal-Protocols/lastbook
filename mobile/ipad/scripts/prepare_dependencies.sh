#!/bin/bash
# Explicit development-time dependency fetch. Xcode builds never download code.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
COMMIT=dde879bc4f954b809892fd0d660515f42536394a
DEST="$HERE/build/deps/llama.cpp"
if [ ! -d "$DEST" ]; then
  mkdir -p "$(dirname "$DEST")"
  git clone --no-checkout https://github.com/ggml-org/llama.cpp.git "$DEST"
  git -C "$DEST" checkout --detach "$COMMIT"
fi
[ "$(git -C "$DEST" rev-parse HEAD)" = "$COMMIT" ] || {
  echo "Expected llama.cpp $COMMIT at $DEST; move an incompatible checkout aside first." >&2
  exit 1
}
git -C "$DEST" diff --quiet HEAD -- || { echo "Dependency has local modifications." >&2; exit 1; }
echo "Pinned llama.cpp source is ready."
