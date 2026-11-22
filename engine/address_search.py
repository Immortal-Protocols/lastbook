"""Read-only address lookup using the state indexes installed with offline maps."""
import math
import re
import sqlite3
from pathlib import Path

from engine import pr_addresses, pr_parcels, pr_permit, pr_rural, pr_rural_model
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
# How a street can end. Three of these are also state codes: Ct (Court, Connecticut), Mt (Mount, Montana), NE (northeast, Nebraska).
STREET_ENDINGS = set(WORDS.values()) | {'ne', 'nw', 'se', 'sw'}


def normalize(text):
    return ' '.join(WORDS.get(word, word) for word in re.sub(r'[^a-z0-9 ]+', ' ', text.lower()).split())


def is_address_query(query, include_rural=True):
    """A standalone ZIP remains a place query. A number followed by words is an address."""
    return bool(re.match(r'^\s*\d[\w-]*\s+\S', query) or pr_addresses.components(query) or
                pr_parcels.number(query) or (include_rural and (pr_rural.looks_rural(query) or pr_rural.parcel_direction(query))))


def street_forms(street, infer_direction=True):
    words = street.split()
    forms = [street, ' '.join(TO_DIGITS.get(word, word) for word in words),
             ' '.join(TO_WORDS.get(word, word) for word in words)]
    forms += [re.sub(r'\b(\d+)(st|nd|rd|th)\b', r'\1', form) for form in forms[:]]
    if infer_direction and words[0] not in ('n', 's', 'e', 'w', 'ne', 'nw', 'se', 'sw'):
        forms += [f'{direction} {form}' for form in forms[:] for direction in ('n', 's', 'e', 'w')]
    return list(dict.fromkeys(forms))


def _parts(query, states=True):
    number, remainder = query.strip().split(None, 1)
    number = number.upper()
    remainder = re.sub(r'[^a-z0-9 ]+', ' ', remainder.lower()).split()
    # A ZIP+4 ("62704-1234", or "62704 1234" once the hyphen is gone) is the same place as its five-digit ZIP, which the
    # index keeps: drop the four extra digits so the ZIP and the state before it are still read.
    if len(remainder) > 1 and re.fullmatch(r'\d{4}', remainder[-1]) and re.fullmatch(r'\d{5}', remainder[-2]):
        remainder.pop()
    postcode = ''
    if remainder and re.fullmatch(r'\d{5}', remainder[-1]):
        postcode = remainder.pop()
    state = ''
    for count in (3, 2, 1):
        if not states or len(remainder) <= count:
            continue
        name = ' '.join(remainder[-count:])
        code = STATES.get(name) or (name.upper() if count == 1 and name.upper() in STATE_CODES else '')
        if code:
            state = code
            remainder = remainder[:-count]
            break
    return number, normalize(' '.join(remainder)).split(), state, postcode


def _readings(query):
    """The ways to read a query, likeliest first, as (number, words, state, postcode, town).
    Words at the end that name a state can also be the street's own ending ('12 Oak Ct', '500 4th St NE') or a town
    ('Washington'), so the query is read both ways. The second reading stays narrow, so that a state that is not installed
    still finds nothing: a two-letter code is tried only as part of the street (town ''), and a state's name only as a town
    of exactly that name (town 'whole'). '100 Main St IN' does not find Inglewood, nor 'Maple Ave Kansas' Kansas City."""
    number, words, state, postcode = _parts(query)
    if not state:
        return [(number, words, state, postcode, 'starts')]
    typed = _parts(query, states=False)
    code = len(typed[1]) == len(words) + 1 and typed[1][-1].upper() in STATE_CODES
    by_state, as_typed = (number, words, state, postcode, 'starts'), (*typed, '' if code else 'whole')
    return [as_typed, by_state] if code and typed[1][-1] in STREET_ENDINGS else [by_state, as_typed]


def locality_wording(query, geo_directory, offset, limit, named_places=()):
    if not re.search(r'[,;\s]', query.strip()):
        return None
    path = Path(geo_directory) / 'addresses' / 'PR.sqlite'
    if not path.is_file():
        return None
    db = None
    try:
        db = sqlite3.connect(ro_uri(path), uri=True)
        matches = pr_permit.matches(db, query, named_places)
        if not matches:
            return None
        return pr_parcels.candidates(db, None, max(0, offset), limit, matches)
    except sqlite3.Error:
        return None
    finally:
        if db is not None:
            db.close()


def find_addresses(query, geo_directory, limit=8, near=None, model=None, parcel_offset=0, parcel_limit=None):
    """Find indexed street addresses or explicitly labeled rural road references."""
    if limit <= 0:
        return []

    def prefer_exact_street(rows):
        # Parcel evidence still wins. A street fix can replace an approximate pin,
        # but should not discard a separately recorded site such as a school.
        if (not parcel_offset and any(row['kind'] == 'Road kilometer' for row in rows)
                and not any('parcelNumber' in row for row in rows)):
            exact = _street_lookup(query, geo_directory, limit, near, exact_only=True)
            if exact:
                return (exact + [row for row in rows if row['kind'] != 'Road kilometer'])[:limit]
        return rows

    key = pr_parcels.number(query)
    rural = pr_rural.parse(query, parcel=True)
    if key or rural or pr_rural.looks_rural(query) or pr_rural.parcel_direction(query):
        path = Path(geo_directory) / 'addresses' / 'PR.sqlite'
        if path.is_file():
            db = None
            try:
                db = sqlite3.connect(ro_uri(path), uri=True)
                parcels = pr_parcels.installed(db)
                if key:
                    rows = pr_parcels.by_number(db, key) if parcels and not parcel_offset else []
                    if rows:
                        return rows
                roads = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='pr_road'").fetchone()
                if not key and (parcels or roads):
                    wording = pr_permit.matches(db, query) if parcels else {}

                    def lookup(address):
                        rows = pr_parcels.candidates(db, address, max(0, parcel_offset), parcel_limit or limit, wording) if parcels else []
                        if address and roads and not parcel_offset:
                            rows.extend(pr_rural.lookup(db, address, limit))
                        return rows

                    rows = lookup(rural)
                    if rows:
                        return prefer_exact_street(rows)
                    interpreted = pr_rural_model.interpret(model, query, rural)
                    rows = lookup(interpreted)
                    if rows:
                        for row in rows:
                            row['interpreted'] = pr_rural_model.description(interpreted)
                        return prefer_exact_street(rows)
            except sqlite3.Error:
                pass
            finally:
                if db is not None:
                    db.close()
    # Ordinary addresses and places have no parcel continuation pages.
    if parcel_offset:
        return []
    return _street_lookup(query, geo_directory, limit, near)


def _street_lookup(query, geo_directory, limit, near, exact_only=False):
    legacy_number = re.match(r'^\s*\d[\w-]*\s+\S', query)
    pr_parts = pr_addresses.components(query)
    if not (legacy_number or pr_parts):
        return []
    readings = _readings(query) if legacy_number else [('', [], '', '', 'starts')]
    for reading in readings:
        found = _lookup(*reading, geo_directory, limit, near, pr_parts, exact_only=exact_only)
        if found:
            return found
    return []


def _lookup(number, words, state, postcode, town, geo_directory, limit, near, pr_parts=None, *, exact_only=False):
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
        for count in range(len(words), 0 if town else len(words) - 1, -1):
            street = ' '.join(words[:count])
            if all(word in set(WORDS.values()) for word in words[:count]):
                continue
            city = ' '.join(words[count:])
            rows = []
            for form in street_forms(street, infer_direction=not exact_only):
                conditions = ['num IN (?, ?)']
                parameters = [number, number.lower()]
                if exact_only:
                    conditions.append('norm = ?')
                    parameters.append(form)
                else:
                    conditions.extend(('norm >= ?', 'norm < ?'))
                    parameters.extend((form, form + '\uffff'))
                if state:
                    conditions.append('state = ?')
                    parameters.append(state)
                if postcode:
                    conditions.append('zip = ?')
                    parameters.append(postcode)
                if city:
                    whole_city = exact_only or town == 'whole'
                    conditions.append('lower(city) = ?' if whole_city else 'lower(city) LIKE ?')
                    parameters.append(city if whole_city else city + '%')
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
