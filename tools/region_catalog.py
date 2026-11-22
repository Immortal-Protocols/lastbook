"""The catalogue of European regions Lastbook can build a detailed map for: tools/regions/europe.json.

  python3 tools/region_catalog.py [--source osmfr|geofabrik] [--out tools/regions/europe.json]

One entry per region: a country's first-level subdivision where an extract of it is published, else the whole country.
Each names the OpenStreetMap extract to build from (.osm.pbf) and its boundary (.poly), and gives the region's box, so
tools/build_europe_region.py needs nothing else to find its sources:

  {"id": "ES-CT", "country": "ES", "country_name": "Spain", "name": "Catalunya", "pbf": "https://...", "poly": "https://...",
   "bbox": [W, S, E, N], "area_km2": 32108}

Ids are ISO 3166-2 codes (ES-CT, CH-ZH, SE-AB) where the region is one of the country's current first-level
subdivisions, as docs/REGIONS*.md propose; the hyphen keeps them apart from US state codes (CT, GA, MD). A region that
is not (France's pre-2016 regions, Norway's pre-2020 counties, Turkey's geographic regions, Wallonia's two parts in OSM
France's extracts) keeps its country code and a slug of its name, e.g. FR-alsace. A whole country is its ISO 3166-1
code. Ids do not depend on the source, so a map keeps its id if its source changes. Sources: OSM France's extracts (download.openstreetmap.fr, region by region for most
countries) and Geofabrik's (download.geofabrik.de, whose index lists every extract with its ISO code; used where it is
reachable, e.g. on GitHub Actions). Both publish OpenStreetMap data under the ODbL.
"""
import argparse, json, math, re, sys, unicodedata, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
OSMFR = 'https://download.openstreetmap.fr/extracts/europe/'
OSMFR_POLY = 'https://download.openstreetmap.fr/polygons/europe/'
GEOFABRIK_INDEX = 'https://download.geofabrik.de/index-v1-nogeom.json'

COUNTRIES = {   # OSM France folder -> (ISO 3166-1, English name)
    'albania': ('AL', 'Albania'), 'andorra': ('AD', 'Andorra'), 'austria': ('AT', 'Austria'), 'belarus': ('BY', 'Belarus'),
    'belgium': ('BE', 'Belgium'), 'bosnia-herzegovina': ('BA', 'Bosnia and Herzegovina'), 'bulgaria': ('BG', 'Bulgaria'),
    'croatia': ('HR', 'Croatia'), 'cyprus': ('CY', 'Cyprus'), 'czech_republic': ('CZ', 'Czech Republic'),
    'denmark': ('DK', 'Denmark'), 'estonia': ('EE', 'Estonia'), 'faroe_islands': ('FO', 'Faroe Islands'),
    'finland': ('FI', 'Finland'), 'france': ('FR', 'France'), 'germany': ('DE', 'Germany'), 'gibraltar': ('GI', 'Gibraltar'),
    'greece': ('GR', 'Greece'), 'guernesey': ('GG', 'Guernsey'), 'hungary': ('HU', 'Hungary'), 'iceland': ('IS', 'Iceland'),
    'ireland': ('IE', 'Ireland'), 'isle_of_man': ('IM', 'Isle of Man'), 'italy': ('IT', 'Italy'), 'jersey': ('JE', 'Jersey'),
    'kosovo': ('XK', 'Kosovo'), 'latvia': ('LV', 'Latvia'), 'liechtenstein': ('LI', 'Liechtenstein'),
    'lithuania': ('LT', 'Lithuania'), 'luxembourg': ('LU', 'Luxembourg'), 'malta': ('MT', 'Malta'), 'moldova': ('MD', 'Moldova'),
    'monaco': ('MC', 'Monaco'), 'montenegro': ('ME', 'Montenegro'), 'netherlands': ('NL', 'Netherlands'),
    'north-macedonia': ('MK', 'North Macedonia'), 'macedonia': ('MK', 'North Macedonia'), 'norway': ('NO', 'Norway'),
    'poland': ('PL', 'Poland'), 'portugal': ('PT', 'Portugal'), 'romania': ('RO', 'Romania'), 'san_marino': ('SM', 'San Marino'),
    'serbia': ('RS', 'Serbia'), 'slovakia': ('SK', 'Slovakia'), 'slovenia': ('SI', 'Slovenia'), 'spain': ('ES', 'Spain'),
    'sweden': ('SE', 'Sweden'), 'switzerland': ('CH', 'Switzerland'), 'turkey': ('TR', 'Turkey'), 'ukraine': ('UA', 'Ukraine'),
    'united_kingdom': ('GB', 'United Kingdom'), 'vatican_city': ('VA', 'Vatican City'),
}
SMALL = ('de', 'del', 'la', 'las', 'los', 'y', 'i', 'el', 'and', 'of', 'the', 'du', 'des', 'et', 'le', 'di', 'e')
NAMES = {   # region names a slug cannot spell
    'ES-catalunya': 'Catalunya / Catalonia', 'ES-comunitat_valenciana': 'Comunitat Valenciana', 'ES-euskadi': 'Euskadi / País Vasco',
    'ES-andalucia': 'Andalucía', 'ES-aragon': 'Aragón', 'ES-castilla_y_leon': 'Castilla y León', 'ES-region_de_murcia': 'Región de Murcia',
    'ES-illes_balears': 'Illes Balears', 'ES-canarias': 'Canarias / Canary Islands', 'ES-castilla_la_mancha': 'Castilla-La Mancha', 'ES-comunidad_de_madrid': 'Comunidad de Madrid', 'ES-comunidad_foral_de_navarra': 'Navarra',
}


# The ISO 3166-2 code of each extract that is a current first-level subdivision, by its slug id. Checked against
# pycountry's copy of ISO 3166-2 (each code exists, none repeats) on 22 November 2026; Geofabrik's index gives the
# code itself and is used first when it does.
ISO = {
    'AT-burgenland': 'AT-1', 'AT-karnten': 'AT-2', 'AT-niederosterreich': 'AT-3', 'AT-oberosterreich': 'AT-4',
    'AT-salzburg': 'AT-5', 'AT-steiermark': 'AT-6', 'AT-tirol': 'AT-7', 'AT-vorarlberg': 'AT-8', 'AT-wien': 'AT-9',
    'BE-brussels_capital_region': 'BE-BRU', 'BE-flanders': 'BE-VLG', 'CH-aargau': 'CH-AG',
    'CH-appenzell_ausserrhoden': 'CH-AR', 'CH-appenzell_innerrhoden': 'CH-AI', 'CH-basel_landschaft': 'CH-BL',
    'CH-basel_stadt': 'CH-BS', 'CH-bern': 'CH-BE', 'CH-fribourg': 'CH-FR', 'CH-geneva': 'CH-GE', 'CH-glarus': 'CH-GL',
    'CH-grisons': 'CH-GR', 'CH-jura': 'CH-JU', 'CH-lucerne': 'CH-LU', 'CH-neuchatel': 'CH-NE', 'CH-nidwalden': 'CH-NW',
    'CH-obwalden': 'CH-OW', 'CH-saint_gallen': 'CH-SG', 'CH-schaffhausen': 'CH-SH', 'CH-schwyz': 'CH-SZ',
    'CH-solothurn': 'CH-SO', 'CH-thurgau': 'CH-TG', 'CH-ticino': 'CH-TI', 'CH-uri': 'CH-UR', 'CH-valais': 'CH-VS',
    'CH-vaud': 'CH-VD', 'CH-zug': 'CH-ZG', 'CH-zurich': 'CH-ZH', 'CZ-jihocesky': 'CZ-31', 'CZ-jihomoravsky': 'CZ-64',
    'CZ-karlovarsky': 'CZ-41', 'CZ-kralovehradecky': 'CZ-52', 'CZ-liberecky': 'CZ-51', 'CZ-moravskoslezsky': 'CZ-80',
    'CZ-olomoucky': 'CZ-71', 'CZ-pardubicky': 'CZ-53', 'CZ-plzensky': 'CZ-32', 'CZ-praha': 'CZ-10',
    'CZ-stredocesky': 'CZ-20', 'CZ-ustecky': 'CZ-42', 'CZ-vysocina': 'CZ-63', 'CZ-zlinsky': 'CZ-72',
    'DK-hovedstaden': 'DK-84', 'DK-midtjylland': 'DK-82', 'DK-nordjylland': 'DK-81', 'DK-sjaelland': 'DK-85',
    'DK-syddanmark': 'DK-83', 'ES-andalucia': 'ES-AN', 'ES-aragon': 'ES-AR', 'ES-asturias': 'ES-AS',
    'ES-canarias': 'ES-CN', 'ES-cantabria': 'ES-CB', 'ES-castilla_la_mancha': 'ES-CM', 'ES-castilla_y_leon': 'ES-CL',
    'ES-catalunya': 'ES-CT', 'ES-ceuta': 'ES-CE', 'ES-comunidad_de_madrid': 'ES-MD',
    'ES-comunidad_foral_de_navarra': 'ES-NC', 'ES-comunitat_valenciana': 'ES-VC', 'ES-euskadi': 'ES-PV',
    'ES-extremadura': 'ES-EX', 'ES-galicia': 'ES-GA', 'ES-illes_balears': 'ES-IB', 'ES-la_rioja': 'ES-RI',
    'ES-melilla': 'ES-ML', 'ES-region_de_murcia': 'ES-MC', 'FI-aland': 'FI-01', 'FI-central_finland': 'FI-08',
    'FI-central_ostrobothnia': 'FI-07', 'FI-kainuu': 'FI-05', 'FI-kanta_hame': 'FI-06', 'FI-kymenlaakso': 'FI-09',
    'FI-lapland': 'FI-10', 'FI-north_karelia': 'FI-13', 'FI-north_ostrobothnia': 'FI-14', 'FI-north_savo': 'FI-15',
    'FI-ostrobothnia': 'FI-12', 'FI-paijat_hame': 'FI-16', 'FI-pirkanmaa': 'FI-11', 'FI-satakunta': 'FI-17',
    'FI-south_karelia': 'FI-02', 'FI-south_ostrobothnia': 'FI-03', 'FI-south_savo': 'FI-04',
    'FI-southwest_finland': 'FI-19', 'FI-uusimaa': 'FI-18', 'GB-england': 'GB-ENG', 'GB-northern_ireland': 'GB-NIR',
    'IT-abruzzo': 'IT-65', 'IT-basilicata': 'IT-77', 'IT-calabria': 'IT-78', 'IT-campania': 'IT-72',
    'IT-emilia_romagna': 'IT-45', 'IT-friuli_venezia_giulia': 'IT-36', 'IT-lazio': 'IT-62', 'IT-liguria': 'IT-42',
    'IT-lombardia': 'IT-25', 'IT-marche': 'IT-57', 'IT-molise': 'IT-67', 'IT-piemonte': 'IT-21', 'IT-puglia': 'IT-75',
    'IT-sardegna': 'IT-88', 'IT-sicilia': 'IT-82', 'IT-toscana': 'IT-52', 'IT-trentino_alto_adige': 'IT-32',
    'IT-umbria': 'IT-55', 'IT-valle_aosta': 'IT-23', 'IT-veneto': 'IT-34', 'NL-drenthe': 'NL-DR',
    'NL-flevoland': 'NL-FL', 'NL-friesland': 'NL-FR', 'NL-gelderland': 'NL-GE', 'NL-groningen': 'NL-GR',
    'NL-limburg': 'NL-LI', 'NL-noord_brabant': 'NL-NB', 'NL-noord_holland': 'NL-NH', 'NL-overijssel': 'NL-OV',
    'NL-utrecht': 'NL-UT', 'NL-zeeland': 'NL-ZE', 'NL-zuid_holland': 'NL-ZH', 'PL-dolnoslaskie': 'PL-02',
    'PL-kujawsko_pomorskie': 'PL-04', 'PL-lodzkie': 'PL-10', 'PL-lubelskie': 'PL-06', 'PL-lubuskie': 'PL-08',
    'PL-malopolskie': 'PL-12', 'PL-mazowieckie': 'PL-14', 'PL-opolskie': 'PL-16', 'PL-podkarpackie': 'PL-18',
    'PL-podlaskie': 'PL-20', 'PL-pomorskie': 'PL-22', 'PL-slaskie': 'PL-24', 'PL-swietokrzyskie': 'PL-26',
    'PL-warminsko_mazurskie': 'PL-28', 'PL-wielkopolskie': 'PL-30', 'PL-zachodniopomorskie': 'PL-32',
    'PT-aveiro': 'PT-01', 'PT-azores': 'PT-20', 'PT-beja': 'PT-02', 'PT-braga': 'PT-03', 'PT-braganca': 'PT-04',
    'PT-castelo_branco': 'PT-05', 'PT-coimbra': 'PT-06', 'PT-evora': 'PT-07', 'PT-faro': 'PT-08', 'PT-guarda': 'PT-09',
    'PT-leiria': 'PT-10', 'PT-lisbon': 'PT-11', 'PT-madeira': 'PT-30', 'PT-portalegre': 'PT-12', 'PT-porto': 'PT-13',
    'PT-santarem': 'PT-14', 'PT-setubal': 'PT-15', 'PT-viana_do_castelo': 'PT-16', 'PT-vila_real': 'PT-17',
    'PT-viseu': 'PT-18', 'SE-blekinge': 'SE-K', 'SE-dalarna': 'SE-W', 'SE-gavleborg': 'SE-X', 'SE-gotland': 'SE-I',
    'SE-halland': 'SE-N', 'SE-jamtland': 'SE-Z', 'SE-jonkoping': 'SE-F', 'SE-kalmar': 'SE-H', 'SE-kronoberg': 'SE-G',
    'SE-norrbotten': 'SE-BD', 'SE-orebro': 'SE-T', 'SE-ostergotland': 'SE-E', 'SE-skane': 'SE-M',
    'SE-sodermanland': 'SE-D', 'SE-stockholm': 'SE-AB', 'SE-uppsala': 'SE-C', 'SE-varmland': 'SE-S',
    'SE-vasterbotten': 'SE-AC', 'SE-vasternorrland': 'SE-Y', 'SE-vastmanland': 'SE-U', 'SE-vastra_gotaland': 'SE-O',
    'SK-banskobystricky': 'SK-BC', 'SK-bratislavsky': 'SK-BL', 'SK-kosicky': 'SK-KI', 'SK-nitriansky': 'SK-NI',
    'SK-presovsky': 'SK-PV', 'SK-trenciansky': 'SK-TC', 'SK-trnavsky': 'SK-TA', 'SK-zilinsky': 'SK-ZI',
    'UA-cherkasy_oblast': 'UA-71', 'UA-chernihiv_oblast': 'UA-74', 'UA-chernivtsi_oblast': 'UA-77',
    'UA-crimea': 'UA-43', 'UA-dnipropetrovsk_oblast': 'UA-12', 'UA-donetsk_oblast': 'UA-14',
    'UA-ivano_frankivsk_oblast': 'UA-26', 'UA-kharkiv_oblast': 'UA-63', 'UA-kherson_oblast': 'UA-65',
    'UA-khmelnytskyi_oblast': 'UA-68', 'UA-kiev': 'UA-30', 'UA-kiev_oblast': 'UA-32', 'UA-kirovohrad_oblast': 'UA-35',
    'UA-luhansk_oblast': 'UA-09', 'UA-lviv_oblast': 'UA-46', 'UA-mykolaiv_oblast': 'UA-48',
    'UA-odessa_oblast': 'UA-51', 'UA-poltava_oblast': 'UA-53', 'UA-rivne_oblast': 'UA-56', 'UA-sevastopol': 'UA-40',
    'UA-sumy_oblast': 'UA-59', 'UA-ternopil_oblast': 'UA-61', 'UA-vinnytsia_oblast': 'UA-05',
    'UA-volyn_oblast': 'UA-07', 'UA-zakarpattia_oblast': 'UA-21', 'UA-zaporizhia_oblast': 'UA-23',
    'UA-zhytomyr_oblast': 'UA-18',
}


def region_id(slug_id, iso2=''):
    if iso2 and re.fullmatch(r'[A-Z]{2}-[A-Z0-9]{1,3}', iso2):
        return iso2
    return ISO.get(slug_id, slug_id)


def slug(text):
    t = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '_', t).strip('_')


def title(s):
    words = s.replace('-', ' ').replace('_', ' ').split()
    return ' '.join(w if i and w in SMALL else w.capitalize() for i, w in enumerate(words))


def fetch(url, timeout=60):
    req = urllib.request.Request(url, headers={'User-Agent': 'lastbook-region-catalog'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def poly_box(text):
    """[W, S, E, N] and an approximate area (km2) of an Osmosis .poly file (outer rings, holes subtracted)."""
    xs, ys, area, ring, hole = [], [], 0.0, [], False
    lines = [l.strip() for l in text.splitlines()]
    for l in lines[1:]:
        if l == 'END':
            if ring:
                a = 0.0
                for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]):
                    a += math.radians(x1 - x0) * (2 + math.sin(math.radians(y0)) + math.sin(math.radians(y1)))
                area += (-1 if hole else 1) * abs(a) * 6371.0 ** 2 / 2
                ring = []
            continue
        if not l:
            continue
        if not re.match(r'^-?[\d.eE+-]+\s+-?[\d.eE+-]+$', l):
            hole = l.startswith('!')
            continue
        x, y = map(float, l.split())
        ring.append((x, y)); xs.append(x); ys.append(y)
    return [round(min(xs), 4), round(min(ys), 4), round(max(xs), 4), round(max(ys), 4)], int(area)


def listing(url):
    html = fetch(url).decode('utf-8', 'replace')
    return re.findall(r'<a href="([^"?/][^"?]*)">', html)


EXTRA_DIRS = {'africa/spain': ('ES', 'Spain')}     # the Canary Islands, Ceuta and Melilla are filed under Africa


def from_osmfr():
    out = []
    top = listing(OSMFR)
    dirs = [e.rstrip('/') for e in top if e.endswith('/') and e.rstrip('/') in COUNTRIES]
    single = [e[:-len('.osm.pbf')] for e in top if e.endswith('.osm.pbf') and not e.endswith('-latest.osm.pbf')]
    jobs = [('europe/' + d, *COUNTRIES[d], True) for d in dirs]
    jobs += [('europe/' + c, *COUNTRIES[c], False) for c in single if c in COUNTRIES and c not in dirs]
    jobs += [(d, cc, name, True) for d, (cc, name) in EXTRA_DIRS.items()]
    base = OSMFR.rsplit('europe/', 1)[0]
    pbase = OSMFR_POLY.rsplit('europe/', 1)[0]
    for path, cc, cname, has_dir in jobs:
        kids = []
        if has_dir:
            kids = [k[:-len('.osm.pbf')] for k in listing(base + path + '/') if k.endswith('.osm.pbf') and not k.endswith('-latest.osm.pbf')]
        if kids:
            targets = [(f'{cc}-{slug(k)}', title(k), f'{base}{path}/{k}.osm.pbf', f'{pbase}{path}/{k}.poly') for k in kids]
        else:
            targets = [(cc, cname, f'{base}{path}.osm.pbf', f'{pbase}{path}.poly')]
        for rid, name, pbf, poly in targets:
            try:
                bbox, area = poly_box(fetch(poly).decode('utf-8', 'replace'))
            except Exception as e:
                print(f'skip {rid}: no boundary ({type(e).__name__})', file=sys.stderr)
                continue
            out.append({'id': region_id(rid), 'country': cc, 'country_name': cname, 'name': NAMES.get(rid, name),
                        'pbf': pbf, 'poly': poly, 'bbox': bbox, 'area_km2': area, 'source': 'osmfr'})
            print(out[-1]['id'], out[-1]['name'], bbox, area, file=sys.stderr)
    return out


def from_geofabrik():
    idx = json.loads(fetch(GEOFABRIK_INDEX))
    feats = [f['properties'] for f in idx['features']]
    by_id = {p['id']: p for p in feats}
    europe = [p for p in feats if p.get('parent') == 'europe']
    out = []
    for c in europe:
        cc = (c.get('iso3166-1:alpha2') or [''])[0]
        if not cc:
            continue
        kids = [p for p in feats if p.get('parent') == c['id']]
        for p in kids or [c]:
            iso2 = (p.get('iso3166-2') or [''])[0] if kids else ''
            rid = (f'{cc}-{slug(p["name"])}' if kids else cc)
            urls = p.get('urls') or {}
            out.append({'id': region_id(rid, iso2), 'country': cc, 'country_name': c['name'], 'name': NAMES.get(rid, p['name']),
                        'pbf': urls.get('pbf'), 'poly': urls.get('pbf', '').replace('-latest.osm.pbf', '.poly'),
                        'bbox': None, 'area_km2': None, 'source': 'geofabrik'})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', choices=('osmfr', 'geofabrik'), default='osmfr')
    ap.add_argument('--out', default=str(HERE / 'regions' / 'europe.json'))
    a = ap.parse_args()
    regions = from_geofabrik() if a.source == 'geofabrik' else from_osmfr()
    regions.sort(key=lambda r: (r['country_name'], r['name']))
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps({'source': a.source, 'regions': regions}, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'{len(regions)} regions in {len({r["country"] for r in regions})} countries -> {a.out}')


if __name__ == '__main__':
    main()
