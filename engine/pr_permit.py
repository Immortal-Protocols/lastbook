"""Match complete public permit directions within their verified municipio."""
import functools
import json
import re

from engine import paths, pr_rural, pr_rural_model


@functools.lru_cache(maxsize=1)
def grammar():
    rules = json.loads((paths.APP / 'web' / 'pr-permit-language.json').read_text(encoding='utf-8'))
    def replacements(name):
        return [(re.compile(pattern), replacement) for pattern, replacement in rules[name]]
    return (re.compile(rules['prefix']), re.compile(rules['postal']), re.compile(rules['literal']),
            replacements('intro'), replacements('aliases'))


@functools.lru_cache(maxsize=128)
def town_field(town):
    # Only remove a delimited municipio or an explicit location phrase. Keep embedded barrio names.
    return re.compile(r'(?:^|[,;]\s*|\ben (?:el municipio de )?)(?:municipio de )?'
                      + re.escape(town) + r'(?=\s*(?:[,;.]|$))')


@functools.lru_cache(maxsize=1)
def numbers():
    return {pr_rural_model.spelled(n, 'es'): str(n) for n in range(10000)}


@functools.lru_cache(maxsize=1)
def spoken_pattern():
    words = set(' '.join(numbers()).split()) | {'punto'}
    token = '(?:' + '|'.join(sorted(words)) + r'|\d+)\b'
    return re.compile(r'\b(kilometros?|km|carretera|por la|solar|lote|parcela|calle|edificio) ('
                      + token + '(?: ' + token + '){0,14})')
MEASURE = re.compile(r'\|(km|road) (\d+)(?:[.,](\d+))?(?!\d)')
LABELS = {'km','road','barrio','sector','interior','solar','parcela','urbanizacion','comunidad','calle','camino','edificio'}


def numeral(phrase, grouped):
    if phrase.isdigit():
        return phrase
    if phrase in numbers():
        return numbers()[phrase]
    words = phrase.split()
    if words and all(len(numbers().get(w, 'xx')) == 1 for w in words):
        return ''.join(numbers()[w] for w in words)
    if grouped:
        forms = {numbers()[a] + numbers()[b] for i in range(1,len(words))
                 if (a := ' '.join(words[:i])) in numbers() and (b := ' '.join(words[i:])) in numbers()}
        if len(forms) == 1:
            return forms.pop()
    return None


def spoken_number(match):
    label = 'carretera' if match[1] == 'por la' else match[1]
    whole, dot, frac = match[2].partition(' punto ')
    n = numeral(whole, label == 'carretera')
    decimal = numeral(frac, False) if dot else ''
    if n is None or decimal is None or (dot and label not in ('km','kilometro','kilometros')):
        return match[0]
    return label + ' ' + n + ('.' + decimal if dot else '')


def plain(text):
    return ' '.join(pr_rural.plain(text).split()).strip(' ,;.')


def key(text, town, *, source=False):
    prefix, postal, literal, intro, aliases = grammar()
    raw = prefix.sub('', plain(text))
    postcodes = postal.findall(raw)
    if len(postcodes) > 1:
        return None
    raw = postal.sub(',', raw)
    raw, found = town_field(town).subn(',', raw, count=1)
    if not source and not found:
        return None
    raw = raw.strip(' ,;.')
    if not raw or '|' in raw:
        return None
    zip_code = postcodes[0].replace('-', '') if postcodes else ''
    literal_key = ('literal ' + raw, zip_code)
    if literal.search(raw):
        return literal_key
    for pattern, replacement in intro:
        raw = pattern.sub(replacement, raw)
    raw = spoken_pattern().sub(spoken_number, raw)
    for pattern, replacement in aliases:
        raw = pattern.sub(replacement, raw)
    def measure(m):
        frac = (m[3] or '').rstrip('0')
        return '|' + m[1] + ' ' + m[2] + ('.' + frac if frac else '') + '|'
    parts = [' '.join(s.split()) for s in re.split(r'[|,;]', MEASURE.sub(measure, raw)) if s.strip()]
    labels = [s.partition(' ')[0] for s in parts]
    if (labels.count('road') != 1 or labels.count('km') != 1 or len(set(labels)) != len(labels)
            or not set(labels) <= LABELS):
        return literal_key
    return ('parts ' + '|'.join(sorted(parts)), zip_code)


SCHEMA = """CREATE TABLE pr_permit_wording(town TEXT, signature TEXT, postal TEXT, base TEXT, source TEXT, wording TEXT,
            PRIMARY KEY(town,signature,postal,base,source,wording)) WITHOUT ROWID"""


def matches(db, query):
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name='pr_permit_wording'").fetchone():
        return {}
    text = plain(query)
    result = {}
    for name, in db.execute('SELECT name FROM municipios ORDER BY name'):
        town = plain(name)
        if town not in text:
            continue
        signature = key(text, town)
        if not signature:
            continue
        value, postal = signature
        rows = db.execute("""SELECT base,source,wording FROM pr_permit_wording
            WHERE town=? AND signature=? AND (?='' OR substr(postal,1,length(?))=?)
            ORDER BY base,source,wording""", (town,value,postal,postal,postal))
        for base, source, wording in rows:
            result.setdefault(base, (source, wording))
    return result
