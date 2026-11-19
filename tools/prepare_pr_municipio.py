"""Add municipal address records to a separate copy of a Lastbook Puerto Rico parcel index."""
import argparse
from contextlib import closing
from itertools import islice
import json
import re
from pathlib import Path
import sqlite3
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import pr_permit
from engine.paths import ro_uri
from engine.pr_addresses import fold
from tools.build_pr_parcels import PREFIXED_ACCOUNT, csv_records, labels
from tools.fetch_pr_rural import query
from tools.pr_areas import area_arguments, select_municipios

PLANNING = 'https://sigejp.pr.gov/server/rest/services/MIPR/Permisos/MapServer/20'


def planning_records(town):
    listing = query(PLANNING, where='1=1', returnDistinctValues='true', outFields='MUNICIPIO', returnGeometry='false')
    names = {}
    for feature in listing['features']:
        name = feature['attributes']['MUNICIPIO']
        if not name:
            continue
        district = re.fullmatch(r'SAN JUAN \((\d{2})\)', name, re.I)
        if fold('San Juan' if district else name) == fold(town):
            names[name] = district[1] if district else None
    if not names:
        return
    quoted = ','.join("'" + name.replace("'", "''") + "'" for name in sorted(names))
    where = f'MUNICIPIO IN ({quoted}) AND NUMERO_CAT IS NOT NULL'
    ids = query(PLANNING, where=where, returnIdsOnly='true')['objectIds']
    if ids is None:
        ids = []
    if len(ids) != len(set(ids)):
        raise ValueError('Planning Board returned duplicate record identifiers.')
    pending = iter(sorted(ids))
    while batch := list(islice(pending, 200)):
        page = query(PLANNING, where=where, objectIds=','.join(map(str, batch)),
                     outFields='OBJECTID,NUMERO_CAT,DIRECCION1,DIRECCION2,MUNICIPIO', returnGeometry='false')
        records = [f['attributes'] for f in page['features']]
        if sorted(row['OBJECTID'] for row in records) != batch:
            raise ValueError('Incomplete Planning Board response. Run again to build a complete copy.')
        for row in records:
            wording = ', '.join(part.strip() for part in (row['DIRECCION1'], row['DIRECCION2']) if part and part.strip())
            district = names[row['MUNICIPIO']]
            number = str(row['NUMERO_CAT'] or '').strip()
            account = PREFIXED_ACCOUNT.fullmatch(number)
            if district and account:
                if account[1] != district:
                    continue
                number = account[2]
            yield {'catastro': number, 'address': wording, 'municipio': town}


def prepare(original, output, municipio=(), planning=False, csv_paths=(), regions=(), whole_island=False):
    if not planning and not csv_paths:
        raise ValueError('Select --planning-board or --crim-addresses.')
    if output.exists():
        raise FileExistsError(f'Choose a new output path. {output} already exists.')
    with closing(sqlite3.connect(ro_uri(original), uri=True)) as source:
        tables = {row[0] for row in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'pr_permit_wording', 'pr_parcel', 'pr_account', 'pr_parcel_address', 'municipios'} <= tables:
            raise ValueError('Start with the Puerto Rico parcel-enabled address pack.')
        towns = select_municipios(source, municipio, regions, whole_island)
        keys = {fold(town) for town in towns}
        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=output.parent) as scratch:
            tmp = Path(scratch) / 'PR.sqlite'
            with closing(sqlite3.connect(tmp)) as dest:
                source.backup(dest)
                count = 'SELECT count(*),count(DISTINCT base) FROM pr_permit_wording WHERE town IN (' + ','.join('?' for _ in keys) + ')'
                before = dest.execute(count, tuple(keys)).fetchone()
                sources = [(csv_records(path), 'CRIM') for path in csv_paths]
                if planning:
                    sources.extend((planning_records(town), 'JP consulta') for town in towns)
                with dest:
                    dest.execute(pr_permit.VERBATIM_INDEX)
                    dest.execute(pr_permit.FIELDS_INDEX)
                    for records, name in sources:
                        labels(dest, (r for r in records if fold(r['municipio'] or '') in keys and (r['address'] or '').strip()), name)
                after = dest.execute(count, tuple(keys)).fetchone()
                if dest.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
                    raise ValueError('The new index failed its integrity check.')
            # Reserve a fresh name before replacement, including on removable drives without hard links.
            with output.open('xb'):
                pass
            try:
                tmp.replace(output)
            except OSError:
                output.unlink()
                raise
    return {'municipio': towns[0] if len(towns) == 1 else None, 'municipios': towns,
            'new_wordings': after[0] - before[0], 'new_parcels_with_wording': after[1] - before[1],
            'parcels_with_wording': after[1], 'index': str(output)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('index', type=Path, help='Existing parcel-enabled PR.sqlite')
    parser.add_argument('output', type=Path, help='New SQLite file to create')
    area_arguments(parser)
    parser.add_argument('--planning-board', action='store_true', help='Download public location records for this municipio')
    parser.add_argument('--crim-addresses', type=Path, action='append', default=[], help='Local physical-address CSV (repeatable)')
    args = parser.parse_args()
    try:
        print(json.dumps(prepare(args.index, args.output, args.municipio, args.planning_board, args.crim_addresses,
                                 args.region, args.whole_island),
                         indent=2, ensure_ascii=False))
    except (ValueError, OSError, sqlite3.Error) as exc:
        parser.exit(1, f'{exc}\n')
