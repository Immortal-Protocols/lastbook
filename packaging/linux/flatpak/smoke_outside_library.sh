#!/usr/bin/env bash
# The installed org.lastbook.Lastbook Flatpak with a library the person chose outside the app's own folder, as on a real desktop:
#   1. no grant: given the outside folder's path with --data, the sandbox cannot see it, and the app says it found no library
#   2. open: --ask, then the real file chooser (the document portal and its GTK chooser), driven with the keyboard; the app opens the
#      library through the portal's /run/user/<uid>/doc/ path and remembers it
#   3. reopen offline: the whole session is ended and a new one started (as after logging out), then the app is started with no
#      arguments and no network (--unshare=network): it opens the remembered library, the app's own sandbox has no routes, a video
#      plays, a search finds pages and a manual page opens drawn
# It runs in a namespace of its own (unshare) with an empty /run/user/<uid> and its own session bus, document portal and permission
# store, so the person's desktop session and their own portal permissions are never touched, and the chooser shows on a private
# Xvfb display. Needs unshare and setpriv (util-linux), dbus-run-session, xdg-desktop-portal and xdg-desktop-portal-gtk, Xvfb, openbox, xdotool and ImageMagick.
#   bash packaging/linux/flatpak/smoke_outside_library.sh [shots-folder] [outside-folder]
# The library in the app's data folder (see README.md) is moved to outside-folder (default ~/LastbookOutside) for the run and
# moved back afterwards, as is the remembered choice.
set -uo pipefail
APP=org.lastbook.Lastbook
OUT="$(realpath -m "${1:-shots-outside}")"
OUTSIDE="$(realpath -m "${2:-$HOME/LastbookOutside}")"
APPDIR="$HOME/.var/app/$APP"
LIB="$APPDIR/data/Lastbook/LastbookData"
SETTINGS="$APPDIR/config/Lastbook/settings.json"
DISP=:99
HERE="$(dirname "$(realpath "$0")")"

if [ "${1:-}" != --inside ]; then
  # ---------------------------------------------------------------------------------------------------- outside the namespace --
  flatpak ps --columns=application | grep -qx "$APP" && { echo "Lastbook is open: quit it first"; exit 2; }
  [ -f "$LIB/library-data/catalog.json" ] || { echo "no library in $LIB (see README.md)"; exit 2; }
  [ -e "$OUTSIDE/LastbookData" ] && { echo "$OUTSIDE/LastbookData already exists"; exit 2; }
  case "$OUTSIDE/" in "$APPDIR"/*) echo "the outside folder must not be in $APPDIR"; exit 2;; esac
  for t in unshare setpriv dbus-run-session Xvfb openbox xdotool import; do command -v $t >/dev/null || { echo "needs $t"; exit 2; }; done
  PRIVATE="$(mktemp -d /tmp/lastbook-portal.XXXXXX)"
  mkdir -p "$OUT" "$OUTSIDE" "$PRIVATE/data" "$PRIVATE/config/xdg-desktop-portal"
  printf '[preferred]\ndefault=gtk\n' > "$PRIVATE/config/xdg-desktop-portal/lastbooktest-portals.conf"
  mv "$LIB" "$OUTSIDE/LastbookData"
  [ -f "$SETTINGS" ] && mv "$SETTINGS" "$PRIVATE/settings.json.saved"
  Xvfb $DISP -screen 0 1360x900x24 -nolisten tcp >"$OUT/xvfb.log" 2>&1 & XVFB=$!
  sleep 2; DISPLAY=$DISP openbox >/dev/null 2>&1 & WM=$!; sleep 1
  restore() {
    kill "$XVFB" "$WM" 2>/dev/null
    mv "$OUTSIDE/LastbookData" "$LIB" && rmdir "$OUTSIDE" 2>/dev/null
    rm -f "$SETTINGS"; [ -f "$PRIVATE/settings.json.saved" ] && mv "$PRIVATE/settings.json.saved" "$SETTINGS"
    rm -rf "$PRIVATE"
    [ -f "$LIB/library-data/catalog.json" ] && echo "== library moved back to the app's folder" || echo "LIBRARY NOT MOVED BACK: it is in $OUTSIDE"
  }
  trap restore EXIT
  # Its own user and mount namespace (keeping this user's id) with an empty /run/user/<uid>: the document portal mounts its FUSE
  # file system there, at the path a real desktop has, which the setuid fusermount cannot do inside bwrap.
  unshare --user --map-current-user --mount --keep-caps env PRIVATE="$PRIVATE" HERE="$HERE" OUT="$OUT" OUTSIDE="$OUTSIDE" bash -c '
    RUNTIME="/run/user/$(id -u)"
    mount -t tmpfs -o mode=0700 tmpfs "$RUNTIME" || exit 3
    export XDG_RUNTIME_DIR="$RUNTIME" XDG_DATA_HOME="$PRIVATE/data" FLATPAK_USER_DIR="$HOME/.local/share/flatpak"
    export XDG_CONFIG_DIRS="$PRIVATE/config:/etc/xdg" XDG_CURRENT_DESKTOP=lastbooktest GIO_USE_VFS=local GIO_USE_VOLUME_MONITOR=unix DISPLAY=:99
    unset WAYLAND_DISPLAY DBUS_SESSION_BUS_ADDRESS
    exec bash "$HERE/smoke_outside_library.sh" --inside "$OUT" "$OUTSIDE"'
  exit $?
fi

# ------------------------------------------------------------------------------------------------------- inside the namespace --
OUT="$2"; OUTSIDE="$3"; FAILED=0
fp() { setpriv --inh-caps=-all --ambient-caps=-all flatpak "$@"; }   # flatpak's own bwrap refuses to start with capabilities
pass() { echo "PASS  $*"; }
fail() { echo "FAIL  $*"; FAILED=1; }
running() { flatpak ps --columns=application | grep -qx "$APP"; }
x() { DISPLAY=$DISP "$@"; }
start() {   # start LOG [flatpak options] [-- app options]
  local log="$1" fo=(); shift
  while [ $# -gt 0 ] && [ "$1" != -- ]; do fo+=("$1"); shift; done; [ "${1:-}" = -- ] && shift
  (fp run --nosocket=wayland --socket=x11 "${fo[@]}" $APP "$@" >"$OUT/$log.log" 2>&1 &); }
wait_window() { for _ in $(seq 40); do x xdotool search --onlyvisible --name "$1" >/dev/null 2>&1 && return 0; sleep 1; done; return 1; }
wait_app() { for _ in $(seq 40); do { x xdotool search --onlyvisible --classname "^[Ll]astbook$" || x xdotool search --onlyvisible --class "^[Ll]astbook$"; } >/dev/null 2>&1 && return 0; sleep 1; done; return 1; }   # its dialogs have no title
fit() { for w in $(x xdotool search --name '^Lastbook$'); do x xdotool windowmove "$w" 0 0 windowsize "$w" 1280 860; done; sleep 2; }
shot() { x import -window root "$OUT/$1.png"; }
click() { x xdotool mousemove "$1" "$2" click 1; sleep "${3:-4}"; }
quit() { for w in $(x xdotool search --name '^Lastbook$'); do x xdotool windowactivate --sync "$w" key ctrl+q 2>/dev/null; done
         for _ in $(seq 15); do running || return 0; sleep 1; done; return 1; }
frames_differ() {
  x import -window root -crop 583x327+301+142 "$OUT/.a.png"; sleep 2; x import -window root -crop 583x327+301+142 "$OUT/.b.png"
  local n; n="$(compare -metric AE "$OUT/.a.png" "$OUT/.b.png" null: 2>&1 | cut -d' ' -f1 | cut -d. -f1)"; rm -f "$OUT"/.?.png; [ "${n:-0}" -gt 0 ]; }
since_start() { awk '/ start pid=/ {s = ""} {s = s $0 "\n"} END {printf "%s", s}' "$OUTSIDE/LastbookData/derived/logs/lastbook.log"; }   # the log from the app's last start
remembered() { python3 -I -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["library"])' "$SETTINGS" 2>/dev/null; }
colours() { magick "$OUT/$1.png" -crop "$2" +repage -format %k info:; }   # distinct colours in a part of a screenshot
changed() { [ "$(compare -metric AE "$OUT/$1.png" "$OUT/$2.png" null: 2>&1 | cut -d' ' -f1 | cut -d. -f1)" -gt 0 ]; }
app_routes() {   # routes in the running app's own network namespace (1 = only the header line: no network at all)
  local pid; pid="$(ps -eo pid=,comm=,args= | awk '$2 == "python3" && /\/app\/lastbook\/lastbook\.py/ {print $1; exit}')"
  [ -n "$pid" ] && wc -l < "/proc/$pid/net/route"; }
session() {   # one desktop session: its own bus and document portal; the steps run without the namespace's capabilities
  local nocaps=(setpriv --inh-caps=-all --ambient-caps=-all) doc rc
  doc="$(sed -n 's/^Exec=//p' "$(for d in ${XDG_DATA_DIRS//:/ }; do ls "$d/dbus-1/services/org.freedesktop.portal.Documents.service" 2>/dev/null; done | head -1)")"
  # The bus starts every other service when asked, without capabilities: GTK's image loaders and Flatpak's portal run bwrap,
  # which refuses to start with them. Only the document portal keeps them, to mount its FUSE file system (no setuid fusermount here).
  export DBUS_SESSION_BUS_ADDRESS
  DBUS_SESSION_BUS_ADDRESS="$("${nocaps[@]}" dbus-daemon --session --fork --print-address=1 --print-pid=3 3>"$OUT/.bus-pid" | head -1)"
  $doc >"$OUT/document-portal.log" 2>&1 & local docpid=$!
  for _ in $(seq 20); do grep -q " $XDG_RUNTIME_DIR/doc " /proc/self/mounts && break; sleep 0.5; done
  "${nocaps[@]}" bash -c "FAILED=0
$1
exit \$FAILED"; rc=$?
  running && fp kill $APP; kill "$docpid" "$(cat "$OUT/.bus-pid")" 2>/dev/null; sleep 1
  umount "$XDG_RUNTIME_DIR/doc" 2>/dev/null; rm -f "$OUT/.bus-pid"
  return $rc
}
export -f fp pass fail running x start wait_window wait_app fit shot click quit frames_differ since_start remembered colours changed app_routes
export APP OUT OUTSIDE DISP SETTINGS LIB

echo "== 1. no grant: --data names the outside folder"
session '
  start no-grant -- --data "$OUTSIDE/LastbookData"
  if wait_app; then sleep 3; shot 01-no-grant; fi
  fp run --command=sh $APP -c "test -e \"$OUTSIDE/LastbookData\"" && fail "the sandbox can see $OUTSIDE without a grant" \
    || pass "the sandbox cannot see the outside folder without a grant"
  x xdotool key Return; sleep 2; running && { flatpak kill $APP; sleep 1; }' || FAILED=1

echo "== 2. open: --ask, then the file chooser"
session '
  start ask -- --ask
  wait_app || { fail "no question window"; exit 1; }
  sleep 2; shot 02-ask
  x xdotool key Return                                  # "Choose Folder…", the default
  wait_window "Choose the folder called LastbookData" || { fail "the file chooser did not open"; exit 1; }
  sleep 2; pass "the file chooser opened (document portal, GTK chooser)"
  w=$(x xdotool search --onlyvisible --name "Choose the folder called LastbookData" | head -1)
  x xdotool windowactivate --sync $w key alt+Home; sleep 1
  x xdotool key ctrl+l; sleep 1; x xdotool key ctrl+a
  x xdotool type --delay 15 "$OUTSIDE/LastbookData/"; sleep 2
  x xdotool key Return; sleep 3
  x xdotool search --onlyvisible --name "Choose the folder called LastbookData" >/dev/null 2>&1 && { x xdotool key Return; sleep 3; }
  for _ in $(seq 30); do [ -n "$(remembered)" ] && break; sleep 1; done
  lib="$(remembered)"
  case "$lib" in /run/user/*/doc/*/LastbookData) pass "chosen and remembered through the document portal: $lib";;
                 *) fail "remembered library: ${lib:-none}"; shot 03-open-failed; exit 1;; esac
  wait_window "^Lastbook$" && sleep 6 && fit && shot 03-opened
  doc="${lib%/LastbookData}"; doc="${doc##*/}"     # the app logs the resolved path, /run/flatpak/doc/<id>/LastbookData
  grep -qE "args=\[.--ask.\] data=/run/(flatpak|user/[0-9]+)/doc/$doc/LastbookData" "$OUTSIDE/LastbookData/derived/logs/lastbook.log" \
    && pass "the app opened it (its log, in the outside folder, says so)" || fail "the log does not show the app opening $lib"
  since_start | grep -q Traceback && fail "a Python error in the log: $(since_start | grep -E "^[A-Za-z.]+Error" | tail -1)"
  quit && pass "Ctrl+Q ends the app" || fail "still running after Ctrl+Q"' || FAILED=1

echo "== 3. reopen, in a new session, with no network"
session '
  start reopen --unshare=network
  wait_window "^Lastbook$" || { fail "no window on reopening"; exit 1; }
  sleep 6; fit; shot 04-reopened
  lib="$(remembered)"
  case "$lib" in /run/user/*/doc/*/LastbookData) ;; *) fail "nothing remembered to reopen: ${lib:-none}"; exit 1;; esac
  doc="${lib%/LastbookData}"; doc="${doc##*/}"
  since_start | head -1 | grep -qE "args=\[\] data=/run/(flatpak|user/[0-9]+)/doc/$doc/LastbookData$" \
    && pass "reopened the remembered library with no arguments: $lib" || fail "did not reopen $lib"
  since_start | grep -q Traceback && fail "a Python error in the log: $(since_start | grep -E "^[A-Za-z.]+Error" | tail -1)"
  routes="$(app_routes)"
  [ "$routes" = 1 ] && pass "no network in the running app sandbox (no routes)" || fail "the running app sandbox has a network: ${routes:-no app process} lines in its route table"
  click 426 505 5; click 592 306 8; shot 05-video
  frames_differ && pass "a video plays from the outside library (picture or clock moves)" || fail "the video does not move"
  click 1143 78 1; x xdotool type --delay 40 "boil water"; x xdotool key Return; sleep 6; shot 06-search
  n="$(colours 06-search 934x180+301+636)"
  changed 05-video 06-search && [ "$n" -gt 1500 ] && pass "search found pages, the first with its page drawn ($n colours)" \
    || fail "no search results with a drawn page ($n colours where the first result should be)"
  click 627 657 6; shot 07-reader
  n="$(colours 07-reader 934x735+301+120)"
  changed 06-search 07-reader && [ "$n" -gt 5000 ] && pass "a manual page opens and is drawn ($n colours)" \
    || fail "no manual page drawn ($n colours in the page area)"
  quit && pass "Ctrl+Q ends the app" || fail "still running after Ctrl+Q"' || FAILED=1

echo "== screenshots in $OUT"
[ $FAILED = 0 ] && echo "== all checks passed" || { echo "== some checks FAILED"; exit 1; }
