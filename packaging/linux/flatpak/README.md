# Flatpak (pilot, x86_64)

One package for every Linux distribution. It is the same app folder as the `.deb`'s `/opt/lastbook`, made by the same staging step (`../stage_linux.py`), at `/app/lastbook` on the GNOME runtime. The runtime brings Python, PyGObject, GTK 3, WebKitGTK 4.1 and GStreamer: dav1d for AV1, and H.264 through Freedesktop's codecs-extra. The `.deb` packages stay as they are while this is tried. The discussion is in #424.

Not in this pilot yet:

- the local AI runner
- aarch64
- Flathub
- a Flatpak answer to Check for updates. Today it points to the website, like the `.deb`.

## Files

- `org.lastbook.Lastbook.yml`: the manifest. It builds from this checkout, with the same steps as the `.deb`: `../stage_linux.py` for the app folder and `../gst/build_lastbooksrc.sh` for the video source. The wheels are `requirements_linux.txt`'s pins for the runtime's Python (3.14), each by SHA-256, so the build itself needs no network. `app/tests/test_flatpak_manifest.py` fails when a pin and its wheels disagree.
- `build_flatpak.sh`: makes the setup manifest as `build_app_linux.sh` does, then runs `flatpak-builder`, then the package scan (`../scan_package_linux.py --flatpak`), then writes a single-file bundle.
- `org.lastbook.Lastbook.metainfo.xml`: store data. The version and date are filled in at build time. The screenshots are the website's.
- `org.lastbook.Lastbook.png`: `packaging/icon/tile-1024.png` at 512 px, the largest icon Flatpak exports.
- `smoke_flatpak.sh`: the smoke test, following `../smoke_deb.sh`.
- `smoke_outside_library.sh`: a library the person chose outside the app's folder, through the file chooser, opened, then reopened offline.

## Build

```sh
flatpak install --user flathub org.gnome.Platform//51 org.gnome.Sdk//51
bash packaging/linux/flatpak/build_flatpak.sh --install      # needs flatpak-builder, appstream, binutils
flatpak run org.lastbook.Lastbook
```

Each build goes into `derived/app-build/flatpak/<date-time>/`, with `scan.txt` and `Lastbook-<version>-x86_64.flatpak`. That one file installs with `flatpak install --user Lastbook-<version>-x86_64.flatpak`, and fetches the GNOME runtime from Flathub the first time.

## Smoke tests

Both run on a private Xvfb display, so nothing shows on the real screen. Both expect a library in the app's own data folder, `~/.var/app/org.lastbook.Lastbook/data/Lastbook/LastbookData`. For example, unzip the Small pack into `~/.var/app/org.lastbook.Lastbook/data/Lastbook/`.

```sh
bash packaging/linux/flatpak/smoke_flatpak.sh /tmp/flatpak-shots
bash packaging/linux/flatpak/smoke_outside_library.sh /tmp/flatpak-outside-shots
```

`smoke_flatpak.sh` checks:

- one AV1 and one H.264 video from the library decode to the end inside the sandbox
- the window opens, and a video plays through `lastbooksrc`
- a second copy exits
- no listening sockets
- Ctrl+Q ends the app and its WebKit processes
- setup opens with no library
- the library is kept

`smoke_outside_library.sh` moves the library out of the app's folder for the run, and moves it back afterwards. It runs in a user and mount namespace of its own (`unshare`) with an empty `/run/user/<uid>`. There it starts its own session bus, document portal, permission store and GTK file chooser, so the person's desktop session and portal permissions are never touched. It checks:

1. **No grant.** Given the outside path with `--data`, the sandbox cannot see the folder, and the app says it found no library.
2. **Open.** With `--ask`, the app opens the real file chooser, and the outside folder is chosen by typing its path. The app opens the library through the document portal, at `/run/user/<uid>/doc/<id>/LastbookData`, and remembers it.
3. **Reopen offline.** The session ends and a new one starts, as after logging out. Then the app starts with no arguments and with `--unshare=network`. It opens the remembered library, and the running app's own network namespace has no routes. A video plays, a search finds pages (the first one with its page drawn), and a manual page opens and is drawn.

Needed on the host: `unshare` and `setpriv` (util-linux), `dbus-daemon`, `xdg-desktop-portal` with `xdg-desktop-portal-gtk`, Xvfb, openbox, xdotool and ImageMagick. Clicks use fixed positions in a 1280x860 window, as in `smoke_deb.sh`.
