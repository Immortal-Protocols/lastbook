"""Public overview envelopes, never a person's saved area or a coverage filter.

Canada's country extent follows the Natural Earth country outline already shipped
in web/world-context.json. Region envelopes come from Geofabrik's extract index
(https://download.geofabrik.de/index-v1.json, 2026-11-17). They deliberately include
border/ocean overlap and are navigation aids, not precise administrative borders.
"""

CANADA_BOUNDS = [-141.1, 41.5, -52.5, 83.7]
CANADA_REGIONS = [
    ('alberta', 'Alberta', [-120.0043, 48.9925, -110.0018, 60.0025]),
    ('british-columbia', 'British Columbia', [-141.7761, 46.4146, -114.049, 60.0068]),
    ('manitoba', 'Manitoba', [-102.014, 48.9906, -88.1218, 60.0085]),
    ('new-brunswick', 'New Brunswick', [-69.0597, 44.1921, -62.8858, 48.3807]),
    (
        'newfoundland-and-labrador',
        'Newfoundland and Labrador',
        [-67.8708, 44.4579, -44.1768, 60.5086],
    ),
    (
        'northwest-territories',
        'Northwest Territories',
        [-136.6974, 59.9896, -101.976, 81.6548],
    ),
    ('nova-scotia', 'Nova Scotia', [-67.2473, 42.1069, -58.2259, 47.8979]),
    ('nunavut', 'Nunavut', [-120.737, 51.1268, -53.2694, 84.952]),
    ('ontario', 'Ontario', [-95.1596, 41.6601, -74.31, 57.5083]),
    (
        'prince-edward-island',
        'Prince Edward Island',
        [-64.6024, 45.825, -61.2488, 47.6857],
    ),
    ('quebec', 'Quebec', [-79.8404, 44.9855, -57.0891, 62.6262]),
    ('saskatchewan', 'Saskatchewan', [-110.0069, 48.9876, -101.3614, 60.0005]),
    ('yukon', 'Yukon', [-141.2389, 59.9974, -123.8021, 70.1629]),
]


def canada_info(meta):
    """Read legacy/current metadata without making an incomplete receipt fatal."""
    bounds = None
    try:
        import math

        values = [float(v) for v in meta.get('bounds', '').split(',')]
        if (
            len(values) == 4
            and all(math.isfinite(v) for v in values)
            and -180 <= values[0] <= values[2] <= 180
            and -90 <= values[1] <= values[3] <= 90
        ):
            bounds = values
    except (ValueError, TypeError):
        pass
    overview_bounds = list(CANADA_BOUNDS)
    if bounds is not None:
        clamped = [
            max(bounds[0], CANADA_BOUNDS[0]),
            max(bounds[1], CANADA_BOUNDS[1]),
            min(bounds[2], CANADA_BOUNDS[2]),
            min(bounds[3], CANADA_BOUNDS[3]),
        ]
        if clamped[0] < clamped[2] and clamped[1] < clamped[3]:
            overview_bounds = clamped
    return {
        'bounds': bounds,
        'overview_bounds': overview_bounds,
        'regions': [
            {'id': key, 'label': label, 'bounds': box}
            for key, label, box in CANADA_REGIONS
        ],
        'data_as_of': meta.get('data_as_of') or 'unknown',
        'source': meta.get('source')
        or 'OpenStreetMap Canada (source metadata unavailable)',
        'limitations': meta.get('limitations')
        or 'Coverage varies with mapped records; no live status.',
    }
