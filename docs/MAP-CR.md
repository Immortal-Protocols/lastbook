# A detailed map of Costa Rica (`CR`): how it is built and what it holds

This is a trial map built from [REGIONS-CR.md](REGIONS-CR.md): the whole of mainland Costa Rica as one region, `CR`, with
the mainland box that proposal gives it. Isla del Coco is left out, as proposed there.

It was built with #80's `tools/build_region_map.py` unchanged (commit `a453274`, the same one #152, #180 and #242 used).
It adds no app, engine or build code. The map is not downloaded by setup and is not in any pack: the shared way to
describe, install and publish regions is still being worked out (#53), and this gives it one more concrete map to carry.

## Build it

The build machine needs Python 3.11 or later and pyosmium. The tool downloads nothing.

```bash
# 1. The source: Geofabrik's Costa Rica extract (OpenStreetMap, ODbL 1.0). About 39 MB.
curl -LO https://download.geofabrik.de/central-america/costa-rica-latest.osm.pbf
curl -LO https://download.geofabrik.de/central-america/costa-rica-latest.osm.pbf.md5 && md5sum -c costa-rica-latest.osm.pbf.md5

# 2. A build environment with pyosmium.
python3 -m venv derived/buildenv && derived/buildenv/bin/pip install osmium

# 3. Build. The box is CR's mainland box with the 0.15 degree margin, from REGIONS-CR.md.
#    The = sign matters: the box starts with a minus sign.
derived/buildenv/bin/python tools/build_region_map.py costa-rica-latest.osm.pbf \
    --id CR --name "Costa Rica" --bbox=-86.11,7.89,-82.40,11.37 --out derived/regions

# 4. Check the files, then check that the engine can use them with every connection blocked.
python3 tools/check_region_map.py derived/regions/CR
python3 tools/check_region_map.py derived/regions/CR --engine \
    --find "Calderón Guardia" --find "Hospital México" --find Cartago --find Liberia --near 9.9326,-84.0795
```

To look at it in the app's interface, follow the steps in MAP-TH-10.md (#80) with `CR` in place of `TH-10`, and go to
`#/map?lat=9.93&lon=-84.08&z=13` (San José).

## The build this was checked with

| | |
|---|---|
| Source file | `costa-rica-latest.osm.pbf`, 39,192,879 bytes |
| Source SHA-256 | `0ce2afcd13dc7eb4520afa67f2fc7d9a752c81aa73042acbb12339ccea731963` |
| Source MD5 (matches Geofabrik's `.md5`) | `f046e22921a2e1837a3bde4e8c00e3a0` |
| OpenStreetMap data up to | 2026-11-17T21:24:30Z (from the file's header) |
| Built on | 18 November 2026, Ubuntu 24.04 on x86-64, Python 3.12.3, pyosmium 4.3.2 from PyPI |
| Build time and memory | 25 seconds, 0.78 GB peak resident memory (`/usr/bin/time -v`) |
| Box | -86.11, 7.89, -82.40, 11.37 (west, south, east, north) |

| File | Bytes | SHA-256 |
|---|---|---|
| `derived/geo/national.sqlite` | 95,342,592 | `068fc0bf739215d994dc35ffc1912adc4bcdc021abfab16f8450f72b7e17dc35` |
| `derived/geo/map.sqlite` | 36,864 | `76d15236697d4479ac2e4b2b42442467aa4aefd6242986eb3a1bbfb3379f73c2` |
| `derived/geo/places.sqlite` | 3,743,744 | `27b8bc0b9b27fb3c94a6aaa512f311b3d282847bbfa7274a1908c8c9056dee5d` |
| `derived/geo/national-status.json` | 59 | `3041c639e08d19d7147acb2935a691f6f016832fe7fc8f58acde8907d28fab39` |
| `derived/geo/socal-cells.json` | 2 | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |

Two builds run one after the other on the machine above gave identical checksums for all five files. Geofabrik replaces
`costa-rica-latest` every day, so a later download gives a different source checksum and slightly different counts.

What the map holds:

| Layer | Features | | Layer | Features |
|---|---|---|---|---|
| Roads | 163,431 (78,843 with a name or number) | | Land use and parks | 28,892 |
| Building outlines | 202,360 | | Water areas | 1,541 |
| Rivers and streams | 15,221 | | Wetland | 516 |
| Place labels | 8,847 | | Islands | 398 |
| Railways | 275 | | Beaches | 356 |

Help points: 22,246 in 40 classes. The largest: schools 4,441, parks 3,226, convenience shops 2,442, supermarkets 1,345,
clinics 1,152, car repair 1,121, community centres 953, communication towers 872, pharmacies 714, police 690, hardware
589, fuel 441, doctors 424, dentists 420, toilets 414, shelters 241, hospitals 119, water towers 120, fire stations 79,
drinking water 54, springs 29. The full list is in `CR.build.json`.

The place finder has 27,435 rows: 8,847 places (15 cities, 69 towns, 437 villages, 2,953 hamlets, 5,259 neighbourhoods
and others) and the named help points.

## What was checked, and how

On the build above, all file checks and all engine checks of `tools/check_region_map.py` passed. With `--engine`:

- **Map display.** Tiles at zoom 10, 13 and 16 around 9.9326, -84.0795 (central San José): roads, water, land,
  railways and place labels at the wider zooms, 482 building outlines at 16.
- **Pins.** 113 groups in a 0.2° square.
- **Nearest help.** Three police posts within 0.09 km and a pharmacy at 0.14 km.
- **Place search.** "Calderón Guardia" finds the hospital; "Hospital México" finds it; "Cartago" finds the city;
  "Liberia" finds the city in Guanacaste, at the other end of the country.
- **Extent.** The engine reports the map as -85.91, 8.09, -82.54, 11.22: Geofabrik's extract is cut close to the
  border, so almost nothing of Nicaragua or Panama comes in.

In the interface (screenshots in the pull request, light and dark), the country view, San José and Cartago draw, and
the "Nearest to the map center" panel lists EBAIS clinics, pharmacies and police with distances.

## Known limits

- **Not built:** terrain, address search, crops, `water.sqlite`, `buildings.sqlite` (outlines are in `national.sqlite`)
  and `atlas.sqlite`, as for every map from #80. REGIONS-CR.md says what could feed each one.
- **Shelters.** The 241 `shelter` points are OSM's `amenity=shelter` without bus shelters: mostly lean-tos, picnic
  roofs and gazebos. They are not emergency shelters.
- **Isla del Coco** is outside the box and not in the map.
- **What still assumes the US.** The map opens over the United States and has a "US" button; the search box says
  "address, town or ZIP"; the country view gives distances in miles; the credits line names USGS, USDA, NOAA, USACE,
  CDFW and CalGEM, none of whose data is in this map; and the heading says the map shows what was "mapped by 25 Oct
  2026", a date fixed in `web/map.js` whatever map is installed, while this data runs to 17 November. None of this stops the map working; each is a point MAPS.md already
  lists under "What is tied to the United States".

## Licence

Map data © OpenStreetMap contributors, under the Open Database Licence 1.0, from Geofabrik's extract. The map set is a
database derived from it and is offered under the ODbL too.
