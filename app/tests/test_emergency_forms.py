#!/usr/bin/env python3
"""tools/emergency_forms.py: the review page and the submit page for content/emergency/.

  python3 -B -m unittest app.tests.test_emergency_forms

The submit page checks an entry in JavaScript. These tests build both pages, and (when Node is installed) run that
checker on the real files and on the test's own broken rows, to prove it gives the same verdict as problems() in
app/tests/test_emergency_numbers.py. The rules live there, once. The pages must also stay offline."""
import contextlib, copy, io, json, shutil, subprocess, sys, tempfile, unittest
from datetime import date
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import emergency_forms as forms  # noqa: E402
from app.tests import test_emergency_numbers as rules  # noqa: E402

NODE = shutil.which('node')
LATEST = date(2026, 11, 22)


class Pages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        with contextlib.redirect_stdout(io.StringIO()):
            forms.main(['x', cls.tmp.name])
        cls.review = (Path(cls.tmp.name) / 'review.html').read_text(encoding='utf-8')
        cls.submit = (Path(cls.tmp.name) / 'submit.html').read_text(encoding='utf-8')

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_review_page_shows_every_number_of_every_file(self):
        for p in sorted(rules.DIR.glob('*.json')):
            d = json.loads(p.read_text(encoding='utf-8'))
            self.assertIn(d['country'], self.review)
            for s in d['services']:
                self.assertIn(f'data-card="{d["code"]} {s["number"]} ', self.review.replace('&amp;', '&'), s['number'])

    def test_the_review_page_has_a_selector_per_row_and_the_format_button(self):
        self.assertGreater(self.review.count('<select data-id='), 100)
        self.assertEqual(self.review.count('<option value="ok">approved</option><option value="c">comment</option>'),
                         self.review.count('<select data-id='))
        self.assertIn('id="format"', self.review)

    def test_the_review_page_says_what_the_test_thinks_of_a_broken_entry(self):
        d = json.loads((rules.DIR / 'CL.json').read_text(encoding='utf-8'))
        d['services'][0]['works_form'] = ['mobile']          # a typo in a key
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / 'CL.json').write_text(json.dumps(d), encoding='utf-8')
            page = forms.build_review(Path(t))
        self.assertIn('The test fails on this entry', page)
        self.assertIn('unknown key', page)

    def test_the_submit_page_states_every_value_the_test_allows(self):
        for group in (rules.KINDS, rules.HOW, rules.WORKS_FROM, rules.VERIFIED):
            for v in group:
                self.assertIn(f'<code>{v}</code>', self.submit, v)
        for key in rules.SERVICE_KEYS - {'free_source', 'works_from_source'}:
            self.assertIn(key, self.submit, key)
        for key in rules.COUNTRY_KEYS:
            self.assertIn(key, self.submit, key)
        self.assertIn('es-cl', self.submit)                   # the rule about regions is stated

    def test_the_pages_load_nothing_and_send_nothing(self):
        for page in (self.review, self.submit):
            for bad in ('<script src', '<link', '<img', '<iframe', 'fetch(', 'XMLHttpRequest', 'sendBeacon', 'WebSocket',
                        '@import', 'url(http'):
                self.assertNotIn(bad, page, bad)


@unittest.skipUnless(NODE, 'Node is not installed: the page checker is not compared with the test')
class SamePageAndTestVerdict(unittest.TestCase):
    """The submit page's JavaScript checker and problems() agree."""

    @staticmethod
    def js(cases):
        """cases: [(data, name, latest date)] -> list of problem lists from the page's checker, run in Node."""
        code = (forms.validator_script() + '\nconst c = JSON.parse(require("fs").readFileSync(0, "utf8"));\n'
                'process.stdout.write(JSON.stringify(c.map(x => validate(x.data, x.name, x.latest))));')
        with tempfile.TemporaryDirectory() as t:
            f = Path(t) / 'check.js'
            f.write_text(code, encoding='utf-8')
            r = subprocess.run([NODE, str(f)], input=json.dumps([{'data': d, 'name': n, 'latest': L.isoformat()} for d, n, L in cases]),
                               capture_output=True, text=True, encoding='utf-8', timeout=60)
        if r.returncode:
            raise AssertionError(r.stderr)
        return json.loads(r.stdout)

    def test_the_real_files_pass_in_the_page_too(self):
        files = sorted(rules.DIR.glob('*.json'))
        cases = [(json.loads(p.read_text(encoding='utf-8')), p.name, rules.REFERENCE_DATE) for p in files]
        for p, found in zip(files, self.js(cases)):
            self.assertEqual(found, [], p.name)

    def test_the_page_and_the_test_agree_on_broken_rows(self):
        good = rules.Checker.GOOD

        def mutate(**change):
            d = copy.deepcopy(good)
            for k, v in change.items():
                if k.startswith('s_'):
                    if v is DELETE:
                        d['services'][0].pop(k[2:], None)
                    else:
                        d['services'][0][k[2:]] = v
                elif v is DELETE:
                    d.pop(k, None)
                else:
                    d[k] = v
            return d
        DELETE = object()
        multi = {'languages': ['es', 'qu', 'ay']}
        full = {'es': ['emergencia'], 'qu': ['ratu'], 'ay': ['jan walt'], 'en': ['emergency']}
        variants = {
            'good': mutate(),
            'no languages': mutate(languages=DELETE), 'empty languages': mutate(languages=[]), 'languages not a list': mutate(languages='es'),
            'duplicate language': mutate(languages=['es', 'es']), 'region language': mutate(languages=['es-cl']),
            'upper language': mutate(languages=['ES']), 'newline language': mutate(languages=['es\n']),
            'multi good': mutate(s_keywords=full, **multi),
            'multi missing es': mutate(s_keywords={k: v for k, v in full.items() if k != 'es'}, **multi),
            'multi missing en': mutate(s_keywords={k: v for k, v in full.items() if k != 'en'}, **multi),
            'multi extra': mutate(s_keywords={**full, 'gn': ['mba']}, **multi),
            'multi empty list': mutate(s_keywords={**full, 'qu': []}, **multi),
            'upper keyword': mutate(s_keywords={'es': ['Emergencia'], 'en': ['emergency']}),
            'local key': mutate(s_keywords={'local': ['emergencia'], 'en': ['emergency']}),
            'region keyword': mutate(s_keywords={'es-cl': ['emergencia'], 'en': ['emergency']}),
            'bad kind': mutate(s_kind='hospital'), 'bad verified': mutate(s_verified='probably'),
            'bad how': mutate(s_how=['pigeon']), 'empty how': mutate(s_how=[]), 'bad works_from': mutate(s_works_from=['telepathy']),
            'number letters': mutate(s_number='nine one one'), 'number plus': mutate(s_number='+911'), 'number star': mutate(s_number='*911', general='*911'),
            'no source': mutate(s_source=''), 'source list': mutate(s_source=['https://example.org/a', 'https://example.org/b']),
            'bad source list': mutate(s_source=['https://example.org/a', '']), 'empty source list': mutate(s_source=[]),
            'works_from no source': mutate(s_works_from_source=DELETE), 'works_from empty keeps source': mutate(s_works_from=[]),
            'works_from empty no source': mutate(s_works_from=[], s_works_from_source=DELETE),
            'free null keeps source': mutate(s_free=None), 'free null no source': mutate(s_free=None, s_free_source=DELETE),
            'free no source': mutate(s_free_source=DELETE), 'free missing': mutate(s_free=DELETE), 'free string': mutate(s_free='yes'),
            'bad date': mutate(s_checked_on='2026-13-40'), 'future date': mutate(s_checked_on='2026-11-23'), 'last day': mutate(s_checked_on='2026-11-22'),
            'slashed date': mutate(s_checked_on='22/11/2026'), 'no date': mutate(s_checked_on=DELETE),
            'url good': mutate(s_url='https://example.org/service'), 'url empty': mutate(s_url=''), 'url null': mutate(s_url=None), 'url bad': mutate(s_url='x'),
            'whole good': mutate(s_area_whole_country=True), 'whole string': mutate(s_area_whole_country='yes'),
            'area good': mutate(s_area='San Miguel'), 'area empty': mutate(s_area=' '), 'area and whole': mutate(s_area='San Miguel', s_area_whole_country=True),
            'general unknown': mutate(general='112'), 'general null': mutate(general=None),
            'typo service key': mutate(s_works_form=['mobile']), 'typo country key': mutate(countri='x'),
            'no calling code': mutate(calling_code='56'), 'no country': mutate(country=''), 'wrong code': mutate(code='YY'),
            'no services': mutate(services=[]), 'when not text': mutate(s_when=None),
        }
        cases = [(d, 'ZZ.json', LATEST) for d in variants.values()]
        js = self.js(cases)
        for (label, d), found in zip(variants.items(), js):
            py = rules.problems(d, 'ZZ.json', latest=LATEST)
            self.assertEqual(bool(py), bool(found), f'{label}: test says {py}, page says {found}')


if __name__ == '__main__':
    unittest.main()
