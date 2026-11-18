# A detailed map of Delhi (`IN-DL`): how it is built and what it holds

This is a map of the National Capital Territory of Delhi, `IN-DL`, built with the region builder from the Bangkok map
([MAP-TH-10.md](MAP-TH-10.md)) and no change to it. The region id and the source follow the India proposal
([REGIONS-IN.md](REGIONS-IN.md)): an ISO 3166-2:IN code with its `IN-` prefix, so it cannot be read as Indiana, and
Geofabrik's India zone extract.

It adds no code. The map is not downloaded by setup and is not in any pack: the shared way to describe, install and
publish regions is still being worked out, and this gives it a second, differently shaped map to carry (a landlocked
city territory, local labels mostly in English, place names in two scripts).

## Build it

The build machine needs Python 3.11 or later and pyosmium. Nothing else is installed, and the tool downloads nothing.

```bash
# 1. The source: Geofabrik's India northern zone (OpenStreetMap, ODbL 1.0), which holds Delhi. About 225 MB.
curl -LO https://download.geofabrik.de/asia/india/northern-zone-latest.osm.pbf
curl -LO https://download.geofabrik.de/asia/india/northern-zone-latest.osm.pbf.md5 && md5sum -c northern-zone-latest.osm.pbf.md5

# 2. A build environment with pyosmium.
python3 -m venv derived/buildenv && derived/buildenv/bin/pip install osmium

# 3. Build. The box is Delhi's outline box plus the 0.15 degree margin (see "The box" below).
derived/buildenv/bin/python tools/build_region_map.py northern-zone-latest.osm.pbf \
    --id IN-DL --name Delhi --bbox 76.68,28.28,77.49,29.03 --out derived/regions

# 4. Check the files, then check that the engine can use them with every connection blocked.
python3 tools/check_region_map.py derived/regions/IN-DL
python3 tools/check_region_map.py derived/regions/IN-DL --engine \
    --find "Connaught Place" --find AIIMS --find "Chandni Chowk" --find Dwarka --find "कनॉट प्लेस" --find दिल्ली
```

To look at it in the app's interface, give the engine a data folder that holds the map and an empty library, as for
Bangkok, and open `#/map?lat=28.6315&lon=77.2167&z=14` (Connaught Place). The map opens on the United States unless an
address or a place search moves it.

## The box

`76.68, 28.28, 77.49, 29.03` (west, south, east, north). It is the bounding box of Delhi's outline in Natural Earth
admin-1 states and provinces, 1:10m, version 5.1.1 (public domain; `ne_10m_admin_1_states_provinces.zip`, SHA-256
`efc59726337323058f9446210adc96673179cd344e053666ee3d28cb58ba2b05`), plus 0.15 degrees on each side, as for US states.
Only the box is used: no boundary is drawn or shipped. It agrees with the sample box with margin in REGIONS-IN.md
(`76.68, 28.25, 77.50, 29.04`) to within 0.03 degrees. The margin takes in the edges of Gurugram, Faridabad, Ghaziabad
and Noida, which are in Haryana and Uttar Pradesh.

## The build this was checked with

| | |
|---|---|
| Source file | `northern-zone-latest.osm.pbf`, 225,131,305 bytes |
| Source SHA-256 | `4b7351b76405f3281c3b21345edec9c29416bba682fba18b6bc3b5c1fecd4e47` |
| Source MD5 (matches Geofabrik's `.md5`) | `c49d3dde32fed8c00882a870409ca1f5` |
| OpenStreetMap data up to | 2026-11-17T21:24:30Z (from the file's header) |
| Built on | 18 November 2026, macOS 27.0 on Apple M1 Pro, Python 3.11.13 (SQLite 3.50.4), pyosmium 4.3.2 |
| Build time | about 145 seconds, reading the whole zone and keeping the box |

| File | Bytes | SHA-256 |
|---|---|---|
| `derived/geo/national.sqlite` | 122,757,120 | `787c34e4ed16711e57e9afc3d9a87cdf065d28a6eb033a602ebf07d7545a7a35` |
| `derived/geo/map.sqlite` | 36,864 | `4f905503c9c3e425f056e7bc5b7ed0f36c2e84e97c0ef894c41378ed9adc04d2` |
| `derived/geo/places.sqlite` | 1,089,536 | `9941ca2c3426366fe54a15d991603f3d8251f4cab3ee05931fa4d705f3b2a354` |
| `derived/geo/national-status.json` | 59 | `9722d81afd22094f82f7acc52b7da404ea16f39f961610658c041525bea4bcdd` |
| `derived/geo/socal-cells.json` | 2 | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |

Two builds run one after the other gave identical checksums for all five files. Geofabrik replaces
`northern-zone-latest` every day, so a later download gives a different source checksum and slightly different counts.

What the map holds:

| Layer | Features | | Layer | Features |
|---|---|---|---|---|
| Roads | 279,704 (16,948 with a name or number) | | Land use and parks | 15,200 |
| Building outlines | 459,240 | | Water areas | 3,360 |
| Canals, rivers and drains | 1,626 | | Wetland | 859 |
| Place labels | 1,417 | | Railways (including the Metro) | 1,335 |

Help points: 14,282 in 39 classes, 6,869 of them with a name. The largest: parks 4,883, schools 1,407, hospitals
1,009, toilets 1,000, convenience stores 866, clinics 813, fuel 522, pharmacies 430, shelters 386, fountains 280,
police 247, drinking water 250, water towers 224, dentists 222, supermarkets 221, doctors 137, fire stations 43. The
full list is in `IN-DL.build.json`.

The place finder has 8,286 rows: 1,417 places (8 cities, 8 towns, 298 suburbs, 10 quarters, 196 villages, 484
neighbourhoods, 410 localities and 3 hamlets) and the named help points.

## What was checked, and how

`tools/check_region_map.py` passed every file check and every engine check on the build above. With `--engine` it
copies the map into a fresh data folder with an empty library, blocks every network connection, loads `server.py`, and
makes the calls the app makes:

- **Map display.** Tiles at zoom 10, 13 and 16 draw roads, water, land, railways and place labels.
- **Pins.** 139 groups around 28.6550, 77.0850.
- **Nearest help.** A police post at 0.48 km and three hospitals within 0.72 km.
- **Place search in English.** "Connaught Place" finds the suburb and its police station; "AIIMS" finds AIIMS
  Emergency and its urban health centre; "Chandni Chowk" and "Dwarka" find the places.
- **What the app is told.** `map_contents` reports 39 kinds within 76.69, 28.28, 77.45, 29.03.

It was also opened in a browser through `python3 server.py`, in light and dark mode: at Connaught Place the map drew
streets, the Metro and pins, and "Nearest to the map center" listed a hospital at 50 m, the Connaught Place police
station at 310 m, Lady Hardinge Medical College at 470 m and the Barakhamba Road fire station at 650 m. Screenshots are
in the pull request.

**Not checked:** the packaged desktop app, and installing through setup (no installer or manifest entry is part of
this change).

## What is and is not in it

**In it**

- Streets and paths of every class `tools/build_map.py` draws, with the same zoom rules, and railways: Indian Railways
  lines and the Delhi Metro.
- The Yamuna, canals and drains, lakes and ponds, wetland; land use, parks and protected areas (the Ridge forests);
  building outlines from OpenStreetMap.
- Place labels and help points in the classes the engine already names.
- Two names, as the builder keeps them: the local `name` as the label and `name:en` in the place finder when the two
  differ.

**Not in it**

- **Addresses and PIN codes.** OpenStreetMap's Indian address data is thin, and the place finder has no PIN code
  handling: a query such as `110001` is read as an address. REGIONS-IN.md keeps six-digit PIN support as a requirement
  for the shared postcode design; this map does not attempt it.
- **Terrain, crops, the water and dam inventory, `buildings.sqlite`.** As for Bangkok.
- **Government lists.** Every point is from OpenStreetMap. The "shelter" points are structures tagged as shelters, not
  official relief or evacuation shelters.
- **Anything outside the box.** A feature that crosses the box is kept whole.

**Known limits**

- **Hindi search finds little.** Most Delhi features carry an English `name`, and their Hindi name is in `name:hi`,
  which the builder does not read. So "दिल्ली" finds Hindi-named shops and schools but not Delhi itself, and
  "कनॉट प्लेस" finds a chemist rather than Connaught Place. Keeping `name:hi` (or `name:<local>` generally) in the place
  finder would fix it; that is a change to the builder, left for the shared design.
- **Completeness follows OpenStreetMap.** 7,413 help points have no name. Nothing was compared against an official
  count.
- **The page header's date, the home view, the "US" button and the "What this map covers" panel** still describe the
  US map, as noted for Bangkok.

## Licence and attribution

All data in this map is from OpenStreetMap, © OpenStreetMap contributors, under the Open Database License 1.0, taken
from Geofabrik's India northern zone extract. A database built from it, which this map is, is offered under the ODbL as
well. The credit and the data's date are written into `meta` in `national.sqlite` and into `IN-DL.build.json`. The box
comes from Natural Earth, which is in the public domain; nothing from it is in the map.
