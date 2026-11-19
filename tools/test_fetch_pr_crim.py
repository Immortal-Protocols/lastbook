"""Check that public lookup checkpoints preserve wording and survive interrupted runs."""
import csv
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import types
import unittest
from unittest.mock import Mock, call, patch

from tools import fetch_pr_crim as fetch
from tools.pr_areas import REGIONS


class PublicPrefixResults(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        self.roster = {'00100200301', '00100200302', '00100400303'}
        fetch.checkpoint(self.db, 'Villa Ejemplo', self.roster)

    @staticmethod
    def row(base='001-002-003-01', address='Bo. Peña , SOLAR A-7, PR, Puerto Rico, 00000', town='Villa Ejemplo'):
        return {'Parcela':base, 'Dirección física':address, 'Municipio':town}

    def test_original_wording_and_completed_grids(self):
        rows = [self.row(), self.row('001-002-003-02', ''), self.row('001-002-003-99')]
        fetch.save_prefix(self.db, '001-002', rows, 3, self.roster)
        fetch.save_prefix(self.db, '001-002', rows, 3, self.roster)
        summary = fetch.write_results(self.db, self.directory, 'Villa Ejemplo', self.roster, {'00100200301'})
        with (self.directory / 'addresses.csv').open(newline='', encoding='utf-8') as stream:
            self.assertEqual(list(csv.DictReader(stream)), [dict(catastro='00100200301', address=rows[0]['Dirección física'], municipio='Villa Ejemplo')])
        self.assertEqual(summary['returned_parcels'], 2)
        self.assertEqual(summary['empty_address_parcels'], 1)
        self.assertEqual(summary['missing_parcels'], 0)
        self.assertEqual(summary['unqueried_parcels'], 1)
        self.assertEqual(summary['newly_collected_parcels'], 0)
        fetch.checkpoint(self.db, 'Villa Ejemplo', self.roster)
        self.db.execute("UPDATE meta SET value='another source' WHERE key='source'")
        self.db.commit()
        with self.assertRaisesRegex(ValueError, 'different'):
            fetch.checkpoint(self.db, 'Otro Pueblo', self.roster)

    def test_failed_prefix_is_never_marked_complete(self):
        for rows, count in [([self.row()], 2), ([self.row('001-004-003-03')], 1), ([{'Parcela':'001-002-003-01'}], 1)]:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                fetch.save_prefix(self.db, '001-002', rows, count, self.roster)
        self.assertEqual(self.db.execute('SELECT count(*) FROM prefix').fetchone(), (0,))
        self.assertEqual(self.db.execute('SELECT count(*) FROM record').fetchone(), (0,))

    def test_different_municipio_and_multiple_address_versions(self):
        rows = [self.row(), self.row(address='BO PEÑA, SOLAR B, PR, 00700'), self.row('001-002-003-02', town='Otro Pueblo')]
        fetch.save_prefix(self.db, '001-002', rows, 3, self.roster)
        fetch.save_prefix(self.db, '001-004', [], 0, self.roster)
        summary = fetch.write_results(self.db, self.directory, 'Villa Ejemplo', self.roster, set())
        self.assertEqual((summary['csv_parcels'], summary['municipio_matched_parcels'], summary['csv_wordings']), (2, 1, 3))
        with (self.directory / 'addresses.csv').open(newline='', encoding='utf-8') as stream:
            saved = list(csv.DictReader(stream))
        self.assertEqual(saved[-1]['municipio'], 'Otro Pueblo')
        self.assertEqual((summary['missing_parcels'], summary['unqueried_parcels']), (1, 0))

    def test_expanding_selection_rechecks_a_shared_grid_and_preserves_cached_records(self):
        fetch.save_prefix(self.db, '001-002', [self.row()], 1, self.roster)
        expanded = self.roster | {'00100200303'}
        fetch.checkpoint(self.db, ['Villa Ejemplo', 'Otro Pueblo'], expanded)
        batches = fetch.grid_rosters(base for base, in self.db.execute('SELECT base FROM scope'))
        self.assertNotIn('001-002', fetch.completed_prefixes(self.db, batches))
        summary = fetch.write_results(self.db, self.directory, 'Villa Ejemplo', expanded, set())
        self.assertEqual((summary['returned_parcels'], summary['missing_parcels'], summary['unqueried_parcels']), (1, 0, 3))
        rows = [self.row(), self.row('001-002-003-03', town='Otro Pueblo')]
        fetch.save_prefix(self.db, '001-002', rows, 2, batches['001-002'])
        mapped = {'00100200301': {'villa ejemplo'}, '00100200303': {'otro pueblo'}}
        summary = fetch.write_results(self.db, self.directory, ['Villa Ejemplo', 'Otro Pueblo'], mapped, set())
        self.assertTrue(summary['complete'])
        self.assertEqual((summary['returned_parcels'], summary['municipio_matched_parcels']), (2, 2))
        summary = fetch.write_results(self.db, self.directory, 'Villa Ejemplo', {'00100200301'}, set())
        self.assertEqual(summary['csv_parcels'], 1)
        self.assertTrue(summary['complete'])
        self.assertEqual(self.db.execute('SELECT count(*) FROM record').fetchone(), (2,))

    def test_single_municipio_checkpoint_upgrade(self):
        with sqlite3.connect(':memory:') as old:
            old.executescript('''
                CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT);
                CREATE TABLE prefix(value TEXT PRIMARY KEY,displayed INTEGER,completed TEXT);
                CREATE TABLE record(prefix TEXT,catastro TEXT,address TEXT,municipio TEXT,
                    PRIMARY KEY(prefix,catastro,address,municipio)) WITHOUT ROWID;
                INSERT INTO prefix VALUES ('001-002',1,'earlier');
                INSERT INTO record VALUES ('001-002','00100200301','BO PEÑA, SOLAR 6','Villa Ejemplo');
            ''')
            identity = json.dumps([fetch.VIEWER, 'Villa Ejemplo', sorted(self.roster)], ensure_ascii=False, separators=(',', ':'))
            old.execute('INSERT INTO meta VALUES (?,?)', ('roster', hashlib.sha256(identity.encode()).hexdigest()))
            old.commit()
            fetch.checkpoint(old, ['Villa Ejemplo', 'Otro Pueblo'], self.roster | {'00100200303'}, ('Villa Ejemplo', self.roster))
            self.assertEqual(old.execute('SELECT address FROM record').fetchone(), ('BO PEÑA, SOLAR 6',))
            self.assertEqual(old.execute('SELECT count(*) FROM scope').fetchone(), (4,))
            batches = fetch.grid_rosters(base for base, in old.execute('SELECT base FROM scope'))
            self.assertNotIn('001-002', fetch.completed_prefixes(old, batches))

    def test_search_retries_only_explicit_query_failures(self):
        search = object.__new__(fetch.PublicSearch)
        search.query = Mock(side_effect=[fetch.PublicQueryFailed('public error'), ([self.row()], 1)])
        with patch.object(fetch.time, 'sleep') as pause:
            self.assertEqual(search.lookup('001-002'), ([self.row()], 1))
            pause.assert_called_once_with(2)
        search.query = Mock(side_effect=ValueError('changed result layout'))
        with self.assertRaisesRegex(ValueError, 'layout'):
            search.lookup('001-002')
        self.assertEqual(search.query.call_count, 1)
        search.query = Mock(side_effect=fetch.PublicQueryFailed('public error'))
        with patch.object(fetch.time, 'sleep') as pause, self.assertRaises(fetch.PublicQueryFailed):
            search.lookup('001-002')
        self.assertEqual(search.query.call_count, 3)
        self.assertEqual(pause.call_args_list, [call(2), call(4)])

    def test_failed_grid_does_not_starve_later_grids_and_resume_retries_only_failures(self):
        driver = Mock()
        @contextmanager
        def playwright():
            yield driver
        sync = types.ModuleType('playwright.sync_api')
        sync.sync_playwright = playwright
        page_module = types.ModuleType('playwright')
        page_module.__path__ = []
        roster = {base: {'villa ejemplo'} for base in self.roster}
        directory = self.directory / 'collection'
        def lookup(prefix):
            if prefix == '001-002':
                raise fetch.PublicQueryFailed('public error')
            return [self.row('001-004-003-03')], 1
        with patch.dict('sys.modules', {'playwright': page_module, 'playwright.sync_api': sync}), \
                patch.object(fetch, 'area_roster', return_value=(['Villa Ejemplo'], roster, set())), \
                patch.object(fetch, 'PublicSearch') as search, patch.object(fetch.time, 'sleep'):
            search.return_value.lookup.side_effect = lookup
            with self.assertRaisesRegex(ValueError, 'remain unqueried'):
                fetch.fetch(self.directory / 'unused.sqlite', directory, 'Villa Ejemplo')
            summary = json.loads((directory / 'summary.json').read_text())
            self.assertEqual((summary['failed_prefixes'], summary['unqueried_parcels'], summary['complete']),
                             (['001-002'], 2, False))
            with sqlite3.connect(directory / 'prefixes.sqlite') as db:
                self.assertEqual(db.execute('SELECT value FROM prefix').fetchall(), [('001-004',)])
            search.return_value.lookup.reset_mock()
            search.return_value.lookup.side_effect = None
            search.return_value.lookup.return_value = ([self.row(), self.row('001-002-003-02')], 2)
            result = fetch.fetch(self.directory / 'unused.sqlite', directory, 'Villa Ejemplo')
            self.assertTrue(result['complete'])
            self.assertEqual(result['failed_prefixes'], [])
            self.assertEqual(result['returned_parcels'], 3)
            search.return_value.lookup.assert_called_once_with('001-002')

    def test_three_consecutive_failed_grids_stop_before_remaining_queries(self):
        driver = Mock()
        @contextmanager
        def playwright():
            yield driver
        sync = types.ModuleType('playwright.sync_api')
        sync.sync_playwright = playwright
        parent = types.ModuleType('playwright')
        parent.__path__ = []
        roster = {f'00100{i}00301': {'villa ejemplo'} for i in range(1, 7)}
        directory = self.directory / 'outage'
        with patch.dict('sys.modules', {'playwright': parent, 'playwright.sync_api': sync}), \
                patch.object(fetch, 'area_roster', return_value=(['Villa Ejemplo'], roster, set())), \
                patch.object(fetch, 'PublicSearch') as search, patch.object(fetch.time, 'sleep'):
            search.return_value.lookup.side_effect = fetch.PublicQueryFailed('public error')
            with self.assertRaisesRegex(ValueError, 'three consecutive'):
                fetch.fetch(self.directory / 'unused.sqlite', directory, 'Villa Ejemplo')
            self.assertEqual(search.return_value.lookup.call_count, 3)
            summary = json.loads((directory / 'summary.json').read_text())
            self.assertEqual(summary['failed_prefixes'], ['001-001', '001-002', '001-003'])
            self.assertFalse(summary['complete'])
            self.assertEqual(summary['unqueried_parcels'], 6)
            with sqlite3.connect(directory / 'prefixes.sqlite') as db:
                self.assertEqual(db.execute('SELECT count(*) FROM prefix').fetchone()[0], 0)
            search.return_value.lookup.reset_mock()
            def intermittent(prefix):
                if int(prefix.split('-')[1]) % 2:
                    raise fetch.PublicQueryFailed('public error')
                return [self.row(prefix + '-003-01')], 1
            search.return_value.lookup.side_effect = intermittent
            with self.assertRaisesRegex(ValueError, 'remain unqueried'):
                fetch.fetch(self.directory / 'unused.sqlite', self.directory / 'intermittent', 'Villa Ejemplo')
            self.assertEqual(search.return_value.lookup.call_count, 6)

    @contextmanager
    def collection(self, lookup):
        driver = Mock()
        @contextmanager
        def playwright():
            yield driver
        sync = types.ModuleType('playwright.sync_api')
        sync.sync_playwright = playwright
        parent = types.ModuleType('playwright')
        parent.__path__ = []
        roster = {base: {'villa ejemplo'} for base in self.roster}
        with patch.dict('sys.modules', {'playwright': parent, 'playwright.sync_api': sync}), \
                patch.object(fetch, 'area_roster', return_value=(['Villa Ejemplo'], roster, set())), \
                patch.object(fetch, 'PublicSearch') as search, patch.object(fetch.time, 'sleep'):
            search.return_value.lookup.side_effect = lookup
            yield search.return_value

    def test_grouped_search_preserves_wording_counts_and_existing_checkpoints(self):
        rows = [self.row(), self.row(address='Another original wording'), self.row('001-002-003-02', ''),
                self.row('001-003-003-99'), self.row('001-004-003-03', town='Otro Pueblo')]
        directory = self.directory / 'grouped'
        with self.collection(lambda prefix: (rows, len(rows))) as search:
            result = fetch.fetch(self.directory / 'unused', directory, 'Villa Ejemplo', group_grids=True)
            self.assertTrue(result['complete'])
            search.lookup.assert_called_once_with('001-0')
            with sqlite3.connect(directory / 'prefixes.sqlite') as db:
                self.assertEqual(db.execute('SELECT value,displayed FROM prefix ORDER BY value').fetchall(),
                                 [('001-002', 3), ('001-004', 1)])
                self.assertEqual(db.execute('SELECT count(*) FROM record').fetchone(), (4,))
                self.assertEqual(db.execute("SELECT address FROM record WHERE municipio='Otro Pueblo'").fetchone(),
                                 (rows[-1]['Dirección física'],))
            self.assertEqual((result['csv_wordings'], result['empty_address_parcels'], result['missing_parcels']), (3, 1, 0))
            search.lookup.reset_mock()
            fetch.fetch(self.directory / 'unused', directory, 'Villa Ejemplo', group_grids=True)
            search.lookup.assert_not_called()

    def test_large_failed_and_empty_groups_narrow_without_marking_false_completion(self):
        for response in ('large', 'failed', 'empty', 'timeout'):
            with self.subTest(response=response):
                def lookup(prefix):
                    if len(prefix) < 7:
                        if response == 'large': raise fetch.PublicResultTooLarge('too many cards')
                        if response == 'failed': raise fetch.PublicQueryFailed('public error')
                        if response == 'timeout': raise fetch.PublicQueryTimeout('timed out')
                        return [], 0
                    if prefix == '001-002': return [], 0
                    return [self.row('001-004-003-03')], 1
                with self.collection(lookup) as search:
                    result = fetch.fetch(self.directory / 'unused', self.directory / response,
                                         'Villa Ejemplo', group_grids=True)
                    self.assertEqual(search.lookup.call_args_list,
                                     [call('001-0'), call('001-00'), call('001-002'), call('001-004')])
                    self.assertTrue(result['complete'])
                    self.assertEqual((result['missing_parcels'], result['unqueried_parcels']), (2, 0))

    def test_incomplete_or_mismatched_group_never_completes_any_grid(self):
        for i, (rows, count) in enumerate([([self.row()], 2), ([self.row(), self.row('002-002-003-01')], 2),
                                           ([self.row(), {'Parcela': '001-004-003-03'}], 2)]):
            directory = self.directory / ('malformed-' + str(i))
            with self.subTest(rows=rows), self.collection(lambda prefix: (rows, count)):
                with self.assertRaises(ValueError):
                    fetch.fetch(self.directory / 'unused', directory, 'Villa Ejemplo', group_grids=True)
                with sqlite3.connect(directory / 'prefixes.sqlite') as db:
                    self.assertEqual(db.execute('SELECT count(*) FROM prefix').fetchone(), (0,))

    def test_interrupted_group_resumes_only_its_unfinished_grids(self):
        directory = self.directory / 'interrupted-group'
        rows = [self.row(), self.row('001-004-003-03')]
        original = fetch.save_prefix
        def save(db, prefix, rows, count, roster):
            if prefix == '001-004': raise KeyboardInterrupt()
            original(db, prefix, rows, count, roster)
        with self.collection(lambda prefix: (rows, 2)), patch.object(fetch, 'save_prefix', side_effect=save):
            with self.assertRaises(KeyboardInterrupt):
                fetch.fetch(self.directory / 'unused', directory, 'Villa Ejemplo', group_grids=True)
        with self.collection(lambda prefix: ([self.row('001-004-003-03')], 1)) as search:
            result = fetch.fetch(self.directory / 'unused', directory, 'Villa Ejemplo', group_grids=True)
            self.assertTrue(result['complete'])
            search.lookup.assert_called_once_with('001-004')

    def test_grouped_fallback_keeps_the_individual_grid_outage_limit(self):
        self.roster = {f'00100{i}00301' for i in range(1, 7)}
        with self.collection(Mock(side_effect=fetch.PublicQueryFailed('public error'))) as search:
            with self.assertRaisesRegex(ValueError, 'three consecutive'):
                fetch.fetch(self.directory / 'unused', self.directory / 'group-outage',
                            'Villa Ejemplo', group_grids=True)
            self.assertEqual(search.lookup.call_args_list,
                             [call('001-0'), call('001-00'), call('001-001'), call('001-002'), call('001-003')])

    @unittest.skipUnless(os.environ.get('LASTBOOK_TEST_CRIM_UI') == '1', 'opt-in local browser fixture')
    def test_public_form_error_and_pagination_retry_in_local_browser(self):
        from playwright.sync_api import sync_playwright
        html = '''<div class="jimu-widget-query">
          <button class="query-tab-item" title="Tasks" onclick="document.getElementById('form').style.display='block'">Tasks</button>
          <div id="form"><input id="dijit_form_ValidationTextBox_0"><input id="dijit_form_TextBox_0">
          <button onclick="apply()">Apply</button></div><div id="resultname"></div>
          <div class="features-result" id="results" style="display:none">
          <span data-dojo-attach-point="numSpan" id="counter"></span><div id="cards"></div>
          <button class="load-more-button" onclick="more()">Load more</button></div></div>
          <div class="jimu-message" id="message" style="display:none"><div class="content">Query failed !</div>
          <div role="button" aria-disabled="true">OK</div>
          <div role="button" tabindex="0" onclick="document.getElementById('message').style.display='none'">OK</div></div>
          <script>
          let attempts=0, moreAttempts=0, mode='apply';
          function card(n) { return `<table class="attrTable"><tr><td>Parcela</td><td>${dijit_form_ValidationTextBox_0.value}-003-0${n}</td></tr>
            <tr><td>Dirección física</td><td>Bo. Peña, Solar ${n}</td></tr><tr><td>Municipio</td><td>Villa Ejemplo</td></tr></table>`; }
          function apply() {
            attempts++;
            if (mode==='always' || (mode==='apply' && attempts===1)) {message.style.display='block';return;}
            form.style.display='none';
            if (mode==='name' && attempts===1) {setTimeout(()=>message.style.display='block',20);return;}
            const label=document.createElement('span');label.textContent=dijit_form_TextBox_0.value;resultname.append(label);
            results.style.display='block';cards.innerHTML=card(1);counter.textContent=mode==='more'?'1 / 2':'1 / 1';
            if (mode==='counter' && attempts===1) {counter.textContent='';setTimeout(()=>message.style.display='block',20);}
            if (mode==='cards' && attempts===1) {cards.innerHTML='';setTimeout(()=>message.style.display='block',20);}
            if (mode==='zero') {cards.innerHTML='';counter.textContent='0 / 0';setTimeout(()=>{cards.innerHTML=card(1);counter.textContent='1 / 1';},200);}
            if (mode==='empty') {cards.innerHTML='';counter.textContent='0 / 0';}
          }
          function more() {
            moreAttempts++;
            if (moreAttempts===1) {message.style.display='block';return;}
            cards.innerHTML+=card(2);counter.textContent='2 / 2';
          }
          </script>'''
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                page = browser.new_page()
                page.set_default_timeout(3000)
                page.set_content(html)
                search = object.__new__(fetch.PublicSearch)
                search.sequence = 0
                search.page, search.widget = page, page.locator('.jimu-widget-query')
                with patch.object(fetch.time, 'sleep'):
                    rows, count = search.lookup('001-002')
                    self.assertEqual((count, rows[0]['Parcela'], page.evaluate('attempts')), (1, '001-002-003-01', 2))
                    page.evaluate("mode='more';attempts=0;moreAttempts=0")
                    rows, count = search.lookup('001-004')
                    self.assertEqual((count, len(rows), page.evaluate('attempts')), (2, 2, 2))
                    self.assertTrue(all(row['Parcela'].startswith('001-004') for row in rows))
                    search.max_records = 1
                    page.evaluate("mode='more';attempts=0;moreAttempts=0")
                    with self.assertRaises(fetch.PublicResultTooLarge):
                        search.lookup('001-004')
                    self.assertEqual((page.evaluate('attempts'), page.evaluate('moreAttempts')), (1, 0))
                    search.max_records = None
                    for mode in ('name', 'counter', 'cards'):
                        page.evaluate('(value)=>{mode=value;attempts=0}', mode)
                        rows, count = search.lookup('001-005')
                        self.assertEqual((count, page.evaluate('attempts')), (1, 2))
                    names = page.locator('#resultname span').all_text_contents()
                    self.assertEqual(len(names), len(set(names)))
                    page.evaluate("mode='zero';attempts=0")
                    rows, count = search.lookup('001-007')
                    self.assertEqual((count, len(rows)), (1, 1))
                    page.evaluate("mode='empty';attempts=0")
                    self.assertEqual(search.lookup('001-008'), ([], 0))
                    page.evaluate("mode='always';attempts=0")
                    with self.assertRaises(fetch.PublicQueryFailed):
                        search.lookup('001-006')
                    self.assertEqual(page.evaluate('attempts'), 3)
                    page.set_default_timeout(100)
                    page.evaluate("apply=()=>{attempts++};attempts=0")
                    with self.assertRaises(fetch.PublicQueryTimeout):
                        search.lookup('001-006')
                    self.assertEqual(page.evaluate('attempts'), 1)
            finally:
                browser.close()


class AreaSelection(unittest.TestCase):
    def test_plans_custom_regions_and_all_municipios(self):
        with tempfile.TemporaryDirectory() as temp:
            index = Path(temp) / 'PR.sqlite'
            names = sorted({name for group in REGIONS.values() for name in group.split('|')})
            self.assertEqual(len(names), 78)
            with sqlite3.connect(index) as db:
                db.executescript('''CREATE TABLE municipios(name); CREATE TABLE pr_parcel(base,municipio);
                                   CREATE TABLE pr_permit_wording(base,town,source);''')
                db.executemany('INSERT INTO municipios VALUES (?)', ((name,) for name in names))
                db.executemany('INSERT INTO pr_parcel VALUES (?,?)', ((f'001002{i:05d}', name) for i, name in enumerate(names)))
            output = Path(temp) / 'not-created'
            plan = fetch.fetch(index, output, ['Yabucoa', 'YABUCOA', 'Las Piedras'], plan=True)
            self.assertEqual((len(plan['municipios']), plan['roster_parcels']), (2, 2))
            region = fetch.fetch(index, None, ['San Juan'], regions=['metro', 'east'], plan=True)
            self.assertEqual(len(region['municipios']), 23)
            self.assertIn('Vieques', region['municipios'])
            all_towns = fetch.fetch(index, None, whole_island=True, plan=True)
            self.assertEqual((len(all_towns['municipios']), all_towns['roster_parcels']), (78, 78))
            self.assertFalse(output.exists())
            with self.assertRaisesRegex(ValueError, 'absent'):
                fetch.fetch(index, None, ['Unknown'], plan=True)
