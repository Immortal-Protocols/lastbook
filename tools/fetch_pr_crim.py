"""Save the public CRIM Parcela prefix-search results for an offline municipio index.

Run on a connected build machine. This tool operates the public search form in a
fresh browser and reads its displayed parcel, physical-address and municipio fields.
"""
import argparse
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


def municipio_roster(index, requested):
    with closing(sqlite3.connect(ro_uri(index), uri=True)) as db:
        names = {fold(name): name for name, in db.execute('SELECT name FROM municipios')}
        town = names.get(fold(requested))
        if town is None:
            raise ValueError('Municipio is absent from the index.')
        roster = {base for base, name in db.execute('SELECT DISTINCT base,municipio FROM pr_parcel')
                  if fold(name or '') == fold(town)}
        if not roster or any(not re.fullmatch(r'[0-9]{11}', base) for base in roster):
            raise ValueError('Expected mapped 11-digit land numbers for the selected municipio.')
        known = {base for base, name in db.execute("SELECT DISTINCT base,town FROM pr_permit_wording WHERE source='CRIM'")
                 if fold(name or '') == fold(town)}
    return town, roster, known


def checkpoint(db, town, roster):
    identity = json.dumps([VIEWER, town, sorted(roster)], ensure_ascii=False, separators=(',', ':'))
    fingerprint = hashlib.sha256(identity.encode()).hexdigest()
    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if tables:
        if not {'meta', 'prefix', 'record'} <= tables:
            raise ValueError('The checkpoint file belongs to another program.')
        if db.execute("SELECT value FROM meta WHERE key='roster'").fetchone() != (fingerprint,):
            raise ValueError('This checkpoint uses a different source or municipio roster. Choose a new directory.')
        return
    with db:
        db.executescript("""
            CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT);
            CREATE TABLE prefix(value TEXT PRIMARY KEY,displayed INTEGER,completed TEXT);
            CREATE TABLE record(prefix TEXT,catastro TEXT,address TEXT,municipio TEXT,
                PRIMARY KEY(prefix,catastro,address,municipio)) WITHOUT ROWID;
        """)
        db.execute('INSERT INTO meta VALUES (?,?)', ('roster', fingerprint))


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
        db.execute('INSERT OR REPLACE INTO prefix VALUES (?,?,?)',
                   (prefix, displayed, datetime.now(timezone.utc).isoformat()))


def write_results(db, directory, town, roster, known):
    csv_path = directory / 'addresses.csv'
    rows = db.execute('SELECT DISTINCT catastro,address,municipio FROM record ORDER BY catastro,address,municipio')
    returned, populated, eligible = set(), set(), set()
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', newline='', dir=directory, delete=False) as stream:
        writer = csv.writer(stream)
        writer.writerow(['catastro', 'address', 'municipio'])
        wordings = 0
        for base, address, municipality in rows:
            returned.add(base)
            if address.strip():
                populated.add(base)
                if fold(municipality) == fold(town):
                    eligible.add(base)
                    writer.writerow((base, address, town))
                    wordings += 1
    Path(stream.name).replace(csv_path)
    completed = {row[0].replace('-', '') for row in db.execute('SELECT value FROM prefix')}
    checked = {base for base in roster if base[:6] in completed}
    summary = dict(municipio=town, roster_parcels=len(roster), completed_prefixes=db.execute('SELECT count(*) FROM prefix').fetchone()[0],
                   total_prefixes=len({base[:6] for base in roster}), returned_parcels=len(returned),
                   nonblank_address_parcels=len(populated), csv_parcels=len(eligible), csv_wordings=wordings,
                   newly_collected_parcels=len(eligible - known), empty_address_parcels=len(returned - populated),
                   missing_parcels=len(checked - returned), unqueried_parcels=len(roster - checked), csv=str(csv_path))
    summary['complete'] = summary['completed_prefixes'] == summary['total_prefixes']
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=directory, delete=False) as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    Path(stream.name).replace(directory / 'summary.json')
    return summary


class PublicSearch:
    def __init__(self, page):
        self.page = page
        page.set_default_timeout(90000)
        page.goto(VIEWER, wait_until='domcontentloaded')
        page.get_by_role('button', name='OK', exact=True).click()
        page.locator('.jimu-anchorbar-iconitem[settingid^="widgets_Query_Widget_"]').click()
        self.widget = page.locator('.jimu-widget-query')
        self.widget.locator('.tasks-table tr').filter(has_text=re.compile(r'^Parcela$')).click()

    def lookup(self, prefix):
        widget = self.widget
        if not widget.locator('input[id^="dijit_form_ValidationTextBox"]:visible').count():
            widget.locator('.query-tab-item[title="Tasks"]').click()
        field = widget.locator('input[id^="dijit_form_ValidationTextBox"]:visible')
        field.fill(prefix)
        # Distinguish this response from the previous prefix while the request runs.
        name = 'Lastbook ' + prefix
        widget.locator('input[id^="dijit_form_TextBox"]:visible').fill(name)
        widget.get_by_text('Apply', exact=True).click()
        field.wait_for(state='hidden')
        widget.get_by_text(name, exact=True).wait_for(state='visible')
        results = widget.locator('.features-result:visible')
        counter = results.locator('[data-dojo-attach-point="numSpan"]')
        counter.wait_for(state='visible')
        while True:
            previous = counter.inner_text()
            value = previous.replace(',', '')
            match = re.fullmatch(r'\s*(\d+)\s*/\s*(\d+)\s*', value)
            if not match:
                raise ValueError(f'{prefix}: unrecognized public result count.')
            displayed, total = map(int, match.groups())
            self.page.wait_for_function("""expected => {
                const active = Array.from(document.querySelectorAll('.features-result')).find(e=>e.getClientRects().length);
                if (!active) return false;
                const cards = Array.from(active.querySelectorAll('.attrTable'));
                return cards.length === expected.count && cards.every(card => {
                    const row = Array.from(card.rows).find(r => r.cells[0]?.textContent.trim() === 'Parcela');
                    return row?.cells[1]?.textContent.trim().startsWith(expected.prefix);
                });
            }""", arg={'count': displayed, 'prefix': prefix})
            if displayed == total:
                return results.evaluate(READ_RESULTS), total
            more = results.locator('.load-more-button:visible')
            more.click()
            self.page.wait_for_function("""old => {
                const active = Array.from(document.querySelectorAll('.features-result')).find(e=>e.getClientRects().length);
                return active?.querySelector('[data-dojo-attach-point="numSpan"]')?.textContent.trim() !== old.trim();
            }""", arg=previous)


def fetch(index, directory, municipio, prefixes=(), show_browser=False):
    town, roster, known = municipio_roster(index, municipio)
    all_prefixes = sorted({base[:3] + '-' + base[3:6] for base in roster})
    if set(prefixes) - set(all_prefixes):
        raise ValueError('Each --prefix must be a mapped grid in the selected municipio (000-000).')
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (directory / '.lock').open('a+b') as lock:
        if lock.tell() == 0:
            lock.write(b'0')
            lock.flush()
        try_lock(lock)
        with closing(sqlite3.connect(directory / 'prefixes.sqlite')) as db:
            checkpoint(db, town, roster)
            done = {row[0] for row in db.execute('SELECT value FROM prefix')}
            pending = [p for p in prefixes or all_prefixes if p not in done]
            try:
                if pending:
                    from playwright.sync_api import sync_playwright
                    with sync_playwright() as playwright:
                        browser = playwright.chromium.launch(headless=not show_browser)
                        try:
                            search = PublicSearch(browser.new_page(viewport={'width': 1280, 'height': 900}))
                            for prefix in pending:
                                rows, count = search.lookup(prefix)
                                save_prefix(db, prefix, rows, count, roster)
                                print(f'{prefix}: saved {count} displayed records; {db.execute("SELECT count(*) FROM prefix").fetchone()[0]}/{len(all_prefixes)} prefixes', flush=True)
                                time.sleep(1)
                        finally:
                            browser.close()
            finally:
                summary = write_results(db, directory, town, roster, known)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('index', type=Path, help='Existing parcel-enabled PR.sqlite')
    parser.add_argument('directory', type=Path, help='Local results and resumable checkpoint directory')
    parser.add_argument('--municipio', required=True)
    parser.add_argument('--prefix', action='append', default=[], help='Collect a specific mapped 000-000 grid (repeatable)')
    parser.add_argument('--show-browser', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(fetch(args.index, args.directory, args.municipio, args.prefix, args.show_browser), ensure_ascii=False, indent=2))
    except KeyboardInterrupt:
        parser.exit(130, 'Stopped. Run the same command to resume.\n')
