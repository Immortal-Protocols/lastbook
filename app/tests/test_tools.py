"""The water guide's bleach tool (web/tools.js) only multiplies each source's own rate by the amount of water, and says how.
These run its arithmetic under Node on the real figures in content/topics/water.json, so a change to the guide or the code
that would print a different number fails here. Needs Node on PATH; skipped without it. Never packaged."""
import json, re, shutil, subprocess, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NODE = shutil.which('node')
RUN = r"""
const fs = require('fs');
const tools = fs.readFileSync(process.argv[1], 'utf8'), app = fs.readFileSync(process.argv[2], 'utf8');
const esc = app.split('\n').find(l => /^const esc\s*=/.test(l));
const Tools = new Function('store', 'navigator', esc + '\n' + tools + '\nreturn Tools;')({ get: (k, d) => d, set() {} }, { language: 'en-US' });
const out = JSON.parse(process.argv[3]).map(([s, amount, unit]) => Tools._doseLines(s, amount, unit));
process.stdout.write(JSON.stringify(out));
"""
WATER = json.loads((ROOT / 'content/topics/water.json').read_text(encoding='utf-8'))
BLEACH = next(t for c in WATER['choices'] for t in c.get('tools', []) if t['id'] == 'bleach')
SRC = {s['doc']: s for s in BLEACH['sources']}
CERT, HESPERIAN, FEMA = SRC['ed5bac0a81b009'], SRC['med-953dfe1df69e0773'], SRC['f7ff53bcaae9cc']


def text(html):
    return [re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', li)).strip() for li in re.findall(r'<li>(.*?)</li>', html)]


@unittest.skipUnless(NODE, 'needs Node')
class Dose(unittest.TestCase):
    def lines(self, *cases):
        r = subprocess.run([NODE, '-e', RUN, str(ROOT / 'web/tools.js'), str(ROOT / 'web/app.js'), json.dumps(cases)],
                           capture_output=True, text=True, check=True)
        return [text(h) for h in json.loads(r.stdout)]

    def test_the_figures_the_pages_give(self):
        """The sources' own rates, read off the pages (CERT p. 135, Hesperian p. 23, FEMA/Red Cross p. 14)."""
        self.assertEqual([r['amount'] for r in CERT['rates']], [8, 16])
        self.assertEqual({r['per']: r['amount'] for r in HESPERIAN['rates']}, {'L': 2, 'gal': 8})
        self.assertEqual(FEMA['rates'], [{'amount': 16, 'per': 'gal'}])

    def test_gallons(self):
        cert, hes, fema = self.lines([CERT, 5, 'gal'], [HESPERIAN, 5, 'gal'], [FEMA, 5, 'gal'])
        self.assertEqual(cert, ['Clear water: 40 drops 8 drops per gallon × 5 gallons',
                                'Cloudy or dirty water: 80 drops 16 drops per gallon × 5 gallons'])
        self.assertEqual(hes, ['40 drops 8 drops per gallon × 5 gallons'])
        self.assertEqual(fema, ['80 drops 16 drops per gallon × 5 gallons'])

    def test_liters_use_the_pages_own_rate_or_say_how_they_were_converted(self):
        hes, fema = self.lines([HESPERIAN, 20, 'L'], [FEMA, 1, 'L'])
        self.assertEqual(hes, ['40 drops 2 drops per liter × 20 liters'])          # Hesperian gives drops per liter itself
        self.assertEqual(fema, ['5 drops 4.2 drops per liter × 1 liter (the page gives 16 per gallon; 1 gallon is 3.785 liters), '
                                'rounded up to a whole drop'])

    def test_rounding(self):
        a, b, c = self.lines([FEMA, 0.5, 'gal'], [CERT, 0.3, 'gal'], [FEMA, 0.1, 'gal'])
        self.assertEqual(a, ['8 drops 16 drops per gallon × 0.5 gallons'])
        self.assertEqual(b[0], 'Clear water: 3 drops 8 drops per gallon × 0.3 gallons, rounded up to a whole drop')   # 2.4
        self.assertEqual(c, ['2 drops 16 drops per gallon × 0.1 gallons, rounded up to a whole drop'])               # 1.6

    def test_a_condition_name_is_escaped(self):
        odd = {'rates': [{'amount': 1, 'per': 'gal', 'when': '<img src=x onerror=alert(1)>'}]}
        r = subprocess.run([NODE, '-e', RUN, str(ROOT / 'web/tools.js'), str(ROOT / 'web/app.js'), json.dumps([[odd, 1, 'gal']])],
                           capture_output=True, text=True, check=True)
        self.assertNotIn('<img', json.loads(r.stdout)[0])


if __name__ == '__main__':
    unittest.main()
