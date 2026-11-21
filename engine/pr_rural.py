"""Read a Puerto Rico route and kilometer address without depending on component order."""
import functools
import json
import re
import unicodedata
from dataclasses import dataclass

from engine.pr_addresses import fold
from engine import paths

# Units may be joined to a number (e.g. 154KM2HM5). A letter on either side of
# an abbreviation belongs to a word, not to a second address component.
KM = re.compile(r'(?<![a-z])(?:kilometros?|kilometers?|kilometres?|kms?|k\s*\.\s*m)\.?\s*#?\s*(\d{1,3}(?:[.,]\d{1,3})?)(?![\d.,]\d|\d)')
HM = re.compile(r'(?<![a-z])(?:hectometros?|hectometers?|h\s*\.?\s*m)\.?\s*(\d)(?!\d)')
ROAD = re.compile(r'(?<![a-z0-9])(?:(?:carreteras?|carret|carr?|crta|ctra|crr|ruta|rta|route|rte|ramal|state (?:road|highway)|road|rd|highway|hwy)\.?\s*'
                  r'(?:estatal\s+)?(?:p\.?\s*r\.?\s*)?|p\.?\s*r\.?\s*)[-#\s]*(\d{1,4})(?![a-z0-9])')
POSTAL = re.compile(r'(?<!\d)(\d{5})(?:-\d{4})?(?!\d)')
LOT_LABEL = r'\b(?:solar|lote|lot)\b'
LOT = re.compile(LOT_LABEL + r'\.?\s*(?:n[uú]m(?:ero)?\.?\s*)?#?\s*'
                 r'([a-z]{0,3}-?\d+[a-z]?(?:[-/][a-z0-9]+)*|[a-z]+)\b(?![-/]\w)')
INSIDE = re.compile(r'\b(?:int|interior)\b')
# Everything after "interior" up to another address component is a required access detail.
ACCESS = re.compile(r'\b(?:int|interior)\b\.?\s*#?\s*([^,;\n]*?)(?=[,;\n]|$|'
                    r'\b(?:sector|sect|sec|comunidad|barrio|bo|municipio|solar|lote|lot|km|hm|carr|carretera|pr)\b)')


@dataclass(frozen=True)
class RuralAddress:
    route: int
    meters: int | None
    locality: str
    postal: str
    interior: bool
    sector: str
    landmark: str
    lot: str = ''
    access: str = ''


def plain(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower()) if not unicodedata.combining(c))


@functools.lru_cache(maxsize=1)
def language():
    return json.loads((paths.APP / 'web' / 'pr-rural-language.json').read_text(encoding='utf-8'))


@functools.lru_cache(maxsize=1)
def lot_words():
    return {word: str(i) for lang in ('en', 'es') for i, word in enumerate(language()[lang]['small'])}


def lot_key(value):
    # A-12 and A12 are two written forms of the same lot label. Preserve significant digits.
    key = re.sub(r'[\s-]', '', plain(value))
    return lot_words().get(key, key) if key.isalpha() and len(key) > 1 else key


def qualifiers(text):
    lots, interiors = list(LOT.finditer(text)), list(ACCESS.finditer(text))
    if len(lots) != len(re.findall(LOT_LABEL, text)) or len(lots) > 1 or len(interiors) > 1:
        return None
    lot = lot_key(lots[0][1].strip()) if lots else ''
    if len(lot) > 1 and lot.isalpha():
        return None
    return lot, fold(interiors[0][1].strip()) if interiors else ''


def looks_rural(query):
    """Keep incomplete and conversational kilometer directions out of the fuzzy place finder."""
    words = plain(query)
    unit = re.search(r'(?<![a-z])(?:k\.?\s*m\.?s?|kilomet(?:ros?|res?|ers?))(?=\W|\d|$)', words)
    return bool((unit and re.search(r'\d|\b(?:bo|barrio|carr|carretera|ruta|road|route|por la)\b', words))
                or re.search(r'\d[.,]\d+\s+(?:de la\s+)?(?:carr(?:etera)?|pr[- ])', words)
                or (ROAD.search(words) and (len(ROAD.findall(words)) > 1 or re.search(r'\b(?:casa|solar|lote|salida|exit)\b', words)))
                or re.search(r'\bhc\s*\d+\s+box\b', words)
                or (re.search(r'\b(?:barrio|bo)\b', words) and re.search(r'\b(?:punto|con)\b', words)
                    and re.search(r'\b(?:la|carr|carretera|pr)\s*[-.]?\s*\d+', words)))


def parcel_direction(query):
    raw = plain(query)
    # A street address can begin with a house number followed by a second, numbered road.
    house = re.match(r'^\s*#?(?:[a-z]{1,3}-?)?\d[\w/-]*\s+', raw)
    if house and ROAD.match(raw, house.end()):
        return False
    route = ROAD.search(raw) or re.search(r'\b(?:por la|carretera|ruta|route)\s+[a-z]+\b', raw)
    return bool(route and re.search(r'\b(?:bo|barrio|municipio|sector|sect|sec|int|interior|solar|lote|lot)\b', raw))


def parse(query, *, parcel=False):
    text = plain(query)
    if re.search(r'\b(?:casa|apto|apt|apartamento|box)\s*#?\s*\d', text):
        return None
    # Deal with fields independently of their position. Commas keep neighboring locality words separate.
    text = re.sub(r'\bkm\.?\s*hm\.?(?=\s*#?\s*\d)', 'km ', text)
    # An interior flag immediately before a ZIP does not name an access road.
    text = POSTAL.sub(lambda m: ', ' + m[0] + ',', text)
    details = qualifiers(text)
    if details is None:
        return None
    lot, access = details
    interior = bool(INSIDE.search(text))
    text = ACCESS.sub(',', LOT.sub(',', text))
    # HRSA site addresses also use "0.6 Carr 119" and "149 State Road".
    # A whole number before a highway can be a house number.
    text = re.sub(r'^\s*(\d{1,3}[.,]\d{1,3})(?=\s+(?:carr(?:etera)?\.?|pr[- ])\s*[-#]?\s*\d)', r'km \1', text)
    text = re.sub(r'\b(\d{1,4})\s+(?:state road|rural street)\b', r'pr-\1', text)
    text = re.sub(r'(?:^|,\s*)([^,;\d]+?)\s+sector(?=\s*,|$)', r', sector \1', text)
    hint = re.search(r'\b(?:esq(?:uina)?\.?\s+(?:carr(?:etera)?|pr)[.\s#-]*\d{1,4}|parque industrial)\b'
                     r'|(?:^|(?<=,))\s*[^,;\d]*?\bshopping cent(?:er|re)\b', text)
    named = ''
    if hint:
        named = fold(hint[0])
        text = text[:hint.start()] + ',' + text[hint.end():]
    # Some directories print the letter O for zero in a tagged numeric field.
    text = re.sub(r'\b(km|hm)\.?\s+o\b', r'\1 0', text)
    markers = list(KM.finditer(text))
    if len(markers) > 1 or not markers and not (parcel and parcel_direction(query) and ROAD.search(text) and
            (lot or interior or re.search(r'\b(?:bo|barrio|sector|sect|sec|municipio)\b', text)) and
            not re.search(r'\b(?:km|hm|kilometros?|kilometers?)\b', text)):
        return None
    meters, fraction = None, ''
    if markers:
        marker = markers[0]
        whole, _, fraction = marker[1].replace(',', '.').partition('.')
        meters = int(whole) * 1000 + int(fraction.ljust(3, '0'))
        text = text[:marker.start()] + ',' + text[marker.end():]
    hectos = list(HM.finditer(text))
    if hectos:
        if len(hectos) != 1 or fraction or meters is None:
            return None
        meters += int(hectos[0][1]) * 100
        text = HM.sub(',', text)
    if re.search(r'\b(?:hm|hectometros?)\b', text):
        return None
    postal = POSTAL.findall(text)
    if len(postal) > 1:
        return None
    text = POSTAL.sub(' ', text)
    routes = list(ROAD.finditer(text))
    if not routes:
        # Some physical address fields start with a bare route number.
        routes = list(re.finditer(r'(?<![a-z0-9])(\d{1,4})(?![a-z0-9])', text))
    if len(routes) != 1:
        return None
    route = routes[0]
    text = text[:route.start()] + ',' + text[route.end():]
    text = re.sub(r'\b(?:int|interior|puerto rico|pr|blvd|ward)\b', ' ', text)
    text = re.sub(r'\bb[º°]|\b(?:bo|barr|brrio)\b\.?', ' barrio ', text)
    text = re.sub(r'\b(?:mun|mpio|municipality)\.?\b', 'municipio', text)
    landmark = re.search(r'\b(?:frente a|al lado de|detras de|junto a|cerca de)\s+([^,;\n]+?)(?=[,;\n]|\b(?:barrio|municipio|sector)\b|$)', text)
    if landmark:
        text = text[:landmark.start()] + ' ' + text[landmark.end():]
    sector = re.search(r'\b(?:sector|sect|sec|comunidad|com)\.?\s+([^,;\n]+?)(?=[,;\n]|\b(?:barrio|municipio)\b|$)', text)
    if sector:
        text = text[:sector.start()] + ' ' + text[sector.end():]
    return RuralAddress(int(route[1]), meters, fold(text), postal[0] if postal else '', interior,
                        fold(sector[1]) if sector else '', ' '.join(x for x in (named, fold(landmark[0]) if landmark else '') if x),
                        lot, access)


def matches_area(locality, barrio, municipality):
    if not locality:
        return True
    barrios = {fold(barrio)}
    if barrio.endswith(' barrio-pueblo'):
        barrios.update(('pueblo', fold(barrio.removesuffix(' barrio-pueblo')) + ' pueblo'))
    town = fold(municipality)
    b_forms = ['', *(form for b in barrios for form in (b, 'barrio ' + b))]
    m_forms = ['', town, 'municipio ' + town]
    if any(locality in (b + ' de ' + town, b + ' en ' + town, b + ' del municipio de ' + town)
           for b in b_forms if b):
        return True
    return any(locality == ' '.join(w for w in pair if w)
               for b in b_forms for m in m_forms for pair in ((b, m), (m, b)))


def lookup(db, address, limit):
    if address.meters is None or address.lot or address.access:
        return []  # A lot or named interior access needs evidence on a parcel record.
    # Each segment lies on one measured path. No extrapolation or guessing across gaps.
    rows = db.execute("""SELECT low,high,lat0,lon0,lat1,lon1,barrio,municipio,zip
                         FROM pr_road r JOIN pr_area a ON a.id=r.area
                         WHERE route=? AND bucket=? AND low<=? AND high>=? ORDER BY r.rowid""",
                      (address.route, address.meters // 1000, address.meters, address.meters))
    results = []
    km = f'{address.meters / 1000:.3f}'.rstrip('0').rstrip('.')
    for low, high, y0, x0, y1, x1, barrio, town, zip_code in rows:
        if (address.postal and address.postal != zip_code) or not matches_area(address.locality, barrio, town):
            continue
        t = (address.meters - low) / (high - low)
        lat, lon = y0 + t * (y1 - y0), x0 + t * (x1 - x0)
        # Adjacent segments and the other carriageway can represent the same location.
        if any(abs(r['lat'] - lat) < 0.0005 and abs(r['lon'] - lon) < 0.0005 for r in results):
            continue
        detail = ', '.join(v for v in ('Bo. ' + barrio if barrio else '', town, 'PR') if v)
        detail += ' · Approximate position on the road.'
        if address.interior:
            detail += ' Interior access is unverified.'
        if address.sector:
            detail += ' Sector directions are unverified.'
        if address.landmark:
            detail += ' Landmark directions are unverified.'
        results.append({'name': f'PR-{address.route} km {km}', 'kind': 'Road kilometer', 'detail': detail,
                        'lat': round(lat, 6), 'lon': round(lon, 6), 'source': 'FHWA HPMS', 'onMap': True})
        if len(results) >= limit:
            return results
    sites = db.execute("""SELECT name,street,lat,lon,barrio,municipio,postal,reported_city FROM pr_school s
                          JOIN pr_area a ON a.id=s.area WHERE route=? AND meters=? ORDER BY name,s.rowid""",
                       (address.route, address.meters))
    for name, street, lat, lon, barrio, town, postal, city in sites:
        if address.postal and address.postal != postal:
            continue
        recorded = parse(street)
        # School directions can use a local barrio name or a mailing city different from the
        # polygon labels. Accept the school's own description only for that named school.
        if not (matches_area(address.locality, barrio, town) or matches_area(address.locality, barrio, city)
                or (recorded and matches_area(address.locality, recorded.locality.removeprefix('barrio '), city))):
            continue
        if address.sector and (' ' + address.sector + ' ') not in (' ' + fold(street) + ' '):
            continue
        if address.interior and not re.search(r'\b(?:interior|int)\b', fold(street)):
            continue
        if address.landmark and (' ' + address.landmark + ' ') not in (' ' + fold(street) + ' '):
            continue
        results.append({'name': name, 'kind': 'Public school', 'detail': street + ', ' + town + ', PR',
                        'lat': lat, 'lon': lon, 'source': 'NCES EDGE', 'onMap': True})
        if len(results) >= limit:
            break
    return results
