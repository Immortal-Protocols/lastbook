"""The map's day and night shade: where the sun is overhead, how high it is at a place, and how dark that place is shaded.

Runs the functions between "sun:start" and "sun:end" in web/map.js under Node, against moments everyone can check: the
equinoxes and solstices, the equation of time, and sunrise and sunset in London. Needs Node on PATH; skipped without it.
Never packaged."""
import json, shutil, subprocess, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NODE = shutil.which('node')
RUN = r"""
const src = require('fs').readFileSync(process.argv[1], 'utf8');
const i = src.indexOf('// sun:start'), j = src.indexOf('// sun:end');
if (i < 0 || j < i) throw new Error('map.js has no sun:start ... sun:end block');
const { sunAt, sunHeight, nightShade } = new Function(src.slice(i, j) + '\nreturn { sunAt, sunHeight, nightShade };')();
const out = JSON.parse(process.argv[2]).map(([what, ...a]) =>
  what === 'sun' ? sunAt(new Date(a[0])) : what === 'height' ? sunHeight(a[1], a[2], sunAt(new Date(a[0]))) : nightShade(a[0]));
process.stdout.write(JSON.stringify(out));
"""


@unittest.skipUnless(NODE, 'needs Node')
class Sun(unittest.TestCase):
    def ask(self, *calls):
        r = subprocess.run([NODE, '-e', RUN, str(ROOT / 'web/map.js'), json.dumps(calls)],
                           capture_output=True, text=True, check=True, encoding='utf-8')
        return json.loads(r.stdout)

    def test_overhead_latitude_at_the_equinoxes_and_solstices(self):
        # 2026: March equinox 20 Mar 14:46 UTC, June solstice 21 Jun 08:24, September equinox 23 Sep 00:05, December solstice 21 Dec 20:50.
        got = [s['lat'] for s in self.ask(['sun', '2026-03-20T14:46Z'], ['sun', '2026-06-21T08:24Z'],
                                          ['sun', '2026-09-23T00:05Z'], ['sun', '2026-12-21T20:50Z'])]
        self.assertAlmostEqual(got[0], 0, delta=0.02)
        self.assertAlmostEqual(got[1], 23.436, delta=0.02)
        self.assertAlmostEqual(got[2], 0, delta=0.02)
        self.assertAlmostEqual(got[3], -23.436, delta=0.02)

    def test_overhead_longitude_follows_the_clock_and_the_equation_of_time(self):
        # At 12:00 UTC the sun is over Greenwich give or take the equation of time: about 16.4 minutes early on 3 November
        # (so already 4.1° west) and 14.2 minutes late on 11 February (still 3.55° east). It moves 15° west an hour.
        nov, feb, later = self.ask(['sun', '2026-11-03T12:00Z'], ['sun', '2026-02-11T12:00Z'], ['sun', '2026-11-03T18:00Z'])
        self.assertAlmostEqual(nov['lon'], -4.1, delta=0.1)
        self.assertAlmostEqual(feb['lon'], 3.55, delta=0.1)
        self.assertAlmostEqual(later['lon'], nov['lon'] - 90, delta=0.1)

    def test_longitude_stays_between_minus_180_and_180(self):
        for s in self.ask(*[['sun', f'2026-05-0{d}T{h:02d}:30Z'] for d in range(1, 4) for h in range(24)]):
            self.assertGreaterEqual(s['lon'], -180)
            self.assertLess(s['lon'], 180)

    def test_sunrise_and_sunset_in_london(self):
        # 21 June 2026 in London: sunrise 04:43 BST and sunset 21:21 BST, when the sun's top edge is at -0.833°; it is highest
        # at 13:02 BST (12:02 UTC) and lowest twelve hours later.
        rise, noon, sset, midnight = self.ask(['height', '2026-06-21T03:43Z', 51.5074, -0.1278], ['height', '2026-06-21T12:02Z', 51.5074, -0.1278],
                                              ['height', '2026-06-21T20:21Z', 51.5074, -0.1278], ['height', '2026-06-22T00:02Z', 51.5074, -0.1278])
        self.assertAlmostEqual(rise, -0.833, delta=0.2)
        self.assertAlmostEqual(sset, -0.833, delta=0.2)
        self.assertAlmostEqual(noon, 90 - 51.5074 + 23.436, delta=0.1)   # highest of the year
        self.assertAlmostEqual(midnight, -(90 - 51.5074 - 23.436), delta=0.1)   # a midsummer night never gets fully dark there

    def test_overhead_and_opposite(self):
        t = '2026-08-01T09:00Z'
        s = self.ask(['sun', t])[0]
        over, opposite = self.ask(['height', t, s['lat'], s['lon']], ['height', t, -s['lat'], s['lon'] + 180])
        self.assertAlmostEqual(over, 90, delta=0.01)
        self.assertAlmostEqual(opposite, -90, delta=0.01)

    def test_shade_none_by_day_deepening_through_twilight_full_at_night(self):
        got = self.ask(*[['shade', h] for h in (45, 0, -0.833, -6, -12, -18, -40, -90)])
        self.assertEqual(got[:3], [0, 0, 0])
        self.assertTrue(0 < got[3] < got[4] < got[5], got)
        self.assertEqual(got[5:], [1, 1, 1])

PREF = r"""
const src = require('fs').readFileSync(process.argv[1], 'utf8');
const i = src.indexOf('// daynight-pref:start'), j = src.indexOf('// daynight-pref:end');
if (i < 0 || j < i) throw new Error('map.js has no daynight-pref block');
const { dayNightOn } = new Function(src.slice(i, j) + '\nreturn { dayNightOn };')();
const out = JSON.parse(process.argv[2]).map(style => dayNightOn(style));
process.stdout.write(JSON.stringify(out));
"""


@unittest.skipUnless(NODE, 'needs Node')
class DayNightPreference(unittest.TestCase):
    def ask(self, *styles):
        r = subprocess.run([NODE, '-e', PREF, str(ROOT / 'web/map.js'), json.dumps(list(styles))],
                           capture_output=True, text=True, check=True, encoding='utf-8')
        return json.loads(r.stdout)

    def test_off_on_a_fresh_install_and_kept_once_saved(self):
        # A fresh mapStyle has no daynight key (see load('mapStyle', { relief: true, contours: true })).
        got = self.ask({}, {'relief': True, 'contours': True}, {'daynight': False}, {'daynight': True, 'relief': True})
        self.assertEqual(got, [False, False, False, True])


if __name__ == '__main__':
    unittest.main()
