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
# 1. The source: Geofabrik's Denmark extract (OpenStreetMap, ODbL 1.0). About 500 MB.
curl -LO https://download.geofabrik.de/europe/denmark-latest.osm.pbf
curl -LO https://download.geofabrik.de/europe/denmark-latest.osm.pbf.md5 && md5sum -c denmark-latest.osm.pbf.md5

# 2. A build environment with pyosmium.
python3 -m venv derived/buildenv && derived/buildenv/bin/pip install osmium

# 3. Build. The box is DK-84's box with the 0.15 degree margin, from REGIONS-DK.md.
derived/buildenv/bin/python tools/build_region_map.py denmark-latest.osm.pbf \
    --id DK-84 --name Hovedstaden --bbox 11.54,54.83,15.35,56.36 --out derived/regions

# 4. Check the files, then check that the engine can use them with every connection blocked.
python3 tools/check_region_map.py derived/regions/DK-84
python3 tools/check_region_map.py derived/regions/DK-84 --engine \
    --find Rigshospitalet --find Nørrebro --find Rønne --find Tivoli --find Hillerød --near 55.6761,12.5683
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
