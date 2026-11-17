#!/usr/bin/env python3
"""Rebuild the small Natural Earth land patches for Ceuta and Melilla.

Build-time only; requires Shapely. See docs/MAPS.md for the pinned source and licence.
"""
import argparse
import hashlib
import json
from pathlib import Path

from shapely.geometry import box, mapping, shape
from shapely.ops import unary_union

SOURCE_SHA256 = '1ac90796408bc6ad6911d69448485d3c4dbf2190370080368a09976e1c9f7416'
REGIONS = (('Ceuta', (-5.5, 35.8, -5.15, 36.0)), ('Melilla', (-3.12, 35.2, -2.82, 35.38)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    data = args.input.read_bytes()
    if hashlib.sha256(data).hexdigest() != SOURCE_SHA256:
        parser.error('Natural Earth source hash does not match the pinned revision')
    land = [shape(f['geometry']) for f in json.loads(data)['features']]
    features = []
    for name, bounds in REGIONS:
        area = box(*bounds)
        clipped = unary_union([polygon.intersection(area) for polygon in land if polygon.intersects(area)])
        features.append({'type': 'Feature', 'properties': {'name': name}, 'geometry': mapping(clipped)})
    args.output.write_text(json.dumps({'type': 'FeatureCollection', 'features': features}, separators=(',', ':')) + '\n')


if __name__ == '__main__':
    main()
