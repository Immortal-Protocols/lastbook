# A detailed map of Bangkok (`TH-10`): how it is built and what it holds

This is the first map built from [REGIONS-TH.md](REGIONS-TH.md): Bangkok's own administrative area, `TH-10`, with the
box that proposal gives it. The six-province grouping ("Bangkok and Vicinities") is left for later and would get its
own id, so `TH-10` keeps one meaning.

It adds two build tools and no app code. The map is not downloaded by setup and is not in any pack: the shared way to
describe, install and publish regions is still being worked out, and this gives it a concrete map to carry.

## What it is

`tools/build_region_map.py` reads one OpenStreetMap extract and writes a map set in the shape of a US state map
(`packaging/build_packs.py`), using the files, tables and classes [MAPS.md](MAPS.md) describes:

| File | Holds |
|---|---|
| `derived/geo/national.sqlite` | Streets, railways, canals and rivers, water, land use, building outlines, place labels, the sea, and the help points (`feat`, `feat_idx`, `poi`, `meta`) |
| `derived/geo/map.sqlite` | The same tables with no rows, as in a state map |
| `derived/geo/places.sqlite` | The place finder (`place`, `place_fts`) |
| `derived/geo/national-status.json`, `socal-cells.json` | As in a state map |
| `map-set.json` | The region id, each file and its size |

The rows are in `national.sqlite` and not in `map.sqlite` for one reason: the engine draws pins from `map.sqlite` only
inside a box around Southern California (`_poi_sources` in `server.py`). With the rows in `national.sqlite`, tiles,
pins, nearest help and place search all work with the engine as it is.

## Build it

The build machine needs Python 3.11 or later and pyosmium, which `tools/build_coast.py` already uses. Nothing else is
installed, and the tool downloads nothing.

```bash
# 1. The source: Geofabrik's Thailand extract (OpenStreetMap, ODbL 1.0). About 315 MB.
curl -LO https://download.geofabrik.de/asia/thailand-latest.osm.pbf
curl -LO https://download.geofabrik.de/asia/thailand-latest.osm.pbf.md5 && md5sum -c thailand-latest.osm.pbf.md5

# 2. A build environment with pyosmium.
python3 -m venv derived/buildenv && derived/buildenv/bin/pip install osmium

# 3. Build. The box is TH-10's box with the 0.15 degree margin, from REGIONS-TH.md.
derived/buildenv/bin/python tools/build_region_map.py thailand-latest.osm.pbf \
    --id TH-10 --name Bangkok --bbox 100.17,13.34,101.09,14.11 --out derived/regions

# 4. Check the files, then check that the engine can use them with every connection blocked.
python3 tools/check_region_map.py derived/regions/TH-10
python3 tools/check_region_map.py derived/regions/TH-10 --engine \
    --find Siriraj --find สยาม --find "Lumphini Park" --near 13.7649,100.5383
```

The output goes to `derived/regions/TH-10/`, with a report beside it in `derived/regions/TH-10.build.json`. The tool
refuses to write into a folder that already holds a map, and it never touches `derived/geo/`, so an installed US map is
left as it is. `derived/` is not kept in this repository.

To look at it in the app's interface, give the engine a data folder that holds the map and an empty library:

```bash
mkdir -p /path/to/BangkokData/library-data && echo '[]' > /path/to/BangkokData/library-data/catalog.json
cp -R derived/regions/TH-10/derived derived/regions/TH-10/map-set.json /path/to/BangkokData/
python3 server.py --data /path/to/BangkokData --port 8890
# then open the address it prints, choose Map, and go to:  #/map?lat=13.75&lon=100.52&z=12.5
```

The map opens on the United States, because the home view is set there; the address above, or a place search, moves it
to Bangkok.

## The build this was checked with

| | |
|---|---|
| Source file | `thailand-latest.osm.pbf`, 330,389,097 bytes |
| Source SHA-256 | `6c358170dc2be7e647ce651696d8ec0e25719f78192f4827597ac1aca78e9b1e` |
| Source MD5 (matches Geofabrik's `.md5`) | `b148cf8d3cedc1f2c5d29cc2e8d264ca` |
| OpenStreetMap data up to | 2026-11-16T21:22:36Z (from the file's header) |
| Built on | 17 November 2026, macOS 26.5 on Apple M4, Python 3.13.2, pyosmium from PyPI |
| Build time | about 150 seconds, reading the whole country and keeping the box |
| Box | 100.17, 13.34, 101.09, 14.11 (west, south, east, north) |

| File | Bytes | SHA-256 |
|---|---|---|
| `derived/geo/national.sqlite` | 191,692,800 | `534365f3fa8cbb42127e8493862aab9d959727c632f31031816218458768c007` |
| `derived/geo/map.sqlite` | 36,864 | `3401c5f02880faa6d229e87a5fbf12add00b59fa83c08113d5de142ab3df999f` |
| `derived/geo/places.sqlite` | 1,822,720 | `a4a294ebf941ce9089614157b31b7551c764acd4b7d30fc79932c008a74576e6` |
| `derived/geo/national-status.json` | 60 | `2abec27e8b829a5600ad260e0e119dbb2309aab1fa825c4cd65e1be3e996a631` |
| `derived/geo/socal-cells.json` | 2 | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |

The files hold no build time, so the same extract and options give the same bytes. Two builds run side by side on the
machine above gave identical checksums for all five files. Whether another SQLite version or platform gives the same
bytes was not tested; the counts below should match in any case. Geofabrik replaces `thailand-latest` every day, so a
later download gives a different source checksum and slightly different counts.

What the map holds:

| Layer | Features | | Layer | Features |
|---|---|---|---|---|
| Roads | 589,977 (63,295 with a name or number) | | Land use and parks | 31,898 |
| Building outlines | 514,659 | | Water areas | 9,896 |
| Canals, rivers and drains | 9,465 | | Wetland | 4,284 |
| Place labels | 1,871 | | Railways | 1,138 |
| Sea | 1 polygon, cut to the box | | Beaches | 2 |

Help points: 12,523 in 40 classes, 8,837 of them with a name. The largest: convenience stores 2,850, schools 1,238,
fuel 1,064, parks 875, toilets 862, shelters 698, supermarkets 538, hardware 513, pharmacies 397, fountains 352,
hospitals 298, drinking water 251, clinics 224, dentists 215, police 164, doctors 123, fire stations 52. The full list
is in `TH-10.build.json`.

The place finder has 10,708 rows: 1,871 places (8 cities, 59 towns, 52 suburbs, 186 quarters, 853 villages, 667
neighbourhoods and others) and 8,837 named help points. 3,931 rows carry a second name.

## What was checked, and how

`tools/check_region_map.py` reads the files and reports each check on a line. On the build above, all 37 file checks
and all 10 engine checks passed. With `--engine` it copies the map into a fresh data folder with an empty library,
replaces `socket.connect` and `socket.create_connection` with a function that raises, loads `server.py`, and makes the
calls the app makes:

- **Map display.** `map_tile` at zoom 10, 13 and 16 around 13.7649, 100.5383: roads, water, land, railways and place
  labels at the wider zooms, building outlines at 16.
- **Pins.** `pins` for hospitals, clinics, pharmacies, police and fire stations: 122 groups in a 0.2° square.
- **Nearest help.** `near`: a pharmacy at 0.26 km, a hospital at 0.27 km and another at 0.29 km.
- **Place search.** `places("Siriraj")` finds the quarter, Siriraj Hospital and its library; `places("สยาม")` finds
  Siam; `places("Lumphini Park")` finds the park.
- **What the app is told.** `map_contents` reports 40 kinds within the box.

It was also opened in a browser through `python3 server.py` (the library server, which serves the same `web/`
interface the desktop app shows): the map drew at city, street and coast zooms, pins and the "Nearest to the map
center" list filled in, and the search box found places typed in English and in Thai. Screenshots are in the pull
request.

**Not checked:** the packaged desktop app. The signed 1.1.10 Mac app was started with `--data` on this folder and no
window could be confirmed, so nothing is claimed for it. Installing through setup was not tried, because no installer
or manifest entry is part of this change.

`tools/test_build_region_map.py` tests the parts that need no map data: cutting a coastline to a box, closing the sea
with the sea on the south, on the north and between two coasts, joining coastline ways given in any order, and the
help-point classes, including that every class is one `tools/build_map.py` keeps.

## What is and is not in it

**In it**

- Streets and paths of every class `tools/build_map.py` draws, with the same zoom rules, plus railways (rail, light rail, subway,
  monorail and tram, as OpenStreetMap tags them).
- Canals (*khlong*), rivers and drains, lakes and ponds, wetland.
- Land use, parks and protected areas, beaches, building outlines from OpenStreetMap.
- The sea, cut to the box. `tools/build_coast.py` closes the coast towards the west, which suits California; here the
  sea is to the south, so the tool walks round the box edge with the sea on the right of the coastline.
- Place labels and help points in the classes the engine already names (`HELP` in `server.py`).
- Two names. The label is the local name (`name`, usually Thai). When a feature also has `name:en`, the place finder
  keeps it, so "Siriraj Hospital" and "โรงพยาบาลศิริราช" find the same row. `--prefer en` builds the map with English
  labels where they exist.

**Not in it**

- **Addresses.** No open address points exist for Thailand (REGIONS-TH.md), so searching for a house number finds
  nothing. Roads are in the map but not in the place finder, so a road or *soi* cannot be searched by name yet.
- **Terrain, contours and the 3D view** (`terrain.sqlite`), **crops** (`crops.sqlite`), and the **water and dam
  inventory** (`water.sqlite`). Water bodies are drawn from OpenStreetMap; there are no dam or reservoir records.
- **`buildings.sqlite`.** Outlines are in `national.sqlite`; there are no heights.
- **Government lists.** Bangkok's hospital, fire, police, drainage and flood files state no licence (REGIONS-TH.md), so
  none is used. Every point here is from OpenStreetMap.
- **Shelters as an emergency plan.** The 698 "shelter" points are OpenStreetMap structures. Bus and taxi shelters are
  left out, but none of these is an official evacuation shelter.
- **Anything outside the box.** A feature that crosses the box is kept whole. Beyond it the app draws its plain world
  base, whose coastline is coarse, so the sea's edge steps at the box boundary.

**Known limits**

- **Thai search matches from the start of a name.** The place finder's index splits words at spaces, and Thai is
  written without them. "สยาม" finds names that begin with it; "ศิริราช" does not find "โรงพยาบาลศิริราช" (the English
  name does). A fix belongs in the place finder's index, not in this builder.
- **Completeness follows OpenStreetMap.** 3,686 help points have no name, and coverage thins out away from the centre.
  Nothing was compared against an official count.
- **The page header's date** ("what was mapped by 25 Oct 2026") is fixed text for the US map. This map's own date is
  in `meta` (`data_as_of`) and is not shown yet.
- **The home view and the "US" button** still point at the United States.
- **Tile size.** A zoom-10 tile over the centre is about 1.3 MB, because every road class down to that zoom is kept
  whole, as in the US map.

## Licence and attribution

All data in this map is from OpenStreetMap, © OpenStreetMap contributors, under the Open Database License 1.0, taken
from Geofabrik's Thailand extract. A database built from it, which this map is, is offered under the ODbL as well. The
credit and the date of the data are written into `meta` in `national.sqlite` and `map.sqlite`, and into
`TH-10.build.json`. The app's map already shows "© OpenStreetMap contributors".
