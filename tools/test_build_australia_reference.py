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
                                        ('"cyanuric acid"', 'nsw-rainwater-tanks'),
                                        ('"radiological quality"', 'nsw-groundwater'),
                                        ('"structural integrity"', 'nsw-tanks-after-flood'),
                                        ('"Boiling will not make"', 'nsw-nonpotable-water'),
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
                                        ('"SMS Relay"', 'au-accessible-calls'),
                                        ('"Jervis Bay"', 'au-jurisdictions'),
                                        ('"West Island Clinic"', 'au-jurisdictions'),
                                        ('"Australian Antarctic Territory"', 'au-jurisdictions'),
                                        ('"different routes"', 'vic-cfa-fire-risk'),
                                        ('"expanding file"', 'vic-cfa-prepare-leave'),
                                        ('"20 watch zones"', 'vic-cfa-warnings'),
                                        ('"frosted windows"', 'vic-cfa-during-fire')]:
                    ids = {r[0] for r in db.execute('SELECT doc_id FROM pages WHERE pages MATCH ?', (query,))}
                    self.assertIn(expected, ids)
                for uid, path, body in db.execute('SELECT doc_id,path,body FROM pages'):
                    self.assertEqual(path, cat[uid]['path'])
                    self.assertEqual(body, (lib / cat[uid]['text_path']).read_text(encoding='utf-8'))
                    self.assertEqual(au.digest((lib / path).read_bytes()), cat[uid]['sha256'])
            directory = json.loads((au.SOURCES / 'jurisdictions.json').read_text(encoding='utf-8'))
            self.assertEqual({r['id'] for r in directory['jurisdictions']},
                             {'AU-ACT', 'AU-NSW', 'AU-NT', 'AU-QLD', 'AU-SA', 'AU-TAS', 'AU-VIC', 'AU-WA',
                              'AU-JBT', 'AU-CX', 'AU-CC', 'AU-NF', 'AU-HM', 'AU-AC', 'AU-CSI', 'AU-AAT'})
            self.assertEqual(cat['au-remote-travel']['license'], 'CC-BY-3.0-AU')
            self.assertEqual(cat['vic-generator']['license'], 'CC-BY-4.0')

    def test_water_sources_keep_full_faq_answers_units_dated_contacts_and_treatment_limits(self):
        entries = {r['id']: r for r in au.checked_sources()[0]['sources']}
        audit = json.loads((au.SOURCES / 'WATER-SOURCE-AUDIT-20261126.json').read_text(encoding='utf-8'))
        def body(uid):
            return (au.SOURCES / entries[uid]['snapshot']).read_text(encoding='utf-8')
        def plain(text):
            parser = au.Page(); parser.feed(text); parser.close()
            return re.sub(r'\s+', ' ', ''.join(parser.text)).strip()
        rain = body('nsw-rainwater-tanks')
        pairs = re.findall(r'<h3>(.*?)</h3>(.*?)(?=<h3>|<h2>Useful links|</body>)', rain, re.S)
        self.assertEqual(len(pairs), 19)
        # Full independently frozen source answers,not merely the question labels.
        for (question, answer), expected in zip(pairs, audit['rainwater_faq']):
            self.assertEqual([re.sub(r'\s+([.,;:!?])', r'\1', plain(x)) for x in (question, answer)],
                             [re.sub(r'\s+([.,;:!?])', r'\1', x) for x in expected])
        for exact in ['calcium hypochlorite, 65% available chlorine',
                      'sodium hypochlorite, 12.5% available chlorine',
                      '7 grams of calcium hypochlorite',
                      '40 millilitres of sodium hypochlorite per 1000 litres',
                      'minimum of two hours', 'at least 0.5 milligrams per litre',
                      '30 minutes after the chlorine is added',
                      'Do not pour water into chlorine; always add chlorine to water.',
                      'at least 24 hours', '2 to 3 minutes', '10 seconds', '48 hours']:
            self.assertIn(exact, plain(rain))
        self.assertIn('Source variation retained.', rain)
        self.assertIn('loss of consciousness', rain.lower())
        bore = body('nsw-groundwater')
        for exact in ['250 metres', '30 degrees Celsius', '25 degrees Celsius',
                      'testing and appropriate treatment including disinfection',
                      'microbiological, chemical and radiological', '2022-10-18',
                      'Department of Industry (DoI) Water on 1800 353 104']:
            self.assertIn(exact, plain(bore))
        flood = plain(body('nsw-tanks-after-flood'))
        for exact in ['licensed electrician', 'structural integrity',
                      'before the surrounding ground has dried out',
                      'qualified, professional tank cleaner',
                      'refilled with clean safe water', 'Rinse, reassemble']:
            self.assertIn(exact, flood)
        nonpotable = plain(body('nsw-nonpotable-water'))
        self.assertIn('Boiling will not make the supply safe.', nonpotable)
        self.assertIn('chemical or radiological', nonpotable)
        self.assertIn("'Do not use'", nonpotable)
        for uid, date in [('nsw-rainwater-tanks', '2026-09-11'),
                          ('nsw-groundwater', '2022-10-18'),
                          ('nsw-tanks-after-flood', '2023-04-04'),
                          ('nsw-nonpotable-water', '2026-04-21')]:
            self.assertEqual(entries[uid]['source_updated'], date)
            self.assertEqual(entries[uid]['license'], 'CC-BY-4.0')
            self.assertIn('Source current as at ' + date, entries[uid]['edition'])
        rights = plain(body('nsw-health-copyright'))
        self.assertIn('All NSW Health material on this website is licensed', rights)
        self.assertIn('any third party material unless expressly stated', rights)
        self.assertIn('Request for Copyright Permission form', rights)

    def test_cfa_adaptation_preserves_tables_checklists_and_last_resort_conditions(self):
        entries = {r['id']: r for r in au.checked_sources()[0]['sources']}
        audit = json.loads((au.SOURCES / 'CFA-SURVIVAL-SOURCE-AUDIT-20261126.json').read_text(encoding='utf-8'))
        def body(uid):
            return (au.SOURCES / entries[uid]['snapshot']).read_text(encoding='utf-8')
        def plain(fragment):
            page = au.Page(); page.feed(fragment); page.close()
            return re.sub(r'\s+', ' ', ''.join(page.text)).strip()
        self.assertEqual(audit['reviewed_block_count'], 359)
        self.assertEqual(audit['visual_review']['rendered_pages'], list(range(1, 21)))
        for selection in audit['selections']:
            r = entries[selection['id']]
            self.assertEqual(r['raw_sha256'], 'de37f989a65b529351f3fe87685bc70a1d84a5d543cb5fef905e5458f90d1918')
            self.assertEqual(r['source_pages'], selection['source_pages'])
            self.assertEqual(r['source_edition'], 'Version 6, July 2022')
            self.assertEqual(r['edition'], 'Version 6, July 2022')
            self.assertEqual(r['license'], 'CC-BY-4.0')
        risk = body('vic-cfa-fire-risk')
        for rating, meaning, action in audit['rating_table']['rows']:
            values = re.search(r'<h4>' + rating + r'</h4>\s*<dl>(.*?)</dl>', risk, re.S).group(1)
            self.assertEqual([plain(x) for x in re.findall(r'<dt>(.*?)</dt>', values, re.S)], audit['rating_table']['columns'])
            self.assertEqual([plain(x) for x in re.findall(r'<dd>(.*?)</dd>', values, re.S)],
                             [' '.join(meaning), ' '.join(action)])
        decisions = re.search(r'<ol>(.*?)</ol>', risk, re.S).group(1)
        self.assertEqual(decisions.count('<li>'), 10)
        prep = body('vic-cfa-prepare-leave')
        before = prep.split('<h3>Before summer</h3>', 1)[1].split('</ul>', 1)[0]
        self.assertEqual(before.count('<li>'), 12)
        self.assertIn('only if you have time.', prep)
        warnings = body('vic-cfa-warnings')
        rows = re.findall(r'<h5>(.*?)</h5><dl><dt>WHAT TO DO</dt><dd>(.*?)</dd></dl>', warnings, re.S)
        self.assertEqual([[plain(x), plain(y)] for x,y in rows], audit['monitoring_table']['rows'])
        self.assertIn('/pages/au/au-ausalert-operational.html', warnings)
        self.assertIn('July 2022', warnings)
        during = body('vic-cfa-during-fire')
        for warning in ['including one direct exit to the outside', 'It may not be immediately safe to go outside.',
                        'are not able to turn around and drive to safety.', 'can result in serious injury or death.',
                        'YOUR SAFETY IS NOT GUARANTEED', 'HIGH RISK OF TRAUMA, INJURY OR DEATH.']:
            self.assertIn(warning, during)
        self.assertIn('does not recommend defending your home', during)
        self.assertIn('Bushifre Place of Last Resort', during)  # printed source spelling
        self.assertNotIn('<table', risk + warnings)

    def test_territory_directory_preserves_service_scope_dates_and_contact_associations(self):
        entries = {r['id']: r for r in au.checked_sources()[0]['sources']}
        source = (au.SOURCES / entries['au-jurisdictions']['snapshot']).read_text(encoding='utf-8')
        directory = json.loads((au.SOURCES / 'jurisdictions.json').read_text(encoding='utf-8'))
        regions = {r['id']: r for r in directory['jurisdictions']}
        parts = re.split(r'<h3>(.*?)</h3>', source)
        sections = dict(zip(parts[1::2], parts[2::2]))
        self.assertEqual(len(sections), 16)
        self.assertEqual(regions['AU-JBT']['classification'], 'internal-territory')
        self.assertEqual(regions['AU-JBT']['source_published'], '2023-08-28')
        self.assertEqual(regions['AU-JBT']['ses_storm_flood'], '132 500')
        self.assertIn('<dd>132 500</dd>', sections['Jervis Bay Territory'])
        self.assertIn('<dd>2023-08-28</dd>', sections['Jervis Bay Territory'])
        for uid in ['AU-ACT','AU-NSW','AU-NT','AU-QLD','AU-SA','AU-TAS','AU-VIC','AU-WA']:
            self.assertEqual(regions[uid]['checked'], '2026-11-17')
        for uid in ['AU-CX','AU-CC','AU-NF']:
            self.assertEqual(regions[uid]['life_threatening'], '000')
            self.assertIsNone(regions[uid]['ses_storm_flood'])
            self.assertNotIn('<dd>132 500</dd>', sections[regions[uid]['title']])
        for uid in ['AU-HM','AU-AC','AU-CSI','AU-AAT']:
            self.assertIsNone(regions[uid]['life_threatening'])
            self.assertIsNone(regions[uid]['ses_storm_flood'])
            self.assertNotIn('<dd>000</dd>', sections[regions[uid]['title']])
        for title, label, phone in [('Christmas Island','Christmas Island Health Centre','08 9164 8333'),
                                    ('Cocos (Keeling) Islands','West Island Clinic','08 9162 6655'),
                                    ('Cocos (Keeling) Islands','Home Island Clinic','08 9162 7609')]:
            self.assertIn('<dt>' + label + ' — health-service contact</dt><dd>' + phone + '</dd>', sections[title])
        self.assertIn('Police emergency (official Cocos boating guide)', sections['Cocos (Keeling) Islands'])
        self.assertEqual(entries['au-jurisdictions']['license'], 'CC-BY-4.0')

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
