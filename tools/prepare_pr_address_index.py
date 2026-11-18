"""Build an offline Puerto Rico address pack directly from the publishers' public downloads."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import shutil
import sys
import tempfile
from urllib.request import urlopen

import osmium

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import build_pr_addresses, fetch_pr_parcels, fetch_pr_rural

OSM = 'https://download.geofabrik.de/north-america/us/puerto-rico-latest.osm.pbf'


def download(url, path):
    if path.is_file():
        return
    print('Downloading', path.name, flush=True)
    with tempfile.TemporaryDirectory(dir=path.parent) as tmp:
        pending = Path(tmp) / path.name
        with urlopen(url, timeout=120) as response, pending.open('wb') as target:
            shutil.copyfileobj(response, target)
            length = response.headers.get('Content-Length')
            if length is not None and target.tell() != int(length):
                raise ValueError('Incomplete download of ' + path.name)
        if path.suffix == '.geojson':
            build_pr_addresses.boundaries(pending)
        else:
            with closing(osmium.io.Reader(str(pending))) as reader:
                if not reader.header().get('osmosis_replication_timestamp'):
                    raise ValueError('Missing OSM replication timestamp in ' + path.name)
        pending.replace(path)


def prepare(folder, crim_addresses=()):
    cache = folder / 'inputs'
    cache.mkdir(parents=True, exist_ok=True)
    osm, census = cache / 'puerto-rico.osm.pbf', cache / 'municipios.geojson'
    rural, parcels = cache / 'rural', cache / 'parcels'
    download(OSM, osm)
    download(build_pr_addresses.BOUNDARIES, census)
    if not all((rural / name).is_file() for name in ('hpms-roads.json', 'barrios.json', 'zctas.json', 'schools.json')):
        fetch_pr_rural.fetch(rural)
    if not (parcels / 'sources.json').is_file():
        fetch_pr_parcels.fetch(parcels)
    return build_pr_addresses.build(osm, census, folder, rural, parcels, crim_addresses)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path, help='Location for the completed pack and its cached inputs')
    parser.add_argument('--crim-addresses', type=Path, action='append', default=[],
                        help='Additional physical-address CSV supplied by CRIM (may be repeated)')
    args = parser.parse_args()
    print(json.dumps(prepare(args.directory, args.crim_addresses), indent=2))
