#!/bin/sh
set -e
mkdir -p "$XDG_CONFIG_HOME"

# server.py needs a library to start. On first run (or after an interrupted one) build it with the app's own
# setup code; a stopped download picks up where it was.
if [ ! -f "$LASTBOOK_DATA/library-data/catalog.json" ]; then
    python3 /opt/lastbook/packaging/docker/headless_setup.py install
fi

# The assistant only talks to a loopback model server (assistant.loopback_base). Forward a port on
# 127.0.0.1 inside the container to the real one, e.g. MODEL_UPSTREAM=ollama:11434, and set
# SURVIVAL_MODEL_BASE=http://127.0.0.1:11434.
if [ -n "$MODEL_UPSTREAM" ]; then
    port="${SURVIVAL_MODEL_BASE##*:}"
    socat "TCP-LISTEN:${port},bind=127.0.0.1,fork,reuseaddr" "TCP:${MODEL_UPSTREAM}" &
fi

# Run from source (not frozen like the desktop apps), engine/library.py imports library-data/tools/vendor-py312
# and executes library-data/tools/remote_storage.py when present. Packs exclude tools/ (pack-spec.json), so
# one that has it is not a published pack: refuse to run code that arrived with the data.
if [ -e "$LASTBOOK_DATA/library-data/tools" ]; then
    echo "refusing to start: $LASTBOOK_DATA/library-data/tools exists (code in the library folder)" >&2
    exit 1
fi

mkdir -p "$LASTBOOK_DATA/derived"
# A fixed LAN key, so links holding it (a dashboard tile) survive a reinstall. server.py only makes one if absent.
if [ -n "$LASTBOOK_LAN_KEY" ] && [ ! -s "$LASTBOOK_DATA/derived/lan-key" ]; then
    (umask 077; printf '%s' "$LASTBOOK_LAN_KEY" > "$LASTBOOK_DATA/derived/lan-key")
fi
cd /opt/lastbook
exec python3 server.py --lan --port "${LASTBOOK_PORT:-8890}" "$@"
