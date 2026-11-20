#!/usr/bin/env python3
"""Assistant settings (assistant.py + llm_local.py): the shared config file, validation, and the
file > env var > built-in default precedence. No model, no server, no library: the settings file
lives in a throwaway LASTBOOK_DATA folder and the model is never called.

  python3 -B app/tests/test_assistant_config.py [-v] [Class.test_name]
"""
import json, os, sys, tempfile, unittest
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE.parent), str(ROOT)]

# engine.paths reads LASTBOOK_DATA once, at import, so the folder must exist before the import.
DATA = Path(tempfile.mkdtemp(prefix='lb-cfg-'))
os.environ['LASTBOOK_DATA'] = str(DATA)
os.environ['SURVIVAL_MODEL_BASE'] = 'http://127.0.0.1:9'   # a valid loopback: the import must not exit
sys.modules['onnxruntime'] = None   # importing it now raises ImportError: no model is loaded or needed here
import assistant   # noqa: E402
import llm_local   # noqa: E402

CFG = assistant.CONFIG_FILE   # LASTBOOK_DATA/derived/llm/config.json, the same file llm_local reads
ENV = ('SURVIVAL_MODEL_BASE', 'SURVIVAL_MODEL', 'SURVIVAL_REASONING_EFFORT', 'LASTBOOK_MODEL_DIR', 'LASTBOOK_AI_IDLE_S')


def write_file(d):
    """A settings file written by hand, bypassing validation — what a damaged or foreign file looks like."""
    CFG.parent.mkdir(parents=True, exist_ok=True)
    CFG.write_text(json.dumps(d), encoding='utf-8')


class Base(unittest.TestCase):
    def setUp(self):
        self._env = {k: os.environ.pop(k, None) for k in ENV}
        if CFG.exists():
            CFG.unlink()

    def tearDown(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        if CFG.exists():
            CFG.unlink()


class ConfigFile(Base):
    def test_missing_file_is_empty(self):
        self.assertEqual(assistant.config(), {})

    def test_save_merges_into_the_file(self):
        assistant.save_config(assistant.validate_config({'model': 'm1'}))
        assistant.save_config(assistant.validate_config({'reasoning_effort': 'high'}))
        self.assertEqual(assistant.config(), {'model': 'm1', 'reasoning_effort': 'high'})
        self.assertEqual(json.loads(CFG.read_text(encoding='utf-8')), assistant.config())

    def test_corrupt_file_is_empty(self):
        CFG.parent.mkdir(parents=True, exist_ok=True)
        CFG.write_text('{not json', encoding='utf-8')
        self.assertEqual(assistant.config(), {})

    def test_non_dict_file_is_empty(self):
        CFG.parent.mkdir(parents=True, exist_ok=True)
        CFG.write_text('[1, 2]', encoding='utf-8')
        self.assertEqual(assistant.config(), {})


class Validate(Base):
    def test_empty_update(self):
        self.assertEqual(assistant.validate_config({}), {})

    def test_not_dict_raises(self):
        with self.assertRaises(ValueError):
            assistant.validate_config([1, 2])

    def test_full_update(self):
        d = assistant.validate_config({'model_base': ' http://127.0.0.1:19443/ ', 'model': ' m1 ',
                                       'reasoning_effort': ' high ', 'model_dir': ' /a/b ', 'idle_s': 60})
        self.assertEqual(d, {'model_base': 'http://127.0.0.1:19443', 'model': 'm1',
                             'reasoning_effort': 'high', 'model_dir': '/a/b', 'idle_s': 60})

    def test_model_base_rejects_off_loopback(self):
        for bad in ('http://example.com:19443', 'https://127.0.0.1:19443', '127.0.0.1:19443.example.com', 'http://localhost.evil:1'):
            with self.assertRaises(ValueError):
                assistant.validate_config({'model_base': bad})

    def test_model_base_takes_an_address_without_the_scheme(self):
        self.assertEqual(assistant.validate_config({'model_base': '127.0.0.1:19443'})['model_base'], 'http://127.0.0.1:19443')
        self.assertEqual(assistant.validate_config({'model_base': 'localhost:19443'})['model_base'], 'http://127.0.0.1:19443')

    def test_model_base_rejects_not_string(self):
        with self.assertRaises(ValueError):
            assistant.validate_config({'model_base': 19443})

    def test_model_and_effort_must_be_nonempty_strings(self):
        for key in ('model', 'reasoning_effort'):
            for bad in ('', '   ', None, 3):
                with self.assertRaises(ValueError):
                    assistant.validate_config({key: bad})

    def test_model_dir_clears_with_null_or_blank(self):
        self.assertIsNone(assistant.validate_config({'model_dir': None})['model_dir'])
        self.assertIsNone(assistant.validate_config({'model_dir': '   '})['model_dir'])
        with self.assertRaises(ValueError):
            assistant.validate_config({'model_dir': 5})

    def test_idle_s_positive_int_only(self):
        self.assertEqual(assistant.validate_config({'idle_s': 60})['idle_s'], 60)
        for bad in (True, False, 0, -5, '60', 60.5, None):
            with self.assertRaises(ValueError):
                assistant.validate_config({'idle_s': bad})

    def test_unknown_keys_are_ignored(self):
        self.assertEqual(assistant.validate_config({'model': 'm', 'bogus': 1, 'another': 'x'}), {'model': 'm'})


class Apply(Base):
    def test_defaults(self):
        r = assistant.apply_config()
        self.assertEqual(r, {'model_base': 'http://127.0.0.1:19443', 'model': 'deepseek-v4.1-flash', 'reasoning_effort': 'low'})

    def test_env_beats_default(self):
        os.environ['SURVIVAL_MODEL_BASE'] = 'http://127.0.0.1:19444'
        os.environ['SURVIVAL_MODEL'] = 'env-model'
        r = assistant.apply_config()
        self.assertEqual((r['model_base'], r['model']), ('http://127.0.0.1:19444', 'env-model'))

    def test_file_beats_env(self):
        os.environ['SURVIVAL_MODEL_BASE'] = 'http://127.0.0.1:19444'
        write_file({'model_base': 'http://127.0.0.1:19445', 'model': 'file-model'})
        r = assistant.apply_config()
        self.assertEqual((r['model_base'], r['model']), ('http://127.0.0.1:19445', 'file-model'))

    def test_bad_file_base_keeps_the_current_value(self):
        assistant.apply_config()   # no file, no env var: the built-in default
        write_file({'model_base': 'http://example.com:1'})   # written by hand, bypassing validation
        r = assistant.apply_config()
        self.assertEqual(r['model_base'], 'http://127.0.0.1:19443')   # unchanged: a damaged file never stops the server

    def test_globals_follow_the_file(self):
        write_file({'model_base': 'http://127.0.0.1:19445', 'model': 'file-model', 'reasoning_effort': 'high'})
        assistant.apply_config()
        self.assertEqual(assistant.BASE, 'http://127.0.0.1:19445')
        self.assertEqual(assistant.MODEL_URL, 'http://127.0.0.1:19445/v1/chat/completions')
        self.assertEqual(assistant.MODEL, 'file-model')
        self.assertEqual(assistant.REASONING_EFFORT, 'high')


class Effective(Base):
    def test_five_keys(self):
        self.assertEqual(set(assistant.effective_config()),
                         {'model_base', 'model', 'reasoning_effort', 'model_dir', 'idle_s'})

    def test_shares_the_file_with_the_local_ai(self):
        assistant.save_config(assistant.validate_config({'model_dir': '/somewhere', 'idle_s': 120}))
        c = assistant.effective_config()
        self.assertEqual((c['model_dir'], c['idle_s']), ('/somewhere', 120))
        self.assertEqual(c['model_dir'], llm_local.effective_config()['model_dir'])
        self.assertEqual(c['idle_s'], llm_local.effective_config()['idle_s'])


class LocalConfig(Base):
    def test_defaults(self):
        self.assertEqual(llm_local.effective_config(), {'model_dir': None, 'idle_s': 900})

    def test_env(self):
        os.environ['LASTBOOK_MODEL_DIR'] = '/env-dir'
        os.environ['LASTBOOK_AI_IDLE_S'] = '30'
        self.assertEqual(llm_local.effective_config(), {'model_dir': '/env-dir', 'idle_s': 30})

    def test_file_beats_env(self):
        os.environ['LASTBOOK_MODEL_DIR'] = '/env-dir'
        os.environ['LASTBOOK_AI_IDLE_S'] = '30'
        write_file({'model_dir': '/file-dir', 'idle_s': 60})
        self.assertEqual(llm_local.effective_config(), {'model_dir': '/file-dir', 'idle_s': 60})

    def test_bad_file_values_fall_through(self):
        write_file({'model_dir': 5, 'idle_s': True})   # written by hand, bypassing validation
        self.assertEqual(llm_local.effective_config(), {'model_dir': None, 'idle_s': 900})

    def test_places_prefers_the_configured_folder(self):
        write_file({'model_dir': '/a/model-folder'})
        self.assertEqual(llm_local.places()[0], Path('/a/model-folder'))

    def test_config_values_and_reload(self):
        write_file({'model_dir': '/a/model-folder', 'idle_s': 60})
        self.assertEqual(llm_local.LOCAL.config_values(), {'model_dir': '/a/model-folder', 'idle_s': 60})
        llm_local.LOCAL.state = 'stopped'   # a stopped model: reload must not start a discovery
        llm_local.LOCAL.reload_config()


if __name__ == '__main__':
    unittest.main()
