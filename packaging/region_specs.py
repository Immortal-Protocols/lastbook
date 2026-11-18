"""The non-US region maps Lastbook can build: one entry per region, keyed by a stable lowercase id (ISO 3166-2 for individual regions).

A region is the "state" equivalent outside the US (docs/MAPS.md, "Region maps"). Unlike a US state map, a region map
ships map.sqlite, detail-cells.json, national-status.json and map-set.json, with optional places.sqlite
for regions declaring places=True, built from a Geofabrik OpenStreetMap
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

    # Metropolitan boxes, not whole states. Natural Earth populated places, checked 2026-11-17.
    'au-ade': {
        'country': 'Australia',
        'places': True,
        'title': 'Adelaide area',
        'bbox': [138.09, -35.44, 139.1, -34.43],
        'extract': 'https://download.geofabrik.de/australia-oceania/australia/south-australia-latest-free.gpkg.zip',
        'source': 'OpenStreetMap contributors, via Geofabrik south-australia-latest-free.gpkg.zip (ODbL 1.0)',
    },
    'au-bri': {
        'country': 'Australia',
        'places': True,
        'title': 'Brisbane area',
        'bbox': [152.53, -27.96, 153.54, -26.95],
        'extract': 'https://download.geofabrik.de/australia-oceania/australia/queensland-latest-free.gpkg.zip',
        'source': 'OpenStreetMap contributors, via Geofabrik queensland-latest-free.gpkg.zip (ODbL 1.0)',
    },
    'au-can': {
        'country': 'Australia',
        'places': True,
        'title': 'Canberra area',
        'bbox': [148.62, -35.79, 149.63, -34.78],
        'extract': 'https://download.geofabrik.de/australia-oceania/australia/new-south-wales-latest-free.gpkg.zip',
        'source': 'OpenStreetMap contributors, via Geofabrik new-south-wales-latest-free.gpkg.zip (ODbL 1.0)',
    },
    'au-dar': {
        'country': 'Australia',
        'places': True,
        'title': 'Darwin area',
        'bbox': [130.35, -12.93, 131.36, -11.92],
        'extract': 'https://download.geofabrik.de/australia-oceania/australia/northern-territory-latest-free.gpkg.zip',
        'source': 'OpenStreetMap contributors, via Geofabrik northern-territory-latest-free.gpkg.zip (ODbL 1.0)',
    },
    'au-hob': {
        'country': 'Australia',
        'places': True,
        'title': 'Hobart area',
        'bbox': [146.79, -43.36, 147.8, -42.35],
        'extract': 'https://download.geofabrik.de/australia-oceania/australia/tasmania-latest-free.gpkg.zip',
        'source': 'OpenStreetMap contributors, via Geofabrik tasmania-latest-free.gpkg.zip (ODbL 1.0)',
    },
    'au-mel': {
        'country': 'Australia',
        'places': True,
        'title': 'Melbourne area',
        'bbox': [144.47, -38.32, 145.48, -37.31],
        'extract': 'https://download.geofabrik.de/australia-oceania/australia/victoria-latest-free.gpkg.zip',
        'source': 'OpenStreetMap contributors, via Geofabrik victoria-latest-free.gpkg.zip (ODbL 1.0)',
    },
    'au-per': {
        'country': 'Australia',
        'places': True,
        'title': 'Perth area',
        'bbox': [115.33, -32.46, 116.34, -31.45],
        'extract': 'https://download.geofabrik.de/australia-oceania/australia/western-australia-latest-free.gpkg.zip',
        'source': 'OpenStreetMap contributors, via Geofabrik western-australia-latest-free.gpkg.zip (ODbL 1.0)',
    },
    'au-syd': {
        'country': 'Australia',
        'places': True,
        'title': 'Sydney area',
        'bbox': [150.68, -34.42, 151.69, -33.41],
        'extract': 'https://download.geofabrik.de/australia-oceania/australia/new-south-wales-latest-free.gpkg.zip',
        'source': 'OpenStreetMap contributors, via Geofabrik new-south-wales-latest-free.gpkg.zip (ODbL 1.0)',
    },
    # Whole Geofabrik extract envelopes, not administrative boundary guarantees.
    'au-nsw': {
        'country': 'Australia',
        'places': True,
        'title': 'New South Wales, ACT and Jervis Bay extract area',
        'bbox': [140.99, -37.76, 160.08, -28.13],
        'extract': 'https://download.geofabrik.de/australia-oceania/australia/new-south-wales-latest-free.gpkg.zip',
        'source': 'OpenStreetMap contributors, via Geofabrik new-south-wales-latest-free.gpkg.zip (ODbL 1.0)',
    },
    'au-nt': {
        'country': 'Australia',
        'places': True,
        'title': 'Northern Territory extract area',
        'bbox': [128.67, -26.01, 140.43, -9.97],
        'extract': 'https://download.geofabrik.de/australia-oceania/australia/northern-territory-latest-free.gpkg.zip',
        'source': 'OpenStreetMap contributors, via Geofabrik northern-territory-latest-free.gpkg.zip (ODbL 1.0)',
    },
    'au-qld': {
        'country': 'Australia',
        'places': True,
        'title': 'Queensland extract area',
        'bbox': [137.99, -29.19, 154.21, -8.84],
        'extract': 'https://download.geofabrik.de/australia-oceania/australia/queensland-latest-free.gpkg.zip',
        'source': 'OpenStreetMap contributors, via Geofabrik queensland-latest-free.gpkg.zip (ODbL 1.0)',
    },
    'au-sa': {
        'country': 'Australia',
        'places': True,
        'title': 'South Australia extract area',
        'bbox': [128.99, -39.84, 141.01, -25.99],
        'extract': 'https://download.geofabrik.de/australia-oceania/australia/south-australia-latest-free.gpkg.zip',
        'source': 'OpenStreetMap contributors, via Geofabrik south-australia-latest-free.gpkg.zip (ODbL 1.0)',
    },
    'au-tas': {
        'country': 'Australia',
        'places': True,
        'title': 'Tasmania extract area',
        'bbox': [143.47, -56.87, 161.68, -39.19],
        'extract': 'https://download.geofabrik.de/australia-oceania/australia/tasmania-latest-free.gpkg.zip',
        'source': 'OpenStreetMap contributors, via Geofabrik tasmania-latest-free.gpkg.zip (ODbL 1.0)',
    },
    'au-vic': {
        'country': 'Australia',
        'places': True,
        'title': 'Victoria extract area',
        'bbox': [140.95, -39.24, 150.47, -33.97],
        'extract': 'https://download.geofabrik.de/australia-oceania/australia/victoria-latest-free.gpkg.zip',
        'source': 'OpenStreetMap contributors, via Geofabrik victoria-latest-free.gpkg.zip (ODbL 1.0)',
    },
    'au-wa': {
        'country': 'Australia',
        'places': True,
        'title': 'Western Australia extract area',
        'bbox': [109.92, -41.17, 130.32, -12.83],
        'extract': 'https://download.geofabrik.de/australia-oceania/australia/western-australia-latest-free.gpkg.zip',
        'source': 'OpenStreetMap contributors, via Geofabrik western-australia-latest-free.gpkg.zip (ODbL 1.0)',
    },
    'au-act': {
        'country': 'Australia',
        'places': True,
        'title': 'Australian Capital Territory extract area',
        'bbox': [148.75, -35.93, 149.41, -35.12],
        'extract': 'https://download.geofabrik.de/australia-oceania/australia/act-latest-free.gpkg.zip',
        'source': 'OpenStreetMap contributors, via Geofabrik act-latest-free.gpkg.zip (ODbL 1.0)',
    },
}
