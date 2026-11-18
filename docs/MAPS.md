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
| Puerto Rico address index | `tools/build_pr_addresses.py` | OpenStreetMap addresses and Census boundaries, with optional measured roads, public schools, CRIM parcels and permit address records |
| a state map | `packaging/build_packs.py map <ST>`, published by `packaging/state_maps.py` | The base map, then every row inside the state's box |

Each tool's header says what it reads, what it writes and the licence of its source. Read it before you run one: some
expect source files that are hundreds of gigabytes.

### Puerto Rico street addresses and land parcels

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
  postal areas. Road estimates label unverified sectors, interior flags and landmarks. An explicit lot or interior access name needs a matching parcel record.

An indexed match appears immediately. When that lookup misses and local AI is enabled and available, Gemma
reads free-form directions such as `Por la 916, en el kilómetro cuatro punto cuatro, barrio Cerro Gordo de San Lorenzo`.
Lastbook checks the proposed road, kilometer, place names and other qualifiers against the text, then searches the
same on-device index. Gemma keeps the supplied solar or lote, sector and interior access name or number.
It can read a parcel address that omits the kilometer. A result from this path displays the interpretation. A busy, disabled or absent model leaves
the ordinary reader available. A map request stops waiting after 60 seconds.

When a rural query names the municipio, the reader also checks the original address on individual SIP and ARPE permits. It can recognize reordered labelled details, abbreviations, and Spanish road and kilometer numbers spoken aloud. A matching permit appears first with its recorded wording. Permits that use relative directions or multiple roads require the literal wording for this match. Other matching parcels follow, and each land boundary appears once. Older packs use their existing structured search.

When the directions match land records, the map outlines the possible parcels and numbers the pins.
Open **Show matches** to compare them. Each row shows the recorded road and kilometer, when known.
A solar, sector or interior detail helps distinguish parcels on the same road. The barrio and municipio
appear underneath. Select a pin or a row to inspect the boundary. **All matches** returns to the group.
**Show more parcels** adds the next page. Each candidate satisfies the supplied lot, sector and interior details.
Even a single candidate is labeled **Possible parcel**. When a source lists the road and area
but omits the requested kilometer, the result says **km unrecorded**. The parcel marker lies
within the recorded land boundary. Its position does not identify an entrance or a building.
These screenshots use invented parcels. [Numbered boundaries](pr-parcels-map.png) · [Match list](pr-parcels-list.png)

If a property document gives a **número de catastro**, pasting it into the same box opens the recorded
land boundary directly. The reader accepts an 11-digit land number with or without hyphens and a full
account number with a recorded suffix. Leading zeros count.

To build a parcel-enabled Puerto Rico pack, use Python 3.11 or newer in a separate build environment on a computer with internet access. The command fetches the islandwide public inputs directly from their publishers and writes `Lastbook-Addresses-PR.zip`, `PR.sqlite` and `PR.coverage.json` in the chosen directory. Reusing the directory reuses its source files. Using a new directory fetches a new snapshot.

```sh
python -m pip install osmium==4.3.2 shapely==2.2.0
python tools/prepare_pr_address_index.py derived/pr-addresses
```

The builder uses address nodes and points inside valid closed ways. Each point must fall within one municipio.
It uses the mapped city when present and accepts the containing municipio as a search qualifier. It uses an
urbanización only when the address identifies one. Coverage varies by municipio. `PR.coverage.json` lists
house counts for all 78, reasons for skipped objects, rural coverage, source fingerprints and the SQLite checksum.
The parcel fetcher reads numbered land polygons from the February 2025 CRIM layer. It also reads
physical addresses and cadastral numbers from the SIP and ARPE permit layers. Many ARPE numbers start with a two-digit CRIM municipio code. The builder accepts those records when the code, the permit's municipio and the indexed municipio of the parcel agree. A multi-parcel permit or conflicting municipality cannot supply a prefixed match.

The November 2026 build found 1,292,468 distinct land numbers. The two permit layers supplied searchable numbered-road addresses for **62,164 parcels across all 78 municipios**. Of these, 52,816 had at least one recorded kilometer. The fetcher requests only the land number, geometry or directions, municipio and the source record identifier. See the counts for each municipio and the results of searching 234 real permit addresses. [Municipio coverage and search results](pr-parcel-coverage.md) · [CRIM municipio codes](https://portal.crim360.com/crimpr/CMS/DOCUMENTOS/download/362.pdf)
[CRIM parcel boundaries](https://sigejp.pr.gov/server/rest/services/crim/crim_feb_2025/MapServer/0) ·
[SIP permits](https://sigejp.pr.gov/server/rest/services/MIPR/Permisos/MapServer/8) ·
[ARPE permits](https://sigejp.pr.gov/server/rest/services/MIPR/Permisos/MapServer/16)

The public build uses the land number to connect the address on a permit to its mapped boundary.
It works with those public sources alone. If a builder already has a CRIM physical-address CSV, it can
supply extra directions with `--crim-addresses file.csv`. Accepted headers include
`número de catastro,dirección física,municipio` and `catastro,address,municipio`. The builder reads
those three fields and reports the additional coverage separately.

#### Prepare a municipio for offline use

Before losing connectivity, build the parcel-enabled index above or start with a copy of an existing parcel-enabled `PR.sqlite`. From this checkout and the same Python environment, run the municipal builder. For example, to add the Planning Board’s land-use consultation records for Utuado:

```sh
python tools/prepare_pr_municipio.py derived/pr-addresses/PR.sqlite prepared/PR.sqlite --municipio Utuado --planning-board
```

This downloads the parcel number, municipio and two location fields from the [Planning Board consulta layer](https://sigejp.pr.gov/server/rest/services/MIPR/Permisos/MapServer/20). A consultation can describe a tract shared by several homes. Coverage depends on which parcels appear in the source. The command reports how many wordings it added and how many additional parcels now have searchable wording.

For a local CRIM physical-address file, use `--crim-addresses file.csv` with the headers above. You can combine both options, or run with just the CSV while disconnected. The builder reads the selected municipio, preserves the recorded wording, and joins it only to land numbers mapped to that municipio. It creates a separate output file and keeps the input intact. To include another municipio, use the previous output as the next input and choose a fresh output path.

To use the result, quit Lastbook, keep a backup of your index, and copy the prepared `PR.sqlite` to `derived/geo/addresses/PR.sqlite` inside your Lastbook data folder. Reopen a reader built from this branch, open the map, and enter the address with its municipio. Keep the prepared file if you reinstall an official address pack. Searching works offline. For a shared description, open **Show matches** to inspect the numbered parcel boundaries.

For a build from existing inputs, run `python tools/build_pr_addresses.py puerto-rico.osm.pbf municipios.geojson derived/pr-addresses --rural derived/pr-rural-inputs --parcels derived/pr-parcel-inputs`. Omit `--parcels` for the earlier road and school index. The OSM and Census inputs are the [Puerto Rico PBF](https://download.geofabrik.de/north-america/us/puerto-rico.html) and [municipio boundaries](https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/1/query?where=STATE%3D%2772%27&outFields=NAME%2CGEOID&outSR=4326&geometryPrecision=5&f=geojson).

A missing house number has no exact address result. Omitting `--rural` builds the smaller house-only index.
To reproduce the road and school preview, use the release's four archived rural inputs and its identified OSM and municipio inputs. For a parcel build, retain the parcel input directory as well. The coverage report fingerprints the raw parcel and permit snapshots.

Run the builder and reader regressions with `python -m unittest tools.test_build_pr_addresses tools.test_build_pr_rural tools.test_build_pr_parcels tools.test_prepare_pr_municipio app.tests.test_pr_addresses app.tests.test_pr_rural app.tests.test_pr_parcels app.tests.test_address_search`.

Road measures come from [Puerto Rico HPMS 2024](https://geo.dot.gov/server/rest/services/Hosted/HPMS_FULL_PR_2024/FeatureServer/0).
Area labels come from [Census barrios](https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Places_CouSub_ConCity_SubMCD/MapServer/1)
and [ZIP Code Tabulation Areas](https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/PUMA_TAD_TAZ_UGA_ZCTA/MapServer/1).
School names, directions and coordinates come from [NCES EDGE, 2024–25](https://nces.ed.gov/opengis/rest/services/K12_School_Locations/EDGE_GEOCODE_PUBLICSCH_2425/MapServer/0).

The comparison in `tools/evaluate_pr_rural.py` uses public [HRSA health center site addresses](https://gisportal.hrsa.gov/server/rest/services/HealthCareFacilities/PrimaryHealthCareFacilities_FS/MapServer/0),
public NCES addresses, synthetic spoken directions, ordering variants and ambiguous inputs.
It checks the extracted road, kilometer, locality, ZIP, interior, sector, landmark, lot and access fields and compares results from the same offline index, including empty results and qualifier warnings.
Run it with the SQLite path and a new output filename. Add `--gemma` to run the same queries through Lastbook's
local runner with its pinned model. Set `LASTBOOK_MODEL_DIR` to the model directory and `LASTBOOK_DATA` to a writable test library.
Use `--live-map` to exercise the production place finder. This mode reads the supplied SQLite file from the test library's
`derived/geo/addresses/PR.sqlite`. The release's public JSON Lines results can also be scored with `--replay`.
With the same model settings, run `LASTBOOK_TEST_PARCEL_MODEL=1 python -m unittest app.tests.test_pr_parcels`
to exercise five parcel directions against invented boundaries, including a conflicting interior and an omitted kilometer.

For local use, close the library and extract the single ZIP member, `derived/geo/addresses/PR.sqlite`,
under `LastbookData/` and open it with the updated reader. For a release, upload the ZIP to the Lastbook
download URL in `PR.manifest.json`, verify the downloaded size and SHA-256, and replace the PR entry in
`address_indexes` in the release manifest. If using the per-state publisher cache, replace its saved
`PR` entry in `derived/packs/address-indexes.json` as well. The OSM address features are available under the ODbL.
Credit © OpenStreetMap contributors when redistributing them. The CRIM service item lists no redistribution terms.
Confirm permissions for the cadastral and permit sources before distributing a combined archive.
[Planning Board parcel service item](https://sigejp.pr.gov/portal/sharing/rest/content/items/cb0f3da3de93455b9515e6a3392d795b?f=pjson) [OpenStreetMap copyright and attribution](https://www.openstreetmap.org/copyright)

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
