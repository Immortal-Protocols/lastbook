#!/usr/bin/env python3
"""Tests for the refugiOS-inspired Brazilian Portuguese modules and routes.

  PYTHONDONTWRITEBYTECODE=1 <venv python> -B app/tests/test_refugios_features.py [-v]

Never packaged."""
import base64
import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'app'), str(HERE)]
import fixture  # noqa: E402

DATA = fixture.ensure()
os.environ['LASTBOOK_DATA'] = str(DATA)
os.environ['SURVIVAL_MODEL_BASE'] = 'http://127.0.0.1:9'
os.environ['SURVIVAL_DISABLE_INDEX_WATCH'] = '1'
sys.modules['onnxruntime'] = None

_real_listen = socket.socket.listen
socket.socket.listen = lambda *a, **kw: None
try:
    import llm_local  # noqa: E402
    import server  # noqa: E402
    import bridge as B  # noqa: E402
    from engine import checker, kiwix_br, translator, vault  # noqa: E402
    from engine.setup import api as setup_api  # noqa: E402
finally:
    socket.socket.listen = _real_listen

if getattr(server, 'INDEX', None) is None:
    server.init(no_index=True)


def _bridge_call(br, method, path, body=None, origin=B.ORIGIN_MAC):
    ev = threading.Event()
    box = []

    class Sink(B.Sink):
        def __init__(self):
            self.status = None
            self.headers = {}
            self.parts = []
            self.ok = None

        def head(self, status, reason, headers):
            self.status = status
            self.headers = {k.lower(): v for k, v in headers}

        def data(self, chunk, ack):
            self.parts.append(chunk)
            ack()

        def finish(self, ok):
            self.ok = ok
            box.append(self)
            ev.set()

    sink = Sink()
    headers = {'Origin': origin, 'X-Lastbook-Key': br.key}
    raw = None
    if body is not None:
        raw = json.dumps(body).encode('utf-8')
        headers['Content-Type'] = 'application/json'
        headers['Content-Length'] = str(len(raw))
    br.start(method, origin + path, headers, raw, sink)
    if not ev.wait(20):
        raise AssertionError(f'timeout calling {method} {path}')
    sink = box[0]
    raw_body = b''.join(sink.parts)
    try:
        parsed = json.loads(raw_body.decode('utf-8'))
    except ValueError:
        parsed = raw_body
    return sink.status, parsed


class VaultTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='lb-vault-'))
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))

    def test_create_open_save_delete_and_wrong_password(self):
        self.assertEqual(vault.list_vaults(data_dir=self.tmp), [])
        created = vault.create_vault('Família Silva', 'senha-forte-123', data_dir=self.tmp)
        vid = created['id']
        listed = vault.list_vaults(data_dir=self.tmp)
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]['id'], vid)
        self.assertEqual(listed[0]['name'], 'Família Silva')

        with self.assertRaises(PermissionError):
            vault.open_vault(vid, 'senha-errada', data_dir=self.tmp)

        opened = vault.open_vault(vid, 'senha-forte-123', data_dir=self.tmp)
        self.assertEqual(opened['name'], 'Família Silva')
        self.assertEqual(set(opened['payload']['sections']), {'documents', 'medical', 'contacts', 'notes'})

        att_raw = b'tipo sanguineo O+'
        payload = {
            'name': 'Família Silva Atualizado',
            'sections': {
                'documents': 'CPF 123',
                'medical': 'Alergia a penicilina',
                'contacts': 'SAMU 192',
                'notes': 'Ponto de encontro: praça central',
            },
            'attachments': [
                {
                    'id': 'a1',
                    'name': 'ficha.txt',
                    'mime': 'text/plain',
                    'size': len(att_raw),
                    'data_b64': base64.b64encode(att_raw).decode('ascii'),
                }
            ],
        }
        saved = vault.save_vault(vid, 'senha-forte-123', payload, data_dir=self.tmp)
        self.assertEqual(saved['name'], 'Família Silva Atualizado')

        with self.assertRaises(PermissionError):
            vault.save_vault(vid, 'senha-errada', payload, data_dir=self.tmp)

        reopened = vault.open_vault(vid, 'senha-forte-123', data_dir=self.tmp)
        self.assertEqual(reopened['payload']['sections']['medical'], 'Alergia a penicilina')
        self.assertEqual(reopened['payload']['attachments'][0]['name'], 'ficha.txt')

        with self.assertRaises(PermissionError):
            vault.delete_vault(vid, 'senha-errada', data_dir=self.tmp)

        deleted = vault.delete_vault(vid, 'senha-forte-123', data_dir=self.tmp)
        self.assertTrue(deleted['ok'])
        self.assertEqual(vault.list_vaults(data_dir=self.tmp), [])


class TranslatorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='lb-trans-'))
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))

    def test_glossary_and_offline_fallback(self):
        gl = translator.glossary()
        self.assertGreaterEqual(len(gl), 4)
        self.assertTrue(any('en' in item and 'es' in item and 'pt' in item for cat in gl for item in cat['items']))

        import assistant
        with mock.patch.object(assistant, 'local_on', return_value=False), \
                mock.patch.object(assistant, 'model_status', return_value={'online': False, 'local': False}):
            res = translator.translate(
                'WARNING: Carbon monoxide hazard. Operate generator outdoors only and boil water.',
                source='en',
                target='pt-BR',
                data_dir=self.tmp,
            )
        self.assertEqual(res['mode'], 'glossary')
        self.assertFalse(res['cached'])
        self.assertIn('monóxido de carbono', res['translated'])
        self.assertIn('gerador', res['translated'])

    def test_disk_cache_hit(self):
        text = 'Keep clean water in sealed containers.'
        cpath = translator._cache_path(text, 'en', 'pt-BR', doc_id='doc-1', page=2, data_dir=self.tmp)
        cpath.parent.mkdir(parents=True, exist_ok=True)
        cpath.write_text(json.dumps({
            'translated': 'Mantenha água limpa em recipientes fechados.',
            'mode': 'ai',
            'model': 'Gemma 4',
            'source': 'en',
            'target': 'pt-BR',
            'cached': False,
        }), encoding='utf-8')
        res = translator.translate(text, source='en', target='pt-BR', doc_id='doc-1', page=2, data_dir=self.tmp)
        self.assertTrue(res['cached'])
        self.assertEqual(res['mode'], 'ai')
        self.assertEqual(res['translated'], 'Mantenha água limpa em recipientes fechados.')


class CheckerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='lb-check-'))
        lib = self.tmp / 'library-data'
        lib.mkdir(parents=True)
        (lib / 'catalog.json').write_text('{}', encoding='utf-8')
        (lib / 'pages.db').write_bytes(b'SQLite format 3\x00')
        (self.tmp / 'pack.json').write_text(json.dumps({'name': 'pt-br-test', 'content_revision': 'v1'}), encoding='utf-8')
        geo = self.tmp / 'derived' / 'geo'
        geo.mkdir(parents=True)
        (geo / 'map.sqlite').write_bytes(b'SQLite format 3\x00')
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))

    def test_fast_and_full_check_writes_report(self):
        for full in (False, True):
            res = checker.run_check(full=full, data_dir=self.tmp)
            self.assertTrue(res['ok'], res)
            self.assertEqual(res['full'], full)
            self.assertEqual(res['report_name'], 'relatorio-verificacao.txt')
            self.assertTrue(res['saved_report'])
            report = self.tmp / 'derived' / 'logs' / 'relatorio-verificacao.txt'
            self.assertTrue(report.is_file())
            txt = report.read_text(encoding='utf-8')
            self.assertIn('RELATÓRIO DE VERIFICAÇÃO DO ÚLTIMO LIVRO', txt)
            self.assertIn('Biblioteca Base', txt)


class KiwixAndLLMTests(unittest.TestCase):
    def test_kiwix_pt_catalog_and_lookup(self):
        self.assertGreaterEqual(len(kiwix_br.ZIMS_PT), 7)
        wikimed = kiwix_br.get_zim('wikimed-pt')
        self.assertIsNotNone(wikimed)
        self.assertEqual(kiwix_br.get_zim(wikimed['file']), wikimed)
        self.assertEqual(kiwix_br.zim_label(wikimed['file']), wikimed['title'])
        public = kiwix_br.public_zims()
        self.assertEqual(len(public), len(kiwix_br.ZIMS_PT))
        self.assertTrue(all('url' not in item for item in public))

    def test_llm_models_selector_and_reasoning_strip(self):
        ids = [m['id'] for m in llm_local.MODELS]
        self.assertIn('gemma-4-e2b', ids)
        self.assertIn('qwen-3.5-0.8b', ids)
        self.assertIsNotNone(llm_local.model_spec('qwen-3.5-0.8b'))

        raw = (
            'O usuário está perguntando como purificar água.\n'
            '1. Analisar os resultados iniciais: os trechos falam sobre fervura.\n'
            '2. Avaliar as fontes: A fonte S1 menciona 1 minuto de ebulição.\n'
            'Resposta final: Ferva a água em ebulição vigorosa por pelo menos 1 minuto [S1].'
        )
        thought, visible = llm_local.split_thinking(raw, streaming=False)
        self.assertIn('Analisar os resultados iniciais', thought)
        self.assertEqual(visible.strip(), 'Ferva a água em ebulição vigorosa por pelo menos 1 minuto [S1].')
        self.assertEqual(llm_local._strip_thinking(raw), 'Ferva a água em ebulição vigorosa por pelo menos 1 minuto [S1].')

        tmp_models = Path(tempfile.mkdtemp(prefix='lb-models-'))
        self.addCleanup(lambda: shutil.rmtree(tmp_models, ignore_errors=True))
        qwen = llm_local.model_spec('qwen-3.5-0.8b')
        fake_path = tmp_models / qwen['file']
        fake_path.write_bytes(b'')
        os.truncate(fake_path, qwen['size'])

        local = llm_local.Local()
        with mock.patch.dict(os.environ, {'LASTBOOK_MODEL_DIR': str(tmp_models)}), \
                mock.patch.object(llm_local, '_save'), \
                mock.patch('threading.Thread'):
            installed = local.installed_models()
            self.assertTrue(any(m['id'] == 'qwen-3.5-0.8b' for m in installed))
            self.assertTrue(local.select_model('qwen-3.5-0.8b'))
            self.assertEqual(local.spec['id'], 'qwen-3.5-0.8b')
            self.assertFalse(local.select_model('modelo-inexistente'))


class RoutesIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.bridge = B.Bridge(server, 'stream', B.ORIGIN_MAC)

    def test_vault_translate_check_setup_and_model_routes(self):
        # Vault routes
        st, created = _bridge_call(self.bridge, 'POST', '/api/vault', {'action': 'create', 'name': 'Teste Rota', 'password': 'abcd'})
        self.assertEqual(st, 200)
        vid = created['id']
        self.addCleanup(lambda: (DATA / 'derived' / 'vault' / f'{vid}.lbvault').unlink(missing_ok=True))

        st, listed = _bridge_call(self.bridge, 'GET', '/api/vault/list')
        self.assertEqual(st, 200)
        self.assertTrue(any(v['id'] == vid for v in listed['vaults']))

        st, err = _bridge_call(self.bridge, 'POST', '/api/vault', {'action': 'open', 'id': vid, 'password': 'errada'})
        self.assertEqual(st, 403)
        self.assertIn('error', err)

        st, deleted = _bridge_call(self.bridge, 'POST', '/api/vault', {'action': 'delete', 'id': vid, 'password': 'abcd'})
        self.assertEqual(st, 200)
        self.assertTrue(deleted['ok'])

        # Translate routes
        st, gl = _bridge_call(self.bridge, 'GET', '/api/translate/glossary')
        self.assertEqual(st, 200)
        self.assertIn('glossary', gl)

        import assistant
        with mock.patch.object(assistant, 'local_on', return_value=False), \
                mock.patch.object(assistant, 'model_status', return_value={'online': False, 'local': False}):
            st, tr = _bridge_call(self.bridge, 'POST', '/api/translate', {'text': 'Carbon monoxide generator outdoors', 'target': 'pt-BR'})
        self.assertEqual(st, 200)
        self.assertEqual(tr['mode'], 'glossary')

        # Checker route
        st, chk = _bridge_call(self.bridge, 'GET', '/api/check?full=0')
        self.assertEqual(st, 200)
        self.assertIn('sections', chk)
        self.assertIn('report_text', chk)

        # Setup state includes PT-BR ZIM catalog + current installed zims (offline, no network fetch)
        tmp_cfg = Path(tempfile.mkdtemp(prefix='lb-setup-'))
        self.addCleanup(lambda: shutil.rmtree(tmp_cfg, ignore_errors=True))
        setup_obj = setup_api.Setup('manage', tmp_cfg, DATA, current=DATA, llm_local=False)
        orig_setup = setup_api.SETUP
        setup_api.SETUP = setup_obj
        self.addCleanup(lambda: setattr(setup_api, 'SETUP', orig_setup))
        fake_hw = {
            'ram_bytes': 16 * 1024**3,
            'gpus': [],
            'unified_memory': True,
            'free_bytes': 50 * 1024**3,
            'disks': [],
            'folders': [],
            'ai': {'fits': True, 'needs_bytes': 4 * 1024**3, 'estimate': True, 'why': ''},
            'ai_models': {},
        }
        with mock.patch.object(setup_obj.manifest, 'fetch_once', return_value=None), \
                mock.patch.object(setup_obj, 'hardware', return_value=fake_hw):
            st, sstate = _bridge_call(self.bridge, 'GET', '/api/setup/state')
        self.assertEqual(st, 200)
        self.assertTrue(any(z['id'] == 'wikimed-pt' for z in sstate['zims']))
        self.assertIn('zims', sstate['current'])

        # Local AI select route (rejects unknown model cleanly)
        st, mres = _bridge_call(self.bridge, 'POST', '/api/assistant/local', {'action': 'select', 'model_id': 'nao-existe'})
        self.assertEqual(st, 404)
        self.assertIn('error', mres)


if __name__ == '__main__':
    unittest.main()
