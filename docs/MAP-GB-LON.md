# Greater London (GB-LON): a working offline map

A detailed offline map of Greater London, with a place finder for British postcodes, places and roads, built from
redistributable sources by one command and kept in its own folder. It follows the file formats in [MAPS.md](MAPS.md)
and uses the code and box proposed for London in the UK region proposal (`docs/REGIONS-UK.md`, #103).

This is a builder and a testable map set, not an installer. The shared region download is still being designed, so
nothing here touches `packaging/`, the release manifest or the setup flow.

## Build it

```sh
python3 tools/build_region_gb.py fetch    # downloads the sources, about 333 MB, into derived/regions/GB-LON/source/
python3 tools/build_region_gb.py build    # writes derived/regions/GB-LON/data/ (about 50 s)
python3 tools/build_region_gb.py demo     # adds an empty library beside it, for trying the map on its own
python3 tools/build_region_gb.py check    # validates it; exits non-zero on any failure
python3 server.py --data derived/regions/GB-LON/demo --no-index
```

It needs Python 3.9 or newer and its standard library, with no GDAL and no other packages. `fetch` is the only step
that uses the network. Everything is written under `derived/regions/GB-LON/`, so no existing map set changes.
`build.json` there records every source (URL, dated file name, data date, licence, size, SHA-256) and every output
(size, SHA-256). The extracted GeoPackage stays in `work/` for rebuilds and can be deleted.

## Sources

| What | Source | Licence | Attribution |
|---|---|---|---|
| Streets, water, land use, rail, buildings, place labels and help points | OpenStreetMap via Geofabrik, `greater-london-YYMMDD-free.gpkg.zip` (the dated name is recorded), cut by `tools/build_map.py` unchanged | ODbL 1.0 | © OpenStreetMap contributors (already on the map) |
| The outline the place finder is clipped to | Geofabrik, `greater-london.poly` | ODbL 1.0 | as above |
| Postcodes with their locality and borough, settlements, named and numbered roads, stations, schools, hospitals | Ordnance Survey, OS Open Names, CSV for Great Britain | Open Government Licence v3.0 | the three lines below |
| Postcodes that Open Names leaves out | Ordnance Survey, Code-Point Open, CSV for Great Britain | Open Government Licence v3.0 | the three lines below |

Both OS downloads hold a `licence.txt` that points to `www.ordnancesurvey.co.uk/opendata/licence`. On 17 November
2026 that address redirected (HTTP 301) to the Open Government Licence v3.0 at the National Archives, which allows
redistribution and adaptation if the provider's attribution statement is kept. Both files give the same statement:

> Contains OS data © Crown copyright and database right 2026.
> Contains Royal Mail data © Royal Mail copyright and database right 2026.
> Contains National Statistics data © Crown copyright and database right 2026.

The builder writes these lines, with the OpenStreetMap credit, into `map.sqlite`'s `meta` (`credit`), into
`map-set.json` (`credit`) and into `build.json`. The app does not show them yet: the credit line under the map is still
the fixed US one. Showing a map set's own credit is part of #103.

Code-Point Open and Open Names come from the same postcode data. Of 1,749,385 Code-Point postcodes, 1,742,582 are also
in Open Names, which adds each one's locality and borough. The builder takes postcodes from Open Names and adds the
6,803 found only in Code-Point (669 of them inside London), naming their locality from the postcode's sector.

### British National Grid

OS gives eastings and northings in the British National Grid (OSGB36). The builder converts them to WGS 84 with the
Ordnance Survey's published formulas: transverse Mercator on the Airy 1830 ellipsoid, then the seven-parameter Helmert
transformation, which OS gives as good to about 5 m. The tests check the conversion against OS's worked example to
better than 1 cm, and check that SW1A 2AA lands within 30 m of 10 Downing Street. `check` compares 1,828 hospitals,
schools, libraries, police and fire stations that OS and OpenStreetMap each mapped independently under the same name.
The median offset is 1.7 m east and 0.2 m north, so there is no datum shift between the two.

## What the build holds

Built on 17 November 2026 from OpenStreetMap data of 16 November 2026 (`greater-london-261116-free.gpkg.zip`), OS Open
Names 2026-10 and Code-Point Open 2026-11. `build` took 51 seconds on an Apple silicon Mac.

| File | Size | SHA-256 (this build) | Holds |
|---|---|---|---|
| `derived/geo/national.sqlite` | 326.8 MB | `3aca8a7a…4291b0` | 572,919 road features, 1,192,399 building outlines, water, land, rail and 764 place labels; 26,692 help and supply points in 37 classes |
| `derived/geo/map.sqlite` | 32 KB | `69512e0b…165980` | empty, as in a US state map; carries the map's source, date, box and credit |
| `derived/geo/places.sqlite` | 31.9 MB | `5ea15f02…15bb` | 273,417 entries: 181,771 postcodes, 316 postcode districts, 33 boroughs, 760 settlements and suburbs, 65,506 roads, stations, schools and other named places, and 19,695 named OpenStreetMap points and places |
| `derived/geo/national-status.json`, `socal-cells.json` | 62 B | | as in a state map |
| `map-set.json` | 593 B | | name `GB-LON`, title, the sizes of the map files, and the credit |

Full checksums are in `build.json`. They identify one build: the map files record their build time, so two builds of
the same sources differ in those bytes, not in content.

Help points include 200 hospitals, 1,290 pharmacies, 111 fire stations, 134 police stations, 560 drinking-water taps
and 1,284 supermarkets, all from OpenStreetMap.

## How the place finder works

`places.sqlite` has the same tables as the US one (`place`, `place_fts`), so `server.places()` reads it unchanged.

- **Postcodes** are kept as `SW1A 2AA`, with the locality and borough as the detail. A postcode typed without its space
  (`sw1a2aa`) is looked up with it. That is the one engine change: `postcode_query()` in `server.py`, which only adds
  the space and changes the letter case, and the place index ignores case.
- **Postcode districts** (`SW1A`) and **boroughs** sit at the middle of their postcodes. Picking one zooms to town
  level (`web/map.js`), as a town or ZIP code does.
- **Postcodes rank last.** Each postcode's detail names its locality and borough, so a search for "Paddington" or
  "Tower Hamlets" matches thousands of them. Ranked any higher, they would push the station, the roads and the borough
  out of the engine's first 200 matches. A postcode typed as such still comes first, because an exact name always
  sorts ahead. `app/tests/test_region_gb.py` holds a test for this.
- The place finder is clipped to Geofabrik's outline, so everything it finds has streets drawn around it. That
  includes a few places just over the Greater London boundary, inside the extract's buffer.
- A named OpenStreetMap point or place label is added unless OS has the same name within 300 m (2 km for a place
  label).

## Checks

`check` runs 41 checks:
- every output against `build.json`; `map-set.json`'s name, sizes and that the set holds nothing else
- SQLite integrity and journal mode
- minimum counts for roads, buildings, six kinds of help point, postcodes, districts, boroughs, roads and settlements
- every point and place inside the region box
- the OS and OpenStreetMap agreement above

It then loads `server.py` on the demo folder with every network connection refused, and asks the engine what the app
asks it:

| Query | First result |
|---|---|
| `SW1A 2AA` and `sw1a2aa` | `SW1A 2AA`, postcode, City of Westminster |
| `SW1A` | `SW1A`, postcode district, City of Westminster |
| `Croydon` | Croydon (settlement), then Croydon (borough) |
| `Tower Hamlets` | Tower Hamlets, borough |
| `Downing Street` | Downing Street, road, City of Westminster, SW1A |
| `East Croydon` | East Croydon, railway station |
| `Paddington` | Paddington (settlement), then Paddington (railway station), before any postcode |
| nearest hospital to Westminster | St Thomas' Hospital, 0.77 km |
| zoom-15 tile over Westminster | 1,213 roads and 341 buildings |

It also checks that the Map page opens on the area itself, from the pins' bounds.

Opened in a browser through `server.py` on the demo folder, in light and dark mode:
- the map opens over Greater London
- `sw1a2aa` puts the marker on Downing Street, with New Scotland Yard, water taps and pharmacies nearby
- `Croydon` lists the town, the borough, its roads and the CR postcode districts

Every request went to the local server.

## Limits

- **No street addresses.** Overture has none for the UK, and there is no open UK address file with text and
  coordinates (`docs/REGIONS-UK.md`). A house number typed with a street (`10 Downing Street`) goes to address search,
  which has no London index and finds nothing. The road can be found by name. Address search from OpenStreetMap is part
  of #103.
- **The app's own words are still American**, as #79 also notes:
  - the fixed "mapped by 25 Oct 2026" line
  - "ZIP" in the search box
  - the US credit line under the map
  - feet beside metres on the scale and contours
  - US sources in the map details panel

  These are left to #103 and to the maintainers' Units setting.
- **Not built:** terrain, crops, the water and dam inventory, building heights and aerial photos. The Layers panel
  offers only what the map holds.
- **Northern Ireland is not covered**, and neither is any other region. OS Open Names and Code-Point Open are Great
  Britain only. Other English regions have no Geofabrik extract of their own and would need cutting from the England
  file.
- **`GB-LON` is not a valid map ID for setup yet.** Setup's map and address-index IDs accept two capital letters only
  (`engine/setup/manifest.py`, `engine/setup/install.py`). It is the same open question as `DE-BE` and `TH-10`.
- **The demo folder's `pack.json`** says only which map it holds. Like a published pack's, it makes the Map page open on
  the map's own area and offer only its layers. It is not a pack and is not meant to ship.
