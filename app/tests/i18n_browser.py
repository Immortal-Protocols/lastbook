"""Browser integration over staged files, the real bridge and the HTTP handler.

Run with the optional Playwright development tool and Chromium:
  python3 -B app/tests/i18n_browser.py --chromium /path/to/chromium
The loopback relay stands in for WebView2's resource callback. It is test-only.
"""
import argparse
import contextlib
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from queue import Empty, Queue
from unittest.mock import patch

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'app')]
import fixture

DATA = fixture.ensure()
os.environ['LASTBOOK_DATA'] = str(DATA)
import bridge
import server
from engine.setup.manifest import Manifest

ROUTE = bridge.ui_language.ROUTE


class Relay(BaseHTTPRequestHandler):
    def do_GET(self):
        b = self.server.bridge
        body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
        hold = self.server.holds.get((self.command, self.path))
        if hold is not None and not hold.wait(15):
            self.send_error(503)
            return
        gate = None
        if self.path == ROUTE:
            try:
                gate = self.server.language_replies[self.command].get_nowait()
            except (Empty, KeyError):
                pass
        done = threading.Event()
        responses = []

        def answer(response):
            responses.append(response)
            done.set()

        b.fetch(self.command, b.origin + self.path, self.headers, body, answer)
        if not done.wait(15):
            self.send_error(504)
            return
        response = responses[0]
        try:
            if gate:
                arrived, release = gate
                arrived.set()
                if not release.wait(15):
                    self.send_error(504)
                    return
            self.send_response(response.status)
            for name, value in response.headers:
                self.send_header(name, value)
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(Path(response.path).read_bytes() if response.path else response.body or b'')
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            if response.delete:
                Path(response.path).unlink()
            response.release()

    do_POST = do_HEAD = do_GET

    def log_message(self, *args):
        pass


@contextlib.contextmanager
def serve(module=None, language_file=None):
    handler = Relay if module else server.Handler
    with ThreadingHTTPServer(('127.0.0.1', 0), handler) as http:
        host = 'lastbook.invalid' if module else '127.0.0.1'
        origin = f'http://{host}:{http.server_port}'
        http.holds = {}
        http.language_replies = {method: Queue() for method in ('GET', 'POST')}
        if module:
            http.bridge = bridge.Bridge(module, 'buffer', origin, language_file=language_file)
        worker = threading.Thread(target=http.serve_forever, daemon=True)
        worker.start()
        try:
            yield origin, http
        finally:
            for gate in http.holds.values():
                gate.set()
            http.shutdown()
            worker.join()


@contextlib.contextmanager
def delay_language_reply(http, method):
    arrived, release = threading.Event(), threading.Event()
    http.language_replies[method].put((arrived, release))
    try:
        yield arrived, release
    finally:
        release.set()


class Browser(unittest.TestCase):
    chromium = None

    @classmethod
    def setUpClass(cls):
        scratch = tempfile.TemporaryDirectory()
        cls.addClassCleanup(scratch.cleanup)
        web = Path(scratch.name) / 'web'
        subprocess.run([sys.executable, '-I', '-B', str(ROOT / 'packaging' / 'ship_app_files.py'), scratch.name],
                       check=True)
        cls.enterClassContext(patch.object(server, 'WEB', web))
        cls.enterClassContext(patch.object(server.setup_api, 'web_dir', return_value=web))
        server.init(no_index=True)
        runtime = cls.enterClassContext(sync_playwright())
        cls.browser = runtime.chromium.launch(executable_path=cls.chromium,
                                             ignore_default_args=['--disable-back-forward-cache'],
                                             args=['--no-proxy-server', '--host-resolver-rules=MAP lastbook.invalid 127.0.0.1'])
        cls.addClassCleanup(cls.browser.close)

    def setUp(self):
        self.tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.language_file = self.tmp / bridge.ui_language.FILENAME

    def configure_setup(self, current=None, library=DATA, setup_manifest=None):
        return server.setup_api.configure(mode='manage' if current else 'first-run', current=current,
                                          settings_dir=self.tmp, default_parent=self.tmp, manifest=setup_manifest or Manifest(remote=None),
                                          pick_folder=lambda files=False: str(library))

    @staticmethod
    def local_ai_manifest():
        from engine.setup import manifest as setup_manifest

        data = {'version': 1, 'packs': [{
            'id': 'small', 'title': 'Small', 'summary': 'The essentials.', 'available': True,
            'installed_bytes': 100, 'files': [{'name': 'small.zip', 'size': 1, 'sha256': '0' * 64,
                'url': 'https://downloads.lastbook.org/small.zip'}],
        }], 'models': [{
            'id': 'local', 'title': 'Local AI', 'file': 'model.gguf', 'size': 17_000_000_000,
            'sha256': '1' * 64, 'url': 'https://huggingface.co/lastbook/model.gguf',
            'memory_bytes': 12_000_000_000, 'available': True,
        }]}
        bundled = setup_manifest.validate(data)
        if bundled is None:
            raise AssertionError('test manifest must be valid')
        return Manifest(bundled=bundled, remote=None)

    def set_hardware(self, setup, *, fits, disk_path=None):
        why = 'The local AI needs about 20 GB of this computer’s memory, and it has 8 GB. Lastbook works without it: search and reading are the same.'
        setup.hardware = lambda: {
            'os': 'linux', 'ram_bytes': 8_000_000_000, 'unified_memory': False, 'gpus': [],
            'disks': [{'path': str(disk_path or self.tmp), 'name': None,
                       'free_bytes': 80_000_000_000, 'total_bytes': 100_000_000_000}],
            'ai': {'fits': fits, 'needs_bytes': 20_000_000_000, 'estimate': True, 'why': why,
                   'why_key': 'setup.why.aiNeedsMemoryShort', 'why_params': {'needs': '20 GB', 'ram': '8 GB'}},
        }

    @contextlib.contextmanager
    def page(self, origin, http, locale='en-US'):
        context = self.browser.new_context(locale=locale, viewport={'width': 1280, 'height': 850}, accept_downloads=True)
        try:
            if hasattr(http, 'bridge'):
                context.add_init_script(http.bridge.top_script())
            page = context.new_page()
            page.set_default_timeout(5000)
            requests, errors = [], []
            page.on('request', lambda r: requests.append(r.url))
            page.on('pageerror', lambda e: errors.append(str(e)))
            yield page
            self.assertEqual(errors, [])
            self.assertTrue(all(url.startswith(origin + '/') for url in requests), requests)
        finally:
            context.close()

    def test_setup_save_and_library_in_a_fresh_profile(self):
        self.configure_setup()
        with serve(server.setup_api.SetupServer, self.language_file) as (origin, http), self.page(origin, http) as page:
            hold = http.holds[('GET', '/api/setup/state')] = threading.Event()
            page.goto(origin, wait_until='domcontentloaded')
            expect(page.locator('.loading')).to_have_text('Looking at this computer…')
            select = page.get_by_label('Interface language')
            expect(select).to_have_value('en')
            self.assertEqual(select.locator('[lang="es-419"]').inner_text(), 'Español (Latinoamérica)')
            select.select_option('es-419')
            page.get_by_role('button', name='Save language').click()
            expect(page.get_by_role('status')).to_have_text('Idioma guardado. Reinicia Lastbook para actualizar los menús.')
            expect(page.locator('.loading')).to_have_text('Revisando esta computadora…')
            self.assertEqual(json.loads(self.language_file.read_bytes()), {'language': 'es-419'})
            hold.set()
            expect(page.locator('h1')).to_have_text('Configuración inicial de Lastbook')
            expect(page.get_by_role('button', name='Guardar idioma')).to_be_focused()
            expect(page.locator('#packH')).to_have_text('Biblioteca')
            page.locator('#haveLib').click()
            with page.expect_response('**/api/setup/finish') as done:
                page.locator('#open').click()
            self.assertEqual(done.value.json()['folder'], str(DATA))

        self.configure_setup(current=DATA)
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.goto(origin + '/#/guides')
            sidebar = page.locator('.side')
            guides = sidebar.get_by_role('link', name='Guías')
            expect(guides).to_have_attribute('aria-current', 'page')
            expect(guides).to_have_attribute('lang', 'es-419')
            expect(page.locator('html')).to_have_attribute('lang', 'es-419')
            expect(page.locator('.need[href="#/t/hurt"] small')).to_have_text('Primeros auxilios para hemorragias, quemaduras, problemas respiratorios, lesiones y enfermedades repentinas')
            expect(page.locator('.need[href="#/t/water"] small')).to_have_text('Tratar, encontrar y almacenar agua')
            expect(page.locator('.need[href="#/t/shelter"] small')).to_have_text('Calor, frío, humo, monóxido de carbono, viviendas dañadas y refugio al aire libre')
            top = page.get_by_role('searchbox', name='Buscar en la biblioteca')
            expect(top).to_have_attribute('placeholder', 'Buscar en la biblioteca')
            page.evaluate("location.hash = '#/search?q=frijoles'")
            expect(page.locator('#kinds')).to_contain_text('Todo')
            expect(page.locator('#kinds')).to_contain_text('Manuales y páginas')
            expect(page.locator('#kinds')).to_contain_text('Videos')
            page.evaluate("location.hash = '#/guides'")
            expect(page.locator('h1')).to_have_text('¿Qué necesitas?')
            page.set_viewport_size({'width': 780, 'height': 820})
            expect(guides).to_have_attribute('title', 'Guías')
            page.set_viewport_size({'width': 390, 'height': 780})
            tab = page.locator('.tabbar').get_by_role('link', name='Guías')
            expect(tab).to_be_visible()
            expect(tab).to_have_attribute('aria-current', 'page')
            page.set_viewport_size({'width': 1280, 'height': 850})
            expect(guides).not_to_have_attribute('title', 'Guías')
            # Force the usual narrow toolbar field, independently of host fonts.
            page.locator('#topQ').evaluate("(el) => el.style.width='110px'")
            expect(top).to_have_attribute('placeholder', 'Buscar')
            top.fill('user text')
            page.locator('.skip').focus()
            page.keyboard.press('Enter')
            expect(page.locator('#main')).to_be_focused()
            self.assertTrue(page.url.endswith('#/guides'))
            expect(top).to_have_value('user text')

            markup = '<img src=x onerror=window.bad=1>'
            page.set_viewport_size({'width': 390, 'height': 780})
            page.evaluate("(q) => location.hash = '#/search?q=' + encodeURIComponent(q)", markup)
            search = page.locator('#searchQ')
            expect(search).to_have_value(markup)
            expect(search).to_have_accessible_name('Buscar')
            self.assertEqual(page.locator('img[src=x]').count(), 0)
            self.assertIsNone(page.evaluate('window.bad'))
            page.evaluate("location.hash = '#/watch/vida?from=%23%2Fsearch'")
            expect(page.locator('.rtop .back')).to_have_text('Resultados de búsqueda')
            expect(page.locator('h1')).to_have_text('vida')  # library title
            page.evaluate("location.hash = '#/missing'")
            expect(page.get_by_role('link', name='Ir a Videos')).to_be_visible()

            page.set_viewport_size({'width': 1280, 'height': 850})
            page.evaluate("location.hash = '#/guides'")
            expect(page.locator('h1')).to_have_text('¿Qué necesitas?')
            sidebar.get_by_role('link', name='Ajustes').click()
            expect(page.locator('h1')).to_have_text('Biblioteca e IA local')
            expect(page.get_by_role('link', name='Volver a la biblioteca')).to_be_visible()
            expect(page.locator('.s-have .s-row b').first).to_have_text(re.compile(r'^Biblioteca\b'))
            expect(page.locator('.s-have .s-row').first).to_contain_text('La más grande')
            expect(page.get_by_role('button', name='Comprobar y reparar')).to_be_visible()
            expect(page.get_by_role('button', name='Abrir otra carpeta de biblioteca')).to_be_visible()
            page.get_by_label('Idioma de la interfaz').select_option('en')
            pending = http.holds[('POST', ROUTE)] = threading.Event()
            page.get_by_role('button', name='Guardar idioma').click()
            expect(page.get_by_role('status')).to_have_text('Guardando el idioma…')
            expect(page.locator('h1')).to_have_text('Biblioteca e IA local')
            self.assertEqual(json.loads(self.language_file.read_bytes()), {'language': 'es-419'})
            page.get_by_label('Idioma de la interfaz').select_option('es-419')
            pending.set()
            expect(page.get_by_role('status')).to_have_text('Language saved. Restart Lastbook to update its menus.')
            expect(page.get_by_label('Interface language')).to_have_value('en')
            expect(page.locator('h1')).to_have_text('Library and local AI')
            expect(page.locator('.s-have .s-row').first).not_to_contain_text('La más grande')
            expect(page.locator('.s-have .s-row').first).to_contain_text('The largest')
            expect(page.get_by_role('button', name='Save language')).to_be_focused()
            page.evaluate('history.back()')
            page.wait_for_url('**/#/guides', wait_until='commit')
            expect(sidebar.get_by_role('link', name='Guides')).to_be_visible()
            expect(page.locator('html')).to_have_attribute('lang', 'en')
            expect(page.locator('.need[href="#/t/hurt"] small')).to_have_text('First aid for bleeding, burns, breathing, injuries and sudden illness')
            expect(page.locator('.need[href="#/t/water"] small')).to_have_text('Treat, find and store water')
            page.reload()
            expect(page.locator('.need[href="#/t/hurt"] small')).to_have_text('First aid for bleeding, burns, breathing, injuries and sudden illness')
            expect(page.locator('.need[href="#/t/water"] small')).to_have_text('Treat, find and store water')
            expect(page.locator('.need[href="#/t/shelter"] small')).to_have_text('Heat, cold, smoke, carbon monoxide, damaged homes and outdoor shelter')
            sidebar.get_by_role('link', name='Settings').click()
            page.get_by_role('link', name='Back to the library').click()
            expect(page.locator('.side').get_by_role('link', name='Guides')).to_be_visible()

    def test_live_language_switch_retranslates_hardware_tiles_and_repair_without_reload(self):
        setup = self.configure_setup(current=DATA)
        self.set_hardware(setup, fits=False, disk_path=DATA)
        with serve(server.setup_api.SetupServer, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.goto(origin)
            tiles = page.locator('.s-pc')
            repair = page.locator('#repair')
            expect(repair).to_have_text('Check and repair')
            expect(tiles).to_contain_text('memory')
            expect(tiles).to_contain_text('free on')
            expect(tiles).to_contain_text('graphics card for the AI')
            expect(tiles).to_have_attribute('aria-label', 'This computer')
            page.evaluate('window.__sameDocument = true')
            page.get_by_label('Interface language').select_option('es-419')
            page.get_by_role('button', name='Save language').click()
            expect(page.get_by_role('status')).to_have_text('Idioma guardado. Reinicia Lastbook para actualizar los menús.')
            expect(repair).to_have_text('Comprobar y reparar')
            expect(tiles).to_contain_text('memoria')
            expect(tiles).to_contain_text('libres en')
            expect(tiles).to_contain_text('tarjeta gráfica para la IA')
            expect(tiles).not_to_contain_text('memory')
            expect(tiles).to_have_attribute('aria-label', 'Esta computadora')
            self.assertTrue(page.evaluate('window.__sameDocument === true'), 'the page reloaded')
            page.get_by_label('Idioma de la interfaz').select_option('en')
            page.get_by_role('button', name='Guardar idioma').click()
            expect(repair).to_have_text('Check and repair')
            expect(tiles).to_contain_text('graphics card for the AI')
            expect(tiles).not_to_contain_text('memoria')
            self.assertTrue(page.evaluate('window.__sameDocument === true'), 'the page reloaded')
            self.assertEqual(json.loads(self.language_file.read_bytes()), {'language': 'en'})

    def test_copy_start_api_error_is_translated_in_spanish(self):
        self.configure_setup(current=DATA)
        self.language_file.write_text('{"language":"es-419"}', encoding='utf-8')
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.route('**/api/setup/start', lambda route: route.fulfill(
                status=200, content_type='application/json',
                body=json.dumps({'code': 'folder', 'error': 'Lastbook cannot save there. Choose another drive.',
                                 'key': 'setup.err.cannotSaveThere'})))
            page.goto(origin + '/ui/setup.html#manage', wait_until='domcontentloaded')
            expect(page.locator('h1')).to_have_text('Biblioteca e IA local')
            page.locator('#copyOut').click()
            expect(page.locator('h1')).to_have_text('Copiar para otra persona')
            page.locator('#copyGo').click()
            expect(page.locator('#haveNote')).to_have_text('Lastbook no puede guardar ahí. Elige una unidad en la que puedas escribir.')

    def test_setup_polling_and_a_completed_action_preserve_the_selector(self):
        setup = self.configure_setup()
        setup.job = {'state': 'downloading', 'items': [
            {'id': 'small', 'kind': 'pack', 'title': 'Library', 'state': 'downloading',
             'bytes_done': 20, 'bytes_total': 100},
        ]}
        with serve(server.setup_api.SetupServer, self.language_file) as (origin, http), self.page(origin, http) as page:
            pause = http.holds[('POST', '/api/setup/pause')] = threading.Event()
            with page.expect_response('**/api/setup/job'):
                page.goto(origin)
                expect(page.get_by_role('button', name='Pause')).to_be_visible()
            expect(page.locator('.s-steps li')).to_have_text(['Download', 'Check', 'Unpack', 'Finish'])
            page.get_by_role('button', name='Pause').click()
            select = page.get_by_label('Interface language')
            select.focus()
            with setup.lock:
                setup.job['state'] = 'paused'
                setup.job['items'][0]['state'] = 'paused'
            pause.set()
            expect(page.get_by_role('button', name='Resume')).to_be_visible()
            expect(select).to_be_focused()
            select.select_option('es-419')
            page.get_by_role('button', name='Save language').click()
            expect(page.get_by_role('status')).to_have_text('Idioma guardado. Reinicia Lastbook para actualizar los menús.')
            expect(page.get_by_role('button', name='Reanudar')).to_be_visible()
            expect(page.locator('.s-steps li')).to_have_text(['Descargar', 'Comprobar', 'Descomprimir', 'Terminar'])
            expect(page.locator('.s-state')).to_have_text('En pausa')

    def test_spanish_search_example_finds_english_library_content(self):
        self.configure_setup(current=DATA)
        self.language_file.write_text('{"language":"es-419"}', encoding='utf-8')
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.goto(origin + '/#/search')
            expect(page.locator('#sout > p.muted')).to_have_text(
                'Usa las palabras que usarías al hablar con alguien. Por ejemplo:')
            expect(page.locator('#sout > p.muted span[lang="es-419"]')).to_have_text(
                'Usa las palabras que usarías al hablar con alguien. Por ejemplo:')
            page.route('**/api/page/**', lambda route: route.fulfill(status=404, body=''))
            page.goto(origin + '/#/search?q=hervir%20agua')
            expect(page.locator('#searchQ')).to_have_value('hervir agua')
            expect(page.locator('.results .result')).to_have_count(1)
            expect(page.locator('.results .result h3')).to_contain_text('pdfsmall')
            expect(page.locator('#sask')).to_contain_text('Pregunta a la biblioteca: “hervir agua”')
            expect(page.locator('#sask')).to_contain_text('Recibe una respuesta escrita basada en las páginas exactas de la biblioteca.')
            self.assertIsNone(page.locator('.results .result').get_attribute('lang'))
            tagged = page.evaluate("""() => {
                const box = document.createElement('div');
                box.innerHTML = resultCard({title:'Documento', hits:[], trust:'', language:'es-MX'});
                return box.firstElementChild.getAttribute('lang');
            }""")
            self.assertEqual(tagged, 'es-MX')

    def test_saved_language_localizes_document_metadata_on_first_load(self):
        self.configure_setup(current=DATA)
        self.language_file.write_text('{"language":"es-419"}', encoding='utf-8')
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.goto(origin + '/#/guides')
            description = page.locator('meta[name="description"]')
            expect(description).to_have_attribute('content',
                'Guía de supervivencia y reconstrucción sin conexión: primeros auxilios, agua, alimentos, energía, refugio, videos, mapas y habilidades.')
            expect(description).to_have_attribute('lang', 'es-419')

    def test_missing_library_item_error_is_translated(self):
        self.configure_setup(current=DATA)
        self.language_file.write_text('{"language":"es-419"}', encoding='utf-8')
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.goto(origin + '/#/read/item-no-longer-present')
            expect(page.locator('#main')).to_contain_text('Este elemento ya no está en la biblioteca.')

    def test_library_note_count_uses_catalogue_plural_and_language(self):
        self.configure_setup(current=DATA)
        self.language_file.write_text('{"language":"es-419"}', encoding='utf-8')
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.route('**/api/not-found', lambda route: route.fulfill(
                status=200, content_type='application/json',
                body=json.dumps({'notes': [{'id': 'note-1'}, {'id': 'note-2'}]})))
            page.goto(origin + '/#/library')
            expect(page.locator('#nfCount')).to_have_text('2 notas en esta computadora')
            expect(page.locator('#nfCount span[lang="es-419"]')).to_have_text('2 notas en esta computadora')

    def test_chat_dynamic_text_tags_the_language_that_supplied_it(self):
        self.configure_setup(current=DATA)
        self.language_file.write_text('{"language":"de"}', encoding='utf-8')
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.route('**/api/assistant/status', lambda route: route.fulfill(
                status=200, content_type='application/json',
                body=json.dumps({'online': False, 'local': {'state': 'absent'}})))
            page.goto(origin + '/#/ask?about=topic:water')
            expect(page.locator('html')).to_have_attribute('lang', 'de')
            expect(page.locator('#chatStatus span[lang="en"]').first).to_have_text('No local AI added')
            expect(page.locator('.starter span[lang="en"]').first).to_have_text('What should I do first?')
            expect(page.locator('#csList li.muted.small span[lang="en"]')).to_have_text('No chats yet.')
            self.assertEqual(page.locator('.starter').first.get_attribute('data-start'), 'What should I do first?')

    def test_chat_context_video_and_page_labels_use_neutral_catalogue_copy(self):
        self.configure_setup(current=DATA)
        self.language_file.write_text('{"language":"es-419"}', encoding='utf-8')
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.route('**/api/doc/**', lambda route: route.fulfill(
                status=200, content_type='application/json', body=json.dumps({'title': 'Reference'})))
            page.goto(origin + '/#/ask?about=video:clip:90')
            expect(page.locator('#ctxChip .muted span[lang="es-419"]')).to_have_text('Video en 1:30')
            page.evaluate("location.hash = '#/ask?about=doc:manual:3'")
            expect(page.locator('#ctxChip .muted span[lang="es-419"]')).to_have_text('Página 3')

    def test_chat_home_fallback_labels_are_language_tagged(self):
        self.configure_setup(current=DATA)
        self.language_file.write_text('{"language":"de"}', encoding='utf-8')
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.goto(origin + '/#/ask')
            expect(page.locator('#askMore .ask-cards .ask-card .ac-t span[lang="en"]').first).to_be_visible()
            expect(page.locator('#askMore .ask-learn a b span[lang="en"]').first).to_be_visible()

    def test_chat_list_recovers_from_invalid_saved_dates(self):
        self.configure_setup(current=DATA)
        chat = {'id': 'invalid-date', 'title': 'Saved chat', 'messages': [{'role': 'user', 'content': 'Question'}]}
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.add_init_script("localStorage.setItem('sg.chats', " + json.dumps(json.dumps([chat])) + ");")
            page.goto(origin + '/#/ask')
            expect(page.locator('#csList li b')).to_have_text('Saved chat')
            expect(page.locator('#csList li small')).to_contain_text('1 question')

    def test_chat_export_survives_without_i18n_date_adapter(self):
        self.configure_setup(current=DATA)
        chat = {
            'id': 'export-date-fallback', 'title': 'Saved chat', 'updated': '2026-11-17T12:00:00Z',
            'messages': [{'role': 'user', 'content': 'Question'}, {'role': 'assistant', 'content': 'Answer.', 'cited': []}],
        }
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.add_init_script("localStorage.setItem('sg.chats', " + json.dumps(json.dumps([chat])) + ");")
            page.goto(origin + '/#/ask/export-date-fallback')
            page.evaluate('window.LastbookI18n = undefined')
            with page.expect_download() as download_info:
                page.locator('[data-act="export"]').click()
            self.assertTrue(download_info.value.suggested_filename.endswith('.md'))

    def test_chat_source_filters_use_neutral_spanish_labels(self):
        self.configure_setup(current=DATA)
        self.language_file.write_text('{"language":"es-419"}', encoding='utf-8')
        chat = {
            'id': 'source-filter-chat', 'title': 'Question', 'updated': '2026-11-17T12:00:00Z',
            'messages': [
                {'role': 'user', 'content': 'Question'},
                {'role': 'assistant', 'content': 'Answer [S1].', 'cited': [
                    {'key': 'S1', 'kind': 'page', 'doc_id': 'manual', 'title': 'Manual'},
                    {'key': 'S2', 'kind': 'video', 'doc_id': 'video', 'title': 'Video', 't': 12},
                ], 'steps': []},
            ],
        }
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.add_init_script("localStorage.setItem('sg.chats', " + json.dumps(json.dumps([chat])) + ");")
            page.goto(origin + '/#/ask/source-filter-chat')
            expect(page.locator('.srcfilter button')).to_have_text(['Todas 2', 'Páginas 1', 'Videos 1'])
            expect(page.locator('.srcfilter button span[lang="es-419"]')).to_have_count(3)
            expect(page.locator('.cite')).to_have_attribute('title', 'Fuente S1')
            expect(page.locator('.cite')).to_have_attribute('lang', 'es-419')

    def test_chat_language_refresh_preserves_focus_and_open_disclosures(self):
        self.configure_setup(current=DATA)
        saved_chat = {
            'id': 'saved-chat', 'title': 'Saved chat', 'updated': '2026-11-17T12:00:00Z',
            'messages': [
                {'role': 'user', 'content': 'Question'},
                {'role': 'assistant', 'content': 'Answer from a page.',
                 'cited': [], 'consulted': [{'key': 'S1', 'kind': 'page', 'doc_id': 'manual', 'title': 'Manual'}],
                 'steps': [{'name': 'found', 'count': 1}]},
            ],
        }
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.add_init_script("localStorage.setItem('sg.chats', " + json.dumps(json.dumps([saved_chat])) + ");")
            page.goto(origin + '/#/ask/saved-chat')
            expect(page.locator('details.also')).to_have_count(2)
            expect(page.locator('#chatIn')).to_be_focused()  # wait for the first page's normal autofocus
            page.locator('details.also').first.evaluate('(el) => { el.open = true; }')
            page.locator('#newChat2').focus()
            page.wait_for_timeout(100)  # let any queued initial-focus callback run before testing refresh state
            page.locator('#newChat2').focus()
            self.assertEqual(page.evaluate('document.activeElement.id'), 'newChat2')
            page.evaluate("""() => {
                const current = window.LastbookI18n;
                window.LastbookI18n = Object.freeze({
                    apply: current.apply, resolve: current.resolve, t: current.t,
                    number: current.number, date: current.date, direction: current.direction,
                    get locale() { return 'de'; },
                });
                document.documentElement.lang = 'de';
                document.dispatchEvent(new Event('lastbook:languagechange'));
            }""")
            page.wait_for_timeout(150)
            expect(page.locator('html')).to_have_attribute('lang', 'de')
            expect(page.locator('#newChat2')).to_be_focused()
            self.assertTrue(page.locator('details.also').first.evaluate('(el) => el.open'))

    def test_chat_local_ai_fit_diagnostic_uses_server_catalogue_key(self):
        self.configure_setup(current=DATA)
        self.language_file.write_text('{"language":"es-419"}', encoding='utf-8')
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.route('**/api/assistant/status', lambda route: route.fulfill(
                status=200, content_type='application/json', body=json.dumps({
                    'online': False, 'index': {'state': 'off'},
                    'local': {'state': 'too_big', 'message': 'The local AI needs about 20 GB of this computer’s memory, and it has 8 GB.',
                              'why_key': 'setup.why.aiNeedsMemoryShort',
                              'why_params': {'needs': '20 GB', 'ram': '8 GB'}},
                })))
            page.goto(origin + '/#/ask')
            expect(page.locator('#chatStatus')).to_contain_text(
                'La IA local necesita unos 20 GB de la memoria de esta computadora, y esta tiene 8 GB. Lastbook funciona sin ella: la búsqueda y la lectura son las mismas.')
            self.assertNotIn('The local AI needs about', page.locator('#chatStatus').inner_text())

    def test_single_map_place_uses_singular_translation(self):
        self.configure_setup(current=DATA)
        self.language_file.write_text('{"language":"es-419"}', encoding='utf-8')
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.route('**/api/map/info', lambda route: route.fulfill(
                status=200, content_type='application/json',
                body=json.dumps({'layers': ['hospital'], 'bounds': [-125, 24, -66, 50], 'datasets': []})))
            page.route('**/api/map/pins*', lambda route: route.fulfill(
                status=200, content_type='application/json',
                body=json.dumps({'points': [{'lat': 39, 'lon': -98, 'count': 1, 'cls': 'hospital', 'kinds': {'hospital': 1}}], 'truncated': False})))
            page.route('**/api/map/near*', lambda route: route.fulfill(
                status=200, content_type='application/json', body='{}'))
            page.goto(origin + '/#/map')
            expect(page.locator('#mstatus')).to_have_text('1 lugar a la vista')

    def test_small_pack_summary_uses_the_selected_interface_language(self):
        from engine.setup import manifest as setup_manifest

        bundled = setup_manifest.validate({'version': 1, 'packs': [{
            'id': 'small', 'title': 'Small',
            'summary': 'The essentials: first aid, water, food, shelter and repair, with the maps of this area.',
            'summary_key': 'setup.packSummary.small', 'available': False, 'files': [],
        }], 'models': []})
        self.assertIsNotNone(bundled)
        self.configure_setup(setup_manifest=Manifest(bundled=bundled, remote=None))
        self.language_file.write_text('{"language":"es-419"}', encoding='utf-8')
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.goto(origin + '/ui/setup.html')
            expect(page.locator('[data-pack-summary="small"]')).to_have_text(
                'Lo esencial: primeros auxilios, agua, alimentos, refugio y reparación, con los mapas de esta zona.')

    def test_static_update_notice_is_translated(self):
        self.configure_setup(current=DATA)
        self.language_file.write_text('{"language":"es-419"}', encoding='utf-8')
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.route('**/api/update/notice', lambda route: route.fulfill(
                status=200, content_type='application/json',
                body=json.dumps({'notify': True, 'available': '1.2.0', 'checking': False})))
            page.goto(origin + '/#/guides')
            expect(page.locator('#sideUpdate')).to_be_visible()
            expect(page.locator('#sideUpdate span')).to_have_text('Hay una actualización disponible')

    def test_history_back_translates_encyclopedia_label(self):
        self.configure_setup(current=DATA)
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.route('**/api/library', lambda route: route.fulfill(
                status=200, content_type='application/json',
                body=json.dumps({'zims': ['mdwiki_en_all_maxi_2025-11.zim']})))
            page.route('**/zim/**', lambda route: route.fulfill(status=200, content_type='text/html', body='<html><body>Article</body></html>'))
            article = origin + '/#/wiki/wikipedia_fixture/Some_Article'
            page.goto(article)
            expect(page.locator('.zn')).to_have_text('Wikipedia (text only) ·')
            page.goto(origin + '/ui/setup.html#manage')
            select = page.get_by_label('Interface language')
            expect(select).to_be_visible()
            select.select_option('es-419')
            page.get_by_role('button', name='Save language').click()
            expect(page.get_by_role('status')).to_have_text('Idioma guardado. Reinicia Lastbook para actualizar los menús.')
            page.evaluate('history.back()')
            page.wait_for_url('**/#/wiki/wikipedia_fixture/Some_Article', wait_until='commit')
            expect(page.locator('html')).to_have_attribute('lang', 'es-419')
            expect(page.locator('.zn')).to_have_text('Wikipedia (solo texto) ·')
            page.evaluate("location.hash = '#/encyclopedias'")
            mdwiki = page.locator('#main .cards2 .card').first
            expect(mdwiki.locator('b')).to_have_text('Enciclopedia médica')
            expect(mdwiki.locator('small')).to_have_text(
                'MDWiki: artículos en lenguaje claro sobre enfermedades, medicamentos y primeros auxilios.')
            page.evaluate("location.hash = '#/wiki/mdwiki_fixture/Some_Article'")
            expect(page.locator('.zn')).to_have_text('Enciclopedia médica (MDWiki) ·')

    def test_settings_library_name_is_one_phrase_in_each_language(self):
        """The library card names the pack with one catalogue phrase, never 'Biblioteca biblioteca' or 'Library library'."""
        from engine.setup import manifest as setup_manifest

        cases = [
            ('es-419', 'Small', 'Biblioteca Small'),
            ('en', 'Small', 'Small library'),
            ('es-419', 'Library', 'Library'),
            ('en', 'Medical library', 'Medical library'),
            ('es-419', None, 'Biblioteca'),
            ('en', None, 'Library'),
        ]
        for locale, title, expected in cases:
            with self.subTest(locale=locale, title=title):
                bundled = setup_manifest.validate({'version': 1, 'packs': [{
                    'id': 'small', 'title': title or 'Small', 'summary': 'The essentials.', 'available': True,
                    'installed_bytes': 100, 'files': [{'name': 'small.zip', 'size': 1, 'sha256': '0' * 64,
                                                       'url': 'https://downloads.lastbook.org/small.zip'}]}], 'models': []})
                self.assertIsNotNone(bundled)
                setup = self.configure_setup(current=DATA, setup_manifest=Manifest(bundled=bundled, remote=None))
                info = setup.current_info

                def current_info(info=info, title=title):
                    current = dict(info() or {})
                    current.pop('pack', None)
                    if title:
                        current['pack'] = 'small'
                    return current
                setup.current_info = current_info
                self.language_file.write_text(json.dumps({'language': locale}), encoding='utf-8')
                with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
                    page.goto(origin + '/ui/setup.html#manage')
                    name = page.locator('.s-have .s-row b').first
                    expect(name).to_have_text(expected)
                    self.assertNotRegex(name.inner_text().lower(), r'(library|biblioteca)\W+(library|biblioteca)')

    def test_bfcache_restore_retranslates_cached_guide_descriptions(self):
        self.configure_setup(current=DATA)
        self.language_file.write_text(json.dumps({'language': 'es-419'}), encoding='utf-8')
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.add_init_script("window.bfcacheRestored = false; addEventListener('pageshow', event => { if (event.persisted) window.bfcacheRestored = true })")
            page.goto(origin + '/#/guides')
            expect(page.locator('.need[href="#/t/hurt"] small')).to_have_text(
                'Primeros auxilios para hemorragias, quemaduras, problemas respiratorios, lesiones y enfermedades repentinas')

            page.goto(origin + '/ui/setup.html#manage')
            page.locator('#interfaceLanguage').select_option('en')
            page.locator('#languageSettings button[type="submit"]').click()
            expect(page.locator('#languageStatus')).to_have_text(
                'Language saved. Restart Lastbook to update its menus.')

            page.go_back(wait_until='commit')
            expect(page.locator('.side').get_by_role('link', name='Guides')).to_be_visible()
            self.assertTrue(page.evaluate('window.bfcacheRestored'))
            expect(page.locator('html')).to_have_attribute('lang', 'en')
            expect(page.locator('.need[href="#/t/hurt"] small')).to_have_text(
                'First aid for bleeding, burns, breathing, injuries and sudden illness')

    def test_map_cluster_error_messages_keep_the_resolved_locale(self):
        self.configure_setup(current=DATA)
        info = {'layers': ['hospital'], 'bounds': [-125, 24, -66, 50], 'datasets': [],
                'version': 'test', 'national': None, 'aerial': False, 'contours': False}
        points = {'points': [{'lat': 37.7749, 'lon': -122.4194, 'count': 2, 'kinds': {'hospital': 2},
                              'cls': 'hospital', 'bbox': [-122.421, 37.773, -122.418, 37.776]}], 'truncated': False}
        cases = [
            ('es-419', 'es-419', '2 lugares aquí', 'No se pudo cargar la lista. Acerca el mapa para ver los lugares uno a uno.'),
            ('de', 'en', '2 places here', 'Couldn’t load the list. Zoom in to see individual places.'),
            ('zh-Hans', 'en', '2 places here', 'Couldn’t load the list. Zoom in to see individual places.'),
        ]
        for locale, expected_locale, title, failure in cases:
            with self.subTest(locale=locale):
                self.language_file.write_text(json.dumps({'language': locale}), encoding='utf-8')
                with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
                    page.route('**/api/map/info', lambda route: route.fulfill(
                        status=200, content_type='application/json', body=json.dumps(info)))
                    page.route('**/api/map/pins*', lambda route: route.fulfill(
                        status=200, content_type='application/json', body=json.dumps(points)))
                    page.route('**/api/map/near*', lambda route: route.fulfill(
                        status=200, content_type='application/json', body='[]'))
                    page.route('**/api/map/members*', lambda route: route.fulfill(
                        status=503, content_type='application/json', body='not-json'))
                    pin_requests = []
                    page.on('request', lambda request: pin_requests.append(request.url)
                            if '/api/map/pins?' in request.url else None)
                    page.goto(origin + '/#/map?lat=37.7749&lon=-122.4194&z=17&layers=hospital')
                    expect(page.locator('html')).to_have_attribute('lang', locale)
                    page.wait_for_load_state('networkidle')
                    expect(page.locator('#mstatus')).to_contain_text('2')
                    canvas = page.locator('#mapc')
                    box = canvas.bounding_box()
                    with page.expect_response(lambda response: '/api/map/members?' in response.url):
                        page.mouse.click(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
                    heading = page.locator('#card h3 span')
                    expect(heading).to_have_text(title)
                    expect(heading).to_have_attribute('lang', expected_locale)
                    failure_copy = page.locator('#card p span')
                    expect(failure_copy).to_have_text(failure)
                    expect(failure_copy).to_have_attribute('lang', expected_locale)

    def test_server_keyed_library_and_map_labels_follow_a_live_language_switch(self):
        self.configure_setup(current=DATA)
        self.language_file.write_text('{"language":"es-419"}', encoding='utf-8')
        engine_hook = """(() => {
          let factory;
          Object.defineProperty(window, 'createI18n', {
            configurable: true,
            get: () => factory,
            set: value => { factory = (...args) => { const engine = value(...args); window.__testI18nEngine = engine; return engine; }; }
          });
        })();"""
        switch = """(locale) => {
          const engine = window.__testI18nEngine;
          engine.usePreferredLocales(locale);
          document.documentElement.lang = engine.locale;
          LastbookI18n.apply();
          document.dispatchEvent(new Event('lastbook:languagechange'));
        }"""
        shelves = [{'id': 'health', 'titleKey': 'library.shelf.health', 'title': 'Health & first aid', 'read': 2, 'video': 0},
                   {'id': 'water', 'titleKey': 'library.shelf.water', 'title': 'Water & sanitation', 'read': 1, 'video': 0}]
        info = {'layers': [], 'bounds': [-125, 24, -66, 50], 'datasets': [
            {'labelKey': 'map.data.baseMap', 'labelParams': None, 'label': 'Main roads, towns and water for the whole US (OpenStreetMap, USGS)',
             'statusKey': 'map.data.areaDownloading', 'statusParams': {'area': 'California'}, 'status': 'California · downloading'}]}
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.add_init_script(engine_hook)
            page.route('**/api/shelves*', lambda route: route.fulfill(
                status=200, content_type='application/json', body=json.dumps(shelves)))
            page.goto(origin + '/#/library')
            rows = page.locator('#shelves .shelfrow b')
            expect(rows).to_have_text(['Salud y primeros auxilios', 'Agua y saneamiento'])
            expect(rows.first.locator('[lang="es-419"]')).to_have_count(1)

            page.route('**/api/map/info', lambda route: route.fulfill(
                status=200, content_type='application/json', body=json.dumps(info)))
            page.route('**/api/map/pins*', lambda route: route.fulfill(
                status=200, content_type='application/json', body=json.dumps({'points': [], 'truncated': False})))
            page.route('**/api/map/near*', lambda route: route.fulfill(
                status=200, content_type='application/json', body='[]'))
            page.evaluate("location.hash = '#/map'")
            data = page.locator('#mdata li').first
            expect(data).to_contain_text('Carreteras principales, pueblos y agua de todo EE. UU.')
            expect(data).to_contain_text('California · descargando')
            page.evaluate(switch, 'en')
            expect(data).to_contain_text('Main roads, towns and water for the whole US')
            expect(data).to_contain_text('California · downloading')
            page.evaluate("location.hash = '#/library'")
            expect(rows).to_have_text(['Health & first aid', 'Water & sanitation'])

    def test_map_panels_use_the_selected_interface_language(self):
        self.configure_setup(current=DATA)
        self.language_file.write_text('{"language":"es-419"}', encoding='utf-8')
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.goto(origin + '/#/map')
            expect(page.locator('.maptools h2')).to_have_text([
                'Más cercanos al centro del mapa', 'Tu zona', 'Cobertura de este mapa'])
            expect(page.locator('.maptools section.panel:nth-of-type(1) p')).to_have_text(
                'Según las capas activadas. Distancia en línea recta, no por carretera.')
            expect(page.locator('.maptools section.panel:nth-of-type(2) p')).to_have_text(
                'El botón de inicio vuelve aquí. Se guarda solo en este dispositivo.')
            expect(page.locator('#sethome')).to_have_text('Usar el centro del mapa como mi zona')

    def test_map_fallback_labels_are_tagged_as_english(self):
        self.configure_setup(current=DATA)
        self.language_file.write_text('{"language":"de"}', encoding='utf-8')
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.goto(origin + '/#/map')
            page.locator('#layers-btn').click()
            expect(page.locator('.presets button span[lang="en"]').first).to_be_visible()
            expect(page.locator('#layers fieldset legend span[lang="en"]').first).to_be_visible()

    def test_chat_guide_label_uses_the_selected_interface_language(self):
        self.configure_setup(current=DATA)
        self.language_file.write_text('{"language":"es-419"}', encoding='utf-8')
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.goto(origin + '/#/ask')
            expect(page.locator('.ask-learn small')).to_have_text(['Guía paso a paso'] * 3)

    def test_selected_interface_language_formats_chat_and_note_dates(self):
        self.configure_setup(current=DATA)
        self.language_file.write_text('{"language":"es-419"}', encoding='utf-8')
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.add_init_script("localStorage.setItem('sg.chats', JSON.stringify([{id:'old', title:'Saved chat', updated:'2026-11-17T12:00:00Z', messages:[{role:'user',content:'Question'}]}]))")
            page.goto(origin + '/#/ask')
            expect(page.locator('#csList li a small').first).to_contain_text('17 nov')
            page.route('**/api/not-found', lambda route: route.fulfill(
                status=200, content_type='application/json',
                body=json.dumps({'notes': [{'id': 'note-1', 'words': 'water filter', 'at': '2026-11-17', 'guide': None}]})))
            page.goto(origin + '/#/not-found')
            expect(page.locator('.row.nf small')).to_contain_text('17 de noviembre de 2026')

    def test_search_results_arriving_after_route_change_do_not_touch_old_dom(self):
        self.configure_setup(current=DATA)
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.add_init_script(r"""window.auditSearchRequests = [];
                window.auditSearchCompleted = 0;
                const realFetch = window.fetch.bind(window);
                window.fetch = (resource, init) => {
                    const url = typeof resource === 'string' ? resource : resource.url;
                    if (url.includes('/api/find?') || url.includes('/api/retrieve?')) {
                        window.auditSearchRequests.push(url);
                        return new Promise((resolve, reject) => setTimeout(
                            () => realFetch(resource, init).then(response => {
                                window.auditSearchCompleted++;
                                resolve(response);
                            }, error => {
                                window.auditSearchCompleted++;
                                reject(error);
                            }), 500));
                    }
                    return realFetch(resource, init);
                };""")
            page_errors = []
            page.on('pageerror', lambda error: page_errors.append(str(error)))
            page.goto(origin + '/#/guides')
            expect(page.locator('h1')).to_have_text('What do you need?')
            page.evaluate("location.hash = '#/search?q=zzqzxqwv'")
            page.wait_for_function('window.auditSearchRequests.length >= 2')
            page.evaluate("location.hash = '#/guides'")
            expect(page.locator('h1')).to_have_text('What do you need?')
            page.wait_for_function('window.auditSearchCompleted === window.auditSearchRequests.length')
            expect(page.locator('#main .results')).to_have_count(0)
            expect(page.locator('#main .result')).to_have_count(0)
            self.assertEqual(page_errors, [])

    def test_english_no_results_fallback_is_tagged(self):
        self.configure_setup(current=DATA)
        self.language_file.write_text('{"language":"de"}', encoding='utf-8')
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.route('**/api/find*', lambda route: route.fulfill(
                status=200, content_type='application/json',
                body=json.dumps({'results': [], 'expanded': [], 'mode': 'all'})))
            page.route('**/api/retrieve*', lambda route: route.fulfill(
                status=200, content_type='application/json', body=json.dumps({'results': []})))
            page.goto(origin + '/#/search?q=zzqzxqwv')
            expect(page.locator('.empty b span[lang="en"]')).to_have_text('No results for “zzqzxqwv”')
            expect(page.locator('.empty p span[lang="en"]')).to_have_text(
                'Try fewer words, or another word for the same thing.')

    def test_topic_card_fallbacks_are_tagged_as_english(self):
        self.configure_setup(current=DATA)
        self.language_file.write_text('{"language":"de"}', encoding='utf-8')
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.goto(origin + '/#/guides')
            expect(page.locator('.need[href="#/t/hurt"] b span[lang="en"]')).to_have_text('Injury & illness')
            expect(page.locator('.need[href="#/t/hurt"] small span[lang="en"]')).to_have_text(
                'First aid for bleeding, burns, breathing, injuries and sudden illness')

    def test_video_speed_copy_uses_the_selected_catalogue_language(self):
        self.configure_setup(current=DATA)
        self.language_file.write_text('{"language":"de"}', encoding='utf-8')
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.goto(origin + '/#/watch/vida')
            expect(page.locator('.video-speed label span[lang="de"]')).to_have_text('Wiedergabegeschwindigkeit')
            expect(page.locator('#videoSpeed option[value="1"]')).to_have_attribute('lang', 'de')
            expect(page.locator('#videoSpeed option[value="1"]')).to_have_text('Normal')

    def test_video_category_and_note_copy_is_translated_and_language_tagged(self):
        self.configure_setup(current=DATA)
        self.language_file.write_text('{"language":"es-419"}', encoding='utf-8')
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.route('**/api/videos', lambda route: route.fulfill(
                status=200, content_type='application/json', body=json.dumps([
                    {'id': 'health', 'title': 'First aid & health', 'note': None, 'count': 1, 'items': []},
                    {'id': 'coalcracker', 'title': 'Coalcracker Bushcraft', 'note': 'Hobbyist channel', 'count': 1, 'items': []},
                ])))
            page.goto(origin + '/#/videos')
            expect(page.locator('#vrows .sec-head h2 span[lang="es-419"]')).to_have_text(
                ['Salud y primeros auxilios', 'Coalcracker Bushcraft'])
            expect(page.locator('#vrows .sec-head .sub span[lang="es-419"]')).to_have_text('Canal de aficionados')

    def test_early_saved_language_hint_updates_meta_description(self):
        self.configure_setup(current=DATA)
        self.language_file.write_text('{"language":"es-419"}', encoding='utf-8')
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.goto(origin + '/#/guides')
            page.evaluate("localStorage.setItem('lastbook.ui-language', 'es-419')")
            page.reload()
            expect(page.locator('meta[name="description"]')).to_have_attribute(
                'content', 'Guía de supervivencia y reconstrucción sin conexión: primeros auxilios, agua, alimentos, energía, refugio, videos, mapas y habilidades.')

    def test_preference_loading_guards_submit_on_success_and_failure(self):
        self.configure_setup()
        for fails in (False, True):
            with self.subTest(fails=fails), serve(server.setup_api.SetupServer, self.language_file) as (origin, http):
                with self.page(origin, http) as page, delay_language_reply(http, 'GET') as (arrived, release):
                    if fails:
                        with patch.object(bridge.ui_language, '_load', side_effect=PermissionError):
                            page.goto(origin)
                            self.assertTrue(arrived.wait(5))
                    else:
                        page.goto(origin)
                        self.assertTrue(arrived.wait(5))
                    posts = []
                    page.on('request', lambda r: posts.append(r) if r.method == 'POST' and r.url.endswith(ROUTE) else None)
                    expect(page.locator('#languageSettings')).to_be_hidden()
                    page.eval_on_selector('#languageSettings', """form => {
                        form.querySelector('select').value = 'es-419';
                        form.requestSubmit();
                    }""")
                    expect(page.locator('h1')).to_have_text('Set up Lastbook')
                    if fails:
                        expect(page.locator('#languageStatus')).to_be_empty()
                    release.set()
                    expect(page.get_by_label('Interface language')).to_have_value('en')
                    if fails:
                        expect(page.get_by_role('status')).to_have_text('Could not load the saved language.')
                    self.assertEqual(posts, [])
                    self.assertFalse(self.language_file.exists())
                    page.get_by_label('Interface language').select_option('es-419')
                    page.get_by_role('button', name='Save language').press('Enter')
                    expect(page.get_by_role('status')).to_have_text('Idioma guardado. Reinicia Lastbook para actualizar los menús.')
                self.language_file.unlink()

    def test_library_ignores_an_old_get_after_a_save_and_route_change(self):
        self.configure_setup(current=DATA)
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as library:
            library.add_init_script("""window.languageReads = 0;
                const readJSON = Response.prototype.json;
                Response.prototype.json = async function () {
                    const data = await readJSON.call(this);
                    if (this.url.endsWith('/api/ui-language')) setTimeout(() => window.languageReads++, 0);
                    return data;
                };""")
            with delay_language_reply(http, 'GET') as (arrived, release):
                library.goto(origin + '/#/guides')
                self.assertTrue(arrived.wait(5))
                with self.page(origin, http) as settings:
                    settings.goto(origin + '/ui/setup.html#manage')
                    settings.get_by_label('Interface language').select_option('es-419')
                    settings.get_by_role('button', name='Save language').click()
                    expect(settings.get_by_role('status')).to_have_text('Idioma guardado. Reinicia Lastbook para actualizar los menús.')
                library.evaluate("""() => {
                    location.hash = '#/search';
                    dispatchEvent(new PageTransitionEvent('pageshow', {persisted: true}));
                }""")
                expect(library.locator('.side').get_by_role('link', name='Guías')).to_be_visible()
                search = library.get_by_role('searchbox', name='Buscar en la biblioteca')
                search.focus()
                release.set()
                library.wait_for_function('window.languageReads === 2')
                expect(search).to_be_focused()
                expect(library.locator('.side').get_by_role('link', name='Guías')).to_be_visible()

    def test_delayed_save_replies_from_two_windows_preserve_the_last_commit(self):
        self.configure_setup()
        for fails in (False, True):
            with self.subTest(fails=fails), serve(server.setup_api.SetupServer, self.language_file) as (origin, http):
                with self.page(origin, http) as first, self.page(origin, http) as second:
                    first.goto(origin)
                    second.goto(origin)
                    first_posts = []
                    first.on('request', lambda r: first_posts.append(r) if r.method == 'POST' and r.url.endswith(ROUTE) else None)
                    first.get_by_label('Interface language').select_option('es-419')
                    expect(second.get_by_label('Interface language')).to_have_value('en')
                    with delay_language_reply(http, 'POST') as (arrived, release):
                        if fails:
                            with patch.object(bridge.ui_language.os, 'replace', side_effect=PermissionError):
                                first.get_by_role('button', name='Save language').click()
                                self.assertTrue(arrived.wait(5))
                        else:
                            first.get_by_role('button', name='Save language').click()
                            self.assertTrue(arrived.wait(5))
                        expect(first.get_by_role('status')).to_have_text('Saving language…')
                        first.get_by_label('Interface language').select_option('en')
                        first.eval_on_selector('#languageSettings', 'form => form.requestSubmit()')
                        second.get_by_role('button', name='Save language').click()
                        expect(second.get_by_role('status')).to_have_text('Language saved. Restart Lastbook to update its menus.')
                        release.set()
                        expected = 'Could not save the language. Try again.' if fails else 'Idioma guardado. Reinicia Lastbook para actualizar los menús.'
                        expect(first.get_by_role('status')).to_have_text(expected)
                        expect(second.get_by_role('status')).to_have_text('Language saved. Restart Lastbook to update its menus.')
                        self.assertEqual(len(first_posts), 1)
                        self.assertEqual(json.loads(self.language_file.read_bytes()), {'language': 'en'})
                with self.page(origin, http, 'es-UY') as restarted:
                    restarted.goto(origin)
                    expect(restarted.get_by_label('Interface language')).to_have_value('en')
                self.language_file.unlink()

    def test_failures_are_visible_and_never_replace_the_saved_preference(self):
        self.configure_setup()
        self.language_file.mkdir()  # replacing a directory with the preference file fails at the filesystem
        with serve(server.setup_api.SetupServer, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.goto(origin)
            page.get_by_label('Interface language').select_option('es-419')
            page.get_by_role('button', name='Save language').click()
            expect(page.get_by_role('status')).to_have_text('Could not save the language. Try again.')
            expect(page.get_by_label('Interface language')).to_have_value('en')
            expect(page.locator('h1')).to_have_text('Set up Lastbook')
            self.assertTrue(self.language_file.is_dir())
            self.language_file.rmdir()
            self.language_file.write_text('{"language":"es-419"}', encoding='utf-8')
            written = self.language_file.read_bytes()
            # Simulate a broken Spanish asset while still loading the real UI and English catalogue.
            page.route('**/i18n-locales.js*', lambda route: route.fulfill(
                status=200, content_type='text/javascript', body='window.lastbookI18nLocales = {"es-419":{"invalid":"bad"}};'))
            page.reload()
            expect(page.get_by_role('status')).to_have_text('The saved language is unavailable. Lastbook is using English.')
            expect(page.get_by_label('Interface language')).to_have_value('es-419')
            self.assertEqual(self.language_file.read_bytes(), written)
            page.unroute('**/i18n-locales.js*')
            page.reload()
            expect(page.locator('h1')).to_have_text('Configuración inicial de Lastbook')
            self.assertEqual(self.language_file.read_bytes(), written)
            invalid = b'{"language":"en","language":"es-419"}'
            self.language_file.write_bytes(invalid)
            page.reload()
            expect(page.get_by_label('Interface language')).to_have_value('en')
            expect(page.locator('h1')).to_have_text('Set up Lastbook')
            self.assertEqual(self.language_file.read_bytes(), invalid)

    def test_desktop_requires_opt_in_even_with_spanish_or_invalid_browser_locales(self):
        self.configure_setup(current=DATA)
        with serve(server, self.language_file) as (origin, http):
            for locale in ('en-US', 'es-UY', 'es-AR', 'es-CL', 'es-ES', 'fr-FR', 'malformed_tag'):
                with self.subTest(locale=locale), self.page(origin, http) as page:
                    page.add_init_script(f"Object.defineProperty(navigator, 'languages', {{value: [{json.dumps(locale)}]}})")
                    page.goto(origin + '/ui/setup.html#manage')
                    expect(page.get_by_label('Interface language')).to_have_value('en')
                    self.assertFalse(self.language_file.exists())
            self.language_file.write_text('{"language":"es-419"}', encoding='utf-8')
            with self.page(origin, http, 'fr-FR') as page:
                page.goto(origin + '/ui/setup.html#manage')
                expect(page.get_by_label('Idioma de la interfaz')).to_have_value('es-419')
                expect(page.locator('h1')).to_have_text('Biblioteca e IA local')

    def test_remembered_language_shows_before_the_bridge_replies_and_the_file_wins(self):
        self.configure_setup(current=DATA)
        self.language_file.write_text('{"language":"es-419"}', encoding='utf-8')
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.goto(origin + '/#/guides')
            expect(page.locator('.side').get_by_role('link', name='Guías')).to_be_visible()
            # Next page load: the GET is held, yet the sidebar is already Spanish (no English flash).
            with delay_language_reply(http, 'GET') as (arrived, release):
                page.reload(wait_until='commit')
                self.assertTrue(arrived.wait(5))
                expect(page.locator('.side').get_by_role('link', name='Guías')).to_be_visible()
                release.set()
            # The file is the truth: a change made elsewhere replaces the remembered language once read.
            self.language_file.write_text('{"language":"en"}', encoding='utf-8')
            with delay_language_reply(http, 'GET') as (arrived, release):
                page.reload(wait_until='commit')
                self.assertTrue(arrived.wait(5))
                expect(page.locator('.side').get_by_role('link', name='Guías')).to_be_visible()
                release.set()
            expect(page.locator('.side').get_by_role('link', name='Guides')).to_be_visible()
            with delay_language_reply(http, 'GET') as (arrived, release):
                page.reload(wait_until='commit')
                self.assertTrue(arrived.wait(5))
                expect(page.locator('.side').get_by_role('link', name='Guides')).to_be_visible()
                release.set()
        # A profile with nothing remembered starts in English, whatever the browser locale says.
        with serve(server, self.language_file) as (origin, http), self.page(origin, http, locale='es-AR') as page:
            with delay_language_reply(http, 'GET') as (arrived, release):
                page.goto(origin + '/#/guides', wait_until='commit')
                self.assertTrue(arrived.wait(5))
                expect(page.locator('.side').get_by_role('link', name='Guides')).to_be_visible()
                release.set()

    def test_a_remembered_value_that_is_not_a_supported_language_is_ignored(self):
        self.configure_setup(current=DATA)
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.add_init_script("localStorage.setItem('lastbook.ui-language', 'fr')")
            with delay_language_reply(http, 'GET') as (arrived, release):
                page.goto(origin + '/#/guides', wait_until='commit')
                self.assertTrue(arrived.wait(5))
                expect(page.locator('.side').get_by_role('link', name='Guides')).to_be_visible()
                release.set()

    def test_a_hung_read_or_save_times_out_and_the_selector_recovers(self):
        self.configure_setup()
        with serve(server.setup_api.SetupServer, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.clock.install()
            with delay_language_reply(http, 'GET') as (arrived, release):
                page.goto(origin)
                self.assertTrue(arrived.wait(5))
                expect(page.locator('#languageSettings')).to_be_hidden()
                page.clock.fast_forward(9000)  # past the read timeout
                expect(page.locator('#languageSettings')).to_be_visible()
                expect(page.get_by_role('status')).to_have_text('Could not load the saved language.')
                expect(page.get_by_label('Interface language')).to_have_value('en')
                release.set()
            with delay_language_reply(http, 'POST') as (arrived, release):
                page.get_by_label('Interface language').select_option('es-419')
                page.get_by_role('button', name='Save language').click()
                self.assertTrue(arrived.wait(5))
                expect(page.get_by_role('status')).to_have_text('Saving language…')
                expect(page.get_by_role('button', name='Save language')).to_have_attribute('aria-disabled', 'true')
                page.clock.fast_forward(16000)  # past the save timeout
                expect(page.get_by_role('status')).to_have_text('Could not save the language. Try again.')
                expect(page.get_by_role('button', name='Save language')).not_to_have_attribute('aria-disabled', 'true')
                expect(page.get_by_label('Interface language')).to_have_value('en')
                release.set()
            page.get_by_label('Interface language').select_option('es-419')
            page.get_by_role('button', name='Save language').click()
            expect(page.get_by_role('status')).to_have_text('Idioma guardado. Reinicia Lastbook para actualizar los menús.')

    def test_label_helpers_accept_plain_strings_and_pairs(self):
        self.configure_setup(current=DATA)
        self.language_file.write_text('{"language":"es-419"}', encoding='utf-8')
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.goto(origin + '/#/guides')
            expect(page.locator('.side').get_by_role('link', name='Guías')).to_be_visible()
            html = page.evaluate("""() => [
                backButton('#/videos', 'Videos'), backButton('#/library', ['nav.library', 'Library']), backButton('#/x', 'Custom label'),
                backButton('#/x', ['nav.back', 'Back']), backButton('#/x'),
                searchBox('a', '', 'p', 'Filter'), searchBox('b', '', 'p', ['search.go', 'Go']), searchBox('c', '', 'p', 'Other'), searchBox('d', '', 'p'),
            ]""")
            def parse(markup):
                return page.evaluate("""(markup) => {
                    const box = document.createElement('div');
                    box.innerHTML = markup;
                    window.LastbookI18n.apply(box);
                    const target = box.querySelector('a[data-back] span, form button');
                    return [target.textContent, target.getAttribute('data-i18n')];
                }""", markup)
            self.assertEqual([parse(m) for m in html], [
                ['Videos', 'nav.videos'], ['Biblioteca', 'nav.library'], ['Custom label', None],
                ['Atrás', 'nav.back'], ['Atrás', 'nav.back'],
                ['Filtrar', 'search.filter'], ['Ir', 'search.go'], ['Other', None], ['Buscar', 'search.label'],
            ])
            self.assertNotIn('data-i18n="null"', ''.join(html))
            self.assertNotIn('data-i18n="undefined"', ''.join(html))

    def test_navigation_helpers_keep_their_labels_and_local_back_target(self):
        self.configure_setup(current=DATA)
        self.language_file.write_text('{"language":"es-419"}', encoding='utf-8')
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.goto(origin + '/#/videos/all')
            expect(page.get_by_role('button', name='Ir', exact=True)).to_be_visible()
            page.locator('#vq').fill('water')
            page.get_by_role('button', name='Ir', exact=True).click()
            page.wait_for_url('**/#/videos/all?*q=water*')
            page.evaluate("(id) => location.hash = '#/shelf/' + id", server.SHELVES[0][0])
            expect(page.get_by_role('button', name='Filtrar', exact=True)).to_be_visible()
            expect(page.locator('a[data-back]')).to_have_text('Biblioteca')
            page.evaluate("(from) => location.hash = '#/watch/vida?from=' + encodeURIComponent(from)", 'javascript:void(0)')
            expect(page.locator('a[data-back]')).to_have_attribute('href', '#/')
            page.evaluate("location.hash = '#/watch/vida?from=%23guides'")
            back = page.locator('a[data-back]')
            expect(back).to_have_attribute('href', '#guides')
            page.set_viewport_size({'width': 390, 'height': 780})
            back.click()
            page.wait_for_url('**/#guides')
            expect(page.locator('h1')).to_have_text('¿Qué necesitas?')

    def test_local_http_has_no_preference_route_and_keeps_its_shell_offline(self):
        self.configure_setup(current=DATA)
        with serve() as (origin, http):
            connection = HTTPConnection('127.0.0.1', http.server_port, timeout=5)
            try:
                for method in ('GET', 'HEAD', 'POST'):
                    connection.request(method, ROUTE, '{"language":"es-419"}' if method == 'POST' else None,
                                       {'Content-Type': 'application/json', bridge.KEY_HEADER: 'not-a-native-key'})
                    response = connection.getresponse()
                    self.assertEqual(response.status, 404)
                    response.read()
            finally:
                connection.close()
            self.assertFalse(self.language_file.exists())
            for locale in ('en-US', 'es-UY', 'es-AR', 'es-CL', 'es-ES', 'fr-FR'):
                with self.page(origin, http, locale) as page:
                    page.goto(origin + '/#/guides')
                    guides = page.locator('.side').get_by_role('link', name='Guides')
                    expect(guides).to_be_visible()
                    expect(page.locator('#sideSettings')).to_be_hidden()
                    page.wait_for_function('!!navigator.serviceWorker.controller')
                    if locale == 'es-CL':
                        self.assertFalse(page.evaluate("async () => !!await caches.match('/api/ui-language')"))
                        page.context.set_offline(True)
                        page.reload(wait_until='domcontentloaded')
                        expect(guides).to_be_visible()
                        self.assertTrue(page.evaluate('!!window.LastbookI18n'))


    def test_gps_marker_card_retranslates_after_language_change(self):
        self.configure_setup(current=DATA)
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.add_init_script("Object.defineProperty(window, 'isSecureContext', {configurable: true, value: true}); Object.defineProperty(navigator, 'geolocation', {configurable: true, value: {getCurrentPosition: ok => ok({coords: {latitude: 37.7749, longitude: -122.4194}})}})")
            page.add_init_script("""(() => {
              let factory;
              Object.defineProperty(window, 'createI18n', {
                configurable: true,
                get: () => factory,
                set: value => { factory = (...args) => { const engine = value(...args); window.__testI18nEngine = engine; return engine; }; }
              });
            })();""")
            page.route('**/api/map/info', lambda route: route.fulfill(
                status=200, content_type='application/json',
                body=json.dumps({'layers': [], 'bounds': [-125, 24, -66, 50], 'datasets': []})))
            page.route('**/api/map/pins*', lambda route: route.fulfill(
                status=200, content_type='application/json', body=json.dumps({'points': [], 'truncated': False})))
            page.route('**/api/map/near*', lambda route: route.fulfill(
                status=200, content_type='application/json', body='[]'))
            page.goto(origin + '/#/map')
            page.locator('#gps').click()
            canvas = page.locator('#mapc')
            box = canvas.bounding_box()
            page.mouse.click(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2 - 18)
            expect(page.locator('#card h3')).to_have_text('You are here (approx.)')
            page.evaluate("""() => {
              const engine = window.__testI18nEngine;
              engine.usePreferredLocales('es-419');
              document.documentElement.lang = engine.locale;
              LastbookI18n.apply();
              document.dispatchEvent(new Event('lastbook:languagechange'));
            }""")
            expect(page.locator('#card h3 span[lang="es-419"]')).to_have_text('Estás aquí (aprox.)')

    def test_linked_map_pin_kind_retranslates_after_language_change(self):
        self.configure_setup(current=DATA)
        self.language_file.write_text('{"language":"es-419"}', encoding='utf-8')
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.add_init_script("""(() => {
              let factory;
              Object.defineProperty(window, 'createI18n', {
                configurable: true,
                get: () => factory,
                set: value => { factory = (...args) => { const engine = value(...args); window.__testI18nEngine = engine; return engine; }; }
              });
            })();""")
            page.route('**/api/map/info', lambda route: route.fulfill(
                status=200, content_type='application/json',
                body=json.dumps({'layers': [], 'bounds': [-125, 24, -66, 50], 'datasets': []})))
            page.route('**/api/map/pins*', lambda route: route.fulfill(
                status=200, content_type='application/json', body=json.dumps({'points': [], 'truncated': False})))
            page.route('**/api/map/near*', lambda route: route.fulfill(
                status=200, content_type='application/json', body='[]'))
            page.goto(origin + '/#/map?lat=37.7749&lon=-122.4194&z=15&pin=Test')
            canvas = page.locator('#mapc')
            box = canvas.bounding_box()
            page.mouse.click(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2 - 18)
            expect(page.locator('#card .kind span[lang="es-419"]')).to_have_text('Lugar vinculado')
            page.evaluate("""() => {
              const engine = window.__testI18nEngine;
              engine.usePreferredLocales('en');
              document.documentElement.lang = engine.locale;
              LastbookI18n.apply();
              document.dispatchEvent(new Event('lastbook:languagechange'));
            }""")
            expect(page.locator('#card .kind span[lang="en"]')).to_have_text('Linked place')

    def test_saved_chat_errors_and_stopped_answers_retranslate(self):
        self.configure_setup(current=DATA)
        self.language_file.write_text('{"language":"es-419"}', encoding='utf-8')
        stopped_spanish = 'Se detuvo.'
        chat = {'id': 'saved-locale-chat', 'title': 'Question', 'updated': '2026-11-25T12:00:00Z', 'messages': [
            {'role': 'user', 'content': 'Question'},
            {'role': 'assistant', 'content': '', 'error': 'La IA local necesita aproximadamente 20 GB de memoria.'},
            {'role': 'user', 'content': 'Question two'},
            {'role': 'assistant', 'content': 'Respuesta parcial.\n\n(' + stopped_spanish + ')', 'stopped': True, 'sources': []},
        ]}
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.add_init_script("localStorage.setItem('sg.chats', " + json.dumps(json.dumps([chat])) + ");")
            page.add_init_script("""(() => {
              let factory;
              Object.defineProperty(window, 'createI18n', {
                configurable: true,
                get: () => factory,
                set: value => { factory = (...args) => { const engine = value(...args); window.__testI18nEngine = engine; return engine; }; }
              });
            })();""")
            page.goto(origin + '/#/ask/saved-locale-chat')
            expect(page.locator('#m1 .ans-error b span[lang="es-419"]')).to_have_text('La IA local necesita aproximadamente 20 GB de memoria.')
            expect(page.locator('#m3 .answer')).to_have_text('Respuesta parcial.')
            expect(page.locator('#m3 .answer')).not_to_contain_text(stopped_spanish)
            expect(page.locator('#m3 .ans-stopped span[lang="es-419"]')).to_have_text(stopped_spanish)
            page.evaluate("""() => {
              const engine = window.__testI18nEngine;
              engine.usePreferredLocales('en');
              document.documentElement.lang = engine.locale;
              LastbookI18n.apply();
              document.dispatchEvent(new Event('lastbook:languagechange'));
            }""")
            expect(page.locator('#m1 .ans-error b span[lang="en"]')).to_have_text('The local AI needs about 20 GB of memory.')
            expect(page.locator('#m3 .ans-stopped span[lang="en"]')).to_have_text('Stopped.')
            self.assertEqual(page.locator('#chatSide').get_attribute('lang'), 'en')
            with page.expect_download() as english_export:
                page.get_by_role('button', name='Export chat').click()
            english_markdown = Path(english_export.value.path()).read_text(encoding='utf-8')
            self.assertIn('Chat: Question', english_markdown)
            self.assertIn('The local AI needs about 20 GB of memory.', english_markdown)
            self.assertIn('## Question', english_markdown)
            self.assertIn('## Answer', english_markdown)
            page.evaluate("""() => {
              const engine = window.__testI18nEngine;
              engine.usePreferredLocales('es-419');
              document.documentElement.lang = engine.locale;
              LastbookI18n.apply();
              document.dispatchEvent(new Event('lastbook:languagechange'));
            }""")
            expect(page.locator('#m1 .ans-error b span[lang="es-419"]')).to_have_text('La IA local necesita aproximadamente 20 GB de memoria.')
            with page.expect_download() as exported:
                page.get_by_role('button', name='Exportar chat').click()
            markdown = Path(exported.value.path()).read_text(encoding='utf-8')
            self.assertIn('Respuesta parcial.\n\n(Se detuvo.)', markdown)
            self.assertNotIn('Respuesta parcial.\n\n(Stopped.)', markdown)

    def test_setup_error_fallback_copy_is_tagged_english(self):
        self.language_file.write_text('{"language":"de"}', encoding='utf-8')
        state = {'mode': 'setup', 'current': None, 'hardware': {'disks': []}, 'job': {
            'state': 'failed', 'error': {'code': 'unreachable', 'host': 'download.example'},
            'items': [], 'folder': str(DATA), 'repair': False,
        }}
        with serve(server.setup_api.SetupServer, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.route('**/api/setup/state', lambda route: route.fulfill(
                status=200, content_type='application/json', body=json.dumps(state)))
            page.route('**/api/setup/updates', lambda route: route.fulfill(
                status=200, content_type='application/json', body=json.dumps({'supported': False})))
            page.goto(origin + '/ui/setup.html')
            expect(page.locator('.s-err b span[lang="en"]')).to_have_text('Lastbook can’t reach download.example.')
            expect(page.locator('.s-err > div > p > span[lang="en"]').first).to_contain_text('It may be down for a while')
            expect(page.locator('.s-err button[data-act="retry"] span[lang="de"]')).to_have_text('Erneut versuchen')

    def test_setup_api_error_keeps_its_key_when_the_language_changes(self):
        self.configure_setup()
        self.language_file.write_text('{"language":"de"}', encoding='utf-8')
        with serve(server.setup_api.SetupServer, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.add_init_script("""(() => {
              let factory;
              Object.defineProperty(window, 'createI18n', {
                configurable: true,
                get: () => factory,
                set: value => { factory = (...args) => { const engine = value(...args); window.__testI18nEngine = engine; return engine; }; }
              });
            })();""")
            page.route('**/api/setup/server-models', lambda route: route.abort())
            page.goto(origin)
            page.locator('#srvOpen').click()
            page.locator('#srvAddr').fill('127.0.0.1:11434')
            page.locator('#srvList').click()
            expect(page.locator('#srvNote span[lang="en"]')).to_have_text(
                'Lastbook did not answer. Close it and open it again.')
            page.evaluate("""() => {
              const engine = window.__testI18nEngine;
              engine.usePreferredLocales('es-419');
              document.documentElement.lang = engine.locale;
              LastbookI18n.apply();
              document.dispatchEvent(new Event('lastbook:languagechange'));
            }""")
            expect(page.locator('#srvNote span[lang="es-419"]')).to_have_text(
                'Lastbook no respondió. Ciérralo y ábrelo de nuevo.')

    def test_setup_keyed_unpack_error_has_resolved_language(self):
        self.language_file.write_text('{"language":"es-419"}', encoding='utf-8')
        state = {'mode': 'setup', 'current': None, 'hardware': {'disks': []}, 'job': {
            'state': 'failed', 'error': {'code': 'unpack', 'key': 'setup.err.cannotPlaceMap',
                                        'params': {'error': 'Permission denied'}},
            'items': [{'id': 'map', 'kind': 'map', 'state': 'failed', 'error': {
                'code': 'unpack', 'key': 'setup.err.cannotPlaceMap', 'params': {'error': 'Permission denied'}}}],
            'folder': str(DATA), 'repair': False,
        }}
        with serve(server.setup_api.SetupServer, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.route('**/api/setup/state', lambda route: route.fulfill(
                status=200, content_type='application/json', body=json.dumps(state)))
            page.route('**/api/setup/updates', lambda route: route.fulfill(
                status=200, content_type='application/json', body=json.dumps({'supported': False})))
            page.goto(origin + '/ui/setup.html')
            headline = page.locator('.s-err b span')
            expect(headline).to_contain_text('Lastbook no pudo poner el mapa nuevo en su lugar')
            self.assertEqual(headline.get_attribute('lang'), 'es-419')

    def test_saved_video_moment_draft_survives_language_change(self):
        self.configure_setup(current=DATA)
        self.language_file.write_text('{"language":"en"}', encoding='utf-8')
        moment = {'key': 'm:vida:120', 'kind': 'video-moment', 'videoId': 'vida',
                  'videoTitle': 'Video title', 'time': 120, 'title': 'Saved title'}
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.add_init_script("""(() => {
              localStorage.setItem('sg.saved', JSON.stringify([%s]));
              let factory;
              Object.defineProperty(window, 'createI18n', {
                configurable: true,
                get: () => factory,
                set: value => { factory = (...args) => { const engine = value(...args); window.__testI18nEngine = engine; return engine; }; }
              });
            })();""" % json.dumps(moment))
            page.goto(origin + '/#/saved')
            page.locator('[data-moment-edit]').click()
            page.locator('#momentName').fill('Draft title')
            page.evaluate("""() => {
              const engine = window.__testI18nEngine;
              engine.usePreferredLocales('es-419');
              document.documentElement.lang = engine.locale;
              LastbookI18n.apply();
              document.dispatchEvent(new Event('lastbook:languagechange'));
            }""")
            expect(page.locator('#momentName')).to_have_value('Draft title')
            page.locator('form.moment-form').evaluate('form => form.requestSubmit()')
            expect(page.locator('[data-moment-edit]')).to_have_count(1)
            self.assertEqual(page.evaluate("JSON.parse(localStorage.getItem('sg.saved'))[0].title"), 'Draft title')

    def test_answer_title_and_markdown_export_use_catalogue_copy(self):
        self.configure_setup(current=DATA)
        self.language_file.write_text('{"language":"es-419"}', encoding='utf-8')
        chat = {'id': 'saved-chat', 'title': 'Pregunta de prueba', 'updated': '2026-11-25T12:00:00Z', 'messages': [
            {'role': 'user', 'content': '¿Cómo hacerlo?'},
            {'role': 'assistant', 'content': 'Respuesta de prueba.', 'cited': []},
            {'role': 'user', 'content': 'Otra pregunta'},
            {'role': 'assistant', 'content': '', 'error': 'stopped'},
        ]}
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.add_init_script("localStorage.setItem('sg.chats', " + json.dumps(json.dumps([chat])) + ");")
            page.goto(origin + '/#/ask/saved-chat')
            page.get_by_role('button', name='Guardar respuesta').click()
            record = page.evaluate("JSON.parse(localStorage.getItem('sg.saved'))[0]")
            self.assertEqual(record['title'], 'Respuesta: ¿Cómo hacerlo?')
            page.evaluate("location.hash = '#/saved'")
            expect(page.locator('.list b').first).to_have_text('Respuesta: ¿Cómo hacerlo?')
            page.evaluate("location.hash = '#/ask/saved-chat'")
            with page.expect_download() as exported:
                page.get_by_role('button', name='Exportar chat').click()
            markdown = Path(exported.value.path()).read_text(encoding='utf-8')
            self.assertIn('# Conversación: Pregunta de prueba', markdown)
            self.assertIn('Exportado desde Lastbook (biblioteca sin conexión)', markdown)
            self.assertIn('Las respuestas se escribieron con un modelo de IA local', markdown)
            self.assertIn('## Pregunta', markdown)
            self.assertIn('## Respuesta', markdown)
            self.assertIn('(sin respuesta: Se detuvo.)', markdown)


    def test_chat_sidebar_landmark_label_translates_and_sets_language(self):
        self.configure_setup(current=DATA)
        for locale, label in (('de', 'Unterhaltungen'), ('zh-Hans', '对话')):
            with self.subTest(locale=locale):
                self.language_file.write_text(json.dumps({'language': locale}), encoding='utf-8')
                with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
                    page.goto(origin + '/#/ask')
                    sidebar = page.locator('#chatSide')
                    expect(sidebar).to_have_attribute('aria-label', label)
                    expect(sidebar).to_have_attribute('lang', locale)



    def test_chat_citation_title_uses_catalogue_language(self):
        self.configure_setup(current=DATA)
        self.language_file.write_text('{"language":"es-419"}', encoding='utf-8')
        chat = {'id': 'source-title-chat', 'title': 'Question', 'updated': '2026-11-17T12:00:00Z',
                'messages': [{'role': 'user', 'content': 'Question'}, {'role': 'assistant', 'content': 'Answer [S1] [S2].',
                              'cited': [{'key': 'S1', 'kind': 'page', 'doc_id': 'manual', 'title': 'Manual'},
                                        {'key': 'S2', 'kind': 'video', 'doc_id': 'video', 'title': 'Video', 't': 12}], 'steps': []}]}
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.add_init_script("localStorage.setItem('sg.chats', " + json.dumps(json.dumps([chat])) + ");")
            page.goto(origin + '/#/ask/source-title-chat')
            expect(page.locator('.cite').first).to_have_attribute('title', 'Fuente S1')
            expect(page.locator('.cite').first).to_have_attribute('lang', 'es-419')
            expect(page.locator('.srcfilter button')).to_have_text(['Todas 2', 'Páginas 1', 'Videos 1'])
            expect(page.locator('.srcfilter button span[lang="es-419"]')).to_have_count(3)

    def test_chat_context_and_home_fallbacks_tag_their_language(self):
        self.configure_setup(current=DATA)
        self.language_file.write_text('{"language":"de"}', encoding='utf-8')
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.route('**/api/doc/**', lambda route: route.fulfill(
                status=200, content_type='application/json', body=json.dumps({'title': 'Reference'})))
            page.goto(origin + '/#/ask?about=video:clip:90')
            expect(page.locator('#ctxChip .muted span[lang="en"]')).to_have_text('Video at 1:30')
            page.evaluate("location.hash = '#/ask'")
            expect(page.locator('#askMore .ask-cards .ask-card .ac-t span[lang="en"]').first).to_be_visible()

    def test_chat_context_starters_use_catalogue_copy(self):
        self.configure_setup(current=DATA)
        self.language_file.write_text('{"language":"es-419"}', encoding='utf-8')
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.goto(origin + '/#/ask?about=topic:water')
            expect(page.locator('.starter').first).to_have_text('¿Qué debería hacer primero?')

    def test_chat_empty_state_and_citation_name_use_resolved_catalogue_locale(self):
        self.configure_setup(current=DATA)
        self.language_file.write_text('{"language":"de"}', encoding='utf-8')
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.goto(origin + '/#/ask')
            expect(page.locator('#csList li.muted.small span[lang="en"]')).to_have_text('No chats yet.')

        self.language_file.write_text('{"language":"es-419"}', encoding='utf-8')
        chat = {'id': 'source-title-chat', 'title': 'Question', 'updated': '2026-11-17T12:00:00Z',
                'messages': [{'role': 'user', 'content': 'Question'}, {'role': 'assistant', 'content': 'Answer [S1] [S2].',
                              'cited': [{'key': 'S1', 'kind': 'page', 'doc_id': 'manual', 'title': 'Manual'},
                                        {'key': 'S2', 'kind': 'video', 'doc_id': 'video', 'title': 'Video', 't': 12}], 'steps': []}]}
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.add_init_script("localStorage.setItem('sg.chats', " + json.dumps(json.dumps([chat])) + ");")
            page.goto(origin + '/#/ask/source-title-chat')
            expect(page.locator('.cite').first).to_have_attribute('title', 'Fuente S1')
            expect(page.locator('.cite').first).to_have_attribute('lang', 'es-419')
            expect(page.locator('.srcfilter button')).to_have_text(['Todas 2', 'Páginas 1', 'Videos 1'])
            expect(page.locator('.srcfilter button span[lang="es-419"]')).to_have_count(3)

    def test_empty_chat_list_tags_the_english_fallback(self):
        self.configure_setup(current=DATA)
        self.language_file.write_text('{"language":"de"}', encoding='utf-8')
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.goto(origin + '/#/ask')
            empty = page.locator('#csList li.muted.small span[lang="en"]')
            expect(empty).to_have_text('No chats yet.')

    def test_empty_search_hint_and_source_language_tags_use_catalogue_metadata(self):
        self.configure_setup(current=DATA)
        self.language_file.write_text('{"language":"es-419"}', encoding='utf-8')
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.goto(origin + '/#/search')
            expect(page.locator('#sout > p.muted span[lang="es-419"]')).to_have_text(
                'Usa las palabras que usarías al hablar con alguien. Por ejemplo:')
            actual = page.evaluate("""() => {
              const language = value => {
                const box = document.createElement('div');
                box.innerHTML = resultCard({title:'Document', hits:[], trust:'', language:value});
                return box.firstElementChild.getAttribute('lang');
              };
              return [language(undefined), language('not_a_tag'), language('es-mx')];
            }""")
            self.assertEqual(actual, [None, None, 'es-MX'])

    def test_language_change_keeps_the_active_chat_stop_control(self):
        self.configure_setup(current=DATA)
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.route('**/api/assistant/status', lambda route: route.fulfill(
                status=200, content_type='application/json', body=json.dumps({'online': True, 'index': {'state': 'off'}})))
            page.add_init_script("""(() => {
              let factory;
              Object.defineProperty(window, 'createI18n', {
                configurable: true,
                get: () => factory,
                set: value => { factory = (...args) => { const engine = value(...args); window.__testI18nEngine = engine; return engine; }; }
              });
              const nativeFetch = window.fetch.bind(window);
              window.fetch = (input, init = {}) => {
                if (new URL(input, location.href).pathname === '/api/chat') {
                  window.chatRequestStarted = true;
                  return new Promise((resolve, reject) => {
                    init.signal?.addEventListener('abort', () => reject(new DOMException('Stopped', 'AbortError')), {once:true});
                  });
                }
                return nativeFetch(input, init);
              };
            })();""")
            page.goto(origin + '/#/ask')
            page.locator('#chatIn').fill('Question')
            page.locator('#composer').evaluate('(form) => form.requestSubmit()')
            expect(page.locator('html')).to_have_attribute('lang', 'en')
            page.wait_for_function('window.chatRequestStarted === true')
            expect(page.locator('#sendBtn')).to_have_class('sendbtn stop')
            page.evaluate("""(() => {
              const engine = window.__testI18nEngine;
              engine.usePreferredLocales('es-419');
              document.documentElement.lang = engine.locale;
              LastbookI18n.apply();
              document.dispatchEvent(new Event('lastbook:languagechange'));
            })()""")
            expect(page.locator('#sendBtn')).to_have_class('sendbtn stop')
            expect(page.locator('#sendBtn')).to_have_accessible_name('Detener la respuesta')
            page.locator('#sendBtn').click()
            expect(page.locator('#sendBtn')).not_to_have_class('sendbtn stop')
            expect(page.locator('#sendBtn')).to_have_accessible_name('Enviar')

    def test_map_dynamic_english_fallbacks_keep_their_language(self):
        self.configure_setup(current=DATA)
        self.language_file.write_text('{"language":"de"}', encoding='utf-8')
        info = {'layers': ['hospital'], 'bounds': [-125, 24, -66, 50], 'datasets': [],
                'version': 'test', 'national': None, 'aerial': False, 'contours': False}
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.route('**/api/map/info', lambda route: route.fulfill(
                status=200, content_type='application/json', body=json.dumps(info)))
            page.route('**/api/map/pins*', lambda route: route.fulfill(
                status=200, content_type='application/json', body=json.dumps({'points': [], 'truncated': False})))
            page.route('**/api/map/near*', lambda route: route.fulfill(
                status=200, content_type='application/json', body='[]'))
            page.route('**/api/places*', lambda route: route.fulfill(
                status=200, content_type='application/json', body='[]'))
            page.goto(origin + '/#/map')
            expect(page.locator('.maptools h2').first).to_have_text('Am nächsten zur Kartenmitte')
            expect(page.locator('#mstatus span[lang="en"]')).to_have_text(
                'Nothing from your layers in this view — zoom out or turn on more layers.')
            expect(page.locator('#near span[lang="en"]')).to_have_text(
                'Nothing from your layers within about 100 miles of the map center.')
            page.get_by_label('Find an address, town, ZIP code or place').fill('123 Main Street')
            page.get_by_label('Find an address, town, ZIP code or place').press('Enter')
            expect(page.locator('#pres span[lang="en"]')).to_have_text([
                'Address not found in your offline data. Check the house number and street.',
                'Add your state’s address search.'])

    def test_map_truncated_status_tags_an_english_fallback_fragment(self):
        self.configure_setup(current=DATA)
        self.language_file.write_text('{"language":"de"}', encoding='utf-8')
        info = {'layers': ['hospital'], 'bounds': [-125, 24, -66, 50], 'datasets': [],
                'version': 'test', 'national': None, 'aerial': False, 'contours': False}
        points = {'points': [{'lat': 39, 'lon': -98, 'count': 1, 'kinds': {'hospital': 1}, 'cls': 'hospital'}],
                  'truncated': True}
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.route('**/api/map/info', lambda route: route.fulfill(
                status=200, content_type='application/json', body=json.dumps(info)))
            page.route('**/api/map/pins*', lambda route: route.fulfill(
                status=200, content_type='application/json', body=json.dumps(points)))
            page.route('**/api/map/near*', lambda route: route.fulfill(
                status=200, content_type='application/json', body='[]'))
            page.goto(origin + '/#/map')
            page.evaluate("""() => {
                const real = window.LastbookI18n;
                window.LastbookI18n = {
                    ...real,
                    resolve(key, params) {
                        if (key === 'map.placesInView')
                            return { text: `${params.count} Orte in Ansicht${params.extra}`, locale: 'de' };
                        if (key === 'map.cappedPlacesInView')
                            return { text: ' (busiest shown — zoom in for all)', locale: 'en' };
                        return real.resolve(key, params);
                    }
                };
            }""")
            page.locator('#zin').click()
            expect(page.locator('#mstatus span[lang="de"]')).to_have_text('1 Orte in Ansicht')
            expect(page.locator('#mstatus span[lang="en"]')).to_have_text(' (busiest shown — zoom in for all)')

    def test_nearby_distance_fragment_uses_catalogue_locale(self):
        self.configure_setup(current=DATA)
        self.language_file.write_text('{"language":"es-419"}', encoding='utf-8')
        info = {'layers': ['hospital'], 'bounds': [-125, 24, -66, 50], 'datasets': [],
                'version': 'test', 'national': None, 'aerial': False, 'contours': False}
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.route('**/api/map/info', lambda route: route.fulfill(
                status=200, content_type='application/json', body=json.dumps(info)))
            page.route('**/api/map/pins*', lambda route: route.fulfill(
                status=200, content_type='application/json', body=json.dumps({'points': [], 'truncated': False})))
            page.route('**/api/map/near*', lambda route: route.fulfill(
                status=200, content_type='application/json', body=json.dumps([
                    {'lat': 39, 'lon': -98, 'km': 0.5, 'cls': 'hospital', 'name': 'Hospital', 'dir': 'north'}])))
            page.goto(origin + '/#/map?lat=39&lon=-98&z=15')
            distance = page.locator('#near .near-distance span')
            expect(distance).to_have_attribute('lang', 'es-419')
            expect(distance).to_have_text('a 500 m al norte')

    def test_no_results_copy_uses_the_resolved_language(self):
        self.configure_setup(current=DATA)
        self.language_file.write_text('{"language":"de"}', encoding='utf-8')
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.route('**/api/find*', lambda route: route.fulfill(
                status=200, content_type='application/json', body=json.dumps({'results': [], 'expanded': [], 'mode': 'all'})))
            page.route('**/api/retrieve*', lambda route: route.fulfill(
                status=200, content_type='application/json', body=json.dumps({'results': []})))
            page.goto(origin + '/#/search?q=CodexAuditNoResults')
            expect(page.locator('#sres .empty b span[lang="en"]')).to_have_text('No results for “CodexAuditNoResults”')
            expect(page.locator('#sres .empty p span[lang="en"]')).to_have_text(
                'Try fewer words, or another word for the same thing.')

    def test_setup_ai_diagnostics_use_the_translated_key_and_params(self):
        manifest = self.local_ai_manifest()
        self.language_file.write_text('{"language":"es-419"}', encoding='utf-8')
        setup = self.configure_setup(setup_manifest=manifest)
        self.set_hardware(setup, fits=False, disk_path=DATA)
        setup.recommend = lambda _hw: {'pack': 'small', 'ai': False, 'why_key': 'setup.why.smallToStart'}
        with serve(server.setup_api.SetupServer, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.goto(origin)
            expect(page.locator('.s-opt.s-ai small')).to_have_text(
                'La IA local necesita unos 20 GB de la memoria de esta computadora, y esta tiene 8 GB. Lastbook funciona sin ella: la búsqueda y la lectura son las mismas.')
            self.assertNotIn('The local AI needs about', page.locator('.s-opt.s-ai').inner_text())

        setup = self.configure_setup(current=DATA, setup_manifest=manifest)
        self.set_hardware(setup, fits=False, disk_path=DATA)
        self.language_file.write_text('{"language":"es-419"}', encoding='utf-8')
        with serve(server.setup_api.SetupServer, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.goto(origin + '/ui/setup.html#manage')
            expect(page.locator('.s-have .s-row').nth(1).locator('small')).to_have_text(
                    'La IA local necesita unos 20 GB de la memoria de esta computadora, y esta tiene 8 GB. Lastbook funciona sin ella: la búsqueda y la lectura son las mismas.')

    def test_setup_local_ai_recommendation_and_linux_disk_fallback_are_translated(self):
        self.language_file.write_text('{"language":"es-419"}', encoding='utf-8')
        setup = self.configure_setup(setup_manifest=self.local_ai_manifest())
        self.set_hardware(setup, fits=True)
        setup.recommend = lambda _hw: {'pack': 'small', 'ai': True, 'why_key': 'setup.why.smallToStart'}
        with serve(server.setup_api.SetupServer, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.goto(origin)
            expect(page.locator('.s-rec')).to_contain_text('con la IA local')

        setup = self.configure_setup(current=DATA, setup_manifest=self.local_ai_manifest())
        self.set_hardware(setup, fits=True, disk_path='/')
        with serve(server.setup_api.SetupServer, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.add_init_script("""(() => {
              Object.defineProperty(navigator, 'platform', {get: () => 'Linux x86_64'});
              const add = DOMTokenList.prototype.add;
              DOMTokenList.prototype.add = function(...tokens) { return add.apply(this, tokens.filter(x => x !== 'plat-win')); };
            })();""")
            page.goto(origin + '/ui/setup.html#manage')
            expect(page.get_by_role('button', name='Agregar')).to_be_visible()
            expect(page.locator('.s-pc')).to_contain_text('libres en esta computadora')

    def test_small_pack_v1_summary_without_a_key_uses_the_selected_language(self):
        from engine.setup import manifest as setup_manifest

        bundled = setup_manifest.validate({'version': 1, 'packs': [{
            'id': 'small', 'title': 'Small',
            'summary': 'The essentials: first aid, water, food, shelter and repair, with the maps of this area.',
            'available': False, 'files': [],
        }], 'models': []})
        self.assertIsNotNone(bundled)
        self.configure_setup(setup_manifest=Manifest(bundled=bundled, remote=None))
        self.language_file.write_text('{"language":"es-419"}', encoding='utf-8')
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.goto(origin + '/ui/setup.html')
            expect(page.locator('[data-pack-summary="small"]')).to_have_text(
                'Lo esencial: primeros auxilios, agua, alimentos, refugio y reparación, con los mapas de esta zona.')

    def test_video_speed_uses_selected_german_catalogue_copy(self):
        self.configure_setup(current=DATA)
        self.language_file.write_text('{"language":"de"}', encoding='utf-8')
        with serve(server, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.goto(origin + '/#/watch/vida')
            expect(page.locator('.video-speed label span[lang="de"]')).to_have_text('Wiedergabegeschwindigkeit')
            expect(page.locator('#videoSpeed option[value="1"]')).to_have_attribute('lang', 'de')
            expect(page.locator('#videoSpeed option[value="1"]')).to_have_text('Normal')

    def test_spanish_language_preview_keeps_the_partial_translation_notice(self):
        self.configure_setup(current=DATA)
        self.language_file.write_text('{"language":"es-419"}', encoding='utf-8')
        with serve(server.setup_api.SetupServer, self.language_file) as (origin, http), self.page(origin, http) as page:
            page.goto(origin + '/ui/setup.html#manage')
            expect(page.locator('#languagePreview')).to_have_text(
                'La traducción al español todavía es parcial. Algunos textos de la interfaz y los menús nativos pueden aparecer en inglés.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chromium', help='path to Chromium, or use the Playwright-managed browser')
    options, rest = parser.parse_known_args()
    Browser.chromium = options.chromium
    unittest.main(argv=[sys.argv[0], *rest])
