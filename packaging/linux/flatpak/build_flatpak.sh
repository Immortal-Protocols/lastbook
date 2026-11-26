#!/bin/bash
# Builds the Lastbook Flatpak (pilot, x86_64) from this checkout, on any Linux with flatpak and flatpak-builder:
#   flatpak install --user flathub org.gnome.Platform//51 org.gnome.Sdk//51
#   bash packaging/linux/flatpak/build_flatpak.sh [--install]
# The app folder is stage_linux.py's, the same as the .deb's /opt/lastbook (org.lastbook.Lastbook.yml). The setup manifest is made
# here first, the way build_app_linux.sh makes it, because the Flatpak build itself reads only this checkout and the pinned wheels.
# Each build gets derived/app-build/flatpak/<date-time>/ with the build folder, the package scan, and Lastbook-<version>-x86_64.flatpak:
# one file that installs with `flatpak install --user Lastbook-<version>-x86_64.flatpak` and fetches the GNOME runtime from Flathub
# the first time. --install also installs this build for this user (flatpak run org.lastbook.Lastbook).
set -euo pipefail
HERE="$(dirname "$(realpath "$0")")"
ROOT="$(dirname "$(dirname "$(dirname "$HERE")")")"
BUILD="$ROOT/derived/app-build/flatpak"
OUT="$BUILD/$(date +%Y%m%d-%H%M%S)"
INSTALL=()
[ "${1:-}" = --install ] && INSTALL=(--install)
export PYTHONDONTWRITEBYTECODE=1

[ "$(uname -m)" = x86_64 ] || { echo "build on x86_64 (aarch64 is not tried yet)" >&2; exit 1; }
command -v flatpak-builder >/dev/null || { echo "needs flatpak-builder" >&2; exit 1; }
VERSION="$(python3 -I -B -c 'import sys; sys.path.insert(0, sys.argv[1]); import stage_linux; print(stage_linux.default_version())' "$ROOT/packaging/linux")"
mkdir -p "$OUT" "$BUILD/setup"

# What setup can install, as the .deb carries it (org.lastbook.Lastbook.yml reads it from here)
python3 -I -B "$ROOT/packaging/release_manifest.py" --packs "$ROOT/derived/release/manifest-v1.json" --out "$BUILD/setup/manifest-v1.json"
if [ "${SKIP_TLS_GATE:-}" != 1 ]; then   # release gate: every download host verifies through engine/setup/roots.pem only
  python3 -I -B "$ROOT/packaging/check_tls_roots.py" || { echo "TLS roots gate failed: refresh engine/setup/roots.pem (packaging/setup_roots.py)" >&2; exit 1; }
fi

flatpak-builder --user --force-clean --state-dir="$BUILD/.flatpak-builder" --repo="$BUILD/repo" ${INSTALL[@]+"${INSTALL[@]}"} "$OUT/build" "$HERE/org.lastbook.Lastbook.yml"
python3 -I -B "$ROOT/packaging/linux/scan_package_linux.py" --flatpak "$OUT/build" --terms-file "$ROOT/derived/app-build/scan-terms.txt" | tee "$OUT/scan.txt"
FLATPAK="$OUT/Lastbook-$VERSION-x86_64.flatpak"
flatpak build-bundle --runtime-repo=https://dl.flathub.org/repo/flathub.flatpakrepo "$BUILD/repo" "$FLATPAK" org.lastbook.Lastbook
ln -sfn "$(basename "$OUT")/$(basename "$FLATPAK")" "$BUILD/latest.flatpak"
echo "Built: $FLATPAK"
ls -l "$FLATPAK"
sha256sum "$FLATPAK" | tee "$FLATPAK.sha256"
