"""Static and source-level checks for the Windows installer localization fallback."""
import ast
import ctypes
import json
import os
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def _installer_source():
    return (ROOT / 'packaging' / 'lastbook_setup.py').read_text(encoding='utf-8')


def _locale_namespace(ctypes_module=ctypes):
    tree = ast.parse(_installer_source())
    definitions = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == 'installer_locale':
            definitions.append(node)
        elif isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == 'SUPPORTED_INSTALLER_LOCALES'
                for target in node.targets):
            definitions.append(node)
    module = ast.Module(body=definitions, type_ignores=[])
    namespace = {'ctypes': ctypes_module, 'json': json, 'os': os, 'Path': Path}
    exec(compile(module, '<installer_locale>', 'exec'), namespace)
    return namespace


class InstallerSource(unittest.TestCase):
    def test_supported_installer_locales_match_the_bundled_catalogue(self):
        namespace = _locale_namespace()
        catalogs = json.loads((ROOT / 'packaging' / 'i18n_installer.json').read_text(encoding='utf-8'))
        self.assertEqual(namespace['SUPPORTED_INSTALLER_LOCALES'], frozenset({'en', *catalogs['locales']}))

    def test_installer_translation_helper_is_defined_when_used(self):
        tree = ast.parse(_installer_source())
        definitions = {node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
        imports = {alias.asname or alias.name.split('.')[0] for node in tree.body
                   if isinstance(node, (ast.Import, ast.ImportFrom)) for alias in node.names}
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == 'installer_t']
        if calls:
            self.assertIn('installer_t', definitions | imports,
                          'installer_t is called but is neither defined nor imported')

    def _locale(self, preference, langid):
        namespace = _locale_namespace()
        if 'installer_locale' not in namespace:
            self.skipTest('installer locale selection is added with installer localization')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            appdata = root / 'roaming'
            preference_path = appdata / 'Lastbook' / 'ui-language.json'
            preference_path.parent.mkdir(parents=True)
            preference_path.write_text(json.dumps({'language': preference}), encoding='utf-8')
            fake_ctypes = types.SimpleNamespace(windll=types.SimpleNamespace(
                kernel32=types.SimpleNamespace(GetUserDefaultUILanguage=lambda: langid)))
            namespace = _locale_namespace(fake_ctypes)
            with patch.dict(os.environ, {'APPDATA': str(appdata)}, clear=False), \
                    patch.object(Path, 'home', return_value=root / 'home'):
                return namespace['installer_locale']()

    def test_malformed_saved_language_falls_back_safely(self):
        self.assertEqual(self._locale(['fr'], 0x0409), 'en')
        self.assertEqual(self._locale({'bad': 'shape'}, 0x0409), 'en')

    def test_windows_ui_language_selects_supported_catalog(self):
        self.assertEqual(self._locale('fr', 0x0407), 'de')
        self.assertEqual(self._locale('fr', 0x0804), 'zh-Hans')
        self.assertEqual(self._locale('fr', 0x0409), 'en')

    def test_supported_saved_language_precedes_windows_ui(self):
        for locale in ('en', 'es-419', 'de', 'zh-Hans'):
            with self.subTest(locale=locale):
                self.assertEqual(self._locale(locale, 0x0409), locale)
