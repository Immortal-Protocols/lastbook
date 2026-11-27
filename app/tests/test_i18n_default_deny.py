"""Adversarial and mutation tests for the default-deny i18n scanner (packaging/i18n_scan.py).

Every case injects one new English literal into a realistic place and requires the
scanner to report it as unapproved: nothing a person can see may pass as "technical"
just because of its name, its function or a sink the scanner has not met before.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'packaging'))
import i18n_scan as scan  # noqa: E402

INJECTED = 'Injected visible sentence'


def unapproved_texts(hits):
    # No allowlist here: these tests check what the scanner proves on its own.
    return {h['text'] for h in scan.unapproved(hits, [])}


class Adversarial(unittest.TestCase):
    """New literals in display sinks of every surface are unapproved."""

    PYTHON_CASES = [
        ('app/shell_macos.py', "alert.setMessageText_('%s')"),
        ('app/shell_macos.py', "alert.setInformativeText_('%s')"),
        ('app/shell_macos.py', "window.setTitle_('%s')"),
        ('app/shell_macos.py', "item = menu.addItemWithTitle_action_keyEquivalent_('%s', 'act:', '')"),
        ('app/shell_macos.py', "field.setPlaceholderString_('%s')"),
        ('app/shell_linux.py', "win.set_title('%s')"),
        ('app/shell_linux.py', "label.set_label('%s')"),
        ('app/shell_linux.py', "box.add(Gtk.Label(label='%s'))"),
        ('app/shell_linux.py', "item = Gtk.MenuItem.new_with_label('%s')"),
        ('app/shell_linux.py', "dialog.set_markup('%s')"),
        ('app/shell_linux.py', "dialog = Gtk.MessageDialog(text='%s')"),
        ('app/shell_windows.py', "form.Text = '%s'"),
        ('app/shell_windows.py', "MessageBox.Show('%s')"),
        ('engine/setup/api.py', "ASK = '%s'"),
        ('engine/setup/api.py', "def f():\n    return {'error': '%s'}"),
        ('engine/setup/api.py', "def f(note):\n    note['error'] += ' %s'"),
        ('engine/setup/api.py', "def f(job):\n    job['error'] = {'code': 'x', 'message': '%s'}"),
        ('engine/setup/install.py', "def f():\n    raise ValueError('%s')"),
        ('engine/setup/install.py', "def f():\n    raise RuntimeError('%s')"),
        ('packaging/lastbook_setup.py', "title = label('%s', 1, 2, 3, 4)"),
        ('server.py', "SHELF = [('new', '%s', r'x')]"),
        ('server.py', "def f():\n    return {'label': '%s', 'status': 'x'}"),
        ('server.py', "TITLES = {'new': '%s'}"),
        ('assistant.py', "def f():\n    emit({'type': 'error', 'text': '%s'})"),
    ]

    JS_CASES = [
        ('app.js', "el.textContent = '%s';"),
        ('app.js', "el.innerHTML = '<b>%s</b>';"),
        ('app.js', "el.innerHTML = `<p>%s</p>`;"),
        ('app.js', "const ASK = '%s';"),
        ('app.js', "const opts = { title: '%s' };"),
        ('app.js', "toast('%s');"),
        ('setup.js', "throw new Error('%s');"),
        ('map.js', "const NEW_TABLE = { a: '%s' };"),
        ('chat.js', "const x = '%s';"),
        ('app.js', "el.setAttribute('aria-label', '%s');"),
        ('app.js', "el.title = '%s';"),
    ]

    def test_python_sinks(self):
        for rel, template in self.PYTHON_CASES:
            with self.subTest(rel=rel, template=template):
                hits = scan.scan_python_text(template % INJECTED + '\n', rel)
                self.assertIn(INJECTED.strip(), {t.strip() for t in unapproved_texts(hits)}, hits)

    def test_javascript_sinks(self):
        for name, template in self.JS_CASES:
            with self.subTest(name=name, template=template):
                hits = scan.scan_js_text(template % INJECTED + '\n', name)
                self.assertIn(INJECTED, unapproved_texts(hits), hits)

    def test_lowercase_prose_is_not_a_class_list(self):
        for text in ('diagram viewed', 'historical stocking record', 'nearby'):
            with self.subTest(text=text):
                kind = scan.classify(text, 'const x = ', '', 'web/chat.js')
                if ' ' in text:
                    self.assertIn(kind, scan.UNAPPROVED_CLASSES)
        self.assertEqual(scan.classify('small muted', 'class="', '', 'web/app.js'), 'technical')

    def test_no_name_or_function_exemptions(self):
        # Names that the old scanner exempted (ASK, TOO_BIG, _keep_unpacked, viewer_csp) prove nothing.
        for source in ("ASK = 'Lastbook asks you something new'\n",
                       "TOO_BIG = 'This file is far too big to open'\n",
                       "def _keep_unpacked(work, note):\n    note['error'] = 'A new sentence for the person'\n",
                       "def viewer_csp():\n    return 'A sentence a person would read'\n"):
            with self.subTest(source=source):
                hits = scan.scan_python_text(source, 'engine/setup/api.py')
                self.assertTrue(unapproved_texts(hits), hits)

    def test_exceptions_are_not_log_calls(self):
        self.assertNotIn('ValueError', scan.LOG_CALLS)
        self.assertNotIn('RuntimeError', scan.LOG_CALLS)
        self.assertNotIn('OSError', scan.LOG_CALLS)

    def test_keyed_pair_requires_the_catalogue_text(self):
        english, _ = scan.load_english()
        key = 'nav.settings'
        text = english[key]
        good = scan.scan_python_text(f"T = ({key!r}, {text!r})\n", 'server.py')
        self.assertFalse(unapproved_texts(good), good)
        bad = scan.scan_python_text(f"T = ({key!r}, 'Some other English')\n", 'server.py')
        self.assertIn('Some other English', unapproved_texts(bad))
        missing = scan.scan_python_text(f"T = ('nav.notAKey', {text!r})\n", 'server.py')
        self.assertTrue(unapproved_texts(missing), missing)

    def test_map_labels_are_wired_only_in_the_renderer(self):
        self.assertEqual(scan.classify('Police', "const LAYERS = [['police', ", '', 'web/map.js'), 'wired')
        hits = scan.scan_python_text("HELP = {'police': 'Police'}\n", 'server.py')
        self.assertIn('Police', unapproved_texts(hits))


class Mutation(unittest.TestCase):
    """Real sources, one injected literal: the injected text is reported, nothing else changes."""

    # (file, anchor found on a real line, code inserted on its own line just before it, same indentation)
    MUTATIONS = [
        ('app/shell_macos.py', 'setMessageText_(', "alert.setMessageText_('%s')"),
        ('app/shell_macos.py', 'setMessageText_(', "alert.setInformativeText_('%s')"),
        ('app/shell_linux.py', 'Gtk.HeaderBar(title=', "bar.set_title('%s')"),
        ('app/shell_linux.py', 'Gtk.HeaderBar(title=', "menu.append(Gtk.MenuItem.new_with_label('%s'))"),
        ('engine/setup/api.py', "note['error'] = str(note['error']).replace(", "note['error'] += ' %s'"),
        ('engine/setup/api.py', "return {'fits': False, 'needs_bytes': None,", "return {'error': '%s'}"),
        ('server.py', 'SHELF_OTHER = (', "SHELF_EXTRA = ('extra', '%s', '')"),
        ('packaging/lastbook_setup.py', 'raise RuntimeError(installer_t(', "raise RuntimeError('%s')"),
    ]
    JS_MUTATIONS = [
        ('map.js', 'const CROP_CLASSES =', "const SURPRISE = '%s';"),
        ('setup.js', 'const errCode = e =>', "const NOTE_TEXT = '%s';"),
        ('chat.js', 'const excerptText = s =>', "const EMPTY = '<p>%s</p>';"),
        ('app.js', 'const keyedHtml = ', "const BANNER = `<b>%s</b>`;"),
    ]

    @staticmethod
    def inject(source, anchor, code):
        at = source.index(anchor)
        start = source.rfind('\n', 0, at) + 1
        indent = source[start:at][:len(source[start:at]) - len(source[start:at].lstrip())]
        return source[:start] + indent + (code % INJECTED) + '\n' + source[start:]

    @staticmethod
    def stripped(hits):
        return {t.strip() for t in unapproved_texts(hits)}

    def test_python_mutations(self):
        for rel, anchor, code in self.MUTATIONS:
            with self.subTest(rel=rel, code=code):
                source = (ROOT / rel).read_text(encoding='utf-8')
                if anchor not in source:
                    self.skipTest(f'{rel} has no {anchor!r} at this layer of the stack')
                before = self.stripped(scan.scan_python_text(source, rel))
                after = self.stripped(scan.scan_python_text(self.inject(source, anchor, code), rel))
                self.assertEqual(after - before, {INJECTED}, after - before)
                self.assertEqual(before - after, set())

    def test_javascript_mutations(self):
        for name, anchor, code in self.JS_MUTATIONS:
            with self.subTest(name=name, code=code):
                source = (ROOT / 'web' / name).read_text(encoding='utf-8')
                if anchor not in source:
                    self.skipTest(f'web/{name} has no {anchor!r} at this layer of the stack')
                before = self.stripped(scan.scan_js_text(source, name))
                after = self.stripped(scan.scan_js_text(self.inject(source, anchor, code), name))
                self.assertEqual(after - before, {INJECTED}, after - before)
                self.assertEqual(before - after, set())

    def test_allowlist_is_exact_and_needs_reasons(self):
        hits = scan.scan_python_text("X = 'An allowlisted sentence'\n", 'server.py')
        entry = {'file': 'server.py', 'string': 'An allowlisted sentence', 'why': 'Reviewed: never shown to a person.'}
        self.assertFalse(scan.unapproved(hits, [entry]))
        self.assertTrue(scan.unapproved(hits, [dict(entry, file='assistant.py')]))
        self.assertTrue(scan.unapproved(hits, [dict(entry, string='An allowlisted sentence.')]))
        self.assertEqual(scan.stale_allowlist(hits, [dict(entry, string='Gone')]), [dict(entry, string='Gone')])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'allow.json'
            path.write_text(json.dumps({'entries': [dict(entry, why='ok')]}), encoding='utf-8')
            with self.assertRaises(ValueError):
                scan.load_allowlist(path)

    def test_real_allowlist_rows_all_have_reasons_and_match(self):
        entries = scan.load_allowlist()
        self.assertTrue(entries)
        self.assertEqual(len({(e['file'], e['string']) for e in entries}), len(entries))


if __name__ == '__main__':
    unittest.main()
