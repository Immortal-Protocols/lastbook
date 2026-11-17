"""Installer must reject tampering and incompatible packages before elevation."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('arch_install', ROOT / 'packaging/linux/arch/install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)
spec = importlib.util.spec_from_file_location('arch_build', ROOT / 'packaging/linux/arch/build_arch.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class ArchInstall(unittest.TestCase):
    def exercise_installer(self, tamper=False, signed=False, fingerprint='A' * 40, valid_key='A' * 40):
        name = 'lastbook-1.1.9-1-x86_64.pkg.tar.zst'

        def external(args):
            if args[:3] == ['gh', 'release', 'view']:
                assets = [name, name + '.sha256'] + ([name + '.sig'] if signed else [])
                return json.dumps({'isDraft': False, 'assets': [{'name': n} for n in assets]})
            if args[:3] == ['gh', 'release', 'download']:
                folder = Path(args[args.index('--dir') + 1])
                (folder / name).write_bytes(b'changed' if tamper else b'fixture')
                (folder / (name + '.sha256')).write_text(hashlib.sha256(b'fixture').hexdigest() + '  ' + name + '\n')
                return ''
            if args[0] == 'bsdtar':
                return 'pkgname = lastbook\narch = x86_64\ndepend = python>=3.14\ndepend = python<3.15\n'
            if args[0] == 'gpg':
                return '[GNUPG:] VALIDSIG ' + valid_key + ' 2026-01-01 0 0 4 0 1 10 00 ' + valid_key
            self.fail(f'unexpected command: {args}')

        argv = ['--release', 'test', '--check-only']
        if signed:
            argv += ['--signing-key', fingerprint]
        with patch.object(installer.os, 'geteuid', return_value=1000), \
                patch.object(installer.platform, 'machine', return_value='x86_64'), \
                patch.object(installer.platform, 'freedesktop_os_release', return_value={'ID': 'omarchy', 'ID_LIKE': 'arch'}), \
                patch.object(installer.shutil, 'which', return_value='/usr/bin/tool'), \
                patch.object(installer, 'run', side_effect=external), \
                patch.object(installer.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '', '')) as command:
            try:
                return installer.main(argv)
            finally:
                self.assertFalse(any(c.args[0][0] == 'sudo' for c in command.call_args_list))

    def test_check_only_validates_without_elevation(self):
        self.assertEqual(self.exercise_installer(), 0)

    def test_tampered_download_stops_installer(self):
        with self.assertRaisesRegex(ValueError, 'mismatch'):
            self.exercise_installer(tamper=True)

    def test_signed_release_requires_expected_signer(self):
        self.assertEqual(self.exercise_installer(signed=True), 0)
        with self.assertRaisesRegex(ValueError, 'specified publisher'):
            self.exercise_installer(signed=True, valid_key='B' * 40)

    def test_arch_derivatives_are_recognized_without_accepting_substrings(self):
        for release in ({'ID': 'arch'}, {'ID': 'omarchy', 'ID_LIKE': 'arch'}, {'ID': 'example', 'ID_LIKE': 'other arch'}):
            self.assertTrue(builder.is_arch(release))
        for release in ({'ID': 'debian'}, {'ID': 'example', 'ID_LIKE': 'archipelago'}, {}):
            self.assertFalse(builder.is_arch(release))

    def test_checksum_rejects_modified_package_and_unrelated_filename(self):
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / 'lastbook-1.1.9-1-x86_64.pkg.tar.zst'
            checksum = Path(str(package) + '.sha256')
            package.write_bytes(b'package fixture')
            digest = hashlib.sha256(package.read_bytes()).hexdigest()
            checksum.write_text(f'{digest}  {package.name}\n')
            installer.verify(package, checksum)
            package.write_bytes(b'tampered fixture')
            with self.assertRaisesRegex(ValueError, 'mismatch'):
                installer.verify(package, checksum)
            checksum.write_text(f'{digest}  ../../other-file\n')
            with self.assertRaisesRegex(ValueError, 'record'):
                installer.verify(package, checksum)

    def test_incompatible_python_stops_before_install(self):
        metadata = 'pkgname = lastbook\narch = x86_64\ndepend = python>=3.14\ndepend = python<3.15\n'
        with patch.object(installer, 'run', return_value=metadata), patch.object(installer.subprocess, 'run') as command:
            command.return_value = subprocess.CompletedProcess([], 127, 'python<3.15', '')
            with self.assertRaisesRegex(ValueError, 'needs python'):
                installer.check_package(Path('fixture.pkg.tar.zst'))
            command.assert_called_once_with(['pacman', '-T', 'python>=3.14', 'python<3.15'], capture_output=True, text=True)

    def test_unexpected_package_cannot_reach_pacman(self):
        with patch.object(installer, 'run', return_value='pkgname = other\narch = x86_64\n'), patch.object(installer.subprocess, 'run') as command:
            with self.assertRaisesRegex(ValueError, 'expected Lastbook'):
                installer.check_package(Path('fixture.pkg.tar.zst'))
            command.assert_not_called()


if __name__ == '__main__':
    unittest.main()
