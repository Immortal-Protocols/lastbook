"""The non-US region maps Lastbook can build: one entry per region, keyed by a stable lowercase id (ISO 3166-2 for individual regions).

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
    'ca-maritimes': {
        'country': 'Canada',
        'title': 'Maritimes (New Brunswick, Nova Scotia and Prince Edward Island)',
        # Envelope of the three Geofabrik extract polygons, rounded outwards (includes offshore islands).
        'bbox': [-69.06, 42.10, -58.22, 48.39],
        'extracts': [
            'https://download.geofabrik.de/north-america/canada/new-brunswick-latest-free.gpkg.zip',
            'https://download.geofabrik.de/north-america/canada/nova-scotia-latest-free.gpkg.zip',
            'https://download.geofabrik.de/north-america/canada/prince-edward-island-latest-free.gpkg.zip',
        ],
        'source': 'OpenStreetMap contributors, via Geofabrik New Brunswick, Nova Scotia and Prince Edward Island extracts (ODbL 1.0)',
    },
}
