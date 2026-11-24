# A detailed map of Central, with Asunción (`PY-11`): how it is built and what it holds

A second worked example for `tools/build_region_map.py`, after Bangkok
([MAP-TH-10.md](https://github.com/AngryAnt3201/lastbook/blob/a453274353b2816b4ccb0114310024ea54c970b2/docs/MAP-TH-10.md)), built with that tool unchanged. It maps Paraguay's Central department with the box [REGIONS-PY.md](REGIONS-PY.md) gives it. That box
contains all of Asunción, so the capital is in the map too.

**A prototype dependency.** The tool, its checker and the Bangkok page come from pull request #80, which is still
open. They are not in the main branch. This map was built and checked with #80 at commit
[`a453274`](https://github.com/AngryAnt3201/lastbook/blob/a453274353b2816b4ccb0114310024ea54c970b2) (AngryAnt3201/lastbook, branch `map/bangkok-th-10`). The files used, at that commit:

- [`tools/build_region_map.py`](https://github.com/AngryAnt3201/lastbook/blob/a453274353b2816b4ccb0114310024ea54c970b2/tools/build_region_map.py), the builder
- [`tools/check_region_map.py`](https://github.com/AngryAnt3201/lastbook/blob/a453274353b2816b4ccb0114310024ea54c970b2/tools/check_region_map.py), the checker
- [`tools/test_build_region_map.py`](https://github.com/AngryAnt3201/lastbook/blob/a453274353b2816b4ccb0114310024ea54c970b2/tools/test_build_region_map.py), its tests
- [`docs/MAP-TH-10.md`](https://github.com/AngryAnt3201/lastbook/blob/a453274353b2816b4ccb0114310024ea54c970b2/docs/MAP-TH-10.md), the Bangkok example and the builder's notes

If #80 changes, or is merged in another form, the build and the checks here need to be run again.

It adds no code and no app change. The map is not downloaded by setup and is not in any pack: the shared way to
describe, install and publish regions is still being worked out, and this gives it one more concrete map to carry.

REGIONS-PY.md proposes one region for the whole country, `PY`. That map was not built here. This smaller one was built
to test the tool on the part of Paraguay where most people live.

## The id and the box

- **Id.** `PY-11` is Central's ISO 3166-2 code, and the box is Central's box with the 0.15° margin from REGIONS-PY.md.
  Asunción (`PY-ASU`) lies inside that box, as REGIONS-PY.md notes. The id still means Central: this is not a map of
  the metropolitan area, which also takes in the Villa Hayes side of Presidente Hayes and would get its own id.
  Whether hyphenated codes are used at all is undecided there, so the id is the maintainers' to change.
- **PR #35** has a smaller box for the capital, `py-asu` (-57.94, -25.59, -57.34, -24.99), cut from the same extract.
- **What the rectangle holds.** Central and Asunción are about a fifth of it (19%). The rest is parts of Paraguarí
  (24%), Cordillera (13%), Presidente Hayes (12%) and Ñeembucú (12%), a corner of San Pedro (1%), and Argentina (20%),
  measured against OCHA's COD-AB department polygons. By help points the picture is different: 6,929 of 7,945 (87%) are
  in Central and Asunción.
- **The west of the box is blank.** The tool keeps everything the extract holds inside the box. Geofabrik's Paraguay
  extract ends a few kilometres past the border, so Clorinda in Argentina is in the map, and the land west of it is
  not. The box does not clip Central or Asunción.

## Build it

The build machine needs Python 3.11 or later and pyosmium. Nothing else is installed, and the tool downloads nothing.

There are two ways to build it. **Reproduce the recorded build** rebuilds this map from the same dated source file, with
#80 at the same commit, and checks the result against the checksums recorded under "The build this was checked with"
below. **A fresh build** makes the same map from today's data; its checksums and counts will differ.

The builder and checker are not in the main branch. Both ways start by taking them from #80 at the exact commit this
map was built with, into a checkout of this repository, without merging #80.

### Reproduce the recorded build

Run from the top of a checkout of this repository. The commands were run as written on macOS 27.0.1. The SHA-256
checks use `shasum`, which macOS and most Linux systems have: macOS's own `sha256sum -c` does not read a list from a
pipe.

```bash
# 0. The prototype builder and checker from pull request #80 (still open), at commit a453274.
git fetch https://github.com/AngryAnt3201/lastbook.git a453274353b2816b4ccb0114310024ea54c970b2
git checkout FETCH_HEAD -- tools/build_region_map.py tools/check_region_map.py tools/test_build_region_map.py

# 1. The dated source this map was built from: Geofabrik's Paraguay extract with data up to 16 November 2026
#    (OpenStreetMap, ODbL 1.0), 154,670,977 bytes. Check it against Geofabrik's MD5 and the recorded SHA-256.
curl -LO https://download.geofabrik.de/south-america/paraguay/paraguay-261116.osm.pbf
curl -LO https://download.geofabrik.de/south-america/paraguay/paraguay-261116.osm.pbf.md5 && md5sum -c paraguay-261116.osm.pbf.md5
echo "041dd8eab303e1f7f91ecba4692db5cfc102843dfad01b5f6d0ce94ddedc053f  paraguay-261116.osm.pbf" | shasum -a 256 -c

# 2. A build environment with the pyosmium version the recorded build used.
python3 -m venv derived/buildenv && derived/buildenv/bin/pip install osmium==4.3.2

# 3. Build. The box is Central's box with the 0.15 degree margin, from REGIONS-PY.md.
#    Write --bbox=... with "=": the box starts with a minus sign, which some Python versions read as an option.
derived/buildenv/bin/python tools/build_region_map.py paraguay-261116.osm.pbf \
    --id PY-11 --name Central --bbox=-57.98,-26.18,-57.04,-24.94 --out derived/regions

# 4. Compare the five files with the recorded checksums. Every line should say OK.
(cd derived/regions/PY-11 && shasum -a 256 -c <<'EOF'
884a726a765e8396732306807bb700ee976169ba5a4bbd5b2c953bddd47b2590  derived/geo/national.sqlite
620cabc336cb71606590f155a29b45c19ed1bebdafba44857e2ab749d7754a45  derived/geo/map.sqlite
4509db3830f8e50b6194880b8989ce896fb0003b1676e14f82996befc46bc81f  derived/geo/places.sqlite
85d352dddc7048f5ee5032f74f80f82441632a772a6b985a37f79a38a5d26143  derived/geo/national-status.json
4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945  derived/geo/socal-cells.json
EOF
)

# 5. Check the files, then check that the engine can use them with every connection blocked.
python3 tools/check_region_map.py derived/regions/PY-11
python3 tools/check_region_map.py derived/regions/PY-11 --engine \
    --find "Hospital de Trauma" --find Luque --find nemby --find lambare --find "San Lorenzo" \
    --near -25.2822,-57.6351
```

Geofabrik keeps dated files for a limited time. If `paraguay-261116.osm.pbf` is gone, only a later snapshot is
available from them: use "A fresh build" below, or a copy of the dated file from elsewhere that passes the SHA-256
check in step 1. The source file's name is written into the map, so a copy saved under another name gives different
checksums for `national.sqlite` and `map.sqlite`.

### A fresh build

Do step 0 and step 2 above, then:

```bash
curl -LO https://download.geofabrik.de/south-america/paraguay-latest.osm.pbf
curl -LO https://download.geofabrik.de/south-america/paraguay-latest.osm.pbf.md5 && md5sum -c paraguay-latest.osm.pbf.md5
derived/buildenv/bin/python tools/build_region_map.py paraguay-latest.osm.pbf \
    --id PY-11 --name Central --bbox=-57.98,-26.18,-57.04,-24.94 --out derived/regions
```

Then run the two checks in step 5. Skip step 4: Geofabrik replaces `paraguay-latest` every day, so the checksums and
some counts will differ from the ones recorded here.

To look at it in the app's interface, give the engine a data folder that holds the map and an empty library:

```bash
mkdir -p /path/to/CentralData/library-data && echo '[]' > /path/to/CentralData/library-data/catalog.json
cp -R derived/regions/PY-11/derived derived/regions/PY-11/map-set.json /path/to/CentralData/
python3 server.py --data /path/to/CentralData --port 8890
# then open the address it prints, choose Map, and go to:  #/map?lat=-25.2867&lon=-57.635&z=13
```

## The build this was checked with

| | |
|---|---|
| Source file | [`paraguay-261116.osm.pbf`](https://download.geofabrik.de/south-america/paraguay/paraguay-261116.osm.pbf), 154,670,977 bytes |
| Source SHA-256 | `041dd8eab303e1f7f91ecba4692db5cfc102843dfad01b5f6d0ce94ddedc053f` |
| Source MD5 (matches Geofabrik's `.md5`) | `afcdcfd67f68a409bc696b049df815c4` |
| OpenStreetMap data up to | 2026-11-16T21:22:36Z (from the file's header) |
| Built on | 24 November 2026, macOS 27.0.1 on Apple M5, Python 3.14.4, pyosmium 4.3.2 from PyPI |
| Build time | about 110 seconds, reading the whole country and keeping the box |
| Box | -57.98, -26.18, -57.04, -24.94 (west, south, east, north) |

| File | Bytes | SHA-256 |
|---|---|---|
| `derived/geo/national.sqlite` | 160,661,504 | `884a726a765e8396732306807bb700ee976169ba5a4bbd5b2c953bddd47b2590` |
| `derived/geo/map.sqlite` | 36,864 | `620cabc336cb71606590f155a29b45c19ed1bebdafba44857e2ab749d7754a45` |
| `derived/geo/places.sqlite` | 823,296 | `4509db3830f8e50b6194880b8989ce896fb0003b1676e14f82996befc46bc81f` |
| `derived/geo/national-status.json` | 59 | `85d352dddc7048f5ee5032f74f80f82441632a772a6b985a37f79a38a5d26143` |
| `derived/geo/socal-cells.json` | 2 | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |

The files hold no build time, so the same extract and options give the same bytes: two builds on the machine above
gave identical checksums for all five files. Whether another SQLite version or platform gives the same bytes was not
tested; the counts below should match in any case.

The map was first built on 17 November 2026 from the same bytes, downloaded that day as `paraguay-latest.osm.pbf`.
The build recorded here was made on 24 November from a fresh download of the dated file. `places.sqlite` and the two
JSON files came out byte for byte the same. `national.sqlite` and `map.sqlite` hold the source file's name, so their
checksums changed with the name and nothing else: a build from the same download saved as `paraguay-latest.osm.pbf`
gave the first build's checksums again (`0d6d89d7…` and `154f6172…`).

What the map holds:

| Layer | Features | | Layer | Features |
|---|---|---|---|---|
| Roads | 89,876 (22,002 with a name or number) | | Land use and parks | 50,775 |
| Building outlines | 768,594 | | Water areas | 12,716 |
| Rivers, streams and drains | 6,186 | | Wetland | 444 |
| Place labels | 461 | | Beaches | 27 (river and lake beaches) |
| Railways | 1 (a short preserved fragment) | | Islands | 1 (see "Known limits") |

Help points: 7,945 in 39 classes, 5,537 of them with a name. The largest: schools 1,557, parks 943, fuel 661,
convenience stores 630, pharmacies 581, water towers 432, supermarkets 381, communication towers 367, car repair 362,
hardware 323, police 304, clinics 218, hospitals 163, universities 132, dentists 118. Others: veterinary 90, toilets 45,
doctors 36, drinking water 33, fire stations 30, shelters 23, springs 11. The full list is in `PY-11.build.json`.

The place finder has 5,998 rows: 461 places (10 cities, 35 towns, 65 suburbs, 83 quarters, 38 villages, 200
neighbourhoods and others) and 5,537 named help points. 69 rows carry a second name.

## What was checked, and how

`tools/check_region_map.py` passed all 37 file checks and all 12 engine checks on the build above. With `--engine`,
every connection blocked and an empty library:

- **Map display.** Tiles at zoom 10, 13 and 16 around the centre of Asunción: roads, water, land and place labels at the
  wider zooms, 576 building outlines in one zoom-16 tile.
- **Pins.** 93 pin groups around the Plaza de los Héroes.
- **Nearest help.** Police at 0.08 and 0.13 km, pharmacies at 0.16 km.
- **Place search, with and without accents.** "Hospital de Trauma" finds the hospital; "Luque", "San Lorenzo", "nemby"
  and "lambare" find the cities of Luque, San Lorenzo, Ñemby and Lambaré. The place finder's index folds accents, so
  people can type names the way a keyboard without ñ or accents allows.
- **What the app is told.** 39 kinds, within the box.

`tools/test_build_region_map.py`: 9 tests pass with pyosmium (without it, all 9 skip).

It was also opened in a browser through `python3 server.py`, which serves the same `web/` interface the desktop app
shows. The map drew at city and street zooms in light and dark mode, pins and the "Nearest to the map center" list
filled in, and the search box found a hospital typed without accents. The browser's request log showed only requests to
the local server; the one 404 was `home-area.json`, which is meant to be absent.

**Not checked:** the packaged desktop app, and installing through setup (no installer or manifest entry is part of this).

## What is and is not in it

**In it**

- Streets and paths of every class `tools/build_map.py` draws, with the same zoom rules.
- The Paraguay River, streams and drains, lakes and ponds, wetland.
- Land use, parks, beaches and building outlines from OpenStreetMap.
- Place labels and help points in the classes the engine already names (`HELP` in `server.py`).

**Not in it**

- **Addresses.** No open address points were found for Paraguay (REGIONS-PY.md), so searching for a house number finds
  nothing. Roads are in the map but not in the place finder, so a street cannot be searched by name yet.
- **Terrain, contours and the 3D view**, **crops** and the **water and dam inventory**.
- **`buildings.sqlite`.** Outlines are in `national.sqlite`; there are no heights.
- **Government lists.** No open list of health facilities, fire stations or flood shelters was found (REGIONS-PY.md).
  Every point here is from OpenStreetMap.
- **Shelters as an emergency plan.** The 23 "shelter" points are OpenStreetMap structures: roofs, two rows of shops and
  an events hall. Bus shelters are left out. None is tagged as an emergency shelter.
- **Guaraní names as a second name.** The tool keeps `name:en` as the second name; `name:gn` is not read. Only 3 of the
  461 place labels have one.
- **Anything outside the box, or outside the extract.** A feature that crosses the box is kept whole. Beyond it, and in
  the blank west of the box, the app draws its plain world base.

**Known limits**

- **Hospital rows are not hospitals.** The 163 hospital rows are about 113 places when rows within 150 m are grouped:
  OpenStreetMap often has one hospital as a point and again as each of its buildings, and one appears 8 times. 29 have
  no name. Some rows tagged as hospitals are laboratories, consulting rooms or health posts, and few say whether they
  take emergencies. "Nearest hospital" can therefore name a place that is not one.
- **Some well-known places are not found by name.** The airport (airports are not a kept class) and Mercado 4 (only
  its police post and fire station are found). The emergency hospital is found as "Hospital de Trauma", its name in
  OpenStreetMap.
- **One stray island.** A small closed way at the river's edge in Asunción is tagged `natural=coastline` in
  OpenStreetMap, so the tool draws it as an island. Paraguay has no sea; the fix belongs in OpenStreetMap.
- **Every place's detail line says "Central"**, the `--name` given, including places in Asunción, in other departments
  and in Clorinda.
- **Completeness follows OpenStreetMap.** 2,408 help points have no name. Nothing was compared against an official
  count; for volunteer fire brigades, for example, no open list was found.
- **The page header's date** ("what was mapped by 25 Oct 2026") is fixed text for the US map; this map's date is in
  `meta` (`data_as_of`) and is not shown yet. The home view and the "US" button still point at the United States, and
  the map's credit line still lists the US sources.
- **Tile size.** A zoom-10 tile over the centre is about 0.6 MB.

## Licence and attribution

All data in this map is from OpenStreetMap, © OpenStreetMap contributors, under the Open Database License 1.0, taken
from Geofabrik's Paraguay extract. A database built from it, which this map is, is offered under the ODbL as well. The
credit and the date of the data are written into `meta` in `national.sqlite` and `map.sqlite`, and into
`PY-11.build.json`. The app's map already shows "© OpenStreetMap contributors".
