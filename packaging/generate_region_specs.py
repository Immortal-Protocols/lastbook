"""Generate packaging/region_specs.py: one region map per sovereign-state capital.

Reads Natural Earth's populated places (the capitals) and Geofabrik's extract index (the
downloads), picks the deepest Geofabrik region that contains each capital, and writes the
REGIONS dict build_packs.py builds from. Edge cases live in packaging/region_overrides.py.

  python -I -B packaging/generate_region_specs.py            # regenerate packaging/region_specs.py
  python -I -B packaging/generate_region_specs.py --check    # also HEAD-check every extract URL

Inputs are cached under derived/packs/region-inputs/ (git-ignored) and fetched on first run:
  ne_populated_places.geojson   Natural Earth, from the nvkelso/natural-earth-vector mirror
  geofabrik-index.json          https://download.geofabrik.de/index-v1.json
"""
import argparse
import importlib.util
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
INPUTS = PROJECT / 'derived' / 'packs' / 'region-inputs'
OUT = PROJECT / 'packaging' / 'region_specs.py'
OVERRIDES_PATH = PROJECT / 'packaging' / 'region_overrides.py'

NE_URL = 'https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_populated_places.geojson'
GEOFABRIK_URL = 'https://download.geofabrik.de/index-v1.json'
RADIUS = 0.3
AGENT = 'lastbook-region-specs/1.0'


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fetch(url, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    print(f'downloading {url}', flush=True)
    req = urllib.request.Request(url, headers={'User-Agent': AGENT})
    with urllib.request.urlopen(req, timeout=120) as r, open(path, 'wb') as f:
        f.write(r.read())


def rings(feature):
    g = feature.get('geometry')
    if not g:
        return []

    def ring(cs):
        return [(x, y) for x, y in cs]

    if g['type'] == 'Polygon':
        return [ring(g['coordinates'][0])]
    if g['type'] == 'MultiPolygon':
        return [ring(p[0]) for p in g['coordinates']]
    return []


def in_ring(x, y, r):
    inside = False
    j = len(r) - 1
    for i in range(len(r)):
        xi, yi = r[i]
        xj, yj = r[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def depth(fid, by_id):
    d = 0
    seen = set()
    parent = by_id[fid]['properties'].get('parent')
    while parent in by_id and parent not in seen:
        seen.add(parent)
        d += 1
        parent = by_id[parent]['properties'].get('parent')
    return d


def area(rings_):
    a = 0.0
    for r in rings_:
        n = len(r)
        j = n - 1
        for i in range(n):
            a += r[j][0] * r[i][1] - r[i][0] * r[j][1]
            j = i
    return abs(a) / 2.0


def gpkg_url(pbf):
    return pbf.replace('-latest.osm.pbf', '-latest-free.gpkg.zip')


def slug(name):
    return re.sub(r'[^a-z0-9]', '', name.lower())[:3]


def sovereign_capitals(ne):
    out = []
    for f in ne['features']:
        p = f['properties']
        if p.get('ADM0CAP') == 1 and p.get('ADM0_A3') == p.get('SOV_A3') and p.get('ADM0_A3'):
            out.append(p)
    return out


def build(ne, index, overrides):
    by_id = {f['properties']['id']: f for f in index['features']}
    polys = {fid: rings(f) for fid, f in by_id.items()}
    rows, warned, seen = [], [], set()
    for p in sorted(sovereign_capitals(ne), key=lambda p: p.get('ADM0_A3') or ''):
        key = p['ADM0_A3']
        ov = overrides.get(key, {})
        if ov.get('exclude'):
            continue
        x, y = p.get('LONGITUDE'), p.get('LATITUDE')
        if x is None or y is None:
            warned.append(f'{key}: no coordinates')
            continue
        code = ov.get('code')
        if code is None:
            iso = (p.get('ISO_A2') or '').lower()
            if not re.fullmatch(r'[a-z]{2}', iso):
                warned.append(f"{key} ({p.get('NAME')}): no ISO 3166-1 alpha-2 code and no override")
                continue
            code = f"{iso}-{slug(p.get('NAMEASCII') or p.get('NAME') or '')}"
        containing = [fid for fid in polys if any(in_ring(x, y, r) for r in polys[fid])]
        if not containing:
            warned.append(f"{key} ({p.get('NAME')}): no Geofabrik region contains it")
            continue
        deepest = max(containing, key=lambda fid: (depth(fid, by_id), -area(polys[fid])))
        pbf = by_id[deepest]['properties']['urls'].get('pbf')
        if not pbf:
            warned.append(f'{key}: {deepest} has no pbf URL')
            continue
        extract = ov.get('extract') or gpkg_url(pbf)
        title = ' '.join(str(ov.get('title') or p.get('NAME') or '').split())
        country = ov.get('country') or p.get('ADM0NAME')
        radius = ov.get('radius', RADIUS)
        bbox = ov.get('bbox') or [x - radius, y - radius, x + radius, y + radius]
        if code in seen:
            i = 2
            while f'{code}{i}' in seen:
                i += 1
            warned.append(f'{key}: code {code} already used; renaming to {code}{i}')
            code = f'{code}{i}'
        seen.add(code)
        rows.append({
            'code': code,
            'country': country,
            'title': title,
            'bbox': bbox,
            'extract': extract,
            'source': f'OpenStreetMap contributors, via Geofabrik {extract.rstrip("/").split("/")[-1]} (ODbL 1.0)',
        })
    rows.sort(key=lambda r: r['code'])
    return rows, warned


def write_specs(rows):
    lines = [
        '"""The non-US region maps Lastbook can build: one entry per sovereign-state capital, keyed by its map id.',
        '',
        'Generated by packaging/generate_region_specs.py - do not edit by hand. Fix an edge case in',
        'packaging/region_overrides.py and regenerate. Each entry is built from a Geofabrik OpenStreetMap',
        'GeoPackage clipped to a box around the capital (docs/MAPS.md, "Region maps").',
        '"""',
        '',
        'REGIONS = {',
    ]
    for r in rows:
        lines.append(f"    '{r['code']}': {{")
        lines.append(f"        'country': {json.dumps(r['country'], ensure_ascii=False)},")
        lines.append(f"        'title': {json.dumps(r['title'], ensure_ascii=False)},")
        lines.append(f"        'bbox': [{', '.join(f'{v:.2f}' for v in r['bbox'])}],")
        lines.append(f"        'extract': {json.dumps(r['extract'])},")
        lines.append(f"        'source': {json.dumps(r['source'], ensure_ascii=False)},")
        lines.append('    },')
    lines += ['}', '']
    OUT.write_text('\n'.join(lines), encoding='utf-8')


def head_ok(url):
    for attempt in range(2):
        req = urllib.request.Request(url, method='HEAD', headers={'User-Agent': AGENT})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status == 200
        except urllib.error.HTTPError as e:
            if e.code != 405:
                return False
        except OSError:
            continue
    # A host that refuses HEAD: a byte-range GET answers the same question.
    req = urllib.request.Request(url, headers={'User-Agent': AGENT, 'Range': 'bytes=0-0'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status in (200, 206)
    except (OSError, urllib.error.HTTPError):
        return False


def check(rows):
    urls = sorted({r['extract'] for r in rows})
    bad = []
    for i, url in enumerate(urls, 1):
        ok = head_ok(url)
        print(f'{i}/{len(urls)} {"200" if ok else "FAIL"} {url}', flush=True)
        if not ok:
            bad.append(url)
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ne', help='Natural Earth populated-places GeoJSON')
    ap.add_argument('--geofabrik', help='Geofabrik index-v1.json')
    ap.add_argument('--check', action='store_true', help='HEAD-check every extract URL after writing')
    args = ap.parse_args()

    ne_path = Path(args.ne) if args.ne else INPUTS / 'ne_populated_places.geojson'
    gf_path = Path(args.geofabrik) if args.geofabrik else INPUTS / 'geofabrik-index.json'
    if not ne_path.exists():
        fetch(NE_URL, ne_path)
    if not gf_path.exists():
        fetch(GEOFABRIK_URL, gf_path)

    ne = json.loads(ne_path.read_text(encoding='utf-8'))
    index = json.loads(gf_path.read_text(encoding='utf-8'))
    overrides = load_module('region_overrides', OVERRIDES_PATH).OVERRIDES
    rows, warned = build(ne, index, overrides)
    for w in warned:
        print(f'warn: {w}', flush=True)
    write_specs(rows)
    print(f'wrote {len(rows)} regions to {OUT.relative_to(PROJECT)}', flush=True)
    if args.check:
        bad = check(rows)
        if bad:
            print(f'{len(bad)} extract URLs failed the HEAD check', flush=True)
            return 1
        print(f'all {len({r["extract"] for r in rows})} distinct extract URLs answered 200', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
