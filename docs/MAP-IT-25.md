# A detailed map of Lombardia (`IT-25`): how it is built and what it holds

A worked example for `tools/build_region_map.py` in Italy, after Bangkok
([MAP-TH-10.md in #80](https://github.com/Immortal-Protocols/lastbook/blob/a453274353b2816b4ccb0114310024ea54c970b2/docs/MAP-TH-10.md)),
Central, Paraguay
([MAP-PY-11.md in #152](https://github.com/Immortal-Protocols/lastbook/blob/aa4f9e7502038d2d31ab93f29272e109709dfae9/docs/MAP-PY-11.md))
and Region Hovedstaden
([MAP-DK-84.md in #180](https://github.com/Immortal-Protocols/lastbook/blob/eb15773c427d2c3ab50d151b4ea74962ddbe37bd/docs/MAP-DK-84.md)),
built with that tool unchanged. It is the first map from Italy and the first from a region with no sea coast. It uses
the id and the box that [REGIONS-IT.md](REGIONS-IT.md) proposes, and covers the whole of that box.

The tool, its checker and the Bangkok page come from pull request #80, and the Paraguay and Copenhagen pages from #152
and #180; none of them is in this repository until they are merged, so the links above point to each file at the head
commit of its pull request. REGIONS-IT.md was merged in #225.
This map was built and checked with the tool as it was at commit `a453274` (#80's head when this was written), the
same commit #152 and #180 used. The files at that commit:

- [`tools/build_region_map.py`](https://github.com/Immortal-Protocols/lastbook/blob/a453274353b2816b4ccb0114310024ea54c970b2/tools/build_region_map.py)
- [`tools/check_region_map.py`](https://github.com/Immortal-Protocols/lastbook/blob/a453274353b2816b4ccb0114310024ea54c970b2/tools/check_region_map.py)
- [`tools/test_build_region_map.py`](https://github.com/Immortal-Protocols/lastbook/blob/a453274353b2816b4ccb0114310024ea54c970b2/tools/test_build_region_map.py)
- [`docs/MAP-TH-10.md`](https://github.com/Immortal-Protocols/lastbook/blob/a453274353b2816b4ccb0114310024ea54c970b2/docs/MAP-TH-10.md)

If the tool changes before #80 is merged, the build and the checks here need to be run again.

It adds no code and no app change. The map is not downloaded by setup and is not in any pack.

## The id and the box

- **Id.** `IT-25` is Lombardia's ISO 3166-2 code, as proposed in REGIONS-IT.md. The id is the maintainers' to change.
- **Box.** 8.34, 44.52, 11.58, 46.79 (west, south, east, north): Lombardia's box from ISTAT's 2026 boundaries with the
  0.15° margin, from REGIONS-IT.md.
- **What the rectangle holds.** Measured against ISTAT's 2026 region outlines, 58,065 of the 68,134 help points (85 %)
  are in Lombardia, 9,192 in Piemonte, 556 in Liguria, 47 in Veneto, 34 in Emilia-Romagna, 27 in Trentino-Alto
  Adige/Südtirol and 213 outside Italy (Switzerland) or on the border. Of the 384 hospital rows, 336 are in Lombardia,
  45 in Piemonte and 3 in Liguria.
- **No sea.** Lombardia has no sea coast, so the tool's sea step has nothing to do: the build read 0 coastline ways and
  wrote no sea polygon. The lakes are kept as water areas from OpenStreetMap, like any other water (see "What the map
  holds").
- **#84** lists all of Italy as one country map set, `eu-it`, from Geofabrik's whole-country extract. This map is one
  region of it at the same level of detail as the other maps built with #80's tool.

## Build it

The build machine needs Python 3.11 or later and pyosmium, and about 6.2 GB of free memory for the tool (see "Memory").
Nothing else is installed, and the tool downloads nothing.

```bash
# 1. The source: Geofabrik's Nord-Ovest extract of Italy (OpenStreetMap, ODbL 1.0), which holds Lombardia,
#    Piemonte and the rest of the north-west. About 600 MB. This is the dated file with the data this map was built
#    from (see "The input, and how far it can be repeated"); the build saw it as nord-ovest-latest.osm.pbf, and that
#    name is written into the map's meta, so it is renamed after the check.
curl -LO https://download.geofabrik.de/europe/italy/nord-ovest/nord-ovest-261117.osm.pbf
curl -LO https://download.geofabrik.de/europe/italy/nord-ovest/nord-ovest-261117.osm.pbf.md5 && md5sum -c nord-ovest-261117.osm.pbf.md5
mv nord-ovest-261117.osm.pbf nord-ovest-latest.osm.pbf
#    For newer data, take https://download.geofabrik.de/europe/italy/nord-ovest/nord-ovest-latest.osm.pbf instead.

# 2. A build environment with pyosmium.
python3 -m venv derived/buildenv && derived/buildenv/bin/pip install osmium

# 3. Build.
derived/buildenv/bin/python tools/build_region_map.py nord-ovest-latest.osm.pbf \
    --id IT-25 --name Lombardia --bbox 8.34,44.52,11.58,46.79 --out derived/regions

# 4. Check the files, then check that the engine can use them with every connection blocked.
python3 tools/check_region_map.py derived/regions/IT-25
python3 tools/check_region_map.py derived/regions/IT-25 --engine \
    --find "Duomo di Milano" --find Niguarda --find Monza --find Navigli --find "Città Studi" --find Citta \
    --find Milan --find Bergamo --find Brescia --find Mantova --find Sirmione --find Bormio --find "Lago di Como" \
    --near 45.4642,9.1916
python3 tools/check_region_map.py derived/regions/IT-25 --engine --find "Città Alta" --find Bergamo --near 45.7037,9.6627
```

The first `--near` point is Piazza del Duomo in Milan, the second the upper town of Bergamo.

To look at it in the app's interface, give the engine a data folder that holds the map and an empty library:

```bash
mkdir -p /path/to/LombardiaData/library-data && echo '[]' > /path/to/LombardiaData/library-data/catalog.json
cp -R derived/regions/IT-25/derived derived/regions/IT-25/map-set.json /path/to/LombardiaData/
python3 server.py --data /path/to/LombardiaData --port 8890
# then open the address it prints, choose Map, and go to:  #/map?lat=45.7037&lon=9.6627&z=15  (Bergamo)
# Lake Garda:  #/map?lat=45.55&lon=10.65&z=11
```

## Memory

The tool keeps every feature it reads in memory until the whole file has been read, then writes them. The build below
ran on a cloud VM with 52,214 MiB of memory and 8 vCPUs (x86-64), under a watcher that measured the tool every 10
seconds. The tool's peak memory was 6,159 MB, with more than 43 GB still free on the machine.

An earlier attempt on a smaller machine (4 ARM cores, 16 GB of memory, much of it in use) was stopped by its watcher
after 1,680.8 seconds, when the tool had reached 5,984 MB and free memory had fallen to 912 MB. On that machine a
build of only the box of the Città metropolitana di Milano (8.55, 45.01, 9.71, 45.80) finished with a peak of
3,270 MB. Nothing below describes that smaller build.

## The build this was checked with

| | |
|---|---|
| Source file | `nord-ovest-latest.osm.pbf` (Geofabrik's file, downloaded on 18 November 2026), 595,652,765 bytes |
| Source SHA-256 | `823c1fdc12aca0d2d87290026c5cad9d82c06dcba1c76de0ac7e10d19e3e50b8` |
| Source MD5 (matches Geofabrik's `.md5`) | `e8952c3c63ffe644f1b497a95cc6df85` |
| OpenStreetMap data up to | 2026-11-17T21:24:30Z (from the file's header) |
| Built on | 18 November 2026, Linux on x86-64, Python 3.13.18, pyosmium 4.3.2 from PyPI |
| Build time | 1,037 seconds (893 of them reading the whole Nord-Ovest file and keeping the box) |
| Peak memory of the tool | 6,159 MB |
| Box | 8.34, 44.52, 11.58, 46.79 (west, south, east, north) |

| File | Bytes | SHA-256 |
|---|---|---|
| `derived/geo/national.sqlite` | 874,303,488 | `844fde1493362473639c8e8bb9009b2f57273a6bce13af90c097751df5cd11e9` |
| `derived/geo/map.sqlite` | 36,864 | `e7ac775746a8725815e5238b9e8e14659769296ab8ed013771c71a9923795f35` |
| `derived/geo/places.sqlite` | 7,585,792 | `99c31917c795af8a494b005ddae247fd18e3c63f99160a15b650239dfa6d2547` |
| `derived/geo/national-status.json` | 60 | `c90778102b7d4a9bd1e6521d159f4e07c12cb35911c66045436c82b456e479bd` |
| `derived/geo/socal-cells.json` | 2 | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |

The map set is 881,926,206 bytes. A second build from the dated input gave the same bytes in every file (see "The
input, and how far it can be repeated").

## The input, and how far it can be repeated

The build read `nord-ovest-latest.osm.pbf`, which Geofabrik replaces every day; a download of it today gives newer data,
a different checksum and slightly different counts. The same data is in a dated file:
[`nord-ovest-261117.osm.pbf`](https://download.geofabrik.de/europe/italy/nord-ovest/nord-ovest-261117.osm.pbf)
([`.md5`](https://download.geofabrik.de/europe/italy/nord-ovest/nord-ovest-261117.osm.pbf.md5)), downloaded again on
22 November 2026 and compared with the file the build used:

| | File the build used | Dated file, 22 November |
|---|---|---|
| Bytes | 595,652,765 | 595,652,765 |
| OpenStreetMap data up to (header) | 2026-11-17T21:24:30Z | 2026-11-17T21:24:30Z |
| Replication sequence (header) | 4032 | 4032 |
| Updates address (header) | `.../europe/italy/nord-ovest-updates` | `.../europe/italy/nord-ovest/updates` |
| MD5 | `e8952c3c63ffe644f1b497a95cc6df85` | `ee4424746ea76c6b1b00c3ad5b096433` |
| SHA-256 | `823c1fdc...19e3e50b8` | `374846d5...161a8521209` |

The two files differ in 3 bytes, all in the file header, where Geofabrik has since moved the Nord-Ovest files into a
`nord-ovest/` folder; every data block is the same. The tool reads only the date from the header, so a build from the
dated file should give the same map. The full SHA-256 of the file the build used is
`823c1fdc12aca0d2d87290026c5cad9d82c06dcba1c76de0ac7e10d19e3e50b8`, and of the dated file
`374846d5bc0857324bd17b529ff4ed5551bd3dbea444f36ab0786161a8521209`.

That build was run on 22 November 2026, following "Build it" above: the dated file was downloaded on the build machine,
its `.md5` checked, the file renamed, and the same build and check commands run with the tool at `a453274`. The
machine was a cloud VM of the same size as the first (52,214 MiB, 8 vCPUs, x86-64) with a different processor (AMD
EPYC 7B12 instead of Intel Xeon), with Python 3.13.18, SQLite 3.45.1 and the same package versions as the first build
(pyosmium 4.3.2). It took 703 seconds, with a peak memory of 6,158 MB. The result:

- The five files in the table above and `map-set.json` have the same sizes and the same SHA-256 as the first build.
- `IT-25.build.json` differs in three values only: the source SHA-256 (the dated file's, since the header differs),
  the build time (`built`) and the seconds it took. Every count is the same: 4,378,939 features, 68,134 help points,
  58,691 place finder rows.
- The file checks, both engine runs and the 9 tests gave the same output as for the first build, apart from the
  folder name in the command line.

The limit: Geofabrik's index on 22 November 2026 listed daily Nord-Ovest files for 12 to 21 November, and older ones
only for the first of September, October and November 2026 and the first of January of each year since 2016. No stated
period for keeping the daily files was found, so the 17 November file may go when it ages out. After that the exact
input cannot be downloaded again; the checksums above let anyone with a copy confirm it is the same file, and a build
from a later file gives a map of a later date, not this one.

## What the map holds

| Layer | Features | | Layer | Features |
|---|---|---|---|---|
| Roads | 1,265,599 (434,327 with a name or number) | | Land use and parks | 399,571 |
| Building outlines | 2,449,932 | | Water areas | 13,427 (9,381 lakes and ponds, 2,803 river areas, 1,243 reservoirs) |
| Streams, rivers, canals and drains | 209,641 | | Wetland | 1,008 |
| Place labels | 25,911 | | Railways | 13,413 |
| Beaches | 437 | | Sea | none |

4,378,939 features in all. The large lakes are named water areas drawn from zoom 7: Lago Maggiore, Lago di Garda, Lago
di Como, Lago di Lugano and Lago d'Iseo, with Lago d'Idro, Lago d'Orta, Lago di Varese and smaller ones after them.

Help points: 68,134 in 40 classes, 32,780 of them with a name. The largest: drinking water 14,663, parks 9,337, schools
4,107, fuel 3,493, pharmacies 3,077, supermarkets 2,958, communication towers 2,343, car repair 2,270, toilets 2,068.
For emergencies: hospitals 384, clinics 443, doctors 804, dentists 745, pharmacies 3,077 (and 380 chemists), fire
stations 159, police 1,027, shelters 1,293, fountains 2,022, springs 1,988, water towers 598, water works 644. By
province, the most are in Milano (13,888), Brescia (9,937), Bergamo (6,783) and Varese (5,173). The full list is in
`IT-25.build.json`.

The place finder has 58,691 rows: 25,911 places (15 cities, 223 towns, 439 suburbs, 209 quarters, 2,870 villages,
7,732 hamlets, 1,153 neighbourhoods, 13,268 localities and 2 islands) and 32,780 named help points.

## What was checked, and how

`tools/check_region_map.py` ended with "all checks passed" for the 37 file checks, for the 20 engine checks with the
Milan point and for the 9 with the Bergamo point. Apart from the first, which checks that the engine reads a copy of
the map, each engine check passes when the answer is not empty: a place search passes when it returns any row, whatever
the row is. So the pass count shows that the engine answered every call from the map with no network; it does not show that every search found the place that was meant. The file checks compare
the files with the build record and with docs/MAPS.md (sizes, SHA-256, tables, classes, the box); the one search among
them, for "Milano", also counts rows only (272).

Of the 29 engine checks:

- 15 are place searches, each meant to find one place (for "Citta", a place with an accent). 11 found it as the
  first row. 4 returned rows that are not the place meant: "Duomo di Milano", "Navigli", "Lago di Como" and "Citta". None returned no rows.
- 14 have no single right answer (counted over both runs): the engine reading the copy, three tiles (each must hold roads), the
  pins, the nearest help and what the app is told. For nearest help, a separate distance count over the
  map's help points gave the same first rows.

The place searches, with the first row the engine returned. "The place meant" was judged by hand from the name, the
kind and the position of that row. Rows are counted to 20, the most the engine returns.

| Run | Search | Rows | First row | The place meant? |
|---|---|---|---|---|
| Milan | Duomo di Milano | 20 | Muzza di Milano (locality) | No. The cathedral is not in the place finder |
| Milan | Niguarda | 7 | Niguarda (suburb) | Yes |
| Milan | Monza | 20 | Monza (city) | Yes |
| Milan | Navigli | 20 | Cernusco sul Naviglio (town) | No. Milan's Navigli district has no row of that name |
| Milan | Città Studi | 7 | Città Studi (suburb) | Yes |
| Milan | Citta | 20 | Cittadella (suburb) | No. Meant to find a Città name typed without the accent; Cittadella has no accent |
| Milan | Milan | 20 | Milano (city) | Yes, from the English name |
| Milan | Bergamo | 20 | Bergamo (city) | Yes |
| Milan | Brescia | 20 | Brescia (city) | Yes |
| Milan | Mantova | 20 | Mantova (city) | Yes |
| Milan | Sirmione | 7 | Sirmione (town) | Yes |
| Milan | Bormio | 9 | Bormio (town) | Yes |
| Milan | Lago di Como | 2 | spartiacque lago di Como/fiume Seveso (275m) (locality) | No. The lake is a water area, not a place |
| Bergamo | Città Alta | 4 | Città Alta (suburb) | Yes |
| Bergamo | Bergamo | 20 | Bergamo (city) | Yes |

The checks without one right answer. With `--engine`, every connection blocked and an empty library:

- **Map display.** Tiles at zoom 10, 13 and 16 around Piazza del Duomo and around Bergamo's upper town: roads, water,
  land, railways, waterways and place labels at the wider zooms, 142 building outlines in one zoom-16 tile in each.
- **Pins.** 165 pin groups around Piazza del Duomo, 75 around Bergamo's upper town.
- **Nearest help.** In Milan, pharmacies at 0.19, 0.23 and 0.24 km and the local police headquarters at 0.27 km; in
  Bergamo, a pharmacy and the municipal police at 0.08 km.
- **What the app is told.** 40 kinds, within 8.34, 44.52, 11.43, 46.62.

The rows, the counts and the distances above are from the logs of the checker's runs and from the same calls made again
on 22 November 2026 on another machine (Linux on ARM, Python 3.13.5) with the tool at `a453274`, which gave the same
checker output. Accents are folded: asked of the engine in that second run, outside the checker, "Citta Alta" and
"Citta Studi" typed without the accent find Città Alta and Città Studi first.

`tools/test_build_region_map.py`: 9 tests pass with pyosmium.

It was also opened in a browser through `python3 server.py`, which serves the same `web/` interface the desktop app
shows. In light mode the map drew at zoom 15 over Bergamo's upper town, with street names (Via delle Mura, Piazza Rosate)
and pins, and at zoom 11 over the southern part of Lake Garda, drawn as one water area with the pins of the western
shore; no lake name was shown at that zoom. The "Nearest to the map center" list filled in from the map's help points
(for the lake view, a tourist medical service and pharmacies, one of them in Sirmione). The browser's list of loaded resources held 57 requests, all to the local server.

**Not checked:** the search box in the interface (the place finder was checked through the engine, above), dark mode,
the packaged desktop app, installing through setup (no installer or manifest entry is part of this), and the lake
names at closer zooms.

## What is and is not in it

**In it**

- Streets and paths of every class `tools/build_map.py` draws, with the same zoom rules, for all of Lombardia and the
  edges of the regions around it that are in the Nord-Ovest extract.
- Lakes, rivers, canals and drains, wetland, land use, parks and building outlines from OpenStreetMap.
- Place labels and help points in the classes the engine already names (`HELP` in `server.py`).

**Not in it**

- **Addresses.** Italy's national register of street numbers (ANNCSU) is described in REGIONS-IT.md, but the tool does
  not build an address index, and the engine could not read Italian addresses yet: the street type and name come
  before the number. Roads are in the map but not in the place finder, so a street cannot be searched by name.
- **Terrain, contours and the 3D view**, **crops** and the **water and dam inventory**. Italian sources for these are
  in REGIONS-IT.md. In a region with the Alps in its north, terrain is the largest gap.
- **`buildings.sqlite`.** Outlines are in `national.sqlite`; there are no heights.
- **Government lists.** Every point here is from OpenStreetMap. REGIONS-IT.md describes the Ministry of Health's list
  of pharmacies, which was not used.

**Known limits**

- **The box reaches past the source.** The box takes in parts of Veneto, Trentino-Alto Adige/Südtirol, Emilia-Romagna
  and Switzerland, which are not in Geofabrik's Nord-Ovest extract, so those parts are nearly empty: 35 help points in
  the province of Verona, which holds the eastern shore of Lake Garda. A complete map of that shore needs the Nord-Est
  extract as well, which the tool does not merge.
- **The box is not the region.** 9,192 help points and 45 hospital rows are in Piemonte, and every place's detail line
  says "Lombardia", the `--name` given, including places in Piemonte, Liguria and Switzerland.
- **Landmarks and lakes are not in the place finder.** "Duomo di Milano" does not find the cathedral and "Lago di
  Como" does not find the lake: places of worship and water are not help-point classes or places, so the search
  returns other rows with those words in their names. "Navigli" does not find Milan's Navigli district, which has no
  place row of that name in this map.
- **Completeness follows OpenStreetMap.** 35,354 help points have no name. Nothing was compared against an official
  count.
- **The page header, the units and the credits are the US map's.** The header says "what was mapped by 25 Oct 2026",
  while this map's date is in `meta` (`data_as_of`, 17 November 2026). Longer distances in the nearest list are shown in
  miles and the scale bar adds feet, the search box asks for an "address, town or ZIP", there is a button labelled "US",
  and the credit line lists USGS, USDA, NOAA and other US sources that are not in this map. The same holds for the other
  maps built with #80's tool.

## Licence and attribution

All data in this map is from OpenStreetMap, © OpenStreetMap contributors, under the Open Database License 1.0, taken
from Geofabrik's Nord-Ovest extract of Italy. A database built from it, which this map is, is offered under the ODbL as
well. The credit and the date of the data are written into `meta` in `national.sqlite` and `map.sqlite`, and into
`IT-25.build.json`. The app's map already shows "© OpenStreetMap contributors". The box was computed from ISTAT's
boundaries (CC BY 4.0), as described in REGIONS-IT.md; no ISTAT data is in the map.
