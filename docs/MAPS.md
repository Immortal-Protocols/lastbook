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
| `derived/geo/national.sqlite` | `feat`, `feat_idx`, `poi`, `meta` | Roads, water and land shapes, and the place pins; for maps built with `tools/build_region.py` this is the region itself | `server.py` (`national_mapdb`) |
| `derived/geo/map.sqlite` | the same four | The original detailed street map of Southern California; it had no rows in the state map checked, nor in maps built with `tools/build_region.py` | `server.py` (`mapdb`) |
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
| `national.sqlite` | `tools/build_map.py`, run by `tools/build_region.py` for a complete set | An OpenStreetMap regional extract (ODbL) |
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

- **The builder for the US national map.** The pack tools copy from an existing `national.sqlite` and `server.py` reads it, but the
  whole-country map is built by a separate pipeline. `tools/build_map.py` does make a regional one from an OpenStreetMap extract,
  and `tools/build_region.py` uses it to build a complete map set for a place without one (below) — which is all a non-US
  region needs, because its map has no detailed `map.sqlite` and falls back to `national.sqlite`.
- **The builder for `atlas.sqlite`.**
- **A reader for seven place files.** `tools/build_places_civic.py`, `_usgs.py`, `_overture.py`, `_atp.py`, `_fsq.py`,
  `_fuel.py` and `_snap.py` each write a `derived/geo/places-*.sqlite` and say it is merged by `game/serve.py`. That file
  is not here, and nothing in this repository reads those seven files, so the extra records they hold are not used by
  the app directly. This is an unused data source, not a missing kind of place: the map already shows shelters,
  libraries, community centres and food shops from the data it does read. A class that has records and no layer is the
  separate case described above.

## What is tied to the United States

- The map itself is not: `tools/build_region.py` builds a regional `national.sqlite`, `places.sqlite` and map set from any
  Geofabrik free extract (below). The remaining files — water, crops, terrain, buildings, the place sources, addresses —
  still are.
- Every detailed source above is a US dataset, or a worldwide one filtered to the US.
- `server.py` treats a box around Southern California as the area `map.sqlite` covers (`_poi_sources`, `socal_classes`).
- Detailed maps are cut and installed one US state at a time (`docs/SETUP-API.md`, "State maps").
- Address search knows US state names and US street words (`engine/address_search.py`, `tools/build_addresses.py`).
- The base map of the world is drawn from `web/world-context.json` and `web/geographic-context.json`.

Coverage outside the US needs a decision on each of these first: which open source replaces each federal list, under
what licence, what a "state" is elsewhere, and how addresses are written. That is a design discussion to have in an
issue before any code.

[REGIONS.md](REGIONS.md) proposes answers for Ontario, British Columbia and Guyana, as a starting point for that issue.
[REGIONS-AR.md](REGIONS-AR.md) does the same for Argentina's provinces and the Autonomous City of Buenos Aires.
[REGIONS-LK.md](REGIONS-LK.md) does the same for Sri Lanka as one island-wide region.
[REGIONS-TH.md](REGIONS-TH.md) does the same for Thailand's provinces and Bangkok.
[REGIONS-DE.md](REGIONS-DE.md) does the same for Germany's 16 states.
[REGIONS-PY.md](REGIONS-PY.md) does the same for Paraguay as one country-wide region.
[REGIONS-IE.md](REGIONS-IE.md) does the same for the island of Ireland, including Northern Ireland, as one region.
[REGIONS-GB-LONDON.md](REGIONS-GB-LONDON.md) does the same for Greater London as one region.
[REGIONS-ES.md](REGIONS-ES.md) does the same for Spain's 17 autonomous communities and its two autonomous cities.
[REGIONS-FR.md](REGIONS-FR.md) does the same for France's 18 regions, with figures from a trial build.
[REGIONS-CL.md](REGIONS-CL.md) does the same for Chile's 16 regions.
[REGIONS-AE.md](REGIONS-AE.md) does the same for the United Arab Emirates, proposed as one map for all seven emirates.
[REGIONS-IN.md](REGIONS-IN.md) does the same for India's 28 states and 8 union territories.
[REGIONS-PK.md](REGIONS-PK.md) does the same for Pakistan's provinces and territories, with Islamabad and Rawalpindi
as one map.
[REGIONS-MB.md](REGIONS-MB.md) does the same for the Canadian province of Manitoba.
[REGIONS-DK.md](REGIONS-DK.md) does the same for Denmark's 5 regions.

## Building a map for a place without one

For a place Lastbook has no map of — a Brazilian state, a European country — `tools/build_region.py` builds the same set of
files from the free OpenStreetMap extract Geofabrik publishes for the region. It is stdlib-only and offline: the extract is
a local file, and the only step that needs more is the optional coastline (pyosmium).

    curl -L -o sudeste.zip https://download.geofabrik.de/south-america/brazil/sudeste-free-gpkg-latest.zip
    python3 tools/build_region.py sudeste.zip --name BR-RJ --label "Rio de Janeiro" \
        --box -46.7,-24.9,-40.1,-19.9 --data /path/to/LastbookData
    python3 server.py --data /path/to/LastbookData

- `--box west,south,east,north` clips the extract to the place: a Brazilian state extract also holds its neighbouring
  states, so without a box the map covers the whole extract.
- The data folder must also hold `library-data/` (the base world map and the search library): clone it from an installed
  LastbookData.
- What it writes: `derived/geo/national.sqlite` (the detailed map), `derived/geo/places.sqlite`, an empty
  `derived/geo/map.sqlite` placeholder, `national-status.json`, `socal-cells.json` (`[]`) and `map-set.json`.
  Re-running rebuilds the set in place.

### The coastline gotcha

The free GeoPackage has no `natural=coastline` ways — only the full `.osm.pbf` has them — so a map built from it has no
real sea edge: the ragged low-resolution base world map shows through along the coast. `tools/build_coast.py` fixes that by
reading the coastline ways from a `.osm.pbf` (it needs pyosmium; `derived/buildenv/bin/python` has it):

    python3 tools/build_region.py sudeste.zip --name BR-RJ --label "Rio de Janeiro" \
        --box -46.7,-24.9,-40.1,-19.9 --coast /path/to/coastline.osm.pbf --coast-close 10 --data /path/to/LastbookData

`--coast-close` is a longitude well out to sea from the open ends of the mainland coast: `-125` (the Pacific) for a
west-facing coast like SoCal's, `10` (mid-Atlantic) for Brazil's east-facing one. The full regional pbf is large — Brazil's
is about 2 GB, and the coast tool's `flex_mem` index scales with the file — so a coastline-only extract of the same area
keeps the step small.

The other files — water, crops, terrain, buildings, the place sources, addresses — are still US datasets; the `REGIONS-*.md`
proposals above cover those.

## Checking a map change

- A change to a layer in `web/map.js` is a change you can see: include screenshots in light and dark mode.
- A change to a pack or map tool: `packaging/test_pack_tools.py` and `packaging/scan_pack.py` check what a map set may
  hold, and `scan_pack.py` lists the allowed files under `derived/geo/` (`GEO_FILES`).
- Nothing a contributor adds may make the app open a connection. New data comes in through a build tool and ships as a
  file.
