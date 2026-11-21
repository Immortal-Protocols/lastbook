#!/bin/bash
# Builds a Linux AppImage from the staging tree that packaging/linux/build_app_linux.sh wrote.
#
#   bash packaging/linux/build_appimage.sh <stage> <version> <x64|arm64> <output-folder>
#
# The AppImage holds the same /opt/lastbook tree as the .deb and uses the system's Python 3.12, GTK 3 and
# WebKitGTK 4.1 (the runtime packages the .deb Depends on). appimagetool is downloaded for the build architecture.
set -euo pipefail
STAGE="${1:?stage folder}"
VERSION="${2:?version}"
ARCH="${3:?x64 or arm64}"
OUT="${4:?output folder}"
STAGE="$(realpath "$STAGE")"
OUT="$(realpath -m "$OUT")"
[ -d "$STAGE/opt/lastbook" ] || { echo "not a Lastbook staging tree: $STAGE" >&2; exit 1; }
case "$ARCH" in
  x64|x86_64|amd64) APPIMAGE_ARCH=x86_64 ;;
  arm64|aarch64) APPIMAGE_ARCH=aarch64 ;;
  *) echo "unsupported architecture: $ARCH" >&2; exit 1 ;;
esac

APPDIR="$OUT/AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/opt" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/256x256/apps"
cp -a "$STAGE/opt/lastbook" "$APPDIR/opt/lastbook"
sed 's/^Exec=.*/Exec=AppRun/' "$STAGE/usr/share/applications/lastbook.desktop" > "$APPDIR/lastbook.desktop"
cp "$STAGE/usr/share/icons/hicolor/256x256/apps/lastbook.png" "$APPDIR/lastbook.png"
cp "$STAGE/usr/share/icons/hicolor/256x256/apps/lastbook.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/lastbook.png"

cat > "$APPDIR/AppRun" <<'APPRUN'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec /usr/bin/python3 -I -B "$HERE/opt/lastbook/lastbook.py" "$@"
APPRUN
chmod 755 "$APPDIR/AppRun"

# appimagetool runs as an AppImage itself. APPIMAGE_EXTRACT_AND_RUN keeps it working on CI machines without FUSE.
TOOL="$OUT/appimagetool-$APPIMAGE_ARCH.AppImage"
if [ ! -x "$TOOL" ]; then
  curl -fsSL -o "$TOOL" \
    "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-$APPIMAGE_ARCH.AppImage"
  chmod 755 "$TOOL"
fi
APPIMAGE="$OUT/Lastbook-${VERSION}-linux-${ARCH}.AppImage"
ARCH="$APPIMAGE_ARCH" APPIMAGE_EXTRACT_AND_RUN=1 "$TOOL" "$APPDIR" "$APPIMAGE"
chmod 755 "$APPIMAGE"
sha256sum "$APPIMAGE" | tee "$APPIMAGE.sha256"
echo "Built: $APPIMAGE"
