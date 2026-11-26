# A place finder from a map's existing GeoPackage

The free Geofabrik GeoPackages used by the proposed Australian region maps already
contain named POINT places. `tools/build_places_gpkg.py` builds the `place` and
`place_fts` schema that `server.places()` queries, using only Python and SQLite FTS5.
No extra download, spatial extension or runtime connection is needed.

This complements the PBF-based builder merged in #63 as
`tools/build_places_region.py`. The GPKG input is useful
when a region builder already has that extract cached. It is less rich: it has the
primary name and place class, not the PBF's alternative-language tags. It only
indexes point settlements; it does not manufacture polygon centroids, street
addresses, Australian postcodes, help points or live facility information.

```sh
python3 -B tools/build_places_gpkg.py /path/to/victoria.gpkg \
  --out /path/to/new/places.sqlite --region 'Australia' \
  --bbox=144.47,-38.32,145.48,-37.31
python3 -B -m unittest tools.test_build_places_gpkg
```

The box is **west,south,east,north**, in longitude/latitude degrees. Only WGS84
longitude/latitude point layers are accepted. The input files are read-only. An
existing output is refused. Multiple extracts can be passed in one build, and
overlapping copies of the same named/classed point are deduplicated.

The schema/rank order agrees with the existing place finder and #63: city before
town, village, hamlet/locality/island, then suburbs and other small places. Every
row attributes OpenStreetMap. Geofabrik's `national_capital` class is ranked like
a city, so Canberra is not accidentally dropped. The detail label is also indexed;
using a country label avoids matching every row when searching the capital name.
Builds and distributions need the usual
OpenStreetMap contributor attribution and ODbL 1.0 notice; the source region map
already carries them. Do not put a private home/user location in `--region`.

This tool does not change the region-map release file contract, the Setup manifest
or its download allowlist. A maintainer must decide how to include `places.sqlite`
in regional packs and keep it with the corresponding map during switches/repair.
Do not overwrite the place finder in a personal installed library to try this out.
Use a separate review library and record the added file in its local map-set
manifest. Match the place-index box to the map box: a result is not proof that
detailed streets exist outside the installed map's coverage.

## Australian review data

Built from the same dated Geofabrik source snapshots used for the Australian
capital-map review, clipped to those existing region boxes:

| Map box | Named point places |
| --- | ---: |
| Melbourne area | 533 |
| Canberra area | 419 |
| Sydney area | 1,013 |

These are named point places, not help facilities or address counts. The free
extract's primary names can themselves use any script; this does not recover
alternate names omitted by Geofabrik. Source manifests and test results accompany
the review artifacts.

The same builder has also produced separate indexes matching all eight broader
state/territory extract areas in #38, from the dated 15 November 2026 sources:

| Map box | Named point places |
| --- | ---: |
| ACT extract | 187 |
| NSW extract (includes ACT and Jervis Bay) | 12,659 |
| Northern Territory extract | 1,019 |
| Queensland extract | 6,136 |
| South Australia extract | 1,652 |
| Tasmania extract | 1,276 |
| Victoria extract | 3,054 |
| Western Australia extract | 3,373 |

These 29,356 rows include overlap between NSW and ACT; they are not a deduplicated
national place count. All eight actual SQLite/FTS integrity checks, bounds checks
and capital/selected regional-town queries passed. On 26 November 2026 the native
combined Australian review app (`5c5e501`) also found Mildura in the broader
Victorian extract, drew detailed streets and showed nearby places with metric
distances. The other seven broader extracts retain engine/data checks rather
than native-window checks. The earlier metro check covered East Melbourne.
[Review sidecars and per-source provenance](https://github.com/pilkster/lastbook/releases/tag/australia-state-maps-review-2026-11-17)
remain separate from the existing four-file map ZIP contract. External-territory
completeness and address/postcode search are not established by these builds.

The separate integration proposal #101 builds this index from the same cached
inputs and box as its map, includes it in the archive inventory, and preserves
or repairs it through Setup's map lifecycle. Its review builds do not change
production Setup or replace the older standalone sidecar downloads. The tool
itself is rebased on main `51658f5`; its four focused tests pass unchanged.
