"""Read-only address lookup using the state indexes installed with offline maps."""
import math
import re
import sqlite3
from pathlib import Path

from engine import pr_addresses, pr_parcels, pr_rural, pr_rural_model
from engine.paths import ro_uri

# Keep normalization compatible with tools/build_addresses.py.
WORDS = {
    'boulevard': 'blvd', 'avenue': 'ave', 'av': 'ave', 'street': 'st',
    'drive': 'dr', 'road': 'rd', 'place': 'pl', 'court': 'ct', 'lane': 'ln',
    'terrace': 'ter', 'circle': 'cir', 'highway': 'hwy', 'parkway': 'pkwy',
    'square': 'sq', 'north': 'n', 'south': 's', 'east': 'e', 'west': 'w',
    'mount': 'mt', 'saint': 'st',
}
STATE_NAMES = (
    'Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|'
    'District of Columbia|Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|'
    'Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|'
    'Mississippi|Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|'
    'New Mexico|New York|North Carolina|North Dakota|Ohio|Oklahoma|Oregon|'
    'Pennsylvania|Puerto Rico|Rhode Island|South Carolina|South Dakota|'
    'Tennessee|Texas|Utah|Vermont|Virginia|Washington|West Virginia|Wisconsin|Wyoming'
).split('|')
STATE_CODES = 'AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA PR RI SC SD TN TX UT VT VA WA WV WI WY'.split()
STATES = dict(zip((name.lower() for name in STATE_NAMES), STATE_CODES))
ONES = 'zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty'.split()
ORDINALS = 'zeroth first second third fourth fifth sixth seventh eighth ninth tenth eleventh twelfth thirteenth fourteenth fifteenth sixteenth seventeenth eighteenth nineteenth twentieth'.split()
TO_DIGITS = {word: str(number) for number, word in enumerate(ONES)}
for number, word in enumerate(ORDINALS):
    suffix = 'th' if 10 <= number % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(number % 10, 'th')
    TO_DIGITS[word] = f'{number}{suffix}'
TO_WORDS = {value: key for key, value in TO_DIGITS.items()}


def normalize(text):
    return ' '.join(WORDS.get(word, word) for word in re.sub(r'[^a-z0-9 ]+', ' ', text.lower()).split())


def is_address_query(query):
    """A standalone ZIP remains a place query. A number followed by words is an address."""
    return bool(re.match(r'^\s*\d[\w-]*\s+\S', query) or pr_addresses.components(query) or
                pr_parcels.number(query) or pr_rural.looks_rural(query) or pr_rural.parcel_direction(query))


def street_forms(street):
    words = street.split()
    forms = [street, ' '.join(TO_DIGITS.get(word, word) for word in words),
             ' '.join(TO_WORDS.get(word, word) for word in words)]
    forms += [re.sub(r'\b(\d+)(st|nd|rd|th)\b', r'\1', form) for form in forms[:]]
    if words[0] not in ('n', 's', 'e', 'w', 'ne', 'nw', 'se', 'sw'):
        forms += [f'{direction} {form}' for form in forms[:] for direction in ('n', 's', 'e', 'w')]
    return list(dict.fromkeys(forms))


def _parts(query):
    number, remainder = query.strip().split(None, 1)
    number = number.upper()
    remainder = re.sub(r'[^a-z0-9 ]+', ' ', remainder.lower()).split()
    postcode = ''
    if remainder and re.fullmatch(r'\d{5}', remainder[-1]):
        postcode = remainder.pop()
    state = ''
    for count in (3, 2, 1):
        if len(remainder) <= count:
            continue
        name = ' '.join(remainder[-count:])
        code = STATES.get(name) or (name.upper() if count == 1 and name.upper() in STATE_CODES else '')
        if code:
            state = code
            remainder = remainder[:-count]
            break
    return number, normalize(' '.join(remainder)).split(), state, postcode


def find_addresses(query, geo_directory, limit=8, near=None, model=None, parcel_offset=0, parcel_limit=None):
    """Find indexed street addresses or explicitly labeled rural road references."""
    key = pr_parcels.number(query)
    rural = pr_rural.parse(query, parcel=True)
    if limit > 0 and (key or rural or pr_rural.looks_rural(query) or pr_rural.parcel_direction(query)):
        path = Path(geo_directory) / 'addresses' / 'PR.sqlite'
        if path.is_file():
            db = None
            try:
                db = sqlite3.connect(ro_uri(path), uri=True)
                parcels = pr_parcels.installed(db)
                if key:
                    return pr_parcels.by_number(db, key) if parcels and not parcel_offset else []
                roads = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='pr_road'").fetchone()
                if not (parcels or roads):
                    return []

                def lookup(address):
                    if not address:
                        return []
                    rows = pr_parcels.candidates(db, address, max(0, parcel_offset), parcel_limit or limit) if parcels else []
                    if roads and not parcel_offset:
                        rows.extend(pr_rural.lookup(db, address, limit))
                    return rows

                rows = lookup(rural)
                if rows:
                    return rows
                interpreted = pr_rural_model.interpret(model, query, rural)
                rows = lookup(interpreted)
                for row in rows:
                    row['interpreted'] = pr_rural_model.description(interpreted)
                return rows
            except sqlite3.Error:
                pass
            finally:
                if db is not None:
                    db.close()
        return []
    legacy_number = re.match(r'^\s*\d[\w-]*\s+\S', query)
    pr_parts = pr_addresses.components(query)
    if limit <= 0 or not (legacy_number or pr_parts):
        return []
    number, words, state, postcode = _parts(query) if legacy_number else ('', [], '', '')
    geo_directory = Path(geo_directory)
    paths = sorted((geo_directory / 'addresses').glob('*.sqlite'))
    if state:
        paths = [path for path in paths if path.stem.upper() == state]
    legacy = geo_directory / 'addresses.sqlite'
    if not paths and legacy.is_file():
        paths = [legacy]
    connections = []
    pr_results = []
    try:
        for path in paths:
            try:
                db = sqlite3.connect(ro_uri(path), uri=True)
            except sqlite3.Error:
                continue
            try:
                if path.stem.upper() == 'PR' and db.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='meta'").fetchone():
                    profile = db.execute("SELECT value FROM meta WHERE key='search_profile'").fetchone()
                    if profile == (pr_addresses.PROFILE,):
                        if pr_parts:
                            pr_results = pr_addresses.lookup(db, pr_parts, near, limit)
                        db.close()
                        continue
            except sqlite3.Error:
                db.close()
                continue
            connections.append(db)
        if not connections or not words or (pr_parts and pr_parts[2]):
            return pr_results
        for count in range(len(words), 0, -1):
            street = ' '.join(words[:count])
            if all(word in set(WORDS.values()) for word in words[:count]):
                continue
            city = ' '.join(words[count:])
            rows = []
            for form in street_forms(street):
                conditions = ['num IN (?, ?)', 'norm >= ?', 'norm < ?']
                parameters = [number, number.lower(), form, form + '\uffff']
                if state:
                    conditions.append('state = ?')
                    parameters.append(state)
                if postcode:
                    conditions.append('zip = ?')
                    parameters.append(postcode)
                if city:
                    conditions.append('lower(city) LIKE ?')
                    parameters.append(city + '%')
                sql = ('SELECT num,street,city,state,zip,lat,lon,norm FROM addr WHERE '
                       + ' AND '.join(conditions) + ' ORDER BY length(norm),norm LIMIT ?')
                for connection in connections:
                    try:
                        rows.extend(connection.execute(sql, [*parameters, limit * 3]).fetchall())
                    except sqlite3.Error:
                        continue
            if rows:
                def rank(row):
                    distance = 0
                    if near:
                        distance = (row[5] - near[0]) ** 2 + ((row[6] - near[1]) * math.cos(math.radians(near[0]))) ** 2
                    return len(row[7]), distance, row[3], row[2], row[1]
                results, seen = [], set()
                for num, name, city_name, state_code, zip_code, lat, lon, normalized in sorted(rows, key=rank):
                    key = (num, normalized, lat, lon)
                    if key in seen:
                        continue
                    seen.add(key)
                    results.append({
                        'name': f'{num} {name}', 'kind': 'Street address',
                        'detail': ', '.join(part for part in (city_name, state_code, zip_code) if part),
                        'lat': lat, 'lon': lon, 'source': 'Overture Maps', 'onMap': True,
                    })
                    if len(results) == limit:
                        break
                if pr_results:
                    results = pr_results + results
                    if near:
                        scale = math.cos(math.radians(near[0]))
                        results.sort(key=lambda item: (item['lat'] - near[0]) ** 2
                                     + ((item['lon'] - near[1]) * scale) ** 2)
                return results[:limit]
        return pr_results
    finally:
        for connection in connections:
            connection.close()
