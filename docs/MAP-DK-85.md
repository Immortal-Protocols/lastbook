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
# 1. The source: Geofabrik's Denmark extract (OpenStreetMap, ODbL 1.0). About 500 MB.
curl -LO https://download.geofabrik.de/europe/denmark-latest.osm.pbf
curl -LO https://download.geofabrik.de/europe/denmark-latest.osm.pbf.md5 && md5sum -c denmark-latest.osm.pbf.md5

# 2. A build environment with pyosmium.
python3 -m venv derived/buildenv && derived/buildenv/bin/pip install osmium

# 3. Build. The box is DK-85's box with the 0.15 degree margin, from REGIONS-DK.md.
derived/buildenv/bin/python tools/build_region_map.py denmark-latest.osm.pbf \
    --id DK-85 --name Sjælland --bbox 10.73,54.41,12.71,56.15 --out derived/regions

# 4. Check the files, then check that the engine can use them with every connection blocked.
python3 tools/check_region_map.py derived/regions/DK-85
python3 tools/check_region_map.py derived/regions/DK-85 --engine \
    --find Roskilde --find Køge --find Næstved --find "Nykøbing Falster" \
    --find "Sjællands Universitetshospital" --near 55.6415,12.0803
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
