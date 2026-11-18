"""Read-only address lookup using the state indexes installed with offline maps."""
import math
import re
import sqlite3
import unicodedata
from pathlib import Path

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


DE_NORM = 'de-1'


def normalize(text):
    return ' '.join(WORDS.get(word, word) for word in re.sub(r'[^a-z0-9 ]+', ' ', text.lower()).split())


def is_address_query(query):
    """A standalone ZIP remains a place query. A number followed by words is an address."""
    return bool(re.match(r'^\s*\d[\w-]*\s+\S', query))


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
    # A ZIP+4 ("62704-1234", or "62704 1234" once the hyphen is gone) is the same place as its five-digit ZIP, which the
    # index keeps: drop the four extra digits so the ZIP and the state before it are still read.
    if len(remainder) > 1 and re.fullmatch(r'\d{4}', remainder[-1]) and re.fullmatch(r'\d{5}', remainder[-2]):
        remainder.pop()
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


_DE_CHARS = str.maketrans({'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue', 'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss'})
DE_WORDS = {'strasse': 'str', 'str': 'str', 'platz': 'pl', 'sankt': 'st', 'saint': 'st'}
_DE_PLACE_STOP = ('stuttgart', 'bw', 'baden-wuerttemberg', 'deutschland', 'de')


def fold_de(text):
    """Expand ä/ö/ü/ß and drop any other accents: 'Königstraße' -> 'koenigstrasse'."""
    text = unicodedata.normalize('NFC', text).translate(_DE_CHARS).lower()
    return ''.join(ch for ch in unicodedata.normalize('NFD', text) if unicodedata.category(ch) != 'Mn')


def normalize_de(text):
    """Scheme 'de-1': 'Königstraße' -> 'koenigstrasse', 'Berliner Straße' -> 'berliner str'."""
    # Suffixes fold as whole words; a compound keeps its letters and the range query matches by prefix.
    words = re.sub(r'[^a-z0-9 ]+', ' ', fold_de(text)).split()
    return ' '.join(DE_WORDS.get(word, word) for word in words)


def _parts_de(query):
    """(number, street words, postcode, qualifier) in German street-first order, or None."""
    tokens = re.sub(r'[^a-z0-9 ]+', ' ', re.sub(r'\b(?:nr|nummer|hausnummer)\.?\s*[:.]?\s*(?=\d)', ' ', fold_de(query))).split()
    if len(tokens) < 2:
        return None
    number_index = -1
    for index in range(1, len(tokens)):
        token = tokens[index]
        if re.fullmatch(r'\d{5}', token):
            continue                                  # a postcode, not a house number
        if re.fullmatch(r'\d{1,4}[a-z]?', token) and tokens[index - 1] != 'des':
            number_index = index
            break
    if number_index < 0:
        return None
    number = tokens[number_index].upper()
    street = tokens[:number_index]
    rest = tokens[number_index + 1:]
    if rest and re.fullmatch(r'[a-z]', rest[0]):
        number += rest.pop(0).upper()                  # '12 a' as written on many German letters
    while rest and re.fullmatch(r'\d{1,4}[a-z]?', rest[0]):
        rest.pop(0)                                   # the second half of a range ('5-7', '5-7a')
    postcode = ''
    for index, token in enumerate(rest):
        if re.fullmatch(r'\d{5}', token):
            postcode = token
            rest.pop(index)
            break
    qualifier = [token for token in rest if token not in _DE_PLACE_STOP]
    if not street or len(' '.join(street)) < 3 or not any(re.search(r'[a-z]', word) for word in street):
        return None                                  # 'B 10 5' must not answer Bodoweg 10
    return number, street, postcode, qualifier


def is_german_address_query(query):
    """Street, then house number ('Hauptstraße 5, 70173 Stuttgart'); a leading postcode is a place."""
    return _parts_de(query) is not None


def _de_street_forms(words):
    mapped = [DE_WORDS.get(word, word) for word in words]
    base = ' '.join(mapped)
    forms = [base]
    if mapped[-1] not in ('str', 'pl', 'weg', 'allee', 'gasse', 'damm', 'ring', 'steige'):
        forms.append(f'{base} str')
    return list(dict.fromkeys(forms))


def _de_postcode_fits(connection, postcode, district, city):
    """Whether this index uses that postcode for the district (or city) an address without one belongs to."""
    column, value = ('district', district) if district else ('city', city)
    if not value:
        return False
    try:
        return connection.execute(f'SELECT 1 FROM addr WHERE zip = ? AND {column} = ? LIMIT 1',
                                  (postcode, value)).fetchone() is not None
    except sqlite3.Error:
        return False


def _de_place_matches(qualifier, city, district):
    words = [word for word in qualifier.split() if word not in _DE_PLACE_STOP]
    if not words:
        return True
    hay = ' '.join(part for part in (normalize_de(city or ''), normalize_de(district or '')) if part).split()
    return all(any(h.startswith(word) for h in hay) for word in words)


def _find_de(parts, geo_directory, limit, near):
    number, words, postcode, qualifier = parts
    qual = ' '.join(qualifier)
    paths = [path for path in sorted((geo_directory / 'addresses').glob('*.sqlite')) if _index_info(path)[0] == DE_NORM]
    rows = []
    for path in paths:
        source = _index_info(path)[1] or 'OpenStreetMap'
        try:
            connection = sqlite3.connect(ro_uri(path), uri=True)
        except sqlite3.Error:
            continue
        try:
            for form in _de_street_forms(words):
                conditions = ['num IN (?, ?)', 'norm >= ?', 'norm < ?']
                parameters = [number, number.lower(), form, form + '\uffff']
                sql = ('SELECT num,street,city,state,zip,lat,lon,norm,district FROM addr WHERE '
                       + ' AND '.join(conditions) + ' ORDER BY length(norm),norm LIMIT 500')
                found = connection.execute(sql, parameters).fetchall()
                if postcode:   # a mapped house with no postcode of its own still answers a postcode this district really uses; a wrong one answers nothing
                    exact = [row for row in found if row[4] == postcode]
                    loose = [row for row in found if not row[4]
                             and _de_postcode_fits(connection, postcode, row[8] or '', row[2] or '')]
                    found = exact or loose
                rows.extend((*row, source) for row in found if not qual or _de_place_matches(qual, row[2], row[8]))
        except sqlite3.Error:
            continue
        finally:
            connection.close()
    results, seen = [], []
    for num, name, city, state, zip_code, lat, lon, normalized, district, source in sorted(rows, key=_rank(near)):
        if any(n == num and s == normalized and c == city and abs(lat - y) < 0.0005 and abs(lon - x) < 0.0006
               for n, s, c, y, x in seen):
            continue
        seen.append((num, normalized, city, lat, lon))
        where = ', '.join(part for part in (district, city, zip_code) if part)
        results.append({
            'name': f'{name} {num}', 'kind': 'Street address',
            'detail': where or 'Stuttgart',
            'lat': lat, 'lon': lon, 'source': source, 'onMap': True,
        })
        if len(results) == limit:
            break
    return results


_INFO = {}


def _index_info(path):
    """(norm scheme, source line) from an index's meta table, cached until the file changes."""
    try:
        stat = path.stat()
    except OSError:
        return US_NORM, None
    key = (str(path), stat.st_mtime_ns, stat.st_size)
    if key not in _INFO:
        meta = {}
        try:
            connection = sqlite3.connect(ro_uri(path), uri=True)
            try:
                meta = dict(connection.execute("SELECT key,value FROM meta WHERE key IN ('norm','source')").fetchall())
            finally:
                connection.close()
        except sqlite3.Error:
            pass
        _INFO[key] = (meta.get('norm') or US_NORM, meta.get('source'))
    return _INFO[key]


def _rank(near):
    def rank(row):
        distance = 0
        if near:
            distance = (row[5] - near[0]) ** 2 + ((row[6] - near[1]) * math.cos(math.radians(near[0]))) ** 2
        return len(row[7]), distance, row[3], row[2], row[1]
    return rank


def find_addresses(query, geo_directory, limit=8, near=None):
    """Return exact house-number matches from installed indexes, never a guessed house.

    A German index is written street first ('Hauptstraße 5'), so it is tried before the number-first US
    rules decide that the query is not an address at all."""
    geo_directory = Path(geo_directory)
    if not is_address_query(query):
        if DE_NORM in {_index_info(path)[0] for path in sorted((geo_directory / 'addresses').glob('*.sqlite'))}:
            parts = _parts_de(query)
            if parts is not None:
                found = _find_de(parts, geo_directory, limit, near)
                if found:
                    return found
        return []
    number, words, state, postcode = _parts(query)
    if not words:
        return []
    paths = sorted((geo_directory / 'addresses').glob('*.sqlite'))
    if state:
        paths = [path for path in paths if path.stem.upper() == state]
    legacy = geo_directory / 'addresses.sqlite'
    if not paths and legacy.is_file():
        paths = [legacy]
    connections = []
    try:
        for path in paths:
            try:
                connections.append(sqlite3.connect(ro_uri(path), uri=True))
            except sqlite3.Error:
                continue
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
                return results
        return []
    finally:
        for connection in connections:
            connection.close()
