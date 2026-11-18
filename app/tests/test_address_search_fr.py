"""French address indexes (tools/build_addresses_ban.py) and the French side of engine/address_search.py.

The US lookup must not change: the last test runs a set of US queries through the engine as it was before French
support (read from git) and through the current one, and requires the same answers.
"""
import csv, gzip, sqlite3, subprocess, sys, tempfile, types, unittest
from pathlib import Path

import engine.address_search as address_search
from engine.address_search import find_addresses, is_address_query, normalize

ROOT = Path(__file__).resolve().parents[2]
BUILDER = ROOT / 'tools' / 'build_addresses_ban.py'
BEFORE_FRENCH = 'ae421bbf4cedc619000be2520bddea0603583b5f'   # last commit of engine/address_search.py before French support
HEADER = ('id;id_fantoir;numero;rep;nom_voie;code_postal;code_insee;nom_commune;code_insee_ancienne_commune;'
          'nom_ancienne_commune;x;y;lon;lat;type_position;alias;nom_ld;libelle_acheminement;nom_afnor;source_position;'
          'source_nom_voie;certification_commune;cad_parcelles').split(';')

# numero, rep, nom_voie, code_postal, code_insee, nom_commune, nom_ancienne_commune, lon, lat, nom_ld
FRENCH = {
    '14': [
        ('12', '', 'Rue Saint-Pierre', '14000', '14118', 'Caen', '', -0.3615, 49.1840, ''),
        ('1', '', 'Rue Écuyère', '14000', '14118', 'Caen', '', -0.3672, 49.1834, ''),
        ('1', 'bis', 'Rue Écuyère', '14000', '14118', 'Caen', '', -0.3673, 49.1835, ''),
        ('14', '', 'Boulevard Maréchal Leclerc', '14000', '14118', 'Caen', '', -0.3620, 49.1810, ''),
        ('3', '', 'Allée des Fleurs', '14000', '14118', 'Caen', '', -0.3700, 49.1900, ''),
        ('2', '', 'Rue Sainte-Marie', '14400', '14047', 'Bayeux', '', -0.7020, 49.2760, ''),
        ('4', '', "Route de l'Église de Malloué", '14350', '14061', 'Souleuvre en Bocage', 'Malloué', -0.9800, 48.9400, ''),
        ('4', '', "Chemin de l'Église de Montamy", '14260', '14061', 'Souleuvre en Bocage', 'Montamy', -0.8500, 48.9600, ''),
        ('13', '', "Route de l'Église", '14700', '14088', 'Bonnœil', '', -0.2300, 48.9600, ''),
        ('87', '', 'Rue des Forges', '14490', '14035', 'Balleroy-sur-Drôme', 'Balleroy', -0.8400, 49.1800, ''),
        ('4', '', 'Le Bourbillon', '14260', '14347', 'Dialan sur Chaîne', 'Le Mesnil-Auzouf', -0.7900, 48.9900, ''),
        ('709', '', 'Chemin de la Bruyère de Lessard', '14140', '14362', 'Lessard-et-le-Chêne', '', 0.1500, 49.0600, ''),
        ('3180', '', 'Route du Perron', '14240', '14672', 'Val de Drôme', 'Sept-Vents', -0.7800, 49.0700, ''),
        ('7', '', 'Rue des Unités', '35000', '35238', 'Rennes', '', -1.6800, 48.1100, ''),          # outside the region
        ('9', 'appt 1', 'Rue Écuyère', '14000', '14118', 'Caen', '', -0.3672, 49.1834, ''),       # a flat, not an index
        ('5', '', 'Rue Loin', '14000', '14118', 'Caen', '', 2.3500, 48.8600, ''),                 # position in Paris
    ],
    '50': [
        ('8', '', 'Rue Carnot', '50110', '50129', 'Cherbourg-en-Cotentin', 'Tourlaville', -1.5900, 49.6400, ''),
        ('4', '', 'Rue de la République', '50110', '50129', 'Cherbourg-en-Cotentin', 'Tourlaville', -1.5800, 49.6400, ''),
        ('4', '', 'rue de la République', '50120', '50129', 'Cherbourg-en-Cotentin', 'Équeurdreville-Hainneville', -1.6600, 49.6500, ''),
        ('6', '', 'Place de la Republique', '50100', '50129', 'Cherbourg-en-Cotentin', 'Cherbourg-Octeville', -1.6200, 49.6400, ''),
        ('4', '', 'Place Général de Gaulle', '50000', '50502', 'Saint-Lô', '', -1.0900, 49.1150, ''),
        ('2', '', 'Rue du Bourg', '50170', '50353', 'Le Mont-Saint-Michel', 'Le Mont-Saint-Michel', -1.5100, 48.6350, ''),
    ],
    '61': [
        ('21', '', 'Rue de Paris', '61130', '61038', 'Bellême', '', 0.5600, 48.3750, ''),
        ('5', '', 'Grande Rue', '61130', '61038', 'Bellême', '', 0.5610, 48.3760, ''),
        ('11', '', 'Rue du Marais', '61210', '61349', 'Ri', '', -0.1400, 48.7900, ''),
        ('4', '', 'Chemin de la Heulinière', '61130', '61005', 'Appenai-sous-Bellême', '', 0.5500, 48.3500, 'La Heulinière'),
        ('23', '', 'Rue des Acacias', '61560', '61027', 'Bazoches-sur-Hoëne', '', 0.4700, 48.5500, ''),
        ('315', '', 'Route de Fanay', '61130', '61440', 'Saint-Martin-du-Vieux-Bellême', '', 0.5700, 48.3900, ''),
        ('3', '', "Rue de l'Église", '61800', '61486', 'Tinchebray-Bocage', 'Tinchebray', -0.7300, 48.7600, ''),
        ('5', '', 'Route des Près des Disons', '61190', '61491', 'Tourouvre au Perche', 'Autheuil', 0.6678, 48.5660, 'Le Moncel'),
        ('5', '', 'Le Moncel', '61190', '61491', 'Tourouvre au Perche', 'Autheuil', 0.6700, 48.5700, ''),
    ],
}
TEN = {  # the ten communes whose last word is a US state code once accents are dropped
    'Bellême': '21 rue de Paris', 'Ri': '11 rue du Marais', 'Bonnœil': "13 route de l'Église",
    'Balleroy-sur-Drôme': '87 rue des Forges', 'Dialan sur Chaîne': '4 Le Bourbillon',
    'Lessard-et-le-Chêne': '709 chemin de la Bruyère de Lessard', 'Val de Drôme': '3180 route du Perron',
    'Appenai-sous-Bellême': '4 chemin de la Heulinière', 'Bazoches-sur-Hoëne': '23 rue des Acacias',
    'Saint-Martin-du-Vieux-Bellême': '315 route de Fanay',
}
US = {
    'MI': [('18001', 'W Nine Mile Road', 'Novi', 'MI', '48375', 42.45, -83.47),
           ('18002', 'W Nine Mile Road', 'Novi', 'MI', '48375', 42.46, -83.47),
           ('18001', 'Nine Mile Rd', 'Farmington', 'MI', '48335', 42.47, -83.40)],
    'CA': [('18001', 'Nine Mile Road', 'Example', 'CA', '90001', 34.0, -118.0),
           ('21', 'W 9 ST', 'Example', 'CA', '90001', 34.01, -118.01),
           ('100', 'Saint Mary Boulevard', 'San Diego', 'CA', '92101', 32.7, -117.1),
           ('12', "O'Farrell Street", 'San Francisco', 'CA', '94102', 37.78, -122.40),
           ('12', 'Oak Court', 'Example', 'CA', '90001', 34.02, -118.02),
           ('100', 'Main Street', 'Inglewood', 'CA', '90301', 33.96, -118.35),
           ('100', 'Main Street', 'Newport Beach', 'CA', '92660', 33.62, -117.93),
           ('23001', 'Maple Avenue', 'Kansas City', 'CA', '90002', 34.03, -118.03)],
    # The street endings and town names that are also states ('Ct', 'NE', 'Washington'): the engine reads such a query
    # two ways (_readings), the part French support had to fit around.
    'CT': [('12', 'Oak Street', 'Hartford', 'CT', '06103', 41.76, -72.67)],
    'DC': [('500', '4th Street NE', 'Washington', 'DC', '20002', 38.896, -77.000),
           ('1600', 'Pennsylvania Avenue NW', 'Washington', 'DC', '20500', 38.8977, -77.0365)],
    'ME': [('21', 'Paris Street', 'Portland', 'ME', '04101', 43.66, -70.25),
           ('5', 'Grand Rue', 'Belleme', 'ME', '04000', 44.0, -70.0)],
    'IL': [('13', 'Church Road', 'Bonn', 'IL', '60000', 41.0, -88.0)],
    'PR': [('7', 'Calle José Martí', 'San Juan', 'PR', '00907', 18.45, -66.07)],
    'CO': [('3', 'Cañon Avenue', 'Cañon City', 'CO', '81212', 38.44, -105.24)],
}
US_QUERIES = [
    '18001 9 mile rd Novi MI', '18001 Nine Mile Road Novi Michigan', '18001 nine mile Novi 48375',
    '18001 W Nine Mile Road, Novi, MI 48375', '18003 nine mile Novi MI', '18001 nine mile Wrongtown MI',
    '18001 nine mile MI 99999', '18001 nine mile CA', '18001 nine mile', '21 ninth st Example CA', '21 9th St',
    '100 St Mary Blvd San Diego', '100 saint mary boulevard CA', "12 O'Farrell St San Francisco CA", '12 ofarrell st',
    '21 Paris St Portland ME', '21 paris street maine', '5 grand rue belleme me', '5 Grande Rue Bellême',
    '13 church rd bonn il', '7 Calle José Martí San Juan PR', '7 calle jose marti PR', '7 calle jos mart',
    '3 Cañon Ave Cañon City CO', '3 canon ave', '23001 Maple Ave', '12 rue Saint-Pierre 14000 Caen',
    '21 rue de Paris Bellême', '4 rue de la République Tourlaville', '18001 nine mile rd novi mi 48375',
    '12 Oak Ct', '12 Oak St CT', '12 Oak Connecticut', '500 4th St NE', '500 4th St NE 20002',
    '500 4th St NE Washington DC', '1600 Pennsylvania Ave NW Washington', '1600 Pennsylvania Ave NW Washington DC',
    '100 Main St IN', '100 Main St NE', '100 Main St Indiana', '100 Main St IN 90301', '23001 Maple Ave Kansas',
]
FRENCH_QUERIES = {'5 Grande Rue Bellême', '12 rue Saint-Pierre 14000 Caen', '21 rue de Paris Bellême',
                  '4 rue de la République Tourlaville'}


def write_ban(directory, department, rows):
    path = directory / f'adresses-{department}.csv.gz'
    with gzip.open(path, 'wt', encoding='utf-8', newline='') as file:
        writer = csv.writer(file, delimiter=';')
        writer.writerow(HEADER)
        for numero, rep, voie, cp, insee, commune, old, lon, lat, lieu in rows:
            record = dict.fromkeys(HEADER, '')
            record.update(id=f'{insee}_x_{numero}', numero=numero, rep=rep, nom_voie=voie, code_postal=cp,
                          code_insee=insee, nom_commune=commune, nom_ancienne_commune=old, lon=lon, lat=lat,
                          nom_ld=lieu, type_position='entrée')
            writer.writerow([record[name] for name in HEADER])
    return path


def write_us(directory, state, rows, normalizer=normalize):
    db = sqlite3.connect(directory / f'{state}.sqlite')
    try:
        db.execute('CREATE TABLE addr(num TEXT,street TEXT,norm TEXT,city TEXT,state TEXT,zip TEXT,lat REAL,lon REAL)')
        db.execute('CREATE INDEX addr_num_norm ON addr(num,norm)')
        db.executemany('INSERT INTO addr VALUES(?,?,?,?,?,?,?,?)',
                       [(num, street, normalizer(street), city, st, z, lat, lon) for num, street, city, st, z, lat, lon in rows])
        db.commit()
    finally:
        db.close()


def build_french(directory, out, region='FR-BN'):
    sources = [str(write_ban(directory, department, rows)) for department, rows in FRENCH.items()]
    return subprocess.run([sys.executable, '-I', str(BUILDER), '--region', region, '--departments', '14,50,61',
                           '--out', str(out), *sources], capture_output=True, text=True)


class FrenchIndexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.geo = Path(cls.temp.name) / 'geo'
        (cls.geo / 'addresses').mkdir(parents=True)
        cls.build = build_french(Path(cls.temp.name), cls.geo / 'addresses' / 'FR-BN.sqlite')

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def find(self, query, **options):
        return find_addresses(query, self.geo, **options)

    def one(self, query):
        found = self.find(query)
        self.assertEqual(len(found), 1, (query, found))
        return found[0]

    def test_builder_output(self):
        self.assertEqual(self.build.returncode, 0, self.build.stderr)
        self.assertIn("rejected: {'outside the region': 1, 'unit in the repetition index': 1, 'position': 1}",
                      self.build.stdout)
        db = sqlite3.connect(self.geo / 'addresses' / 'FR-BN.sqlite')
        try:
            columns = [row[1] for row in db.execute('PRAGMA table_info(addr)')]
            indexes = {row[1]: [col[2] for col in db.execute(f'PRAGMA index_info({row[1]})')]
                       for row in db.execute('PRAGMA index_list(addr)')}
            meta = dict(db.execute('SELECT key, value FROM meta'))
            nums = {row[0] for row in db.execute("SELECT num FROM addr WHERE street = 'Rue Écuyère'")}
            city = db.execute("SELECT city, state FROM addr WHERE street = 'Rue Carnot'").fetchone()
            same_name = db.execute("SELECT city FROM addr WHERE street = 'Rue du Bourg'").fetchone()[0]
        finally:
            db.close()
        self.assertEqual(columns, ['num', 'street', 'norm', 'city', 'state', 'zip', 'lat', 'lon'])
        self.assertEqual(indexes, {'addr_norm': ['norm', 'num'], 'addr_num_norm': ['num', 'norm']})
        self.assertEqual((meta['norm'], meta['region'], meta['count']), ('fr-1', 'FR-BN', '28'))
        self.assertEqual(meta['rows'], '30')     # two lieu-dit rows
        self.assertEqual(nums, {'1', '1bis'})
        self.assertEqual(city, ('Cherbourg-en-Cotentin (Tourlaville)', 'FR-BN'))
        self.assertEqual(same_name, 'Le Mont-Saint-Michel')

    def test_builder_refuses_a_us_state_code(self):
        result = build_french(Path(self.temp.name), Path(self.temp.name) / 'ME.sqlite', region='ME')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((Path(self.temp.name) / 'ME.sqlite').exists())

    def test_queries_as_people_write_them(self):
        cases = {
            '12, rue Saint-Pierre Caen': ('12 Rue Saint-Pierre', '14000 Caen'),                       # 1
            '12 rue Saint-Pierre 14000 Caen': ('12 Rue Saint-Pierre', '14000 Caen'),                  # 2
            '12 rue Saint-Pierre Caen 14000': ('12 Rue Saint-Pierre', '14000 Caen'),
            "3 rue de l'Eglise Tinchebray-Bocage": ("3 Rue de l'Église", 'Tinchebray, 61800 Tinchebray-Bocage'),  # 3
            '6 place de la République Cherbourg': ('6 Place de la Republique', 'Cherbourg-Octeville, 50100 Cherbourg-en-Cotentin'),
            '8 rue Carnot Cherbourg-en-Cotentin': ('8 Rue Carnot', 'Tourlaville, 50110 Cherbourg-en-Cotentin'),  # 4
            '4 place Général de Gaulle Saint-Lô': ('4 Place Général de Gaulle', '50000 Saint-Lô'),       # 5
            '4 pl du gal de gaulle st lo': ('4 Place Général de Gaulle', '50000 Saint-Lô'),
            '5 Grande Rue Bellême': ('5 Grande Rue', '61130 Bellême'),                                 # 6
            '4 rue de la République Tourlaville': ('4 Rue de la République', 'Tourlaville, 50110 Cherbourg-en-Cotentin'),  # 7
            '4 rue de la République 50120 Cherbourg-en-Cotentin': ('4 rue de la République', 'Équeurdreville-Hainneville, 50120 Cherbourg-en-Cotentin'),
            '1 bis rue Écuyère Caen': ('1 bis Rue Écuyère', '14000 Caen'),                             # 8
            '1bis rue Ecuyere Caen': ('1 bis Rue Écuyère', '14000 Caen'),                              # 9
            '1 BIS, rue Ecuyère, 14000 CAEN': ('1 bis Rue Écuyère', '14000 Caen'),
            '14 bd Maréchal Leclerc Caen': ('14 Boulevard Maréchal Leclerc', '14000 Caen'),            # 10
            '14 boulevard mal leclerc caen': ('14 Boulevard Maréchal Leclerc', '14000 Caen'),
            '3 allee des Fleurs Caen': ('3 Allée des Fleurs', '14000 Caen'),                           # 11
            '3 all des Fleurs Caen': ('3 Allée des Fleurs', '14000 Caen'),
            '2 rue Ste Marie Bayeux': ('2 Rue Sainte-Marie', '14400 Bayeux'),                          # 12
            '2 rue du Bourg Le Mont-Saint-Michel': ('2 Rue du Bourg', '50170 Le Mont-Saint-Michel'),
        }
        for query, (name, detail) in cases.items():
            with self.subTest(query=query):
                result = self.one(query)
                self.assertEqual((result['name'], result['detail']), (name, detail))
                self.assertEqual(result['source'], 'Base Adresse Nationale')

    def test_places_and_po_boxes_are_not_addresses(self):
        self.assertFalse(is_address_query('Le Bourg Beauchêne Tinchebray-Bocage'))
        self.assertFalse(is_address_query('BP 25 14050 Caen Cedex 4'))
        self.assertFalse(is_address_query('14000'))

    def test_delegated_communes_are_told_apart(self):
        found = self.find("4 route de l'Église Souleuvre en Bocage")
        self.assertEqual([r['detail'] for r in found], ['Malloué, 14350 Souleuvre en Bocage'])
        found = self.find("4 rue de la République Cherbourg-en-Cotentin")
        self.assertEqual(sorted(r['detail'] for r in found), ['Tourlaville, 50110 Cherbourg-en-Cotentin',
                                                             'Équeurdreville-Hainneville, 50120 Cherbourg-en-Cotentin'])
        self.assertEqual(len(self.find('4 rue de la République Tourlaville Cherbourg-en-Cotentin')), 1)

    def test_ten_communes_are_not_us_states(self):
        for commune, street in TEN.items():
            for query in (f'{street} {commune}', f'{street} {address_search.fold(commune)}', f'{street}, {commune.upper()}'):
                with self.subTest(query=query):
                    result = self.one(query)
                    self.assertIn(commune, result['detail'])

    def test_another_script_finds_nothing(self):
        self.assertEqual(self.find('١٢ شارع'), [])     # Arabic-Indic digits pass is_address_query; no token is left to read

    def test_never_a_guessed_house(self):
        self.assertEqual(self.find('2 rue Écuyère Caen'), [])
        self.assertEqual(self.find('1 ter rue Écuyère Caen'), [])
        self.assertEqual([r['name'] for r in self.find('1 rue Écuyère Caen')], ['1 Rue Écuyère'])
        self.assertEqual(self.find('12 rue Saint-Pierre Bayeux'), [])
        self.assertEqual(self.find('12 rue Saint-Pierre 14400 Caen'), [])
        self.assertEqual(self.find('12 rue 14000 Caen'), [])
        self.assertEqual(self.find('9 rue Écuyère Caen'), [])           # the flat ('appt 1') was not indexed

    def test_lieu_dit_rows_come_after_the_street(self):
        found = self.find('5 Le Moncel Tourouvre au Perche')
        self.assertEqual([r['name'] for r in found], ['5 Le Moncel', '5 Route des Près des Disons'])
        self.assertEqual(found[1]['detail'], 'Autheuil, 61190 Tourouvre au Perche')
        self.assertEqual(self.one('4 La Heulinière Appenai')['name'], '4 Chemin de la Heulinière')

    def test_normalize_fr(self):
        self.assertEqual(address_search.normalize_fr("Rue de l'Église"), 'rue eglise')
        self.assertEqual(address_search.normalize_fr('R. de l’Eglise'), 'rue eglise')
        self.assertEqual(address_search.normalize_fr('Bonnœil'), 'bonnoeil')
        self.assertEqual(address_search.normalize_fr('Saint-Lô'), address_search.normalize_fr('ST LO'))


class UnchangedForUSTests(unittest.TestCase):
    """The same answers as before French support, with and without a French index installed."""

    @classmethod
    def setUpClass(cls):
        try:
            source = subprocess.run(['git', '-C', str(ROOT), 'show', f'{BEFORE_FRENCH}:engine/address_search.py'],
                                    capture_output=True, text=True, check=True).stdout
        except (OSError, subprocess.CalledProcessError):
            raise unittest.SkipTest('the engine before French support is not in this checkout (git history needed)')
        cls.before = types.ModuleType('address_search_before_french')
        exec(compile(source, 'address_search@' + BEFORE_FRENCH[:7], 'exec'), cls.before.__dict__)
        cls.temp = tempfile.TemporaryDirectory()
        cls.us = Path(cls.temp.name) / 'us'
        cls.mixed = Path(cls.temp.name) / 'mixed'
        for geo in (cls.us, cls.mixed):
            (geo / 'addresses').mkdir(parents=True)
            for state, rows in US.items():
                write_us(geo / 'addresses', state, rows, cls.before.normalize)
        result = build_french(Path(cls.temp.name), cls.mixed / 'addresses' / 'FR-BN.sqlite')
        assert result.returncode == 0, result.stderr
        legacy = Path(cls.temp.name) / 'legacy'
        legacy.mkdir()
        write_us(legacy, 'addresses', [('23001', 'Maple Avenue', 'Kansas City', 'MO', '64105', 39.0997, -94.5786)],
                 cls.before.normalize)
        cls.legacy = legacy

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_us_normalization_is_unchanged(self):
        for text in ('Saint Mary Boulevard', 'Calle José Martí', 'Cañon Avenue', "O'Farrell Street", 'Rue de l’Église'):
            self.assertEqual(normalize(text), self.before.normalize(text))

    def test_address_query_detection_is_unchanged(self):
        for text in ('48375', 'Novi MI', '18001 nine mile', '12, Main St', '12,Main St', '1-2 Oak Rd', ' 7 calle',
                     '12bis rue X', 'BP 25 Caen', '12, Avenue of the Stars'):
            with self.subTest(text=text):
                self.assertEqual(is_address_query(text), self.before.is_address_query(text))
        self.assertFalse(self.before.is_address_query('12, rue Saint-Pierre'))
        self.assertTrue(is_address_query('12, rue Saint-Pierre'))     # the one deliberate change: French comma form

    def test_us_queries_keep_their_route(self):
        """What was an address query still ends with the address answer; what was a place query still reaches places."""
        was_address = ('18001 nine mile', '1-2 Oak Rd', ' 7 calle', '12bis rue X', '48375 Novi', '62704-1234 Springfield')
        for text in was_address:
            with self.subTest(text=text):
                self.assertTrue(self.before.is_address_query(text))
                self.assertFalse(address_search.goes_on_to_places(text))
        # French street words that open a US street too: now address queries by the comma form, they find no house and
        # go on to the place finder, where they went before.
        for text in ('1200, R Street Sacramento CA', '10, Rte 66', '5, All Saints Way', '12, Che Guevara'):
            with self.subTest(text=text):
                self.assertFalse(self.before.is_address_query(text))
                self.assertEqual(find_addresses(text, self.us), [])
                self.assertEqual(find_addresses(text, self.mixed), [])
                self.assertTrue(address_search.goes_on_to_places(text))
        self.assertTrue(address_search.goes_on_to_places('14000 Caen', region=True))    # a postcode and its commune
        self.assertFalse(address_search.goes_on_to_places('12 rue Haute Caen', region=True))

    def test_same_answers(self):
        near = (42.0, -83.0)
        for query in US_QUERIES:
            for options in ({}, {'near': near}, {'limit': 1}):
                with self.subTest(query=query, options=options):
                    old = self.before.find_addresses(query, self.us, **options)
                    self.assertEqual(find_addresses(query, self.us, **options), old)
                    if query not in FRENCH_QUERIES:   # these find the French rows when a French index is installed
                        self.assertEqual(find_addresses(query, self.mixed, **options), old)
                    self.assertEqual(find_addresses(query, self.legacy, **options),
                                     self.before.find_addresses(query, self.legacy, **options))
        self.assertEqual(find_addresses('23001 Maple Ave Kansas City MO', self.legacy)[0]['lat'], 39.0997)

    def test_some_us_answers_are_not_empty(self):
        """Guards the comparison above against two engines that both find nothing."""
        self.assertEqual(find_addresses('18001 9 mile rd Novi MI', self.mixed)[0]['name'], '18001 W Nine Mile Road')
        self.assertEqual(find_addresses('21 paris street maine', self.mixed)[0]['detail'], 'Portland, ME, 04101')
        self.assertEqual(find_addresses('7 calle jos mart', self.mixed)[0]['name'], '7 Calle José Martí')
        self.assertEqual(find_addresses('12 Oak Ct', self.mixed)[0]['name'], '12 Oak Court')     # Court, with CT installed
        self.assertEqual(find_addresses('1600 Pennsylvania Ave NW Washington', self.mixed)[0]['detail'],
                         'Washington, DC, 20500')        # a town named like a state, read the second way
        self.assertEqual(find_addresses('100 Main St IN', self.mixed), [])     # Indiana is not installed


if __name__ == '__main__':
    unittest.main()
