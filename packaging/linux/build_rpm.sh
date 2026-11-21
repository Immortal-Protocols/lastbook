#!/bin/bash
# Builds an RPM from the staging tree that packaging/linux/build_app_linux.sh wrote.
#
#   bash packaging/linux/build_rpm.sh <stage> <version> <amd64|arm64> <output-folder>
#
# <stage> is the folder holding opt/, usr/ and DEBIAN/ (the .deb's root). The RPM installs the same paths as the .deb:
# /opt/lastbook, /usr/bin/lastbook, the desktop entry, icons and copyright. Run on a machine with rpmbuild:
#   apt-get install -y rpm        (Ubuntu 24.04)
set -euo pipefail
STAGE="${1:?stage folder}"
VERSION="${2:?version}"
ARCH="${3:?amd64 or arm64}"
OUT="${4:?output folder}"
STAGE="$(realpath "$STAGE")"
OUT="$(realpath -m "$OUT")"
case "$ARCH" in
  amd64|x86_64) RPM_ARCH=x86_64 ;;
  arm64|aarch64) RPM_ARCH=aarch64 ;;
  *) echo "unsupported architecture: $ARCH" >&2; exit 1 ;;
esac
command -v rpmbuild >/dev/null || { echo "rpmbuild is missing: apt-get install -y rpm" >&2; exit 1; }
[ -d "$STAGE/opt/lastbook" ] || { echo "not a Lastbook staging tree: $STAGE" >&2; exit 1; }

# RPM versions cannot contain a hyphen; a pre-release (1.2.3-rc1) becomes 1.2.3~rc1, which RPM sorts before 1.2.3.
RPM_VERSION="${VERSION//-/\~}"
WORK="$OUT/rpmbuild"
rm -rf "$WORK"
mkdir -p "$WORK/SPECS" "$WORK/BUILD" "$WORK/RPMS" "$WORK/SRPMS" "$WORK/BUILDROOT" "$WORK/tmp"
SPEC="$WORK/SPECS/lastbook.spec"

cat > "$SPEC" <<SPEC
Name:           lastbook
Version:        $RPM_VERSION
Release:        1%{?dist}
Summary:        Offline survival library
License:        MIT
URL:            https://lastbook.org
BuildArch:      $RPM_ARCH
AutoReqProv:    no
# The bundled wheels in /opt/lastbook/lib are built for Ubuntu 24.04's python3 3.12. A newer system python cannot load them.
Requires:       python3 >= 3.12
Requires:       python3 < 3.13
Requires:       python3-gobject
Requires:       gtk3
Requires:       webkit2gtk4.1
Requires:       gstreamer1
Requires:       gstreamer1-plugins-base
Requires:       gstreamer1-plugins-good
Requires:       gstreamer1-libav
Requires:       libgomp
Recommends:     vulkan-loader

%description
Lastbook searches and reads a survival library kept on this computer: guides,
manuals, videos, maps and an encyclopedia, with no internet. It opens no network
port. Setup downloads the library the first time; nothing else goes online unless
you ask it to check for a newer version. The person's library and settings stay
in their home folder and are never removed with the package.

%prep

%build

%install
mkdir -p %{buildroot}
cp -a "$STAGE"/. %{buildroot}/
rm -rf %{buildroot}/DEBIAN

%files
/opt/lastbook
/usr/bin/lastbook
/usr/share/applications/lastbook.desktop
/usr/share/icons/hicolor
/usr/share/doc/lastbook

%changelog
* $(date -u '+%a %b %d %Y') Lastbook <noreply@lastbook.org> - $RPM_VERSION-1
- Build from the Lastbook release tree.
SPEC

rpmbuild --define "_topdir $WORK" --define "_tmppath $WORK/tmp" --define "debug_package %{nil}" -bb "$SPEC" >"$OUT/rpm.log" 2>&1 \
  || { tail -50 "$OUT/rpm.log" >&2; exit 1; }
RPM="$(find "$WORK/RPMS" -type f -name '*.rpm' | head -1)"
[ -n "$RPM" ] || { echo "rpmbuild produced no RPM" >&2; exit 1; }
RPM_OUT="$OUT/Lastbook-${VERSION}-1.${RPM_ARCH}.rpm"
cp "$RPM" "$RPM_OUT"
sha256sum "$RPM_OUT" | tee "$RPM_OUT.sha256"
echo "Built: $RPM_OUT"
