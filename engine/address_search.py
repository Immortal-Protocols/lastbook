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
    'rua': 'r', 'avenida': 'av', 'travessa': 'tv', 'alameda': 'al',
    'praca': 'pc', 'rodovia': 'rod', 'estrada': 'estr', 'beco': 'bc',
    'largo': 'lg', 'viaduto': 'vd', 'passagem': 'psg', 'servidao': 'srv',
    'quadra': 'qd', 'lote': 'lt', 'bloco': 'bl', 'conjunto': 'cj',
    'norte': 'n', 'sul': 's', 'leste': 'e', 'oeste': 'w',
    'sao': 's', 'santa': 'sta', 'santo': 'sto', 'doutor': 'dr',
    'professor': 'prof', 'general': 'gal', 'coronel': 'cel',
    'presidente': 'pres', 'governador': 'gov', 'senador': 'sen',
    'deputado': 'dep', 'brigadeiro': 'brig', 'marechal': 'mal',
}
BR_STATE_NAMES = (
    'Acre|Alagoas|Amapa|Amazonas|Bahia|Ceara|Distrito Federal|Espirito Santo|'
    'Goias|Maranhao|Mato Grosso|Mato Grosso do Sul|Minas Gerais|Para|Paraiba|'
    'Parana|Pernambuco|Piaui|Rio de Janeiro|Rio Grande do Norte|'
    'Rio Grande do Sul|Rondonia|Roraima|Santa Catarina|Sao Paulo|Sergipe|Tocantins'
).split('|')
BR_STATE_CODES = 'AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO'.split()
BR_STATES = dict(zip((name.lower() for name in BR_STATE_NAMES), BR_STATE_CODES))

US_STATE_NAMES = (
    'Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|'
    'District of Columbia|Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|'
    'Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|'
    'Mississippi|Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|'
    'New Mexico|New York|North Carolina|North Dakota|Ohio|Oklahoma|Oregon|'
    'Pennsylvania|Puerto Rico|Rhode Island|South Carolina|South Dakota|'
    'Tennessee|Texas|Utah|Vermont|Virginia|Washington|West Virginia|Wisconsin|Wyoming'
).split('|')
US_STATE_CODES = 'AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA PR RI SC SD TN TX UT VT VA WA WV WI WY'.split()

STATE_CODES = BR_STATE_CODES + US_STATE_CODES
STATES = {**dict(zip((name.lower() for name in US_STATE_NAMES), US_STATE_CODES)), **BR_STATES}

ONES = 'zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty'.split()
ORDINALS = 'zeroth first second third fourth fifth sixth seventh eighth ninth tenth eleventh twelfth thirteenth fourteenth fifteenth sixteenth seventeenth eighteenth nineteenth twentieth'.split()
TO_DIGITS = {word: str(number) for number, word in enumerate(ONES)}
for number, word in enumerate(ORDINALS):
    suffix = 'th' if 10 <= number % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(number % 10, 'th')
    TO_DIGITS[word] = f'{number}{suffix}'
TO_WORDS = {value: key for key, value in TO_DIGITS.items()}

PT_ONES = 'zero um dois tres quatro cinco seis sete oito nove dez onze doze treze quatorze quinze dezesseis dezessete dezoito dezenove vinte'.split()
PT_TO_DIGITS = {word: str(number) for number, word in enumerate(PT_ONES)}
PT_TO_DIGITS.update({'uma': '1', 'duas': '2', 'catorze': '14', 'primeiro': '1', 'primeira': '1', 'segundo': '2', 'segunda': '2', 'terceiro': '3', 'terceira': '3'})
PT_TO_WORDS = {str(number): word for number, word in enumerate(PT_ONES)}

_STANDALONE_POSTCODE = re.compile(r'^\s*(?:\d{5}|\d{5}-?\d{3})\s*$')
_LEADING_NUM_ADDR = re.compile(r'^\s*\d[\w-]*\s+\S')
_LEADING_CEP = re.compile(r'^\s*\d{5}-\d{3}(?:\s|$)')
_BR_NUM_ADDR = re.compile(r'^\s*[^\d\s][\w\s.,\'-]*?(?:,|\s)\s*(?:n[roº°.]*\s+|num(?:ero)?\s+)?(\d{1,5}[a-zA-Z]?)(?:\s*$|[\s,])', re.I)
_HOUSE_NUM_TOKEN = re.compile(r'^\d{1,5}[a-z]?$')


def _strip_accents(text):
    return ''.join(ch for ch in unicodedata.normalize('NFKD', text or '') if not unicodedata.combining(ch))


def normalize(text):
    clean = _strip_accents(text).lower()
    return ' '.join(WORDS.get(word, word) for word in re.sub(r'[^a-z0-9 ]+', ' ', clean).split())


def is_address_query(query):
    """A standalone ZIP or CEP remains a place query. A street with a house number is an address."""
    q = re.sub(r'^\s*cep\b[:\s-]*', '', query or '', flags=re.I)
    if _STANDALONE_POSTCODE.fullmatch(q):
        return False
    if _LEADING_NUM_ADDR.match(q) and not _LEADING_CEP.match(q):
        return True
    cleaned = re.sub(r'(?:[\s,;-]+)\d{5}-?\d{3}\s*$', '', _strip_accents(q))
    return bool(_BR_NUM_ADDR.match(cleaned))


def street_forms(street):
    words = street.split()
    forms = [street, ' '.join(TO_DIGITS.get(word, word) for word in words),
             ' '.join(TO_WORDS.get(word, word) for word in words),
             ' '.join(PT_TO_DIGITS.get(word, word) for word in words),
             ' '.join(PT_TO_WORDS.get(word, word) for word in words)]
    forms += [re.sub(r'\b(\d+)(st|nd|rd|th)\b', r'\1', form) for form in forms[:]]
    for form in forms[:]:
        fw = form.split()
        swapped = ['av' if w == 'ave' else 'ave' if w == 'av' else w for w in fw]
        if swapped != fw:
            forms.append(' '.join(swapped))
    if words[0] not in ('n', 's', 'e', 'w', 'ne', 'nw', 'se', 'sw', 'r', 'av', 'ave', 'tv', 'al', 'pc', 'rod', 'estr'):
        forms += [f'{direction} {form}' for form in forms[:] for direction in ('n', 's', 'e', 'w')]
    return list(dict.fromkeys(forms))


def _pop_state(tokens):
    state = ''
    for count in (4, 3, 2, 1):
        if len(tokens) <= count:
            continue
        name = ' '.join(tokens[-count:])
        code = STATES.get(name) or (name.upper() if count == 1 and name.upper() in STATE_CODES else '')
        if code:
            state = code
            tokens = tokens[:-count]
            break
    return tokens, state


def _parts(query):
    raw = re.sub(r'^\s*cep\b[:\s-]*', '', query.strip(), flags=re.I).strip()
    postcode = ''
    m_cep = re.search(r'(?:[\s,;-]+)(\d{5})-?(\d{3})\s*$', raw)
    if m_cep:
        postcode = m_cep.group(1) + m_cep.group(2)
        raw = raw[:m_cep.start()].strip()

    if _LEADING_NUM_ADDR.match(raw) and not _LEADING_CEP.match(raw):
        number, remainder = raw.split(None, 1)
        number = number.upper()
        tokens = re.sub(r'[^a-z0-9 ]+', ' ', _strip_accents(remainder).lower()).split()
        if not postcode and tokens and re.fullmatch(r'\d{5}|\d{8}', tokens[-1]):
            postcode = tokens.pop()
        tokens, state = _pop_state(tokens)
        return number, tokens, state, postcode

    tokens = re.sub(r'[^a-z0-9 ]+', ' ', _strip_accents(raw).lower()).split()
    if not postcode and tokens and re.fullmatch(r'\d{5}|\d{8}', tokens[-1]):
        postcode = tokens.pop()
    num_idx = max((i for i, tok in enumerate(tokens) if i > 0 and _HOUSE_NUM_TOKEN.fullmatch(tok)), default=-1)
    if num_idx < 0:
        return '', [], '', postcode
    number = tokens[num_idx].upper()
    street_tokens = tokens[:num_idx]
    while street_tokens and street_tokens[-1] in ('n', 'no', 'nr', 'num', 'numero'):
        street_tokens.pop()
    after_tokens, state = _pop_state(tokens[num_idx + 1:])
    if not state and after_tokens:
        # Handle queries like "Rua Augusta, 1500, São Paulo" where city matches a state name and no UF was given.
        name = ' '.join(after_tokens)
        if name in BR_STATES:
            state = BR_STATES[name]
            after_tokens = []
    return number, street_tokens + after_tokens, state, postcode


def find_addresses(query, geo_directory, limit=8, near=None):
    """Return exact house-number matches from installed indexes, never a guessed house."""
    if not is_address_query(query):
        return []
    number, words, state, postcode = _parts(query)
    if not number or not words:
        return []
    geo_directory = Path(geo_directory)
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
                conn = sqlite3.connect(ro_uri(path), uri=True)
                conn.create_function('fold_txt', 1, lambda v: _strip_accents(v or '').lower(), deterministic=True)
                connections.append(conn)
            except sqlite3.Error:
                continue
        for count in range(len(words), 0, -1):
            street = normalize(' '.join(words[:count]))
            if not street or all(word in set(WORDS.values()) for word in street.split()):
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
                    if len(postcode) == 8:
                        conditions.append("replace(zip, '-', '') IN (?, ?)")
                        parameters.extend([postcode, postcode[:5]])
                    else:
                        conditions.append("replace(zip, '-', '') LIKE ?")
                        parameters.append(postcode + '%')
                if city:
                    conditions.append('fold_txt(city) LIKE ?')
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
                    z_clean = re.sub(r'\D', '', zip_code or '')
                    z_fmt = f'{z_clean[:5]}-{z_clean[5:]}' if len(z_clean) == 8 else zip_code
                    display_name = f'{name}, {num}' if state_code in BR_STATE_CODES else f'{num} {name}'
                    results.append({
                        'name': display_name, 'kind': 'Street address',
                        'detail': ', '.join(part for part in (city_name, state_code, z_fmt) if part),
                        'lat': lat, 'lon': lon, 'source': 'Overture Maps', 'onMap': True,
                    })
                    if len(results) == limit:
                        break
                return results
        return []
    finally:
        for connection in connections:
            connection.close()
