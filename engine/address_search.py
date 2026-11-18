"""Read-only address lookup using the state indexes installed with offline maps."""
import functools
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
# How a street can end. Three of these are also state codes: Ct (Court, Connecticut), Mt (Mount, Montana), NE (northeast, Nebraska).
STREET_ENDINGS = set(WORDS.values()) | {'ne', 'nw', 'se', 'sw'}
DIAGONALS = {'ne': 'northeast', 'nw': 'northwest', 'se': 'southeast', 'sw': 'southwest'}
DIAGONALS.update({full: short for short, full in DIAGONALS.copy().items()})


def normalize(text):
    return ' '.join(WORDS.get(word, word) for word in re.sub(r'[^a-z0-9 ]+', ' ', text.lower()).split())


NUMBER_FIRST = re.compile(r'^\s*\d[\w-]*\s+\S')


def is_address_query(query):
    """A standalone ZIP remains a place query. A number followed by words is an address.

    French writing also puts a comma after the number ('12, rue Saint-Pierre'); that form is accepted before a French
    street word. Some of those words open a US street too ('1200, R Street'): such a query finds no house and then
    goes on to the place finder (goes_on_to_places), where it went before."""
    return bool(NUMBER_FIRST.match(query) or FR_COMMA_QUERY.match(query))


def goes_on_to_places(query, region=False):
    """For an address query that found no house: is it tried as a place next?

    Yes for one that is an address only by the French comma form: it was a place query before that form existed. Yes
    too, where a region outside the US is installed, for a postcode and its commune: '14000 Caen' is not house 14000.
    Never for a number followed by words on a US map: 'Address not found' stays the answer."""
    return not NUMBER_FIRST.match(query) or bool(region and re.match(r'\s*\d{5}\s', query))


def street_forms(street):
    words = street.split()
    forms = [street, ' '.join(TO_DIGITS.get(word, word) for word in words),
             ' '.join(TO_WORDS.get(word, word) for word in words)]
    forms += [re.sub(r'\b(\d+)(st|nd|rd|th)\b', r'\1', form) for form in forms[:]]
    # Existing indexes keep both spellings, so try each without changing their normalization.
    for position in (0, -1):
        for form in forms[:]:
            parts = form.split()
            if parts[position] in DIAGONALS:
                parts[position] = DIAGONALS[parts[position]]
                forms.append(' '.join(parts))
    if words[0] not in ('n', 's', 'e', 'w') and words[0] not in DIAGONALS:
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
    return number, normalize(' '.join(remainder)).split(), state, postcode, remainder


def _readings(query):
    """The ways to read a query, likeliest first, as (number, words, state, postcode, plain, town).
    Words at the end that name a state can also be the street's own ending ('12 Oak Ct', '500 4th St NE') or a town
    ('Washington'), so the query is read both ways. The second reading stays narrow, so that a state that is not installed
    still finds nothing: a two-letter code is tried only as part of the street (town ''), and a state's name only as a town
    of exactly that name (town 'whole'). '100 Main St IN' does not find Inglewood, nor 'Maple Ave Kansas' Kansas City."""
    number, words, state, postcode, plain = _parts(query)
    if not state:
        return [(number, words, state, postcode, plain, 'starts')]
    typed = _parts(query, states=False)
    code = len(typed[1]) == len(words) + 1 and typed[1][-1].upper() in STATE_CODES
    by_state, as_typed = (number, words, state, postcode, plain, 'starts'), (*typed, '' if code else 'whole')
    return [as_typed, by_state] if code and typed[1][-1] in STREET_ENDINGS else [by_state, as_typed]


# French indexes, built by tools/build_addresses_ban.py from the Base Adresse Nationale. Such an index names its rule in
# its meta table (norm = fr-1), the per-index key discussed in #31; a file named after a US state, or the legacy
# addresses.sqlite, is always read the US way.
# French text is folded (é -> e, œ -> oe) where the US rules above drop accented letters ('Église' -> 'glise'). The US
# indexes were built with those rules, so the US side keeps them: folding there too needs every state rebuilt.
FR_WORDS = {
    'r': 'rue', 'av': 'avenue', 'ave': 'avenue', 'bd': 'boulevard', 'bld': 'boulevard', 'blvd': 'boulevard',
    'boul': 'boulevard', 'ch': 'chemin', 'che': 'chemin', 'chem': 'chemin', 'imp': 'impasse', 'rte': 'route',
    'all': 'allee', 'pl': 'place', 'sq': 'square', 'res': 'residence', 'lot': 'lotissement', 'pas': 'passage',
    'rpt': 'rond point', 'vlge': 'village', 'ham': 'hameau', 'ld': 'lieu dit', 'fg': 'faubourg', 'fbg': 'faubourg',
    'crs': 'cours', 'sen': 'sentier', 'prom': 'promenade', 'mte': 'montee', 'st': 'saint', 'ste': 'sainte',
    'gal': 'general', 'gen': 'general', 'mal': 'marechal', 'dr': 'docteur', 'pdt': 'president', 'cdt': 'commandant',
    'mgr': 'monseigneur', 'nd': 'notre dame',
}
FR_DROP = {'de', 'du', 'des', 'la', 'le', 'les', 'l', 'd', 'au', 'aux'}   # 'Place du Général de Gaulle' = 'place Général de Gaulle'
FR_TYPES = {'rue', 'avenue', 'boulevard', 'chemin', 'impasse', 'route', 'allee', 'place', 'square', 'residence',
            'lotissement', 'passage', 'rond', 'point', 'village', 'hameau', 'lieu', 'dit', 'faubourg', 'cours', 'quai',
            'sentier', 'promenade', 'montee', 'venelle', 'ruelle', 'saint', 'sainte'}
FR_REPEATS = ('bis', 'ter', 'quater', 'quinquies')
# Only words a US address does not start with: 'avenue', 'boulevard', 'place' and 'route' are left out.
FR_COMMA_QUERY = re.compile(r'^\s*\d+\s*(?:bis|ter|quater|quinquies|[a-z])?\s*,\s*(?:rue|r|bd|chemin|che|impasse|imp|'
                            r'all[ée]e|all|rte|quai|venelle|ruelle|sentier|hameau|lotissement|r[ée]sidence|'
                            r'lieu[- ]dit)\b', re.IGNORECASE)
FR_NORM = 'fr-1'
FOLD = str.maketrans({'œ': 'oe', 'Œ': 'OE', 'æ': 'ae', 'Æ': 'AE', 'ß': 'ss'})


def fold(text):
    """'Bonnœil' -> 'bonnoeil', 'Église' -> 'eglise': letters lose their accents instead of being dropped."""
    text = unicodedata.normalize('NFKD', text.translate(FOLD))
    return ''.join(char for char in text if not unicodedata.combining(char)).lower()


def normalize_fr(text):
    """'Place du Général de Gaulle' and 'pl general de gaulle' -> 'place general gaulle'. Index and query share it."""
    words = []
    for word in re.sub(r'[^a-z0-9 ]+', ' ', fold(text)).split():
        words += FR_WORDS.get(word, word).split()
    return ' '.join(word for word in words if word not in FR_DROP)


def _parts_fr(query):
    """'1 bis, rue Écuyère 14000 Caen' -> ('1bis', ['rue', 'ecuyere'], ['caen'], '14000').

    The postcode comes before the commune in French; words after it can only be the place."""
    tokens = re.sub(r'[^a-z0-9 ]+', ' ', fold(query)).split()
    if not tokens:   # digits and letters of another script: nothing a French index holds
        return '', [], [], ''
    number = tokens.pop(0)
    if len(tokens) > 1 and number.isdigit():
        word = tokens[0]
        if word in FR_REPEATS or (len(word) == 1 and word.isalpha() and word not in FR_WORDS
                                  and FR_WORDS.get(tokens[1], tokens[1]).split()[0] in FR_TYPES):
            number += tokens.pop(0)
    cut = next((index for index, token in enumerate(tokens) if re.fullmatch(r'\d{5}', token)), None)
    postcode, before, after = '', tokens, []
    if cut is not None:
        postcode, before, after = tokens[cut], tokens[:cut], tokens[cut + 1:]
        if 'cedex' in after:
            after = after[:after.index('cedex')]
    return number, normalize_fr(' '.join(before)).split(), normalize_fr(' '.join(after)).split(), postcode


@functools.lru_cache(maxsize=4096)
def _french_places(city):
    """The index stores 'Cherbourg-en-Cotentin (Tourlaville)' for an address in a delegated commune."""
    match = re.fullmatch(r'(.*?) \((.*)\)', city or '')
    commune, delegated = (match[1], match[2]) if match else (city or '', '')
    names = [normalize_fr(commune)]
    if delegated:
        old = normalize_fr(delegated)
        names += [old, f'{old} {names[0]}', f'{names[0]} {old}']
    return commune, delegated, tuple(names)


def _french_place(city, typed):
    return any(name.startswith(typed) for name in _french_places(city)[2])


def _french_number(num):
    match = re.fullmatch(r'(\d+)([a-z]+)', num)
    if not match:
        return num
    return f'{match[1]} {match[2]}' if match[2] in FR_REPEATS else match[1] + match[2].upper()


def _french_index(path):
    """Only an index that is not named after a US state is opened to read its rule."""
    if path.stem.upper() in STATE_CODES:
        return None
    try:
        connection = sqlite3.connect(ro_uri(path), uri=True)
    except sqlite3.Error:
        return None
    try:
        row = connection.execute("SELECT value FROM meta WHERE key = 'norm'").fetchone()
    except sqlite3.Error:
        row = None
    if row and row[0] == FR_NORM:
        connection.create_function('fr_place', 2, _french_place, deterministic=True)
        return connection
    connection.close()
    return None


def _find_french(connections, query, limit, near):
    number, before, after, postcode = _parts_fr(query)
    for count in range(len(before), 0, -1):
        street_words = before[:count]
        if all(word in FR_TYPES for word in street_words):
            continue
        street = ' '.join(street_words)
        city = ' '.join(before[count:] + after)
        conditions = ['num IN (?, ?)', 'norm >= ?', 'norm < ?']
        parameters = [number, number.upper(), street, street + '￿']
        if postcode:
            conditions.append('zip = ?')
            parameters.append(postcode)
        if city:
            conditions.append('fr_place(city, ?)')
            parameters.append(city)
        sql = ('SELECT num,street,city,state,zip,lat,lon,norm FROM addr WHERE '
               + ' AND '.join(conditions) + ' ORDER BY length(norm),norm LIMIT ?')
        rows = []
        for connection in connections:
            try:
                rows.extend(connection.execute(sql, [*parameters, limit * 3]).fetchall())
            except sqlite3.Error:
                continue
        if not rows:
            continue

        def rank(row):
            distance = 0
            if near:
                distance = (row[5] - near[0]) ** 2 + ((row[6] - near[1]) * math.cos(math.radians(near[0]))) ** 2
            # A row found through its lieu-dit (norm is not its street) comes after rows found by their street.
            return (row[7] != normalize_fr(row[1]), bool(city) and city not in _french_places(row[2])[2],
                    len(row[7]), distance, row[2], row[1])
        results, seen = [], set()
        for num, name, city_name, _, zip_code, lat, lon, _ in sorted(rows, key=rank):
            key = (num, name, lat, lon)
            if key in seen:
                continue
            seen.add(key)
            commune, delegated, _ = _french_places(city_name)
            place = ' '.join(part for part in (zip_code, commune) if part)
            results.append({
                'name': f'{_french_number(num)} {name}', 'kind': 'Street address',
                'detail': ', '.join(part for part in (delegated, place) if part),
                'lat': lat, 'lon': lon, 'source': 'Base Adresse Nationale', 'onMap': True,
            })
            if len(results) == limit:
                break
        return results
    return []


def find_addresses(query, geo_directory, limit=8, near=None):
    """Return exact house-number matches from installed indexes, never a guessed house."""
    if not is_address_query(query):
        return []
    geo_directory = Path(geo_directory)
    paths = sorted((geo_directory / 'addresses').glob('*.sqlite'))
    french = []
    try:
        for path in paths[:]:
            connection = _french_index(path)
            if connection:
                french.append(connection)
                paths.remove(path)
        # A French index is read with French rules whatever the query ends with ('Bellême' is not Maine).
        found = _find_french(french, query, limit, near) if french else []
        found_us = _find_us(query, geo_directory, paths, limit, near)
    finally:
        for connection in french:
            connection.close()
    if not found:
        return found_us
    if not found_us:
        return found
    both = found_us + found
    if near:
        both.sort(key=lambda r: (r['lat'] - near[0]) ** 2 + ((r['lon'] - near[1]) * math.cos(math.radians(near[0]))) ** 2)
    return both[:limit]


def _find_us(query, geo_directory, paths, limit, near):
    """The US lookup, unchanged: US words, a state name or code at the end, the ZIP last."""
    if len(query.split()) < 2:  # '12,rue Haute' passes is_address_query for the French side only
        return []
    for reading in _readings(query):
        found = _lookup(*reading, geo_directory, paths, limit, near)
        if found:
            return found
    return []


def _lookup(number, words, state, postcode, plain, town, geo_directory, paths, limit, near):
    if not words:
        return []
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
        for count in range(len(words), 0 if town else len(words) - 1, -1):
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
                    # normalize() keeps a word's first letter (north->n, saint->st, mount->mt) and only strips
                    # punctuation, so this cheap SQL prefilter never drops a row the Python city check would keep.
                    conditions.append('lower(substr(city,1,1)) = ?')
                    parameters.append(city[0])
                # The city is compared in Python, after normalize() on both sides: the query's "north", "saint" and
                # punctuation must meet the stored "North Hollywood", "Saint Paul" and "St. Louis" in the same form.
                sql = ('SELECT num,street,city,state,zip,lat,lon,norm FROM addr WHERE '
                       + ' AND '.join(conditions) + ' ORDER BY length(norm),norm')
                if not city:
                    sql += ' LIMIT ?'
                    parameters.append(limit * 3)
                plain_city = ' '.join(plain[count:])   # normalize() maps word for word, so the split lines up
                match = str.__eq__ if town == 'whole' else str.startswith   # 'whole': a state's name read as a town of just that name
                for connection in connections:
                    # Rows the city check drops must not use up the limit, so read on until enough pass it.
                    kept = 0
                    try:
                        for row in connection.execute(sql, parameters):
                            stored = row[2] or ''
                            if city and not (match(normalize(stored), city) or match(stored.lower(), plain_city)):
                                continue
                            rows.append(row)
                            kept += 1
                            if kept == limit * 3:
                                break
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
