"""Builds derived/geo/water.sqlite for a French region: dams from the ROE and lakes, ponds, reservoirs, springs, water
outlines and streams from the IGN BD TOPO, in the schema tools/build_water.py writes for the US (resource + spatial,
feat + feat_idx, meta, nhd_seen, water_fts), so server.py reads it unchanged.

  python3 tools/build_water_bdtopo.py --out derived/geo/water.sqlite --departments 14,50,61 \
      --roe roe-14.json --roe roe-50.json --roe roe-61.json  BDTOPO_D014_folder BDTOPO_D050_folder BDTOPO_D061_folder

Sources, both Licence Ouverte 2.0 and only read:
- IGN BD TOPO v3.5 "tous thèmes" GeoPackage per department (Lambert-93), hydrography theme: `surface_hydrographique`
  (drawn outlines and unnamed ponds), `plan_d_eau` (named lakes and reservoirs; one made of salt-water outlines,
  such as a coastal havre, is written as kind 'estuary', which the map does not show, as NHD estuaries in the US), `troncon_hydrographique` (streams,
  drawn as `waterway` lines), `detail_hydrographique` (springs). A department file reaches into its neighbours: an
  outline or a line is kept when one of its vertices (up to 16 tested) lies in --departments, a point when it does.
- Sandre / OFB ROE (référentiel des obstacles à l'écoulement), GeoJSON in EPSG:4326 from the WFS
  https://services.sandre.eaufrance.fr/geo/obs (typename ObstEcoul_FXX, filtered on CdDepartement). Only dams
  (CdTypeOuvrage 1.1*) still standing are kept: weirs, bridge sills, dikes and fish grids are other ROE types, and a
  dam recorded "Détruit entièrement" (e.g. Vezins, removed in 2019-2020) is no longer there.

Units: the schema names US units, so values are converted and the key says the truth: `height_ft` is the ROE
`HautMaxTer` (height above natural ground, metres) x 3.28084; `area_acres` is the BD TOPO outline area in m² /
4046.8564224. Metric values are kept beside them (`height_m`, `drop_height_m`, `area_ha`). The ROE gives no storage
or reservoir surface, so `normal_storage_af`, `max_storage_af` and `surface_acres` are never written.
"""
import argparse, json, math, os, re, sqlite3, sys, time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_water import inside_point, pack, simplify  # noqa: E402
from gpkg_reader import (LINESTRING, POLYGON, DepartmentFilter, bdtopo_package, geometry, geometry_column,  # noqa: E402
                         open_gpkg, ring_area)
from lambert93 import to_lonlat  # noqa: E402

M2_PER_ACRE = 4046.8564224
FT_PER_M = 1 / 0.3048
BDTOPO_URL = 'https://geoservices.ign.fr/bdtopo'
ROE_URL = 'https://www.data.gouv.fr/datasets/597b4533c751df06dd254d52/'
DEPT_NAME = {'14': 'Calvados', '50': 'Manche', '61': 'Orne'}

# surface_hydrographique nature -> (layer, cls) for drawing, as tools/build_water.py LAYER / AREA_LAYER
SURFACE_LAYER = {'Ecoulement naturel': ('water', 'river'), 'Ecoulement canalisé': ('water', 'river'), 'Canal': ('water', 'river'),
                 'Estuaire': ('water', 'water'), 'Marais': ('wet', 'wet'), 'Mare': ('water', 'water'), 'Retenue': ('water', 'water'),
                 "Plan d'eau de gravière": ('water', 'water'), "Plan d'eau de mine": ('water', 'water'),
                 'Retenue-barrage': ('water', 'reservoir'), 'Retenue-bassin portuaire': ('water', 'water'),
                 'Réservoir-bassin': ('water', 'reservoir'), "Réservoir-bassin d'orage": ('water', 'reservoir'),
                 'Réservoir-bassin piscicole': ('water', 'reservoir')}
STILL = {'Mare', 'Retenue', "Plan d'eau de gravière", "Plan d'eau de mine", 'Retenue-barrage', 'Réservoir-bassin',
         "Réservoir-bassin d'orage", 'Réservoir-bassin piscicole'}
# reservoir_type shown on the card (English, like NHD's), and basins that are not a water source
RESERVOIR_TYPE = {'Retenue-barrage': 'Dam reservoir', 'Réservoir-bassin': 'Basin', "Réservoir-bassin d'orage": 'Storm-water basin',
                  'Réservoir-bassin piscicole': 'Fish-farm basin', "Plan d'eau de gravière": 'Gravel pit',
                  "Plan d'eau de mine": 'Flooded mine'}
NOT_DRINKING = {"Réservoir-bassin d'orage"}
# stream lines: natures that are a flowing channel (the others are axes drawn through lakes, marshes and estuaries)
FLOW = {'Ecoulement naturel', 'Ecoulement canalisé', 'Canal', 'Inconnue', 'Ecoulement endoréique', 'Aqueduc'}
WIDE = {'Entre 15 et 50 m': 9, 'Plus de 50 m': 9, 'Entre 5 et 15 m': 10}
WATER_TYPE = {'Permanent': 'Year-round', 'Intermittent': 'Seasonal (may be dry)', 'Sec': 'Seasonal (may be dry)', '1': 'Year-round', '0': 'Seasonal (may be dry)'}


def open_db(path):
    db = sqlite3.connect(path)
    db.executescript('''PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;
      CREATE TABLE IF NOT EXISTS resource(id INTEGER PRIMARY KEY, source_id TEXT, kind TEXT, name TEXT, lat REAL, lon REAL, detail TEXT, source TEXT, origin TEXT);
      CREATE INDEX IF NOT EXISTS resource_kind ON resource(kind);
      CREATE INDEX IF NOT EXISTS resource_origin ON resource(origin);
      CREATE VIRTUAL TABLE IF NOT EXISTS spatial USING rtree(id, minx, maxx, miny, maxy);
      CREATE TABLE IF NOT EXISTS feat(id INTEGER PRIMARY KEY, layer TEXT, cls TEXT, name TEXT, minz INTEGER, geom BLOB, origin TEXT);
      CREATE INDEX IF NOT EXISTS feat_origin ON feat(origin);
      CREATE VIRTUAL TABLE IF NOT EXISTS feat_idx USING rtree(id, minx, maxx, miny, maxy, minz, maxz);
      CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
      CREATE TABLE IF NOT EXISTS nhd_seen(pid TEXT PRIMARY KEY, origin TEXT);''')
    return db


def add_point(db, origin, source_id, kind, name, lat, lon, detail, source):
    cur = db.execute('INSERT INTO resource(source_id,kind,name,lat,lon,detail,source,origin) VALUES (?,?,?,?,?,?,?,?)',
                     (source_id, kind, name, lat, lon, json.dumps(detail, separators=(',', ':'), ensure_ascii=False), source, origin))
    db.execute('INSERT INTO spatial VALUES (?,?,?,?,?)', (cur.lastrowid, lon, lon, lat, lat))


def add_feat(db, origin, layer, cls, name, minz, parts):
    """parts: list of [(lon, lat), ...] (rings of one polygon, or one line)."""
    xs = [x for p in parts for x, _ in p]; ys = [y for p in parts for _, y in p]
    cur = db.execute('INSERT INTO feat(layer,cls,name,minz,geom,origin) VALUES (?,?,?,?,?,?)', (layer, cls, name or '', minz, pack(parts), origin))
    db.execute('INSERT INTO feat_idx VALUES (?,?,?,?,?,?,?)', (cur.lastrowid, min(xs), max(xs), min(ys), max(ys), minz, 30))


def lonlat_list(a):
    lo, la = to_lonlat(a[:, 0], a[:, 1])
    return list(zip(np.round(lo, 7).tolist(), np.round(la, 7).tolist()))


def touches(depts, arrays):
    """Department of the first tested vertex inside --departments, or ''."""
    pts = np.vstack(arrays)
    if len(pts) > 16:
        pts = pts[np.linspace(0, len(pts) - 1, 16).astype(int)]
    d = depts.which(pts[:, 0], pts[:, 1])
    hit = [x for x in d if x]
    return hit[0] if hit else ''


def tol_for(minz):
    return 0.00002 if minz >= 12 else 0.00006 if minz >= 9 else 0.0002


def build_bdtopo(db, pkgs, depts, stats):
    seen = set()
    for pkg in pkgs:
        g = open_gpkg(pkg)
        t0 = time.time()
        # lakes the BD TOPO marks as salt water (through the outlines that make them up), such as the coastal havres
        salt = {m for (links,) in g.execute('SELECT liens_vers_plan_d_eau FROM surface_hydrographique WHERE salinite=1 AND liens_vers_plan_d_eau IS NOT NULL')
                for m in re.findall(r'PLANDEAU\w+', links)}
        # named lakes and reservoirs: one point each, in the middle of the largest piece
        gc = geometry_column(g, 'plan_d_eau')
        for cleabs, nature, name, perm, depth, alt, blob in g.execute(
                f'SELECT cleabs, nature, toponyme, caractere_permanent, hauteur_d_eau_maximale, altitude_moyenne, {gc} FROM plan_d_eau'):
            if cleabs in seen or nature in ('Marais', 'Retenue-bassin portuaire'):
                continue
            seen.add(cleabs)
            polys = [p for t, p in geometry(blob) if t == POLYGON]
            if not polys:
                continue
            area = sum(abs(ring_area(p[0])) - sum(abs(ring_area(h)) for h in p[1:]) for p in polys)
            big = max(polys, key=lambda p: abs(ring_area(p[0])))
            lon, lat = inside_point(lonlat_list(big[0]))
            cx, cy = _l93_of(big[0])
            d = depts.which(np.array([cx]), np.array([cy]))[0]
            if not d:
                continue
            kind = 'reservoir' if nature in RESERVOIR_TYPE else 'pond' if (nature == 'Mare' or (not name and area < 40000)) else 'lake'
            if cleabs in salt:  # like NHD estuaries: kept in the file, but not a kind the map shows as fresh water
                kind = 'estuary'
            detail = {'area_acres': round(area / M2_PER_ACRE, 1), 'area_ha': round(area / 1e4, 2), 'state': DEPT_NAME.get(d, d),
                      'water_type': WATER_TYPE.get(str(perm), '')}
            if nature in RESERVOIR_TYPE:
                detail['reservoir_type'] = RESERVOIR_TYPE[nature]
            if nature in NOT_DRINKING:
                detail['not_drinking_water'] = True
            if cleabs in salt:
                detail['salt_water'] = True
            if depth:
                detail['max_depth_m'] = depth
            if alt:
                detail['altitude_m'] = alt
            detail['nature'] = nature
            add_point(db, f'bdtopo:{d}', cleabs, kind, name or '', lat, lon, detail, BDTOPO_URL)
            stats[kind] += 1
        # water outlines; unnamed year-round ponds and lakes of an acre or more get a point, as in the US build
        gc = geometry_column(g, 'surface_hydrographique')
        for cleabs, nature, pers, sal, pe, n1, n2, blob in g.execute(
                f'SELECT cleabs, nature, persistance, salinite, liens_vers_plan_d_eau, cpx_toponyme_de_plan_d_eau, cpx_toponyme_de_cours_d_eau, {gc} FROM surface_hydrographique'):
            if cleabs in seen or nature not in SURFACE_LAYER:
                continue
            seen.add(cleabs)
            polys = [p for t, p in geometry(blob) if t == POLYGON]
            if not polys:
                continue
            d = touches(depts, [p[0] for p in polys])
            if not d:
                continue
            area = sum(abs(ring_area(p[0])) - sum(abs(ring_area(h)) for h in p[1:]) for p in polys)
            layer, cls = SURFACE_LAYER[nature]
            name = n1 or n2 or ''
            minz = max(5, min(14, round(14 - math.log2(max(area / 1e6, 1e-5) ** 0.5 / 0.02))))
            for p in polys:
                rings = [r2 for r2 in (simplify(lonlat_list(r), tol_for(minz)) for r in p) if len(r2) >= 4]
                if rings:
                    add_feat(db, f'bdtopo:{d}', layer, cls, name, minz, rings)
                    stats['outlines'] += 1
            if nature in STILL and not pe and pers == 'Permanent' and sal != 1 and area >= 0.004e6 and nature not in NOT_DRINKING:
                big = max(polys, key=lambda p: abs(ring_area(p[0])))
                lon, lat = inside_point(lonlat_list(big[0]))
                kind = 'reservoir' if nature in RESERVOIR_TYPE else 'pond' if area < 0.04e6 else 'lake'
                detail = {'area_acres': round(area / M2_PER_ACRE, 1), 'area_ha': round(area / 1e4, 2), 'state': DEPT_NAME.get(d, d),
                          'water_type': 'Year-round', 'nature': nature}
                if nature in RESERVOIR_TYPE:
                    detail['reservoir_type'] = RESERVOIR_TYPE[nature]
                add_point(db, f'bdtopo:{d}', cleabs, kind, n1 or '', lat, lon, detail, BDTOPO_URL)
                stats[kind] += 1
        # streams and rivers, drawn as waterway lines (the US build leaves them to the base map)
        gc = geometry_column(g, 'troncon_hydrographique')
        for cleabs, nature, fictif, pos, pers, width, name, blob in g.execute(
                f'SELECT cleabs, nature, fictif, position_par_rapport_au_sol, persistance, classe_de_largeur, cpx_toponyme_de_cours_d_eau, {gc} FROM troncon_hydrographique'):
            if cleabs in seen or nature not in FLOW or fictif in (1, '1', 'true') or (pos is not None and str(pos).lstrip('-').isdigit() and int(pos) < 0):
                continue
            seen.add(cleabs)
            ls = [p for t, p in geometry(blob) if t == LINESTRING and len(p) >= 2]
            if not ls:
                continue
            d = touches(depts, ls)
            if not d:
                continue
            cls = 'river' if width in WIDE else 'stream'
            minz = WIDE.get(width) or (12 if name and pers == 'Permanent' else 13)
            for p in ls:
                pts = simplify(lonlat_list(p), tol_for(minz))
                if len(pts) >= 2:
                    add_feat(db, f'bdtopo:{d}', 'waterway', cls, name or '', minz, [pts])
                    stats['lines'] += 1
        # springs
        gc = geometry_column(g, 'detail_hydrographique')
        for cleabs, nature, name, pers, blob in g.execute(
                f"SELECT cleabs, nature, toponyme, persistance, {gc} FROM detail_hydrographique WHERE nature IN ('Source', 'Source captée')"):
            if cleabs in seen:
                continue
            seen.add(cleabs)
            pts = [p for t, p in geometry(blob) if t == 1]
            if not pts:
                continue
            x, y = pts[0][0]
            d = depts.which(np.array([x]), np.array([y]))[0]
            if not d:
                continue
            lo, la = to_lonlat(x, y)
            detail = {'state': DEPT_NAME.get(d, d), 'spring_type': 'Captured spring (public supply)' if nature == 'Source captée' else 'Spring',
                      'water_type': WATER_TYPE.get(pers or '', ''), 'nature': nature}
            add_point(db, f'bdtopo:{d}', cleabs, 'spring', name or '', round(float(la), 7), round(float(lo), 7), detail, BDTOPO_URL)
            stats['spring'] += 1
        g.close()
        db.commit()
        print(f'{pkg.name}: {time.time() - t0:.0f}s, totals so far {dict(stats)}', flush=True)


def _l93_of(ring):
    """Centre of a Lambert-93 ring, for the department test."""
    return float(ring[:, 0].mean()), float(ring[:, 1].mean())


def build_roe(db, files, codes, stats):
    n = 0
    for f in files:
        data = json.loads(Path(f).read_text(encoding='utf-8'))
        for ft in data['features']:
            p = ft['properties']
            typ, state, dep = p.get('CdTypeOuvrage') or '', p.get('LbEtOuvrage') or '', p.get('CdDepartement') or ''
            if dep not in codes:
                stats['roe_other_department'] += 1
                continue
            if not typ.startswith('1.1'):
                stats['roe_not_dam'] += 1
                continue
            if state in ('Détruit entièrement', 'En projet'):
                stats['roe_dam_removed'] += 1
                continue
            try:
                lon, lat = ft['geometry']['coordinates'][:2]
            except (KeyError, TypeError, ValueError):
                continue
            def metres(k):
                try:
                    v = float(str(p.get(k)).replace(',', '.'))
                except ValueError:
                    return None
                return v if v > 0 else None
            h, drop = metres('HautMaxTer'), metres('HautChutEtObstEcoul')
            uses = [p.get(f'LbUsageObstEcoul{i}') for i in range(1, 5) if p.get(f'LbUsageObstEcoul{i}')]
            detail = {'other_names': p.get('NomSecondaireObstEcoul') or '', 'purpose': uses[0] if uses else '',
                      'purposes': ', '.join(uses), 'river': p.get('NomEntiteHydrographique') or '', 'state': DEPT_NAME.get(dep, dep),
                      'city': (p.get('LbCommune') or '').title(), 'dam_type': f'Dam (ROE type {typ})', 'status': state,
                      'roe_id': p.get('CdObstEcoul')}
            if h:
                detail['height_m'] = h
                detail['height_ft'] = round(h * FT_PER_M, 1)
            if drop:
                detail['drop_height_m'] = drop
            detail = {k: v for k, v in detail.items() if v not in ('', None)}
            add_point(db, 'roe', p.get('CdObstEcoul'), 'dam', (p.get('NomPrincipalObstEcoul') or '').strip() or 'Unnamed dam',
                      round(lat, 7), round(lon, 7), detail, ROE_URL)
            n += 1
    stats['dam'] += n


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('packages', nargs='+', help='extracted BD TOPO folders (or .gpkg files)')
    ap.add_argument('--out', required=True)
    ap.add_argument('--departments', default='14,50,61')
    ap.add_argument('--roe', action='append', default=[], help='ROE GeoJSON file (EPSG:4326); repeat for each')
    a = ap.parse_args()
    t0 = time.time()
    pkgs = [bdtopo_package(p) for p in a.packages]
    codes = a.departments.split(',')
    depts = DepartmentFilter(pkgs, codes)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix('.tmp')
    tmp.unlink(missing_ok=True)
    db = open_db(tmp)
    stats = {k: 0 for k in ('dam', 'reservoir', 'lake', 'pond', 'estuary', 'spring', 'outlines', 'lines',
                            'roe_not_dam', 'roe_dam_removed', 'roe_other_department')}
    build_roe(db, a.roe, codes, stats)
    build_bdtopo(db, pkgs, depts, stats)
    db.executescript('DROP TABLE IF EXISTS water_fts; CREATE VIRTUAL TABLE water_fts USING fts5(name, other, tokenize="unicode61");')
    db.execute("INSERT INTO water_fts(rowid,name,other) SELECT id,name,COALESCE(json_extract(detail,'$.other_names'),'') FROM resource "
               "WHERE kind IN ('dam','reservoir','lake') AND name!=''")
    built = time.strftime('%Y-%m-%dT%H:%M:%S')
    db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', ('roe', json.dumps({'records': stats['dam'], 'files': [Path(f).name for f in a.roe], 'built': built})))
    for d in codes:
        pts = db.execute("SELECT count(*) FROM resource WHERE origin=?", (f'bdtopo:{d}',)).fetchone()[0]
        n = db.execute("SELECT count(*) FROM feat WHERE origin=?", (f'bdtopo:{d}',)).fetchone()[0]
        db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', (f'bdtopo:{d}', json.dumps({'outlines_and_lines': n, 'points': pts, 'built': built})))
    db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', ('source', 'IGN BD TOPO v3.5 (' + ', '.join(p.stem for p in pkgs)
                                                            + '); Sandre/OFB ROE; Licence Ouverte 2.0'))
    db.commit()
    print('search index:', db.execute('SELECT count(*) FROM water_fts').fetchone()[0], 'named waters and dams')
    db.close()
    os.replace(tmp, out)
    print(' '.join(f'{k}={v:,}' for k, v in stats.items()))
    print(f'done in {time.time() - t0:.0f}s')


if __name__ == '__main__':
    main()
