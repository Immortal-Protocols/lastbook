#!/usr/bin/env python3
"""Download, verify and install the native test package; never run this as root."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile

REPO = 'jonnyace/lastbook-omarchy'
PACKAGE = re.compile(r'lastbook-[0-9][A-Za-z0-9.+_-]*-x86_64\.pkg\.tar\.zst')


def run(args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout.strip()


def verify(package, checksum):
    # Parse exactly one record, never let a downloaded checksum name other files.
    record = checksum.read_text(encoding='utf-8').strip()
    match = re.fullmatch(r'([0-9a-fA-F]{64}) [ *]' + re.escape(package.name), record)
    if not match:
        raise ValueError('invalid package checksum record')
    with package.open('rb') as stream:
        actual = hashlib.file_digest(stream, 'sha256').hexdigest()
    if actual != match[1].lower():
        raise ValueError('package checksum mismatch; nothing installed')


def check_package(package):
    metadata = run(['bsdtar', '-xOf', str(package), '.PKGINFO'])
    fields = {}
    for line in metadata.splitlines():
        key, sep, value = line.partition(' = ')
        if sep:
            fields.setdefault(key, []).append(value)
    if fields.get('pkgname') != ['lastbook'] or fields.get('arch') != ['x86_64']:
        raise ValueError('release asset is not the expected Lastbook x86_64 package')
    abi = [d for d in fields.get('depend', []) if re.fullmatch(r'python(?:>=|<)[0-9]+\.[0-9]+', d)]
    if len(abi) != 2 or not any(d.startswith('python>=') for d in abi) or not any(d.startswith('python<') for d in abi):
        raise ValueError('package is missing its Python ABI bounds')
    result = subprocess.run(['pacman', '-T', *abi], capture_output=True, text=True)
    if result.returncode:
        raise ValueError('this package needs ' + ', '.join(abi) + '; obtain a build for your system Python')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release', help='specific release tag; default: newest non-draft, including prereleases')
    parser.add_argument('--check-only', action='store_true', help='download and validate without installing')
    parser.add_argument('--signing-key', help='trusted publisher full GPG fingerprint (required for signed releases)')
    args = parser.parse_args(argv)
    if os.geteuid() == 0:
        raise ValueError('run as your ordinary desktop user; only pacman needs elevation')
    release = platform.freedesktop_os_release()
    if platform.machine() != 'x86_64' or not (release.get('ID') == 'arch' or 'arch' in release.get('ID_LIKE', '').split()):
        raise ValueError('requires x86_64 Arch Linux or an Arch derivative such as Omarchy')
    for command in ('gh', 'bsdtar', 'pacman', *([] if args.check_only else ['sudo'])):
        if not shutil.which(command):
            raise ValueError(f'missing {command}; install prerequisites first (see the Arch README)')
    tag = args.release
    if tag is None:
        releases = json.loads(run(['gh', 'api', f'repos/{REPO}/releases?per_page=100']))
        tag = next((r['tag_name'] for r in releases if not r['draft']), None)
        if not tag:
            raise ValueError('no published test release found')
    info = json.loads(run(['gh', 'release', 'view', tag, '--repo', REPO, '--json', 'assets,isDraft']))
    if info['isDraft']:
        raise ValueError('draft releases must be reviewed and published before installation')
    assets = {asset['name'] for asset in info['assets']}
    packages = [name for name in assets if PACKAGE.fullmatch(name)]
    if len(packages) != 1 or packages[0] + '.sha256' not in assets:
        raise ValueError('release must contain exactly one native package and its checksum')
    name = packages[0]
    print(f'Downloading {tag}: {name}', flush=True)
    with tempfile.TemporaryDirectory(prefix='lastbook-install-') as scratch:
        run(['gh', 'release', 'download', tag, '--repo', REPO, '--dir', scratch,
             '--pattern', name, '--pattern', name + '.sha256'])
        package = Path(scratch) / name
        verify(package, Path(scratch) / (name + '.sha256'))
        check_package(package)
        # Signed releases are checked too. Trust must be configured independently;
        # never import a signing key supplied alongside the downloaded package.
        if name + '.sig' in assets:
            if not args.signing_key or not re.fullmatch(r'[A-Fa-f0-9]{40}', args.signing_key):
                raise ValueError('signed release requires --signing-key with the independently trusted publisher fingerprint')
            if not shutil.which('gpg'):
                raise ValueError('signed release needs gpg and the trusted maintainer key')
            run(['gh', 'release', 'download', tag, '--repo', REPO, '--dir', scratch, '--pattern', name + '.sig'])
            status = run(['gpg', '--batch', '--status-fd', '1', '--verify', str(package) + '.sig', str(package)])
            valid = [line.split() for line in status.splitlines() if line.startswith('[GNUPG:] VALIDSIG ')]
            fingerprint = args.signing_key.upper()
            if not any(fingerprint in (fields[2].upper(), fields[-1].upper()) for fields in valid):
                raise ValueError('package was not signed by the specified publisher key')
        else:
            print('This test release has a matching checksum but no publisher signature.', flush=True)
        print('Package checksum and Python compatibility verified.', flush=True)
        if args.check_only:
            return 0
        # Inherit the terminal so sudo and pacman can ask their normal questions.
        subprocess.run(['sudo', 'pacman', '-U', '--', str(package)], check=True)
    print('Installed. Open Lastbook from your application launcher or run lastbook.')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.CalledProcessError, StopIteration) as error:
        sys.exit(f'Lastbook installation stopped: {error}')
