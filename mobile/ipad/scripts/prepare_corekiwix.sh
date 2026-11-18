#!/bin/bash
# Downloads the prebuilt CoreKiwix XCFramework used by the iPhone target's encyclopedia reader.
# It is not committed: it is 200 MB of compiled libkiwix/libzim (GPL-3.0; see THIRD_PARTY_NOTICES.md).
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION="14.2.1-2"
if [ -d CoreKiwix.xcframework ]; then
  echo "CoreKiwix.xcframework is already here"
  exit 0
fi
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
curl -fL -o "$TMP/corekiwix.tar.gz" "https://download.kiwix.org/release/libkiwix/libkiwix_xcframework.tar.gz"
tar xzf "$TMP/corekiwix.tar.gz" -C "$TMP"
cp -R "$TMP/libkiwix_xcframework-$VERSION/lib/CoreKiwix.xcframework" .
echo "CoreKiwix.xcframework installed"
