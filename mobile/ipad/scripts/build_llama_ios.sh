#!/bin/bash
# Builds the local AI runtime linked into the iPad app: llama.cpp at the desktop's pinned commit (dde879bc, tag b12032),
# Metal on (shaders embedded, compiled on the device), static, with nothing that can open a socket (no RPC backend, no
# server, no curl, no common library beyond the fitting and its log: as packaging/llm/build_llm_macos.sh). Our bridge
# (llm/lastbook_llm_bridge.cpp, the desktop runner as in-process calls) and llama.cpp go into one static library per platform:
#
#   build/llama/iphoneos/liblastbook_llm.a          arm64 iPadOS 18+
#   build/llama/iphonesimulator/liblastbook_llm.a   arm64 iPad Simulator
#   build/llama/macosx/liblastbook_llm.a            arm64 macOS 14+ (only for the Mac test harness, tools/aiharness)
#
# The app finds the C header through llm/include/module.modulemap (Swift: import LastbookLLM).
#
#   bash scripts/build_llama_ios.sh [iphoneos|iphonesimulator|macosx|all]     (default: all)
#
# LLAMA_SRC: the llama.cpp checkout, only read (default: build/deps/llama.cpp, prepared explicitly with scripts/prepare_dependencies.sh).
# An up-to-date library is left as it is, so Xcode's build phase can call this on every build.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
COMMIT=dde879bc4f954b809892fd0d660515f42536394a
SRCROOT_LB="${LASTBOOK_SOURCE:-$(cd "$HERE/../.." && pwd)}"
L="${LLAMA_SRC:-$HERE/build/deps/llama.cpp}"
OUT="$HERE/build/llama"
BRIDGE="$HERE/llm/lastbook_llm_bridge.cpp"
HDR="$HERE/llm/include/lastbook_llm.h"
WHICH="${1:-all}"

# Xcode runs this with its own build settings in the environment (SDKROOT, ARCHS, CC...). They must not reach CMake.
if [ -z "${LB_CLEAN_ENV:-}" ]; then
  CMAKE_DIR=""
  for c in "$(command -v cmake || true)" "$HOME/.local/bin/cmake" /opt/homebrew/bin/cmake /usr/local/bin/cmake /Applications/CMake.app/Contents/bin/cmake; do
    [ -n "$c" ] && [ -x "$c" ] && { CMAKE_DIR="$(dirname "$c")"; break; }
  done
  [ -n "$CMAKE_DIR" ] || { echo "error: cmake not found (3.28 or newer is needed)" >&2; exit 1; }
  exec env -i LB_CLEAN_ENV=1 PATH="$CMAKE_DIR:/usr/bin:/bin:/usr/sbin:/sbin" HOME="$HOME" \
    DEVELOPER_DIR="${DEVELOPER_DIR:-$(xcode-select -p)}" LASTBOOK_SOURCE="$SRCROOT_LB" LLAMA_SRC="$L" /bin/bash "$0" "$WHICH"
fi

[ -f "$SRCROOT_LB/packaging/llm/fit_unused_win.cpp" ] || { echo "error: $SRCROOT_LB/packaging/llm/fit_unused_win.cpp not found" >&2; exit 1; }
[ -f "$L/CMakeLists.txt" ] || { echo "error: llama.cpp source not found at $L (run scripts/prepare_dependencies.sh, or set LLAMA_SRC)" >&2; exit 1; }
# Refuse a different or modified dependency checkout.
HEAD="$(git -C "$L" rev-parse HEAD)"
[ "$HEAD" = "$COMMIT" ] || { echo "error: llama.cpp must be pinned to $COMMIT" >&2; exit 1; }
git -C "$L" diff --quiet HEAD -- || { echo "error: llama.cpp has local modifications" >&2; exit 1; }

JOBS="$(sysctl -n hw.ncpu)"
MAP="-ffile-prefix-map=$L=llama.cpp -ffile-prefix-map=$HERE=lastbook-ipad"   # no folder of this Mac inside the app

build_one() {
  local plat="$1" sys target sdk dep
  case "$plat" in
    iphoneos)        sys=iOS;    sdk=iphoneos;        dep=18.0; target=arm64-apple-ios18.0 ;;
    iphonesimulator) sys=iOS;    sdk=iphonesimulator; dep=18.0; target=arm64-apple-ios18.0-simulator ;;
    macosx)          sys=Darwin; sdk=macosx;          dep=14.0; target=arm64-apple-macos14.0 ;;
    *) echo "error: unknown platform $plat" >&2; exit 2 ;;
  esac
  local B="$OUT/cmake-$plat" O="$OUT/$plat" lib="$OUT/$plat/liblastbook_llm.a"
  if [ -f "$lib" ] && [ "$lib" -nt "$BRIDGE" ] && [ "$lib" -nt "$HDR" ] && [ "$lib" -nt "$0" ]; then
    echo "llama ($plat): up to date"; return 0
  fi
  mkdir -p "$B" "$O"
  local SYSROOT; SYSROOT="$(xcrun --sdk "$sdk" --show-sdk-path)"
  local extra=()
  [ "$sys" = iOS ] && extra+=(-DCMAKE_SYSTEM_NAME=iOS -DGGML_METAL_TARGET_OS=ios)
  echo "llama ($plat): configuring and building (first time takes a few minutes)"
  cmake -S "$L" -B "$B" -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF \
    -DLLAMA_BUILD_COMMON=OFF -DLLAMA_BUILD_APP=OFF -DLLAMA_BUILD_TOOLS=OFF -DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_BUILD_TESTS=OFF \
    -DLLAMA_BUILD_SERVER=OFF -DLLAMA_BUILD_MTMD=OFF -DLLAMA_CURL=OFF -DLLAMA_OPENSSL=OFF -DGGML_RPC=OFF \
    -DGGML_METAL=ON -DGGML_METAL_EMBED_LIBRARY=ON -DGGML_NATIVE=OFF -DGGML_OPENMP=OFF -DGGML_CCACHE=OFF \
    -DCMAKE_OSX_SYSROOT="$SYSROOT" -DCMAKE_OSX_ARCHITECTURES=arm64 -DCMAKE_OSX_DEPLOYMENT_TARGET="$dep" ${extra[@]+"${extra[@]}"} \
    -DCMAKE_C_FLAGS="$MAP" -DCMAKE_CXX_FLAGS="$MAP" -DCMAKE_OBJC_FLAGS="$MAP" > "$OUT/cmake-$plat.log"
  cmake --build "$B" -j "$JOBS" --target llama > "$OUT/build-$plat.log"

  local objs="$OUT/obj-$plat"; rm -rf "$objs"; mkdir -p "$objs"
  local CXX=(xcrun --sdk "$sdk" clang++ -std=c++17 -O2 -DNDEBUG $MAP -target "$target" -isysroot "$SYSROOT"
             -I"$HERE/llm/include" -I"$L/include" -I"$L/ggml/include" -I"$L/common" -I"$L/vendor" -I"$L/src")
  "${CXX[@]}" -c "$BRIDGE" -o "$objs/bridge.o"
  "${CXX[@]}" -c "$L/common/fit.cpp" -o "$objs/fit.o"
  "${CXX[@]}" -c "$L/common/log.cpp" -o "$objs/log.o"
  "${CXX[@]}" -c "$L/common/json.cpp" -o "$objs/json.o"
  # fit.cpp's common_measure_memory() needs three functions of common.cpp, which is not built in. Nothing calls it; a static
  # library keeps the reference, so the desktop's stand-ins (they stop the app if ever reached) resolve it.
  "${CXX[@]}" -c "$SRCROOT_LB/packaging/llm/fit_unused_win.cpp" -o "$objs/fit_unused.o"
  local libs; libs="$(find "$B" -name '*.a' | sort)"
  rm -f "$lib"
  # shellcheck disable=SC2086
  xcrun libtool -static -no_warning_for_no_symbols -o "$lib" "$objs"/*.o $libs
  if echo "$libs" | grep -qi rpc; then echo "error: an RPC backend was built" >&2; rm -f "$lib"; exit 1; fi
  # Nothing in it may reach a network: no socket calls, no name lookups, no network classes.
  if nm -u "$lib" 2>/dev/null | grep -E '_(socket|connect|bind|listen|accept|getaddrinfo|gethostbyname|sendto|recvfrom)$|CFNetwork|CFSocket|NSURLSession|NSURLConnection|_nw_'; then
    echo "error: the local AI library imports network calls" >&2; rm -f "$lib"; exit 1
  fi
  cp "$L/LICENSE" "$O/LICENSE-llama.cpp.txt"
  cp "$L/licenses/LICENSE-jsonhpp" "$O/LICENSE-jsonhpp.txt"
  echo "llama ($plat): $(du -h "$lib" | cut -f1) $lib"
}

# One build at a time per folder: parallel Xcode builds (simulator and device) share build/llama.
mkdir -p "$OUT"
LOCK="$OUT/.lock"
for _ in $(seq 1 1800); do
  mkdir "$LOCK" 2>/dev/null && { echo $$ > "$LOCK/pid"; break; }
  pid="$(cat "$LOCK/pid" 2>/dev/null || true)"
  if [ -n "$pid" ] && ! kill -0 "$pid" 2>/dev/null; then rm -rf "$LOCK"; continue; fi   # left by a build that was stopped
  sleep 1
done
trap 'rm -rf "$LOCK"' EXIT

if [ "$WHICH" = all ]; then
  for p in iphoneos iphonesimulator macosx; do build_one "$p"; done
else
  build_one "$WHICH"
fi
