"""Read offline Puerto Rico land parcels. Property identifiers remain strings, including their leading zeros."""
import json
import re
from collections import defaultdict

from engine import pr_rural
from engine.pr_addresses import fold

PREFIX = re.compile(r'^(?:(?:n(?:umero|um|o)\.?\s*(?:de\s+)?)?(?:catastro|crim|parcel(?:a)?(?:\s+(?:id|number))?)\s*[:#]?\s*)')
GROUPED = re.compile(r'([0-9]{3})-([0-9]{3})-([0-9]{3})-([0-9]{2})(?:-([0-9]{3}|0{1,2}))?')
PAGE = 30


def number(text):
    value = PREFIX.sub('', pr_rural.plain(text).strip())
    if re.fullmatch(r'[0-9]{11}(?:[0-9]{3})?', value):
        return value
    parts = GROUPED.fullmatch(value)
    if parts:
        base = ''.join(parts.groups()[:4])
        return base + (parts[5].zfill(3) if parts[5] else '')
    return ''


def display(key):
    return '-'.join(part for part in (key[:3], key[3:6], key[6:9], key[9:11], key[11:]) if part)


def installed(db):
    return bool(db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='pr_parcel'").fetchone())


def outline(db, base):
    rows = db.execute('SELECT barrio,municipio,lat,lon,rings FROM pr_parcel WHERE base=? ORDER BY area DESC,id', (base,))
    first = next(rows, None)
    if first is None:
        return None
    barrio, town, lat, lon, rings = first
    parts = json.loads(rings)
    for row in rows:
        parts.extend(json.loads(row[4]))
    return {'name': display(base), 'parcelNumber': display(base), 'kind': 'CRIM parcel', 'lat': lat, 'lon': lon,
            'detail': ', '.join(part for part in ('Bo. ' + barrio if barrio else '', town, 'PR') if part),
            'source': 'CRIM / Junta de Planificación', 'rings': parts, 'onMap': True}


def by_number(db, key):
    if len(key) == 14 and key[11:] != '000':
        if not db.execute('SELECT 1 FROM pr_account WHERE number=?', (key,)).fetchone():
            return []
    item = outline(db, key[:11])
    if item is None:
        return []
    if len(key) == 14:
        item['name'] = display(key)
        if key[11:] != '000':
            item['detail'] += ' · Recorded account on this land parcel.'
    return [item]


def structured_records(db, address):
    # Filter qualifiers on one source record; two permits on the same parcel cannot corroborate each other.
    sql = """SELECT DISTINCT a.base,a.meters,a.lot,a.sector,a.interior,a.access,a.source,p.barrio,p.municipio
             FROM pr_parcel_address a JOIN pr_parcel p ON p.base=a.base
             WHERE a.route=? AND (a.meters=? OR (a.meters IS NULL AND ?) OR ? IS NULL)
               AND (?='' OR a.lot=?) AND (?='' OR a.sector=?) AND (?=0 OR a.interior=1)
               AND (?='' OR a.access=?) AND (?='' OR COALESCE(NULLIF(a.postal,''),p.zip)=?)
               AND (?='' OR instr(' ' || a.landmark || ' ', ' ' || ? || ' ')>0)"""
    args = (address.route, address.meters, bool(address.locality or address.lot or address.sector), address.meters,
            address.lot, address.lot, address.sector, address.sector, address.interior,
            address.access, address.access, address.postal, address.postal, address.landmark, address.landmark)
    matches = defaultdict(list)
    for base, meters, lot, sector, interior, access, source, barrio, town in db.execute(sql, args):
        if pr_rural.matches_area(address.locality, barrio, town):
            matches[base].append((meters, lot, sector, interior, access, source))
    def best(record):
        meters, lot, sector, inside, access, source = record
        return (meters is None, source != 'CRIM', -(bool(lot) + bool(sector) + bool(inside) + bool(access)),
                source, meters or 0, lot, sector, inside, access)
    return {base: min(rows, key=best) for base, rows in matches.items()}


def candidates(db, address, offset=0, limit=PAGE, wording=None):
    wording = wording or {}
    records = structured_records(db, address) if address else {}
    ordered = sorted(wording) + sorted(records.keys() - wording.keys(), key=lambda base: (records[base][0] is None, base))
    result = []
    for base in ordered[offset:offset + limit]:
        item = outline(db, base)
        if base in wording:
            source, text = wording[base]
            item.update(name=text, kind='Possible parcel', parcelCount=len(ordered),
                        detail=item['detail'] + ' · ' + source)
            result.append(item)
            continue
        meters, lot, sector, inside, access, source = records[base]
        road = f'PR-{address.route}' + (f' km {meters / 1000:g}' if meters is not None else '')
        qualifiers = [part for part in (f'Solar {lot.upper()}' if lot else '',
                                        f'Sector {sector}' if sector else '',
                                        ('Interior ' + access).rstrip() if inside else '') if part]
        name = f'{qualifiers[0]} · {road}' if qualifiers else road
        detail = [', '.join(qualifiers[1:]), item['detail'], 'km unrecorded' if meters is None else '', source]
        item.update(name=name, kind='Possible parcel', parcelCount=len(ordered),
                    detail=' · '.join(part for part in detail if part))
        result.append(item)
    return result
