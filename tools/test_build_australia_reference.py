"""Source integrity, offline build, local links and protection of existing libraries."""
import importlib.util
import json
from pathlib import Path
import re
import shutil
import socket
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

TOOL = Path(__file__).with_name('build_australia_reference.py')
spec = importlib.util.spec_from_file_location('au_builder', TOOL)
au = importlib.util.module_from_spec(spec); spec.loader.exec_module(au)


class Reference(unittest.TestCase):
    def test_real_sources_build_without_network_and_search_opens_the_same_text(self):
        with tempfile.TemporaryDirectory() as d, patch.object(socket, 'socket', side_effect=AssertionError('network')):
            out = Path(d) / 'LastbookData'
            count = au.build(out)
            lib = out / 'library-data'
            cat = {r['id']: r for r in json.loads((lib / 'catalog.json').read_text(encoding='utf-8'))}
            self.assertEqual(count, len(cat))
            with sqlite3.connect(lib / 'search.sqlite') as db:
                self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
                for query, expected in [('"Triple Zero"', 'au-emergency-calls'),
                                        ('livestock', 'nsw-rural-flood'), ('chemicals', 'qld-water'),
                                        ('"carbon monoxide"', 'vic-generator'),
                                        ('"fuel and rest stops"', 'au-remote-travel'),
                                        ('"No Rating"', 'au-fire-danger-ratings'),
                                        ('"cell broadcast"', 'au-ausalert'),
                                        ('"Critical Alerts"', 'au-ausalert-operational'),
                                        ('"heightened level"', 'nsw-warning-levels'),
                                        ('"downed powerline"', 'sa-storm-during'),
                                        ('"qualified electrician"', 'sa-flood-after'),
                                        ('"small animals"', 'sa-animal-planning'),
                                        ('"seasonal preparation"', 'sa-property-preparation'),
                                        ('"short range devices"', 'au-locating-devices'),
                                        ('"not be compatible"', 'vic-lcc27-faq'),
                                        ('"solar system"', 'vic-flood-energy'),
                                        ('"emergency assistance"', 'au-remote-work-risks'),
                                        ('"Spare fuel"', 'qld-road-trip'),
                                        ('"everyday tasks"', 'qld-inclusive-planning'),
                                        ('"continence aids"', 'qld-mobility-planning'),
                                        ('"tactile"', 'qld-vision-planning'),
                                        ('"SMS Relay"', 'au-accessible-calls')]:
                    ids = {r[0] for r in db.execute('SELECT doc_id FROM pages WHERE pages MATCH ?', (query,))}
                    self.assertIn(expected, ids)
                for uid, path, body in db.execute('SELECT doc_id,path,body FROM pages'):
                    self.assertEqual(path, cat[uid]['path'])
                    self.assertEqual(body, (lib / cat[uid]['text_path']).read_text(encoding='utf-8'))
                    self.assertEqual(au.digest((lib / path).read_bytes()), cat[uid]['sha256'])
            directory = json.loads((au.SOURCES / 'jurisdictions.json').read_text(encoding='utf-8'))
            self.assertEqual({r['id'] for r in directory['jurisdictions']},
                             {'AU-ACT', 'AU-NSW', 'AU-NT', 'AU-QLD', 'AU-SA', 'AU-TAS', 'AU-VIC', 'AU-WA'})
            self.assertEqual(cat['au-remote-travel']['license'], 'CC-BY-3.0-AU')
            self.assertEqual(cat['vic-generator']['license'], 'CC-BY-4.0')

    def test_new_sources_keep_connector_questions_and_flatten_only_trip_controls(self):
        entries = {r['id']: r for r in au.checked_sources()[0]['sources']}
        faq = (au.SOURCES / entries['vic-lcc27-faq']['snapshot']).read_text(encoding='utf-8')
        self.assertEqual(faq.count('<h3>'), 9)
        self.assertIn('If I buy a gas appliance with the new connection', faq)
        self.assertIn('Adaptors must not be used', faq)
        trip = (au.SOURCES / entries['qld-road-trip']['snapshot']).read_text(encoding='utf-8')
        self.assertEqual(trip.count('<h4>'), 27)
        self.assertEqual(trip.count('<h4>Food and water</h4>'), 1)
        self.assertIn('20 litres', trip)
        self.assertNotIn('48.00%', trip)
        self.assertNotIn('Hover over', trip)
        audit = json.loads((au.SOURCES / 'ENERGY-REMOTE-SOURCE-AUDIT-20261126.json').read_text(encoding='utf-8'))
        contacts = next(s for s in audit['selections'] if s['id'] == 'vic-gas-emergencies')['contact_table_display']
        source = contacts['source_matrix']
        for col, distributor in enumerate(source[0][1:], 1):
            self.assertEqual(contacts['displayed_pairs'][distributor], [[row[0], row[col]] for row in source[1:]])
        gas = (au.SOURCES / entries['vic-gas-emergencies']['snapshot']).read_text(encoding='utf-8')
        for distributor, pairs in contacts['displayed_pairs'].items():
            section = gas.split('<h3>' + distributor + '</h3>', 1)[1].split('</dl>', 1)[0]
            def texts(tag):
                values = []
                for fragment in re.findall('<' + tag + '>(.*?)</' + tag + '>', section, re.S):
                    page = au.Page(); page.feed(fragment); page.close()
                    values.append(re.sub(r'\s+', ' ', ''.join(page.text)).strip())
                return values
            self.assertEqual(list(map(list, zip(texts('dt'), texts('dd')))), pairs)

    def test_accessibility_selections_keep_all_decision_row_associations(self):
        entries = {r['id']: r for r in au.checked_sources()[0]['sources']}
        audit = json.loads((au.SOURCES / 'ACCESSIBILITY-SOURCE-AUDIT-20261126.json').read_text(encoding='utf-8'))

        def text(fragment):
            page = au.Page(); page.feed(fragment); page.close()
            return re.sub(r'\s+', ' ', ''.join(page.text)).strip()

        for selection in audit['selections']:
            body = (au.SOURCES / entries[selection['id']]['snapshot']).read_text(encoding='utf-8')
            matrix = selection['decision_table_source_matrix']
            if matrix:
                sections = re.findall(r'<h3>([^<]+)</h3>\s*<dl>(.*?)</dl>', body, re.S)
                self.assertEqual(len(sections), 5)
                for (heading, values), row in zip(sections, matrix[1:]):
                    self.assertEqual(text(heading), row[0])
                    labels = [text(v) for v in re.findall(r'<dt>(.*?)</dt>', values, re.S)]
                    answers = [text(v) for v in re.findall(r'<dd>(.*?)</dd>', values, re.S)]
                    self.assertEqual(list(zip(labels, answers)), list(zip(matrix[0][1:], row[1:])))
                self.assertNotIn('<table', body)
                tips = re.search(r'<ol[^>]*>(.*?)</ol>', body, re.S)
                self.assertIsNotNone(tips)
                self.assertEqual(len(re.findall(r'<li(?:\s|>)', tips.group(1))), 10)
        inclusive = (au.SOURCES / entries['qld-inclusive-planning']['snapshot']).read_text(encoding='utf-8')
        for phrase in ['What you do best', 'What you have already done', 'What might be hard',
                       'What you can do to fix', 'Your living situation', 'Your social network',
                       'Ways you get around', 'Assistance animals', 'Personal Support',
                       'Management of Health', 'Assistive Technology']:
            self.assertIn(phrase, inclusive)
        self.assertNotIn('Uncle Willie', inclusive)
        self.assertNotIn('1300 555 727', inclusive)
        calls = (au.SOURCES / entries['au-accessible-calls']['snapshot']).read_text(encoding='utf-8')
        self.assertIn('106. This requires a TTY/textphone', calls)
        self.assertIn('not an ordinary mobile SMS number', calls)
        self.assertIn('0423 677 767', calls)
        self.assertEqual(entries['au-accessible-calls']['license'], 'CC0-1.0')

    def test_existing_output_is_untouched(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d); sentinel = out / 'catalog.json'; sentinel.write_text('keep me', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'already exists'):
                au.build(out)
            self.assertEqual(sentinel.read_text(encoding='utf-8'), 'keep me')

    def test_changed_source_cannot_be_built(self):
        with tempfile.TemporaryDirectory() as d:
            sources = Path(d) / 'sources'; shutil.copytree(au.SOURCES, sources)
            (sources / 'sources/au-emergency-calls.html').write_text('changed source', encoding='utf-8')
            out = Path(d) / 'LastbookData'
            with self.assertRaisesRegex(ValueError, 'Snapshot changed'):
                au.build(out, sources)
            self.assertFalse(out.exists())

    def test_active_content_and_external_or_broken_links_are_refused(self):
        for bad in ['<script>x</script>', '<img src="https://example.invalid/x">',
                    '<a href="https://example.invalid">x</a>', '<p onclick="x()">x</p>']:
            with self.assertRaises(ValueError):
                au.Page().feed(bad)
        with tempfile.TemporaryDirectory() as d:
            sources = Path(d) / 'sources'; shutil.copytree(au.SOURCES, sources)
            m = json.loads((sources / 'manifest.json').read_text(encoding='utf-8'))
            r = m['sources'][0]; file = sources / r['snapshot']
            data = file.read_bytes() + b'<a href="/pages/au/missing.html">missing</a>'
            file.write_bytes(data); r.update(bytes=len(data), sha256=au.digest(data))
            (sources / 'manifest.json').write_text(json.dumps(m), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Unbundled local link'):
                au.checked_sources(sources)


if __name__ == '__main__':
    unittest.main()
