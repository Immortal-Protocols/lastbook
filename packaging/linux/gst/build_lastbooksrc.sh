#!/bin/sh
# lastbooksrc: the GStreamer source for lastbook://app/videos/ (WebKitGTK's player has none for a custom scheme; shell_linux.py points
# the web process at gst/). One build command for every Linux package (build_app_linux.sh, flatpak/org.lastbook.Lastbook.yml).
#   sh packaging/linux/gst/build_lastbooksrc.sh OUT.so
# Needs gcc, pkg-config and GStreamer's development files.
set -eu
OUT="${1:?where to write libgstlastbooksrc.so}"
LINUX="$(dirname "$(dirname "$(realpath "$0")")")"     # packaging/linux, written as "lastbook" in the binary
gcc -shared -fPIC -O2 -Wall -Werror -s -ffile-prefix-map="$LINUX"=lastbook "$LINUX/gst/lastbooksrc.c" -o "$OUT" \
  $(pkg-config --cflags --libs gstreamer-1.0 gstreamer-base-1.0)
