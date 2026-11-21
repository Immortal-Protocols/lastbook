# Berlin (DE-BE): a working offline map

The first map outside the United States: streets, named places, help points and street addresses for Berlin, built
from redistributable sources by one command, kept in its own folder, and searchable offline. It follows the plan in
[REGIONS-DE.md](REGIONS-DE.md) and the file formats in [MAPS.md](MAPS.md). The region keeps its full ID, `DE-BE`: a bare
`DE` means Delaware.

This is a builder and a testable map set, not an installer: the shared region download is still being designed, so
nothing here touches `packaging/`, the release manifest or the setup flow.

## Build it

```sh
python3 tools/build_region_de_be.py fetch    # downloads the sources, about 270 MB, into derived/regions/DE-BE/source/
python3 tools/build_region_de_be.py build    # writes derived/regions/DE-BE/data/ (about 25 s)
python3 tools/build_region_de_be.py check    # validates it; exits non-zero on any failure
python3 tools/build_region_de_be.py demo     # adds an empty library beside it for trying the map alone
python3 server.py --data derived/regions/DE-BE/demo --no-index
```

Python 3.9 or newer and its standard library; no GDAL, no other packages. `fetch` is the only step that uses the
network. Everything is written under `derived/regions/DE-BE/`, so no existing map set changes. `build.json` there
records every source (URL, dated file name, data date, licence, size, SHA-256) and every output (size, SHA-256).

## Sources

| What | Source | Licence | Attribution |
|---|---|---|---|
| Streets, water, land use, buildings, named places and points | OpenStreetMap via Geofabrik, `berlin-YYMMDD-free.gpkg.zip` (the dated name is recorded) | ODbL 1.0 | © OpenStreetMap contributors (already on the map) |
| Street addresses (house number, suffix, postcode, locality) | Geoportal Berlin WFS `adressen_rbs` | Datenlizenz Deutschland Zero 2.0 | none required |
| Hospitals | Geoportal Berlin WFS `krankenhaeuser` (plan hospitals and other hospitals) | dl-de/zero-2.0 | none required |
| Pharmacies | Geoportal Berlin WFS `apotheken` | dl-de/zero-2.0 | none required |
| Fire stations | Geoportal Berlin WFS `feuerwehr` | dl-de/zero-2.0 | none required (one catalogue entry says dl-de/by-2.0; the service says Zero) |
| Police stations | Geoportal Berlin WFS `polizei` | dl-de/zero-2.0 | none required |
| Districts (Bezirke) and localities (Ortsteile) | Geoportal Berlin WFS `alkis_bezirke`, `alkis_ortsteile` | dl-de/zero-2.0 | none required |

Postcode areas are placed at the middle of their own addresses rather than taken from the postcode polygons, which are
CC BY 3.0 DE; that keeps the map to ODbL plus sources without an attribution duty.

For the four official kinds, the Geoportal records replace OpenStreetMap's points, so each facility has one pin from
the public register. Everything else, including street hand pumps, comes from OpenStreetMap.

## What the build holds

Built on 17 November 2026 from OpenStreetMap data of 16 November 2026 (`berlin-261116-free.gpkg.zip`) and the
Geoportal services as served that morning. A full `fetch`, `build`, `check` took under two minutes.

| File | Size | SHA-256 (this build) | Holds |
|---|---|---|---|
| `derived/geo/national.sqlite` | 188.1 MB | `f92fdce0…0c457` | 467,739 road features plus water, land, rail, buildings and places; 21,000-odd help and supply points |
| `derived/geo/map.sqlite` | 32 KB | `5d421123…650dd` | empty, as in a US state map; carries the map's source and date |
| `derived/geo/places.sqlite` | 3.3 MB | `1105067b…3f38` | 12 districts, 97 localities, 193 postcode areas, 11,321 streets, 13,488 named points, 196 named places |
| `derived/geo/addresses/DE-BE.sqlite` | 51.6 MB | `5e152e53…3965` | 404,303 addresses; a sidecar, as the US address indexes are |
| `map-set.json` | 191 B | | name `DE-BE` and the sizes of the map files |

Help points: 111 hospitals, 702 pharmacies, 102 fire stations and 37 police stations from the Geoportal (replacing
59, 685, 103 and 68 OpenStreetMap points), and 2,080 street hand pumps from OpenStreetMap.

Full checksums are in `build.json`. They identify one build: the map and address files record their build time, so two
builds of the same sources differ in those bytes, not in content.

## Checks

`check` verifies, and fails on any miss:

- every output file has the size and SHA-256 recorded at build time; `map-set.json` is named `DE-BE` and its sizes match;
- every SQLite file passes `PRAGMA integrity_check`;
- streets are present, and each help kind has a plausible count (hospitals, pharmacies, fire stations, police, pumps);
- every help point and address lies inside Berlin's box from `regions-de-proposed.json`, and every address has a
  five-digit postcode;
- three addresses are found through `engine/address_search.py` exactly, and an unknown house number returns nothing;
- the place finder has a locality, a district, a postcode area and a street.

## Try it

With the demo server running, the map opens over the US; go to Berlin with
`http://127.0.0.1:8890/#/map?lat=52.5163&lon=13.39&z=15&layers=hospital,pharmacy,fire,police,pump`.

| Search | Result |
|---|---|
| `Unter den Linden 77, 10117 Berlin` | Unter den Linden 77, 10117 Berlin-Mitte |
| `Oranienstraße 25 Kreuzberg` | Oranienstraße 25, 10999 Berlin-Kreuzberg |
| `Müllerstr. 12a` | every Müllerstraße 12A in Berlin |
| `Straße des 17. Juni 135` | that house: the 17 stays part of the street name |
| `Unter den Linden 99999` | no house is guessed; the street itself is offered |
| `Kreuzberg`, `10117 Berlin`, `Oranienstraße` | the locality, the postcode area, the street |
| `Route 66` | still a place search, as before |

`/api/map/near?lat=52.5163&lon=13.3777&cls=hospital,pharmacy,fire_station,police,water_well` lists the nearest help
around the Brandenburg Gate.

## Changes outside the builder

- `tools/build_map.py`: `--source`, `--as-of`, `--bounds` and `--extra-poi`, so the same builder serves another region.
  Without them it writes exactly what it wrote before.
- `engine/address_search.py` and `server.py` (`places`): German order, `Straße Hausnummer, PLZ Ort`, for indexes whose
  `meta` says `norm = de-1`. Each index is searched only with its own spelling rule, so the published US indexes
  and every US query behave as before; `app/tests/test_address_search.py` keeps its US tests unchanged and adds German
  ones, including US queries with a Berlin index installed. A German-looking query that finds no house falls back to
  the place search, so `Route 66` or `Pier 39` still find places.
- `web/map.js` and `server.py` (`HELP`): a `water_well` class and a "Hand pumps & water wells (untested water)" layer
  in the Water group. Berlin has some 2,000 street hand pumps meant for emergencies; the official list is restricted,
  and OpenStreetMap has 2,080 of them.

## Limits

- **The app's words are still American.** The map page says it shows what was mapped by 25 Oct 2026 (a fixed line in
  `web/map.js`; this map's date is in its `meta`), the search box asks for a ZIP, a button says "Whole United States",
  and the map opens over the US. The source list in `map_info` names US datasets. These belong to the shared region
  work, not to one region's builder.
- **Not in this map:** terrain, the water and dam layers, crops and the resource atlas (US datasets); Berlin's
  disaster-relief points (Katastrophenschutz-Leuchttürme), which are published only as a map and a PDF without a licence.
- **Pumps are not checked.** OpenStreetMap does not say whether a pump works, and the water is untested.
- **The iPad app** marks place results as on the map only inside Southern California or in a pack (`onMap` in
  `server.py`); the web app does not use that flag.

### German addresses

- Supported: `Straße 12`, `Straße 12a` or `12 a`, `Str.`/`Strasse`/`Straße`, umlauts typed or spelled out
  (`Muellerstrasse`), an optional postcode, an optional `Berlin` or locality, and numbers inside street names.
- Not supported: the number first (`77 Unter den Linden` is read as a US address), ranges (`12-14` finds 14), a
  street name split in two (`Oranien Str. 25`), and building parts beyond one letter.
- Eleven houses in Schmöckwitz and Rahnsdorf officially carry a Brandenburg postcode (155xx); they are kept as recorded.
- The source has no postal place names beyond Berlin, so results read `10117 Berlin-Mitte` (postcode, city, locality).
- A locality in the query (`Kreuzberg`) is matched after the index returns its first 500 houses with that street and
  number. One city never comes near that; a national index with very common street names would need the locality
  filtered inside SQLite instead.
