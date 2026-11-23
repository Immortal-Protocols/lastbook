# A detailed map of the Santiago Metropolitan Region (`CL-RM`): how it is built and what it holds

A worked example in Chile for the region map builder proposed in pull request #80, after its Bangkok example, built
with that tool unchanged. It maps the Región Metropolitana de Santiago with the box from the DPA 2023 study
([REGIONS-CL-DPA2023.md](REGIONS-CL-DPA2023.md)), to test that box against a real build.

**A prototype dependency.** The builder is a prototype from pull request #80, which is still open. It is not in the
main branch. This map was built and checked with #80 at commit
[`a453274`](https://github.com/AngryAnt3201/lastbook/blob/a453274353b2816b4ccb0114310024ea54c970b2) (AngryAnt3201/lastbook, branch `map/bangkok-th-10`). The files used, at that commit:

- [`tools/build_region_map.py`](https://github.com/AngryAnt3201/lastbook/blob/a453274353b2816b4ccb0114310024ea54c970b2/tools/build_region_map.py), the builder
- [`tools/check_region_map.py`](https://github.com/AngryAnt3201/lastbook/blob/a453274353b2816b4ccb0114310024ea54c970b2/tools/check_region_map.py), the checker
- [`tools/test_build_region_map.py`](https://github.com/AngryAnt3201/lastbook/blob/a453274353b2816b4ccb0114310024ea54c970b2/tools/test_build_region_map.py), its tests
- [`docs/MAP-TH-10.md`](https://github.com/AngryAnt3201/lastbook/blob/a453274353b2816b4ccb0114310024ea54c970b2/docs/MAP-TH-10.md), the Bangkok example and the builder's notes

If #80 changes, or is merged in another form, the build and the checks here need to be run again.

It adds no code and no app change. The map is not downloaded by setup and is not in any pack.

## The id and the box

- **Id.** `CL-RM` is the region's ISO 3166-2 code, as both Chile proposals use it. Whether hyphenated codes are used
  as ids is still open (REGIONS-CL-DPA2023.md, open question 1), so the id is the maintainers' to change.
- **Box.** `-71.87, -34.45, -69.61, -32.77` (west, south, east, north): the DPA 2023 box with the 0.15° margin.
  Unpadded, the DPA box is `-71.7155, -34.2910, -69.7698, -32.9219`. OpenStreetMap's own boundary for the region
  (relation tagged `ISO3166-2=CL-RM` in this extract) spans `-71.7149, -34.2917, -69.7691, -32.9222`, so the DPA box
  and OpenStreetMap agree to within 0.001°, and the padded box clips nothing of the region.
- **The other Chile proposal.** [REGIONS-CL.md](REGIONS-CL.md) (#133) gives `CL-RM` `-71.87, -34.44, -69.62, -32.77`
  with its margin: the same box to 0.01° (0.01° less to the south and to the east). Either would have given almost
  the same map. The two proposals differ more elsewhere (Valparaíso's island boxes and Magallanes' south edge), not
  for this region.
- **What the rectangle holds.** The region is landlocked, but the rectangle is not. By the DPA study's measure the
  region fills 56% of its unpadded box; the padded box takes in the coast of Valparaíso from Quintero to Cartagena,
  Viña del Mar, Valparaíso, Los Andes, Quillota and San Antonio, and the north of O'Higgins with Rancagua. Measured
  against OpenStreetMap's region polygon: 68.8% of help points (21,343 of 31,005), 76.3% of building outlines, 65.2%
  of roads and 54.1% of place labels are inside the region.
- **The east of the box is blank.** The eastern 0.15° lies in Argentina. Geofabrik's Chile extract ends near the
  border, so no help point lies east of -69.775. A few features that cross the border are kept whole (a protected
  area reaches -69.22).

## Build it

The build machine needs Python 3.11 or later and pyosmium. Nothing else is installed, and the tool downloads nothing.
Geofabrik offers Chile only as one country file (about 352 MB), so the region is cut from it by the box. Sizes on
this page are in MB, where 1 MB is 1,000,000 bytes.

The builder and checker are not in the main branch. Step 0 takes them from #80 at the exact commit this map was built
with, into a checkout of this repository, without merging #80.

```bash
# 0. The prototype builder and checker from pull request #80 (still open), at commit a453274.
git fetch https://github.com/AngryAnt3201/lastbook.git a453274353b2816b4ccb0114310024ea54c970b2
git checkout FETCH_HEAD -- tools/build_region_map.py tools/check_region_map.py tools/test_build_region_map.py

# 1. The source: Geofabrik's Chile extract (OpenStreetMap, ODbL 1.0). About 352 MB.
curl -LO https://download.geofabrik.de/south-america/chile/chile-latest.osm.pbf
curl -LO https://download.geofabrik.de/south-america/chile/chile-latest.osm.pbf.md5 && md5sum -c chile-latest.osm.pbf.md5

# 2. A build environment with pyosmium.
python3 -m venv derived/buildenv && derived/buildenv/bin/pip install osmium

# 3. Build. The box is CL-RM's DPA 2023 box with the 0.15 degree margin, from REGIONS-CL-DPA2023.md.
#    Write --bbox=... with "=": the box starts with a minus sign, which argparse would otherwise read as an option.
derived/buildenv/bin/python tools/build_region_map.py chile-latest.osm.pbf \
    --id CL-RM --name "Metropolitana de Santiago" --bbox=-71.87,-34.45,-69.61,-32.77 --out derived/regions

# 4. Check the files, then check that the engine can use them with every connection blocked.
python3 tools/check_region_map.py derived/regions/CL-RM
python3 tools/check_region_map.py derived/regions/CL-RM --engine \
    --find Maipú --find Providencia --find "Hospital del Salvador" --find Ñuñoa --find "San José de Maipo" \
    --find nunoa --near=-33.4378,-70.6505
```

To look at it in the app's interface, give the engine a data folder that holds the map and an empty library:

```bash
mkdir -p /path/to/SantiagoData/library-data && echo '[]' > /path/to/SantiagoData/library-data/catalog.json
cp -R derived/regions/CL-RM/derived derived/regions/CL-RM/map-set.json /path/to/SantiagoData/
python3 server.py --data /path/to/SantiagoData --port 8890
# then open the address it prints, choose Map, and go to:  #/map?lat=-33.4378&lon=-70.6505&z=16
```

Geofabrik's Chile files now sit under `south-america/chile/`; the older `south-america/chile-latest.osm.pbf` address
redirects there. `chile-latest` is replaced every day; the dated file used here is `chile-261120.osm.pbf`.

## The build this was checked with

| | |
|---|---|
| Source file | `chile-261120.osm.pbf` (from `https://download.geofabrik.de/south-america/chile/chile-261120.osm.pbf`), 352,392,606 bytes (352.4 MB), `Last-Modified` 21 Nov 2026 01:11:15 GMT |
| Source SHA-256 | `3b169b7a146f6f28c1a78a3a887d5246896f906ee09820240a3fe18c434df8d8` |
| Source MD5 (matches Geofabrik's `.md5`) | `fef09ad7ee6f28c7afc925ef68c737a4` |
| OpenStreetMap data up to | 2026-11-20T21:21:21Z (from the file's header) |
| Built on | 21 November 2026, Ubuntu 24.04.5 (Linux 7.0), Python 3.12.4, SQLite 3.45.3, pyosmium 4.3.2 from PyPI |
| Build time | 192 seconds, reading the whole country and keeping the box; peak memory 2.5 GB |
| Box | -71.87, -34.45, -69.61, -32.77 (west, south, east, north) |

| File | Bytes | SHA-256 |
|---|---|---|
| `derived/geo/national.sqlite` | 187,408,384 | `a6fc979c62aaef127c84399012cea497bc58c255ae2edf5ec171aed2f23152b8` |
| `derived/geo/map.sqlite` | 36,864 | `cd617d0747452f2f91a5fc02a66095bc04a8d0d0a23ed0320e5db527f77ef22f` |
| `derived/geo/places.sqlite` | 4,775,936 | `54d7a427d55475cbaf422e0253f4dcc61a9eae7bd00d9172828b86e26b530956` |
| `derived/geo/national-status.json` | 59 | `1e3b42cd9a61c002837d73f22c8c1924951fca53ca13eec0cfad856847b0d364` |
| `derived/geo/socal-cells.json` | 2 | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |

The map set is 192,221,245 bytes in all (192.2 MB). The files hold no build time, so the same extract and
options give the same bytes: a second build on the same machine (194 seconds) gave identical checksums for all five
files. Whether another SQLite version or platform gives the same bytes was not tested.

What the map holds:

| Layer | Features | | Layer | Features |
|---|---|---|---|---|
| Roads | 384,121 (178,028 with a name or number) | | Land use and parks | 69,282 |
| Building outlines | 411,626 | | Water areas | 5,047 |
| Rivers, streams and drains | 24,205 | | Wetland | 484 |
| Place labels | 6,518 | | Beaches | 171 |
| Railways | 1,014 (890 rail, 123 metro, 1 monorail) | | Sea | 2 polygons |
| | | | Islands | 266 (coastal rocks) |

Help points: 31,005 in 40 classes, 22,945 of them with a name. The largest: parks 7,458, schools 5,032, convenience
stores 3,488, kindergartens 1,801, pharmacies 1,744, supermarkets 930, car repair 861, communication towers 826,
fuel 778, clinics 683, doctors 647, toilets 632, hardware 569. Emergency services: fire stations 333, police 287,
hospitals 125, shelters 80, drinking water 140, springs 26, water towers 223. The full list is in `CL-RM.build.json`.

Inside the region itself (OpenStreetMap's polygon): hospitals 73, clinics 473, doctors 377, pharmacies 1,308, fire
stations 193, police 174, fuel 525, supermarkets 606, schools 3,543, shelters 45, drinking water 103.

The place finder has 29,463 rows: 6,518 places (11 cities, 62 towns, 77 suburbs, 81 quarters, 223 villages, 3,581
neighbourhoods, 2,403 hamlets, 80 localities) and 22,945 named help points. 132 rows carry a second name (`name:en`).

## What was checked, and how

The checker, `tools/check_region_map.py` from #80 at `a453274`, passed all 37 file checks and all 13 engine checks
on the build above. With `--engine`, every connection blocked and an empty library:

- **Map display.** Tiles at zoom 10, 13 and 16 around the Plaza de Armas: 4,999 roads in the zoom-10 tile, 257
  building outlines in the zoom-16 tile.
- **Pins.** 179 pin groups around the Plaza de Armas.
- **Nearest help.** Pharmacies at 0.09 to 0.11 km, police (1 Comisaría Santiago Central) at 0.33 km.
- **Place search, with and without accents.** "Maipú", "Providencia", "Ñuñoa" and "San José de Maipo" find the
  comunas; "Hospital del Salvador" finds the hospital. "nunoa", typed without ñ or accent, finds Ñuñoa: the place
  finder's index folds accents.
- **What the app is told.** 40 kinds, within -71.87, -34.45, -69.78, -32.76.

`tools/test_build_region_map.py` (from #80 at `a453274`): 9 tests pass with pyosmium.

**The sea.** The tool cut the coastline to the box and closed it into 2 sea polygons: one from the north edge near
Quintero down to the west edge at -33.95 (Valparaíso, Viña del Mar, San Antonio), and a small one in Quintero bay.
Checked against the map's own rows: no place label, 1 of 63,348 coastal building outlines and 33 of 69,997 coastal
roads have their centre in the sea, all along the shoreline; the beach points sit on the shoreline too. Tiles over
San Antonio draw sea, beach and land correctly. The coast leaves the box at -33.95 because the coast south of there
lies west of -71.87.

It was also opened through `python3 server.py`, which serves the same `web/` interface the desktop app shows, in
headless Chrome with light and dark colour schemes. The map drew at city, street and coast zooms, pins and the
"Nearest to the map center" list filled in, and the search box found Hospital del Salvador. Every request went to the
local server; the only error was a 404 for `home-area.json`, which is meant to be absent. The map itself has no dark
style yet, as for the US maps: in dark mode the interface around it turns dark and the map stays light.

**Not checked:** the packaged desktop app, Windows and macOS, and installing through setup (no installer or manifest
entry is part of this).

## What is and is not in it

**In it**

- Streets and paths of every class `tools/build_map.py` draws, with the same zoom rules, including the many short
  `living_street` passages (pasajes) of Santiago's housing estates.
- The Maipo and Mapocho, their streams and canals, reservoirs such as El Yeso, wetland.
- Land use, parks, beaches, building outlines, the Pacific coast inside the box.
- Place labels and help points in the classes the engine already names (`HELP` in `server.py`).

**Not in it**

- **Addresses.** Overture holds about 1.6 million addresses in the region (REGIONS-CL-DPA2023.md), but the tool does
  not build addresses, and `tools/build_addresses.py` is US-only. Roads are not in the place finder.
- **Terrain, contours and the 3D view**, **crops** and the **water and dam inventory**. In this region terrain matters:
  the Andes rise to over 6,000 m in the east of the box.
- **Government lists.** MINSAL's health facilities and SENAPRED's layers (REGIONS-CL-DPA2023.md) are not used. Every
  point here is from OpenStreetMap.
- **Emergency points the tool does not read.** In the box, OpenStreetMap has 203 `emergency=assembly_point` (the
  meeting points for earthquakes and tsunamis), 14 `emergency=ambulance_station`, 53 defibrillators, 150
  `amenity=social_facility` (39 nursing homes, 17 shelters for people in need) and 225 health facilities tagged only
  with `healthcare=*`. None of them is in the map: the tool's classes do not include them.
- **Shelters as an emergency plan.** The 80 "shelter" points are OpenStreetMap structures. Of those in the box with a
  `shelter_type`, most are gazebos, picnic shelters and lean-tos; many have no type at all. Bus shelters are left out.
  None is tagged as an emergency shelter.
- **Anything outside the box or outside the extract.** A feature that crosses the box is kept whole (19 reach more
  than 0.05° past it, mostly parks and rivers in the Andes). East of the border the map is blank.

**Known limits**

- **Every place's detail line says "Metropolitana de Santiago"**, the `--name` given, including Viña del Mar,
  Valparaíso, Quilpué, Villa Alemana, Quillota, Los Andes, San Antonio and Rancagua, which are in other regions. 8 of
  the 11 city labels are outside the region; only Santiago, Melipilla and Colina are in it.
- **The checker's search test is too easy here.** It searches for the first word of a city name ("Santiago"), and the
  word is in every row's detail line, so it would pass with any index. The `--find` searches above are the real test.
- **Hospital rows are not all hospitals.** 125 rows group into 118 places within 150 m. Some are primary care centres
  (for example a CESFAM-SAR in Puente Alto), so "nearest hospital" can name a place without an emergency ward. 3 have
  no name.
- **Duplicates.** 132 named help points lie within 50 m of another with the same class and name, mostly where a place
  is mapped as a point and as an outline. A search for "Hospital del Salvador" lists it twice.
- **Completeness follows OpenStreetMap.** 8,060 help points have no name. Nothing was compared against an official
  count.
- **The page header's date** ("what was mapped by 25 Oct 2026") is fixed text for the US map; this map's date is in
  `meta` (`data_as_of`) and is not shown yet. The home view and the "US" button still point at the United States, and
  the map's credit line still lists the US sources (Microsoft buildings, USGS, USDA and others), though every row
  here is from OpenStreetMap.
- **Miles.** The "Nearest" list gives longer distances in miles (for example "7.9 mi"), and the scale bar shows miles
  beside kilometres, as for the US maps.
- **Tile size.** A zoom-10 tile over central Santiago (10/311/613) is 731,230 bytes (0.73 MB), with 4,999 roads.

## Licence and attribution

All data in this map is from OpenStreetMap, © OpenStreetMap contributors, under the Open Database License 1.0, taken
from Geofabrik's Chile extract. A database built from it, which this map is, is offered under the ODbL as well. The
credit and the date of the data are written into `meta` in `national.sqlite` and `map.sqlite`, and into
`CL-RM.build.json`. The app's map already shows "© OpenStreetMap contributors". No DPA 2023 data is in the map: the
DPA layer was only used, in the companion study, to choose the box.
