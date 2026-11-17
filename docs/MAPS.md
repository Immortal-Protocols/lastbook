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
| Puerto Rico address index | `tools/build_pr_addresses.py` | OpenStreetMap address objects and US Census municipio boundaries |
| a state map | `packaging/build_packs.py map <ST>`, published by `packaging/state_maps.py` | The base map, then every row inside the state's box |

Each tool's header says what it reads, what it writes and the licence of its source. Read it before you run one: some
expect source files that are hundreds of gigabytes.

### Puerto Rico street addresses

The optional Puerto Rico index uses mapped house numbers and street names. Queries for
`7 Ave. Constitucion, San Juan, PR` and `7 Avenida Constitución, San Juan, PR` find the same point.
Results keep the source spelling. Search also accepts common forms of calle, carretera, camino and
bulevar, alphanumeric house numbers, and a comma-separated urbanización such as `Urb. Sol, A-12 Calle Ejemplo`.
A supplied ZIP, locality or urbanización must match the record. Urbanización names and ZIPs are often missing.

A rural search accepts the numbered road, kilometer and barrio in any order. Try
`Carr. 916 km 4 hm 4, Bo. Cerro Gordo, San Lorenzo` or `Bº Cerro Gordo, km 4,4, PR-916, San Lorenzo`.
Both refer to kilometer 4.4. A decimal before a road, as in `0.6 Carr 119`, also identifies a kilometer.
A whole number in that position can be a house number.

- **Road kilometer** places the marker along a measured road segment from the Federal Highway Administration.
  The builder converts each vertex's mile measure to meters and splits the segment at barrio and ZIP-area boundaries.
  Search interpolates between two measured vertices on the same path. A missing segment leaves a gap.
  The point is on the road. Someone meeting you at a house may still need a turn, gate or driveway.
- **Public school** uses the NCES coordinates for a named school whose published street address contains the
  same road and kilometer. Its address can name a local barrio or postal city. Lastbook labels the school by name.
- A supplied barrio, municipality or ZIP restricts the search. Census ZIP Code Tabulation Areas approximate
  postal areas. Interior, sector and landmark directions are shown as unverified on road results.

For a build, download the Puerto Rico OSM PBF from [Geofabrik](https://download.geofabrik.de/north-america/us/puerto-rico.html)
and the [US Census municipio boundaries](https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/1/query?where=STATE%3D%2772%27&outFields=NAME%2CGEOID&outSR=4326&geometryPrecision=5&f=geojson).
Save them as `puerto-rico.osm.pbf` and `municipios.geojson`. Use Python 3.11 or newer in a separate build environment.

```sh
python -m pip install osmium==4.3.2 shapely==2.2.0
python tools/fetch_pr_rural.py derived/pr-rural-inputs
python tools/build_pr_addresses.py puerto-rico.osm.pbf municipios.geojson derived/pr-addresses --rural derived/pr-rural-inputs
python -m unittest tools.test_build_pr_addresses tools.test_build_pr_rural app.tests.test_pr_addresses app.tests.test_pr_rural app.tests.test_address_search
```

The builder uses address nodes and points inside valid closed ways. Each point must fall within one municipio.
It uses the mapped city when present and accepts the containing municipio as a search qualifier. It uses an
urbanización only when the address identifies one. Coverage varies by municipio. `PR.coverage.json` lists
house counts for all 78, reasons for skipped objects, rural coverage, source fingerprints and the SQLite checksum.
A missing house number has no exact address result. Omitting `--rural` builds the smaller house-only index.
For reproducible builds use the release's four archived rural inputs together with its two identified OSM and
municipio inputs. Fetching again requests the publisher's current edition of each endpoint.

Road measures come from [Puerto Rico HPMS 2024](https://geo.dot.gov/server/rest/services/Hosted/HPMS_FULL_PR_2024/FeatureServer/0).
Area labels come from [Census barrios](https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Places_CouSub_ConCity_SubMCD/MapServer/1)
and [ZIP Code Tabulation Areas](https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/PUMA_TAD_TAZ_UGA_ZCTA/MapServer/1).
School names, directions and coordinates come from [NCES EDGE, 2024–25](https://nces.ed.gov/opengis/rest/services/K12_School_Locations/EDGE_GEOCODE_PUBLICSCH_2425/MapServer/0).

The comparison in `tools/evaluate_pr_rural.py` uses public [HRSA health center site addresses](https://gisportal.hrsa.gov/server/rest/services/HealthCareFacilities/PrimaryHealthCareFacilities_FS/MapServer/0),
public NCES addresses, synthetic spoken directions, ordering variants and ambiguous inputs.
It checks all seven extracted fields and compares results from the same offline index, including empty results and qualifier warnings.
Run it with the SQLite path and a new output filename. Add `--gemma` to run the same queries through Lastbook's
local runner with its pinned model. Set `LASTBOOK_MODEL_DIR` to the model directory and `LASTBOOK_DATA` to a writable test library.

For local use, close the library and extract the single ZIP member, `derived/geo/addresses/PR.sqlite`,
under `LastbookData/` and open it with the updated reader. For a release, upload the ZIP to the Lastbook
download URL in `PR.manifest.json`, verify the downloaded size and SHA-256, and replace the PR entry in
`address_indexes` in the release manifest. If using the per-state publisher cache, replace its saved
`PR` entry in `derived/packs/address-indexes.json` as well. The ZIP contains a separate ODbL database.
Credit © OpenStreetMap contributors when redistributing the address data. [OpenStreetMap copyright and attribution](https://www.openstreetmap.org/copyright)

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

## What is tied to the United States

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

## Checking a map change

- A change to a layer in `web/map.js` is a change you can see: include screenshots in light and dark mode.
- A change to a pack or map tool: `packaging/test_pack_tools.py` and `packaging/scan_pack.py` check what a map set may
  hold, and `scan_pack.py` lists the allowed files under `derived/geo/` (`GEO_FILES`).
- Nothing a contributor adds may make the app open a connection. New data comes in through a build tool and ships as a
  file.
