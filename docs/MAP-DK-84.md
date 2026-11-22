# A detailed map of Region Hovedstaden (`DK-84`): how it is built and what it holds

A third worked example for `tools/build_region_map.py`, after Bangkok ([MAP-TH-10.md](MAP-TH-10.md)) and Central,
Paraguay ([MAP-PY-11.md](MAP-PY-11.md)), built with that tool unchanged. It maps Denmark's capital region, Copenhagen and
Bornholm, with the box [REGIONS-DK.md](REGIONS-DK.md) gives it. It is the first map from a country whose regions are
split by sea, and it shows what a box does when a region is in two pieces.

The tool, its checker and the Bangkok page come from pull request #80, and the Paraguay page from #152; none of them is
in this repository until they are merged. This map was built and checked with the tool as it was at commit `a453274`,
the same commit #152 used. If the tool changes before then, the build and the checks here need to be run again.

It adds no code and no app change. The map is not downloaded by setup and is not in any pack: the shared way to
describe, install and publish regions is still being worked out, and this gives it one more concrete map to carry.

## The id and the box

- **Id.** `DK-84` is Region Hovedstaden's ISO 3166-2 code, as proposed in REGIONS-DK.md. Whether hyphenated codes are
  used at all is undecided there, so the id is the maintainers' to change.
- **Box.** 11.54, 54.83, 15.35, 56.36 (west, south, east, north): the region's box with the 0.15° margin, from
  REGIONS-DK.md. It is 3.8° wide because Bornholm lies about 150 km east of Copenhagen.
- **What the rectangle holds.** The region is a small part of it. Most of the land in the box west of 14° E is Region
  Sjælland, and most of the land east of the Øresund is Skåne in Sweden. Measured against Eurostat's region outlines,
  9,880 of the 13,983 help points (71 %) are in Region Hovedstaden and 3,749 (27 %) in Region Sjælland; the other 354
  are on the coast just outside the generalised outlines. Of the 95 hospital rows, 42 are in Hovedstaden and 53 in
  Sjælland.
- **Sweden is drawn as sea.** The tool keeps everything the extract holds inside the box and fills the rest of the box
  with sea, cut to the box (its own header says so). Geofabrik's Denmark extract stops at the Danish border, so Malmö,
  Lund, Helsingborg and Ystad, all inside the box, are drawn as open water. This is the strongest argument in
  REGIONS-DK.md for cutting a region by its outline rather than its box, or for a sea polygon taken from coastline data
  instead of from the box.
- **PR #35** has a smaller box for the city, `dk-kob` (12.26, 55.38, 12.86, 55.98), and **#84** lists all of Denmark as
  `eu-dk`. Both come from the same extract.

## Build it

The build machine needs Python 3.11 or later and pyosmium. Nothing else is installed, and the tool downloads nothing.

```bash
# 1. The source: Geofabrik's Denmark extract of 17 November 2026 (OpenStreetMap, ODbL 1.0), 498,163,345 bytes.
#    Save it under the name the build used: the tool writes the file name into the map's meta table.
curl -L -o denmark-latest.osm.pbf https://download.geofabrik.de/europe/denmark/denmark-261117.osm.pbf
sha256sum denmark-latest.osm.pbf     # see "Reproducing this build" for the two hashes this can give

# 2. A build environment with pyosmium.
python3 -m venv derived/buildenv && derived/buildenv/bin/pip install osmium

# 3. Build. The box is DK-84's box with the 0.15 degree margin, from REGIONS-DK.md.
derived/buildenv/bin/python tools/build_region_map.py denmark-latest.osm.pbf \
    --id DK-84 --name Hovedstaden --bbox 11.54,54.83,15.35,56.36 --out derived/regions

# 4. Check the files, then check that the engine can use them with every connection blocked.
#    These are the exact commands behind "What was checked" and "Searches" below.
python3 tools/check_region_map.py derived/regions/DK-84
python3 tools/check_region_map.py derived/regions/DK-84 --engine \
    --find Rigshospitalet --find Nørrebro --find Rønne --find Hillerød --find Elsinore --find "Kgs. Lyngby" \
    --find København --find Tivoli --find Copenhagen --find Kobenhavn --find Koebenhavn --find Hillerod \
    --find Helsingor --find Christiansø --find Christianso --near 55.6761,12.5683
python3 tools/check_region_map.py derived/regions/DK-84 --engine --near 55.1004,14.7010     # Rønne, on Bornholm
```

On Windows the same steps work in Git Bash, with `derived/buildenv/Scripts/python` in place of
`derived/buildenv/bin/python`. The build used about 1.3 GB of memory when watched, and writes 330 MB of output plus
SQLite's temporary files, which go where `TMP` points. A first run here stopped with "database or disk is full" on a
nearly full drive and finished once `TMP` and the output were on another drive.

To look at it in the app's interface, give the engine a data folder that holds the map and an empty library:

```bash
mkdir -p /path/to/HovedstadenData/library-data && echo '[]' > /path/to/HovedstadenData/library-data/catalog.json
cp -R derived/regions/DK-84/derived derived/regions/DK-84/map-set.json /path/to/HovedstadenData/
python3 server.py --data /path/to/HovedstadenData --port 8890
# then open the address it prints, choose Map, and go to:  #/map?lat=55.6761&lon=12.5683&z=12.5
# Bornholm:  #/map?lat=55.1004&lon=14.7010&z=14
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

**The input.** Geofabrik's Denmark extract of 17 November 2026, downloaded on 18 November as `denmark-latest.osm.pbf`:
498,163,345 bytes, OpenStreetMap data up to 2026-11-17T21:24:30Z, replication sequence 4974.

| | SHA-256 | MD5 |
|---|---|---|
| The file this map was built from | `904be7011e61d508f420b71d973d4c589886c7733c7e68017d3f73a2dd81ffb8` | `e64ec59e210baefa26acb0c3c428aec4` |
| The dated file served today, `https://download.geofabrik.de/europe/denmark/denmark-261117.osm.pbf` | `b1479ed14197f5b2eb2f7ec2a2a6fed1c6f4f81899f04c8247472d2c74872047` | `eb70e94a26b18752bea85f5a0feff430` |

**The original bytes can no longer be downloaded.** Geofabrik has since moved its dated files into a folder per country,
and the file served today differs from the original in 3 bytes, all in the file header: the replication URL changed from
`https://download.geofabrik.de/europe/denmark-updates` to `https://download.geofabrik.de/europe/denmark/updates`. Size,
replication timestamp and sequence are the same, and every OpenStreetMap data block is byte for byte the same (`cmp -l`
lists only those 3 bytes). A rebuild on 22 November 2026 from the file served today, saved as `denmark-latest.osm.pbf`,
gave the same SHA-256 for all five files listed under "The build this was checked with". How long Geofabrik keeps dated
files was not checked.

## The build this was checked with

| | |
|---|---|
| Source file | `denmark-latest.osm.pbf` (Geofabrik's file of 17 November), 498,163,345 bytes |
| Source SHA-256 | `904be7011e61d508f420b71d973d4c589886c7733c7e68017d3f73a2dd81ffb8` |
| Source MD5 (matches Geofabrik's `.md5`) | `e64ec59e210baefa26acb0c3c428aec4` |
| OpenStreetMap data up to | 2026-11-17T21:24:30Z (from the file's header) |
| Built on | 17 November 2026, Windows 11 (10.0.22631), Python 3.12.7, pyosmium 4.3.2 from PyPI |
| Build time | 819 seconds, reading the whole country and keeping the box |
| Box | 11.54, 54.83, 15.35, 56.36 (west, south, east, north) |

| File | Bytes | SHA-256 |
|---|---|---|
| `derived/geo/national.sqlite` | 328,302,592 | `a1b26a369a2420019185a9ccefdf1eeafa3bc1083d09ddfae4f191940d382972` |
| `derived/geo/map.sqlite` | 36,864 | `bd5d7b3d0dfbb50182cc1b7b062d59829a9093e0958903badc71b018ce62bd09` |
| `derived/geo/places.sqlite` | 1,343,488 | `77fbee95a03fb495ddc29747ebdad102c375d8e71f1e7e30a387f60640b88f00` |
| `derived/geo/national-status.json` | 60 | `a21f5ba6f8219039a01a38ac489fc66798d3613c47b437f386ca879d94ec3f16` |
| `derived/geo/socal-cells.json` | 2 | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |

The map was built once; whether a second build gives the same bytes on Windows was not tested (#80 reports identical
checksums for two builds on a Mac). Geofabrik replaces `denmark-latest` every day, so a later download gives a different
source checksum and slightly different counts.

What the map holds:

| Layer | Features | | Layer | Features |
|---|---|---|---|---|
| Roads | 435,560 (117,382 with a name or number) | | Land use and parks | 141,303 |
| Building outlines | 1,168,744 | | Water areas | 26,399 |
| Streams, rivers, canals and drains | 66,583 | | Wetland | 2,738 |
| Place labels | 2,666 | | Railways | 2,942 |
| Islands | 384 | | Beaches | 451 |
| Sea | 1 polygon, cut to the box | | | |

Help points: 13,983 in 40 classes, 7,579 of them with a name. The largest: parks 2,895, toilets 1,222, shelters 1,095,
supermarkets 1,050, schools 884, kindergartens 761, convenience stores 664, fuel 583, community centres 403. For
emergencies: drinking water 325, pharmacies 198 (and 205 chemists), doctors 137, dentists 116, hospitals 95, clinics
94, fire stations 62, police 45, water towers 57, water works 94, springs 94. The full list is in `DK-84.build.json`.

The place finder has 10,245 rows: 2,666 places (2 cities, 41 towns, 126 suburbs, 157 quarters, 350 villages, 1,452
hamlets, 295 neighbourhoods, 242 localities and 1 island) and 7,579 named help points. 140 rows carry a second name,
the English one where OpenStreetMap has it.

## What was checked, and how

The first command passed all 37 file checks. The second runs those 37 again, then 7 engine checks and one per search: 59
in all, 55 passed and 4 failed. The 4 failures are the searches marked "No rows" under "Searches": the checker counts a
search that returns nothing as a failure. The third, around Rønne, made 44 checks and all passed. With `--engine`, every
connection blocked and an empty library:

- **Map display.** Tiles at zoom 10, 13 and 16 around Copenhagen's city hall square: roads, water, land, railways and
  place labels at the wider zooms, 78 building outlines in one zoom-16 tile.
- **Pins.** 80 pin groups around the city hall square.
- **Nearest help.** Pharmacies at 0.3 and 0.36 km, and the police at Copenhagen Central Station at 0.5 km. Around Rønne
  on Bornholm (the third command): a pharmacy at 0.37 km, the police at 0.83 km and Bornholms Hospital at
  1.05 km.
- **Place search.** Every search in the command above, with what it finds, is under "Searches" below.
- **What the app is told.** 40 kinds, within 11.54, 54.83, 15.19, 56.13, the extent of the data inside the box.

### Searches

A search passes the checker as soon as it returns any row, so this table says, for each search in the command above,
whether it finds the place it is meant to. "First rows" is what the checker prints (up to three). Where the place comes
lower, its rank is from the app's own place search, with the server running as under "Build it", for example `curl
"http://127.0.0.1:8890/api/places?q=Karon"`: the same `places()` the checker calls, with no location.

| Search | Meant to find | First rows | Result |
|---|---|---|---|
| `Rigshospitalet` | the hospital | Rigshospitalet (hospital) | Finds it first |
| `Nørrebro` | the district | Nørrebro (suburb); Nørrebroparken (park); Nørrebrogade (park) | Finds it first |
| `Rønne` | the town on Bornholm | Rønne (town); Rønnede (village); Rønnebæk (village) | Finds it first |
| `Hillerød` | the town | Hillerød (town); Hillerød Øst (suburb); Hillerødsholm (neighbourhood) | Finds it first |
| `Elsinore` | Helsingør, by its English name | Helsingør (town) | Finds it first |
| `Kgs. Lyngby` | Kongens Lyngby | Kongens Lyngby (town); Lyngbyvejskvarteret (quarter); Store Lyngby (village) | Finds it first |
| `København` | the city | København (city); Københavns Byret (courthouse); Københavns Cykelbørs (bicycle shop) | Finds it first |
| `Tivoli` | Tivoli Gardens (not a kept class) | Tivoli (hamlet) | Rows, but not the intended place |
| `Copenhagen` | the city København | Copenhagen Bikeshop (bicycle shop); Copenhagen Camping (camp site); Copenhagen Bicycle Store (bicycle shop) | Finds it, 14 of 20 |
| `Kobenhavn` | the city København | (none) | No rows (the checker reports FAIL) |
| `Koebenhavn` | the city København | (none) | No rows (the checker reports FAIL) |
| `Hillerod` | the town Hillerød | (none) | No rows (the checker reports FAIL) |
| `Helsingor` | the town Helsingør | Sveriges Konsulat i Helsingör (embassy) | Rows, but not the intended place |
| `Christiansø` | the island (it has no place row) | Christiansø Købmandshandel (convenience); Christiansø Posthus (post office); Christiansø Skole (school) | Rows, but not the intended place |
| `Christianso` | the island (it has no place row) | (none) | No rows (the checker reports FAIL) |

`tools/test_build_region_map.py`: 9 tests pass with pyosmium.

It was also opened in a browser through `python3 server.py`, which serves the same `web/` interface the desktop app
shows. The map drew at city and street zooms in light and dark mode, on Zealand and on Bornholm; pins and the "Nearest
to the map center" list filled in; and the search box took the map to Rigshospitalet. The browser's request log showed
92 requests, all to the local server; the one 404 was `home-area.json`, which is meant to be absent.

**Not checked:** the packaged desktop app, and installing through setup (no installer or manifest entry is part of this).

## What is and is not in it

**In it**

- Streets and paths of every class `tools/build_map.py` draws, with the same zoom rules, for north-east Zealand, most of
  the rest of Zealand, Bornholm and Ertholmene.
- Lakes, streams and drains, wetland, beaches, land use, parks and building outlines from OpenStreetMap.
- Place labels and help points in the classes the engine already names (`HELP` in `server.py`).

**Not in it**

- **Addresses.** Denmark's address register is open (REGIONS-DK.md), but the tool does not build an address index, and
  the engine could not read Danish addresses yet: the street comes before the number. Roads are in the map but not in
  the place finder, so a street cannot be searched by name.
- **Terrain, contours and the 3D view**, **crops** and the **water and dam inventory**. Denmark's elevation model and
  coastal dike layer are described in REGIONS-DK.md.
- **`buildings.sqlite`.** Outlines are in `national.sqlite`; there are no heights.
- **Government lists.** Defibrillators, warning sirens and public shelters have no open national list (REGIONS-DK.md).
  Every point here is from OpenStreetMap.
- **Shelters as an emergency plan.** Most of the 1,095 "shelter" points are lean-tos at nature camping sites and picnic
  shelters. Bus shelters are left out. None is a public shelter (*sikringsrum*).
- **Sweden.** Inside the box, Skåne is drawn as sea (see "The id and the box").

**Known limits**

- **Danish letters typed without them find nothing.** The place finder's index (FTS5 `unicode61`) folds accents, but
  `ø`, `æ` and `å` are letters of their own, not accented ones. "Kobenhavn", "Koebenhavn", "Hillerod" and "Christianso"
  find nothing, and "Helsingor" finds only the Swedish consulate. Someone on a keyboard without these letters cannot
  find Copenhagen by its Danish name.
- **"Copenhagen" finds the city 14th of 20.** The English name is kept in the row's detail line, and name matches
  rank first, so shops, clinics and schools with "Copenhagen" in their names come before it. "København" finds
  the city first.
- **Hospital rows are not hospitals.** The 95 hospital rows are 47 places when rows within 150 m are grouped:
  OpenStreetMap often has one hospital as a point and again as each of its buildings. More than half of them (53) are
  in Region Sjælland, because the box holds most of Zealand.
- **Every place's detail line says "Hovedstaden"**, the `--name` given, including places in Region Sjælland.
- **Completeness follows OpenStreetMap.** 6,404 help points have no name. Nothing was compared against an official
  count.
- **The page header, the units and the credits are the US map's.** The header says "what was mapped by 25 Oct 2026",
  while this map's date is in `meta` (`data_as_of`, 17 November 2026) and is not shown yet. Distances are in miles at
  wider zooms, the search box asks for a "town or ZIP" and its "no place" message for "a 5-digit ZIP", the home view
  and the "US" button point at the United States, and the credit line lists USGS, USDA, NOAA and other US sources that
  are not in this map. The same holds for the Bangkok and Paraguay maps.

## Licence and attribution

All data in this map is from OpenStreetMap, © OpenStreetMap contributors, under the Open Database License 1.0, taken
from Geofabrik's Denmark extract. A database built from it, which this map is, is offered under the ODbL as well. The
credit and the date of the data are written into `meta` in `national.sqlite` and `map.sqlite`, and into
`DK-84.build.json`. The app's map already shows "© OpenStreetMap contributors".
