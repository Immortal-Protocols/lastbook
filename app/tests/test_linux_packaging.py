"""Linux packaging contracts using synthetic local fixtures, never release data.

Runs the real stager/scanner and dpkg-deb on a tiny fixture payload. The ELF
fixture is not lastbooksrc; these checks do not prove a working app or package.
"""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import venv
import zipfile

ROOT = Path(__file__).resolve().parents[2]
LINUX = ROOT / 'packaging/linux'


def write(root, rel, data=''):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data, encoding='utf-8')
    return path


@unittest.skipUnless(all(shutil.which(c) for c in ('gcc', 'readelf', 'nm')), 'needs GCC and binutils for local fixtures')
class LinuxPackaging(unittest.TestCase):
    def setUp(self):
        scratch = ROOT / 'derived/packaging-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / 'payload'
        # Independent minimum payload for scan tests; not a runnable app.
        for rel in ('lastbook.py', 'app/main.py', 'app/shell_linux.py', 'engine/setup/roots.pem',
                    'web/index.html', 'setup/manifest-v1.json', 'VERSION'):
            write(self.root, 'opt/lastbook/' + rel)
        write(self.root, 'usr/bin/lastbook', '#!/bin/sh\n')
        write(self.root, 'usr/share/applications/lastbook.desktop', '[Desktop Entry]\n')
        write(self.root, 'usr/share/icons/hicolor/256x256/apps/lastbook.png', 'synthetic icon fixture')
        c = write(self.base, 'fixture.c', 'int local_fixture(void) { return 7; }\n')
        self.plugin = self.root / 'opt/lastbook/gst/libgstlastbooksrc.so'
        self.plugin.parent.mkdir(parents=True)
        subprocess.run(['gcc', '-shared', '-fPIC', '-s', str(c), '-o', str(self.plugin)], check=True)

    def scan(self, path, *args):
        return subprocess.run([sys.executable, '-I', '-B', str(LINUX / 'scan_package_linux.py'), str(path), *args],
                              capture_output=True, text=True)

    def both_formats(self, expected, message):
        for fmt in ('directory', '.deb'):
            with self.subTest(format=fmt):
                path = self.root
                if fmt == '.deb':
                    if not shutil.which('dpkg-deb'):
                        self.skipTest('dpkg-deb unavailable; directory checks still run')
                    control = write(self.root, 'DEBIAN/control',
                                    'Package: lastbook\nVersion: 0.0.1\nArchitecture: amd64\nMaintainer: Example <example@example.org>\nDescription: synthetic scan fixture\n')
                    path = self.base / 'fixture.deb'
                    subprocess.run(['dpkg-deb', '--root-owner-group', '--build', str(self.root), str(path)], check=True, capture_output=True)
                    control.unlink()
                    control.parent.rmdir()
                result = self.scan(path)
                self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
                self.assertIn(message, result.stdout)

    def test_clean_stage_and_deb_share_rules(self):
        self.both_formats(0, 'SCAN PASSED')

    def test_unexpected_artifacts_are_rejected_in_both_formats(self):
        cases = (
            ('opt/lastbook/app/test_leak.py', '', 'file not allowed'),
            ('opt/lastbook/app/leak.py', 'import socket\n', 'network module'),
            ('opt/lastbook/web/leak.txt', 'placeholdertown', 'household or working name'),
            ('opt/lastbook/web/home-area.json', '{}', 'file not allowed'),
            ('usr/bin/lastbook-extra', '', 'file outside'),
        )
        for rel, data, message in cases:
            with self.subTest(artifact=rel):
                path = write(self.root, rel, data)
                self.both_formats(1, message)
                path.unlink()

    def test_symlink_escape_and_dangling_required_asset(self):
        path = self.root / 'opt/lastbook/web/index.html'
        path.unlink()
        # Target is a synthetic local fixture, never a user's file.
        outside = write(self.base, 'outside.html', 'private fixture must not be read')
        for target in (str(outside), 'missing.html'):
            with self.subTest(target=target):
                path.symlink_to(target)
                self.both_formats(1, 'symlink')
                path.unlink()

    def test_missing_required_assets(self):
        for rel in ('engine/setup/roots.pem', 'gst/libgstlastbooksrc.so', 'setup/manifest-v1.json'):
            with self.subTest(asset=rel):
                path = self.root / 'opt/lastbook' / rel
                data = path.read_bytes()
                path.unlink()
                self.both_formats(1, 'missing from the package')
                path.write_bytes(data)

    def staging_inputs(self):
        source, ship, vendor = (self.base / name for name in ('source', 'ship', 'vendor'))
        for rel in ('app/main.py', 'app/bridge.py', 'app/shell_linux.py', 'server.py', 'retrieval.py', 'assistant.py', 'llm_local.py',
                    'engine/__init__.py', 'engine/paths.py', 'engine/library.py', 'engine/saved_pages.py',
                    'engine/address_search.py', 'engine/update.py', 'engine/setup/__init__.py', 'engine/setup/api.py',
                    'engine/setup/download.py', 'engine/setup/hardware.py', 'engine/setup/install.py', 'engine/setup/manifest.py'):
            write(source, rel, '# Synthetic staging fixture\n')
        write(source, 'engine/setup/roots.pem', 'synthetic certificate fixture')
        for rel in ('packaging/linux/lastbook.py', 'packaging/linux/lastbook.desktop', 'packaging/icon/tile-1024.png'):
            dest = source / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / rel, dest)
        write(ship, 'web/index.html', '<p>Synthetic staging fixture</p>')
        write(ship, 'content/gaps.json', '{}')
        write(ship, 'setup/manifest-v1.json', json.dumps({'version': 1, 'packs': []}))
        write(vendor, 'example/__init__.py', '# Synthetic wheel payload\n')
        write(vendor, 'example/tests/test_unused.py', '# removed like Debian wheel tests\n')
        return source, ship, vendor

    def stage(self, source, ship, vendor, llm=None, dest=None, **kw):
        spec = importlib.util.spec_from_file_location('stage_linux', LINUX / 'stage_linux.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.stage(source, ship, vendor, self.plugin, dest or self.base / 'staged', '0.0.1', llm, **kw)

    def test_stager_records_package_channel(self):
        inputs = self.staging_inputs()
        self.stage(*inputs)
        self.assertEqual((self.base / 'staged/opt/lastbook/CHANNEL').read_text(), 'deb\n')
        self.stage(*inputs, dest=self.base / 'arch', channel='arch')
        self.assertEqual((self.base / 'arch/opt/lastbook/CHANNEL').read_text(), 'arch\n')
        with self.assertRaisesRegex(ValueError, 'channel'):
            self.stage(*inputs, dest=self.base / 'bad', channel='flatpak')
        self.assertFalse((self.base / 'bad').exists())

    def test_stager_layout_and_clean_destination(self):
        inputs = self.staging_inputs()
        self.stage(*inputs)
        stage = self.base / 'staged'
        self.assertEqual((stage / 'opt/lastbook/VERSION').read_text(), '0.0.1\n')
        self.assertIn('/usr/bin/python3 -I -B /opt/lastbook/lastbook.py', (stage / 'usr/bin/lastbook').read_text())
        self.assertTrue(os.access(stage / 'usr/bin/lastbook', os.X_OK))
        self.assertFalse((stage / 'opt/lastbook/lib/example/tests').exists())
        self.assertTrue((stage / 'usr/share/icons/hicolor/128x128/apps/lastbook.png').is_file())
        scanned = self.scan(stage)
        self.assertEqual(scanned.returncode, 0, scanned.stdout + scanned.stderr)
        sentinel = write(stage, 'keep.txt', 'do not delete')
        with self.assertRaisesRegex(ValueError, 'empty'):
            self.stage(*inputs)
        self.assertEqual(sentinel.read_text(), 'do not delete')

    def test_stager_refuses_missing_asset_and_source_symlink(self):
        inputs = self.staging_inputs()
        for rel in ('app/main.py', 'engine/setup/roots.pem', 'packaging/icon/tile-1024.png'):
            with self.subTest(asset=rel):
                path = inputs[0] / rel
                data = path.read_bytes()
                path.unlink()
                with self.assertRaisesRegex(ValueError, rel):
                    self.stage(*inputs)
                path.write_bytes(data)
        path = inputs[0] / 'app/main.py'
        path.unlink()
        outside = write(self.base, 'outside.py', '# synthetic fixture\n')
        path.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            self.stage(*inputs)

    def test_debian_stage_can_live_under_checkout_without_copying_build_artifacts(self):
        inputs = self.staging_inputs()
        dest = inputs[0] / 'derived/build/root'
        write(inputs[0], 'derived/unrelated-cache.txt', 'must not ship')
        self.stage(*inputs, dest=dest)
        self.assertTrue((dest / 'opt/lastbook/app/main.py').is_file())
        self.assertFalse((dest / 'opt/lastbook/derived').exists())
        result = self.scan(dest)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_optional_runner_keeps_internal_library_aliases_but_rejects_escapes(self):
        inputs = self.staging_inputs()
        llm = self.base / 'llm'
        runner = write(llm, 'lastbook-llm', '#!/bin/sh\nexit 0\n')
        runner.chmod(0o755)
        write(llm, 'libexample.so.1', 'synthetic library fixture')
        alias = llm / 'libexample.so'
        alias.symlink_to('libexample.so.1')
        self.stage(*inputs, llm=llm)
        shipped = self.base / 'staged/opt/lastbook/llm'
        self.assertFalse((shipped / 'libexample.so').is_symlink())
        self.assertEqual((shipped / 'libexample.so').read_bytes(), (shipped / 'libexample.so.1').read_bytes())
        self.assertTrue(os.access(shipped / 'lastbook-llm', os.X_OK))
        shutil.rmtree(self.base / 'staged')
        alias.unlink()
        alias.symlink_to(write(self.base, 'outside.so', 'synthetic external fixture'))
        with self.assertRaisesRegex(ValueError, 'symlink'):
            self.stage(*inputs, llm=llm)

    def test_arch_wheel_lock_pins_transitive_wheels_and_rejects_non_wheels(self):
        spec = importlib.util.spec_from_file_location('build_arch', LINUX / 'arch/build_arch.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        wheels = self.base / 'wheels'
        wheels.mkdir()
        for name in ('example', 'dependency'):
            wheel = wheels / f'{name}-1.0-py3-none-any.whl'
            with zipfile.ZipFile(wheel, 'w') as z:
                dependency = 'Requires-Dist: dependency==1.0\n' if name == 'example' else ''
                z.writestr(f'{name}-1.0.dist-info/METADATA', f'Metadata-Version: 2.1\nName: {name}\nVersion: 1.0\n{dependency}')
                z.writestr(f'{name}-1.0.dist-info/WHEEL', 'Wheel-Version: 1.0\nGenerator: synthetic-fixture\nRoot-Is-Purelib: true\nTag: py3-none-any\n')
                z.writestr(f'{name}-1.0.dist-info/RECORD', '')
                z.writestr(f'{name}/__init__.py', '# Synthetic offline wheel fixture\n')
        lock = module.wheel_lock(wheels)
        self.assertEqual(len(lock.splitlines()), 2)
        for name in ('example', 'dependency'):
            import hashlib
            digest = hashlib.sha256((wheels / f'{name}-1.0-py3-none-any.whl').read_bytes()).hexdigest()
            self.assertIn(f'{name}==1.0 --hash=sha256:{digest}', lock)
        # Prove pip accepts this lock and installs the transitive fixture fully
        # offline into a private target; no real dependency or system install.
        tools = self.base / 'tools'
        venv.EnvBuilder(with_pip=True).create(tools)
        lockfile = write(self.base, 'wheels.lock', lock)
        command = [str(tools / 'bin/python'), '-I', '-B', '-m', 'pip', '--isolated', '--disable-pip-version-check',
                   'install', '--no-cache-dir', '--no-compile', '--no-index', '--require-hashes',
                   '--find-links', str(wheels), '-r', str(lockfile)]
        result = subprocess.run([*command, '--target', str(self.base / 'installed')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.base / 'installed/dependency/__init__.py').is_file())
        with (wheels / 'example-1.0-py3-none-any.whl').open('ab') as f:
            f.write(b'changed fixture')
        result = subprocess.run([*command, '--target', str(self.base / 'tampered')], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('HASHES', result.stdout + result.stderr)
        write(wheels, 'unexpected.tar.gz', 'not a wheel')
        with self.assertRaisesRegex(ValueError, 'wheel'):
            module.wheel_lock(wheels)


if __name__ == '__main__':
    unittest.main()
