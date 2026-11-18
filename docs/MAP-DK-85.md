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
