# Private Omarchy test build

This is an experimental, private testing copy of [Lastbook](https://github.com/Immortal-Protocols/lastbook), based on upstream commit `83f2ca9`. No upstream PR has been submitted. It adds native Arch packaging around Lastbook's existing GTK 3 / WebKitGTK window, not a browser wrapper or an HTTP server.

## Status

- The native x86_64 Arch package built successfully with Python 3.14.10.
- The required TLS-root check and both package-content scans passed.
- The repository test suite ran 323 tests successfully, with 4 skipped. This was a host-side test run, not proof of all features on Omarchy.
- The real Small library was downloaded and verified against the publisher's SHA-256. That library is not committed or bundled in the app package.
- Actual Omarchy / Hyprland desktop behavior remains unverified. The nested compositor test hit protocol-version mismatches; this is not a successful application test.
- This initial package does **not** include the local AI runner. Do not expect generated AI answers. The intended scope is the library, search, maps, and media.
- Independent Fable review (claude-fable-5-2) of `7bdb1b6`: **OK for private testing**. It found no build breaker, new network path, or unsafe pacman step. Full desktop/media testing remains open. Treat this as a test build, not an upstream release.

## Install the test package

Before installing, note these two limits from the independent review:

- **Untick “Local AI” in setup.** Setup may still suggest the roughly 17 GB AI model, but this package has no AI runner, so the download would be wasted.
- **Python upgrades.** The package requires Python 3.14. When Arch moves to Python 3.15, pacman will refuse the full system upgrade while this package is installed. Run `sudo pacman -R lastbook`, upgrade the system, then install a rebuilt package. Your library and settings stay in place.

Use an x86_64 Omarchy machine with Python **3.14**. The package declares that Python ABI dependency; do not force it onto another Python minor version.

Download the `.pkg.tar.zst` file and its `.sha256` companion from this private repository's prerelease. From the download directory:

```bash
sha256sum -c lastbook-1.1.9-1-x86_64.pkg.tar.zst.sha256
sudo pacman -U ./lastbook-1.1.9-1-x86_64.pkg.tar.zst
lastbook
```

Pacman resolves the declared GTK, WebKitGTK, GStreamer and Python dependencies. Use your normal Omarchy update process first if dependency versions are out of date. The app should also appear as **Lastbook** in the application launcher.

Use a separate library folder for testing. First-run setup requires internet to acquire the library; Small needs approximately 7.7 GB. An existing verified library may instead be selected. Do not put the only copy of important data into an experimental workflow.

## What to check

1. Launch from Omarchy's application menu; confirm the setup window appears and the folder picker works.
2. Open or download a library, then check search, PDF pages, the map, an encyclopedia entry, and video playback/seeking.
3. Verify it is a native Wayland window with `hyprctl clients` (`xwayland: 0` or `false`). Test tiling, resize, full screen and your display scaling.
4. Disconnect from the internet after setup and repeat reading/search/media checks.
5. Open a second copy, quit, and relaunch; report errors or leftover processes.

Please report the command you ran, exact error, Omarchy / Hyprland versions, Python version and whether the window appeared. Avoid sharing library contents, private paths or other personal information.

## Build from source instead

```bash
gh repo clone jonnyace/lastbook-omarchy
cd lastbook-omarchy
```

Follow [the native Arch build instructions](packaging/linux/arch/README.md). The build requires explicit manifest input and matching Python wheels; it does not install dependencies, disable security checks, or install the resulting package automatically.

## Updates and removal

Use this testing repository for updates. The inherited in-app update screen may still refer to Ubuntu / a `.deb`, which is not an Arch update route. Do not install that package on Omarchy.

```bash
sudo pacman -R lastbook
```

The package owns application files only. Library/settings folders are outside the package and should remain; package removal with user data still needs a real desktop test. A future Arch Python minor upgrade requires rebuilding the app package; never bypass pacman's dependency check.
