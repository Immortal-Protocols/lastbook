#!/bin/bash
# Builds Lastbook_<version>_<arch>.deb for Ubuntu 24.04 LTS, x86_64 or aarch64. Run inside Ubuntu 24.04 of the same architecture
# (a container is fine) from a checkout:
#   apt-get install -y python3 python3-venv python3-pil dpkg-dev binutils   (the script installs them itself when run as root)
#   bash packaging/linux/build_app_linux.sh
#
# Environment:
#   LASTBOOK_VERSION             package version (default 1.1.9)
#   LASTBOOK_BUILD_OUT           exact output folder (default derived/app-build/linux/<date-time>)
#   LASTBOOK_BUILD_ROOT          parent for timestamped output (default derived/app-build/linux)
#   LASTBOOK_CLEAN=1             remove LASTBOOK_BUILD_OUT before building
#   LASTBOOK_LLM                 local AI runner folder (default derived/llm/bin-linux)
#   LASTBOOK_PACKS               packs manifest (default derived/release/manifest-v1.json)
#   LASTBOOK_ALLOW_EMPTY_MANIFEST=1  local development only: write an empty setup manifest when LASTBOOK_PACKS is missing
#   SKIP_TLS_GATE=1              skip the roots.pem gate (not for releases)
#
# What the .deb holds (nothing is written outside these at install, and nothing at all at removal but these):
#   /opt/lastbook/            lastbook.py (the launcher), app/ (main, bridge, shell_linux), server.py and the engine, web/ and content/ as they
#                             ship (ship_app_files.py), setup/manifest-v1.json, engine/setup/roots.pem, lib/ (wheels for the system's
#                             python3 3.12: requirements_linux.txt), llm/ (lastbook-llm and its llama.cpp libraries, when derived/llm/bin-linux
#                             has them: packaging/llm/build_llm_linux.sh), gst/ (lastbooksrc, the video source: gst/lastbooksrc.c), VERSION
#   /usr/bin/lastbook          runs /usr/bin/python3 -I -B /opt/lastbook/lastbook.py
#   /usr/share/applications/lastbook.desktop, /usr/share/icons/hicolor/<size>/apps/lastbook.png
# The window is the system's GTK 3 and WebKitGTK 4.1 through python3-gi (Depends below). The person's library, settings and WebKit's
# storage live in their home folder (~/.local/share/Lastbook, ~/.config/Lastbook, ~/.cache/Lastbook) and the package never touches them.
# Each build gets derived/app-build/linux/<date-time>/; derived/app-build/linux/latest.deb points at the newest good one.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT="$(dirname "$(dirname "$HERE")")"
APP_VERSION="${LASTBOOK_VERSION:-1.1.9}"
BUILD="${LASTBOOK_BUILD_ROOT:-$ROOT/derived/app-build/linux}"
OUT="${LASTBOOK_BUILD_OUT:-$BUILD/$(date +%Y%m%d-%H%M%S)}"
OUT="$(realpath -m "$OUT")"
STAGE="$OUT/root"
OPT="$STAGE/opt/lastbook"
LLM="${LASTBOOK_LLM:-$ROOT/derived/llm/bin-linux}"
PACKS="${LASTBOOK_PACKS:-$ROOT/derived/release/manifest-v1.json}"
case "$(uname -m)" in
  x86_64) DEB_ARCH=amd64 ;;
  aarch64|arm64) DEB_ARCH=arm64 ;;
  *) echo "build on x86_64 or aarch64" >&2; exit 1 ;;
esac
DEB="$OUT/Lastbook_${APP_VERSION}_${DEB_ARCH}.deb"
export PYTHONDONTWRITEBYTECODE=1

if [ "${LASTBOOK_CLEAN:-0}" = 1 ]; then rm -rf "$OUT"; fi
OS="$(. /etc/os-release; echo "$ID $VERSION_ID")"
[ "$OS" = "ubuntu 24.04" ] || { echo "build on Ubuntu 24.04 (this is $OS): the wheels must match its python3" >&2; exit 1; }
if [ "$(id -u)" = 0 ] && ! { python3 -c 'import venv, PIL' 2>/dev/null && pkg-config --exists gstreamer-base-1.0; }; then
  apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3 python3-venv python3-pil dpkg-dev binutils file gcc pkg-config libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev >/dev/null
fi
PYV="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
[ "$PYV" = 3.12 ] || { echo "python3 is $PYV, not 3.12" >&2; exit 1; }
mkdir -p "$OPT"

# web/ and content/ as they ship, and what setup can install (the same steps as the Mac and Windows builds)
python3 -I -B "$ROOT/packaging/ship_app_files.py" "$OUT/ship"
MANIFEST_ARGS=(--packs "$PACKS" --out "$OUT/ship/setup/manifest-v1.json")
if [ ! -f "$PACKS" ] && [ "${LASTBOOK_ALLOW_EMPTY_MANIFEST:-0}" = 1 ]; then
  MANIFEST_ARGS+=(--allow-empty)
fi
python3 -I -B "$ROOT/packaging/release_manifest.py" "${MANIFEST_ARGS[@]}"
if [ "${LASTBOOK_ALLOW_EMPTY_MANIFEST:-0}" != 1 ]; then
  python3 -I -B "$ROOT/packaging/check_release_manifest.py" "$OUT/ship/setup/manifest-v1.json"
fi
if [ "${SKIP_TLS_GATE:-}" != 1 ]; then   # release gate: every download host verifies through engine/setup/roots.pem only
  python3 -I -B "$ROOT/packaging/check_tls_roots.py" || { echo "TLS roots gate failed: refresh engine/setup/roots.pem (packaging/setup_roots.py)" >&2; exit 1; }
fi

# The wheels, for this python3, into lib/
python3 -m venv "$OUT/tools"
"$OUT/tools/bin/pip" install -q --disable-pip-version-check --only-binary=:all: --no-compile --target "$OPT/lib" -r "$HERE/requirements_linux.txt"
rm -rf "$OPT/lib/bin" "$OPT/lib/numpy/tests" "$OPT/lib/numpy/_core/tests" "$OPT/lib/numpy/f2py" "$OPT/lib/numpy/testing" "$OPT/lib/pypdfium2_cli"
find "$OPT/lib" -depth \( -name tests -o -name testing -o -name __pycache__ \) -type d -exec rm -rf {} +
find "$OPT/lib" -type f -name '*_tests*' -delete

# Our own program files: only what the app imports (the list in lastbook_macos.spec, with shell_linux for shell_macos)
mkdir -p "$OPT/app" "$OPT/engine/setup" "$OPT/setup"
cp "$ROOT/app/main.py" "$ROOT/app/bridge.py" "$ROOT/app/shell_linux.py" "$OPT/app/"
cp "$ROOT/server.py" "$ROOT/retrieval.py" "$ROOT/assistant.py" "$ROOT/llm_local.py" "$OPT/"
cp "$ROOT/engine/__init__.py" "$ROOT/engine/paths.py" "$ROOT/engine/library.py" "$ROOT/engine/saved_pages.py" "$ROOT/engine/address_search.py" "$ROOT/engine/update.py" "$OPT/engine/"
cp "$ROOT"/engine/setup/*.py "$ROOT/engine/setup/roots.pem" "$OPT/engine/setup/"
cp -R "$OUT/ship/web" "$OUT/ship/content" "$OPT/"
cp "$OUT/ship/setup/manifest-v1.json" "$OPT/setup/"
cp "$HERE/lastbook.py" "$OPT/"
echo "$APP_VERSION" > "$OPT/VERSION"
LLM_NOTE="without the local AI's runner (no $LLM/lastbook-llm yet)"
if [ -x "$LLM/lastbook-llm" ]; then
  mkdir -p "$OPT/llm"
  cp "$LLM"/lastbook-llm "$LLM"/*.so* "$OPT/llm/"
  cp "$LLM"/LICENSE* "$LLM"/NOTICE* "$OPT/llm/" 2>/dev/null || true
  LLM_NOTE="with the local AI's runner from $LLM"
fi
# lastbooksrc: the GStreamer source for lastbook://app/videos/ (WebKitGTK's player has none for a custom scheme). shell_linux.py points the web process at gst/.
mkdir -p "$OPT/gst"
gcc -shared -fPIC -O2 -Wall -Werror -s -ffile-prefix-map="$HERE"=lastbook "$HERE/gst/lastbooksrc.c" -o "$OPT/gst/libgstlastbooksrc.so" $(pkg-config --cflags --libs gstreamer-1.0 gstreamer-base-1.0)
python3 -I -m compileall -q -j 0 -s "$STAGE" -p / "$OPT" >/dev/null   # imports start fast; -B at run time writes nothing into /opt

# Launcher, menu entry, icons
mkdir -p "$STAGE/usr/bin" "$STAGE/usr/share/applications" "$STAGE/usr/share/doc/lastbook"
printf '#!/bin/sh\nexec /usr/bin/python3 -I -B /opt/lastbook/lastbook.py "$@"\n' > "$STAGE/usr/bin/lastbook"
chmod 755 "$STAGE/usr/bin/lastbook"
cp "$HERE/lastbook.desktop" "$STAGE/usr/share/applications/lastbook.desktop"
python3 -I - "$ROOT/packaging/icon/tile-1024.png" "$STAGE/usr/share/icons/hicolor" <<'PY'
import sys
from pathlib import Path
from PIL import Image
src, out = Image.open(sys.argv[1]).convert('RGBA'), Path(sys.argv[2])
for n in (16, 24, 32, 48, 64, 128, 256, 512):
    d = out / f'{n}x{n}' / 'apps'
    d.mkdir(parents=True, exist_ok=True)
    src.resize((n, n), Image.LANCZOS).save(d / 'lastbook.png', optimize=True)
PY
cat > "$STAGE/usr/share/doc/lastbook/copyright" <<'TXT'
Lastbook: MIT licence, https://github.com/Immortal-Protocols/lastbook
Bundled Python packages in /opt/lastbook/lib keep their own licences (see each *.dist-info). The local AI's runner in /opt/lastbook/llm:
llama.cpp, MIT licence (LICENSE-llama.cpp.txt there).
TXT
find "$STAGE" -type d -exec chmod 755 {} +
find "$STAGE" -type f -exec chmod go-w,a+r {} +

# The package. Depends: the system's window (GTK 3, WebKitGTK 4.1 and its GObject bindings) and the codecs the library's videos need:
# H.264/AAC in MP4 through gstreamer1.0-libav, WebM and the rest through gstreamer1.0-plugins-good. With them present, WebKit never asks
# the system to go and look for a codec. The local AI's runner needs libgomp1, and libvulkan1 for graphics cards (else it runs on the CPU).
mkdir -p "$STAGE/DEBIAN"
SIZE_KB="$(du -sk --exclude=DEBIAN "$STAGE" | cut -f1)"
cat > "$STAGE/DEBIAN/control" <<CTRL
Package: lastbook
Version: $APP_VERSION
Architecture: $DEB_ARCH
Maintainer: Lastbook <noreply@lastbook.org>
Installed-Size: $SIZE_KB
Depends: python3 (>= 3.12), python3 (<< 3.13), python3-gi, gir1.2-gtk-3.0, gir1.2-webkit2-4.1, gir1.2-soup-3.0, libwebkit2gtk-4.1-0 (>= 2.40), libgstreamer1.0-0, gstreamer1.0-plugins-base, gstreamer1.0-plugins-good, gstreamer1.0-libav, libgomp1
Recommends: libvulkan1
Section: education
Priority: optional
Homepage: https://lastbook.org
Description: Offline survival library
 Lastbook searches and reads a survival library kept on this computer: guides,
 manuals, videos, maps and an encyclopedia, with no internet. It opens no network
 port. Setup downloads the library the first time; nothing else goes online unless
 you ask it to check for a newer version. The person's library and settings stay
 in their home folder and are never removed with the package.
CTRL
dpkg-deb --root-owner-group -Zxz --build "$STAGE" "$DEB" >/dev/null
SCAN_ARGS=()
if [ -f "$ROOT/derived/app-build/scan-terms.txt" ]; then
  SCAN_ARGS+=(--terms-file "$ROOT/derived/app-build/scan-terms.txt")
fi
python3 -I -B "$HERE/scan_package_linux.py" "$DEB" "${SCAN_ARGS[@]}" | tee "$OUT/scan.txt"
mkdir -p "$BUILD"
if [[ "$OUT" == "$BUILD"/* ]]; then
  ln -sfn "$(basename "$OUT")/$(basename "$DEB")" "$BUILD/latest.deb"
fi
echo "Built $LLM_NOTE: $DEB"
ls -l "$DEB"
sha256sum "$DEB" | tee "$DEB.sha256"
