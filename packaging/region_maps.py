"""Build, check, zip, upload and list one non-US region's detailed map (docs/MAPS.md, "Region maps").

  derived/app-build/mac-venv/bin/python3 -I -B packaging/region_maps.py ve-a ...   # one region at a time, in this order
  ... packaging/region_maps.py --order                                              # every region, in release order

Each region: build (a Geofabrik OpenStreetMap extract clipped to the region's box), scan, zip to
derived/packs/region-zips/, upload to maps/ on the bucket, check the public SHA-256, list it under "maps" in
derived/release/manifest-v1.json and upload that, then delete the zip and the build copy. Results go to
derived/packs/region-maps.json and REGION-MAPS.md.
"""
import fcntl
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAPS = ROOT / 'derived/packs/maps'
ZIPS = ROOT / 'derived/packs/region-zips'
RESULTS = ROOT / 'derived/packs/region-maps.json'
LOCK = ROOT / 'derived/packs/region-maps.lock'      # one writer at a time for the manifest, results and table
TABLE = ROOT / 'derived/packs/REGION-MAPS.md'

sys.path.insert(0, str(ROOT / 'packaging'))
sys.path.insert(0, str(ROOT / 'derived/release'))
import scan_pack as S            # noqa: E402
from build_packs import REGIONS  # noqa: E402

INCLUDES = 'Local streets, buildings, water and places to get help'
ALLOWED = {'derived/geo/map.sqlite', 'derived/geo/detail-cells.json', 'derived/geo/national-status.json', 'map-set.json'}


def regions():
    return list(REGIONS)


def scan(d, code):
    """The scan_pack rules that apply to a region map set, and the region-set rules: only the listed files, nothing about the household's area, and map.sqlite itself is the detail."""
    terms = S.read_terms(str(ROOT / 'derived/packs/private-terms.txt'))
    if not terms:
        sys.exit('no private terms')
    sc = S.Scan(d, terms, {}, None)
    sc.done_early = set()
    files = sc.walk()
    rels = [p.relative_to(d).as_posix() for p in files]
    fails = []
    if set(rels) != ALLOWED:
        fails.append(f'files differ from the contract: extra {sorted(set(rels) - ALLOWED)} missing {sorted(ALLOWED - set(rels))}')
    for p, rel in zip(files, rels):
        st = os.lstat(p)
        if rel == 'map-set.json':
            info = sc.load_json(rel, rels, 'map-set')
            if not isinstance(info, dict) or info.get('name') != code or set(info) - {'name', 'files', 'bytes', 'seconds'}:
                fails.append('map-set.json does not name the region')
            continue
        sc.name_rules(rel, st, p.is_symlink())
        if rel == 'derived/geo/detail-cells.json':
            data = sc.load_json(rel, rels, 'status')
            if not (isinstance(data, dict) and data.get('name') == code and not set(data) - {'name', 'bbox', 'cells'}
                    and isinstance(data.get('bbox'), list) and len(data['bbox']) == 4 and all(isinstance(v, (int, float)) for v in data['bbox'])
                    and isinstance(data.get('cells'), list)):
                fails.append('detail-cells.json is not the region box')
        elif rel == 'derived/geo/national-status.json':
            data = sc.load_json(rel, rels, 'status')
            if not isinstance(data, dict) or set(data) - {'state', 'stage', 'features'}:
                fails.append('status fields')
        else:
            sc.inspect_map(rel, p)
            db = sqlite3.connect(f'file:{p}?immutable=1', uri=True)
            for t in ('meta', 'metadata'):
                if db.execute('SELECT 1 FROM sqlite_master WHERE name=?', (t,)).fetchone():
                    for row in db.execute(f'SELECT * FROM "{t}"'):
                        for x in row:
                            if isinstance(x, str) and (S.HOUSEHOLD.search(x.encode()) or S.USER_PATH.search(x.encode()) or S.LAN.search(x.encode())):
                                fails.append(f'{rel}: {t} names the household, a local path or a LAN address')
            if rel == 'derived/geo/map.sqlite' and not db.execute('SELECT 1 FROM feat LIMIT 1').fetchone():
                fails.append('map.sqlite holds no features (a region map is its own detail)')
            if db.execute("SELECT 1 FROM sqlite_master WHERE name IN ('done','done_socal')").fetchone():
                fails.append(f'{rel}: build progress tables left in')
            db.close()
    for rule, paths in sc.fails.items():
        fails.append(f'{rule}: {paths[:5]}')
    return fails, sc.listed


def make_zip(d, out):
    tmp = out.with_suffix('.partial')
    with zipfile.ZipFile(tmp, 'w', allowZip64=True) as z:
        for rel in sorted(ALLOWED):
            zi = zipfile.ZipInfo(rel, date_time=(2026, 11, 16, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            with open(d / rel, 'rb') as src, z.open(zi, 'w', force_zip64=True) as dst:
                while b := src.read(1 << 24):
                    dst.write(b)
    with zipfile.ZipFile(tmp) as z:
        names = {i.filename: i.file_size for i in z.infolist()}
    if names != {rel: (d / rel).stat().st_size for rel in ALLOWED}:
        sys.exit('zip does not hold exactly the set')
    os.replace(tmp, out)


def list_in_manifest(ctx, entry):
    """Like state_maps.list_in_manifest, but regions are appended after the states already listed (no state order to preserve)."""
    import state_maps as SM
    m = json.loads(SM.MANIFEST.read_text())
    packs, models = json.dumps(m['packs']), json.dumps(m.get('models'))
    m['maps'] = [x for x in m.get('maps', []) if x['id'] != entry['id']] + [entry]
    assert json.dumps(m['packs']) == packs and json.dumps(m.get('models')) == models
    tmp = SM.MANIFEST.with_suffix('.maps-tmp')
    tmp.write_text(json.dumps(m, indent=1) + '\n')
    os.replace(tmp, SM.MANIFEST)
    data = SM.MANIFEST.read_bytes()
    st, _, out = SM.R.s3(ctx, 'PUT', 'manifest-v1.json', body=data, headers={'content-type': 'application/json; charset=utf-8'})
    if st != 200:
        sys.exit(f'manifest upload HTTP {st}')
    for _ in range(10):
        got, _n = SM.public_sha(f'{SM.BASE}/manifest-v1.json')
        if got == hashlib.sha256(data).hexdigest():
            return
        time.sleep(3)
    sys.exit('public manifest does not match')


def write_table(res):
    rows = ['# Region maps', '', 'One detailed map per non-US region, for first-run setup (docs/MAPS.md, "Region maps"). Built by', '`packaging/region_maps.py`; each zip was scanned, uploaded, checked by its public SHA-256 and then listed under', '`maps` in `manifest-v1.json`.', '', '| Region | Zip size | Installed size | SHA-256 | URL |', '|---|---:|---:|---|---|']
    for code in sorted(res):
        r = res[code]
        spec = REGIONS.get(code, {})
        rows.append(f"| {spec.get('title', code)} | {r['size'] / 1e9:.2f} GB ({r['size']:,}) | {r['installed_bytes'] / 1e9:.2f} GB ({r['installed_bytes']:,}) | `{r['sha256']}` | {r['url']} |")
    TABLE.write_text('\n'.join(rows) + '\n')


def one_region(ctx, code, res):
    import state_maps as SM
    d = MAPS / code
    t0 = time.time()
    while shutil.disk_usage(ROOT).free < 5e9:      # the extract and its build
        SM.log(code, 'waiting for disk space')
        time.sleep(120)
    SM.log(code, 'building')
    subprocess.run([sys.executable, '-I', '-B', str(ROOT / 'packaging/build_packs.py'), 'map', code], check=True, stdout=subprocess.DEVNULL)
    fails, listed = scan(d, code)
    wf, web = SM.web_text(d)
    fails += wf
    if fails:
        sys.exit(f'{code} scan failed: {fails}')
    SM.log(code, 'scan passed', dict((k, len(v)) for k, v in listed.items()))
    installed = sum((d / rel).stat().st_size for rel in ALLOWED)
    ZIPS.mkdir(exist_ok=True)
    z = ZIPS / f'Lastbook-Map-{code}.zip'
    make_zip(d, z)
    sha, size = SM.sha_file(z), z.stat().st_size
    SM.log(code, 'zipped', size)
    key = f'maps/{z.name}'
    SM.upload(ctx, z, key)
    url = f'{SM.BASE}/{key}'
    got, n = SM.public_sha(url)
    if got != sha or n != size:
        sys.exit(f'{code}: public copy differs ({got} {n})')
    SM.log(code, 'public copy verified')
    spec = REGIONS[code]
    entry = {'id': code, 'title': spec['title'], 'country': spec['country'], 'kind': 'region', 'installed_bytes': installed, 'available': True,
             'includes': INCLUDES, 'files': [{'name': z.name, 'url': url, 'size': size, 'sha256': sha, 'kind': 'zip'}]}
    with open(LOCK, 'a') as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        list_in_manifest(ctx, entry)
        res.clear()
        res.update(json.loads(RESULTS.read_text()) if RESULTS.exists() else {})
        res[code] = {'size': size, 'installed_bytes': installed, 'sha256': sha, 'url': url, 'web_address_text': web, 'seconds': round(time.time() - t0)}
        tmp = RESULTS.with_suffix('.tmp')
        tmp.write_text(json.dumps(res, indent=1) + '\n')
        os.replace(tmp, RESULTS)
        write_table(res)
    SM.log(code, 'listed')
    z.unlink()
    shutil.rmtree(d)


def main():
    args = sys.argv[1:]
    if args[:1] == ['--zip-only']:
        if not args[1:] or any(code not in regions() for code in args[1:]):
            sys.exit('usage: region_maps.py --zip-only <built region> ...')
        ZIPS.mkdir(parents=True, exist_ok=True)
        for code in args[1:]:
            archive = ZIPS / f'Lastbook-Map-{code}.zip'
            make_zip(MAPS / code, archive)
            print(archive)
        return
    import state_maps as SM  # release-only tools and bucket access
    ctx = SM.R.Context()
    todo = regions() if args == ['--order'] else args
    res = json.loads(RESULTS.read_text()) if RESULTS.exists() else {}
    for code in todo:
        if code not in REGIONS:
            sys.exit(f'unknown region {code}')
        if code in res:
            continue
        one_region(ctx, code, res)
    SM.log('done', len(res), 'regions')


if __name__ == '__main__':
    main()
