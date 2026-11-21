"""Offline lookup for the Puerto Rico OpenStreetMap address sidecar."""
import math
import re
import unicodedata

# Only expand a street type in the leading position, e.g. Avenida del Camino.
STREET_TYPES = {
    'avenida': 'ave', 'avda': 'ave', 'av': 'ave', 'ave': 'ave',
    'calle': 'cll', 'cl': 'cll', 'cll': 'cll',
    'carretera': 'carr', 'ctra': 'carr', 'carr': 'carr',
    'camino': 'cam', 'cam': 'cam',
    'bulevar': 'blvd', 'boulevard': 'blvd', 'blvd': 'blvd',
}
NUMBER = re.compile(r'^\s*#?([a-z]{1,3}\(\d+\)-\d+|[a-z]{1,3}-?\d[\w-]*(?:\(\d+\))?'
                    r'|\d[\w/-]*)\s+(\S.*)$', re.I | re.S)
URB = re.compile(r'^(?:urb\.?|urbanizaci[oó]n)\s+(.+)$', re.I)
SOURCE = '© OpenStreetMap contributors'
PROFILE = 'pr-osm-v1'


def fold(text):
    letters = unicodedata.normalize('NFD', text.casefold())
    letters = ''.join(c for c in letters if not unicodedata.combining(c))
    return ' '.join(re.findall(r'[a-z0-9]+', letters))


def street_key(text):
    words = fold(text).split()
    if words:
        words[0] = STREET_TYPES.get(words[0], words[0])
    return ' '.join(words)


def components(query):
    """Keep the explicitly named urbanización separate from the street and locality."""
    address, urbanizations = [], []
    for part in re.split(r'[,\n]', unicodedata.normalize('NFC', query)):
        part = part.strip()
        if not part:
            continue
        urb = URB.fullmatch(part)
        if urb:
            urbanizations.append(fold(urb[1]))
        else:
            address.append(part)
    match = NUMBER.match(' '.join(address))
    if not match or len(urbanizations) > 1:
        return None
    # A compact lot number or highway code alone is ambiguous (B52 Museum, I-95 Rest Area).
    if re.fullmatch(r'(?:PR|US|I)-\d+|[a-z]{1,3}\d\w*', match[1], re.I) and not (
            urbanizations or address[0].startswith('#') or
            fold(match[2]).partition(' ')[0] in STREET_TYPES
            or re.search(r'\s(?:PR|Puerto Rico)(?:\s+\d{5}(?:-\d{4})?)?$', match[2], re.I)):
        return None
    return match[1], match[2], next(iter(urbanizations), '')


def lookup(db, parts, near, limit):
    number, text, urb = parts
    postcode = ''
    postal = re.search(r'(?:^|\s)(\d{5})(?:[-\s]\d{4})?\s*$', text)
    if postal:
        postcode = postal[1]
        text = text[:postal.start()]
    text = re.sub(r'\s+(?:PR|Puerto\s+Rico)\s*$', '', text, flags=re.I)
    key = street_key(text)
    if not key:
        return []
    # The number index bounds this query even when the caller omits a locality.
    sql = """SELECT DISTINCT num,street,city,zip,lat,lon,urbanization
             FROM addr WHERE num = ? COLLATE NOCASE
             AND ? IN (street_key, street_key || ' ' || city_key, street_key || ' ' || municipio_key)
             AND (? = '' OR zip = ?) AND (? = '' OR urb_key = ?)
             ORDER BY city, urbanization, street, lat, lon"""
    rows = list(db.execute(sql, (number, key, postcode, postcode, urb, urb)))
    if near:
        scale = math.cos(math.radians(near[0]))
        rows.sort(key=lambda r: (r[4] - near[0]) ** 2 + ((r[5] - near[1]) * scale) ** 2)
    return [{'name': f'{num} {street}', 'kind': 'Street address',
             'detail': ', '.join(p for p in (f'Urb. {urbanization}' if urbanization else '', city, 'PR', zip_code) if p),
             'lat': lat, 'lon': lon, 'source': SOURCE, 'onMap': True}
            for num, street, city, zip_code, lat, lon, urbanization in rows[:limit]]
