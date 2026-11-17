#!/bin/bash
# Simulator review: relaunch Lastbook with launch arguments and take one screenshot.
#   bash tools/simshot.sh NAME [launch args...]     -> build/shot-NAME.png
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
SIM="${LB_SIM:?set LB_SIM to your simulator ID from xcrun simctl list devices}"
NAME="$1"; shift
xcrun simctl terminate "$SIM" local.lastbook.ipad 2>/dev/null || true
xcrun simctl launch "$SIM" local.lastbook.ipad "$@" >/dev/null
sleep "${LB_WAIT:-12}"
xcrun simctl io "$SIM" screenshot "$HERE/build/shot-$NAME.png" >/dev/null 2>&1
echo "$HERE/build/shot-$NAME.png"
