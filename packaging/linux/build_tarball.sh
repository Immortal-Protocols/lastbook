#!/bin/bash
# Builds a portable Linux "bin" tarball from the staging tree that packaging/linux/build_app_linux.sh wrote.
#
#   bash packaging/linux/build_tarball.sh <stage> <version> <x64|arm64> <output-folder>
#
# The archive unpacks to Lastbook-<version>-linux-<arch>/ with the app under opt/lastbook and a launcher named lastbook.
# It uses the system's Python 3.12, GTK 3 and WebKitGTK 4.1, like the .deb does.
set -euo pipefail
STAGE="${1:?stage folder}"
VERSION="${2:?version}"
ARCH="${3:?x64 or arm64}"
OUT="${4:?output folder}"
STAGE="$(realpath "$STAGE")"
OUT="$(realpath -m "$OUT")"
[ -d "$STAGE/opt/lastbook" ] || { echo "not a Lastbook staging tree: $STAGE" >&2; exit 1; }
case "$ARCH" in x64|x86_64|amd64|arm64|aarch64) ;; *) echo "unsupported architecture: $ARCH" >&2; exit 1 ;; esac
NAME="Lastbook-${VERSION}-linux-${ARCH}"
DIR="$OUT/$NAME"
rm -rf "$DIR"
mkdir -p "$DIR/opt"
cp -a "$STAGE/opt/lastbook" "$DIR/opt/lastbook"
cat > "$DIR/lastbook" <<'LAUNCHER'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec /usr/bin/python3 -I -B "$HERE/opt/lastbook/lastbook.py" "$@"
LAUNCHER
chmod 755 "$DIR/lastbook"
cat > "$DIR/README.txt" <<'README'
Lastbook, the offline survival library.

Run ./lastbook

This build uses the system Python 3.12, GTK 3 and WebKitGTK 4.1, like the Ubuntu
package. On Ubuntu 24.04 install the runtime packages once:

  sudo apt install python3 python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.1 \
    gir1.2-soup-3.0 libwebkit2gtk-4.1-0 libgstreamer1.0-0 \
    gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-libav \
    libgomp1

Your library, settings and WebKit storage stay in your home folder.
README
chmod 644 "$DIR/README.txt"
tar -C "$OUT" -cJf "$OUT/$NAME.tar.xz" "$NAME"
sha256sum "$OUT/$NAME.tar.xz" | tee "$OUT/$NAME.tar.xz.sha256"
echo "Built: $OUT/$NAME.tar.xz"
