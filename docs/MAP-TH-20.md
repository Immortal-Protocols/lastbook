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
# 1. The source: Geofabrik's Thailand extract (OpenStreetMap, ODbL 1.0). About 330 MB.
curl -LO https://download.geofabrik.de/asia/thailand-latest.osm.pbf
curl -LO https://download.geofabrik.de/asia/thailand-latest.osm.pbf.md5 && md5sum -c thailand-latest.osm.pbf.md5

# 2. A build environment with pyosmium.
python3 -m venv derived/buildenv && derived/buildenv/bin/pip install osmium

# 3. Build. The box is TH-20's box with the 0.15 degree margin, from REGIONS-TH.md.
derived/buildenv/bin/python tools/build_region_map.py thailand-latest.osm.pbf \
    --id TH-20 --name "Chon Buri" --bbox 100.51,12.35,101.87,13.75 --out derived/regions

# 4. Check the files, then check that the engine can use them with every connection blocked.
python3 tools/check_region_map.py derived/regions/TH-20
python3 tools/check_region_map.py derived/regions/TH-20 --engine \
    --find พัทยา --find "Bang Saen" --find "Si Racha" --find "Chonburi Hospital" --find "Laem Chabang" \
    --near 12.9276,100.8771
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
