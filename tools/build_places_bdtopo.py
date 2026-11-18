"""Builds derived/geo/places.sqlite (the offline place finder) for a French region from the IGN BD TOPO, in the schema
tools/build_places.py writes for the US: place(id, name, kind, detail, lat, lon, rank, source) and place_fts.

  python3 tools/build_places_bdtopo.py --out derived/geo/places.sqlite --departments 14,50,61 \
      BDTOPO_D014_folder BDTOPO_D050_folder BDTOPO_D061_folder

Source: IGN BD TOPO v3.5 "tous thèmes" GeoPackage per department (Licence Ouverte 2.0, Lambert-93), only read.
Populations are the INSEE figures the BD TOPO carries in `commune.population` (date in `date_du_recensement`).

What goes in, and its rank (lower comes first, as in build_places.py where OpenStreetMap places are 1, ZIP codes and
counties 2, GNIS towns 3 and points 4). The US file has no population; here the rank of a commune follows it:
  department                                   kind 'department'                    rank 1
  commune of 10,000 inhabitants or more        kind 'city' (50,000+) or 'town'      rank 1
  commune of 1,000 to 9,999                    kind 'town' (2,000+) or 'village'    rank 2
  commune under 1,000                          kind 'village'                       rank 3
  delegated or associated commune              kind 'delegated commune' / 'associated commune'   rank 3
  river with a name (cours_d_eau importance 1-4)  kind 'river'                      rank 3
  centre of a commune named differently        kind 'commune centre'                rank 3 (Cherbourg in Cherbourg-en-Cotentin)
  named hamlet, quarter, château, mill...      kind 'hamlet', 'neighbourhood', ...  rank 4 (zone_d_habitation)
  other named stream                           kind 'stream'                        rank 5
  named unpopulated place, wood, named site    kind 'locality', 'wood', 'site'...   rank 5
  postcode (--postcodes)                       kind 'postcode'                      rank 2
The population and the postcode go in `detail` (the table has no population column), e.g.
"Calvados · 109,400 inhabitants (INSEE) · postcode 14000". A commune is placed on its chef-lieu (the inhabited area
the BD TOPO links to it); the chef-lieu itself is then not listed a second time under the same name.
The BD TOPO gives one postcode per commune, and the parent's for a delegated commune. With --postcodes, every postcode
of an address index (tools/build_addresses_ban.py) becomes a place of its own, set at the middle of its addresses and
naming the communes it serves, the way a US ZIP code is a place.
A department file reaches into its neighbours: communes are kept by `code_insee_du_departement`, delegated communes
by the first digits of their INSEE code, everything else when its point lies inside --departments.
"""
import argparse, os, sqlite3, sys, time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_water import inside_point  # noqa: E402
from gpkg_reader import (LINESTRING, POLYGON, DepartmentFilter, bdtopo_package, geometry, geometry_column,  # noqa: E402
                         open_gpkg, ring_area)
from lambert93 import to_lonlat  # noqa: E402

SOURCE = 'IGN BD TOPO'
DEPT_NAME = {'14': 'Calvados', '50': 'Manche', '61': 'Orne'}
HABITATION_KIND = {'Lieu-dit habité': 'hamlet', 'Quartier': 'neighbourhood', 'Château': 'château', 'Moulin': 'mill',
                   'Grange': 'farm building', 'Ruines': 'ruins', 'Habitat temporaire': 'temporary settlement'}
UNINHABITED_KIND = {'Lieu-dit non habité': 'locality', 'Bois': 'wood', 'Arbre': 'notable tree', 'Pare-feu': 'firebreak'}
SITE_KIND = {'Administratif ou militaire': 'public or military site', 'Culture et loisirs': 'culture or leisure site',
             'Gestion des eaux': 'water works', 'Industriel et commercial': 'business or industrial site',
             'Religieux': 'religious site', 'Santé': 'health site', 'Science et enseignement': 'school or research site',
             'Sport': 'sports ground'}


def fmt(n):
    return f'{n:,}'


def poly_point(blob):
    """(x, y) Lambert-93 point inside the largest polygon of the blob, or None."""
    polys = [p for t, p in geometry(blob) if t == POLYGON]
    if not polys:
        pts = [p for t, p in geometry(blob) if t == 1]
        return (float(pts[0][0, 0]), float(pts[0][0, 1])) if pts else None
    ring = max(polys, key=lambda p: abs(ring_area(p[0])))[0]
    return inside_point([tuple(v) for v in ring[:, :2].tolist()])


def commune_kind(pop):
    if pop is None:
        return 'village', 3
    if pop >= 50000:
        return 'city', 1
    if pop >= 10000:
        return 'town', 1
    if pop >= 2000:
        return 'town', 2
    if pop >= 1000:
        return 'village', 2
    return 'village', 3


def postcodes(index):
    """(postcode, 'Tourlaville, Digosville, Bretteville · Manche', lat, lon) for each postcode of an address index."""
    db = sqlite3.connect(Path(index).resolve().as_uri() + '?mode=ro', uri=True)
    found = {}
    for code, city, count, lat, lon in db.execute(
            "SELECT zip, city, count(*), sum(lat), sum(lon) FROM addr WHERE zip != '' GROUP BY zip, city"):
        entry = found.setdefault(code, {'count': 0, 'lat': 0.0, 'lon': 0.0, 'communes': {}})
        entry['count'] += count
        entry['lat'] += lat
        entry['lon'] += lon
        # 'Cherbourg-en-Cotentin (Tourlaville)': the delegated commune is the name a person knows the postcode by
        commune = city[city.index('(') + 1:-1] if city.endswith(')') and '(' in city else city
        entry['communes'][commune] = entry['communes'].get(commune, 0) + count
    db.close()
    for code, entry in sorted(found.items()):
        communes = sorted(entry['communes'], key=lambda c: -entry['communes'][c])
        names = ', '.join(communes[:4]) + (f' and {len(communes) - 4} more' if len(communes) > 4 else '')
        yield (code, f'{names} · {DEPT_NAME.get(code[:2], code[:2])}', round(entry['lat'] / entry['count'], 6),
               round(entry['lon'] / entry['count'], 6))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('packages', nargs='+', help='extracted BD TOPO folders (or .gpkg files)')
    ap.add_argument('--out', required=True)
    ap.add_argument('--departments', default='14,50,61')
    ap.add_argument('--postcodes', help='address index (addresses/XX.sqlite) whose postcodes become places')
    a = ap.parse_args()
    t0 = time.time()
    pkgs = [bdtopo_package(p) for p in a.packages]
    codes = a.departments.split(',')
    depts = DepartmentFilter(pkgs, codes)
    dbs = [open_gpkg(p) for p in pkgs]
    rows = []  # (name, kind, detail, x, y, rank, source, dept or '' to test)
    stats = {}

    def add(name, kind, detail, x, y, rank, dept=''):
        rows.append((name, kind, detail, x, y, rank, dept))

    # communes, and the inhabited areas they point to as chef-lieu
    commune_name, chef, seen = {}, {}, set()
    for g in dbs:
        for code, name, chl in g.execute('SELECT code_insee, nom_officiel, lien_vers_chef_lieu FROM commune'):
            commune_name[code] = name
            if chl:
                chef.setdefault(chl, []).insert(0, name)
        for code, name, chl in g.execute('SELECT code_insee, nom_officiel, lien_vers_chef_lieu FROM commune_associee_ou_deleguee'):
            commune_name.setdefault(code, name)
    for g in dbs:  # a delegated commune often shares its chef-lieu with the new commune (Vire in Vire Normandie)
        for code, name, chl in g.execute('SELECT code_insee, nom_officiel, lien_vers_chef_lieu FROM commune_associee_ou_deleguee'):
            if chl:
                chef.setdefault(chl, []).append(name)
    habitat = {}
    for g in dbs:
        gc = geometry_column(g, 'zone_d_habitation')
        for cleabs, blob in g.execute(f'SELECT cleabs, {gc} FROM zone_d_habitation WHERE cleabs IN (%s)' % ','.join('?' * len(chef)), list(chef)):
            habitat[cleabs] = poly_point(blob)
    for g in dbs:
        gc = geometry_column(g, 'departement')
        for code, name, blob in g.execute(f'SELECT code_insee, nom_officiel, {gc} FROM departement'):
            if code in codes and ('dep', code) not in seen:
                seen.add(('dep', code))
                x, y = poly_point(blob)
                add(name, 'department', f'Département {code}, Normandy, France', x, y, 1, code)
        gc = geometry_column(g, 'commune')
        for code, name, dep, pop, year, cp, chl, blob in g.execute(
                f'SELECT code_insee, nom_officiel, code_insee_du_departement, population, date_du_recensement, code_postal, lien_vers_chef_lieu, {gc} FROM commune'):
            if dep not in codes or ('com', code) in seen:
                continue
            seen.add(('com', code))
            x, y = habitat.get(chl) or poly_point(blob)
            kind, rank = commune_kind(pop)
            bits = [DEPT_NAME.get(dep, dep)]
            if pop is not None:
                bits.append(f'{fmt(pop)} inhabitants (INSEE{", " + str(year)[:4] if year else ""})')
            if cp:
                bits.append(f'postcode {cp}')
            bits.append(f'INSEE {code}')
            add(name, kind, ' · '.join(bits), x, y, rank, dep)
        gc = geometry_column(g, 'commune_associee_ou_deleguee')
        for code, name, parent, nature, pop, cp, chl, blob in g.execute(
                f'SELECT code_insee, nom_officiel, code_insee_de_la_commune_de_rattach, nature, population, code_postal, lien_vers_chef_lieu, {gc} FROM commune_associee_ou_deleguee'):
            if code[:2] not in codes or ('del', code) in seen:
                continue
            seen.add(('del', code))
            x, y = habitat.get(chl) or poly_point(blob)
            kind = 'associated commune' if 'associée' in (nature or '') else 'delegated commune'
            bits = [f'{"Associated" if kind.startswith("associated") else "Delegated"} commune of {commune_name.get(parent, parent)}, {DEPT_NAME.get(code[:2], code[:2])}']
            if pop is not None:
                bits.append(f'{fmt(pop)} inhabitants')
            if cp:
                bits.append(f'postcode {cp}')
            add(name, kind, ' · '.join(bits), x, y, 3, code[:2])
    # hamlets, quarters and other named inhabited places (not the chef-lieu already listed under its commune's name)
    for g in dbs:
        gc = geometry_column(g, 'zone_d_habitation')
        for cleabs, nature, name, insee, blob in g.execute(
                f'SELECT cleabs, nature, toponyme, insee_commune, {gc} FROM zone_d_habitation WHERE toponyme IS NOT NULL'):
            if ('hab', cleabs) in seen:
                continue
            seen.add(('hab', cleabs))
            if cleabs in chef and name.lower() in {c.lower() for c in chef[cleabs]}:
                stats['chef-lieu skipped'] = stats.get('chef-lieu skipped', 0) + 1
                continue
            p = poly_point(blob)
            if p is None:
                continue
            where = commune_name.get((insee or '')[:5], '')
            if cleabs in chef:  # the centre of a commune whose official name differs (Cherbourg in Cherbourg-en-Cotentin)
                add(name, 'commune centre', f'Chef-lieu of {chef[cleabs][0]}', p[0], p[1], 3)
                continue
            kind = HABITATION_KIND.get(nature, 'locality')
            add(name, kind, f'{kind.capitalize()} in {where}' if where else kind.capitalize(), p[0], p[1], 4)
        gc = geometry_column(g, 'lieu_dit_non_habite')
        for cleabs, nature, name, insee, blob in g.execute(
                f'SELECT cleabs, nature, toponyme, insee_commune, {gc} FROM lieu_dit_non_habite WHERE toponyme IS NOT NULL'):
            if ('ldn', cleabs) in seen:
                continue
            seen.add(('ldn', cleabs))
            p = poly_point(blob)
            if p is None:
                continue
            where = commune_name.get((insee or '')[:5], '')
            kind = UNINHABITED_KIND.get(nature, 'locality')
            add(name, kind, f'{kind.capitalize()} in {where}' if where else kind.capitalize(), p[0], p[1], 5)
        gc = geometry_column(g, 'zone_d_activite_ou_d_interet')
        for cleabs, cat, nature, name, insee, blob in g.execute(
                f'SELECT cleabs, categorie, nature, toponyme, insee_commune, {gc} FROM zone_d_activite_ou_d_interet WHERE toponyme IS NOT NULL'):
            if ('zai', cleabs) in seen:
                continue
            seen.add(('zai', cleabs))
            p = poly_point(blob)
            if p is None:
                continue
            where = commune_name.get((insee or '')[:5], '')
            add(name, SITE_KIND.get(cat, 'site'), f'{nature} · {where}' if where else nature, p[0], p[1], 5)
        # rivers: a point on the river inside the region (the middle of its vertices there)
        gc = geometry_column(g, 'cours_d_eau')
        for cleabs, name, imp, blob in g.execute(f'SELECT cleabs, toponyme, importance, {gc} FROM cours_d_eau WHERE toponyme IS NOT NULL'):
            if ('ce', cleabs) in seen:
                continue
            seen.add(('ce', cleabs))
            ls = [p for t, p in geometry(blob) if t == LINESTRING]
            if not ls:
                continue
            pts = np.vstack(ls)
            if len(pts) > 400:
                pts = pts[np.linspace(0, len(pts) - 1, 400).astype(int)]
            d = depts.which(pts[:, 0], pts[:, 1])
            inside = pts[d != '']
            if not len(inside):
                continue
            mid = inside[len(inside) // 2]
            ds = sorted({x for x in d if x})
            big = str(imp) in ('1', '2', '3', '4')
            kind = 'river' if big else 'stream'
            add(name, kind, f'{kind.capitalize()} in ' + ', '.join(DEPT_NAME.get(x, x) for x in ds), float(mid[0]), float(mid[1]),
                3 if big else 5, ds[0])
    for g in dbs:
        g.close()
    # keep only what lies in the region, then convert to longitude/latitude
    xs = np.array([r[3] for r in rows]); ys = np.array([r[4] for r in rows])
    test = np.array([not r[6] for r in rows])
    dep = np.array([r[6] for r in rows], dtype=object)
    if test.any():
        dep[test] = depts.which(xs[test], ys[test])
    lon, lat = to_lonlat(xs, ys)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix('.tmp')
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.executescript('''CREATE TABLE place(id INTEGER PRIMARY KEY, name TEXT, kind TEXT, detail TEXT, lat REAL, lon REAL, rank INTEGER, source TEXT);
      CREATE VIRTUAL TABLE place_fts USING fts5(name, detail, content='place', content_rowid='id', tokenize='unicode61');''')
    ins = 'INSERT INTO place(name,kind,detail,lat,lon,rank,source) VALUES (?,?,?,?,?,?,?)'
    n = 0
    for r, d, lo, la in zip(rows, dep, lon.tolist(), lat.tolist()):
        if not d:
            stats['outside'] = stats.get('outside', 0) + 1
            continue
        src = SOURCE + (' (population INSEE)' if r[1] in ('city', 'town', 'village', 'delegated commune', 'associated commune') and 'inhabitants' in r[2] else '')
        db.execute(ins, (r[0], r[1], r[2], round(la, 6), round(lo, 6), r[5], src))
        stats[r[1]] = stats.get(r[1], 0) + 1
        n += 1
    for name, detail, la, lo in postcodes(a.postcodes) if a.postcodes else ():
        db.execute(ins, (name, 'postcode', detail, la, lo, 2, 'Base Adresse Nationale'))
        stats['postcode'] = stats.get('postcode', 0) + 1
        n += 1
    db.execute("INSERT INTO place_fts(place_fts) VALUES ('rebuild')")
    db.execute('CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT)')   # read for the map's list of sources and its credits
    db.executemany('INSERT INTO meta VALUES (?,?)', {
        'source': 'IGN BD TOPO v3.5, populations from INSEE (Licence Ouverte 2.0)'
                  + ('; postcodes from the Base Adresse Nationale (Licence Ouverte 2.0)' if a.postcodes else ''),
        'attribution': 'IGN BD TOPO' + ('; Base Adresse Nationale' if a.postcodes else ''),
        'built': time.strftime('%Y-%m-%dT%H:%M:%S'), 'departments': a.departments}.items())
    db.commit()
    db.close()
    os.replace(tmp, out)
    print(' '.join(f'{k}={v:,}' for k, v in sorted(stats.items())))
    print(f'places {n:,} in {time.time() - t0:.0f}s')


if __name__ == '__main__':
    main()
