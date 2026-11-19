# Native Arch / Omarchy build

This builds an unsigned native `lastbook-<version>-1-x86_64.pkg.tar.zst` from a
local checkout. It is not an AUR submission or a conversion of the Ubuntu
package. Installation and desktop testing on Arch / Omarchy are still required
before distributing a build.

## Install or update a release

From this checkout, as your ordinary desktop user, with the publisher's signing
key already imported into your keyring from a channel you trust:

```bash
/usr/bin/python3 -I -B packaging/linux/arch/install.py --signing-key FULL_FINGERPRINT
```

By default this reads releases from `Immortal-Protocols/lastbook`, the same
repository the workflow below publishes to, and selects the newest non-draft
release that carries an Arch package. It uses `gh`, so run `gh auth login` first
if needed, and requires `github-cli`, `libarchive`, `gnupg`, `pacman` and `sudo`
(on Omarchy: `omarchy pkg add github-cli libarchive`).

It downloads into a temporary directory and checks, in this order, before any
elevation: the package checksum; the detached signature, which must exist and
be a valid, unexpired signature by the fingerprint you gave (or one of its
subkeys); the package name and architecture; and the Python ABI bounds against
your system Python. Only then does it run `sudo pacman -U` with the normal
confirmation prompt, and pacman resolves the declared desktop and media
dependencies. It never imports a key shipped with a release, runs downloaded
scripts or changes desktop configuration. Use `--release TAG` for a known build
and `--check-only` to verify without installing. Configure pacman's own keyring
separately if you also want pacman to check package signatures.

### Community test builds

Builds published anywhere else are never picked up implicitly. Name the
repository, and the installer labels the result as a community test build
before downloading:

```bash
/usr/bin/python3 -I -B packaging/linux/arch/install.py \
  --community-repo OWNER/NAME --signing-key FULL_FINGERPRINT
```

If that community build has no signature, `--allow-unsigned` replaces
`--signing-key`. Then only the checksum published in the same release is
checked, which detects corruption but says nothing about who built the package.
`--allow-unsigned` is refused for upstream releases.

## Automated builds and draft releases

`.github/workflows/arch.yml` tests and builds in a fresh Arch container on pull
requests, weekly, and through **Actions → Native Arch package → Run workflow**.
Weekly builds expose rolling Python/wheel compatibility problems. The build
runs as an unprivileged user, retains the downloaded publisher manifest and
its hash, and keeps the existing mandatory TLS and package scans. Artifacts
contain the package, checksum, manifest, wheel lock, source commit and Python version.
They do not include a library or model. A failed gate prevents release output.
The disposable container also installs the built package, checks its launcher,
imports bundled native dependencies, confirms the Arch update path stays
offline, and removes the package. Desktop/media checks still require Omarchy.

By default, the workflow only uploads a build artifact. To enable signed draft
prereleases, configure the GitHub environment `arch-release`:

- Secret `ARCH_SIGNING_KEY_BASE64`: base64-encoded exported GPG private signing key.
- Secret `ARCH_SIGNING_PASSPHRASE`: its passphrase.
- Variable `ARCH_SIGNING_FINGERPRINT`: full 40-character signing-key fingerprint.

Use a dedicated release key and publish its public key/fingerprint through a
trusted channel. Restrict the environment to trusted release branches and add
required reviewers where supported. With `draft_release` selected on a manual
run, the separate release job signs the package and creates a **draft**
prerelease. Review and publish it manually after real desktop testing. No
release is created on pull requests or the weekly schedule; signing secrets
are only used by the release job. Missing signing configuration fails that job.
The workflow must first be merged/pushed to GitHub before it can run; a local
checkout edit does not register or execute it.

The container follows current Arch packages; each build records the Python
version and resolves a hashed wheel lock. This is compatibility monitoring,
not a claim of bit-for-bit reproducible builds. Before an Arch Python minor
transition, build and distribute the matching replacement package; the existing
ABI bounds intentionally remain in place.

## Build locally

Use an up-to-date Arch x86_64 environment, as an ordinary user, with `base-devel`,
`git`, `python`, `python-pip`, `python-pillow`, `pkgconf`, `python-gobject`, `gtk3`,
`webkit2gtk-4.1`, `libsoup3`, `gstreamer`, `gst-plugins-base`, `gst-plugins-good`,
`gst-libav`, `gst-plugins-bad-libs`, `gst-plugin-dav1d`, `gcc-libs`, and `zstd`
already installed. The wrapper checks
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
  --manifest derived/arch-inputs/manifest-v1.json
```

The version defaults to the release in `packaging/linux/build_app_linux.sh`, so the
Arch package and the `.deb` from one checkout match; `--version` overrides it.
`TMPDIR` matters: some editors, agents and IDE terminals point it inside your home
directory, which the build refuses (see below). To include the local AI runner,
build it first with `packaging/llm/build_llm_linux.sh` and add `--llm DIR`.

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
into system Python. Debian keeps its Ubuntu 24.04 / 26.04 release and Python guards and
optional local runner behavior.

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
added. Packages built by the workflow omit the local AI runner (local builds
include it with `--llm`); without it Chat search and reading remain available,
setup never offers the model download, and no remote AI is enabled. **Check for
updates** on an Arch package says to update it the way it was installed and
makes no network request.

For local packaging regression checks (Pillow, GCC and binutils required;
`dpkg-deb` additionally exercises the same fixtures as Debian archives):

```bash
python3 -B -m unittest app.tests.test_linux_packaging app.tests.test_setup.Hardware
```

These use synthetic assets and a small ELF fixture, not release data. They do not
prove installation, a Wayland window, video playback, offline behavior, or
uninstallation; exercise those on the built package in an isolated Arch desktop.
