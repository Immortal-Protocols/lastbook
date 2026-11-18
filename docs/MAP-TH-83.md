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
