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


def normalize(text):
    return ' '.join(WORDS.get(word, word) for word in re.sub(r'[^a-z0-9 ]+', ' ', text.lower()).split())


def fold(text):
    """Drop accents: 'Ffordd y Cŵn' -> 'Ffordd y Cwn'. normalize() turns an accented letter into a space, which is what the
    US indexes were built with, so find_addresses() tries the text as typed first and this folded form second."""
    return ''.join(c for c in unicodedata.normalize('NFKD', text) if not unicodedata.combining(c)).replace('ß', 'ss')


def uk_postcode(words):
    """A UK postcode ('SW1A 2AA', 'sw1a2aa') at the end of lowercase words: (canonical 'SW1A 2AA', words it used), else None.
    Only a full postcode counts, so a US street such as 'Highway I5' is never read as one."""
    outward, inward = r'[a-z]{1,2}\d[a-z\d]?', r'\d[a-z]{2}'
    if words and len(words[-1]) in (5, 6, 7) and re.fullmatch(outward + inward, words[-1]):
        return f'{words[-1][:-3]} {words[-1][-3:]}'.upper(), 1
    if len(words) >= 2 and re.fullmatch(outward, words[-2]) and re.fullmatch(inward, words[-1]):
        return f'{words[-2]} {words[-1]}'.upper(), 2
    return None


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


def _parts(query, states=True):
    number, remainder = query.strip().split(None, 1)
    number = number.upper()
    remainder = re.sub(r'[^a-z0-9 ]+', ' ', remainder.lower()).split()
    postcode = ''
    if remainder and re.fullmatch(r'\d{5}', remainder[-1]):
        postcode = remainder.pop()
    elif (uk := uk_postcode(remainder)):
        postcode = uk[0]
        del remainder[-uk[1]:]
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


def _source_label(connection):
    """What to credit a result to: the index's own meta 'source' (Overture indexes keep their short 'Overture Maps' label)."""
    try:
        row = connection.execute("SELECT value FROM meta WHERE key = 'source'").fetchone()
    except sqlite3.Error:
        row = None
    text = (row[0] if row else '') or ''
    return text if text and not text.lower().startswith('overture') else 'Overture Maps'


def find_addresses(query, geo_directory, limit=8, near=None):
    """Return exact house-number matches from installed indexes, never a guessed house.
    If the text as typed finds nothing and has accents (Welsh, say), it is tried once more with the accents dropped."""
    found = _find(query, geo_directory, limit, near)
    folded = fold(query)
    return found if found or folded == query else _find(folded, geo_directory, limit, near)


def _find(query, geo_directory, limit, near):
    if not is_address_query(query):
        return []
    number, words, state, postcode = _parts(query)
    if not words:
        return []
    geo_directory = Path(geo_directory)
    paths = sorted((geo_directory / 'addresses').glob('*.sqlite'))
    legacy = geo_directory / 'addresses.sqlite'
    if state and not legacy.is_file() and not any(path.stem.upper() in STATE_CODES for path in paths):
        # No US state index is installed, so 'Washington' in '7 Church Lane Washington NE37 1AA' is a town, not a state filter.
        # (With any US index installed, a state that is not installed still finds nothing, as before.)
        number, words, state, postcode = _parts(query, states=False)
    if state:
        paths = [path for path in paths if path.stem.upper() == state]
    if not paths and legacy.is_file():
        paths = [legacy]
    connections, sources = [], {}
    try:
        for path in paths:
            try:
                connections.append(sqlite3.connect(ro_uri(path), uri=True))
                sources[connections[-1]] = _source_label(connections[-1])
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
                        rows.extend((*row, sources[connection]) for row in connection.execute(sql, [*parameters, limit * 3]).fetchall())
                    except sqlite3.Error:
                        continue
            if rows:
                def rank(row):
                    distance = 0
                    if near:
                        distance = (row[5] - near[0]) ** 2 + ((row[6] - near[1]) * math.cos(math.radians(near[0]))) ** 2
                    return len(row[7]), distance, row[3], row[2], row[1]
                results, seen = [], set()
                for num, name, city_name, state_code, zip_code, lat, lon, normalized, source in sorted(rows, key=rank):
                    key = (num, normalized, lat, lon)
                    if key in seen:
                        continue
                    seen.add(key)
                    results.append({
                        'name': f'{num} {name}', 'kind': 'Street address',
                        'detail': ', '.join(part for part in (city_name, state_code, zip_code) if part),
                        'lat': lat, 'lon': lon, 'source': source, 'onMap': True,
                    })
                    if len(results) == limit:
                        break
                return results
        return []
    finally:
        for connection in connections:
            connection.close()
