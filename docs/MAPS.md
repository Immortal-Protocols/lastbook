# How the offline map is put together

A guide for anyone who wants to improve the map: add a kind of place, show one that is already in the data, or extend
coverage. It says which files the app reads, what builds each one, and where the gaps are. Everything here was read from
the code and from one installed state map, without running the app; where something could not be found in this
repository, it says so.

The map follows the same rules as the rest of Lastbook (see [CONTRIBUTING.md](../CONTRIBUTING.md)). The app draws only
from files on the computer and never asks the network for a tile, a place or an address. The build tools in `tools/` are
different: they run on a build machine, and several of them download public data. They are never part of the app.

## What the app reads

A map set lives in the data folder. `map-set.json` at its top lists the files and their sizes.

| File | Tables | What it holds | Read by |
|---|---|---|---|
| `derived/geo/national.sqlite` | `feat`, `feat_idx`, `poi`, `meta` | Roads, water and land shapes, and the place pins | `server.py` (`national_mapdb`) |
| `derived/geo/map.sqlite` | the same four | The original detailed street map of Southern California; it had no rows in the state map checked | `server.py` (`mapdb`) |
| `derived/geo/water.sqlite` | `resource`, `spatial`, `feat`, `feat_idx` | Dams, reservoirs, lakes and ponds | `server.py` |
| `derived/geo/crops.sqlite` | `resource`, `spatial`, `tile` | Orchards, vineyards and berries | `server.py` |
| `derived/geo/terrain.sqlite` | `tile` | Elevation tiles for relief, contours and the 3D view | `server.py` |
| `derived/geo/buildings.sqlite` | `bldg` | Building outlines | `server.py` |
| `derived/geo/places.sqlite` | `place`, `place_fts` | The place finder: towns, ZIP codes, counties, named places | `server.py` (`/api/places`) |
| `library-data/geography/resources/atlas.sqlite` | `resource`, `spatial` | Natural resource records. The state map checked held minerals only; the fish, boating and well layers are labelled California in `web/map.js` | `server.py` |
| `derived/geo/addresses/` | one index per state | Street addresses for address search | `engine/address_search.py` |

Two kinds of table carry the things a person can tap:

- `poi(id, cls, name, lon, lat)`: a point with a class, such as `hospital` or `fuel`.
- `resource(id, source_id, kind, name, lat, lon, detail, source, origin)` with its `spatial` index: a record with a kind,
  a line of detail and the name of its source.

## How a place gets onto the map

1. A row with a class (`poi.cls`) or a kind (`resource.kind`) is in one of the files above.
2. The class is named in a layer in `web/map.js` (`LAYERS`: id, label, symbol, colour, classes, group).
3. The engine reports which classes a map set really holds (`map_contents` in `server.py`), and the app offers only the
   layers that have something to show.

A class that is in the data but in no layer has no entry in the Layers panel, so it cannot be switched on. The engine
already has a plain name for several of them (`HELP` in `server.py`: School, Dentist, Vet, Care home, Post office).

### Places that are in the data and not shown

The data holds more classes than `web/map.js` has layers for (`tools/build_map.py` lists the ones it keeps as
`POI_KEEP`). In one state map checked on 15 November 2026 (77,356 pins), these classes had rows and no layer:

| Class | Rows |
|---|---|
| `school` | 13,862 |
| `fountain` | 4,971 |
| `dentist` | 2,769 |
| `post_office` | 2,224 |
| `car_repair` | 1,444 |
| `park` | 1,102 |
| `veterinary` | 1,102 |
| `college` | 468 |
| `university` | 362 |
| `garden_centre` | 176 |
| `nursing_home` | 49 |
| `water_works` | 3 |

Showing one of these needs no new data: add a layer line in `web/map.js` and say in the pull request why the kind helps
someone in an emergency. The comment in `map.js` about retired layers shows that some kinds were left out on purpose,
so ask before adding many.

## What builds each file

| File | Built by | From |
|---|---|---|
| `map.sqlite` | `tools/build_map.py`, then `tools/build_coast.py` for the ocean | An OpenStreetMap regional extract (ODbL) |
| `water.sqlite` | `tools/build_water.py` (`nid`, then `nhd`) | USACE National Inventory of Dams, USGS National Hydrography Dataset |
| `crops.sqlite` | `tools/build_crops.py` | USDA Cropland Data Layer |
| `terrain.sqlite` | `tools/build_terrain.py` | USGS 3DEP elevation |
| `buildings.sqlite` | `tools/build_buildings.py`, `tools/build_osm_heights.py` | Microsoft building footprints (ODbL), OpenStreetMap heights |
| `places.sqlite` | `tools/build_places.py` | USGS GNIS, Census gazetteers, named OpenStreetMap places |
| address indexes | `tools/build_addresses.py`, then `packaging/address_indexes.py` | Overture Maps addresses |
| a state map | `packaging/build_packs.py map <ST>`, published by `packaging/state_maps.py` | The base map, then every row inside the state's box |

Each tool's header says what it reads, what it writes and the licence of its source. Read it before you run one: some
expect source files that are hundreds of gigabytes.

### Not in this repository

- **The builder for `national.sqlite`.** The pack tools copy from an existing `national.sqlite` and `server.py` reads it,
  but no tool here makes it from OpenStreetMap data.
- **The builder for `atlas.sqlite`.**
- **A reader for seven place files.** `tools/build_places_civic.py`, `_usgs.py`, `_overture.py`, `_atp.py`, `_fsq.py`,
  `_fuel.py` and `_snap.py` each write a `derived/geo/places-*.sqlite` and say it is merged by `game/serve.py`. That file
  is not here, and nothing in this repository reads those seven files, so the extra records they hold are not used by
  the app directly. This is an unused data source, not a missing kind of place: the map already shows shelters,
  libraries, community centres and food shops from the data it does read. A class that has records and no layer is the
  separate case described above.

## Spain

Spain is a separate, replaceable map set, identified as `ES`. It uses OpenStreetMap data processed by
[Geofabrik](https://download.geofabrik.de/europe/spain.html), with the separately published
[Canary Islands extract](https://download.geofabrik.de/africa/canary-islands.html). The inputs cover the
mainland, Balearic and Canary Islands, Ceuta and Melilla, subject to the contents and boundaries of those
extracts. Boundaries can include neighboring areas. Features and service points are only as complete and
current as OpenStreetMap, and do not describe closures or hazards.

The map includes mapped streets, building outlines, water, land use, railways, island polygons, named places and selected
help points. It has **no elevation, relief, contours, aerial photographs, US resource inventories or
street-address search**. Street geometry is not an address index: town and named-place search is supported,
but searching for a house number and street is not. Selecting Spain replaces the current map set, including
the US map in the All library; a US state can be selected again later. To restore the whole US map in an All
library, use **Download All and restore** in Library and local AI; this downloads and installs All again.
Setup shows the download size before starting. Existing address index files are kept but are not searched while
the Spain map is active.

The Canary and Balearic island land outlines come from the OSM extracts. Ceuta and Melilla use small,
generalized [Natural Earth 1:10m land](https://www.naturalearthdata.com/downloads/10m-physical-vectors/10m-land/)
patches, which can be inaccurate at street zoom. Natural Earth data is public domain. The patches are stored in
`web/spain-context.json` and are drawn behind the detailed OSM features.

Map data: © OpenStreetMap contributors, licensed under the [Open Database License 1.0](https://opendatacommons.org/licenses/odbl/1-0/).
See the [OpenStreetMap copyright and attribution page](https://www.openstreetmap.org/copyright) and
[Geofabrik's extract page](https://download.geofabrik.de/europe/spain.html). These are build-time sources;
the app does not contact them. When distributing a derived database, follow the ODbL's attribution,
share-alike and source-availability requirements.

### Rebuild the Spain map

Use Python 3.11 or newer with SQLite R-tree and FTS5, `curl`, and `unzip`. The following downloads the
19 Geofabrik GeoPackage snapshots dated 15 November 2026. The compressed source archives total about **3.20 GB**;
the extracted inputs and build output require additional disk space. A local build of these inputs with
Python 3.15.2 and SQLite 3.54.1 produced a **1,415,768,867-byte zip** and **3,758,842,174 installed bytes**.
That is a build measurement, not a published release; later releases can differ and setup uses the sizes in
their manifest. The local zip's SHA-256 was `23e874aed049de474a85f294ca05971821195b1876252171ffd663517053b17a`.
The checked [input hashes](spain-input-2026-11-15.sha256) pin these specific archives. Keep the archives if
an identical input needs to be rebuilt later; Geofabrik may retire dated snapshots. `latest` changes over time
and is not reproducible.

```bash
mkdir -p /path/to/spain-input
lastbook_root="$PWD"
for region in andalucia aragon asturias cantabria castilla-la-mancha castilla-y-leon cataluna ceuta \
  extremadura galicia islas-baleares la-rioja madrid melilla murcia navarra pais-vasco valencia; do
  curl -fL "https://download.geofabrik.de/europe/spain/${region}-261115-free.gpkg.zip" \
    -o "/path/to/spain-input/${region}.zip"
  unzip -p "/path/to/spain-input/${region}.zip" "${region}.gpkg" > "/path/to/spain-input/${region}.gpkg"
done
curl -fL "https://download.geofabrik.de/africa/canary-islands-261115-free.gpkg.zip" \
  -o /path/to/spain-input/canary-islands.zip
unzip -p /path/to/spain-input/canary-islands.zip canary-islands.gpkg > /path/to/spain-input/canary-islands.gpkg
(cd /path/to/spain-input && shasum -a 256 -c "$lastbook_root/docs/spain-input-2026-11-15.sha256")
python3 -B tools/build_spain.py --input-dir /path/to/spain-input \
  --output-dir /path/to/new-spain-build --data-date 2026-11-15
```

The output directory must not already exist. The builder refuses a full `ES` build if any required extract
is missing; it records SHA-256 hashes of the unpacked inputs in the map database, combines overlapping
extracts, creates the place finder, and prints the zip's SHA-256, download bytes and installed bytes. Use the
same inputs, Python and SQLite versions when comparing builds. Generated GeoPackages, SQLite databases and
zips belong outside Git. A small **incomplete** test can be built from any subset by adding `--sample`;
it is labeled `ES-SAMPLE`, never `ES`.

For release, a maintainer can place the `ES` directory from the build under `derived/packs/maps/ES`, then run
`packaging/state_maps.py ES` in the established release environment. That script applies the map scan,
zips and uploads the set, verifies the public SHA-256, and publishes the entry in the separate
`manifest-spain-v1.json`. Do not add Spain to `manifest-v1.json`: older clients read that manifest but do
not support country maps. The release script makes its
own archive and records its own hash and sizes. Its release-only publisher,
credentials, private-term scan list and storage access are not part of this repository. Until an actual
archive has been published on Lastbook's approved download host and listed with its real sizes and hash,
Spain appears as unavailable in setup. Do not publish an `ES-SAMPLE` as a full country map.

To regenerate the small Natural Earth patches (not needed for an ordinary map build), install
`shapely==2.1.2` in a build environment, then run:

```bash
curl -fL https://raw.githubusercontent.com/nvkelso/natural-earth-vector/ace5fed0eaf3c6c03c951e75b439ba8fffbc218e/geojson/ne_10m_land.geojson -o /path/to/ne_10m_land.geojson
python3 -B tools/build_spain_context.py /path/to/ne_10m_land.geojson /path/to/spain-context.json
```

The tool verifies the source SHA-256 before writing. Shapely (BSD-3-Clause; GEOS is LGPL-2.1) is used only
to regenerate this asset, not by the app or the Spain map builder.

## What else is tied to the United States

- The US state map sources listed above are US datasets, or worldwide ones filtered to the US.
- `server.py` treats a box around Southern California as the area `map.sqlite` covers (`_poi_sources`, `socal_classes`).
- US detailed maps are cut and installed one state at a time (`docs/SETUP-API.md`, "State maps").
- Address search knows US state names and US street words (`engine/address_search.py`, `tools/build_addresses.py`).
- The base map of the world is drawn from `web/world-context.json` and `web/geographic-context.json`.

Other countries need the same source, licence, coverage and address-search decisions; US federal layers do not
automatically extend to them.

## Checking a map change

- A change to a layer in `web/map.js` is a change you can see: include screenshots in light and dark mode.
- A change to a pack or map tool: `packaging/test_pack_tools.py` and `packaging/scan_pack.py` check what a map set may
  hold, and `scan_pack.py` lists the allowed files under `derived/geo/` (`GEO_FILES`).
- Spain builder and setup regressions: `python3 -B -m unittest app.tests.test_spain_map`. The setup download test
  starts a temporary HTTPS server bound to localhost; no external network is used by the tests.
- Nothing a contributor adds may make the app open a connection. New data comes in through a build tool and ships as a
  file.
