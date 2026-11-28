"""Regression checks for the local AI's first-load status wording (#323)."""

import json
from pathlib import Path
import unittest


WEB = Path(__file__).resolve().parents[2] / "web"


class LocalAiFirstLoadCopy(unittest.TestCase):
    def test_chat_stopped_status_describes_first_load(self):
        source = (WEB / "chat.js").read_text(encoding="utf-8")
        self.assertIn("stopped: [true, translated('chat.available', null, 'Local AI available · your first question loads it and may take a while')]", source)
        english = json.loads((WEB.parent / 'translations' / 'desktop' / 'en.json').read_text(encoding='utf-8'))
        self.assertEqual(english['chat.available'], 'Local AI available · your first question loads it and may take a while')
        self.assertNotIn("Local AI ready · it starts when you ask", source)

    def test_settings_stopped_status_describes_first_load_and_idle_stop(self):
        source = (WEB / "app.js").read_text(encoding="utf-8")
        self.assertIn("available; your first question loads it and may take a while; it stops after 15 minutes unused", source)
        self.assertNotIn("ready; it starts when you ask and stops after 15 minutes unused", source)

    def test_running_and_loading_states_remain_distinct(self):
        chat = (WEB / "chat.js").read_text(encoding="utf-8")
        settings = (WEB / "app.js").read_text(encoding="utf-8")
        self.assertIn("ready: [true, translated('chat.ready', null, 'Local AI ready')]", chat)
        self.assertIn("loading: [true, translated('chat.state.startingPct'", chat)
        self.assertIn("ready: tr('about.localRunning', null, 'running now')", settings)
        self.assertIn("loading: tr('about.localStarting', null, 'starting')", settings)
        english = json.loads((WEB.parent / 'translations' / 'desktop' / 'en.json').read_text(encoding='utf-8'))
        self.assertNotEqual(english['chat.ready'], english['chat.available'])


if __name__ == "__main__":
    unittest.main()
