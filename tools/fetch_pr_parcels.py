"""Fetch parcel geometry and physical permit addresses from Puerto Rico's Planning Board on a build machine."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.fetch_pr_rural import query

BOARD = 'https://sigejp.pr.gov/server/rest/services/'
LAYERS = {
    'parcels': (BOARD + 'crim/crim_feb_2025/MapServer/0', 'NUM_CATASTRO', '', ''),
    'sip': (BOARD + 'MIPR/Permisos/MapServer/8', 'Catastro', 'Dirección', 'Municipio'),
    'arpe': (BOARD + 'MIPR/Permisos/MapServer/16', 'CATASTRO', 'DIRECCIÓN', 'PUEBLO'),
}
BATCH = 1500


def fetch_layer(root, name):
    url, number, street, town = LAYERS[name]
    where = f"{number} IS NOT NULL AND " + (f"{street} IS NOT NULL" if street else "TIPO='P'")
    ids = sorted(query(url, where=where, returnIdsOnly='true')['objectIds'])
    if not ids or len(ids) != len(set(ids)):
        raise ValueError('Missing or duplicate source IDs in ' + name)
    fingerprint = hashlib.sha256(json.dumps(ids, separators=(',', ':')).encode()).hexdigest()
    folder = root / (name + '-' + fingerprint[:16])
    folder.mkdir(parents=True, exist_ok=True)

    def page(start):
        expected = ids[start:start + BATCH]
        path = folder / f'{start:08d}.jsonl.gz'
        if path.exists():
            with gzip.open(path, 'rt', encoding='utf-8') as stream:
                if [json.loads(line)['id'] for line in stream] == expected:
                    return path.name
            raise ValueError('Incomplete saved page: ' + str(path))
        select = f'({where}) AND OBJECTID BETWEEN {expected[0]} AND {expected[-1]}'
        options = dict(where=select, outFields=','.join(filter(None, ['OBJECTID', number, street, town])),
                       returnGeometry='false' if street else 'true', orderByFields='OBJECTID')
        if not street:
            options.update(f='geojson', outSR=4326, geometryPrecision=6)
        items = query(url, **options)['features']
        rows = []
        for feature in items:
            a = feature.get('attributes') or feature['properties']
            row = {'id': a['OBJECTID'], 'catastro': a[number]}
            if street:
                row.update(address=a[street], municipio=a[town])
            else:
                row['geometry'] = feature['geometry']
            rows.append(row)
        rows.sort(key=lambda row: row['id'])
        if [row['id'] for row in rows] != expected:
            raise ValueError(f'Source changed or incomplete page in {name} at {start}.')
        with tempfile.NamedTemporaryFile(dir=folder, delete=False) as tmp:
            with gzip.GzipFile(fileobj=tmp, mode='wb', filename='', mtime=0) as output:
                for row in rows:
                    output.write((json.dumps(row, ensure_ascii=False, separators=(',', ':')) + '\n').encode())
        Path(tmp.name).replace(path)
        return path.name

    with ThreadPoolExecutor(max_workers=4) as pool:
        pages = list(pool.map(page, range(0, len(ids), BATCH)))
    return {'source': url, 'folder': folder.name, 'pages': pages, 'records': len(ids)}


def fetch(root):
    root.mkdir(parents=True, exist_ok=True)
    layers = {}
    for name in LAYERS:
        layers[name] = fetch_layer(root, name)
        print(name, layers[name]['records'], flush=True)
    with tempfile.NamedTemporaryFile('w', dir=root, delete=False, encoding='utf-8') as tmp:
        json.dump(layers, tmp, sort_keys=True, indent=2)
    Path(tmp.name).replace(root / 'sources.json')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    fetch(parser.parse_args().directory)
