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
# 1. The source: Geofabrik's Thailand extract (OpenStreetMap, ODbL 1.0). About 330 MB.
curl -LO https://download.geofabrik.de/asia/thailand-latest.osm.pbf
curl -LO https://download.geofabrik.de/asia/thailand-latest.osm.pbf.md5 && md5sum -c thailand-latest.osm.pbf.md5

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
