"""Sample public ARPE records before the parcel join and check rural directions through the offline reader."""
import argparse
import collections
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import address_search
from engine.pr_addresses import fold
from tools.build_pr_parcels import pages

ACCOUNT = re.compile(r'[0-9]{2}-([0-9]{3}-[0-9]{3}-[0-9]{3}-[0-9]{2})-[0-9]{3}')
ROAD = re.compile(r'\b(?:carretera|carr|pr)[.\s#-]*([0-9]{1,4})\b', re.I)
KM = re.compile(r'\b(?:kil[oó]metros?|km(?:\.?hm)?)[.\s#]*([0-9]{1,3}(?:[.,][0-9]{1,3})?)\b', re.I)


def sample(folder, towns, size):
    """Keep the lowest hashes of distinct land numbers per municipio, independent of index membership."""
    source = json.loads((folder / 'sources.json').read_text())['arpe']
    selected = {fold(town): {} for town in towns}
    for row in pages(folder, source):
        town = fold(row['municipio'] or '')
        if town not in selected:
            continue
        text = row['address'] or ''
        account = ACCOUNT.fullmatch((row['catastro'] or '').strip())
        roads, marks = ROAD.findall(text), KM.findall(text)
        if not account or len(roads) != 1 or len(marks) != 1:
            continue
        land = account[1]
        rank = hashlib.sha256(land.encode('ascii')).digest()
        candidates = selected[town]
        if rank in candidates:
            continue
        if len(candidates) == size:
            last = max(candidates)
            if rank >= last:
                continue
            del candidates[last]
        candidates[rank] = land, text, roads[0], marks[0]
    return selected


def parcel_result(geo, query, land, model=None):
    if len(query) > 400 or not address_search.is_address_query(query):
        return False, 0
    offset = 0
    while True:
        rows = address_search.find_addresses(query, geo, model=model, parcel_offset=offset, parcel_limit=30)
        parcels = [row for row in rows if row['kind'] == 'Possible parcel']
        count = parcels[0]['parcelCount'] if parcels else 0
        if any(row['parcelNumber'] == land for row in parcels):
            return True, count
        offset += len(parcels)
        if not parcels or offset >= parcels[0]['parcelCount']:
            return False, count


def includes(geo, query, land, model=None):
    return parcel_result(geo, query, land, model)[0]


def full_directions(directions, town):
    return directions if f' {fold(town)} ' in f' {fold(directions)} ' else f'{directions}, {town}'


def read_rephrasings(path):
    queries = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        row = json.loads(line)
        key = row['sample_id']
        if key in queries or not all(isinstance(row[k], str) and row[k].strip() for k in ('spoken','typed','source_preserving')):
            raise ValueError('Duplicate sample ID or empty query in rephrased directions')
        queries[key] = row
    return queries


def sample_id(land, full):
    return hashlib.sha256((land + '\n' + full).encode()).hexdigest()


def evaluate(database, folder, size, model=None, rephrasings=None):
    with sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True) as db, tempfile.TemporaryDirectory() as tmp:
        geo = Path(tmp)
        (geo / 'addresses').mkdir()
        index = geo / 'addresses' / 'PR.sqlite'
        try:
            os.link(database, index)
        except OSError:  # A read-only drive or a temporary directory on another volume.
            shutil.copyfile(database, index)
        towns = [town for town, in db.execute('SELECT name FROM municipios ORDER BY name')]
        selected = sample(folder, towns, size)
        counts = collections.Counter()
        for town in towns:
            cases = selected[fold(town)]
            counts['municipios_sampled'] += bool(cases)
            for land, directions, road, km in cases.values():
                counts['cases'] += 1
                base = land.replace('-', '')
                exists = db.execute('SELECT 1 FROM pr_parcel WHERE base=?', (base,)).fetchone()
                counts['with_indexed_boundary'] += bool(exists)
                short = f'{town}, km {km}, PR-{road}'
                full = full_directions(directions, town)
                counts['road_km_municipio_returned_parcel'] += includes(geo, short, land)
                baseline = includes(geo, full, land)
                counts['source_directions_returned_parcel'] += baseline
                if rephrasings is not None:
                    row = rephrasings.pop(sample_id(land, full))
                    for style in ('spoken','typed','source_preserving'):
                        hit, total = parcel_result(geo, row[style], land, model)
                        counts[style + '_returned_parcel'] += hit
                        counts[style + '_single_correct_parcel'] += hit and total == 1
                        counts[style + '_other_parcels_only'] += not hit and total > 0
                if model is not None:
                    assisted = includes(geo, full, land, model)
                    counts['gemma_enabled_returned_parcel'] += assisted
                    counts['gemma_enabled_gained'] += assisted and not baseline
                    counts['gemma_enabled_lost'] += baseline and not assisted
        if rephrasings:
            raise ValueError('Rephrased directions include records outside this sample')
        return dict(counts)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database', type=Path)
    parser.add_argument('sources', type=Path, help='Snapshot directory from fetch_pr_parcels.py')
    parser.add_argument('--per-municipio', type=int, default=3)
    parser.add_argument('--gemma', action='store_true', help='also replay full directions with Lastbook’s local model enabled')
    parser.add_argument('--rephrasings', type=Path, help='replay saved spoken and typed queries from rephrase_pr_permits.py')
    args = parser.parse_args()
    if args.per_municipio < 1:
        parser.error('--per-municipio must be positive')
    model = None
    try:
        if args.gemma:
            import llm_local
            model = llm_local.LOCAL
            model.discover()
            problem = model.ensure_running()
            if problem or not model.enabled() or not model.available():
                parser.error(problem or 'Enable the installed local model before running --gemma.')
        queries = read_rephrasings(args.rephrasings) if args.rephrasings else None
        print(json.dumps(evaluate(args.database, args.sources, args.per_municipio, model, queries), indent=2))
    finally:
        if model is not None:
            model.stop('Finished permit address evaluation')
