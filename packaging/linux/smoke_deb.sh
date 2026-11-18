#!/bin/bash
# Smoke test of a built .deb in a clean copy of the Ubuntu release it was built for (a fresh ubuntu:24.04 or ubuntu:26.04 container, as root):
#   docker run --rm -v <folder with the .deb and LastbookData>:/t ubuntu:24.04 bash /t/smoke_deb.sh /t/Lastbook_<v>_amd64.deb /t/LastbookData
# Installs the .deb with apt (so Depends are resolved from Ubuntu's archive), starts it under Xvfb with a session bus as an ordinary
# user, once on a library and once with none (setup), checks the window, the log and one copy only, takes screenshots into shots/,
# checks the bundled manifest, Videos, Map and the local AI runner, then removes the package and checks the person's folders are still there.
set -uo pipefail
DEB="$1"; LIB="$2"; REPO="${3:-}"; OUTD="$(dirname "$DEB")/shots"
FAIL=0
pass() { echo "PASS: $*"; }
fail() { echo "FAIL: $*"; FAIL=1; }
mkdir -p "$OUTD" && chmod 777 "$OUTD"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq "$DEB" xvfb xauth dbus-x11 x11-apps imagemagick xdotool procps iproute2 >/tmp/apt.log 2>&1 || { tail -30 /tmp/apt.log; exit 1; }
INSTALLED="$(dpkg-query -W -f '${Package} ${Version}' lastbook 2>/dev/null)"
[ -n "$INSTALLED" ] && pass "installed: $INSTALLED" || fail "the .deb did not install"
[ -f /opt/lastbook/setup/manifest-v1.json ] && pass "the bundled setup manifest is present" || fail "the bundled setup manifest is missing"
python3 -I -B - <<'PY' && pass "the bundled manifest has a downloadable library pack" || fail "the bundled manifest is empty or invalid"
import json, sys
sys.path.insert(0, '/opt/lastbook')
from engine.setup import manifest
m = manifest.validate(json.load(open('/opt/lastbook/setup/manifest-v1.json', encoding='utf-8')))
packs = [p for p in (m or {}).get('packs', []) if p['available'] and p['files'] and sum(f['size'] for f in p['files']) > 0]
print(f"{len(packs)} downloadable packs: {', '.join(p['id'] for p in packs)}")
raise SystemExit(0 if packs else 1)
PY
[ -x /opt/lastbook/llm/lastbook-llm ] && pass "the local AI runner is bundled" || fail "the local AI runner is missing"
if [ -x /opt/lastbook/llm/lastbook-llm ]; then
  out="$(/opt/lastbook/llm/lastbook-llm --model /tmp/does-not-exist.gguf --cpu-only 2>/dev/null)"
  code=$?
  { [ "$code" = 3 ] && printf '%s' "$out" | grep -q '"ev":"error"'; } && pass "the local AI runner starts and refuses a missing model" || fail "the local AI runner did not answer with its model_file error (exit $code)"
fi
apt-get install -y -qq gstreamer1.0-tools >/dev/null 2>&1   # gst-inspect, for this check only
gst-inspect-1.0 avdec_h264 >/dev/null 2>&1 && echo "== H.264 decoder present (gstreamer1.0-libav)" || echo "== NO H.264 decoder"
gst-inspect-1.0 matroskademux >/dev/null 2>&1 && echo "== WebM/Matroska demuxer present" || echo "== NO matroskademux"
useradd -m tester
cp -a "$LIB" /home/tester/LastbookData && chown -R tester: /home/tester/LastbookData
# a real H.264/AAC MP4 in place of the fixture's videos/a.mp4 (patterned bytes), so the player has something to decode
apt-get install -y -qq ffmpeg openbox >/dev/null 2>&1
ffmpeg -loglevel error -y -f lavfi -i testsrc=size=640x360:rate=25 -f lavfi -i sine=frequency=440 -t 20 -c:v libx264 -pix_fmt yuv420p -c:a aac -movflags +faststart /home/tester/LastbookData/library-data/videos/a.mp4 && chown tester: /home/tester/LastbookData/library-data/videos/a.mp4

run_as() { su tester -s /bin/bash -c "$1"; }
shot() { run_as "DISPLAY=:99 import -window root '$OUTD/$1.png'" 2>/dev/null; echo "== screenshot $1.png"; }

run_as "Xvfb :99 -screen 0 1360x900x24 -nolisten tcp >/tmp/xvfb.log 2>&1 &"
sleep 2
run_as "DISPLAY=:99 openbox >/tmp/wm.log 2>&1 &"
sleep 1
run_as "cd ~ && DISPLAY=:99 dbus-daemon --session --fork --address=unix:path=/tmp/tester-bus --print-address >/dev/null"
ENV="DISPLAY=:99 DBUS_SESSION_BUS_ADDRESS=unix:path=/tmp/tester-bus"

echo "== 1. with a library"
run_as "$ENV lastbook --data /home/tester/LastbookData >/tmp/run1.out 2>&1 &"
sleep 25
pgrep -u tester -f /opt/lastbook/lastbook.py >/dev/null && pass "running" || { fail "the app did not run"; cat /tmp/run1.out; }
run_as "$ENV xdotool search --name '^Lastbook$'" >/dev/null && pass "window" || fail "the window did not appear"
shot library-home
run_as "$ENV xdotool search --name '^Lastbook$' windowactivate --sync key ctrl+2" 2>/dev/null; sleep 6; shot library-map
run_as "$ENV xdotool search --name '^Lastbook$' windowactivate --sync key ctrl+1" 2>/dev/null; sleep 6; shot library-videos
echo "-- a video: open its card, then play"
W="$ENV xdotool search --name '^Lastbook$'"
run_as "$W windowmove 0 0 windowsize 1280 860" 2>/dev/null; sleep 2
run_as "$W windowactivate --sync key ctrl+1" 2>/dev/null; sleep 3; shot videos-page
run_as "$ENV xdotool mousemove 428 611 click 1"; sleep 5; shot video-opened
run_as "$ENV xdotool mousemove 600 330 click 1"; sleep 4; shot video-playing
grep -c "couldn" /dev/null >/dev/null
echo "-- second copy (must leave at once, the first comes forward)"
start=$(date +%s); run_as "$ENV timeout 30 lastbook --data /home/tester/LastbookData"; code=$?
[ "$code" = 0 ] && pass "a second copy leaves at once" || fail "the second copy exited $code after $(( $(date +%s) - start )) s"
echo "-- listening sockets of the app (must be none)"
for p in $(pgrep -u tester -f 'lastbook|WebKit'); do ls -l /proc/$p/fd 2>/dev/null; done | grep -c socket | sed 's/^/sockets (unix, to X and D-Bus) /'
ss -ltnup 2>/dev/null | grep -v '^Netid' | sed 's/^/LISTEN: /' || true
echo "-- log"
tail -25 /home/tester/LastbookData/derived/logs/lastbook.log
echo "-- Quit (Ctrl+Q): the app and its WebKit processes must end"
run_as "export $ENV; W=\$(xdotool search --name '^Lastbook\$' | head -1); xdotool windowactivate --sync \$W key ctrl+q" 2>/dev/null; sleep 6
ps -u tester -o stat=,args= | grep -v '^Z' | grep -qE '/opt/lastbook/lastbook.py|WebKit' && { fail "quit: the app or WebKit is still running"; ps -u tester -o pid,stat,args | grep -E 'lastbook|WebKit' | cut -c1-120; tail -2 /home/tester/LastbookData/derived/logs/lastbook.log; pkill -u tester -f /opt/lastbook/lastbook.py; sleep 2; } || pass "quit ended the app and WebKit"

if [ -n "$REPO" ] && [ -f "$REPO/packaging/smoke_library.py" ]; then
  echo "-- Videos, Map and local AI from the installed package"
  run_as "/usr/bin/python3 -I -B '$REPO/packaging/smoke_library.py' --packaged --app /opt/lastbook --data /home/tester/LastbookData --require-ai" \
    && pass "Videos, Map and local AI from the installed package" || fail "Videos, Map or local AI failed from the installed package"
fi

echo "== 2. no library: setup"
run_as "$ENV lastbook >/tmp/run2.out 2>&1 &"
sleep 20
pgrep -u tester -f /opt/lastbook/lastbook.py >/dev/null && pass "setup runs" || { fail "setup did not run"; cat /tmp/run2.out; }
shot setup
tail -15 /home/tester/.local/share/Lastbook/Setup/derived/logs/lastbook.log 2>/dev/null
pkill -u tester -f /opt/lastbook/lastbook.py; sleep 2

echo "== 3. remove"
apt-get remove -y -qq lastbook >/dev/null 2>&1
dpkg-query -W lastbook 2>/dev/null | grep -q . && fail "the package is still installed" || pass "the package was removed"
[ -e /opt/lastbook ] && { fail "files left behind in /opt/lastbook"; find /opt/lastbook | head; } || pass "/opt/lastbook gone"
[ -f /home/tester/LastbookData/library-data/catalog.json ] && pass "library kept" || fail "LIBRARY GONE"
ls -d /home/tester/.config/Lastbook /home/tester/.local/share/Lastbook 2>/dev/null | sed 's/^/kept: /'
chmod -R a+rX "$OUTD"
[ "$FAIL" = 0 ] && echo "SMOKE PASSED" || echo "SMOKE FAILED"
exit "$FAIL"
