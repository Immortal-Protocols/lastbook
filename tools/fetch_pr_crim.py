"""Save public CRIM Parcela prefix-search results for selected Puerto Rico areas.

Run on a connected build machine. This tool operates the public search form in a
fresh browser and reads its displayed parcel, physical-address and municipio fields.
"""
import argparse
from collections import deque
from contextlib import closing
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine.paths import ro_uri, try_lock
from engine.pr_addresses import fold
from engine.pr_parcels import number
from tools.pr_areas import area_arguments, select_municipios

VIEWER = 'https://catastro.crimpr.net/cdprpc/'

# Read values from the result cards, keeping the address's original punctuation.
READ_RESULTS = """element => Array.from(element.querySelectorAll('.attrTable')).map(table => {
    const record = {};
    for (const row of table.rows) {
        const label = row.cells[0]?.textContent.trim();
        if (['Parcela', 'Dirección física', 'Municipio'].includes(label)) {
            record[label] = row.cells[1]?.textContent ?? '';
        }
    }
    return record;
})"""


def area_roster(index, requested=(), regions=(), whole_island=False):
    with closing(sqlite3.connect(ro_uri(index), uri=True)) as db:
        towns = select_municipios(db, requested, regions, whole_island)
        placeholders = ','.join('?' for _ in towns)
        owners = {name: frozenset({fold(name)}) for name in towns}
        roster = {}
        found = set()
        for base, name in db.execute('SELECT DISTINCT base,municipio FROM pr_parcel WHERE municipio IN (' + placeholders + ')', towns):
            if base in roster:
                roster[base] |= owners[name]
            else:
                roster[base] = owners[name]
            found.add(name)
        if set(towns) - found:
            raise ValueError('The index lacks mapped parcels for: ' + ', '.join(sorted(set(towns) - found)))
        if not roster or any(not re.fullmatch(r'[0-9]{11}', base) for base in roster):
            raise ValueError('Expected mapped 11-digit land numbers for the selected area.')
        keys = {fold(town) for town in towns}
        known = {base for base, name in db.execute("SELECT DISTINCT base,town FROM pr_permit_wording WHERE source='CRIM'")
                 if name in keys and base in roster}
    return towns, roster, known


def municipio_roster(index, requested):
    towns, roster, known = area_roster(index, requested)
    return towns[0], set(roster), known


def grid_rosters(roster):
    grids = {}
    for base in roster:
        grids.setdefault(base[:3] + '-' + base[3:6], set()).add(base)
    return grids


def roster_digest(roster):
    return hashlib.sha256(','.join(sorted(roster)).encode()).hexdigest()


def legacy_selection(index, db):
    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not tables or 'scope' in tables:
        return None
    if not {'meta', 'prefix', 'record'} <= tables:
        raise ValueError('The checkpoint file belongs to another program.')
    stored = db.execute("SELECT value FROM meta WHERE key='roster'").fetchone()
    with closing(sqlite3.connect(ro_uri(index), uri=True)) as source:
        names = {fold(name): name for name, in source.execute('SELECT name FROM municipios')}
        rosters = {}
        for base, name in source.execute('SELECT base,municipio FROM pr_parcel'):
            rosters.setdefault(fold(name or ''), set()).add(base)
    for key, bases in rosters.items():
        if key in names:
            identity = json.dumps([VIEWER, names[key], sorted(bases)], ensure_ascii=False, separators=(',', ':'))
            if stored == (hashlib.sha256(identity.encode()).hexdigest(),):
                return names[key], bases
    raise ValueError('The earlier checkpoint uses a different parcel roster. Choose a new directory.')


def checkpoint(db, town, roster, legacy=None):
    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if tables:
        if not {'meta', 'prefix', 'record'} <= tables:
            raise ValueError('The checkpoint file belongs to another program.')
        if 'scope' in tables and db.execute("SELECT value FROM meta WHERE key='source'").fetchone() != (VIEWER,):
            raise ValueError('This checkpoint uses a different source. Choose a new directory.')
        if 'scope' not in tables:
            legacy = legacy or (town, roster)
            identity = json.dumps([VIEWER, legacy[0], sorted(legacy[1])], ensure_ascii=False, separators=(',', ':'))
            if db.execute("SELECT value FROM meta WHERE key='roster'").fetchone() != (hashlib.sha256(identity.encode()).hexdigest(),):
                raise ValueError('The earlier checkpoint uses a different parcel roster. Choose a new directory.')
    with db:
        db.execute('BEGIN IMMEDIATE')
        if not tables:
            db.execute('CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT)')
            db.execute('CREATE TABLE prefix(value TEXT PRIMARY KEY,displayed INTEGER,completed TEXT,roster TEXT)')
            db.execute('''CREATE TABLE record(prefix TEXT,catastro TEXT,address TEXT,municipio TEXT,
                          PRIMARY KEY(prefix,catastro,address,municipio)) WITHOUT ROWID''')
        elif 'scope' not in tables:
            db.execute('ALTER TABLE prefix ADD COLUMN roster TEXT')
            for prefix, bases in grid_rosters(legacy[1]).items():
                db.execute('UPDATE prefix SET roster=? WHERE value=?', (roster_digest(bases), prefix))
        if 'scope' not in tables:
            db.execute('CREATE TABLE scope(base TEXT PRIMARY KEY) WITHOUT ROWID')
            db.execute('INSERT INTO meta VALUES (?,?)', ('source', VIEWER))
            if legacy:
                db.executemany('INSERT OR IGNORE INTO scope VALUES (?)', ((base,) for base in legacy[1]))
        db.executemany('INSERT OR IGNORE INTO scope VALUES (?)', ((base,) for base in roster))


def completed_prefixes(db, batches):
    return {prefix for prefix, signature in db.execute('SELECT value,roster FROM prefix')
            if prefix in batches and signature == roster_digest(batches[prefix])}


def save_prefix(db, prefix, rows, displayed, roster):
    if len(rows) != displayed:
        raise ValueError(f'{prefix}: expected {displayed} displayed cards, received {len(rows)}.')
    records = []
    for row in rows:
        if set(row) != {'Parcela', 'Dirección física', 'Municipio'}:
            raise ValueError(f'{prefix}: the public result layout changed.')
        base = number(row['Parcela'])
        if not base or len(base) != 11 or not base.startswith(prefix.replace('-', '')):
            raise ValueError(f'{prefix}: a displayed parcel does not match the requested prefix.')
        if base in roster:
            records.append((prefix, base, row['Dirección física'], row['Municipio']))
    with db:
        db.execute('DELETE FROM record WHERE prefix=?', (prefix,))
        db.executemany('INSERT OR IGNORE INTO record VALUES (?,?,?,?)', records)
        signature = roster_digest(base for base in roster if base.startswith(prefix.replace('-', '')))
        db.execute('INSERT OR REPLACE INTO prefix VALUES (?,?,?,?)',
                   (prefix, displayed, datetime.now(timezone.utc).isoformat(), signature))


def write_results(db, directory, town, roster, known, failed=()):
    towns = [town] if isinstance(town, str) else town
    mapped = roster if isinstance(roster, dict) else {base: {fold(town)} for base in roster}
    csv_path = directory / 'addresses.csv'
    rows = db.execute('SELECT DISTINCT catastro,address,municipio FROM record ORDER BY catastro,address,municipio')
    returned, populated, eligible = set(), set(), set()
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', newline='', dir=directory, delete=False) as stream:
        writer = csv.writer(stream)
        writer.writerow(['catastro', 'address', 'municipio'])
        wordings = 0
        for base, address, municipality in rows:
            if base not in roster:
                continue
            returned.add(base)
            if address.strip():
                populated.add(base)
                writer.writerow((base, address, municipality))
                wordings += 1
                if fold(municipality) in mapped[base]:
                    eligible.add(base)
    Path(stream.name).replace(csv_path)
    batches = grid_rosters(base for base, in db.execute('SELECT base FROM scope'))
    selected = grid_rosters(roster)
    completed = completed_prefixes(db, batches) & selected.keys()
    checked = returned | {base for prefix in completed for base in selected[prefix]}
    summary = dict(municipio=towns[0] if len(towns) == 1 else None, municipios=towns,
                   roster_parcels=len(roster), completed_prefixes=len(completed),
                   total_prefixes=len(selected), returned_parcels=len(returned),
                   nonblank_address_parcels=len(populated), csv_parcels=len(populated), csv_wordings=wordings,
                   municipio_matched_parcels=len(eligible), newly_collected_parcels=len(populated - known),
                   empty_address_parcels=len(returned - populated),
                   missing_parcels=len(checked - returned), unqueried_parcels=len(set(roster) - checked),
                   failed_prefixes=list(failed), csv=str(csv_path))
    summary['complete'] = summary['completed_prefixes'] == summary['total_prefixes']
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=directory, delete=False) as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    Path(stream.name).replace(directory / 'summary.json')
    return summary


class PublicQueryFailed(ValueError):
    """The public viewer explicitly rejected a query, without returning records."""


class PublicResultTooLarge(ValueError):
    """Narrow a grouped search before loading an unnecessarily large result."""


class PublicQueryTimeout(ValueError):
    """The browser could not finish a public query within its normal timeout."""


def search_groups(prefixes, width):
    groups = {}
    for prefix in prefixes:
        groups.setdefault(prefix[:width], []).append(prefix)
    return [(grids[0] if len(grids) == 1 else prefix, grids) for prefix, grids in groups.items()]


def split_results(prefix, grids, rows, displayed):
    if len(rows) != displayed:
        raise ValueError(f'{prefix}: incomplete grouped result.')
    result = {grid: [] for grid in grids}
    for row in rows:
        if set(row) != {'Parcela', 'Dirección física', 'Municipio'}:
            raise ValueError(f'{prefix}: the public result layout changed.')
        base = number(row['Parcela'])
        if not base or len(base) != 11 or not base.startswith(prefix.replace('-', '')):
            raise ValueError(f'{prefix}: a displayed parcel does not match the requested prefix.')
        grid = base[:3] + '-' + base[3:6]
        if grid in result:
            result[grid].append(row)
    return result


class PublicSearch:
    max_records = None
    def __init__(self, page):
        self.page = page
        self.sequence = 0
        page.set_default_timeout(90000)
        page.goto(VIEWER, wait_until='domcontentloaded')
        page.get_by_role('button', name='OK', exact=True, disabled=False).click()
        page.locator('.jimu-anchorbar-iconitem[settingid^="widgets_Query_Widget_"]').click()
        self.widget = page.locator('.jimu-widget-query')
        self.widget.locator('.tasks-table tr').filter(has_text=re.compile(r'^Parcela$')).click()

    def restart(self):
        # A capped or timed-out query may still update its page. Keep those late
        # responses out of the narrower search by discarding the old context.
        browser = self.page.context.browser
        self.page.close()
        self.__init__(browser.new_page(viewport={'width': 1280, 'height': 900}, locale='en-US'))

    def wait_for_result(self, condition, arg=None):
        self.page.wait_for_function(r"""state => {
            const failed = Array.from(document.querySelectorAll('.jimu-message')).some(e =>
                e.getClientRects().length && /^Query failed\s*!$/.test(e.querySelector('.content')?.textContent.trim() || ''));
            return failed || (""" + condition + '); }', arg=arg)
        message = self.page.locator('.jimu-message:visible').filter(has_text=re.compile(r'Query failed\s*!')).first
        if message.count():
            element = message.element_handle()
            message.get_by_role('button', name='OK', exact=True, disabled=False).click()
            self.page.wait_for_function('element => !element.isConnected || !element.getClientRects().length', arg=element)
            raise PublicQueryFailed('The public viewer reports Query failed !')

    def lookup(self, prefix):
        for attempt in range(3):
            try:
                return self.query(prefix)
            except PublicQueryFailed:
                if attempt == 2:
                    raise
                print(f'{prefix}: public query failed; retrying ({attempt + 2}/3)', flush=True)
                time.sleep(2 ** (attempt + 1))

    def query(self, prefix):
        from playwright.sync_api import TimeoutError as BrowserTimeout
        try:
            return self.query_pages(prefix)
        except BrowserTimeout as error:
            raise PublicQueryTimeout(f'{prefix}: the public search timed out; completed grids are saved.') from error

    def query_pages(self, prefix):
        self.wait_for_result('true')  # Dismiss a leftover failure before operating the form again.
        widget = self.widget
        if not widget.locator('input[id^="dijit_form_ValidationTextBox"]:visible').count():
            widget.locator('.query-tab-item[title="Tasks"]').click()
        field = widget.locator('input[id^="dijit_form_ValidationTextBox"]:visible')
        field.fill(prefix)
        # Distinguish this response from the previous prefix while the request runs.
        self.sequence += 1
        name = f'Lastbook {prefix} {self.sequence}'
        widget.locator('input[id^="dijit_form_TextBox"]:visible').fill(name)
        widget.get_by_text('Apply', exact=True).click()
        self.wait_for_result("""!Array.from(document.querySelectorAll(
            '.jimu-widget-query input[id^="dijit_form_ValidationTextBox"]')).some(e => e.getClientRects().length)""")
        self.wait_for_result(r"""Array.from(document.querySelectorAll('.jimu-widget-query *')).some(e =>
            e.getClientRects().length && e.textContent.replace(/\s+/g,' ').trim() === state)""", arg=name)
        results = widget.locator('.features-result:visible')
        counter = results.locator('[data-dojo-attach-point="numSpan"]')
        while True:
            self.wait_for_result(r"""(() => {
                const active = Array.from(document.querySelectorAll('.features-result')).find(e=>e.getClientRects().length);
                const counter = active?.querySelector('[data-dojo-attach-point="numSpan"]');
                return !!counter?.getClientRects().length && /^\s*[\d,]+\s*\/\s*[\d,]+\s*$/.test(counter.textContent);
            })()""")
            previous = counter.inner_text()
            value = previous.replace(',', '')
            match = re.fullmatch(r'\s*(\d+)\s*/\s*(\d+)\s*', value)
            if not match:
                raise ValueError(f'{prefix}: unrecognized public result count.')
            displayed, total = map(int, match.groups())
            if self.max_records is not None and total > self.max_records:
                raise PublicResultTooLarge(f'{prefix}: narrow the {total}-card public result.')
            self.wait_for_result("""(() => {
                const active = Array.from(document.querySelectorAll('.features-result')).find(e=>e.getClientRects().length);
                if (!active) return false;
                const cards = Array.from(active.querySelectorAll('.attrTable'));
                return cards.length === state.count && cards.every(card => {
                    const row = Array.from(card.rows).find(r => r.cells[0]?.textContent.trim() === 'Parcela');
                    return row?.cells[1]?.textContent.trim().startsWith(state.prefix);
                });
            })()""", arg={'count': displayed, 'prefix': prefix})
            if displayed == total:
                if total == 0:
                    # An empty counter can precede the cards or an explicit error while the viewer renders.
                    self.page.wait_for_timeout(1000)
                    self.wait_for_result('true')
                    if counter.inner_text() != previous:
                        continue
                return results.evaluate(READ_RESULTS), total
            more = results.locator('.load-more-button:visible')
            more.click()
            self.wait_for_result("""(() => {
                const active = Array.from(document.querySelectorAll('.features-result')).find(e=>e.getClientRects().length);
                return active?.querySelector('[data-dojo-attach-point="numSpan"]')?.textContent.trim() !== state.trim();
            })()""", arg=previous)


def fetch(index, directory, municipio=(), prefixes=(), show_browser=False, regions=(), whole_island=False, plan=False,
          group_grids=False):
    towns, roster, known = area_roster(index, municipio, regions, whole_island)
    all_prefixes = sorted(grid_rosters(roster))
    if plan:
        return dict(municipios=towns, roster_parcels=len(roster), total_prefixes=len(all_prefixes), indexed_crim_parcels=len(known))
    if set(prefixes) - set(all_prefixes):
        raise ValueError('Each --prefix must be a mapped grid in the selected area (000-000).')
    if directory is None:
        raise ValueError('Choose a results directory.')
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (directory / '.lock').open('a+b') as lock:
        if lock.tell() == 0:
            lock.write(b'0')
            lock.flush()
        try_lock(lock)
        with closing(sqlite3.connect(directory / 'prefixes.sqlite')) as db:
            checkpoint(db, towns, roster, legacy_selection(index, db))
            batches = grid_rosters(base for base, in db.execute('SELECT base FROM scope'))
            done = completed_prefixes(db, batches)
            pending = [p for p in prefixes or all_prefixes if p not in done]
            failed = []
            consecutive_failures = 0
            try:
                if pending:
                    from playwright.sync_api import sync_playwright
                    with sync_playwright() as playwright:
                        browser = playwright.chromium.launch(headless=not show_browser)
                        try:
                            search = PublicSearch(browser.new_page(viewport={'width': 1280, 'height': 900}, locale='en-US'))
                            searches = deque(search_groups(pending, 5 if group_grids else 7))
                            while searches:
                                prefix, grids = searches.popleft()
                                search.max_records = 5000 if len(grids) > 1 else None
                                try:
                                    rows, count = search.lookup(prefix)
                                except (PublicQueryFailed, PublicResultTooLarge, PublicQueryTimeout) as error:
                                    if len(grids) > 1:
                                        print(f'{prefix}: narrowing grouped search to smaller grids', flush=True)
                                        searches.extendleft(reversed(search_groups(grids, len(prefix) + 1)))
                                        search.restart()
                                        time.sleep(1)
                                        continue
                                    if not isinstance(error, PublicQueryFailed):
                                        raise
                                    failed.append(prefix)
                                    consecutive_failures += 1
                                    print(f'{prefix}: query failed three times; left unqueried for the next run', flush=True)
                                    if consecutive_failures >= 3:
                                        raise ValueError('Stopped after three consecutive prefixes failed. '
                                                         'Completed searches were saved. Retry later.')
                                    time.sleep(1)
                                    continue
                                if count == 0 and len(grids) > 1:
                                    # Confirm empty groups through their smaller searches.
                                    searches.extendleft(reversed(search_groups(grids, len(prefix) + 1)))
                                    search.restart()
                                    time.sleep(1)
                                    continue
                                partitioned = split_results(prefix, grids, rows, count)
                                consecutive_failures = 0
                                for grid, records in partitioned.items():
                                    save_prefix(db, grid, records, len(records), batches[grid])
                                    done.add(grid)
                                    print(f'{grid}: saved {len(records)} displayed records; {len(done & set(all_prefixes))}/{len(all_prefixes)} prefixes', flush=True)
                                time.sleep(1)
                        finally:
                            browser.close()
            finally:
                summary = write_results(db, directory, towns, roster, known, failed)
            if failed:
                raise ValueError(f'{len(failed)} prefixes remain unqueried after public query failures. '
                                 'Completed searches were saved. Run the same command to retry them.')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('index', type=Path, help='Existing parcel-enabled PR.sqlite')
    parser.add_argument('directory', type=Path, nargs='?', help='Local results and resumable checkpoint directory')
    area_arguments(parser)
    parser.add_argument('--plan', action='store_true', help='Preview selected municipios and mapped parcel/prefix counts')
    parser.add_argument('--prefix', action='append', default=[], help='Collect a specific mapped 000-000 grid (repeatable)')
    parser.add_argument('--show-browser', action='store_true')
    parser.add_argument('--group-grids', action='store_true', help='Combine neighboring grids in fewer public searches')
    args = parser.parse_args()
    try:
        print(json.dumps(fetch(args.index, args.directory, args.municipio, args.prefix, args.show_browser,
                               args.region, args.whole_island, args.plan, args.group_grids), ensure_ascii=False, indent=2))
    except KeyboardInterrupt:
        parser.exit(130, 'Stopped. Run the same command to resume.\n')
    except (ValueError, OSError, sqlite3.Error) as exc:
        parser.exit(1, f'{exc}\n')
