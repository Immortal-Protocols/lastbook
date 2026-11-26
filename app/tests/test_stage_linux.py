#!/usr/bin/env python3
"""packaging/linux/stage_linux.py: the one list of program files the .deb and the Flatpak ship, and the app folder made from it.

  python3 -B app/tests/test_stage_linux.py [-v]

The list is checked against the app's own imports, followed from the launcher (packaging/linux/lastbook.py) and app/main.py through
every first-party module, read with ast and never run. A module the app starts importing fails here until it is listed, instead of
in a package on someone's computer. Staging runs into a temporary folder from small stand-in inputs. Never packaged."""
import ast, importlib.util, shutil, sys, tempfile, unittest
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('stage_linux', ROOT / 'packaging' / 'linux' / 'stage_linux.py')
stage_linux = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage_linux)

# Imported on other systems only, each behind its own check: the Mac and Windows windows, and the Windows onnxruntime guard.
OTHER_SYSTEMS = {'app/shell_macos.py', 'app/shell_windows.py', 'engine/quiet_onnx.py'}


def module_file(name):
    """A module name as lastbook.py's sys.path finds it (app/, then the root), or None when it is not ours."""
    parts = name.split('.')
    for base in (ROOT / 'app', ROOT):
        path = base.joinpath(*parts)
        if path.with_suffix('.py').is_file():
            return path.with_suffix('.py')
        if (path / '__init__.py').is_file():
            return path / '__init__.py'
    return None


def imported_names(path):
    """Every module name a file imports, at any depth: top level, inside functions, behind checks."""
    package = path.relative_to(ROOT).parent.parts
    for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
        if isinstance(node, ast.Import):
            yield from (a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = '.'.join(package[:len(package) - node.level + 1])
                module = f'{base}.{node.module}' if node.module else base
            else:
                module = node.module
            yield module
            yield from (f'{module}.{a.name}' for a in node.names)   # "from engine import notes" names a module too


def app_imports():
    """The first-party files the app can import on Linux, as paths relative to the checkout."""
    start = [ROOT / stage_linux.LAUNCHER, ROOT / 'app' / 'main.py']
    seen, todo = set(), list(start)
    while todo:
        path = todo.pop()
        if path in seen:
            continue
        seen.add(path)
        for name in imported_names(path):
            parts = name.split('.')
            for found in (module_file('.'.join(parts[:i])) for i in range(1, len(parts) + 1)):   # a package's __init__ too
                if found and str(found.relative_to(ROOT)) not in OTHER_SYSTEMS and found not in seen:
                    todo.append(found)
    return {str(p.relative_to(ROOT)) for p in seen} - {stage_linux.LAUNCHER}


class ProgramFiles(unittest.TestCase):
    def test_every_module_the_app_imports_is_listed(self):
        listed = {r for r in stage_linux.PROGRAM_FILES if r.endswith('.py')}
        self.assertEqual(sorted(app_imports() - listed), [], 'imported by the app but not in stage_linux.PROGRAM_FILES')

    def test_nothing_listed_that_the_app_never_imports(self):
        listed = {r for r in stage_linux.PROGRAM_FILES if r.endswith('.py')}
        self.assertEqual(sorted(listed - app_imports()), [], 'in stage_linux.PROGRAM_FILES but never imported on Linux')

    def test_listed_files_exist(self):
        self.assertEqual([r for r in (*stage_linux.PROGRAM_FILES, stage_linux.LAUNCHER) if not (ROOT / r).is_file()], [])

    def test_a_module_left_off_the_list_is_caught(self):
        listed = set(stage_linux.PROGRAM_FILES) - {'app/ui_language.py'}
        self.assertIn('app/ui_language.py', app_imports() - listed)

    def test_default_version_is_the_deb_build_version(self):
        text = (ROOT / 'packaging' / 'linux' / 'build_app_linux.sh').read_text(encoding='utf-8')
        self.assertIn(f'APP_VERSION="${{LASTBOOK_VERSION:-{stage_linux.default_version()}}}"', text)


class Stage(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='lastbook-stage-'))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.ship, self.vendor = self.tmp / 'ship', self.tmp / 'vendor'
        for rel in ('web/index.html', 'web/app.js', 'content/gaps.json', 'setup/manifest-v1.json'):
            self.write(self.ship / rel)
        for rel in ('numpy/__init__.py', 'numpy/_core/tests/test_a.py', 'numpy/f2py/x.py', 'numpy/testing/x.py', 'numpy/core_tests.py',
                    'bin/f2py', 'pypdfium2_cli/x.py', 'bs4/__init__.py', 'bs4/__pycache__/x.pyc', 'libzim.so'):
            self.write(self.vendor / rel)
        self.plugin = self.write(self.tmp / 'libgstlastbooksrc.so')
        self.opt = self.tmp / 'opt' / 'lastbook'

    def write(self, path, text='x'):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        return path

    def files(self):
        return sorted(str(p.relative_to(self.opt)) for p in self.opt.rglob('*') if p.is_file())

    def test_the_app_folder(self):
        stage_linux.stage(ROOT, self.ship, self.vendor, self.plugin, self.opt, '9.9.9')
        files = self.files()
        for rel in stage_linux.PROGRAM_FILES:
            self.assertIn(rel, files)
        for rel in ('lastbook.py', 'VERSION', 'gst/libgstlastbooksrc.so', 'setup/manifest-v1.json', 'web/index.html', 'web/app.js',
                    'content/gaps.json', 'lib/numpy/__init__.py', 'lib/bs4/__init__.py', 'lib/libzim.so'):
            self.assertIn(rel, files)
        self.assertEqual((self.opt / 'VERSION').read_text(encoding='utf-8'), '9.9.9\n')
        self.assertEqual([f for f in files if f.startswith('lib/') and any(s in f for s in ('tests', 'f2py', 'testing', 'bin/', '_cli', '__pycache__'))], [])
        self.assertFalse((self.opt / 'llm').exists())
        self.assertNotIn('app/shell_macos.py', files)

    def test_the_runner_when_there_is_one(self):
        llm = self.tmp / 'llm'
        runner = self.write(llm / 'lastbook-llm')
        runner.chmod(0o755)
        for name in ('libllama.so', 'libggml-vulkan.so.0', 'LICENSE-llama.cpp.txt', 'build.log'):
            self.write(llm / name)
        stage_linux.stage(ROOT, self.ship, self.vendor, self.plugin, self.opt, '9.9.9', llm)
        self.assertEqual(sorted(p.name for p in (self.opt / 'llm').iterdir()),
                         ['LICENSE-llama.cpp.txt', 'lastbook-llm', 'libggml-vulkan.so.0', 'libllama.so'])
        self.assertTrue((self.opt / 'llm' / 'lastbook-llm').stat().st_mode & 0o111)

    def test_refuses_a_missing_input_before_writing(self):
        (self.ship / 'setup' / 'manifest-v1.json').unlink()
        with self.assertRaises(ValueError):
            stage_linux.stage(ROOT, self.ship, self.vendor, self.plugin, self.opt, '9.9.9')
        self.assertFalse(self.opt.exists())

    def test_refuses_a_folder_that_is_not_empty(self):
        self.write(self.opt / 'old')
        with self.assertRaises(ValueError):
            stage_linux.stage(ROOT, self.ship, self.vendor, self.plugin, self.opt, '9.9.9')

    def test_refuses_a_version_that_is_not_one(self):
        with self.assertRaises(ValueError):
            stage_linux.stage(ROOT, self.ship, self.vendor, self.plugin, self.opt, '1.0; rm -rf /')


if __name__ == '__main__':
    unittest.main()
