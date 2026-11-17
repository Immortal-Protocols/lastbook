"""Exercise federal mile measures, boundary clipping, gaps and excluded roads on tiny synthetic inputs."""
import unittest
from shapely.geometry import box, mapping
from tools.build_pr_rural import Areas, M_PER_MILE, sections


def areas(items):
    return Areas([{'properties': {'id': label}, 'geometry': mapping(polygon)}
                  for label, polygon in items], lambda a: a['id'])


def feature(label, paths):
    return {'attributes': {'route_id': label}, 'geometry': {'paths': paths}}


class BuildRural(unittest.TestCase):
    def test_split_at_barrio_and_zip_boundaries_and_convert_reversed_miles(self):
        barrios = areas([(('Oeste','Pueblo'), box(-.01,0,.01,1)), (('Este','Pueblo'), box(.01,0,.03,1))])
        zctas = areas([('00700', box(-.01,0,.015,1))])
        roads = [feature('PR-007 NB', [[[.02,.2,2], [0,.2,1]]])]
        rows = list(sections(roads, barrios, zctas, lambda b,t,z: (b,t,z)))
        intervals = {(row[8], round(row[2],3), round(row[3],3)) for row in rows}
        self.assertEqual(intervals, {
            (('Oeste','Pueblo','00700'), round(M_PER_MILE,3), round(1.5*M_PER_MILE,3)),
            (('Este','Pueblo','00700'), round(1.5*M_PER_MILE,3), round(1.75*M_PER_MILE,3)),
            (('Este','Pueblo',''), round(1.75*M_PER_MILE,3), round(2*M_PER_MILE,3))})
        self.assertEqual({r[0] for r in rows}, {7})
        for m in (1700, 2000, 2500, 3000):
            self.assertTrue(any(row[1] == m//1000 and row[2] <= m <= row[3] for row in rows))

    def test_no_interpolation_across_missing_paths_or_calibration_jumps(self):
        barrio = areas([(('Oeste','Pueblo'), box(-1,-1,1,1))])
        zip_area = areas([('00700', box(-1,-1,1,1))])
        paths = [[[0,0,0],[.01,0,.6]], [[.02,0,4],[.03,0,4.6]]]
        roads = [feature('PR-007', paths), feature('PR-008 RAMP', paths),
                 feature('PR-009', [[[0,0,0],[.001,0,20]]]),
                 feature('PR-010', [[[0,0,None],[.01,0,.6]]])]
        rows = list(sections(roads, barrio, zip_area, lambda *area: 1))
        self.assertEqual({r[0] for r in rows}, {7})
        self.assertFalse(any(r[2] <= 3000 <= r[3] for r in rows))
