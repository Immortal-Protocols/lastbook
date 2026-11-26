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
from collections import Counter
from unittest.mock import patch

TOOL = Path(__file__).with_name('build_australia_reference.py')
spec = importlib.util.spec_from_file_location('au_builder', TOOL)
au = importlib.util.module_from_spec(spec); spec.loader.exec_module(au)


class Reference(unittest.TestCase):
    def test_built_guides_follow_moved_sources_with_catalogue_left_intact(self):
        import server
        from tools.validate_topics import items
        with tempfile.TemporaryDirectory() as d, patch.object(socket, 'socket', side_effect=AssertionError('network')):
            out = Path(d) / 'LastbookData'
            au.build(out)
            lib = out / 'library-data'
            catalogue = lib / 'catalog.json'
            original_bytes, original_mtime = catalogue.read_bytes(), catalogue.stat().st_mtime_ns
            with patch.object(server, 'APP', au.ROOT), patch.object(server, 'LIB', lib), \
                 patch.object(server, '_cat', {'mtime': None}), patch.object(server, 'zim_names', return_value=[]):
                def resolve():
                    return {t['id']: t for t in server.topics_resolved()}
                def links(guides):
                    return [r['doc'] for g in guides.values() for _, r in items(g) if r.get('doc')]
                present = resolve()  # Warm the real catalogue cache, not a mocked dictionary.
                regional = {'au-household', 'au-rural', 'au-health'}
                self.assertTrue(regional <= present.keys())
                self.assertIn('nsw-bat-lyssavirus', links(present))
                source = lib / 'pages/au/nsw-bat-lyssavirus.html'
                held = Path(d) / 'bat.html'
                source.rename(held)
                without_one = resolve()
                self.assertTrue(regional <= without_one.keys())
                self.assertNotIn('nsw-bat-lyssavirus', links(without_one))
                held.rename(source)
                self.assertEqual(resolve(), present)
                folder, moved = lib / 'pages/au', Path(d) / 'moved-au'
                folder.rename(moved)
                missing = resolve()
                self.assertFalse(regional & missing.keys())
                self.assertFalse(links(missing))
                self.assertEqual(set(missing), set(present) - regional)
                for gid, guide in missing.items():
                    self.assertEqual([r['text'] for r in guide['limits']],
                                     [r['text'] for r in present[gid]['limits']])
                folder.parent.mkdir(parents=True, exist_ok=True)
                moved.rename(folder)
                self.assertEqual(resolve(), present)
                self.assertEqual(catalogue.read_bytes(), original_bytes)
                self.assertEqual(catalogue.stat().st_mtime_ns, original_mtime)

    def test_bat_factsheet_and_reuse_readings_preserve_reviewed_source_blocks(self):
        audit = json.loads((au.SOURCES / 'VERBATIM-REUSE-AUDIT-20261127.json').read_text())
        records = {r['id']: r for r in au.checked_sources()[0]['sources']}
        self.assertEqual(audit['counts'], dict(public_records=124, new_practical=1, new_rights=2, guide_references=10))
        for selection in audit['selections']:
            r = records[selection['id']]
            html = (au.SOURCES / r['snapshot']).read_text()
            body = html.split('<hr>', 1)[1].split('</body>', 1)[0]
            self.assertEqual(au.source_text(body), au.source_text('\n'.join(x['text'] for x in selection['source_blocks'])))
            self.assertEqual(r['sha256'], selection['reader_sha256'])
            self.assertEqual(r['raw_sha256'], selection['raw']['raw_sha256'])
        self.assertEqual(records['nsw-bat-lyssavirus']['source_updated'], '2025-11-27')
        medical = next(s for s in audit['selections'] if s['id'] == 'nsw-bat-lyssavirus')
        original = ' '.join(x['text'] for x in medical['source_blocks'])
        self.assertIn('Even if previously vaccinated', original)
        self.assertIn('It might not always be clear', original)
        self.assertIn('Only four cases', original)
        self.assertIn('the three known human cases', original)
        self.assertNotIn('delayed-presentation', json.dumps(audit['guide_placements']))
        html = (au.SOURCES / records['nsw-bat-lyssavirus']['snapshot']).read_text()
        self.assertIn(audit['clinical_selection']['source_count_caveat'], html.split('<hr>', 1)[0])
        self.assertEqual(records['nsw-bat-lyssavirus']['copyright_source'], records['nsw-health-copyright']['source_url'])
        self.assertEqual(records['cc-by-nd-legalcode']['license'], 'CC0-1.0')
        legal = (au.SOURCES / records['cc-by-nd-legalcode']['snapshot']).read_text()
        for section in range(1, 9):
            self.assertIn('Section ' + str(section), legal)
        self.assertIn('Creative Commons is not a party', legal)
        numbering = [re.search(r'\btype="([aAiI1])"', tag) for tag in re.findall(r'<ol\b[^>]*>', legal)]
        self.assertEqual([m.group(1) if m else None for m in numbering], audit['legal_ordered_list_types'])
        self.assertEqual([r['id'] for r in records.values() if r['license'] == 'CC-BY-ND-4.0'], ['qld-health-copyright'])
        self.assertNotIn('qpic-ticks', records)
        self.assertNotIn('qpic-bats', records)
        self.assertIn('remote-removal', audit['clinical_selection']['qpic_ticks'])

    def nd_fixture(self, directory):
        source = Path(directory) / 'source'
        shutil.copytree(au.SOURCES, source)
        manifest = json.loads((source / 'manifest.json').read_text())
        record = next(r for r in manifest['sources'] if r['id'] == 'qld-health-copyright')
        return source, manifest, record

    def nd_save(self, source, manifest, record, html=None):
        if html is not None:
            data = html.encode()
            (source / record['snapshot']).write_bytes(data)
            record.update(bytes=len(data), sha256=au.digest(data))
        (source / 'manifest.json').write_text(json.dumps(manifest))

    def test_nd_body_edit_is_refused_even_when_the_snapshot_hash_is_updated(self):
        with tempfile.TemporaryDirectory() as d:
            source, manifest, r = self.nd_fixture(d)
            html = (source / r['snapshot']).read_text()
            self.assertIn('If you alter or adapt', html)
            html = html.replace('If you alter or adapt', 'You may freely alter or adapt')
            self.nd_save(source, manifest, r, html)
            with self.assertRaisesRegex(ValueError, 'body changed'):
                au.checked_sources(source)

    def test_nd_text_review_is_required_even_if_the_body_hash_is_updated(self):
        with tempfile.TemporaryDirectory() as d:
            source, manifest, r = self.nd_fixture(d)
            html = (source / r['snapshot']).read_text().replace('If you alter or adapt', 'You may freely alter or adapt')
            audit_path = source / r['verbatim_audit']; audit = json.loads(audit_path.read_text())
            body = html.split(au.VERBATIM_START, 1)[1].split(au.VERBATIM_END, 1)[0]
            audit['records'][r['id']]['reader_body_sha256'] = au.digest(body.encode())
            audit_path.write_text(json.dumps(audit))
            self.nd_save(source, manifest, r, html)
            with self.assertRaisesRegex(ValueError, 'body changed'):
                au.checked_sources(source)

    def test_nd_requires_explicit_mode_safe_audit_and_matching_provenance(self):
        for key, value in [('reuse_mode', ''), ('verbatim_audit', '../outside.json'), ('verbatim_audit', 4),
                           ('raw_sha256', '0' * 64), ('source_url', 'https://example.invalid/source')]:
            with self.subTest(key=key, value=value), tempfile.TemporaryDirectory() as d:
                source, manifest, r = self.nd_fixture(d)
                r[key] = value
                self.nd_save(source, manifest, r)
                with self.assertRaisesRegex(ValueError, 'audit|provenance'):
                    au.checked_sources(source)

    def test_nd_missing_or_duplicate_markers_and_malformed_audits_are_refused(self):
        for changed in ['', au.VERBATIM_START + au.VERBATIM_START]:
            with tempfile.TemporaryDirectory() as d:
                source, manifest, r = self.nd_fixture(d)
                html = (source / r['snapshot']).read_text().replace(au.VERBATIM_START, changed)
                self.nd_save(source, manifest, r, html)
                with self.assertRaisesRegex(ValueError, 'markers'):
                    au.checked_sources(source)
        for bad in [[], {'records': []}]:
            with tempfile.TemporaryDirectory() as d:
                source, manifest, r = self.nd_fixture(d)
                (source / r['verbatim_audit']).write_text(json.dumps(bad))
                with self.assertRaisesRegex(ValueError, 'Invalid unchanged-source audit'):
                    au.checked_sources(source)

    def test_bat_placements_preserve_original_guides_and_equal_household_rural_access(self):
        import copy
        audit = json.loads((au.SOURCES / 'VERBATIM-REUSE-AUDIT-20261127.json').read_text())
        guides = {g: json.loads((au.ROOT / 'content/topics' / (g + '.json')).read_text()) for g in audit['baseline_guides']}
        self.assertEqual(len(audit['guide_placements']), 10)
        for gid, original in guides.items():
            guide = copy.deepcopy(original)
            if gid == 'hurt':
                extension = json.loads((au.ROOT / 'docs/AUSTRALIA-ORDINARY-FIRST-AID-ROUTING-20261127.json').read_text())
                later = {p['reference']['doc'] for p in extension['placements']}
                for choice in guide['choices']:
                    choice['read'] = [r for r in choice['read'] if r.get('doc') not in later]
            # Compare the historical bat increment after removing the later,
            # separately audited community-planning addition.
            guide['choices'] = [c for c in guide['choices'] if c['id'] != 'aboriginal-planning']
            for key in ['prepare', 'learn']:
                if key in guide:
                    guide[key] = [r for r in guide[key] if r.get('doc') != 'nsw-aboriginal-planning']
            for key in ['prepare', 'learn']:
                if key in guide:
                    guide[key] = [r for r in guide[key] if r.get('doc') != 'nsw-bat-lyssavirus']
            guide['choices'] = [c for c in guide['choices'] if c['id'] != 'bat-exposure']
            for choice in guide['choices']:
                choice['read'] = [r for r in choice.get('read', []) if r.get('doc') != 'nsw-bat-lyssavirus']
            self.assertEqual(au.digest(json.dumps(guide, sort_keys=True).encode()), audit['baseline_guides'][gid])
        household = [x for x in audit['guide_placements'] if x['guide'] == 'au-household']
        rural = [x for x in audit['guide_placements'] if x['guide'] == 'au-rural']
        self.assertEqual([{k:v for k,v in x.items() if k != 'guide'} for x in household],
                         [{k:v for k,v in x.items() if k != 'guide'} for x in rural])

    def test_bat_cards_use_existing_individual_record_availability(self):
        import server
        from tools.validate_topics import items
        audit = json.loads((au.SOURCES / 'VERBATIM-REUSE-AUDIT-20261127.json').read_text())
        guides = [json.loads((au.ROOT / 'content/topics' / (g + '.json')).read_text()) for g in audit['baseline_guides']]
        records = {r['id']: r for r in au.checked_sources()[0]['sources']}
        base = {r['doc']: dict(id=r['doc'], title='Fixture', path='pages/base.html', kind='html')
                for g in guides for _, r in items(g) if r.get('doc') and r['doc'] != 'nsw-bat-lyssavirus'}
        # Include required hub records so this tests card filtering within existing guides.
        base.update({r: records[r] for g in guides for r in g.get('requires_docs', [])})
        for available, expected in [({}, 0), ({'nsw-bat-lyssavirus': records['nsw-bat-lyssavirus']}, 10)]:
            with tempfile.TemporaryDirectory() as d, patch.object(server, 'LIB', Path(d)), \
                 patch.object(server, 'APP', au.ROOT), patch.object(server, 'topics', return_value=guides), \
                 patch.object(server, 'zim_names', return_value=[]), \
                 patch.object(server, 'catalog', return_value={'by_id': {**base, **available}}), \
                 patch.object(socket, 'socket', side_effect=AssertionError('network')):
                for record in {**base, **available}.values():
                    path = Path(d) / record['path']; path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text('Source fixture', encoding='utf-8')
                resolved = server.topics_resolved()
            refs = [r for g in resolved for _, r in items(g) if r.get('doc') == 'nsw-bat-lyssavirus']
            self.assertEqual(len(refs), expected)
            for ref in refs:
                self.assertEqual(ref['src']['id'], 'nsw-bat-lyssavirus')

    def test_ordinary_need_links_preserve_existing_choices_and_source_boundaries(self):
        audit = json.loads((au.ROOT / 'docs/AUSTRALIA-GUIDE-LINKS-20261127.json').read_text())
        entries = {r['id']: r for r in au.checked_sources()[0]['sources']}
        self.assertEqual(audit['counts'], {'guides': 7, 'choices': 25, 'references': 40})
        for gid, digest in audit['baseline_topic_sha256'].items():
            guide = json.loads((au.ROOT / 'content/topics' / (gid + '.json')).read_text())
            for choice in guide['choices']:
                added = [p for p in audit['placements'] if p['guide'] == gid and p['choice'] == choice['id']]
                self.assertEqual(choice.get('read', [])[:len(added)], [p['reference'] for p in added])
                for placement in added:
                    ref = placement['reference']; record = entries[ref['doc']]
                    self.assertEqual(record['sha256'], placement['source_sha256'])
                    self.assertTrue(ref['label'].startswith(record['jurisdiction'] + ': '))
                if added:
                    choice['read'] = choice['read'][len(added):]
            # Frozen pre-change guide protects labels, hints, ranking fields and all original references.
            self.assertEqual(au.digest(json.dumps(guide, sort_keys=True).encode()), digest)
        wastewater = next(p['reference'] for p in audit['placements'] if p['reference']['doc'] == 'nsw-flooded-wastewater')
        self.assertIn('does not provide a sewer-backup cleanup procedure', wastewater['note'])
        tank = next(p['reference'] for p in audit['placements'] if p['reference']['doc'] == 'nsw-tanks-after-flood')
        self.assertIn('not a treatment method for chemically contaminated river water', tank['note'])

    def test_ordinary_need_links_resolve_only_installed_australian_sources(self):
        import copy
        import server
        audit = json.loads((au.ROOT / 'docs/AUSTRALIA-GUIDE-LINKS-20261127.json').read_text())
        records = au.checked_sources()[0]['sources']
        australian = {r['id']: r for r in records}
        topics = [json.loads(p.read_text()) for p in sorted((au.ROOT / 'content/topics').glob('*.json'))]
        # Ordinary source fixtures let the test verify full fallback order, not just an empty guide.
        from tools.validate_topics import items
        base = {r['doc']: dict(id=r['doc'], title='Baseline source', path='pages/baseline.html', kind='html')
                for t in topics for _, r in items(t)
                if r.get('doc') and r['doc'] not in australian and not r['doc'].startswith('personal-au-')}
        originals = copy.deepcopy(topics)
        for t in originals:
            for c in t.get('choices', []):
                count = sum(p['guide'] == t['id'] and p['choice'] == c['id'] for p in audit['placements'])
                if count:
                    c['read'] = c['read'][count:]
        def resolve(available, source=topics):
            cat = {'by_id': {**base, **available}, 'by_path': {}, 'video_tx': {}, 'thumbs': {}}
            with tempfile.TemporaryDirectory() as d, patch.object(server, 'LIB', Path(d)), \
                 patch.object(server, 'APP', au.ROOT), patch.object(server, 'topics', return_value=source), \
                 patch.object(server, 'catalog', return_value=cat), patch.object(server, 'zim_names', return_value=[]), \
                 patch.object(socket, 'socket', side_effect=AssertionError('network')):
                for record in cat['by_id'].values():
                    path = Path(d) / record['path']; path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text('Source fixture', encoding='utf-8')
                return {t['id']: t for t in server.topics_resolved()}
        absent = resolve({}); baseline = resolve({}, originals)
        for gid in audit['baseline_topic_sha256']:
            self.assertEqual(absent[gid], baseline[gid])
        self.assertNotIn('au-household', absent)
        for available in [australian, {'nsw-smoke-protection': australian['nsw-smoke-protection']}]:
            resolved = resolve(available)
            for placement in audit['placements']:
                guide = resolved[placement['guide']]
                choice = next(c for c in guide['choices'] if c['id'] == placement['choice'])
                uid = placement['reference']['doc']
                matches = [r for r in choice['read'] if r.get('doc') == uid]
                self.assertEqual(len(matches), int(uid in available))
                if matches:
                    self.assertEqual(matches[0]['src']['id'], uid)
                    self.assertEqual(matches[0]['src']['path'], available[uid]['path'])

    def test_smoke_and_wastewater_readings_keep_full_conditions_and_equal_access(self):
        entries = {r['id']: r for r in au.checked_sources()[0]['sources']}
        audit = json.loads((au.SOURCES / 'SMOKE-SANITATION-SOURCE-AUDIT-20261127.json').read_text())
        def plain(html):
            page = au.Page(); page.feed(html); page.close()
            return re.sub(r'\s+', '', ''.join(page.text))
        bodies = {}
        for selection in audit['selections']:
            uid = selection['id']; record = entries[uid]
            html = (au.SOURCES / record['snapshot']).read_text()
            body = html.split('<hr>', 1)[1].split('</body>', 1)[0]
            self.assertEqual(plain(body), re.sub(r'\s+', '', ''.join(b['source_text'] for b in selection['blocks'])))
            self.assertEqual(record['raw_sha256'], selection['raw']['raw_sha256'])
            self.assertEqual(record['source_updated'], selection['source_updated'])
            self.assertEqual(record['license'], 'CC-BY-4.0')
            self.assertIn('/pages/au/nsw-health-copyright.html', html)
            bodies[uid] = body
        protection = plain(bodies['nsw-smoke-protection'])
        for condition in ['open them when air quality improves', 'do not use evaporative coolers',
                          'small, well-sealed areas', 'Surgical and cloth masks do not protect you from smoke.',
                          'trouble breathing or chest pain or tightness', '1800 633 422']:
            self.assertIn(re.sub(r'\s+', '', condition), protection)
        mask = plain(bodies['nsw-p2-n95-masks'])
        for condition in ['Speak to your doctor before wearing one.',
                          'remove the mask and go indoors or to a place where there is better air quality.',
                          'not designed to fit the smaller face of children', 'It becomes moist',
                          'It becomes hard to breathe through', 'replaced after each use']:
            self.assertIn(re.sub(r'\s+', '', condition), mask)
        high = bodies['nsw-smoke-higher-risk']
        pairs = re.findall(r'<h3>(.*?)</h3>(.*?)(?=<h3>|<h2>)', high, re.S)
        self.assertEqual(len(pairs), 5)
        self.assertEqual([[plain(q), plain(a)] for q,a in pairs],
                         [[re.sub(r'\s+', '', v) for v in row] for row in audit['higher_risk_faq']])
        wastewater = plain(bodies['nsw-flooded-wastewater'])
        for condition in ['do not use any toilets, laundry, kitchen, bathroom or clean-up equipment',
                          'inspected and approved for use by the local council',
                          'provided the tank is not damaged', 'do not use the system until it is repaired or replaced',
                          'only leave the tank empty for a short time',
                          'Reduce water use as much as possible until the system is inspected and repaired',
                          'If possible avoid using automatic clothes washers and dishwashers']:
            self.assertIn(re.sub(r'\s+', '', condition), wastewater)
        self.assertIn('<ul>', bodies['nsw-flooded-wastewater'].split('Reduce water use',1)[1].split('</li>\n</ul>',1)[0])
        for gid in ['au-household', 'au-rural']:
            guide = json.loads((au.ROOT / 'content/topics' / (gid + '.json')).read_text())
            choice = next(c for c in guide['choices'] if c['id'] == 'smoke-sanitation')
            self.assertEqual({r['doc'] for r in choice['read']}, set(bodies))
            for key in ['prepare','learn']:
                self.assertTrue(set(bodies) <= {r.get('doc') for r in guide[key]})

    def test_arabic_factsheets_keep_source_order_conditions_and_equal_guide_access(self):
        entries = {r['id']: r for r in au.checked_sources()[0]['sources']}
        audit = json.loads((au.SOURCES / 'ARABIC-HAZARDS-SOURCE-AUDIT-20261127.json').read_text(encoding='utf-8'))
        self.assertEqual(audit['source_pages'], 14)
        self.assertEqual(len(audit['selections']), 7)
        bodies = {}
        for selection in audit['selections']:
            uid = selection['reader_id']; record = entries[uid]
            html = (au.SOURCES / record['snapshot']).read_text(encoding='utf-8')
            body = html.split('<hr>', 1)[1].split('<h2 lang="en-AU" dir="ltr">Source, dates and reuse</h2>', 1)[0]
            self.assertEqual(au.digest(body.encode()), selection['body_html_sha256'])
            page = au.Page(); page.feed(re.sub(r'<h2 lang="en-AU" dir="ltr">Source page [12]</h2>', '', body))
            text = ''.join(page.text); compact = re.sub(r'\s+', '', text)
            self.assertEqual(compact, selection['normalized_source_text_without_whitespace'], uid)
            self.assertEqual(Counter(compact), Counter(selection['source_character_counts']))
            self.assertEqual(record['language'], 'ar')
            self.assertIn('<html lang="ar" dir="rtl">', html)
            self.assertEqual(record['source_url'], selection['source']['licensed_source']['url'])
            self.assertEqual(record['raw_sha256'], selection['source']['factsheet']['sha256'])
            self.assertEqual(record['raw_sha256'], selection['source']['licensed_source']['sha256'])
            self.assertEqual(record['license'], 'CC-BY-4.0')
            self.assertIn('<bdi dir="ltr">131 450</bdi>', body)
            self.assertIn('<bdi dir="ltr">000</bdi>', body)
            self.assertNotIn('<img', html)
            self.assertIn('no new translation', html.lower())
            bodies[uid] = compact
        self.assertIn('إذاكانبكامِلوعيهوقادرعلىالاستجابة'.replace('ِ', ''), bodies['au-getready-arabic-heatwaves'])
        self.assertIn('فقدملهرشفاتصغيرةمتكررةمنالماء.', bodies['au-getready-arabic-heatwaves'])
        self.assertIn('إذالمتتمكنمنالمغادرة،فانتقلإلىالطابقالعلويمنمبنىقويعلىارتفاععشرةأمتارعلىالأقلفوقمستوىسطحالبحر.', bodies['au-getready-arabic-tsunamis'])
        self.assertIn('لاتقمأبدًابالقيادةأوالمشيأوالسباحةفيمياهالفيضانات.', bodies['au-getready-arabic-floods'])
        self.assertIn('خادعًا.بمجردمروره،', bodies['au-getready-arabic-cyclones'])
        earthquake = next(s for s in audit['selections'] if s['reader_id'].endswith('earthquakes'))
        self.assertEqual(earthquake['earthquake_number_action_pairs'], [['1', 'انخفض!'], ['2', 'احتمِ!'], ['3', 'تمسّك!']])
        for gid in ['au-household', 'au-rural']:
            guide = json.loads((au.ROOT / 'content/topics' / (gid + '.json')).read_text(encoding='utf-8'))
            choice = next(c for c in guide['choices'] if c['id'] == 'arabic-hazards')
            self.assertEqual({r['doc'] for r in choice['read']}, set(bodies))
            for key in ['prepare', 'learn']:
                self.assertTrue(set(bodies) <= {r.get('doc') for r in guide[key]})

    def test_text_direction_is_explicit_and_rejects_nonstandard_values(self):
        for direction in ['rtl', 'ltr', 'auto']:
            page = au.Page()
            page.feed('<html lang="ar" dir="' + direction + '"><body><p>استعد للفيضانات <bdi dir="ltr">131 450</bdi></p></body></html>')
            self.assertIn('استعد للفيضانات', ''.join(page.text))
            self.assertIn('131 450', ''.join(page.text))
        for direction in ['sideways', '', 'RTL', 'rtl onload=alert(1)']:
            with self.assertRaisesRegex(ValueError, 'Invalid text direction'):
                au.Page().feed('<p dir="' + direction + '">Text</p>')

    def test_wa_tas_planning_preserves_local_distinctions_and_equal_access(self):
        entries = {r['id']: r for r in au.checked_sources()[0]['sources']}
        audit = json.loads((au.SOURCES / 'WA-TAS-PLANNING-SOURCE-AUDIT-20261126.json').read_text(encoding='utf-8'))
        bodies = {}
        for selection in audit['selections']:
            uid = selection['reader_id']; entry = entries[uid]
            body = (au.SOURCES / entry['snapshot']).read_text(encoding='utf-8')
            self.assertEqual(au.digest(body.encode('utf-8')), selection['sha256'])
            self.assertEqual(entry['publisher'], 'Lastbook Australia contributors')
            self.assertEqual(entry['source_url'], '')
            self.assertIn('does not collect or save a completed plan', body)
            self.assertNotIn('<form', body)
            self.assertNotIn('<input', body)
            bodies[uid] = body
        wa = bodies['au-wa-local-plan']; tas = bodies['au-tas-local-plan']
        for condition in ['15 July 2024', 'no longer the WA system', 'does not establish that all hazards have gone',
                          'recognised assistance animals are a separate exception', 'as an animal booking']:
            self.assertIn(condition, wa)
        for condition in ['not evacuation centres or assembly areas', 'Some communities have no identified site',
                          'rather than its full spread', 'road-closure information is incomplete',
                          'does not select, rate or promise safe access']:
            self.assertIn(condition, tas)
        for gid in ['au-household', 'au-rural']:
            guide = json.loads((au.ROOT / 'content/topics' / (gid + '.json')).read_text(encoding='utf-8'))
            for cid, uid, hazards in [('wa-planning', 'au-wa-local-plan', ['cyclones','floods','bushfires']),
                                     ('tas-planning', 'au-tas-local-plan', ['floods','storms','bushfires'])]:
                choice = next(c for c in guide['choices'] if c['id'] == cid)
                self.assertEqual({r['doc'] for r in choice['read']}, {uid} | {'au-getready-' + h for h in hazards})
                for key in ['prepare', 'learn']:
                    self.assertIn(uid, {r.get('doc') for r in guide[key]})

    def test_infant_source_status_is_dated_visible_and_does_not_add_unreviewed_protocols(self):
        manifest = au.checked_sources()[0]
        audit = json.loads((au.SOURCES / 'INFANT-CPR-SOURCE-REVIEW-20261126.json').read_text(encoding='utf-8'))
        self.assertEqual(audit['video']['id'], 'video-bsP45AXQGC4')
        self.assertEqual(audit['video']['upload_date'], '20251014')
        self.assertEqual(len(audit['original_pdf_candidates']), 3)
        self.assertEqual({r['id'] for r in audit['source_comparisons']}, {'anzcor-guideline6', 'schn-infant-factsheet'})
        self.assertTrue(all(r['kind'] == 'html' for r in manifest['sources']))
        guide = json.loads((au.ROOT / 'content/topics/au-health.json').read_text(encoding='utf-8'))
        choice = next(c for c in guide['choices'] if c['id'] == 'child')
        baby = next(r for r in choice['read'] if r['doc'] == audit['video']['id'])
        for scope in ['2025', 'ANZCOR Guideline 6', 'clinical review is pending', 'source video is unchanged']:
            self.assertIn(scope, baby['note'])
        self.assertIn('26 November 2026', choice['hint'])
        self.assertIn('dated', choice['label'])
        self.assertEqual(len(choice['read']), 2)
        hub = next(r for r in manifest['sources'] if r['id'] == 'au-reference')
        html = (au.SOURCES / hub['snapshot']).read_text(encoding='utf-8')
        self.assertIn('Dated infant CPR source status', html)
        self.assertIn('does not create a replacement treatment protocol', html)
        self.assertIn('https://www.anzcor.org/home/basic-life-support/guideline-6-compressions', html)

    def test_fsanz_consumer_readings_preserve_complete_source_conditions_and_equal_access(self):
        entries = {r['id']: r for r in au.checked_sources()[0]['sources']}
        audit = json.loads((au.SOURCES / 'FOOD-SAFETY-SOURCE-AUDIT-20261126.json').read_text(encoding='utf-8'))
        bodies = {}
        for selection in audit['selections']:
            uid = selection['reader_id']; r = entries[uid]
            html = (au.SOURCES / r['snapshot']).read_text(encoding='utf-8')
            body = html.split('<hr>', 1)[1].split('<h2>Source, dates and reuse</h2>', 1)[0]
            parser = au.Page(); parser.feed(body); parser.close()
            compact = re.sub(r'\s+', '', ''.join(parser.text))
            expected = selection['source_text_without_whitespace']
            self.assertEqual(au.digest(expected.encode('utf-8')), selection['source_text_sha256'])
            if r['category'] == 'source-rights':
                self.assertIn(expected, compact)
            else:
                self.assertEqual(compact, expected, uid)
                self.assertEqual(au.digest(body.encode('utf-8')), selection['body_html_sha256'])
                self.assertEqual(r['source_updated'], selection['source_updated'])
                self.assertEqual(r['year'], 2025)
                self.assertEqual(r['raw_sha256'], selection['raw_source']['raw_sha256'])
                bodies[uid] = compact
            self.assertEqual(r['license'], 'CC-BY-4.0')
            self.assertEqual(r['copyright_source'], 'https://www.foodstandards.gov.au/legal-policies/copyright')
        basics = bodies['fsanz-food-basics']
        for condition in ['at least 75°C in the centre:', 'all poultry', 'all meat that has been minced or rolled',
                          'liver and other offal', 'between 2 and 4 hours, eat it straight away',
                          'after 4 hours, throw it away', 'Do not thaw frozen food at room temperature',
                          "Don't use soap, disinfectants or detergents to wash your food"]:
            self.assertIn(re.sub(r'\s+', '', condition), basics)
        flood = bodies['fsanz-food-flood']
        for condition in ['Do not taste or cook flood-affected food', 'if they have not touched flood water and look undamaged',
                          'salvaging cans and pouches for sale is not recommended',
                          'Private water supplies should be tested before using', '1 tablespoon of chlorine bleach per 2 litres of hot water',
                          'for 10 minutes in boiling water']:
            self.assertIn(re.sub(r'\s+', '', condition), flood)
        emergency = bodies['fsanz-food-emergency']
        for condition in ['around four hours', 'around 24 hours', "If frozen foods have thawed don't refreeze!", 'including food in cans and jars even if they appear OK']:
            self.assertIn(re.sub(r'\s+', '', condition), emergency)
        for gid in ['au-household', 'au-rural']:
            guide = json.loads((au.ROOT / 'content/topics' / (gid + '.json')).read_text(encoding='utf-8'))
            choice = next(c for c in guide['choices'] if c['id'] == 'food-safety')
            self.assertEqual({r['doc'] for r in choice['read']}, set(bodies))
            for key in ['prepare', 'learn']:
                self.assertTrue(set(bodies) <= {r.get('doc') for r in guide[key]})

    def test_nt_worksheet_keeps_contact_associations_shelter_limits_and_original_rights(self):
        entries = {r['id']: r for r in au.checked_sources()[0]['sources']}
        r = entries['au-nt-local-plan']
        html = (au.SOURCES / r['snapshot']).read_text(encoding='utf-8')
        self.assertEqual(r['publisher'], 'Lastbook Australia contributors')
        self.assertEqual(r['source_url'], '')
        audit = json.loads((au.SOURCES / 'NT-PLANNING-SOURCE-AUDIT-20261126.json').read_text(encoding='utf-8'))
        self.assertEqual(au.digest(html.encode('utf-8')), audit['reader_sha256'])
        for purpose, number in [('Police, fire or ambulance emergency','000'), ('Police assistance','131 444'), ('Storm assistance','132 500'), ('Power and Water','1800 245 090'), ('NT road report','1800 246 199')]:
            self.assertIn('<td>' + purpose + '</td><td>' + number + '</td>', html)
        for condition in ['not necessarily open', 'not public emergency shelters', 'temporary calm in the cyclone eye is not an all-clear', 'caravans are unsuitable cyclone shelters', 'at least 10 litres of bottled water per person for three days', 'not a ceiling', 'after travel becomes unsafe', '29 April 2024', 'It does not relicense NT Government pages', 'does not collect or save them']:
            self.assertIn(condition, html)
        self.assertNotIn('<form', html)
        self.assertNotIn('<input', html)
        expected = {'au-nt-local-plan','au-getready-cyclones','au-getready-floods','au-getready-bushfires'}
        for gid in ['au-household','au-rural']:
            guide = json.loads((au.ROOT / 'content/topics' / (gid + '.json')).read_text(encoding='utf-8'))
            choice = next(c for c in guide['choices'] if c['id'] == 'nt-planning')
            self.assertEqual({r['doc'] for r in choice['read']}, expected)
            for key in ['prepare','learn']:
                self.assertIn('au-nt-local-plan', {r.get('doc') for r in guide[key]})

    def test_chinese_factsheets_preserve_script_characters_conditions_and_guide_access(self):
        entries = {r['id']: r for r in au.checked_sources()[0]['sources']}
        audit = json.loads((au.SOURCES / 'CHINESE-HAZARDS-SOURCE-AUDIT-20261126.json').read_text(encoding='utf-8'))
        self.assertEqual((audit['source_pages'], audit['source_characters']), (28, 20838))
        self.assertEqual(len(audit['selections']), 14)
        bodies = {}
        for selection in audit['selections']:
            uid = selection['reader_id']; r = entries[uid]
            html = (au.SOURCES / r['snapshot']).read_text(encoding='utf-8')
            body = html.split('<hr>', 1)[1].split('<h2 lang="en-AU">Source, dates and reuse</h2>', 1)[0]
            self.assertEqual(au.digest(body.encode('utf-8')), selection['body_html_sha256'])
            page = au.Page(); page.feed(re.sub(r'<h2 lang="en-AU">Source page [12]</h2>', '', body)); page.close()
            text = ''.join(page.text)
            self.assertEqual(Counter(re.sub(r'[\s\ufeff\x00-\x1f•]', '', text)), Counter(selection['source_character_counts']), uid)
            source = selection['source']
            self.assertTrue(source['licensed_host_identical'])
            self.assertEqual(r['raw_sha256'], source['factsheet']['sha256'])
            self.assertEqual(r['raw_sha256'], source['licensed_source']['sha256'])
            self.assertEqual(r['source_url'], source['licensed_source']['url'])
            self.assertEqual(r['language'], selection['language'])
            self.assertIn('<html lang="' + r['language'] + '">', html)
            expected_date = '2026-04-01' if r['language'] == 'zh-Hans' else '2026-04-08' if uid.endswith('tsunamis') else '2026-04-02'
            self.assertEqual(r['source_updated'], expected_date)
            self.assertEqual(r['license'], 'CC-BY-4.0')
            self.assertIn('131 450', text)
            self.assertIn('000', text)
            bodies[uid] = re.sub(r'\s+', '', text)
            if uid.endswith('tsunamis'):
                labels = ['如果您感到大地震动', '如果您看到海平面下降', '如果您听到异常的轰鸣声'] if r['language'] == 'zh-Hans' else ['若感覺地面震動', '若看見海水驟退', '若聽見異常轟鳴聲']
                for label in labels: self.assertIn('<h4>' + label + '</h4>', body)
            if not uid.endswith('heatwaves'):
                items = re.findall(r'<li>([^<]+)</li>', body)
                for item in (['衣物', '贵重物品', '现金和银行卡', '常用药物'] if r['language'] == 'zh-Hans' else ['衣物', '貴重物品', '現金和銀行卡', '藥物']): self.assertIn(item, items)
        self.assertIn('如果他们神志清醒且能做出反应，可让他们频繁小口饮水。', bodies['au-getready-simplified-chinese-heatwaves'])
        self.assertIn('若患者神志清醒且反應良好，可讓其頻繁少量飲水。', bodies['au-getready-traditional-chinese-heatwaves'])
        self.assertIn('清潔知悉', bodies['au-getready-traditional-chinese-heatwaves'])
        self.assertIn('如果无法撤离，请前往坚固建筑物顶层，并确保所在位置至少高于海平面十米。', bodies['au-getready-simplified-chinese-tsunamis'])
        self.assertIn('若無法撤離，請前往堅固建築物頂層，該處需高於海平面至少十公尺。', bodies['au-getready-traditional-chinese-tsunamis'])
        for gid in ['au-household', 'au-rural']:
            guide = json.loads((au.ROOT / 'content/topics' / (gid + '.json')).read_text(encoding='utf-8'))
            for script in ['simplified', 'traditional']:
                choice = next(c for c in guide['choices'] if c['id'] == script + '-chinese-hazards')
                expected = {uid for uid in bodies if script + '-chinese-' in uid}
                self.assertEqual(len(expected), 7)
                self.assertEqual({r['doc'] for r in choice['read']}, expected)
                for key in ['prepare', 'learn']: self.assertTrue(expected <= {r.get('doc') for r in guide[key]})

    def test_road_sources_preserve_conditions_transcripts_ratings_and_dated_selection(self):
        entries = {r['id']: r for r in au.checked_sources()[0]['sources']}
        audit = json.loads((au.SOURCES / 'ROAD-RECOVERY-SOURCE-AUDIT-20261126.json').read_text(encoding='utf-8'))
        bodies = {}
        for selection in audit['selections']:
            uid = selection['id']; r = entries[uid]
            html = (au.SOURCES / r['snapshot']).read_text(encoding='utf-8')
            body = html.split('<hr>', 1)[1].split('<h2>Source, dates and reuse</h2>', 1)[0]
            parser = au.Page(); parser.feed(body); parser.close()
            text = re.sub(r'\s+', ' ', ''.join(parser.text)).strip()
            # The independently frozen source text protects full conditions and order.
            # HTMLParser inserts separation around inline tags, so normalize punctuation.
            normalized = lambda v: re.sub(r'\s+([.,;:!?])', r'\1', v)
            self.assertEqual(normalized(text), normalized(selection['normalized_source_text']), uid)
            self.assertEqual(au.digest(selection['normalized_source_text'].encode('utf-8')), selection['normalized_source_text_sha256'])
            self.assertEqual(r['raw_sha256'], selection['raw_source']['sha256'])
            self.assertEqual(r['source_updated'], selection['metadata']['DCTERMS.modified'])
            self.assertEqual(r['year'], int(r['source_updated'][:4]))
            self.assertEqual(r['license'], 'CC-BY-4.0')
            self.assertEqual(selection['metadata']['DCTERMS.license'], r['license_url'])
            bodies[uid] = text
        breakdown = bodies['qld-motorway-breakdown']
        for condition in ["if it's safe to do, exit your vehicle", "If it's not safe to exit your vehicle",
                          'fasten their seat belts securely', "Don't walk along highways or motorways.",
                          'Do not walk along highways and do not attempt repairs.', '13 19 40']:
            self.assertIn(condition, breakdown)
        self.assertEqual(breakdown.count('Video transcript'), 2)
        recovery = bodies['qld-recovery-straps']
        self.assertEqual(re.findall(r'Step ([1-7])—', recovery), list('1234567'))
        for condition in ['lighter of the 2 vehicles', 'Never use a damaged strap.', 'Never attach it to:',
                          'a standard tow ball', 'tie-down point.', 'Never use them to lift a vehicle or tow it conventionally.',
                          'at least 1.5 times the length of the unstretched strap', 'Check with the course provider']:
            self.assertIn(condition, recovery)
        selected = bodies['qld-long-trip-checks']
        for text in ['Checking your vehicle', 'Towing on your journey', 'Pack your vehicle for country and outback driving',
                     '20L emergency use and 4L per person per day', 'communication equipment as your mobile phone may not work']:
            self.assertIn(text, selected)
        for excluded in ['Footbrake failure', 'Shattered windscreen', 'Car stalling', '8–10 hours']:
            self.assertNotIn(excluded, selected)
        for gid in ['au-household', 'au-rural']:
            guide = json.loads((au.ROOT / 'content/topics' / (gid + '.json')).read_text(encoding='utf-8'))
            choice = next(c for c in guide['choices'] if c['id'] == 'road-recovery')
            self.assertEqual({r['doc'] for r in choice['read']}, set(bodies))
            for key in ['prepare', 'learn']:
                self.assertTrue(set(bodies) <= {r.get('doc') for r in guide[key]})

    def test_national_factsheets_keep_all_source_words_and_conditional_actions(self):
        entries = {r['id']: r for r in au.checked_sources()[0]['sources']}
        audit = json.loads((au.SOURCES / 'NATIONAL-HAZARDS-SOURCE-AUDIT-20261126.json').read_text(encoding='utf-8'))
        self.assertEqual(audit['source_pages'], 14)
        self.assertEqual(audit['source_word_tokens'], 4944)
        tsunami = (au.SOURCES / 'sources/au-getready-tsunamis.html').read_text(encoding='utf-8')
        for label in ['If you feel the earth shake', 'If you see the ocean drop', 'If you hear an unusual roaring']:
            self.assertIn('<h4>' + label + '</h4><p>', tsunami)
        self.assertEqual(len(audit['selections']), 7)
        bodies = {}
        for selection in audit['selections']:
            uid = selection['reader_id']; r = entries[uid]
            html = (au.SOURCES / r['snapshot']).read_text(encoding='utf-8')
            body = html.split('<hr>', 1)[1].split('<h2>Source, dates and reuse</h2>', 1)[0]
            self.assertIn('Source page 1', body)
            self.assertIn('Source page 2', body)
            page = au.Page()
            page.feed(re.sub(r'<h2>Source page [12]</h2>', '', body)); page.close()
            text = re.sub(r'\s+', ' ', ''.join(page.text)).strip()
            expected = Counter()
            for p in selection['pages']:
                for blocks in p['panels'].values():
                    for b in blocks:
                        expected.update(b['text'].replace('•', ' ').split())
            self.assertEqual(Counter(text.split()), expected, uid)
            self.assertEqual(r['source_url'], selection['licensed_source']['url'])
            self.assertTrue(r['source_url'].startswith('https://www.getready.qld.gov.au/'))
            self.assertTrue(selection['licensed_source']['identical_to_national_source'])
            self.assertEqual(r['raw_sha256'], selection['national_source']['factsheet']['sha256'])
            self.assertEqual(r['license'], 'CC-BY-4.0')
            self.assertEqual(r['copyright_source'], 'https://www.qld.gov.au/legal/copyright')
            self.assertEqual(r['source_created'], '2026-02-19')
            self.assertEqual(r['source_updated'], '2026-03-06' if uid.endswith('tsunamis') else '2026-02-20')
            self.assertIn('not the separate illustrated Easy Read edition', html)
            self.assertIn('call 000 immediately.', text)
            self.assertIn('131 450', text)
            self.assertNotRegex(body, r'<li>[^<]*Where will you go\?')
            bodies[uid] = text
        for text in ['If fully alert and responsive, give them frequent small drinks of water.',
                     'call 000 immediately.', 'Warning signs of heat stroke']:
            self.assertIn(text, bodies['au-getready-heatwaves'])
        for text in ['If you cannot leave, move to the top floor of a strong building at least ten metres above sea level.',
                     'Leave straight away — do not wait for official warnings.', 'eastern costs of Australia']:
            self.assertIn(text, bodies['au-getready-tsunamis'])
        self.assertIn('If you can’t get under furniture, use your arms or a cushion to cover your head.', bodies['au-getready-earthquakes'])
        self.assertIn('Leaving early is the safest option.', bodies['au-getready-bushfires'])
        for uid, text in bodies.items():
            self.assertIn('at least three days of supplies', text)
            if not uid.endswith('heatwaves'):
                self.assertIn('Water (at least 3 litres per person, per day)', text)
        expected_ids = set(bodies)
        for gid in ['au-household', 'au-rural']:
            g = json.loads((au.ROOT / 'content/topics' / (gid + '.json')).read_text(encoding='utf-8'))
            c = next(c for c in g['choices'] if c['id'] == 'national-hazards')
            self.assertEqual({r['doc'] for r in c['read']}, expected_ids)
            for key in ['prepare', 'learn']:
                self.assertTrue(expected_ids <= {r.get('doc') for r in g[key]})

    def test_published_language_posters_keep_complete_wording_language_and_metadata(self):
        manifest, checked = au.checked_sources()
        entries = {r['id']: r for r in manifest['sources']}
        audit = json.loads((au.SOURCES / 'LANGUAGE-POSTERS-SOURCE-AUDIT-20261126.json').read_text(encoding='utf-8'))
        self.assertEqual(audit['total_posters'], 4)
        self.assertEqual(audit['total_practical_bullets'], 20)
        for selection in audit['selections']:
            uid = selection['id']
            entry = entries[uid]
            html = (au.SOURCES / entry['snapshot']).read_text(encoding='utf-8')
            quoted = html.split('<hr>', 1)[1].split('</blockquote>', 1)[0] + '</blockquote>'
            page = au.Page(); page.feed(quoted); page.close()
            text = re.sub(r'\s+', ' ', ''.join(page.text)).strip()
            self.assertEqual(text, selection['complete_source_text'])
            self.assertEqual(au.digest(text.encode('utf-8')), selection['source_normalized_text_sha256'])
            self.assertIn('<blockquote lang="' + selection['language'] + '">', quoted)
            self.assertEqual(entry['language'], selection['language'])
            self.assertEqual(entry['year'], 2024)
            self.assertEqual(entry['source_updated'][:10], '2024-03-20')
            self.assertEqual(entry['license'], 'CC-BY-4.0')
            self.assertEqual(quoted.count('<li>'), 5)
            self.assertNotIn('href=', quoted)
            self.assertIn('1800 173 349', quoted)
            self.assertIn('not newly translated or corrected', html)
        by_id = {r['id']: r for r in audit['selections']}
        # Preserve actual source differences rather than smoothing the translations.
        self.assertIn('warning ak', by_id['qld-wik-mungkan-bushfires-poster']['complete_source_text'])
        self.assertIn('warning aak', by_id['qld-wik-mungkan-cyclones-poster']['complete_source_text'])
        self.assertIn('Mek sur', by_id['qld-yumplatok-bushfires-poster']['complete_source_text'])
        self.assertIn('Meke sur', by_id['qld-yumplatok-cyclones-poster']['complete_source_text'])
        for gid in ['au-household', 'au-rural']:
            guide = json.loads((au.ROOT / 'content/topics' / (gid + '.json')).read_text(encoding='utf-8'))
            for cid, language in [('yumplatok-posters', 'tcs'), ('wik-mungkan-posters', 'wim')]:
                choice = next(c for c in guide['choices'] if c['id'] == cid)
                self.assertEqual({r['doc'] for r in choice['read']},
                                 {r['id'] for r in audit['selections'] if r['language'] == language})
            for key in ['prepare', 'learn']:
                self.assertTrue(set(by_id) <= {r.get('doc') for r in guide[key]})

    def test_original_planning_aids_keep_decision_limits_and_distress_cancellation_separate(self):
        entries = {r['id']: r for r in au.checked_sources()[0]['sources']}
        def body(uid):
            return (au.SOURCES / entries[uid]['snapshot']).read_text(encoding='utf-8')
        ids = {'au-remote-trip-plan', 'au-isolation-plan', 'au-beacon-preparation'}
        for uid in ids:
            self.assertEqual(entries[uid]['license'], 'CC-BY-4.0')
            self.assertEqual(entries[uid]['publisher'], 'Lastbook Australia contributors')
            self.assertEqual(entries[uid]['source_url'], '')
            self.assertTrue(entries[uid]['references'])
            self.assertIn('not reproduced or relicensed', body(uid))
        trip = body('au-remote-trip-plan')
        for text in ['no universal daily minimum', 'before additional allowances',
                     'not a reason to delay urgent help', 'does not establish a public, passable road']:
            self.assertIn(text, trip)
        isolation = body('au-isolation-plan')
        for text in ['Do not disconnect essential medical equipment',
                     'not a promise that roads or services will return',
                     'not specify a generator size', 'before a route or essential backup is lost']:
            self.assertIn(text, isolation)
        beacon = body('au-beacon-preparation')
        genuine = beacon.split('<h2>Genuine distress:', 1)[1].split('<h2>Accidental activation:', 1)[0]
        accidental = beacon.split('<h2>Accidental activation:', 1)[1].split('<h2>Bundled readings', 1)[0]
        self.assertIn('until rescue authorities tell you otherwise', genuine)
        self.assertNotIn('switch the beacon off', genuine)
        self.assertIn('switch the beacon off promptly', accidental)
        self.assertIn('1800 641 792', accidental)
        for text in ['4 November 2024', "does not extend the battery's expiry date",
                     'separated groups should each activate a beacon',
                     'no guaranteed rescue time', "manufacturer's self-test instructions"]:
            self.assertIn(text, beacon)
        for gid in ['au-household', 'au-rural']:
            guide = json.loads((au.ROOT / 'content/topics' / (gid + '.json')).read_text(encoding='utf-8'))
            choice = next(c for c in guide['choices'] if c['id'] == 'planning-tools')
            self.assertEqual({r['doc'] for r in choice['read']}, ids)
            for key in ['prepare', 'learn']:
                self.assertTrue(ids <= {r.get('doc') for r in guide[key]})

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
                                        ('"Farm FireWise"', 'act-bushfire'),
                                        ('"water pooling"', 'act-flooding'),
                                        ('"thunderstorm asthma"', 'act-severe-storm'),
                                        ('"1800MEDICARE"', 'act-heatwave'),
                                        ('"chosen consumption"', 'au-remote-trip-plan'),
                                        ('"Verified backup"', 'au-isolation-plan'),
                                        ('"Accidental activation"', 'au-beacon-preparation'),
                                        ('"buspaya"', 'qld-yumplatok-bushfires-poster'),
                                        ('"cyclone or flood"', 'qld-yumplatok-cyclones-poster'),
                                        ('"ngantam"', 'qld-wik-mungkan-bushfires-poster'),
                                        ('"kaap"', 'qld-wik-mungkan-cyclones-poster'),
                                        ('"ember attacks"', 'au-getready-bushfires'),
                                        ('"typhoons"', 'au-getready-cyclones'),
                                        ('"aftershocks"', 'au-getready-earthquakes'),
                                        ('"centralised"', 'au-getready-floods'),
                                        ('"fully alert"', 'au-getready-heatwaves'),
                                        ('"trampolines"', 'au-getready-storms'),
                                        ('"Onslow"', 'au-getready-tsunamis'),
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

    def test_act_hazards_preserve_all_36_complete_accordion_answers_and_source_contact_dates(self):
        entries = {r['id']: r for r in au.checked_sources()[0]['sources']}
        audit = json.loads((au.SOURCES / 'ACT-HAZARDS-SOURCE-AUDIT-20261126.json').read_text(encoding='utf-8'))
        def source(uid):
            return (au.SOURCES / entries[uid]['snapshot']).read_text(encoding='utf-8').split('<hr>', 1)[1].split('</body>', 1)[0]
        def plain(text):
            parser = au.Page(); parser.feed(text); parser.close()
            return re.sub(r'\s+([.,;:!?])', r'\1', re.sub(r'\s+', ' ', ''.join(parser.text)).strip())
        self.assertEqual(audit['total_practical_accordion_pairs'], 36)
        for uid, hazard in [('act-bushfire', 'bushfire'), ('act-flooding', 'flood'),
                            ('act-severe-storm', 'storm'), ('act-heatwave', 'heatwave')]:
            html = source(uid)
            headings = [plain(x) for x in re.findall(r'<h2>(.*?)</h2>', html, re.S)]
            phases = ['Before a ' + hazard, 'During a ' + hazard, 'After a ' + hazard]
            self.assertEqual([h for h in headings if h in phases], phases)
            pairs = re.findall(r'<h3>(.*?)</h3>(.*?)(?=<h3>|<h2>)', html, re.S)
            self.assertEqual(len(pairs), 9)
            # Independently frozen full source answers protect conditions and ordering.
            self.assertEqual([[plain(q), plain(a)] for q, a in pairs],
                             [[re.sub(r'\s+([.,;:!?])', r'\1', v) for v in row]
                              for row in audit['accordion_pairs'][uid]])
            self.assertEqual(entries[uid]['license'], 'CC-BY-4.0')
            self.assertEqual(entries[uid]['source_created'][:4], '2025')
        bushfire = plain(source('act-bushfire'))
        for text in ['Leaving early is always the safest option.', 'Farm FireWise Program',
                     'Do not enter a bushfire effected area until it is safe.', '1800 022 222']:
            self.assertIn(text, bushfire)
        self.assertIn('Do not drive, ride, walk or play in floodwater.', plain(source('act-flooding')))
        storm = plain(source('act-severe-storm'))
        self.assertIn('Do not leave your property unless told to do so.', storm)
        self.assertIn('October to December', storm)
        self.assertIn('Carry your prescribed medication', storm)
        heat = plain(source('act-heatwave'))
        for text in ['1800Medicare', '1800 633 422', 'you do not need a Medicare card',
                     'Avoid working outdoors in the peak heat', 'Do not exercise animals during the day.',
                     'call triple zero (000) for an ambulance.']:
            self.assertIn(text, heat)
        self.assertNotIn('1800 022 222', heat)
        self.assertEqual(entries['act-heatwave']['source_updated'], '2026-11-16')
        for uid in ['act-bushfire', 'act-flooding', 'act-severe-storm']:
            self.assertEqual(entries[uid]['source_updated'], '2026-07-01')
        rights = plain(source('act-copyright'))
        for text in ['The appropriate credit is © Australian Capital Territory',
                     'any third party material', 'the ACT', 'Coat of Arms',
                     'copyright belongs to the author', 'automatic language translation services']:
            self.assertIn(text, rights)

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
        for uid in ['AU-ACT','AU-NSW','AU-QLD','AU-SA','AU-TAS','AU-VIC','AU-WA']:
            self.assertEqual(regions[uid]['checked'], '2026-11-17')
        self.assertEqual(regions['AU-NT']['checked'], '2026-11-26')
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

    def test_aboriginal_planning_preserves_the_complete_source_and_scope(self):
        audit = json.loads((au.SOURCES / 'ABORIGINAL-PLANNING-SOURCE-AUDIT-20261127.json').read_text(encoding='utf-8'))
        records = {r['id']: r for r in au.checked_sources()[0]['sources']}
        record = records[audit['id']]
        html = (au.SOURCES / record['snapshot']).read_text(encoding='utf-8')
        body = html.split('<hr>\n', 1)[1].split('<hr>', 1)[0]
        self.assertEqual(au.digest(body.encode()), audit['reader_body_html_sha256'])
        self.assertEqual(au.source_text(body), audit['source_text'])
        self.assertEqual(au.digest(audit['source_text'].encode()), audit['source_text_sha256'])
        self.assertEqual(record['raw_sha256'], audit['raw']['raw_sha256'])
        self.assertEqual(record['source_updated'], '2025-10-28')
        self.assertEqual(record['license'], 'CC-BY-4.0')
        self.assertTrue(audit['rights']['policy_matches_existing_bundled_body'])
        lists = re.findall(r'<ul>(.*?)</ul>', body, re.S)
        self.assertEqual([part.count('<li>') for part in lists], [5, 4, 6])
        for condition in ['planning led by Aboriginal people', 'self-determination at all 4 stages',
                          'information for Aboriginal communities is to be informed by Aboriginal people',
                          'family, housing, and mobility patterns', 'local Lore', 'cultural governance structures',
                          'formal partnership mechanisms', '(under review)']:
            self.assertIn(condition, au.source_text(body))
        self.assertIn('does not establish community endorsement', html)
        self.assertIn('linked GL2024_016 guideline', html)
        self.assertEqual(len(audit['linked_resources_excluded']), 7)
        for resource in audit['linked_resources_excluded']:
            self.assertIn(resource['url'].replace('&', '&amp;'), html)
        self.assertNotIn('href="https://', html)
        for uid, digest in audit['base_sources_sha256'].items():
            if uid != 'au-reference':
                self.assertEqual(records[uid]['sha256'], digest, uid)

    def test_aboriginal_planning_addition_preserves_guides_and_follows_actual_availability(self):
        import copy
        import server
        from tools.validate_topics import items
        audit = json.loads((au.SOURCES / 'ABORIGINAL-PLANNING-SOURCE-AUDIT-20261127.json').read_text(encoding='utf-8'))
        uid = audit['id']
        for gid, digest in audit['baseline_guides'].items():
            guide = json.loads((au.ROOT / 'content/topics' / (gid + '.json')).read_text(encoding='utf-8'))
            guide['choices'] = [c for c in guide['choices'] if c['id'] != 'aboriginal-planning']
            for key in ['prepare', 'learn']:
                guide[key] = [r for r in guide[key] if r.get('doc') != uid]
            self.assertEqual(au.digest(json.dumps(guide, sort_keys=True).encode()), digest)
        household = [x for x in audit['guide_placements'] if x['guide'] == 'au-household']
        rural = [x for x in audit['guide_placements'] if x['guide'] == 'au-rural']
        self.assertEqual([{k:v for k,v in x.items() if k != 'guide'} for x in household],
                         [{k:v for k,v in x.items() if k != 'guide'} for x in rural])
        with tempfile.TemporaryDirectory() as d, patch.object(socket, 'socket', side_effect=AssertionError('network')):
            data = Path(d) / 'LastbookData'; au.build(data); lib = data / 'library-data'
            source = lib / 'pages/au' / (uid + '.html'); held = Path(d) / 'held.html'
            with patch.object(server, 'APP', au.ROOT), patch.object(server, 'LIB', lib), \
                 patch.object(server, '_cat', {'mtime': None}), patch.object(server, 'zim_names', return_value=[]):
                def refs():
                    return [r for g in server.topics_resolved() for _,r in items(g) if r.get('doc') == uid]
                present = refs()
                self.assertEqual(len(present), 8)
                self.assertTrue(all(r['src']['id'] == uid for r in present))
                catalogue = (lib / 'catalog.json').read_bytes()
                source.rename(held)
                self.assertEqual(refs(), [])
                held.rename(source)
                self.assertEqual(refs(), present)
                self.assertEqual((lib / 'catalog.json').read_bytes(), catalogue)

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
                    '<a href="https://example.invalid">x</a>', '<p onclick="x()">x</p>',
                    '<ol type="unknown"><li>x</li></ol>', '<p type="a">x</p>']:
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
