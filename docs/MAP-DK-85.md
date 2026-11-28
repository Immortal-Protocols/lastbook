# A detailed map of Region Sjælland (`DK-85`): how it is built and what it holds

A worked example for `tools/build_region_map.py` covering the whole of Region Sjælland: Zealand outside the capital
region, with Lolland, Falster, Møn and the smaller islands, built with that tool unchanged. It uses the box
[REGIONS-DK.md](REGIONS-DK.md) gives the region, and it is the companion of [MAP-DK-84.md](MAP-DK-84.md), the map of
Region Hovedstaden next door. Together the two show what one box per region does when two regions share an island.

The tool, its checker and the Bangkok page come from pull request #80, the Denmark proposal from #179 and the
Hovedstaden page from #180; none of them is in this repository until they are merged. This map was built and checked
with the tool as it was at commit `a453274`, the commit #152 and #180 used. If the tool changes before then, the build
and the checks here need to be run again.

It adds no code and no app change. The map is not downloaded by setup and is not in any pack: the shared way to
describe, install and publish regions is still being worked out, and this gives it one more concrete map to carry.

## The id and the box

- **Id.** `DK-85` is Region Sjælland's ISO 3166-2 code, as proposed in REGIONS-DK.md. Whether hyphenated codes are
  used at all is undecided there, so the id is the maintainers' to change.
- **The region.** 17 municipalities and 860,130 people on 1 October 2026 (Danmarks Statistik, FOLK1A), from Roskilde,
  Køge and Holbæk in the north to Lolland and Falster in the south.
- **Box.** 10.73, 54.41, 12.71, 56.15 (west, south, east, north): the region's box with the 0.15° margin, from
  REGIONS-DK.md.
- **What the rectangle holds: more of the capital region than of Sjælland.** Region Sjælland wraps around Region
  Hovedstaden on Zealand, so its box takes in almost all of the capital region west of the Øresund as well. Measured
  against Eurostat's region outlines, the 15,942 help points are:

  | Region | Help points | Share | Hospital rows |
  |---|---|---|---|
  | Hovedstaden (`DK-84`) | 9,213 | 58 % | 40 |
  | Sjælland (`DK-85`) | 5,947 | 37 % | 66 |
  | Syddanmark (`DK-83`): Langeland and the east of Funen | 293 | 2 % | 1 |
  | On the coast, outside the generalised outlines | 489 | 3 % | 0 |

  Most of the hospitals in the map are still Sjælland's, but the file holds the city of Copenhagen twice over once
  the Hovedstaden map is installed beside it: the two maps together are 733 MB, and much of what they hold on Zealand
  is in both. Cutting each region by its outline, as REGIONS-DK.md and REGIONS-FR.md propose, would remove the overlap.
- **Germany is drawn as sea.** The box's south edge, 54.41° N, crosses Fehmarn. Geofabrik's Denmark extract stops at
  the Danish border and the tool fills the rest of the box with sea, so at Burg and Puttgarden the map holds only sea:
  no land, no roads and no places. This is the same effect MAP-DK-84.md shows for Skåne in Sweden.

## Build it

The build machine needs Python 3.11 or later and pyosmium. Nothing else is installed, and the tool downloads nothing.

```bash
# 1. The source: Geofabrik's Denmark extract of 17 November 2026 (OpenStreetMap, ODbL 1.0), 498,163,345 bytes.
#    Save it under the name the build used: the tool writes the file name into the map's meta table.
curl -L -o denmark-latest.osm.pbf https://download.geofabrik.de/europe/denmark/denmark-261117.osm.pbf
sha256sum denmark-latest.osm.pbf     # see "Reproducing this build" for the two hashes this can give

# 2. A build environment with pyosmium.
python3 -m venv derived/buildenv && derived/buildenv/bin/pip install osmium

# 3. Build. The box is DK-85's box with the 0.15 degree margin, from REGIONS-DK.md.
derived/buildenv/bin/python tools/build_region_map.py denmark-latest.osm.pbf \
    --id DK-85 --name Sjælland --bbox 10.73,54.41,12.71,56.15 --out derived/regions

# 4. Check the files, then check that the engine can use them with every connection blocked.
#    These are the exact commands behind "What was checked" and "Searches" below.
python3 tools/check_region_map.py derived/regions/DK-85
python3 tools/check_region_map.py derived/regions/DK-85 --engine \
    --find Roskilde --find Køge --find Næstved --find Holbæk --find Kalundborg --find "Nykøbing Falster" \
    --find Vordingborg --find Sorø --find "Sjællands Universitetshospital" --find "Roskilde Domkirke" \
    --find Koge --find Naestved --find Holbaek --find Soro --find Møn --find Lolland --near 55.6415,12.0803
```

On Windows the same steps work in Git Bash, with `derived/buildenv/Scripts/python` in place of
`derived/buildenv/bin/python`, and with `PYTHONIOENCODING=utf-8` set before sending the checker's output to a file.
The build writes 405 MB of output plus SQLite's temporary files, which go where `TMP` points.

To look at it in the app's interface, give the engine a data folder that holds the map and an empty library:

```bash
mkdir -p /path/to/SjaellandData/library-data && echo '[]' > /path/to/SjaellandData/library-data/catalog.json
cp -R derived/regions/DK-85/derived derived/regions/DK-85/map-set.json /path/to/SjaellandData/
python3 server.py --data /path/to/SjaellandData --port 8890
# then open the address it prints, choose Map, and go to:  #/map?lat=55.6415&lon=12.0803&z=14   (Roskilde)
# the whole region:  #/map?lat=55.30&lon=11.75&z=8.2
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
lists only those 3 bytes). This map was not rebuilt from today's file. `DK-84`, built from the same input with the same
tool, was, and gave the same SHA-256 for all five of its files. How long Geofabrik keeps dated files was not checked.

## The build this was checked with

| | |
|---|---|
| Source file | `denmark-latest.osm.pbf` (Geofabrik's file of 17 November), 498,163,345 bytes |
| Source SHA-256 | `904be7011e61d508f420b71d973d4c589886c7733c7e68017d3f73a2dd81ffb8` |
| Source MD5 (matches Geofabrik's `.md5`) | `e64ec59e210baefa26acb0c3c428aec4` |
| OpenStreetMap data up to | 2026-11-17T21:24:30Z (from the file's header) |
| Built on | 18 November 2026, Windows 11 (10.0.22631), Python 3.12.7, pyosmium 4.3.2 from PyPI |
| Build time | 808 seconds, reading the whole country and keeping the box |
| Box | 10.73, 54.41, 12.71, 56.15 (west, south, east, north) |

| File | Bytes | SHA-256 |
|---|---|---|
| `derived/geo/national.sqlite` | 405,258,240 | `62213d2c1d4e64aed8daea4f038498f7933a8fdf4f547c64e5d0cbee33256ee9` |
| `derived/geo/map.sqlite` | 36,864 | `e8c97419afd5532e101799f328a2f76e9ee4bafcc38d5ed634b05507e38ea494` |
| `derived/geo/places.sqlite` | 1,564,672 | `d2e6594c3dff499e2ddd8c3a1bc30bb2cb3ca31ebd402a4b44a6386ea0f32f46` |
| `derived/geo/national-status.json` | 60 | `9ed5a06b234553b558ad19e62b5a39fe6113a0436f94db53d741507e17edc733` |
| `derived/geo/socal-cells.json` | 2 | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |

The map was built once; whether a second build gives the same bytes on Windows was not tested (#80 reports identical
checksums for two builds on a Mac). It was built from the same extract as the Hovedstaden map, so the two can be
compared directly. Geofabrik replaces `denmark-latest` every day, so a later download gives a different source checksum
and slightly different counts.

What the map holds:

| Layer | Features | | Layer | Features |
|---|---|---|---|---|
| Roads | 516,799 (138,829 with a name or number) | | Land use and parks | 179,574 |
| Building outlines | 1,445,028 | | Water areas | 34,587 |
| Streams, rivers, canals and drains | 95,117 | | Wetland | 3,562 |
| Place labels | 3,724 | | Railways | 3,325 |
| Islands | 279 | | Beaches | 602 |
| Sea | 1 polygon, cut to the box | | | |

Help points: 15,942 in 40 classes, 8,584 of them with a name. The largest: parks 3,141, toilets 1,450, shelters 1,408,
supermarkets 1,186, schools 1,023, kindergartens 801, convenience stores 725, fuel 712. For emergencies: drinking water
332, pharmacies 227 (and 224 chemists), doctors 160, dentists 120, hospitals 107, clinics 99, fire stations 81, police
57, water works 109, springs 103. The full list is in `DK-85.build.json`.

The place finder has 12,308 rows: 3,724 places (2 cities, 49 towns, 133 suburbs, 208 quarters, 449 villages, 2,262
hamlets, 317 neighbourhoods, 303 localities and 1 island) and 8,584 named help points. 149 rows carry a second name, the
English one where OpenStreetMap has it.

## What was checked, and how

The first command passed all 37 file checks. The second runs those 37 again, then 7 engine checks and one per search: 60
in all, 56 passed and 4 failed. The 4 failures are the searches marked "No rows" under "Searches": the checker counts a
search that returns nothing as a failure. With `--engine`, every connection blocked and an empty library:

- **Map display.** Tiles at zoom 10, 13 and 16 around the centre of Roskilde: roads, water, land, railways and place
  labels at the wider zooms, 143 building outlines in one zoom-16 tile.
- **Pins.** 13 pin groups around the centre of Roskilde.
- **Nearest help.** A pharmacy at 0.18 km, Roskilde Privathospital at 0.39 km, another pharmacy at 0.5 km and the
  police station at 0.52 km.
- **Place search.** Every search in the command above, with what it finds, is under "Searches" below.
- **What the app is told.** 40 kinds, within 10.73, 54.56, 12.69, 56.13, the extent of the data inside the box.

### Searches

A search passes the checker as soon as it returns any row, so this table says, for each search in the command above,
whether it finds the place it is meant to. "First rows" is what the checker prints (up to three). Where the place comes
lower, its rank is from the app's own place search, with the server running as under "Build it", for example `curl
"http://127.0.0.1:8890/api/places?q=Karon"`: the same `places()` the checker calls, with no location.

| Search | Meant to find | First rows | Result |
|---|---|---|---|
| `Roskilde` | the city | Roskilde (city); Roskilde Camping (camp site); Roskilde Dyreklinik (veterinary) | Finds it first |
| `Køge` | the town | Køge (town); Køge Søhuse (hamlet); Køge Bibliotek (library) | Finds it first |
| `Næstved` | the town | Næstved (town); Næstved Bibliotek (library); Næstved Lokalpoliti (police) | Finds it first |
| `Holbæk` | the town | Holbæk (town); Holbæk Huse (quarter); Holbæk Seniorlandsby (quarter) | Finds it first |
| `Kalundborg` | the town | Kalundborg (town); Kalundborg Lyng (quarter); Kalundborg Lokalstation (police) | Finds it first |
| `Nykøbing Falster` | the town | Nykøbing Falster (town); Nykøbing Falster Bibliotek (library); Nykøbing Falster Lokalpoliti (police) | Finds it first |
| `Vordingborg` | the town | Vordingborg (town); Vordingborg-senderen (comms tower); Vordingborg Kommune (town hall) | Finds it first |
| `Sorø` | the town | Sorø (town); Sorø Rådhus (town hall); Sorø Apotek (pharmacy) | Finds it first |
| `Sjællands Universitetshospital` | the hospital | Sjællands Universitetshospital, Køge (hospital); Sjællands Universitetshospital, Nykøbing F. (hospital) | Finds it first |
| `Roskilde Domkirke` | the cathedral (not a kept class) | Roskilde (city); Roskilde Camping (camp site); Roskilde Dyreklinik (veterinary) | Rows, but not the intended place |
| `Koge` | the town Køge | (none) | No rows (the checker reports FAIL) |
| `Naestved` | the town Næstved | (none) | No rows (the checker reports FAIL) |
| `Holbaek` | the town Holbæk | (none) | No rows (the checker reports FAIL) |
| `Soro` | the town Sorø | (none) | No rows (the checker reports FAIL) |
| `Møn` | the island (it has no place row) | Mønge (hamlet); Mønge Huse (hamlet); Møns Contregarde (locality) | Rows, but not the intended place |
| `Lolland` | the island (it has no place row) | Lolland-Falster Brandvæsen (fire station); Rådhuset Lolland Kommune (town hall); S/I FGU Lolland-Falster (school) | Rows, but not the intended place |

`tools/test_build_region_map.py`: 9 tests pass with pyosmium.

It was also opened in a browser through `python3 server.py`, which serves the same `web/` interface the desktop app
shows. The map drew the whole region, Roskilde and Nykøbing Falster, Roskilde in dark mode as well, and the "Nearest to the map
center" list filled in. The browser's request log showed 90 requests, all to the local server; the one 404 was
`home-area.json`, which is meant to be absent.

**Not checked:** the packaged desktop app, and installing through setup (no installer or manifest entry is part of this).

## What is and is not in it

**In it**

- Streets and paths of every class `tools/build_map.py` draws, with the same zoom rules, for all of Zealand, Lolland,
  Falster, Møn and the islands in the box, and for Langeland and the east of Funen.
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
- **Shelters as an emergency plan.** The 1,408 "shelter" points are OpenStreetMap structures tagged `amenity=shelter`,
  233 of them with a name. In Denmark as a whole over half of these are lean-tos at nature camping sites
  (REGIONS-DK.md). Bus shelters are left out. None is a public shelter (*sikringsrum*).
- **Fehmarn.** Inside the box, the north of the island is drawn as sea (see "The id and the box").

**Known limits**

- **Danish letters typed without them find nothing.** As in MAP-DK-84.md: "Koge", "Naestved", "Holbaek" and "Soro"
  find no rows at all, while "Køge", "Næstved", "Holbæk" and "Sorø" find the towns first. The place finder's index folds
  accents, but `ø`, `æ` and `å` are letters of their own.
- **Islands are not found by name.** "Møn" finds the hamlet of Mønge first, and "Lolland" finds the fire service and the
  town hall; the islands themselves are not places in the place finder.
- **Hospital rows are not hospitals.** The 107 hospital rows are 58 places when rows within 150 m are grouped, and 4
  have no name; 40 of them are in the capital region.
- **Every place's detail line says "Sjælland"**, the `--name` given, including the places in Copenhagen and on Funen.
- **Completeness follows OpenStreetMap.** 7,358 help points have no name. Nothing was compared against an official
  count.
- **The page header, the units and the credits are the US map's.** The header says "what was mapped by 25 Oct 2026",
  while this map's date is in `meta` (`data_as_of`, 17 November 2026). Distances are in miles at wider zooms, the search
  box asks for a "town or ZIP", the home view and the "US" button point at the United States, and the credit line lists
  US sources that are not in this map. The same holds for the other region maps.

## Licence and attribution

All data in this map is from OpenStreetMap, © OpenStreetMap contributors, under the Open Database License 1.0, taken
from Geofabrik's Denmark extract. A database built from it, which this map is, is offered under the ODbL as well. The
credit and the date of the data are written into `meta` in `national.sqlite` and `map.sqlite`, and into
`DK-85.build.json`. The app's map already shows "© OpenStreetMap contributors".
