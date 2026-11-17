"""The non-US region maps Lastbook can build: one entry per region, keyed by its ISO 3166-2 code (lowercase).

A region is the "state" equivalent outside the US (docs/MAPS.md, "Region maps"). Unlike a US state map, a region map
ships only map.sqlite, detail-cells.json, national-status.json and map-set.json, built from a Geofabrik OpenStreetMap
GeoPackage clipped to the region's box. Add a region here and run packaging/region_maps.py <id>.
"""

REGIONS = {
    've-a': {   # Distrito Capital, the federal capital district of Venezuela
        'country': 'Venezuela',
        'title': 'Caracas (Distrito Capital)',
        'bbox': [-67.10, 10.40, -66.80, 10.56],
        'extract': 'https://download.geofabrik.de/south-america/venezuela-latest-free.gpkg.zip',
        'source': 'OpenStreetMap contributors, via Geofabrik venezuela-latest-free.gpkg.zip (ODbL 1.0)',
    },
}
