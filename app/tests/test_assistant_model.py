#!/usr/bin/env python3
"""Choosing a model the configured loopback server already lists. No real server and no real home folder.

  python3 -B app/tests/test_assistant_model.py [-v]
"""
import json, os, sys, tempfile, unittest
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
os.environ['SURVIVAL_MODEL_BASE'] = 'http://127.0.0.1:9'   # dead: this test never opens a connection
os.environ['SURVIVAL_MODEL'] = 'deepseek-v4.1-flash'
sys.path[:0] = [str(ROOT), str(ROOT / 'app')]
import assistant  # noqa: E402


class AssistantModel(unittest.TestCase):
    IDS = ['gemma4:26b-a4b', 'gpt-oss:20b']

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = mock.patch.dict(os.environ, {'XDG_CONFIG_HOME': self.tmp.name})
        env.start()
        self.addCleanup(env.stop)
        listed = mock.patch.object(assistant, 'listed_models', return_value=(self.IDS, None))
        listed.start()
        self.addCleanup(listed.stop)
        assistant._listed['at'] = 0

    def settings(self):
        return json.loads(assistant._settings_path().read_text(encoding='utf-8'))

    def test_startup_model_is_used_until_someone_chooses(self):
        self.assertIsNone(assistant.active_model(self.IDS))
        self.assertEqual(assistant.http_target()[1], 'deepseek-v4.1-flash')
        status = assistant.model_status()
        self.assertFalse(status['online'])
        self.assertEqual(status['picker']['models'], self.IDS)
        self.assertIsNone(status['picker']['model'])

    def test_unknown_model_is_refused_and_a_listed_one_is_kept(self):
        path = assistant._settings_path()
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({'library': '/library'}), encoding='utf-8')
        self.assertFalse(assistant.set_assistant_model('not-installed'))
        self.assertEqual(self.settings(), {'library': '/library'})
        self.assertTrue(assistant.set_assistant_model('gpt-oss:20b'))
        self.assertEqual(self.settings()['library'], '/library')
        self.assertEqual(self.settings()['assistant_model'], 'gpt-oss:20b')
        self.assertEqual(assistant.http_target()[1], 'gpt-oss:20b')
        status = assistant.model_status()
        self.assertTrue(status['online'])
        self.assertEqual(status['model'], 'gpt-oss:20b')

    def test_a_saved_model_that_is_no_longer_listed_is_not_used(self):
        self.assertTrue(assistant.set_assistant_model('gpt-oss:20b'))
        with mock.patch.object(assistant, 'listed_models', return_value=(['gemma4:26b-a4b'], None)):
            self.assertIsNone(assistant.active_model(['gemma4:26b-a4b']))
            self.assertEqual(assistant.http_target()[1], 'deepseek-v4.1-flash')

    def test_ollama_port_is_labelled_ollama(self):
        self.assertEqual(assistant.picker_label('http://127.0.0.1:11434'), 'Ollama')
        self.assertEqual(assistant.picker_label('http://127.0.0.1:19443'), 'Model')
        self.assertEqual(assistant.picker_label(), 'Model')


if __name__ == '__main__':
    unittest.main()
