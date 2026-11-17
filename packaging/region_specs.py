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
    # Metropolitan boxes, not whole states. Natural Earth populated places, checked 2026-11-17.
    'au-ade': {
        'country': 'Australia',
        'title': 'Adelaide area',
        'bbox': [138.09, -35.44, 139.1, -34.43],
        'extract': 'https://download.geofabrik.de/australia-oceania/australia/south-australia-latest-free.gpkg.zip',
        'source': 'OpenStreetMap contributors, via Geofabrik south-australia-latest-free.gpkg.zip (ODbL 1.0)',
    },
    'au-bri': {
        'country': 'Australia',
        'title': 'Brisbane area',
        'bbox': [152.53, -27.96, 153.54, -26.95],
        'extract': 'https://download.geofabrik.de/australia-oceania/australia/queensland-latest-free.gpkg.zip',
        'source': 'OpenStreetMap contributors, via Geofabrik queensland-latest-free.gpkg.zip (ODbL 1.0)',
    },
    'au-can': {
        'country': 'Australia',
        'title': 'Canberra area',
        'bbox': [148.62, -35.79, 149.63, -34.78],
        'extract': 'https://download.geofabrik.de/australia-oceania/australia/new-south-wales-latest-free.gpkg.zip',
        'source': 'OpenStreetMap contributors, via Geofabrik new-south-wales-latest-free.gpkg.zip (ODbL 1.0)',
    },
    'au-dar': {
        'country': 'Australia',
        'title': 'Darwin area',
        'bbox': [130.35, -12.93, 131.36, -11.92],
        'extract': 'https://download.geofabrik.de/australia-oceania/australia/northern-territory-latest-free.gpkg.zip',
        'source': 'OpenStreetMap contributors, via Geofabrik northern-territory-latest-free.gpkg.zip (ODbL 1.0)',
    },
    'au-hob': {
        'country': 'Australia',
        'title': 'Hobart area',
        'bbox': [146.79, -43.36, 147.8, -42.35],
        'extract': 'https://download.geofabrik.de/australia-oceania/australia/tasmania-latest-free.gpkg.zip',
        'source': 'OpenStreetMap contributors, via Geofabrik tasmania-latest-free.gpkg.zip (ODbL 1.0)',
    },
    'au-mel': {
        'country': 'Australia',
        'title': 'Melbourne area',
        'bbox': [144.47, -38.32, 145.48, -37.31],
        'extract': 'https://download.geofabrik.de/australia-oceania/australia/victoria-latest-free.gpkg.zip',
        'source': 'OpenStreetMap contributors, via Geofabrik victoria-latest-free.gpkg.zip (ODbL 1.0)',
    },
    'au-per': {
        'country': 'Australia',
        'title': 'Perth area',
        'bbox': [115.33, -32.46, 116.34, -31.45],
        'extract': 'https://download.geofabrik.de/australia-oceania/australia/western-australia-latest-free.gpkg.zip',
        'source': 'OpenStreetMap contributors, via Geofabrik western-australia-latest-free.gpkg.zip (ODbL 1.0)',
    },
    'au-syd': {
        'country': 'Australia',
        'title': 'Sydney area',
        'bbox': [150.68, -34.42, 151.69, -33.41],
        'extract': 'https://download.geofabrik.de/australia-oceania/australia/new-south-wales-latest-free.gpkg.zip',
        'source': 'OpenStreetMap contributors, via Geofabrik new-south-wales-latest-free.gpkg.zip (ODbL 1.0)',
    },
}
