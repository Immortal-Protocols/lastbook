"""Catalogue schema, deterministic generation and the release staging gate."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'packaging'))
import i18n_catalogs as catalogues  # noqa: E402


class Catalogues(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.work = Path(tmp.name)
        self.english = self.work / 'en.json'
        self.spanish = self.work / 'es-419.json'
        self.english.write_text('{"hi":"Hello, {name}", "files":{"=0":"None", "other":"{count} files"}}', encoding='utf-8')
        self.spanish.write_text('{"hi":"Hola, {name}"}', encoding='utf-8')

    def test_rejects_missing_catalogues(self):
        for file in (self.english, self.spanish):
            with self.subTest(file=file.name):
                contents = file.read_bytes()
                file.unlink()
                with self.assertRaisesRegex(ValueError, f'missing catalogues: {file.stem}'):
                    catalogues.generate(self.work)
                file.write_bytes(contents)

    def test_rejects_duplicate_keys_at_every_depth(self):
        for text in ('{"hi":"A", "hi":"B"}', '{"files":{"other":"A", "other":"B"}}'):
            self.spanish.write_text(text, encoding='utf-8')
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, 'duplicate key'):
                catalogues.generate(self.work)

    def test_rejects_invalid_values_and_placeholders(self):
        for value in [None, False, 2, {}, [], '', ' ', '\ufeff \ufeff', '{name', '{{name}}', '{first-name}', '\ud800', {'other': False},
                      {'other': 'a', '=9007199254740992': 'b'}, {'other': 'a', '=01': 'b'}, {'one': 'one'},
                      {'other': 'Hello, {name}', 'one': 'one'}, {'other': 'a', 'notACategory': 'b'}]:
            self.spanish.write_text(json.dumps({'hi': value}), encoding='utf-8')
            with self.subTest(value=value), self.assertRaises(ValueError):
                catalogues.generate(self.work)
        self.spanish.write_bytes(b'{"hi":"\xff {name}"}')
        with self.assertRaisesRegex(ValueError, 'utf-8'):
            catalogues.generate(self.work)

    def test_rejects_unknown_keys_and_incompatible_contracts(self):
        for value, message in [({'__proto__': 'x'}, 'invalid message key'), ({'unknown': 'x'}, 'unknown message key'),
                               ({'hi': 'Hola, {persona}'}, 'incompatible message'),
                               ({'hi': {'other': 'Hola, {name}'}}, 'incompatible message'),
                               ({'files': '{count} archivos'}, 'incompatible message'),
                               ({'files': {'other': '{count} archivos'}}, 'incompatible message')]:
            self.spanish.write_text(json.dumps(value), encoding='utf-8')
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, message):
                catalogues.generate(self.work)

    def test_allows_missing_messages_and_locale_specific_plural_categories(self):
        self.spanish.write_text('{"files":{"=0":"Ninguno", "many":"{count} archivos", "other":"{count} archivos"}}', encoding='utf-8')
        self.assertIn('Ninguno', catalogues.generate(self.work)['i18n-locales.js'].decode('utf-8'))

    def test_output_is_order_independent_and_writes_literal_data(self):
        value = '¡Está listo! \u2028 <img src=x onerror="bad()"> "); bad(); ({name}'
        messages = {'hi': value, 'files': {'other': '{count} archivos', '=0': 'Ninguno'}}
        self.spanish.write_text(json.dumps(messages, ensure_ascii=False), encoding='utf-8')
        first = catalogues.generate(self.work)
        self.spanish.write_text(json.dumps(dict(reversed(list(messages.items())))), encoding='utf-8')
        self.assertEqual(catalogues.generate(self.work), first)
        js = first['i18n-locales.js'].decode('utf-8')
        self.assertIn('¡Está listo!', js)
        self.assertNotIn('\u2028', js)
        literal = js.split(' = JSON.parse(', 1)[1].removesuffix(');\n')
        self.assertEqual(json.loads(json.loads(literal)), {'es-419': messages})

    def test_source_staging_and_missing_or_stale_assets(self):
        generated = catalogues.generate()
        catalogues.check_assets(ROOT / 'web', generated)
        stage = self.work / 'stage'
        subprocess.run([sys.executable, '-I', '-B', str(ROOT / 'packaging' / 'ship_app_files.py'), str(stage)],
                       check=True, capture_output=True)
        web = stage / 'web'
        catalogues.check_assets(web, generated)
        self.assertFalse((stage / 'translations').exists())
        for name in ('i18n-en.js', 'i18n-locales.js', 'i18n-app.js', 'app.js'):
            with self.subTest(name=name):
                (web / name).unlink()
                with self.assertRaisesRegex(ValueError, 'required localization asset missing'):
                    catalogues.check_assets(web, generated)
                shutil.copyfile(ROOT / 'web' / name, web / name)
        (web / 'setup.html').write_text('<!doctype html><title>Old Setup</title>', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'missing or misordered localization scripts'):
            catalogues.check_assets(web, generated)
        setup = (ROOT / 'web' / 'setup.html').read_text(encoding='utf-8')
        script = next(line for line in setup.splitlines() if 'src="/ui/i18n-app.js' in line)
        for bad in ('<!--' + script + '-->', script.replace('src=', 'data-src='), script.replace('<script ', '<script defer ')):
            with self.subTest(script=bad):
                (web / 'setup.html').write_text(setup.replace(script, bad), encoding='utf-8')
                with self.assertRaisesRegex(ValueError, 'missing or misordered localization scripts'):
                    catalogues.check_assets(web, generated)
        shutil.copyfile(ROOT / 'web' / 'setup.html', web / 'setup.html')
        (web / 'app.js').write_bytes(b'// old controller\n')
        with self.assertRaisesRegex(ValueError, 'packaged web asset differs from source'):
            catalogues.check_assets(web, generated)
        shutil.copyfile(ROOT / 'web' / 'app.js', web / 'app.js')
        (web / 'i18n-locales.js').write_bytes(b'// stale\n')
        with self.assertRaisesRegex(ValueError, 'stale catalogue'):
            catalogues.check_assets(web, generated)


class FallbackWording(unittest.TestCase):
    """language.unavailable is shown in English when the saved language's catalogue cannot load (web/i18n-app.js), whichever
    language that is. The selector offers more than one translated language, so the message must not name one."""

    def test_english_fallback_names_no_language(self):
        en = json.loads((ROOT / 'translations' / 'desktop' / 'en.json').read_text(encoding='utf-8'))
        text = en['language.unavailable']
        self.assertEqual(text, 'The saved language is unavailable. Lastbook is using English.')
        for name in ('Spanish', 'German', 'Chinese', 'español', 'Deutsch', '中文'):
            self.assertNotIn(name, text)


class SimplifiedChineseWording(unittest.TestCase):
    """The zh-Hans catalogue keeps the conventions in docs/i18n.md#simplified-chinese-zh-hans."""

    @classmethod
    def setUpClass(cls):
        load = lambda name: json.loads((ROOT / 'translations' / 'desktop' / name).read_text(encoding='utf-8'))
        cls.en, cls.zh = load('en.json'), load('zh-Hans.json')

    def test_setup_and_settings_are_different_words(self):
        self.assertEqual(self.zh['nav.settings'], '设置')
        self.assertIn('初始设置', self.zh['setup.title'])
        # "初始设置" contains "设置"; the rest of the heading must not say it again.
        self.assertNotIn('设置', self.zh['setup.title'].replace('初始设置', ''))
        # Where a sentence names both screens, it names both.
        self.assertIn('初始设置', self.zh['language.preview'])
        self.assertIn('设置', self.zh['language.preview'])

    def test_simplified_characters_only(self):
        traditional = '設資庫這個們來時間對話選擇頁題導覽視頻標開關閉啟儲載網路線說檔電腦檢區換'
        everything = ' '.join(self.zh.values())
        self.assertEqual([character for character in traditional if character in everything], [])

    def test_everyday_words_and_formatting(self):
        self.assertIn('这台电脑', self.zh['setup.loading'])
        self.assertIn('州或地区', self.zh['setup.chooseIntro'])
        # A space separates Chinese from Latin words, and names stay as they are.
        self.assertIn('Lastbook 会', self.zh['setup.chooseIntro'])
        self.assertEqual(self.zh['setup.settingsTitle'], '资料库与本地 AI')
        # Full-width punctuation, no space before it, no ideographic space.
        everything = ' '.join(self.zh.values())
        for bad in (' ,', ' 。', ' ，', ' ；', ' …', '\u3000', '..'):
            self.assertNotIn(bad, everything)
        self.assertTrue(self.zh['language.saving'].endswith('…'))

    def test_no_message_is_left_in_english(self):
        same = {key for key in self.zh if self.zh[key] == self.en[key]}
        self.assertEqual(same, set())


class GermanWording(unittest.TestCase):
    """The de catalogue keeps the conventions in docs/i18n.md#german-de: formal "Sie" throughout, and fixed words for the screens."""

    @classmethod
    def setUpClass(cls):
        load = lambda name: json.loads((ROOT / 'translations' / 'desktop' / name).read_text(encoding='utf-8'))
        cls.en, cls.de = load('en.json'), load('de.json')

    def test_formal_address_only(self):
        import re
        everything = ' '.join(self.de.values())
        informal = re.findall(r'\b(du|dich|dir|dein\w*|euch|euer\w*|ihr)\b', everything, flags=re.IGNORECASE)
        self.assertEqual(informal, [])
        self.assertIn('Wählen Sie', self.de['setup.chooseIntro'])

    def test_setup_and_settings_are_different_words(self):
        self.assertEqual(self.de['setup.title'], 'Lastbook einrichten')
        self.assertEqual(self.de['nav.settings'], 'Einstellungen')
        self.assertIn('Einrichtung und Einstellungen', self.de['language.preview'])
        self.assertIn('Region', self.de['setup.chooseIntro'])        # not "Bundesstaat": the prompt is for any region

    def test_no_message_is_left_in_english(self):
        same = {key for key in self.de if self.de[key] == self.en[key]}
        self.assertLessEqual(same, {'nav.chat', 'nav.videos', 'nav.video', 'search.filter'})


class SpanishWording(unittest.TestCase):
    """The shipped es-419 catalogue keeps the terms docs/i18n.md#sample-locale-wording-es-419 asks for."""

    @classmethod
    def setUpClass(cls):
        load = lambda name: json.loads((ROOT / 'translations' / 'desktop' / name).read_text(encoding='utf-8'))
        cls.en, cls.es = load('en.json'), load('es-419.json')

    def test_setup_and_settings_are_different_words(self):
        self.assertEqual(self.es['nav.settings'], 'Ajustes')
        self.assertIn('Configuración inicial', self.es['setup.title'])
        self.assertIn('configuración inicial', self.es['setup.error'])
        self.assertNotEqual(self.es['nav.settings'], self.es['setup.title'])
        # Settings and first-run Setup stay distinct throughout the catalogue.
        joined = ' '.join(self._texts(self.es))
        self.assertIn('configuración inicial', joined)
        self.assertIn('Ajustes', joined)

    def test_state_prompt_and_everyday_words(self):
        self.assertIn('estado o región', self.es['setup.chooseIntro'])
        self.assertIn('computadora', self.es['setup.loading'])
        everything = ' '.join(self._texts(self.es))
        for avoid in (' equipo', 'Equipo', 'ordenador', 'vídeo', 'Vídeo'):
            self.assertNotIn(avoid, everything)
        self.assertEqual(self.es['language.unavailable'], 'El idioma guardado no está disponible. Lastbook usa inglés.')
        self.assertNotIn('está en inglés', self.es['language.unavailable'])
        self.assertNotIn('Spanish', self.en['language.unavailable'])
        self.assertEqual(self.en['language.unavailable'], 'The saved language is unavailable. Lastbook is using English.')

    @staticmethod
    def _texts(catalog):
        out = []
        for value in catalog.values():
            if isinstance(value, str):
                out.append(value)
            else:
                out.extend(value.values())
        return out

    def test_no_message_is_left_in_english(self):
        # Words that must differ from English (brand names, units and loan words such as "Chat" may match).
        same = {key for key in self.es if self.es[key] == self.en[key]}
        self.assertLessEqual(same, {
            'nav.chat', 'nav.videos', 'nav.video', 'library.chats', 'videos.title',
            'videos.headingQuoted', 'videos.kindPrefix', 'videos.speedNormal', 'videos.10to30',
            'saved.pdf', 'app.titleSuffix', 'time.hoursMinutes', 'time.minutes', 'time.seconds',
            'map.zoom', 'library.shelfVideos',
            'native.menu.zoom', 'common.video',
            'native.appFileDescription', 'installer.productName', 'installer.companyName',
        })

    def test_everyday_words_cover_the_full_catalogue(self):
        everything = ' '.join(self._texts(self.es))
        for avoid in (' equipo', 'Equipo', 'ordenador', 'vídeo', 'Vídeo'):
            self.assertNotIn(avoid, everything)

class CatalogueCoverage(unittest.TestCase):
    """Keys used in the desktop UI exist in the English catalogue."""

    def test_marked_and_tr_keys_are_in_english(self):
        import re
        en = json.loads((ROOT / 'translations' / 'desktop' / 'en.json').read_text(encoding='utf-8'))
        used = set()
        for path in (ROOT / 'web').glob('*'):
            if path.suffix not in {'.js', '.html'} or path.name in {'i18n-en.js', 'i18n-locales.js', 'i18n-core.js', 'i18n-dom.js'}:
                continue
            text = path.read_text(encoding='utf-8')
            used.update(re.findall(r'''data-i18n(?:-aria-label|-placeholder|-title|-alt)?=["']([A-Za-z][A-Za-z0-9_.-]*)["']''', text))
            used.update(k for k in re.findall(r'''\btr\(\s*['"]([A-Za-z][A-Za-z0-9_.-]*)['"]''', text) if not k.endswith('.'))
        missing = sorted(used - set(en))
        self.assertEqual(missing, [], f'missing from en.json: {missing}')
        self.assertGreaterEqual(len(used), 200)

class WindowsVersionInfo(unittest.TestCase):
    """App and Setup VERSIONINFO tables include es-MX / es-ES stand-ins for es-419."""

    def setUp(self):
        import windows_versioninfo as versioninfo
        self.versioninfo = versioninfo
        self.english, self.locales = versioninfo.load_catalogs()

    def test_pyinstaller_and_rc_include_spanish_tables(self):
        py = self.versioninfo.render_pyinstaller('setup', '1.2.3', '20261121-010203', self.english, self.locales)
        rc = self.versioninfo.render_rc('setup', '1.2.3', '20261121-010203', self.english, self.locales)
        for text in (py, rc):
            self.assertIn('040904B0', text)
            self.assertIn('080A04B0', text)
            self.assertIn('0C0A04B0', text)
            self.assertIn('Lastbook Setup', text)
            self.assertIn('Instalación de Lastbook', text)
            self.assertIn('build 20261121-010203', text)
            self.assertIn('compilación 20261121-010203', text)
        self.assertIn('1033, 1200, 2058, 1200, 3082, 1200', py)
        self.assertIn('0x409, 1200, 0x80A, 1200, 0xC0A, 1200', rc)
        uninstall = self.versioninfo.render_pyinstaller('uninstall', '1.2.3', 'stamp', self.english, self.locales)
        self.assertIn('Uninstall Lastbook', uninstall)
        self.assertIn('Desinstalar Lastbook', uninstall)
        app = self.versioninfo.render_pyinstaller('app', '1.2.3', 'stamp', self.english, self.locales)
        self.assertIn("StringStruct('FileDescription', 'Lastbook')", app)


class NativeInterpolation(unittest.TestCase):
    def test_parameter_values_are_not_recursively_interpolated(self):
        sys.path.insert(0, str(ROOT / 'app'))
        from i18n_native import interpolate
        self.assertEqual(interpolate('{name} / {other}', {
            'name': 'literal {other}', 'other': 'expanded',
        }), 'literal {other} / expanded')

    def test_native_visible_strings_have_localized_templates(self):
        en = json.loads((ROOT / 'translations' / 'desktop' / 'en.json').read_text(encoding='utf-8'))
        es = json.loads((ROOT / 'translations' / 'desktop' / 'es-419.json').read_text(encoding='utf-8'))
        self.assertEqual(en['installer.version'], 'Version {version}')
        self.assertEqual(es['installer.version'], 'Versión {version}')
        self.assertEqual((en['native.choose'], es['native.choose']), ('Choose', 'Elegir'))

    def test_native_invalid_library_error_uses_catalogue(self):
        sys.path.insert(0, str(ROOT / 'app'))
        import i18n_native
        import main
        old_locale = i18n_native.current_locale()
        self.addCleanup(i18n_native.set_locale, old_locale)
        i18n_native.set_locale('es-419')
        _, message = main.check(ROOT / 'does-not-exist')
        self.assertIn('no es una biblioteca de Lastbook', message)
        self.assertIn('LastbookData', message)
