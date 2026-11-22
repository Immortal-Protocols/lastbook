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

## Opening a locally built map on Windows

The setup picker lists published maps. To preview a map you built, keep it in its own writable folder with
`map-set.json` at the top and the map files under `derived/geo/`. The desktop app also requires a
`library-data/catalog.json` in that folder. For a new map-only folder, the commands below create an empty
catalog without a byte order mark. Keep any existing catalog intact.

Open PowerShell and replace `C:\path\to\LastbookData` with your map folder. This example uses the default
location of the installed Windows app.

```powershell
$map = "C:\path\to\LastbookData"
$library = Join-Path $map "library-data"
$catalog = Join-Path $library "catalog.json"
if (-not (Test-Path -LiteralPath $catalog)) {
    New-Item -ItemType Directory -Path $library -Force | Out-Null
    Set-Content -LiteralPath $catalog -Value '[]' -Encoding ASCII
}
& "$env:LOCALAPPDATA\Programs\Lastbook\Lastbook.exe" --data $map
```

Select **Map** in Lastbook and look up a place within the map's coverage to check that the detail loads.

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

If the Puerto Rico index is unavailable or has no applicable rural result, the desktop reader continues with ordinary installed address or place lookup. Words such as “Exit” or “Salida” in another region’s street name do not stop that lookup. An exact street match takes precedence over an approximate road pin; a street prefix does not. House-number and parcel-number misses do not guess a nearby place. Parcel continuation requests do not restart ordinary lookup.

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

When the barrio is in the saved gazetteer, `Barrio Las Peñas, Villa Ejemplo` finds that place even if a parcel records only `BO. LAS PEÑAS` as its address. Include a lot, sector, road or another specific address detail to search the parcel wording. Recorded wording remains available when the gazetteer has no matching place.

Newly prepared indexes also match reordered labelled fields with or without a final period on the barrio, sector or lot. Internal kilometer decimals and the supplied lot, sector, municipio and ZIP still have to agree. The index keeps the original wording and signatures for older readers.

Newly prepared indexes also store sparse lookup aliases for repeated field-ending periods, empty comma fields before words, and comma spacing in literal text. Alias creation preserves the stored signatures and display wording. The CSV formatter preserves decimal commas inside explicit kilometer measures. It does not turn a comma-separated pair of road numbers into a decimal road. Aliases do not combine numeric comma sequences or reorder relative directions. Rebuild a prepared index to add them; older indexes remain readable.

A tight comma after a kilometer value is read as a decimal (`km 4,123`); a source that intended a separate house number needs a clearer separator.

Non-placeholder CRIM and consultation wording that cannot be parsed is retained for an exact paste with its municipio. A municipio or ZIP alone does not become a parcel address. Unparsed wording does not supply inferred road, lot or sector fields.

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

#### Build or use a local index

The reader and builder do not fetch address records. This change does not ship a Puerto Rico index or expand
the coverage of an existing one. House-number lookup is limited to house numbers stored in the installed
index. Parcel wording and boundaries require a separately supplied index or source inputs; an address-only
index is not a substitute for that coverage.

On a separate build machine with the required Python dependencies already installed, the offline builder
can assemble an index from files you already have permission to use:

```sh
python tools/build_pr_addresses.py puerto-rico.osm.pbf municipios.geojson output --rural rural-inputs --parcels parcel-inputs
```

Omit `--parcels` for roads and schools without parcel search, or both optional arguments for house
numbers only. Compatible parcel inputs may include a locally supplied physical-address CSV via
`--crim-addresses`. These options do not grant permission to acquire or share the underlying records.
The output includes a coverage report so you can see what was actually indexed by municipio.

To try a compatible index locally, quit Lastbook, keep a backup of the existing index, and place the
prepared `PR.sqlite` at `derived/geo/addresses/PR.sqlite` inside the Lastbook data folder. Reopen the reader
and search offline. Parcel boundaries are candidates, not confirmed entrances.

Run the offline reader and builder checks with the synthetic fixtures:

```sh
python -m unittest app.tests.test_address_search app.tests.test_pr_addresses app.tests.test_pr_rural app.tests.test_pr_parcels tools.test_build_pr_addresses tools.test_build_pr_rural tools.test_build_pr_parcels
```

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
[REGIONS-PY.md](REGIONS-PY.md) does the same for Paraguay as one country-wide region.
[REGIONS-IE.md](REGIONS-IE.md) does the same for the island of Ireland, including Northern Ireland, as one region.
[REGIONS-GB-LONDON.md](REGIONS-GB-LONDON.md) does the same for Greater London as one region.
[REGIONS-ES.md](REGIONS-ES.md) does the same for Spain's 17 autonomous communities and its two autonomous cities.
[REGIONS-FR.md](REGIONS-FR.md) does the same for France's 18 regions, with figures from a trial build.
[REGIONS-CL.md](REGIONS-CL.md) does the same for Chile's 16 regions.
[REGIONS-CL-DPA2023.md](REGIONS-CL-DPA2023.md) adds a DPA 2023 companion study and paired Spanish text for Chile.
[REGIONS-AE.md](REGIONS-AE.md) does the same for the United Arab Emirates, proposed as one map for all seven emirates.
[REGIONS-IN.md](REGIONS-IN.md) does the same for India's 28 states and 8 union territories.
[REGIONS-PK.md](REGIONS-PK.md) does the same for Pakistan's provinces and territories, with Islamabad and Rawalpindi
as one map.
[REGIONS-MB.md](REGIONS-MB.md) does the same for the Canadian province of Manitoba.
[REGIONS-DK.md](REGIONS-DK.md) does the same for Denmark's 5 regions.
[REGIONS-AT.md](REGIONS-AT.md) does the same for Austria's nine states.

[REGIONS-MX.md](REGIONS-MX.md) does the same for Mexico's 32 states (entidades federativas).

[REGIONS-BR.md](REGIONS-BR.md) does the same for Brazil's 26 states and the Federal District (Distrito Federal), 27 in all.

[REGIONS-BO.md](REGIONS-BO.md) does the same for Bolivia as one country-wide region, with its nine departments as an
alternative.

### To do: maps for every place on Earth

The goal is a detailed map for any place a person lives.

- [ ] **Region ids.** The manifest already accepts map ids such as `DE-BE` and `CA-ON`. Address-index ids in
  `engine/setup/manifest.py` and the address-index filenames carried over by `engine/setup/install.py` still use
  two capital letters. The map builders in `packaging/state_maps.py` and `packaging/build_packs.py` use US regions.
  Most proposals above use ISO 3166-2 ids to avoid reusing US state codes such as `DE` and `CA`.
- [ ] **Sources.** Pick an open replacement for each US dataset, region by region, with its licence. The region
  proposals above do this.
- [ ] **No Southern California box.** `server.py` assumes `map.sqlite` covers Southern California (`_poi_sources`,
  `socal_classes`).
- [ ] **Setup.** First run asks for a US state map (#267). Installing several maps or a locally built map through
  Setup is #53. A hand-built library already opens with [`--data`](#opening-a-locally-built-map-on-windows).
- [ ] **Address search.** It knows US state names and US street words. Other countries write the number after the
  street, fold accents, or have no postcode.
- [ ] **Units.** The map shows distances in miles above 1.6 km and contour lines in feet (`web/map.js`).
- [ ] **Emergency number** for the person's country (#261).

The design discussion is in #23, #25, #31 and #95.

## Building the place finder for a region outside the US

`tools/build_places_region.py` builds the two files the app already reads — `places.sqlite` (`place` +
`place_fts`) and the `poi` table of `national.sqlite` — from one OpenStreetMap extract, so a region does not
need a federal gazetteer of its own. Each region writes into its own directory
(`derived/geo/regions/<region>/` by default), so a regional build cannot truncate the shared databases.
Before any database write, the tool checks both target files read-only and refuses existing databases without
its builder marker or with a different region marker, with or without `--fresh`. `--fresh` only clears owned
target files and also refuses a directory containing other SQLite databases.
Merging the per-region files into the shipped packs stays with the regional pipeline that calls this tool.

```bash
python3 tools/build_places_region.py australia-latest.osm.pbf --region Australia
python3 tools/build_places_region.py 'New Zealand'.osm.pbf --region 'New Zealand' --bbox=166,-48,179,-34
# only part of an extract, or another directory:
python3 tools/build_places_region.py oceania.osm.pbf --region 'New South Wales' --bbox=141,-38,154,-28 \
    --out derived/geo/regions/au-nsw
```

- `--bbox` is **west,south,east,north** in degrees — longitude first, the order a Geofabrik country box and a
  GeoJSON envelope use, so a region's box can be passed straight through. Before reading the extract or
  touching output, the tool rejects non-finite numbers, longitude outside [-180,180], latitude outside [-90,90],
  west > east or south > north. A valid box matching nothing produces a warning.
- `--no-poi` writes only `places.sqlite`. Where a region map from the map pipeline already fills the `poi`
  table from the same extract, the place finder is the only part missing and this keeps the two from
  writing the same thing twice.
- **Places** come from `place=city/town/village/hamlet/suburb/…`, as nodes or as areas, with the rank order
  the finder sorts by (city 1, town 2, village 3, hamlet 4, suburb 5). A `name:zh` (or `name:en/ru/es/fr/ar`)
  goes in front of `detail`, which `place_fts` indexes, so the finder matches other-language queries:
  `悉尼` finds Sydney, `悉尼唐人街` finds Chinatown.
- **Help points** are `amenity=hospital/clinic/doctors/dentist/pharmacy/police/fire_station/drinking_water/
  shelter/toilets/fuel/water_point`, `emergency=ambulance_station/water_tank`,
  `shop=supermarket/convenience/hardware/doityourself` and `tourism=camp_site/alpine_hut/wilderness_hut`.
  Closed ways and multipolygons are read as areas (a hospital drawn as a building is not dropped), and
  unnamed help points are kept.
- The class says what the thing is: `drinking_water=no` is `water_point`, a firefighting `emergency=water_tank`
  stays `water_tank`, an `emergency=ambulance_station` stays `ambulance_station` instead of being relabelled as
  a fire station. `amenity=shelter` is a bus shelter in much of the world: a shelter is kept when it is
  tagged `weather_shelter`/`basic_hut`, or when it has a name and no `shelter_type`. Other shelter types and
  anonymous shelters with no type are excluded. Classes with no layer yet are in the data but not drawn,
  as the US classes already are.
- **Australia**, from the Geofabrik extract of 17 November 2026: 39,563 places and 88,218 help points,
  6.8 MB + 9.1 MB. That is more than the node-only version did — suburb and island polygons are read as
  places, hospitals and clinics mapped as buildings are kept, and unnamed help points such as public toilets
  and drinking-water taps no longer need a name to be useful. Running the same region again adds no
  duplicates.

`tools/test_build_places_region.py` checks the schema, the rank order, the `place_fts` prefix query in English
and Chinese, the shelter filter, the meaning of the water and ambulance tags, nodes and polygons, unnamed
points, bbox order and invalid-coordinate rejection, a rerun without duplicates, and byte-for-byte protection
of shared or other-region databases on normal/fresh builds and rejected input. It needs
only pyosmium (already a build-time dependency in `tools/build_coast.py`) and no data folder.

The data is OpenStreetMap, ODbL: a pack built from it must carry the attribution the other OSM layers already do.

## Checking a map change

- A change to a layer in `web/map.js` is a change you can see: include screenshots in light and dark mode.
- A change to a pack or map tool: `packaging/test_pack_tools.py` and `packaging/scan_pack.py` check what a map set may
  hold, and `scan_pack.py` lists the allowed files under `derived/geo/` (`GEO_FILES`).
- Nothing a contributor adds may make the app open a connection. New data comes in through a build tool and ships as a
  file.
