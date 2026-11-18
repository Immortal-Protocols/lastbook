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


US_NORM = 'us'        # indexes without a meta 'norm' key: the published US state indexes and the legacy addresses.sqlite


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


class Scheme:
    """One street-first address scheme, as data. An index declares its scheme in meta ('norm').

    The engine holds no code per country: adding a street-first country is one entry in SCHEMES
    saying how its letters fold, which street words shorten, what word marks the house number,
    what a postcode and a house number look like, which words after the number merely name the
    place, and how a found address is written back."""

    def __init__(self, chars, words, markers=(), number_pick='first', skip_after=(),
                 number=r'\d{1,4}[a-z]?', postcode=r'\d{5}', postcode_policy='strict',
                 street_kinds=(), form_suffixes=(), place_stop=(), name='{street} {num}',
                 min_street=3):
        self.chars = str.maketrans(chars)
        self.words = words
        self.markers = markers
        self.number_pick = number_pick
        self.skip_after = skip_after
        self.number = re.compile(number)
        self.postcode = re.compile(postcode)
        self.postcode_policy = postcode_policy
        self.street_kinds = street_kinds
        self.form_suffixes = form_suffixes
        self.place_stop = place_stop
        self.name = name
        self.min_street = min_street

    def fold(self, text):
        """Map the scheme's letters, lower-case, and drop any other accents."""
        text = unicodedata.normalize('NFC', text).translate(self.chars).lower()
        text = ''.join(ch for ch in unicodedata.normalize('NFD', text) if unicodedata.category(ch) != 'Mn')
        return text.translate(self.chars)

    def normalize(self, text):
        """'Königstraße' -> 'koenigstrasse', 'Berliner Straße' -> 'berliner str' under de-1."""
        # Suffixes fold as whole words; a compound keeps its letters and the range query matches by prefix.
        words = re.sub(r'[^a-z0-9 ]+', ' ', self.fold(text)).split()
        return ' '.join(self.words.get(word, word) for word in words)

    def tokens(self, query):
        text = self.fold(query)
        if self.markers:
            marker = '|'.join(re.escape(word) for word in self.markers)
            text = re.sub(rf'\b(?:{marker})\.?\s*[:.]?\s*(?=\d)', f' {self.markers[0]} ', text)
        text = re.sub(r'(\d+)\s*/\s*([a-z])\b', r'\1\2', text)               # '5/a' is one house number
        text = re.sub(r'(\b\d+)\s*[-–]\s*\d+[a-z]?\b', r'\1', text)          # a range ('5-7') answers at its first end
        return re.sub(r'[^a-z0-9 ]+', ' ', text).split()

    def _number_index(self, tokens):
        """(index of the house number, index where the street ends), or (-1, -1)."""
        for index in range(len(tokens) - 2, 0, -1):                          # an explicit marker ('No: 22') wins
            if tokens[index] in self.markers and self.number.fullmatch(tokens[index + 1]):
                return index + 1, index
        indexes = range(1, len(tokens)) if self.number_pick == 'first' else range(len(tokens) - 1, 0, -1)
        for index in indexes:
            token = tokens[index]
            if self.postcode.fullmatch(token):
                continue                                  # a postcode, not a house number
            if self.number.fullmatch(token) and tokens[index - 1] not in self.skip_after:
                return index, index
        return -1, -1

    def parse(self, query):
        """(number, street words, postcode, qualifier words) in street-first order, or None."""
        tokens = self.tokens(query)
        if len(tokens) < 2:
            return None
        number_index, street_end = self._number_index(tokens)
        if number_index < 0:
            return None
        number = tokens[number_index].upper()
        street = tokens[:street_end]
        rest = tokens[number_index + 1:]
        if rest and re.fullmatch(r'[a-z]', rest[0]):
            number += rest.pop(0).upper()                  # '12 a' as written on many letters
        while rest and self.number.fullmatch(rest[0]):
            rest.pop(0)                                   # the second half of a spaced range ('5 7')
        postcode = ''
        for index, token in enumerate(rest):
            if self.postcode.fullmatch(token):
                postcode = token
                rest.pop(index)
                break
        qualifier = [token for token in rest if self.words.get(token, token) not in self.place_stop]
        if not street or len(' '.join(street)) < self.min_street or not any(re.search(r'[a-z]', word) for word in street):
            return None                                  # 'B 10 5' must not answer Bodoweg 10
        return number, street, postcode, qualifier

    def street_forms(self, words):
        mapped = [self.words.get(word, word) for word in words]
        base = ' '.join(mapped)
        forms = [base]
        if mapped and mapped[-1] not in self.street_kinds:
            forms += [f'{base} {suffix}' for suffix in self.form_suffixes]
        return list(dict.fromkeys(forms))

    def place_matches(self, qualifier, city, district):
        words = [word for word in qualifier.split() if word not in self.place_stop]
        if not words:
            return True
        hay = ' '.join(part for part in (self.normalize(city or ''), self.normalize(district or '')) if part).split()
        return all(any(h.startswith(word) for h in hay) for word in words)


SCHEMES = {
    'de-1': Scheme(
        chars={'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue', 'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss'},
        words={'strasse': 'str', 'str': 'str', 'platz': 'pl', 'sankt': 'st', 'saint': 'st'},
        markers=('nr', 'nummer', 'hausnummer'),
        skip_after=('des',),
        postcode_policy='district-loose',
        street_kinds=('str', 'pl', 'weg', 'allee', 'gasse', 'damm', 'ring', 'steige'),
        form_suffixes=('str',),
        place_stop=('stuttgart', 'bw', 'baden-wuerttemberg', 'deutschland', 'de'),
    ),
}


def normalize_as(norm, text):
    """Normalize a street name the way the index that declares scheme `norm` stored it."""
    return SCHEMES[norm].normalize(text)


def is_street_first_address_query(query):
    """Street, then house number ('Hauptstraße 5, 70173 Stuttgart') under some known scheme."""
    return any(scheme.parse(query) is not None for scheme in SCHEMES.values())


def _postcode_fits(connection, postcode, district, city):
    """Whether this index uses that postcode for the district (or city) an address without one belongs to."""
    column, value = ('district', district) if district else ('city', city)
    if not value:
        return False
    try:
        return connection.execute(f'SELECT 1 FROM addr WHERE zip = ? AND {column} = ? LIMIT 1',
                                  (postcode, value)).fetchone() is not None
    except sqlite3.Error:
        return False


def _find_street_first(scheme, norm, parts, geo_directory, limit, near):
    number, words, postcode, qualifier = parts
    qual = ' '.join(qualifier)
    paths = [path for path in sorted((geo_directory / 'addresses').glob('*.sqlite')) if _index_info(path)[0] == norm]
    rows = []
    for path in paths:
        source = _index_info(path)[1] or 'OpenStreetMap'
        try:
            connection = sqlite3.connect(ro_uri(path), uri=True)
        except sqlite3.Error:
            continue
        try:
            for form in scheme.street_forms(words):
                conditions = ['num IN (?, ?)', 'norm >= ?', 'norm < ?']
                parameters = [number, number.lower(), form, form + '\uffff']
                if postcode and scheme.postcode_policy == 'strict':
                    conditions.append('zip = ?')
                    parameters.append(postcode)
                sql = ('SELECT num,street,city,state,zip,lat,lon,norm,district FROM addr WHERE '
                       + ' AND '.join(conditions) + ' ORDER BY length(norm),norm LIMIT 500')
                found = connection.execute(sql, parameters).fetchall()
                if postcode and scheme.postcode_policy == 'district-loose':
                    # A mapped house with no postcode of its own still answers a postcode this district really uses; a wrong one answers nothing.
                    exact = [row for row in found if row[4] == postcode]
                    loose = [row for row in found if not row[4]
                             and _postcode_fits(connection, postcode, row[8] or '', row[2] or '')]
                    found = exact or loose
                rows.extend((*row, source) for row in found if not qual or scheme.place_matches(qual, row[2], row[8]))
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
            'name': scheme.name.format(street=name, num=num), 'kind': 'Street address',
            'detail': where,
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

    A street-first index is written 'Hauptstraße 5', so installed schemes are tried before the
    number-first US rules decide that the query is not an address at all."""
    geo_directory = Path(geo_directory)
    if not is_address_query(query):
        installed = {_index_info(path)[0] for path in sorted((geo_directory / 'addresses').glob('*.sqlite'))}
        for norm, scheme in SCHEMES.items():
            if norm not in installed:
                continue
            parts = scheme.parse(query)
            if parts is not None:
                found = _find_street_first(scheme, norm, parts, geo_directory, limit, near)
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
