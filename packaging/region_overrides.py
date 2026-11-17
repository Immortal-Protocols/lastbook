"""Per-region overrides for packaging/generate_region_specs.py.

The generator derives one entry per Natural Earth sovereign capital, keyed by its Natural
Earth ADM0_A3 code (stable and unique), and resolves its Geofabrik extract. This file is the
human-edited place to fix the cases the data cannot decide on its own. Edit it, then
regenerate with `python -I -B packaging/generate_region_specs.py`.

Each value may set:

  exclude: true        drop this capital - no region map is generated for it
  code:    'xx-abc'    replace the generated map id (two-letter country prefix plus city slug)
  title:   '...'       replace the shown city name
  country: '...'       replace the shown country name
  radius:  0.3         replace the box half-width, in degrees (default 0.3)
  bbox:    [w, s, e, n] replace the whole box (overrides radius)
  extract: 'https://…'  replace the Geofabrik GeoPackage download URL
"""

OVERRIDES = {
    'USA': {'code': 'us-wdc'},   # "Washington, D.C." would slug to "was"; use the conventional DC code
    'KOS': {'code': 'xk-pri'},   # Kosovo: Natural Earth stores no ISO 3166-1 code for it; use the de facto XK
    'SOL': {'exclude': True},    # Somaliland: self-declared, not an ISO 3166-1 member; no code to key on
}
