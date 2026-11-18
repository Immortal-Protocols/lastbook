"""Municipio selections shared by the connected Puerto Rico preparation tools."""
from engine.pr_addresses import fold

# Metro follows the nine municipios in Guaynabo's 2024 planning memorandum:
# https://jp.pr.gov/wp-content/uploads/2024/08/Memorial-Justificativo-sobre-Posible-Enmienda-Menor-PUT-PR-2015_PT-MAG_2024_VEDA.pdf
# The other presets follow the Tourism Company's published municipal lists:
# https://tourism.pr.gov/regions/ (west combines Porta del Sol Norte and Sur).
REGIONS = {
    'metro': 'Bayamón|Canóvanas|Carolina|Cataño|Guaynabo|San Juan|Toa Alta|Toa Baja|Trujillo Alto',
    'east': (
        'Canóvanas|Ceiba|Culebra|Fajardo|Humacao|Juncos|Las Piedras|Loíza|Luquillo|Maunabo|Naguabo|'
        'Río Grande|San Lorenzo|Vieques|Yabucoa'
    ),
    'west': (
        'Aguada|Aguadilla|Añasco|Isabela|Lares|Las Marías|Moca|Quebradillas|Rincón|San Sebastián|'
        'Cabo Rojo|Guánica|Hormigueros|Lajas|Maricao|Mayagüez|Sabana Grande|San Germán|Yauco'
    ),
    'north': 'Arecibo|Barceloneta|Camuy|Dorado|Florida|Hatillo|Manatí|Toa Alta|Toa Baja|Vega Alta|Vega Baja',
    'south': (
        'Arroyo|Coamo|Guayama|Guayanilla|Juana Díaz|Patillas|Peñuelas|Ponce|Salinas|Santa Isabel|'
        'Villalba'
    ),
    'central': (
        'Adjuntas|Aibonito|Barranquitas|Ciales|Cidra|Comerío|Corozal|Jayuya|Morovis|Naranjito|'
        'Orocovis|Utuado'
    ),
    'capital': 'Aguas Buenas|Bayamón|Caguas|Carolina|Cataño|Cayey|Guaynabo|Gurabo|San Juan|Trujillo Alto',
}


def select_municipios(db, requested=(), regions=(), whole_island=False):
    names = {fold(name): name for name, in db.execute('SELECT name FROM municipios')}
    requested = [requested] if isinstance(requested, str) else list(requested)
    for region in regions:
        if region not in REGIONS:
            raise ValueError('Unknown region: ' + region)
        requested.extend(REGIONS[region].split('|'))
    unknown = [name for name in requested if fold(name) not in names]
    if unknown:
        raise ValueError('Municipio is absent from the index: ' + ', '.join(unknown))
    chosen = set(names) if whole_island else {fold(name) for name in requested}
    if not chosen:
        raise ValueError('Choose --municipio, --region or --all.')
    return sorted((names[key] for key in chosen), key=fold)


def area_arguments(parser):
    parser.add_argument('--municipio', action='append', default=[], help='Municipio to include (repeatable)')
    parser.add_argument('--region', action='append', default=[], choices=REGIONS, help='Preset municipio group (repeatable)')
    parser.add_argument('--all', dest='whole_island', action='store_true', help='Include all municipios in the Puerto Rico index')
