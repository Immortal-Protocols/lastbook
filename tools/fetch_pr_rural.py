"""Fetch fresh public inputs for tools/build_pr_addresses.py --rural (build machine only)."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
import tempfile
import time
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.build_pr_rural import BARRIOS, HPMS, SCHOOLS, ZCTAS


def query(layer, **params):
    url = layer + '/query?' + urlencode({'f':'json', **params})
    for attempt in range(3):
        try:
            with urlopen(url, timeout=100) as stream:
                reply = json.load(stream)
            if reply.get('error') or reply.get('exceededTransferLimit'):
                raise ValueError(f'Incomplete response from {layer}: {reply.get("error", "transfer limit")}')
            return reply
        except (TimeoutError, URLError):
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def roads():
    ids = sorted(query(HPMS, where="route_id LIKE 'PR-%'", returnIdsOnly='true')['objectIds'])
    if not ids or len(set(ids)) != len(ids):
        raise ValueError('Expected distinct federal road feature IDs.')

    def batch(start):
        part = ids[start:start + 200]
        response = query(HPMS, objectIds=','.join(map(str, part)), outFields='objectid,route_id',
                         outSR=4326, returnM='true', geometryPrecision=7)
        if not response.get('hasM') or sorted(f['attributes']['objectid'] for f in response['features']) != part:
            raise ValueError('Incomplete federal road geometry or measures.')
        return response['features']

    with ThreadPoolExecutor(max_workers=4) as pool:
        features = [f for page in pool.map(batch, range(0, len(ids), 200)) for f in page]
    features.sort(key=lambda f: f['attributes']['objectid'])
    return {'hasM':True, 'spatialReference':{'wkid':4326}, 'features':features}


def complete(layer, where, id_field, **params):
    count = query(layer, where=where, returnCountOnly='true')['count']
    response = query(layer, where=where, **params)
    keys = {(f.get('properties') or f['attributes'])[id_field] for f in response['features']}
    if not count or count != len(keys) or count != len(response['features']):
        raise ValueError(f'Expected {count} unique records from {layer}.')
    return response


def fetch(folder):
    folder.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=folder) as temp:
        stage = Path(temp)
        def save(name, data):
            (stage / name).write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
            print(name, len(data['features']), flush=True)
        save('hpms-roads.json', roads())
        polygon = {'f':'geojson', 'outSR':4326, 'geometryPrecision':5}
        save('barrios.json', complete(BARRIOS, "STATE='72'", 'GEOID', outFields='GEOID,NAME,COUNTY,COUSUB,BASENAME', **polygon))
        save('zctas.json', complete(ZCTAS, "ZCTA5 LIKE '006%' OR ZCTA5 LIKE '007%' OR ZCTA5 LIKE '009%'",
                                    'ZCTA5', outFields='ZCTA5', **polygon))
        save('schools.json', complete(SCHOOLS, "STATE='PR'", 'NCESSCH', outFields='NCESSCH,NAME,STREET,CITY,STATE,ZIP,LAT,LON',
                                      returnGeometry='false', resultRecordCount=2000))
        for path in stage.iterdir():
            path.replace(folder / path.name)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    fetch(parser.parse_args().directory)
