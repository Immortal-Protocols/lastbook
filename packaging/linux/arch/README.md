# Native Arch / Omarchy build

This builds an unsigned native `lastbook-<version>-1-x86_64.pkg.tar.zst` from a
local checkout. It is not an AUR submission or a conversion of the Ubuntu
package. Installation and desktop testing on Arch / Omarchy are still required
before distributing a build.

Use an up-to-date Arch x86_64 environment, as an ordinary user, with `base-devel`,
`git`, `python`, `python-pip`, `python-pillow`, `pkgconf`, `python-gobject`, `gtk3`,
`webkit2gtk-4.1`, `libsoup3`, `gstreamer`, `gst-plugins-base`, `gst-plugins-good`,
`gst-libav`, `gcc-libs`, and `zstd` already installed. The wrapper checks
prerequisites; it never installs dependencies or changes system configuration.
The icon input is `packaging/icon/tile-1024.png`.

Supply an explicit public **setup manifest**, validated against the checkout's
setup schema and download-host allowlist. The checkout does not contain
`derived/release/manifest-v1.json`. One way to obtain the public manifest is:

```bash
mkdir -p derived/arch-inputs
curl --fail --show-error --silent --proto '=https' --tlsv1.2 \
  --cacert engine/setup/roots.pem \
  https://downloads.lastbook.org/manifest-v1.json \
  --output derived/arch-inputs/manifest-v1.json
sha256sum derived/arch-inputs/manifest-v1.json
```

Review and retain that manifest and its hash with the build. An empty manifest,
a fixture, or invented release hashes are not substitutes for release data.
The wrapper preserves the supplied bytes; it does not synthesize pack or model
entries or require unpublished release tooling.

From the checkout root:

```bash
TMPDIR=/tmp /usr/bin/python3 -I -B packaging/linux/arch/build_arch.py \
  --manifest derived/arch-inputs/manifest-v1.json --version 1.1.9
```

The command prints its unique scratch directory and, on success, the package
path and SHA-256. It keeps the selected sources, manifest, `wheels.lock`, generated
`PKGBUILD`, source archive, payload and logs for review. A failed preparation or
scan stops the build; inspect `logs/tls.txt`, `logs/wheels.txt`, `logs/makepkg.txt`
and `logs/scan.txt` as applicable. No TLS or package-scan bypass is provided.
Use a neutral scratch path: makepkg's standard `.BUILDINFO` records build paths
and installed package versions. Home-directory paths are refused. Build in a
clean Arch environment and inspect native package metadata before sharing it.

Preparation copies the explicit runtime files and tracked public web/content
assets from their current working-tree contents. Untracked UI assets, Git
history, tests, caches, data folders and private home-area files are not copied.
Source symlinks and missing inputs fail closed. The existing ship sanitizer and
TLS roots gate run before wheel resolution. PyPI supplies binary wheels for the
running system Python using the existing pinned Linux requirements; all resolved
transitive wheels are also pinned by version and SHA-256 in `wheels.lock`.

makepkg then uses only a checksummed local source archive. Its build/package
functions make no network requests: pip uses `--no-index --require-hashes` and a
private target directory, and GCC builds `lastbooksrc` from the existing C source.
The shared Linux stager installs the frozen launcher, program files, wheels,
desktop entry and icons. The shared scanner checks both the staged tree and the
payload extracted from the final native archive. Neither phase installs anything
into system Python. Debian keeps its Ubuntu 24.04 / Python 3.12 guards and optional
local runner behavior.

The package depends on the Python minor ABI used to resolve its wheels (for
example, `python>=3.14` and `python<3.15`). Rebuild from the checkout after an Arch
Python minor update; do not force an incompatible package through pacman. If a
pinned dependency has no matching wheel, preparation stops rather than changing
the pins or compiling an unreviewed replacement. If the ABI dependency blocks a
full Arch upgrade, remove the app package, upgrade Arch, then rebuild and reinstall.
The library and settings are outside the package and remain in place.

After reviewing the archive, install it with `pacman -U` and launch `lastbook`
from the menu or terminal in a desktop session. It uses the existing GTK3 /
WebKitGTK 4.1 shell and `lastbook://` bridge, including the packaged environment
scrub and data-folder code isolation. No HTTP server or new GUI framework is
added. This first Arch workflow omits the local AI runner; Chat search and reading
remain available, but local AI answers do not. No remote AI is enabled. The
existing update UI may still mention Ubuntu and offer its `.deb`; Arch updates
must be rebuilt with this workflow.

For local packaging regression checks (Pillow, GCC and binutils required;
`dpkg-deb` additionally exercises the same fixtures as Debian archives):

```bash
python3 -B -m unittest app.tests.test_linux_packaging app.tests.test_setup.Hardware
```

These use synthetic assets and a small ELF fixture, not release data. They do not
prove installation, a Wayland window, video playback, offline behavior, or
uninstallation; exercise those on the built package in an isolated Arch desktop.
