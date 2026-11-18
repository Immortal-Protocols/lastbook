#!/usr/bin/env python3
"""Lambert-93 (EPSG:2154, RGF93, GRS80) to and from longitude/latitude, with no dependency beyond numpy.

IGN products (BD TOPO, BD ALTI, RPG) are delivered in Lambert-93. RGF93 and WGS84 agree to well under a metre,
so the result is used as WGS84. Both functions accept floats or numpy arrays.
"""
import numpy as np

A = 6378137.0
F = 1 / 298.257222101
E = (2 * F - F * F) ** 0.5
LON0 = np.radians(3.0)
X0, Y0 = 700000.0, 6600000.0


def _iso(lat):
    s = E * np.sin(lat)
    return np.log(np.tan(np.pi / 4 + lat / 2) * ((1 - s) / (1 + s)) ** (E / 2))


def _m(lat):
    return np.cos(lat) / np.sqrt(1 - (E * np.sin(lat)) ** 2)


_P1, _P2, _P0 = np.radians(44.0), np.radians(49.0), np.radians(46.5)
N = float(np.log(_m(_P1) / _m(_P2)) / (_iso(_P2) - _iso(_P1)))
C = float(A * _m(_P1) * np.exp(N * _iso(_P1)) / N)
R0 = float(C * np.exp(-N * _iso(_P0)))


def to_lonlat(x, y):
    """Lambert-93 easting, northing in metres -> (lon, lat) in degrees."""
    x = np.asarray(x, dtype='float64') - X0
    y = R0 - (np.asarray(y, dtype='float64') - Y0)
    r = np.hypot(x, y)
    lon = LON0 + np.arctan2(x, y) / N
    iso = -np.log(r / C) / N
    lat = 2 * np.arctan(np.exp(iso)) - np.pi / 2
    for _ in range(8):
        s = E * np.sin(lat)
        lat = 2 * np.arctan(np.exp(iso) * ((1 + s) / (1 - s)) ** (E / 2)) - np.pi / 2
    return np.degrees(lon), np.degrees(lat)


def from_lonlat(lon, lat):
    """(lon, lat) in degrees -> Lambert-93 easting, northing in metres."""
    lon, lat = np.radians(np.asarray(lon, dtype='float64')), np.radians(np.asarray(lat, dtype='float64'))
    r = C * np.exp(-N * _iso(lat))
    g = N * (lon - LON0)
    return X0 + r * np.sin(g), Y0 + R0 - r * np.cos(g)


if __name__ == '__main__':
    lon, lat = to_lonlat(700000, 6600000)
    assert abs(lon - 3) < 1e-9 and abs(lat - 46.5) < 1e-9, (lon, lat)
    for lo, la in ((-0.3707, 49.1829), (-1.6222, 49.6337), (0.0906, 48.4323), (2.3499, 48.8530)):
        x, y = from_lonlat(lo, la)
        lo2, la2 = to_lonlat(x, y)
        assert abs(lo - lo2) < 1e-9 and abs(la - la2) < 1e-9
        print(f'{lo:9.4f} {la:8.4f} -> {float(x):11.2f} {float(y):11.2f}')
    print('n', N, 'C', C, 'R0', R0)
