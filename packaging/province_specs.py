"""Province-wide extracts offered alongside the region maps. Bounds enclose the Geofabrik extract polygons."""

PROVINCES = {
    'ca-nb': {
        'country': 'Canada',
        'title': 'New Brunswick',
        'bbox': [-69.06, 44.19, -62.88, 48.39],
        'extract': 'https://download.geofabrik.de/north-america/canada/new-brunswick-latest-free.gpkg.zip',
        'source': 'OpenStreetMap contributors, via Geofabrik new-brunswick-latest-free.gpkg.zip (ODbL 1.0)',
    },
    'ca-ns': {
        'country': 'Canada',
        'title': 'Nova Scotia',
        'bbox': [-67.25, 42.1, -58.22, 47.9],
        'extract': 'https://download.geofabrik.de/north-america/canada/nova-scotia-latest-free.gpkg.zip',
        'source': 'OpenStreetMap contributors, via Geofabrik nova-scotia-latest-free.gpkg.zip (ODbL 1.0)',
    },
    'ca-pe': {
        'country': 'Canada',
        'title': 'Prince Edward Island',
        'bbox': [-64.61, 45.82, -61.24, 47.69],
        'extract': 'https://download.geofabrik.de/north-america/canada/prince-edward-island-latest-free.gpkg.zip',
        'source': 'OpenStreetMap contributors, via Geofabrik prince-edward-island-latest-free.gpkg.zip (ODbL 1.0)',
    },
    'za-wc': {
        'country': 'South Africa',
        'title': 'Western Cape and nearby areas',
        # Mainland and nearshore envelope of OSM relation 80501, rounded outwards.
        'bbox': [17.56, -35.04, 24.23, -30.43],
        'extract': 'https://download.geofabrik.de/africa/south-africa-latest-free.gpkg.zip',
        'source': 'OpenStreetMap contributors, via Geofabrik south-africa-latest-free.gpkg.zip (ODbL 1.0)',
    },
}
