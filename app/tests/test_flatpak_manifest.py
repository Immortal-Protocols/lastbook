#!/usr/bin/env python3
"""packaging/linux/flatpak/: the manifest's pinned wheels against requirements_linux.txt, the shared build steps it calls, and the
package scan's mapping of a Flatpak's /app onto the .deb's paths.

  python3 -B app/tests/test_flatpak_manifest.py [-v]

The manifest is read as text (no YAML library), and nothing is built. Never packaged."""
import importlib.util, re, shutil, sys, tempfile, unittest
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / 'packaging' / 'linux' / 'flatpak' / 'org.lastbook.Lastbook.yml'
REQUIREMENTS = ROOT / 'packaging' / 'linux' / 'requirements_linux.txt'
ARCHES = ('x86_64', 'aarch64')
PYTHON_TAG = 'cp314'       # GNOME runtime 51's Python is 3.14 (runtime-version in the manifest)
# Wheels the pins need that requirements_linux.txt leaves to pip: beautifulsoup4 needs soupsieve and typing_extensions.
DEPENDENCIES = {'soupsieve', 'typing_extensions'}


def norm(name):
    return re.sub(r'[-_.]+', '_', name).lower()


def pins():
    out = {}
    for line in REQUIREMENTS.read_text(encoding='utf-8').splitlines():
        line = line.split('#')[0].strip()
        if line:
            name, version = line.split('==')
            out[norm(name)] = version.strip()
    return out


def wheels():
    """Each `dest: wheels` source as {'url', 'sha256', 'arches'}; arches is None when it has no only-arches (all of them)."""
    text = MANIFEST.read_text(encoding='utf-8')
    out = []
    for block in re.split(r'\n\s*- type: ', text):
        if not re.search(r'^\s*dest: wheels\s*$', block, re.M):
            continue
        fields = dict(re.findall(r'^\s*([a-z0-9-]+): (.*)$', block, re.M))
        arches = re.findall(r'[a-z0-9_]+', fields['only-arches']) if 'only-arches' in fields else None
        out.append({'url': fields.get('url', ''), 'sha256': fields.get('sha256', ''), 'arches': arches})
    return out


def wheel_name(url):
    """(distribution, version, tags) from a wheel file name."""
    parts = url.rsplit('/', 1)[-1][:-len('.whl')].split('-')
    return norm(parts[0]), parts[1], '-'.join(parts[2:])


class Wheels(unittest.TestCase):
    def test_every_pin_has_a_wheel_at_its_version_for_every_arch(self):
        found = {}
        for w in wheels():
            name, version, _ = wheel_name(w['url'])
            for arch in w['arches'] or ARCHES:
                found.setdefault((name, arch), set()).add(version)
        missing = [(n, v, a) for n, v in pins().items() for a in ARCHES if found.get((n, a)) != {v}]
        self.assertEqual(missing, [], 'pins without exactly one wheel at that version: (name, version, arch)')

    def test_every_wheel_is_a_pin_or_a_named_dependency(self):
        names = {wheel_name(w['url'])[0] for w in wheels()}
        self.assertEqual(sorted(names - set(pins()) - DEPENDENCIES), [])
        self.assertEqual(sorted(DEPENDENCIES - names), [], 'a named dependency is no longer in the manifest')

    def test_compiled_wheels_are_for_the_runtime_python_and_their_arch(self):
        for w in wheels():
            name, _, tags = wheel_name(w['url'])
            if tags.endswith('none-any'):
                self.assertIsNone(w['arches'], f'{name}: a pure-Python wheel needs no only-arches')
                continue
            self.assertTrue(tags.startswith((PYTHON_TAG + '-', 'py3-none-')), f'{name}: {tags}')
            self.assertEqual(len(w['arches'] or ()), 1, f'{name}: a compiled wheel is for one arch')
            self.assertIn(w['arches'][0], tags, f'{name}: {tags} is not for {w["arches"][0]}')

    def test_every_wheel_is_pinned_by_sha256(self):
        self.assertEqual([w['url'] for w in wheels() if not re.fullmatch(r'[0-9a-f]{64}', w['sha256'])], [])
        self.assertTrue(all(w['url'].startswith('https://files.pythonhosted.org/') for w in wheels()))


class BuildSteps(unittest.TestCase):
    def test_the_app_folder_and_lastbooksrc_come_from_the_shared_steps(self):
        text = MANIFEST.read_text(encoding='utf-8')
        self.assertIn('packaging/linux/stage_linux.py', text)
        self.assertIn('packaging/linux/gst/build_lastbooksrc.sh', text)
        self.assertNotIn('lastbooksrc.c', text, 'compile lastbooksrc through build_lastbooksrc.sh, as the .deb does')
        deb = (ROOT / 'packaging' / 'linux' / 'build_app_linux.sh').read_text(encoding='utf-8')
        self.assertIn('stage_linux.py', deb)
        self.assertIn('gst/build_lastbooksrc.sh', deb)


class ScanMapping(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('scan_package_linux', ROOT / 'packaging' / 'linux' / 'scan_package_linux.py')
        self.scan = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.scan)
        self.tmp = Path(tempfile.mkdtemp(prefix='lastbook-flatpak-scan-'))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def mapped(self, *rels):
        files, root = self.tmp / 'files', self.tmp / 'root'
        for rel in rels:
            (files / rel).parent.mkdir(parents=True, exist_ok=True)
            (files / rel).write_text('x', encoding='utf-8')
        self.scan.unpack_flatpak(files, root)
        return sorted(p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file())

    def test_the_app_lands_on_the_debs_paths(self):
        self.assertEqual(self.mapped('lastbook/app/main.py', 'bin/lastbook', 'share/applications/org.lastbook.Lastbook.desktop',
                                     'share/icons/hicolor/512x512/apps/org.lastbook.Lastbook.png'),
                         ['opt/lastbook/app/main.py', 'usr/bin/lastbook', 'usr/share/applications/lastbook.desktop',
                          'usr/share/icons/hicolor/512x512/apps/org.lastbook.Lastbook.png'])

    def test_anything_else_is_outside_every_owned_place(self):
        owned = ('opt/lastbook/', 'usr/bin/lastbook', 'usr/share/applications/lastbook.desktop', 'usr/share/icons/hicolor/',
                 'usr/share/doc/lastbook/') + self.scan.FLATPAK_OWNED
        stray = self.mapped('flatpak/share/metainfo/org.lastbook.Lastbook.metainfo.xml', 'lib/debug/x.debug', 'opt/lastbook/x')
        self.assertEqual([r for r in stray if r.startswith(owned)], [])

    def test_the_flatpaks_own_store_data_is_owned(self):
        files = self.mapped('share/metainfo/org.lastbook.Lastbook.metainfo.xml', 'share/app-info/xmls/org.lastbook.Lastbook.xml.gz',
                            'manifest.json')
        self.assertTrue(all(r.startswith(self.scan.FLATPAK_OWNED) for r in files), files)


if __name__ == '__main__':
    unittest.main()
