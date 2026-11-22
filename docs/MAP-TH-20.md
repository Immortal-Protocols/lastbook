# A detailed map of Chon Buri, with Pattaya (`TH-20`): how it is built and what it holds

A worked example for `tools/build_region_map.py` on Thailand's Eastern Seaboard, after Bangkok
([MAP-TH-10.md](MAP-TH-10.md)) and Central, Paraguay ([MAP-PY-11.md](MAP-PY-11.md)), built with that tool unchanged. It
maps Chon Buri province, with Pattaya, Si Racha, Laem Chabang and Bang Saen, with the box
[REGIONS-TH.md](REGIONS-TH.md) gives it. It is the first map built from a box that reaches into Bangkok, and it shows
how much of a neighbouring province a box can carry.

The tool, its checker and the Bangkok page come from pull request #80, and the Paraguay page from #152; none of them is
in this repository until they are merged. This map was built and checked with the tool as it was at commit `a453274`,
the same commit #152 used. If the tool changes before then, the build and the checks here need to be run again.

It adds no code and no app change. The map is not downloaded by setup and is not in any pack: the shared way to
describe, install and publish regions is still being worked out, and this gives it one more concrete map to carry.

## The id and the box

- **Id.** `TH-20` is Chon Buri's ISO 3166-2 code, as REGIONS-TH.md proposes. ISO also lists `TH-S` for Pattaya, a
  special city inside Chon Buri; REGIONS-TH.md does not propose it as a region, and it is inside this map. Whether
  hyphenated codes are used at all is undecided there, so the id is the maintainers' to change.
- **Box.** 100.51, 12.35, 101.87, 13.75 (west, south, east, north): Chon Buri's box with the 0.15° margin, from
  REGIONS-TH.md.
- **What the rectangle holds: more Bangkok than Chon Buri.** The box's north-west corner reaches 13.75° N and
  100.51° E, which takes in most of eastern Bangkok. Measured against geoBoundaries' province outlines (the file
  REGIONS-TH.md computed its boxes from), the 7,908 help points are:

  | Province | Help points | Share | Hospital rows |
  |---|---|---|---|
  | Bangkok (`TH-10`) | 2,930 | 37 % | 53 |
  | Chon Buri (`TH-20`) | 2,730 | 35 % | 41 |
  | Rayong (`TH-21`) | 968 | 12 % | 32 |
  | Samut Prakan (`TH-11`) | 872 | 11 % | 27 |
  | Chachoengsao (`TH-24`) | 317 | 4 % | 15 |
  | Chanthaburi, Prachin Buri | 27 | 0 % | 1 |
  | On the shore, outside the simplified outlines | 64 | 1 % | 0 |

  Inside Chon Buri this does no harm to "nearest help": from Sattahip, Chon Buri town, Ban Bueng, Bo Win, Nong Yai
  and Bo Thong, the two nearest hospital rows are all in Chon Buri. The cost is the name and the size: someone who
  picks "Chon Buri" gets a map that is more than half other provinces, with Bangkok's eastern districts such as Bang Na,
  and Suvarnabhumi airport in Samut Prakan. It is the strongest case yet for what REGIONS-FR.md proposes: cut a region by its outline
  and keep the box for display and the index.
- **The sea.** The tool fills the box around the land with sea, cut to the box. Here that matches the ground: the
  Gulf of Thailand on the west and south.

## Build it

The build machine needs Python 3.11 or later and pyosmium. Nothing else is installed, and the tool downloads nothing.

```bash
# 1. The source: Geofabrik's Thailand extract of 17 November 2026 (OpenStreetMap, ODbL 1.0), 330,447,194 bytes.
#    Save it under the name the build used: the tool writes the file name into the map's meta table.
curl -L -o thailand-latest.osm.pbf https://download.geofabrik.de/asia/thailand/thailand-261117.osm.pbf
sha256sum thailand-latest.osm.pbf     # see "Reproducing this build" for the two hashes this can give

# 2. A build environment with pyosmium.
python3 -m venv derived/buildenv && derived/buildenv/bin/pip install osmium

# 3. Build. The box is TH-20's box with the 0.15 degree margin, from REGIONS-TH.md.
derived/buildenv/bin/python tools/build_region_map.py thailand-latest.osm.pbf \
    --id TH-20 --name "Chon Buri" --bbox 100.51,12.35,101.87,13.75 --out derived/regions

# 4. Check the files, then check that the engine can use them with every connection blocked.
#    These are the exact commands behind "What was checked" and "Searches" below.
python3 tools/check_region_map.py derived/regions/TH-20
python3 tools/check_region_map.py derived/regions/TH-20 --engine \
    --find พัทยา --find Pattaya --find "Bang Saen" --find "Si Racha" --find "Sri Racha" --find "Laem Chabang" \
    --find Sattahip --find Jomtien --find "Chonburi Hospital" --find "Bangkok Hospital Pattaya" --near 12.9276,100.8771
```

On Windows the same steps work in Git Bash, with `derived/buildenv/Scripts/python` in place of
`derived/buildenv/bin/python`. Set `PYTHONIOENCODING=utf-8` before running the checker with its output sent to a file:
otherwise Windows writes that output in its legacy code page, and the checker stops at the first line with Thai text.

To look at it in the app's interface, give the engine a data folder that holds the map and an empty library:

```bash
mkdir -p /path/to/ChonBuriData/library-data && echo '[]' > /path/to/ChonBuriData/library-data/catalog.json
cp -R derived/regions/TH-20/derived derived/regions/TH-20/map-set.json /path/to/ChonBuriData/
python3 server.py --data /path/to/ChonBuriData --port 8890
# then open the address it prints, choose Map, and go to:  #/map?lat=12.9276&lon=100.8771&z=14   (Pattaya)
# the province:  #/map?lat=13.05&lon=101.15&z=9.2
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
lists only those 3 bytes). This map was not rebuilt from today's file. `TH-83`, built from the same input with the same
tool, was, and gave the same SHA-256 for all five of its files. How long Geofabrik keeps dated files was not checked.

## The build this was checked with

| | |
|---|---|
| Source file | `thailand-latest.osm.pbf` (Geofabrik's file of 17 November), 330,447,194 bytes |
| Source SHA-256 | `6a2908238debf96dd36e5c66bbaff19da7ab1f77b08bc8e106fd78b9fa3a6759` |
| Source MD5 (matches Geofabrik's `.md5`) | `de5d72d732c387d2edda85ab571230bb` |
| OpenStreetMap data up to | 2026-11-17T21:24:30Z (from the file's header) |
| Built on | 17 November 2026, Windows 11 (10.0.22631), Python 3.12.7, pyosmium 4.3.2 from PyPI |
| Build time | 565 seconds, reading the whole country and keeping the box |
| Box | 100.51, 12.35, 101.87, 13.75 (west, south, east, north) |

| File | Bytes | SHA-256 |
|---|---|---|
| `derived/geo/national.sqlite` | 109,752,320 | `fc1c53722077ee4f66788e3105630c3a23d69d18c0b700078a86370f66537ea2` |
| `derived/geo/map.sqlite` | 36,864 | `f694303d8af09c5a5862d3c2a73ba12be39ecbd6725cb59f9cfeefc2f816cf1d` |
| `derived/geo/places.sqlite` | 1,085,440 | `dbe19064979449f5e0efe7fcafd4a7e2fd9fc7be812b0a4c57f49f6f33c4e3b7` |
| `derived/geo/national-status.json` | 59 | `c62f201abf8a0d3d23af479d36067bae87596f9602f1d38212049ac0cbc98c72` |
| `derived/geo/socal-cells.json` | 2 | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |

The map was built once; whether a second build gives the same bytes on Windows was not tested (#80 reports identical
checksums for two builds on a Mac). Geofabrik replaces `thailand-latest` every day, so a later download gives a
different source checksum and slightly different counts.

What the map holds:

| Layer | Features | | Layer | Features |
|---|---|---|---|---|
| Roads | 334,642 (30,298 with a name or number) | | Land use and parks | 15,770 |
| Building outlines | 286,112 | | Water areas | 6,113 |
| Streams, canals and drains | 4,615 | | Wetland | 1,177 |
| Place labels | 777 | | Railways | 521 |
| Islands | 117 | | Beaches | 108 |
| Sea | 1 polygon, cut to the box | | | |

Help points: 7,908 in 39 classes, 5,693 of them with a name. The largest: convenience stores 2,083, fuel 852, schools
684, toilets 531, pharmacies 361, parks 324, supermarkets 312, shelters 298. For emergencies: hospitals 169 (156
places when rows within 150 m are grouped), clinics 158, police 122, drinking water 110, doctors 105, fire stations
34. The full list is in `TH-20.build.json`.

The place finder has 6,470 rows: 777 places (5 cities, 65 towns, 13 suburbs, 46 quarters, 381 villages, 223
neighbourhoods and others) and 5,693 named help points. 1,998 rows carry a second name, the English one where
OpenStreetMap has it.

## What was checked, and how

The first command passed all 37 file checks. The second runs those 37 again, then 7 engine checks and one per search: 54
in all, and all passed. A search passes the checker when it returns any row, so "Searches" below says which ones find
the place they are meant to. With `--engine`, every connection blocked and an empty library:

- **Map display.** Tiles at zoom 10, 13 and 16 around central Pattaya: roads, water, land, railways, beaches and place
  labels at the wider zooms, 262 building outlines in one zoom-16 tile.
- **Pins.** 34 pin groups around central Pattaya.
- **Nearest help.** Pharmacies at 0.04, 0.05 and 0.11 km, a police box at 0.24 km.
- **Place search.** Every search in the command above, with what it finds, is under "Searches" below.
- **What the app is told.** 39 kinds, within 100.51, 12.52, 101.87, 13.75, the extent of the data inside the box.

### Searches

A search passes the checker as soon as it returns any row, so this table says, for each search in the command above,
whether it finds the place it is meant to. "First rows" is what the checker prints (up to three). Where the place comes
lower, its rank is from the app's own place search, with the server running as under "Build it", for example `curl
"http://127.0.0.1:8890/api/places?q=Karon"`: the same `places()` the checker calls, with no location.

| Search | Meant to find | First rows | Result |
|---|---|---|---|
| `พัทยา` | the city of Pattaya | พัทยา (city); พัทยาแพทย์เฉพาะทาง (clinic); พัทยาเหนือฟาร์มาซี (pharmacy) | Finds it first |
| `Pattaya` | the city of Pattaya | Pattaya Garage (car repair); Pattaya Dentist (dentist); Pattaya Garden (garden centre) | Finds it, 19 of 20 |
| `Bang Saen` | the town | บางแสน (town); The Pine Cone Bang Saen (neighbourhood); หาดบางแสน (beach) | Finds it first |
| `Si Racha` | the town | ศรีราชา (town); ที่ว่าการอำเภอศรีราชา (town hall); เวิลด์ ไบค์ ศรีราชา (bicycle shop) | Finds it first |
| `Sri Racha` | the town Si Racha | สถานีวิจัยประมงศรีราชา (university) | Rows, but not the intended place |
| `Laem Chabang` | the city | แหลมฉบัง (city); โรงเรียนเทศบาลแหลมฉบัง 1 (school); หอบังคับการพัฒนาแหลมฉบัง (park) | Finds it first |
| `Sattahip` | the town | Sattahip market (supermarket); Sattahip Police Station (police); สัตหีบ (town) | Finds it, 3 of 4 |
| `Jomtien` | the neighbourhood (OSM: Chom Thian) | Jomtien Dental Clinic (dentist); Jomtien Medical Clinic (doctors); Pattaya Dental Care (Jomtien) (dentist) | Rows, but not the intended place |
| `Chonburi Hospital` | the hospital | โรงพยาบาลชลบุรี (hospital) | Finds it first |
| `Bangkok Hospital Pattaya` | the hospital | โรงพยาบาลกรุงเทพพัทยา (hospital) | Finds it first |

`tools/test_build_region_map.py`: 9 tests pass with pyosmium.

It was also opened in a browser through `python3 server.py`, which serves the same `web/` interface the desktop app
shows. The map drew the province, Pattaya and Si Racha in light and dark mode, and the "Nearest to the map center" list
filled in. The browser's request log showed 68 requests, all to the local server; the one 404 was `home-area.json`,
which is meant to be absent.

**Not checked:** the packaged desktop app, and installing through setup (no installer or manifest entry is part of this).

## What is and is not in it

**In it**

- Streets and paths of every class `tools/build_map.py` draws, with the same zoom rules, for Chon Buri and the parts of
  Bangkok, Samut Prakan, Chachoengsao and Rayong inside the box.
- The Eastern line railways, streams, canals, ponds, wetland, beaches, land use, parks and building outlines from
  OpenStreetMap.
- Place labels in Thai, with the English name as a second name where OpenStreetMap has one, and help points in the
  classes the engine already names (`HELP` in `server.py`).

**Not in it**

- **Addresses.** REGIONS-TH.md found no open address points for Thailand. Roads are in the map but not in the place
  finder, so a street or *soi* cannot be searched by name.
- **Terrain, contours and the 3D view**, **crops** and the **water and dam inventory**. REGIONS-TH.md lists
  the national flood layers and their licence labels.
- **`buildings.sqlite`.** Outlines are in `national.sqlite`; there are no heights.
- **Shelters as an emergency plan.** The 298 "shelter" points are OpenStreetMap structures tagged `amenity=shelter`, 43
  of them with a name. Bus shelters are left out. None is tagged as an emergency shelter.

**Known limits**

- **"Pattaya" finds the city nineteenth.** Town labels are in Thai, and their English names are kept in each row's
  detail line. Place search ranks names that start with the query before everything else, so "Pattaya" lists a garage,
  a dentist, a garden centre, the fire station and fourteen more before the city, in 19th place of 20. "Jomtien" finds
  the beach but not the neighbourhood, whose English name in OpenStreetMap is the official transcription "Chom
  Thian"; and "Sri Racha", a common spelling, finds only a fisheries station; "Si Racha", as OpenStreetMap
  spells it, finds the town first. พัทยา finds the city first.
- **Hospital rows are not all hospitals.** The 169 hospital rows are 156 places when rows within 150 m are grouped, and
  7 have no name; 53 of them are in Bangkok and 32 in Rayong.
- **Every place's detail line says "Chon Buri"**, the `--name` given, including the places in Bangkok and the other
  provinces in the box.
- **Completeness follows OpenStreetMap.** 2,215 help points have no name. Nothing was compared against an official
  count.
- **The page header, the units and the credits are the US map's.** The header says "what was mapped by 25 Oct 2026",
  while this map's date is in `meta` (`data_as_of`, 17 November 2026). Distances are in miles at wider zooms, the search
  box asks for a "town or ZIP", the home view and the "US" button point at the United States, and the credit line lists
  US sources that are not in this map. The same holds for the Bangkok and Paraguay maps.

## Licence and attribution

All data in this map is from OpenStreetMap, © OpenStreetMap contributors, under the Open Database License 1.0, taken
from Geofabrik's Thailand extract. A database built from it, which this map is, is offered under the ODbL as well. The
credit and the date of the data are written into `meta` in `national.sqlite` and `map.sqlite`, and into
`TH-20.build.json`. The app's map already shows "© OpenStreetMap contributors".
