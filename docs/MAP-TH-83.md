# A detailed map of Phuket (`TH-83`): how it is built and what it holds

A worked example for `tools/build_region_map.py` on Thailand's Andaman coast, after Bangkok ([MAP-TH-10.md](MAP-TH-10.md))
and Central, Paraguay ([MAP-PY-11.md](MAP-PY-11.md)), built with that tool unchanged. It maps Phuket province with the
box [REGIONS-TH.md](REGIONS-TH.md) gives it. Phuket is a small island province, a place many visitors stay in, and the
coast where the 2004 tsunami struck, so it tests the tool on what a visitor would search for and on what the map can
and cannot say about a tsunami.

The tool, its checker and the Bangkok page come from pull request #80, and the Paraguay page from #152; none of them is
in this repository until they are merged. This map was built and checked with the tool as it was at commit `a453274`,
the same commit #152 used. If the tool changes before then, the build and the checks here need to be run again.

It adds no code and no app change. The map is not downloaded by setup and is not in any pack: the shared way to
describe, install and publish regions is still being worked out, and this gives it one more concrete map to carry.

## The id and the box

- **Id.** `TH-83` is Phuket's ISO 3166-2 code, as REGIONS-TH.md proposes. Whether hyphenated codes are used at all is
  undecided there, so the id is the maintainers' to change.
- **Box.** 98.10, 7.33, 98.63, 8.36 (west, south, east, north): Phuket's box with the 0.15° margin, from REGIONS-TH.md.
- **What the rectangle holds.** Measured against geoBoundaries' province outlines (the file REGIONS-TH.md computed its
  boxes from), 2,009 of the 2,297 help points (87 %) are in Phuket, 148 (6 %) on the Phang Nga side of the Sarasin
  bridge and the islands to the north-east, 2 in Krabi, and 138 (6 %) on the shore just outside the simplified
  outlines. Of the 29 hospital rows, 24 are in Phuket and 4 in Phang Nga.
- **The sea.** The tool fills the box around the land with sea, cut to the box. Here that matches the ground: the
  Andaman Sea on the west and Phang Nga Bay on the east.

## Build it

The build machine needs Python 3.11 or later and pyosmium. Nothing else is installed, and the tool downloads nothing.

```bash
# 1. The source: Geofabrik's Thailand extract of 17 November 2026 (OpenStreetMap, ODbL 1.0), 330,447,194 bytes.
#    Save it under the name the build used: the tool writes the file name into the map's meta table.
curl -L -o thailand-latest.osm.pbf https://download.geofabrik.de/asia/thailand/thailand-261117.osm.pbf
sha256sum thailand-latest.osm.pbf     # see "Reproducing this build" for the two hashes this can give

# 2. A build environment with pyosmium.
python3 -m venv derived/buildenv && derived/buildenv/bin/pip install osmium

# 3. Build. The box is TH-83's box with the 0.15 degree margin, from REGIONS-TH.md.
derived/buildenv/bin/python tools/build_region_map.py thailand-latest.osm.pbf \
    --id TH-83 --name Phuket --bbox 98.10,7.33,98.63,8.36 --out derived/regions

# 4. Check the files, then check that the engine can use them with every connection blocked.
python3 tools/check_region_map.py derived/regions/TH-83
python3 tools/check_region_map.py derived/regions/TH-83 --engine \
    --find Vachira --find ป่าตอง --find "Bangkok Hospital Phuket" --find ภูเก็ต --near 7.8961,98.2964
```

On Windows the same steps work in Git Bash, with `derived/buildenv/Scripts/python` in place of
`derived/buildenv/bin/python`. Set `PYTHONIOENCODING=utf-8` before running the checker with its output sent to a file:
otherwise Windows writes that output in its legacy code page, and the checker stops at the first line with Thai text.

To look at it in the app's interface, give the engine a data folder that holds the map and an empty library:

```bash
mkdir -p /path/to/PhuketData/library-data && echo '[]' > /path/to/PhuketData/library-data/catalog.json
cp -R derived/regions/TH-83/derived derived/regions/TH-83/map-set.json /path/to/PhuketData/
python3 server.py --data /path/to/PhuketData --port 8890
# then open the address it prints, choose Map, and go to:  #/map?lat=7.8961&lon=98.2964&z=14.5   (Patong)
# the whole island:  #/map?lat=7.95&lon=98.36&z=10.3
```

## Reproducing this build

**The tool.** `tools/build_region_map.py` and `tools/check_region_map.py` from #80 at commit
[`a453274`](https://github.com/Immortal-Protocols/lastbook/commit/a453274353b2816b4ccb0114310024ea54c970b2), #80's head
when this was checked (22 November 2026). The checks load `server.py` from the same commit.

| File at `a453274` | SHA-256 |
|---|---|
| `tools/build_region_map.py` | `552d6745a177052e16e7ed67adc0333fa22fbbd7e956bfde92fc8ef86924ecac` |
| `tools/check_region_map.py` | `7117cb462930fb17567290cc63d3a15dca996767ab2f5fed17f4ddf29dfd908d` |
| `tools/test_build_region_map.py` | `9968a5481e84201264f588b6eee70cfd130d13ffd3a8f14a8ff280df40e05c0b` |

**The input.** Geofabrik's Thailand extract of 17 November 2026, downloaded on 18 November as `thailand-latest.osm.pbf`:
330,447,194 bytes, OpenStreetMap data up to 2026-11-17T21:24:30Z, replication sequence 4955.

| | SHA-256 | MD5 |
|---|---|---|
| The file this map was built from | `6a2908238debf96dd36e5c66bbaff19da7ab1f77b08bc8e106fd78b9fa3a6759` | `de5d72d732c387d2edda85ab571230bb` |
| The dated file served today, `https://download.geofabrik.de/asia/thailand/thailand-261117.osm.pbf` | `bee5a964008e20579c55e25eef732fe99cc4022040e6f931e83bf32d53f0f406` | `e890288cabbef296f4197139726a78b4` |

**The original bytes can no longer be downloaded.** Geofabrik has since moved its dated files into a folder per country,
and the file served today differs from the original in 3 bytes, all in the file header: the replication URL changed from
`https://download.geofabrik.de/asia/thailand-updates` to `https://download.geofabrik.de/asia/thailand/updates`. Size,
replication timestamp and sequence are the same, and every OpenStreetMap data block is byte for byte the same (`cmp -l`
lists only those 3 bytes). A rebuild on 22 November 2026 from the file served today, saved as `thailand-latest.osm.pbf`,
gave the same SHA-256 for all five files listed under "The build this was checked with". How long Geofabrik keeps dated
files was not checked.

## The build this was checked with

| | |
|---|---|
| Source file | `thailand-latest.osm.pbf` (Geofabrik's file of 17 November), 330,447,194 bytes |
| Source SHA-256 | `6a2908238debf96dd36e5c66bbaff19da7ab1f77b08bc8e106fd78b9fa3a6759` |
| Source MD5 (matches Geofabrik's `.md5`) | `de5d72d732c387d2edda85ab571230bb` |
| OpenStreetMap data up to | 2026-11-17T21:24:30Z (from the file's header) |
| Built on | 17 November 2026, Windows 11 (10.0.22631), Python 3.12.7, pyosmium 4.3.2 from PyPI |
| Build time | 511 seconds, reading the whole country and keeping the box |
| Box | 98.10, 7.33, 98.63, 8.36 (west, south, east, north) |

| File | Bytes | SHA-256 |
|---|---|---|
| `derived/geo/national.sqlite` | 22,122,496 | `1ebb8d332b9a342469c1ea136eaaffe262dbff5e4514687e7dea1c0e0887893e` |
| `derived/geo/map.sqlite` | 36,864 | `72c019de2f80354e7bf2ed13acac61fd532a63778cb0361fbe7f133bd041a527` |
| `derived/geo/places.sqlite` | 217,088 | `76f948c74de775ef03d50e52ebd5e0cb7d27f0b7e501c7de188a91ba8e90ca10` |
| `derived/geo/national-status.json` | 59 | `b5a0aa874ce2dd85a0d8d9cf95e0a583c7ab9a2089dc95ee48c943e67b4cfcb1` |
| `derived/geo/socal-cells.json` | 2 | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |

The map was built once; whether a second build gives the same bytes on Windows was not tested (#80 reports identical
checksums for two builds on a Mac). Geofabrik replaces `thailand-latest` every day, so a later download gives a
different source checksum and slightly different counts.

What the map holds:

| Layer | Features | | Layer | Features |
|---|---|---|---|---|
| Roads | 29,043 (3,172 with a name or number) | | Land use and parks | 2,930 |
| Building outlines | 98,325 | | Water areas | 1,907 |
| Streams, canals and drains | 682 | | Wetland | 76 |
| Place labels | 111 | | Islands | 147 |
| Beaches | 173 | | Railways | none (Phuket has no railway) |
| Sea | 1 polygon, cut to the box | | | |

Help points: 2,297 in 39 classes, 1,180 of them with a name. The largest: convenience stores 516, pharmacies 255,
toilets 216, shelters 206, beaches 173, schools 141, supermarkets 137, fuel 105. For emergencies: police 58, clinics
32, hospitals 29, dentists 30, doctors 17, drinking water 15, fire stations 10. The full list is in `TH-83.build.json`.

The place finder has 1,291 rows: 111 places (1 city, 11 towns, 72 villages, 15 neighbourhoods, 4 quarters, 4 islands
and others) and 1,180 named help points. 273 rows carry a second name, the English one where OpenStreetMap has it.

## What was checked, and how

`tools/check_region_map.py` passed all 37 file checks and all 14 engine checks on the build above. With `--engine`,
every connection blocked and an empty library:

- **Map display.** Tiles at zoom 10, 13 and 16 around Patong beach: roads, water, land, beaches and place labels at the
  wider zooms, 219 building outlines in one zoom-16 tile.
- **Pins.** 62 pin groups around Patong.
- **Nearest help.** Pharmacies at 0.15, 0.18 and 0.19 km from the middle of Patong beach, the police at 0.28 km.
- **Place search, in both scripts.** "Vachira" finds Vachira Phuket Hospital (โรงพยาบาลวชิระภูเก็ต) by its English
  name; "Bangkok Hospital Phuket" finds it (โรงพยาบาลกรุงเทพ ภูเก็ต) and Bangkok Hospital Siriroj; ป่าตอง finds the town
  of Patong, and ภูเก็ต the city.
- **What the app is told.** 39 kinds, within 98.26, 7.47, 98.63, 8.35, the extent of the data inside the box.

`tools/test_build_region_map.py`: 9 tests pass with pyosmium.

It was also opened in a browser through `python3 server.py`, which serves the same `web/` interface the desktop app
shows. The map drew the whole island and the streets of Patong in light and dark mode, and the "Nearest to the map
center" list filled in. The browser's request log showed 63 requests, all to the local server; the one 404 was
`home-area.json`, which is meant to be absent.

**Not checked:** the packaged desktop app, and installing through setup (no installer or manifest entry is part of this).

## What is and is not in it

**In it**

- Streets and paths of every class `tools/build_map.py` draws, with the same zoom rules, for Phuket, the Phang Nga
  shore across the Sarasin bridge and the islands in the box.
- Beaches, streams, ponds, wetland, land use, parks and building outlines from OpenStreetMap.
- Place labels in Thai, with the English name as a second name where OpenStreetMap has one, and help points in the
  classes the engine already names (`HELP` in `server.py`).

**Not in it**

- **Tsunami evacuation.** For the whole box, OpenStreetMap has 2 nodes tagged `emergency=assembly_point`, 1
  `emergency=siren` and 3 with "tsunami" in their name or description (counted from the same extract; ways and areas
  not counted). The tool does not keep assembly points either. The evacuation routes and signs along the Andaman coast
  are not in this map, and OpenStreetMap is not a source for them yet. Whether the Department of Disaster Prevention
  and Mitigation publishes them as open data was not checked.
- **Addresses.** REGIONS-TH.md found no open address points for Thailand. Roads are in the map but not in the place
  finder, so a street or *soi* cannot be searched by name.
- **Terrain, contours and the 3D view**, **crops** and the **water and dam inventory**.
- **`buildings.sqlite`.** Outlines are in `national.sqlite`; there are no heights.
- **Shelters as an emergency plan.** The 206 "shelter" points are OpenStreetMap structures tagged `amenity=shelter`,
  all but one with no name. Bus shelters are left out. None is tagged as a tsunami or emergency shelter.

**Known limits**

- **Visitors' spellings find shops, not towns.** Town labels are in Thai, and their English names are kept in each
  row's detail line. Place search ranks names that start with the query before everything else, so "Patong" lists
  twelve shops, offices and pharmacies and never the town, which OpenStreetMap spells "Pa Tong" in English; "Kata"
  never finds the town; "Karon" finds it fifth and "Chalong" sixth. ป่าตอง and "Pa Tong" find it first. In a
  province full of visitors who type in Latin letters, this matters more than anywhere else built so far.
- **Hospital rows are not all hospitals.** The 29 hospital rows are 23 places when rows within 150 m are grouped, 4
  have no name, and some are clinics tagged as hospitals (Siam International Clinic and Dr. Bangla Clinic in Patong
  are shown under "Hospitals"). "Nearest hospital" can
  name a place that does not take emergencies.
- **Every place's detail line says "Phuket"**, the `--name` given, including places in Phang Nga.
- **Completeness follows OpenStreetMap.** 1,117 help points have no name. Nothing was compared against an official
  count.
- **The page header, the units and the credits are the US map's.** The header says "what was mapped by 25 Oct 2026",
  while this map's date is in `meta` (`data_as_of`, 17 November 2026). Distances are in miles at wider zooms, the search
  box asks for a "town or ZIP", the home view and the "US" button point at the United States, and the credit line lists
  US sources that are not in this map. The same holds for the Bangkok and Paraguay maps.

## Licence and attribution

All data in this map is from OpenStreetMap, © OpenStreetMap contributors, under the Open Database License 1.0, taken
from Geofabrik's Thailand extract. A database built from it, which this map is, is offered under the ODbL as well. The
credit and the date of the data are written into `meta` in `national.sqlite` and `map.sqlite`, and into
`TH-83.build.json`. The app's map already shows "© OpenStreetMap contributors".
