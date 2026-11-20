# Lastbook for Android (development preview)

A native Android app for the Lastbook offline survival library: **Videos, Map, Chat and Library**, working offline from a library stored on the phone. Like `mobile/ipad`, this is **source for contributors**, not a store release.

Licence: MIT, like the rest of this repository (see [`/LICENSE`](../../LICENSE)). Third-party parts are listed in [`/THIRD_PARTY_NOTICES.md`](../../THIRD_PARTY_NOTICES.md).

## What works

- **Videos:** a native Compose home feed ("Picked for the guides" plus category rows up to 10 items with "Show all"), title search, duration filter chips (Under 10 min / 10–30 min / Over 30 min), and a native Media3 ExoPlayer watch page with playback speed, Picture in Picture, resume point, searchable synchronized transcript, and Up next.
- **Map:** the offline map from the desktop app (`web/map.js` + local SQLite tile/query endpoints in a WebView, no listening port), keeping search, layers, zoom/3D and place cards, plus a **native "Nearby" bottom sheet** listing items near the map center that focuses the map and opens the place card on tap.
- **Chat:** answers from the library with numbered citations (`[S1]`, `[S2]`, …) that open the exact PDF page or video moment, starter prompts, searchable chat history with per-chat delete, keep-history toggle, and delete-all.
  - With the optional local AI (Gemma 4 E2B / 12B / 26B or a custom `.gguf`, run in-process by `llama.cpp` via JNI), Chat writes cited answers on-device.
  - Without the local AI, Chat shows the matching library pages with an option to install local AI.
- **Library:** readiness checklist (library pack, state map, street addresses, local AI, encyclopedias), storage path & location switcher, searchable/filterable catalog of everything on device (All / Reading / Videos / Encyclopedias), native `PdfRenderer` PDF reader, saved web page reader, and a **ZIM Encyclopedia Reader** (`libkiwix`/`libzim`) with back/forward/home toolbar, instant title suggestions, and full-text search.
- **First-run setup & background progress:**
  1. Choose your state (required; no location lookup).
  2. Choose a library size (`Small / Medium / All`), with download, installed, and peak space shown and sizes that cannot fit disabled with an explanation.
  3. Toggle local AI (auto-selects the best tier for the phone's RAM: Gemma 4 E2B on 8 GB phones, Gemma 4 12B on 12–16 GB phones, Gemma 4 26B on 24+ GB devices, or pick a custom `.gguf` file with GGUF magic validation).
  4. Choose storage location (external app storage, internal app storage, or custom folder via All Files Access).
  5. Foreground service (`InstallService`) runs `downloading → checking → unpacking → finishing` with Pause, Resume, Cancel, SHA-256 verification, and automatic recovery if interrupted (`install-job.json`).

## Build and test

Prerequisites:
- JDK 17+ (tested with JDK 21)
- Android SDK (compileSdk 36, minSdk 29) and NDK `27.0.12077973` with CMake `3.22.1`
- The pinned `llama.cpp` checkout prepared via `cd ../ipad && bash scripts/prepare_dependencies.sh`

Build and install on a connected Android device:

```bash
cd mobile/android
./gradlew installDebug
```

Run engine unit tests (manifest & RAM tier selection, plan space/fit calculation, catalog & trust weighting, geo haversine/clipping, SHA-256 & zip-slip checks):

```bash
./gradlew :core:testDebugUnitTest
```

Run connected Compose UI tests on a device:

```bash
./gradlew :app:connectedDebugAndroidTest
```


## Notes

- The native AI library is compiled with `-O3` even in debug builds. A debug (`-O0`) llama.cpp is more than an order of magnitude slower; with `-O3`, Gemma 4 E2B answers a typical question in about 20 seconds on the Moto G Power 2026 (8 GB).
- Connected UI tests uninstall and reinstall the app when they finish. If you keep a seeded library in app storage, back it up or re-push it after `connectedDebugAndroidTest`.
