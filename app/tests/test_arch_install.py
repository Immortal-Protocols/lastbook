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


TRUSTED = 'A' * 40


class ArchInstall(unittest.TestCase):
    def exercise_installer(self, argv=('--signing-key', TRUSTED), tamper=False, signed=True, signer=TRUSTED,
                           gpg_status=None, gpg_fails=False, release='test', repos=None, check_only=False, log=None):
        """Run main() with gh, gpg and bsdtar faked; return (result or exception, whether pacman ran)."""
        name = 'lastbook-1.1.9-1-x86_64.pkg.tar.zst'
        repos = [] if repos is None else repos
        log = [] if log is None else log

        def external(args):
            log.append(args)
            if '--repo' in args:
                repos.append(args[args.index('--repo') + 1])
            if args[:2] == ['gh', 'api']:
                repos.append(args[2].split('/releases')[0].removeprefix('repos/'))
                return json.dumps([
                    {'tag_name': 'v9-mac', 'draft': False, 'assets': [{'name': 'Lastbook-9-mac.dmg'}]},
                    {'tag_name': 'arch-draft', 'draft': True, 'assets': [{'name': name}]},
                    {'tag_name': 'arch-1.1.9-1', 'draft': False, 'assets': [{'name': name}]},
                ])
            if args[:3] == ['gh', 'release', 'view']:
                assets = [name, name + '.sha256'] + ([name + '.sig'] if signed else [])
                return json.dumps({'isDraft': False, 'assets': [{'name': n} for n in assets]})
            if args[:3] == ['gh', 'release', 'download']:
                folder = Path(args[args.index('--dir') + 1])
                (folder / name).write_bytes(b'changed' if tamper else b'fixture')
                (folder / (name + '.sha256')).write_text(hashlib.sha256(b'fixture').hexdigest() + '  ' + name + '\n')
                if name + '.sig' in args:
                    (folder / (name + '.sig')).write_bytes(b'signature')
                return ''
            if args[0] == 'bsdtar':
                return 'pkgname = lastbook\narch = x86_64\ndepend = python>=3.14\ndepend = python<3.15\n'
            if args[0] == 'gpg':
                if gpg_fails:
                    raise subprocess.CalledProcessError(1, args)
                return gpg_status or ('[GNUPG:] GOODSIG 0123 Publisher\n'
                                      '[GNUPG:] VALIDSIG ' + signer + ' 2026-01-01 0 0 4 0 1 10 00 ' + signer)
            self.fail(f'unexpected command: {args}')

        args = (['--release', release] if release else []) + (['--check-only'] if check_only else []) + list(argv)
        with patch.object(installer.os, 'geteuid', return_value=1000), \
                patch.object(installer.platform, 'machine', return_value='x86_64'), \
                patch.object(installer.platform, 'freedesktop_os_release', return_value={'ID': 'omarchy', 'ID_LIKE': 'arch'}), \
                patch.object(installer.shutil, 'which', return_value='/usr/bin/tool'), \
                patch.object(installer, 'run', side_effect=external), \
                patch('builtins.print', side_effect=lambda *a, **k: log.append(' '.join(map(str, a)))), \
                patch.object(installer.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '', '')) as command:
            try:
                outcome = installer.main(args)
            except (ValueError, subprocess.CalledProcessError) as error:
                outcome = error
        installed = any(c.args[0][:3] == ['sudo', 'pacman', '-U'] for c in command.call_args_list)
        return outcome, installed

    def assert_refused(self, pattern, **kwargs):
        outcome, installed = self.exercise_installer(**kwargs)
        self.assertIsInstance(outcome, (ValueError, subprocess.CalledProcessError))
        self.assertRegex(str(outcome), pattern)
        self.assertFalse(installed, 'pacman ran although verification failed')

    def test_valid_signature_from_trusted_key_installs(self):
        self.assertEqual(self.exercise_installer(), (0, True))

    def test_signature_by_subkey_of_trusted_primary_key_installs(self):
        status = '[GNUPG:] VALIDSIG ' + 'C' * 40 + ' 2026-01-01 0 0 4 0 1 10 00 ' + TRUSTED
        self.assertEqual(self.exercise_installer(gpg_status=status), (0, True))

    def test_check_only_validates_without_elevation(self):
        self.assertEqual(self.exercise_installer(check_only=True), (0, False))

    def test_missing_signature_is_refused_when_a_key_was_given(self):
        self.assert_refused('no signature', signed=False)

    def test_wrong_signer_is_refused(self):
        self.assert_refused('specified publisher', signer='B' * 40)

    def test_bad_signature_is_refused(self):
        self.assert_refused('gpg', gpg_fails=True)

    def test_expired_or_revoked_key_is_refused(self):
        for word in ('EXPKEYSIG', 'REVKEYSIG'):
            status = f'[GNUPG:] {word} 0123 Publisher\n[GNUPG:] VALIDSIG {TRUSTED} 2026 0 0 4 0 1 10 00 {TRUSTED}'
            self.assert_refused('expired or revoked', gpg_status=status)

    def test_tampered_package_is_refused(self):
        self.assert_refused('mismatch', tamper=True)

    def test_a_trust_choice_is_required(self):
        with patch('sys.stderr'), self.assertRaises(SystemExit):
            installer.main(['--check-only'])
        with self.assertRaisesRegex(ValueError, '40-character'):
            installer.main(['--signing-key', 'ABCD'])

    def test_unsigned_install_is_only_for_named_community_builds(self):
        self.assert_refused('only with --signing-key', argv=['--allow-unsigned'], signed=False)
        community = ['--community-repo', 'tester/lastbook-arch', '--allow-unsigned']
        self.assertEqual(self.exercise_installer(argv=community, signed=False), (0, True))
        self.assert_refused('mismatch', argv=community, signed=False, tamper=True)

    def test_upstream_is_the_default_release_source(self):
        repos = []
        self.assertEqual(self.exercise_installer(release=None, repos=repos)[0], 0)
        self.assertEqual(set(repos), {installer.UPSTREAM})

    def test_newest_release_skips_drafts_and_releases_without_an_arch_package(self):
        log = []
        self.assertEqual(self.exercise_installer(release=None, log=log)[0], 0)
        views = [c for c in log if isinstance(c, list) and c[:3] == ['gh', 'release', 'view']]
        self.assertEqual([c[3] for c in views], ['arch-1.1.9-1'])

    def test_community_build_needs_explicit_repository_and_is_labelled(self):
        repos, log = [], []
        argv = ['--community-repo', 'tester/lastbook-arch', '--signing-key', TRUSTED]
        self.assertEqual(self.exercise_installer(argv=argv, repos=repos, log=log)[0], 0)
        self.assertEqual(set(repos), {'tester/lastbook-arch'})
        self.assertIn('COMMUNITY TEST BUILD', log[0])
        self.assert_refused('OWNER/NAME', argv=['--community-repo', 'https://example.com/x', '--allow-unsigned'])

    def test_arch_build_defaults_to_the_ubuntu_release_number(self):
        script = (ROOT / 'packaging/linux/build_app_linux.sh').read_text(encoding='utf-8')
        self.assertIn('APP_VERSION="${LASTBOOK_VERSION:-' + builder.release_version() + '}"', script)

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
