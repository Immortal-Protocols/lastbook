"""Catalogue schema, deterministic generation and the release staging gate."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'packaging'))
sys.path.insert(0, str(ROOT / 'app'))
import i18n_catalogs as catalogues  # noqa: E402
import i18n_native  # noqa: E402


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

    def test_requires_every_spanish_message(self):
        self.spanish.write_text('{"hi":"Hola, {name}"}', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, "missing required translations: 'files'"):
            catalogues.generate(self.work)

    def test_allows_locale_specific_plural_categories_and_partial_sample_locales(self):
        self.spanish.write_text(
            '{"hi":"Hola, {name}", "files":{"=0":"Ninguno", "many":"{count} archivos", "other":"{count} archivos"}}',
            encoding='utf-8')
        (self.work / 'de.json').write_text('{"hi":"Hallo, {name}"}', encoding='utf-8')
        generated = catalogues.generate(self.work)
        self.assertIn('Ninguno', generated['i18n-locales.js'].decode('utf-8'))
        self.assertIn('de', generated['i18n-locales.js'].decode('utf-8'))

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
        desktop = generated['desktop'].decode('utf-8')
        self.assertIn('GenericName[es_419]=Biblioteca de supervivencia sin conexión', desktop)
        self.assertIn('Comment[de]=Die Survival-Bibliothek auf diesem Computer ohne Internet durchsuchen und lesen', desktop)
        self.assertIn('Keywords[zh_Hans]=生存;资料库;离线;急救;', desktop)
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

    def test_native_installer_desktop_and_macos_permission_assets_are_catalog_backed(self):
        generated = catalogues.generate()
        header = generated['stub_header'].decode('ascii')
        for phrase in ('El instalador no pudo localizarse.', 'Setup konnte sich nicht finden.', '\\u65e0\\u6cd5'):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, header)
        self.assertIn('GenericName[es_419]=Biblioteca de supervivencia sin conexión', generated['desktop'].decode('utf-8'))
        self.assertIn('GenericName[de]=Offline-Bibliothek für Krisenvorsorge', generated['desktop'].decode('utf-8'))
        self.assertIn('Keywords[es_419]=supervivencia;biblioteca;sin conexión;primeros auxilios;', generated['desktop'].decode('utf-8'))
        self.assertIn('Keywords[es]=supervivencia;biblioteca;sin conexión;primeros auxilios;', generated['desktop'].decode('utf-8'))
        self.assertIn('Comment[zh_Hans]=无需联网', generated['desktop'].decode('utf-8'))
        self.assertIn('Comment[zh_CN]=无需联网', generated['desktop'].decode('utf-8'))
        self.assertIn('Keywords[zh]=生存;资料库;离线;急救;', generated['desktop'].decode('utf-8'))
        spanish = generated['macos/es-419.lproj/InfoPlist.strings'].decode('utf-8')
        self.assertIn('NSDocumentsFolderUsageDescription', spanish)
        self.assertIn('Lastbook busca en Documentos', spanish)
        self.assertIn('macos/zh-Hans.lproj/InfoPlist.strings', generated)
        spec = (ROOT / 'packaging' / 'lastbook_macos.spec').read_text(encoding='utf-8')
        self.assertIn("'es-419', 'de', 'zh-Hans'", spec)
        self.assertIn("NATIVE_ENGLISH['native.macosPermission.documents']", spec)
        stub = (ROOT / 'packaging' / 'setup_stub' / 'lastbook_setup_stub.c').read_text(encoding='utf-8')
        self.assertIn('fail(STUB_DAMAGED)', stub)
        self.assertNotIn('fail(L"', stub)

    def test_every_supported_installer_locale_covers_the_full_installer_ui(self):
        installer = json.loads(catalogues.generate()['installer'].decode('utf-8'))
        required = set(installer['en'])
        for locale in ('es-419', 'de', 'zh-Hans'):
            with self.subTest(locale=locale):
                translated = set(installer['locales'][locale])
                self.assertEqual(required - translated, set(),
                                 f'{locale} installer messages fall back to English: {sorted(required - translated)}')

    def test_setup_stub_translations_use_static_storage_for_stack_probe_free_build(self):
        stub = (ROOT / 'packaging' / 'setup_stub' / 'lastbook_setup_stub.c').read_text(encoding='utf-8')
        self.assertIn('static char data[4096];', stub)
        self.assertNotIn('char data[4096];', stub.replace('static char data[4096];', ''))


class FallbackWording(unittest.TestCase):
    """Unavailable-language copy stays neutral across all offered locales."""

    def test_english_fallback_names_no_language(self):
        en = json.loads((ROOT / 'translations' / 'desktop' / 'en.json').read_text(encoding='utf-8'))
        text = en['language.unavailable']
        self.assertEqual(text, 'The saved language is unavailable. Lastbook is using English.')
        for name in ('Spanish', 'German', 'Chinese', 'español', 'Deutsch', '中文'):
            self.assertNotIn(name, text)


class NativeLocaleSettings(unittest.TestCase):
    def test_malformed_saved_language_falls_back_to_english(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = Path(tmp)
            for value in ([], {}, 7, True, None, 'not-a-locale'):
                (settings / 'ui-language.json').write_text(
                    json.dumps({'language': value}), encoding='utf-8')
                with self.subTest(value=value):
                    self.assertEqual(i18n_native.configure(settings), 'en')
            (settings / 'ui-language.json').write_text(
                json.dumps({'language': ['es-419']}), encoding='utf-8')
            self.assertEqual(i18n_native.configure(settings), 'en')
        self.assertEqual(i18n_native.set_locale('en'), 'en')

    def test_non_string_locale_is_safe_even_when_set_directly(self):
        for value in ([], {}, 7, True, None):
            with self.subTest(value=value):
                self.assertEqual(i18n_native.set_locale(value), 'en')
        self.assertEqual(i18n_native.set_locale('en'), 'en')

    def test_invalid_catalogue_uses_next_candidate_or_source_english(self):
        old_catalogs = i18n_native._catalogs
        old_locale = i18n_native.current_locale()
        self.addCleanup(setattr, i18n_native, '_catalogs', old_catalogs)
        self.addCleanup(setattr, i18n_native, '_locale', old_locale)
        with tempfile.TemporaryDirectory() as tmp:
            settings = Path(tmp) / 'settings'
            settings.mkdir()
            (settings / 'ui-language.json').write_text(
                json.dumps({'language': 'es-419'}), encoding='utf-8')
            bad = Path(tmp) / 'bad.json'
            unreadable = Path(tmp) / 'unreadable.json'
            packaged = Path(tmp) / 'packaged.json'
            bad.write_text('{ broken', encoding='utf-8')
            unreadable.write_text('{}', encoding='utf-8')
            packaged.write_text(json.dumps({
                'en': {'native.probe': 'Packaged English'},
                'locales': {'es-419': {'native.probe': 'Texto traducido'}},
            }), encoding='utf-8')
            read_text = Path.read_text

            def read_catalogue(path, *args, **kwargs):
                if path == unreadable:
                    # Simulate a permission error even when the test runs as root.
                    raise PermissionError('catalogue is not readable')
                return read_text(path, *args, **kwargs)

            with (mock.patch.object(i18n_native, '_candidates',
                                    return_value=iter((bad, unreadable, packaged))),
                  mock.patch.object(Path, 'read_text', new=read_catalogue)):
                i18n_native._catalogs = None
                self.assertEqual(i18n_native.configure(settings), 'es-419')
                self.assertEqual(i18n_native.native_t('native.probe', 'Source English'), 'Texto traducido')
            with (mock.patch.object(i18n_native, '_candidates',
                                    return_value=iter((bad, unreadable))),
                  mock.patch.object(Path, 'read_text', new=read_catalogue)):
                i18n_native._catalogs = None
                self.assertEqual(i18n_native.configure(settings), 'en')
                self.assertEqual(i18n_native.native_t('native.probe', 'Source English'), 'Source English')
            malformed_shape = Path(tmp) / 'malformed-shape.json'
            malformed_shape.write_text(json.dumps({
                'en': {'native.probe': 'English catalogue'},
                'locales': {'de': 'not a catalogue'},
            }), encoding='utf-8')
            with mock.patch.object(i18n_native, '_candidates', return_value=iter((malformed_shape,))):
                i18n_native._catalogs = None
                self.assertEqual(i18n_native.configure(settings), 'en')
                self.assertEqual(i18n_native.native_t('native.probe', 'Source English'), 'Source English')


class GermanWording(unittest.TestCase):
    """The de catalogue keeps the conventions in docs/i18n.md#german-de."""

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

    def test_informal_imperatives_are_not_used(self):
        import re
        informal = re.findall(r'\b(?:Erhalte|Versuche|Wähle|Klicke|Öffne|Lade|Verwende|Prüfe|Gib|Nimm|Trage|Gehe|Tippe|Schließe|Bestätige|Füge|Warte|Fahre|Stelle|Setze|Mach|Tue|Sieh|Lies|Rufe|Halte)\b',
                              ' '.join(self.de.values()), flags=re.IGNORECASE)
        self.assertEqual(informal, [])
        self.assertEqual(self.de['search.label'], 'Suche')  # noun, not the informal imperative

    def test_setup_and_settings_are_different_words(self):
        self.assertEqual(self.de['setup.title'], 'Lastbook einrichten')
        self.assertEqual(self.de['nav.settings'], 'Einstellungen')
        self.assertIn('Einrichtung und Einstellungen', self.de['language.preview'])
        self.assertIn('Region', self.de['setup.chooseIntro'])

    def test_no_message_is_left_in_english(self):
        same = {key for key in self.de if self.de[key] == self.en[key]}
        self.assertLessEqual(same, {
            'nav.chat', 'nav.videos', 'nav.video', 'search.filter',
            'installer.productName', 'installer.companyName',
            'installer.version', 'videos.speedNormal',
            'videos.row.coalcracker', 'videos.row.corporals', 'videos.row.canterbury', 'videos.row.primitive',
        })


class SimplifiedChineseWording(unittest.TestCase):
    """The zh-Hans catalogue keeps the conventions in docs/i18n.md#simplified-chinese-zh-hans."""

    @classmethod
    def setUpClass(cls):
        load = lambda name: json.loads((ROOT / 'translations' / 'desktop' / name).read_text(encoding='utf-8'))
        cls.en, cls.zh = load('en.json'), load('zh-Hans.json')

    def test_setup_and_settings_are_different_words(self):
        self.assertEqual(self.zh['nav.settings'], '设置')
        self.assertIn('初始设置', self.zh['setup.title'])
        self.assertNotIn('设置', self.zh['setup.title'].replace('初始设置', ''))
        self.assertIn('初始设置', self.zh['language.preview'])
        self.assertIn('设置', self.zh['language.preview'])

    def test_simplified_characters_only(self):
        traditional = '設資庫這個們來時間對話選擇頁題導覽視頻標開關閉啟儲載網線說檔電腦檢區換'
        everything = ' '.join(self.zh.values())
        self.assertEqual([character for character in traditional if character in everything], [])

    def test_everyday_words_and_formatting(self):
        self.assertIn('这台电脑', self.zh['setup.loading'])
        self.assertIn('州或地区', self.zh['setup.chooseIntro'])
        self.assertIn('Lastbook 会', self.zh['setup.chooseIntro'])
        self.assertEqual(self.zh['setup.settingsTitle'], '资料库与本地 AI')
        everything = ' '.join(self.zh.values())
        for bad in (' ,', ' 。', ' ，', ' ；', ' …', '\u3000', '..'):
            self.assertNotIn(bad, everything)
        self.assertTrue(self.zh['language.saving'].endswith('…'))

    def test_no_message_is_left_in_english(self):
        same = {key for key in self.zh if self.zh[key] == self.en[key]}
        # Lastbook and creator/channel names are intentionally preserved.
        self.assertEqual(same, {
            'installer.productName', 'installer.companyName',
            'videos.row.coalcracker', 'videos.row.corporals', 'videos.row.canterbury', 'videos.row.primitive',
        })


class SpanishWording(unittest.TestCase):
    """The shipped es-419 catalogue keeps the terms docs/i18n.md#sample-locale-wording-es-419 asks for."""

    @classmethod
    def setUpClass(cls):
        load = lambda name: json.loads((ROOT / 'translations' / 'desktop' / name).read_text(encoding='utf-8'))
        cls.en, cls.es = load('en.json'), load('es-419.json')

    def test_language_preview_describes_complete_interface(self):
        preview = self.es['language.preview']
        self.assertIn('parcial', preview.casefold())
        self.assertIn('algunos textos de la interfaz', preview.casefold())
        self.assertIn('menús nativos', preview.casefold())
        self.assertIn('inglés', preview.casefold())

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
            'chat.sourceType.videos',
            'native.appFileDescription', 'installer.productName', 'installer.companyName',
            'setup.facts.sha256', 'setup.facts.bytes', 'videos.videoCount',
            'videos.row.coalcracker', 'videos.row.corporals', 'videos.row.canterbury', 'videos.row.primitive',
            # Server-sent labels whose Spanish is the same word.
            'kind.pdf', 'kind.video', 'poi.hospital', 'map.summary.acres',
        })

    def test_catalogue_covers_every_english_message(self):
        self.assertEqual(set(self.es), set(self.en),
                         f'missing: {sorted(set(self.en) - set(self.es))}; extra: {sorted(set(self.es) - set(self.en))}')

    def test_everyday_words_cover_the_full_catalogue(self):
        everything = ' '.join(self._texts(self.es))
        for avoid in (
            ' equipo', 'Equipo', 'ordenador', 'vídeo', 'Vídeo', 'relevamiento',
            'gazetero', 'nata verde', 'en marcha', 'arrancando', 'municipalidades',
        ):
            self.assertNotIn(avoid, everything)

    def test_reviewed_copy_uses_neutral_consistent_wording(self):
        self.assertEqual(self.es['map.nothingNearby'], 'No hay elementos de tus capas a menos de 100 millas del centro del mapa.')
        self.assertIn('como familia', self.es['chat.starter.comms'])
        self.assertIn('mantén presionada la tecla Mayús', self.es['map3d.dragMouse'])
        self.assertIn('mejor coinciden con tu pregunta', self.es['chat.offlinePages'])
        self.assertIn('se conserva en la unidad', self.es['setup.stopCopyConfirm'])
        self.assertIn('Instalaciones para embarcaciones', self.es['map.layer.boat'])
        self.assertEqual(self.es['setup.tryAgain'], 'Reintentar')
        self.assertIn('Vuelve a intentarlo', self.es['setup.connectionHint'])

    def test_3d_building_height_summary_is_a_complete_plural_message(self):
        key = 'map3d.buildingHeightSummary'
        self.assertEqual(set(self.en[key]), {'one', 'other'})
        self.assertEqual(set(self.es[key]), {'one', 'other'})
        for catalog in (self.en, self.es):
            for fragment in ('map3d.heightsAre', 'map3d.mappedHeights', 'map3d.oneStoreyShown'):
                self.assertNotIn(fragment, catalog)
            for selector in ('one', 'other'):
                self.assertIn('{count}', catalog[key][selector])
                for param in ('mapped', 'satellite', 'guessed', 'nearest'):
                    self.assertIn('{' + param + '}', catalog[key][selector])

    def test_topic_short_catalogue_entries_match_topic_data(self):
        topics = [json.loads(path.read_text(encoding='utf-8'))
                  for path in sorted((ROOT / 'content' / 'topics').glob('*.json'))]
        self.assertEqual(len(topics), 14)
        expected = {f"topic.short.{topic['id']}" for topic in topics}
        self.assertTrue(expected <= set(self.en))
        self.assertTrue(expected <= set(self.es))
        for topic in topics:
            key = f"topic.short.{topic['id']}"
            with self.subTest(topic=topic['id']):
                self.assertEqual(self.en[key], topic['short'])
                self.assertNotEqual(self.es[key], self.en[key])
                self.assertEqual(catalogues.placeholders(self.es[key]),
                                 catalogues.placeholders(self.en[key]))

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
    """App and Setup VERSIONINFO tables cover the supported desktop locales."""

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

    def test_pyinstaller_and_rc_include_german_and_simplified_chinese_tables(self):
        self.assertEqual(set(self.locales), {'es-419', 'de', 'zh-Hans'})
        py = self.versioninfo.render_pyinstaller('setup', '1.2.3', '20261121-010203', self.english, self.locales)
        rc = self.versioninfo.render_rc('setup', '1.2.3', '20261121-010203', self.english, self.locales)
        uninstall_py = self.versioninfo.render_pyinstaller('uninstall', '1.2.3', 'stamp', self.english, self.locales)
        uninstall_rc = self.versioninfo.render_rc('uninstall', '1.2.3', 'stamp', self.english, self.locales)
        app = self.versioninfo.render_pyinstaller('app', '1.2.3', 'stamp', self.english, self.locales)
        for text in (py, rc, uninstall_py, uninstall_rc, app):
            for table in ('040704B0', '080404B0', '100404B0'):
                self.assertIn(table, text)
        for text in (py, rc):
            self.assertIn('Lastbook-Installation', text)
            self.assertIn('Lastbook 安装程序', text)
        for text in (uninstall_py, uninstall_rc):
            self.assertIn('Lastbook entfernen', text)
            self.assertIn('卸载 Lastbook', text)
        self.assertIn('1031, 1200', py)
        self.assertIn('2052, 1200', py)
        self.assertIn('4100, 1200', py)
        self.assertIn('0x407, 1200', rc)
        self.assertIn('0x804, 1200', rc)
        self.assertIn('0x1004, 1200', rc)


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

    def test_native_unwritable_library_error_uses_catalogue(self):
        sys.path.insert(0, str(ROOT / 'app'))
        import i18n_native
        import main
        old_locale = i18n_native.current_locale()
        self.addCleanup(i18n_native.set_locale, old_locale)
        i18n_native.set_locale('es-419')
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / 'LastbookData'
            (folder / 'library-data').mkdir(parents=True)
            (folder / 'library-data' / 'catalog.json').write_text('{}', encoding='utf-8')
            with mock.patch.object(main, 'writable', return_value=False):
                found, message = main.check(folder)
        self.assertIsNone(found)
        self.assertIn('Lastbook no puede guardar en', message)
        self.assertIn('LastbookData', message)
