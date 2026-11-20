#!/bin/bash
# Downloads the prebuilt CoreKiwix XCFramework used by the iPhone target's encyclopedia reader.
# It is not committed: it is compiled libkiwix/libzim (GPL-3.0; see THIRD_PARTY_NOTICES.md).
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION="14.2.1-2"
SHA256="14820648788dddc3df8a89ff0820af60d7efc1cfda6c83602989455263ee1561"
ARCHIVE="libkiwix_xcframework-${VERSION}.tar.gz"
URL="https://download.kiwix.org/release/libkiwix/${ARCHIVE}"
MARKER=".corekiwix-version"

if [ -d CoreKiwix.xcframework ]; then
  if [ -f "$MARKER" ] && [ "$(cat "$MARKER")" = "$VERSION $SHA256" ]; then
    echo "CoreKiwix.xcframework $VERSION is already here"
    exit 0
  fi
  echo "CoreKiwix.xcframework is here but does not match $VERSION." >&2
  echo "Delete it and run this script again." >&2
  exit 1
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
curl -fL -o "$TMP/$ARCHIVE" "$URL"
ACTUAL="$(shasum -a 256 "$TMP/$ARCHIVE" | awk '{print $1}')"
if [ "$ACTUAL" != "$SHA256" ]; then
  echo "Checksum mismatch for $ARCHIVE" >&2
  echo "  expected $SHA256" >&2
  echo "  got      $ACTUAL" >&2
  exit 1
fi
tar xzf "$TMP/$ARCHIVE" -C "$TMP"
cp -R "$TMP/libkiwix_xcframework-$VERSION/lib/CoreKiwix.xcframework" .
printf '%s %s\n' "$VERSION" "$SHA256" > "$MARKER"
echo "CoreKiwix.xcframework $VERSION installed"
