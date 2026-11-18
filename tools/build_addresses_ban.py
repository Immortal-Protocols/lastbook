"""French street addresses for address search: derived/geo/addresses/<REGION>.sqlite, from the Base Adresse Nationale.

  python3 -I tools/build_addresses_ban.py --region FR-BN --departments 14,50,61 \\
      --out derived/geo/addresses/FR-BN.sqlite adresses-14.csv.gz adresses-50.csv.gz adresses-61.csv.gz

Reads the per-department "CSV historique" files of the Base Adresse Nationale (one row per numbered address,
';'-separated, UTF-8, WGS84 lon/lat), published daily at https://adresse.data.gouv.fr/data/ban/adresses/latest/csv/
under the Licence Ouverte 2.0 (Etalab). This tool does not download them: pass the saved files.

It writes the same table, columns and indexes as a US state index (tools/build_addresses.py, then
packaging/address_indexes.py), so engine/address_search.py opens it like any other, and names its rule in its meta
table (norm = fr-1, with region = the file name) so the engine reads it with French rules. What goes in each column:

  num     numero and rep (the repetition index) joined in lower case: '3', '14bis', '12b' (the BAN geocoder's form)
  street  nom_voie as published, accents and case kept: 'Rue de l'Église'
  norm    engine.address_search.normalize_fr(street): accents folded, French street words, no articles
  city    nom_commune; for an address in a delegated or associated commune (nom_ancienne_commune, when it differs):
          'Cherbourg-en-Cotentin (Tourlaville)'. No French commune name holds a parenthesis; the tool checks it
  state   the region code (--region), the file name, as in a US index; the department is in zip
  zip     code_postal, five digits
  lat/lon WGS84, rounded to 6 decimals

A numbered address that also names a lieu-dit (nom_ld, e.g. '5 Route des Près des Disons', lieu-dit 'Le Moncel') gets
a second row with the same street and position and norm = normalize_fr(lieu-dit), so '5 Le Moncel Tourouvre' finds it.
The engine ranks such rows after rows found by their street. Places with no number (toponyms) are not in this file
format and are not addresses here.

The files are treated as untrusted input: every field is checked (number, postcode, department, coordinates inside
the region's box, length) and a row that fails is counted and skipped, never repaired.
"""
import argparse, csv, gzip, hashlib, re, sqlite3, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
from engine.address_search import fold, normalize_fr  # noqa: E402  the engine must read what this writes

COLUMNS = ('numero', 'rep', 'nom_voie', 'code_postal', 'code_insee', 'nom_commune', 'nom_ancienne_commune',
           'lon', 'lat', 'nom_ld')
BOX = (-2.2, 48.1, 1.1, 49.8)   # W, S, E, N around Calvados, Manche and Orne, with margin
MAX_TEXT = 200


def clean(text):
    """One line of printable text, or '' if the field is too long to be a name."""
    text = ' '.join(''.join(char if char.isprintable() else ' ' for char in text).split())
    return text if len(text) <= MAX_TEXT else ''


def rows_of(path, departments, counts, rejected):
    with gzip.open(path, 'rt', encoding='utf-8', newline='') as file:
        reader = csv.reader(file, delimiter=';')
        header = next(reader)
        missing = [name for name in COLUMNS if name not in header]
        if missing:
            raise SystemExit(f'{path}: not a BAN CSV file, columns missing: {missing}')
        at = {name: header.index(name) for name in COLUMNS}
        for record in reader:
            if len(record) != len(header):
                rejected['malformed row'] += 1
                continue
            field = {name: record[index] for name, index in at.items()}
            numero, rep = field['numero'].strip(), field['rep'].strip().lower()
            street, commune = clean(field['nom_voie']), clean(field['nom_commune'])
            delegated, lieu = clean(field['nom_ancienne_commune']), clean(field['nom_ld'])
            postcode, insee = field['code_postal'].strip(), field['code_insee'].strip()
            if not re.fullmatch(r'\d{1,5}', numero):
                rejected['number'] += 1
                continue
            if not re.fullmatch(r'[a-z]{0,9}', rep):
                # A flat or door ('appt 1', 'a1', '2'), not a repetition index: '12' + '1' would read as 121.
                rejected['unit in the repetition index'] += 1
                continue
            if not re.fullmatch(r'\d{5}', postcode) or not re.fullmatch(r'\d[\dAB]\d{3}', insee):
                rejected['postcode or INSEE code'] += 1
                continue
            department = insee[:2]
            if department not in departments or not postcode.startswith(department):
                rejected['outside the region'] += 1
                continue
            if not street or not commune or '(' in commune or '(' in delegated:
                rejected['name'] += 1
                continue
            try:
                lat, lon = round(float(field['lat']), 6), round(float(field['lon']), 6)
            except ValueError:
                rejected['position'] += 1
                continue
            if not (BOX[0] <= lon <= BOX[2] and BOX[1] <= lat <= BOX[3]):
                rejected['position'] += 1
                continue
            city = commune
            if delegated and fold(delegated) != fold(commune):
                city = f'{commune} ({delegated})'
            num = str(int(numero)) + rep
            counts[department] += 1
            norm = normalize_fr(street)
            yield num, street, norm, city, postcode, lat, lon
            alias = normalize_fr(lieu) if lieu else ''
            if alias and alias != norm:
                counts['lieu-dit rows'] += 1
                yield num, street, alias, city, postcode, lat, lon


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as file:
        for chunk in iter(lambda: file.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def build(sources, out, region, departments, title=''):
    """Write the index; return the counts by department, the extra lieu-dit rows and the rejected rows."""
    from collections import Counter
    started = time.monotonic()
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix('.partial')
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.executescript('PRAGMA page_size=8192; PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF; '
                     'CREATE TABLE addr(num TEXT, street TEXT, norm TEXT, city TEXT, state TEXT, zip TEXT, lat REAL, lon REAL); '
                     'CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);')
    counts, rejected = Counter(), Counter()
    for source in sources:
        rows = rows_of(source, departments, counts, rejected)
        db.executemany('INSERT INTO addr VALUES (?,?,?,?,?,?,?,?)',
                       ((num, street, norm, city, region, postcode, lat, lon)
                        for num, street, norm, city, postcode, lat, lon in rows))
        db.commit()
    addresses = sum(counts[department] for department in departments)
    if not addresses:
        db.close()
        tmp.unlink()
        raise SystemExit('no address read: nothing written')
    db.executescript('CREATE INDEX addr_norm ON addr(norm,num); CREATE INDEX addr_num_norm ON addr(num,norm);')
    meta = [('region', region), ('norm', 'fr-1'), ('title', title), ('count', str(addresses)),
            ('rows', str(addresses + counts['lieu-dit rows'])), ('departments', ','.join(departments)),
            ('built', time.strftime('%Y-%m-%dT%H:%M:%S')),
            ('source', 'Base Adresse Nationale (adresse.data.gouv.fr), Licence Ouverte 2.0'),
            ('licence', 'Licence Ouverte / Open Licence 2.0 (Etalab), https://www.etalab.gouv.fr/licence-ouverte-open-licence/'),
            ('source_files', ' '.join(f'{Path(source).name}:{sha256(source)}' for source in sources))]
    db.executemany('INSERT INTO meta VALUES (?,?)', meta)
    db.commit()
    check = db.execute('PRAGMA quick_check').fetchone()[0]
    db.close()
    if check != 'ok':
        raise SystemExit(f'SQLite check failed: {check}')
    tmp.replace(out)
    return counts, rejected, time.monotonic() - started


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('sources', nargs='+', type=Path, help='BAN adresses-XX.csv.gz files')
    ap.add_argument('--region', required=True,
                    help='the region id and index file name: two capital letters, optionally a dash and a code (FR-BN)')
    ap.add_argument('--departments', required=True, help='comma-separated department codes kept (14,50,61)')
    ap.add_argument('--title', default='', help='region name stored in meta')
    ap.add_argument('--out', type=Path, help='default: derived/geo/addresses/<REGION>.sqlite')
    a = ap.parse_args()
    if not re.fullmatch(r'[A-Z]{2}(-[A-Za-z0-9_]{1,48})?', a.region):
        raise SystemExit('--region must be two capital letters, optionally followed by a dash and a code (FR-BN)')
    from engine.address_search import STATE_CODES
    if a.region in STATE_CODES:
        raise SystemExit(f'--region {a.region} is a US state code: the engine would read the index the US way')
    departments = [code.strip() for code in a.departments.split(',') if code.strip()]
    out = a.out or HERE / 'derived/geo/addresses' / f'{a.region}.sqlite'
    counts, rejected, seconds = build(a.sources, out, a.region, departments, a.title)
    for department in departments:
        print(f'{department}: {counts[department]:,} addresses')
    print(f'lieu-dit rows: {counts["lieu-dit rows"]:,}; rejected: {dict(rejected) or 0}')
    print(f'done: {sum(counts[d] for d in departments):,} addresses, {out.stat().st_size:,} bytes, {seconds:.1f}s -> {out}')


if __name__ == '__main__':
    main()
