#!/bin/bash
# Local AI regression checks on this Mac (prewarm, lifecycle, questions while preparing), with the exact model, read only.
#   bash tools/run_ai_regression.sh [MODEL_FOLDER]      Output: build/aiharness-reg/<scenario>.txt (+ .err: the app's log)
set -uo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
MODEL="${1:-$HOME/Models/gemma-4-26b-a4b}"
DATA="$HERE/build/LastbookData"
SRC="${LASTBOOK_SOURCE:-$(cd "$HERE/../.." && pwd)}"
O="$HERE/build/aiharness-reg"
H="$HERE/build/aiharness"
rm -rf "$O"; mkdir -p "$O/empty"
run() {   # name state-file model-folder scenario [env...]
  local name="$1" st="$2" mf="$3" sc="$4"; shift 4
  echo "== $name"
  env "$@" "$H" "$DATA" "$SRC" "$mf" "$st" "$O/$name" "$sc" > "$O/$name.txt" 2> "$O/$name.err"
  echo "   exit $?: $(grep -E 'ALL PASS|FAILURES' "$O/$name.txt")"
}
SLOW=LASTBOOK_AI_TEST_SLOW_LOAD_MS=25
# 1. A first launch with no remembered check: a question asked while it checks waits through checking, measuring, loading.
run q-checking  "$O/state-fresh.json" "$MODEL" q-checking
# 2. Relaunch twice with that state: no SHA read (log "remembered"), straight to loading.
run relaunch-1  "$O/state-fresh.json" "$MODEL" relaunch
run relaunch-2  "$O/state-fresh.json" "$MODEL" relaunch
# 3. Checked but never measured: a question during measuring.
python3 -c "import json,sys; d=json.load(open(sys.argv[1])); d.pop('fit',None); json.dump(d,open(sys.argv[2],'w'))" "$O/state-fresh.json" "$O/state-nofit.json"
run q-measuring "$O/state-nofit.json" "$MODEL" q-measuring
cp "$O/state-fresh.json" "$O/state.json"
run prewarm     "$O/state.json" "$MODEL" prewarm
echo "   loads started during prewarm despite repeated prewarm calls: $(grep -c 'local AI: loading (' "$O/prewarm.err") (want 1)"
run prewarm-slow "$O/state.json" "$MODEL" prewarm "$SLOW"
run q-loading   "$O/state.json" "$MODEL" q-loading "$SLOW"
run q-stop      "$O/state.json" "$MODEL" q-stop "$SLOW"
run background  "$O/state.json" "$MODEL" background "$SLOW"
run memory      "$O/state.json" "$MODEL" memory
cp "$O/state.json" "$O/state-off.json"
run disabled    "$O/state-off.json" "$MODEL" disabled
run missing     "$O/state-missing.json" "$O/empty" missing
echo "logs: $O"
