#!/bin/bash
# Assembles a ready-to-copy LastbookData for a device test: the Small pack + one state map set + the H.264 video copies.
# Everything is an APFS clone (cp -c) of the published/built files; sources are only read.
#
#   bash tools/assemble_handoff.sh STATE OUT_DIR
#   e.g. bash tools/assemble_handoff.sh CA build/handoff/Small-CA
#
# The state map replaces the pack's own map set file by file, as desktop setup does (SETUP-API "State maps"): every file
# map-set.json lists, plus map-set.json itself. It is checked afterwards (each listed file at its listed size).
set -euo pipefail
ST="${1:?state code}"; OUT="${2:?output folder}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
REPO="${LASTBOOK_SOURCE:-$(cd "$HERE/../.." && pwd)}"
PACK="$REPO/derived/packs/small"
MAP="$REPO/derived/packs/maps/$ST"
SIDE="$HERE/build/video-compat/h264-v1"
case "$(cd "$(dirname "$OUT")" 2>/dev/null && pwd)/" in
  */build/handoff/*) [ -f "$HERE/build/handoff/FROZEN" ] && { echo "build/handoff is FROZEN (a device test is using it): write to build/handoff-next/ instead"; exit 1; } ;;
esac
[ -f "$MAP/map-set.json" ] || { echo "no map set for $ST at $MAP"; exit 1; }
[ -f "$SIDE/manifest.json" ] || { echo "no video sidecar at $SIDE (run build/videocompat first)"; exit 1; }
rm -rf "$OUT"; mkdir -p "$OUT"
L="$OUT/LastbookData"
cp -cR "$PACK" "$L"
/usr/bin/python3 - "$MAP" "$L" <<'EOF'
import json, os, shutil, subprocess, sys
src, dst = sys.argv[1], sys.argv[2]
m = json.load(open(os.path.join(src, 'map-set.json')))
for rel, size in m['files'].items():
    s, d = os.path.join(src, rel), os.path.join(dst, rel)
    assert os.path.getsize(s) == size, f'{rel}: source size differs from map-set.json'
    os.makedirs(os.path.dirname(d), exist_ok=True)
    if os.path.exists(d):
        os.remove(d)
    subprocess.run(['cp', '-c', s, d], check=True)
subprocess.run(['cp', '-c', os.path.join(src, 'map-set.json'), os.path.join(dst, 'map-set.json')], check=True)
bad = [rel for rel, size in m['files'].items() if os.path.getsize(os.path.join(dst, rel)) != size]
print(f"map {m['name']}: {len(m['files'])} files, {m.get('bytes')} bytes", 'OK' if not bad else f'BAD {bad}')
sys.exit(1 if bad else 0)
EOF
# Street addresses: the state's own address index (desktop Lastbook-Addresses-<ST>.zip installs this one file).
ADDR="$REPO/derived/packs/address-indexes/$ST.sqlite"
[ -f "$ADDR" ] || { echo "no address index for $ST at $ADDR"; exit 1; }
mkdir -p "$L/derived/geo/addresses"
cp -c "$ADDR" "$L/derived/geo/addresses/$ST.sqlite"
echo "addresses $ST: $(stat -f %z "$ADDR") bytes"
mkdir -p "$L/derived/video-compat"
cp -cR "$SIDE" "$L/derived/video-compat/"
echo "video copies: $(ls "$L/derived/video-compat/h264-v1" | grep -c '\.mp4$') files"
du -sh "$L" | cut -f1 | sed 's/^/total size: /'
