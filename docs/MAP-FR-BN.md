# Basse-Normandie (FR-BN): the trial build behind the France proposal

A map set for three French départements (Calvados, Manche, Orne) with all seven layers and street addresses, built
from redistributable sources by one command, kept in its own folder, and searchable offline. It is the trial build
whose figures [REGIONS-FR.md](REGIONS-FR.md) quotes, made repeatable. The file formats are those of [MAPS.md](MAPS.md).

`FR-BN` is a trial area, not one of the 18 regions that document proposes: the three départements are the former region
of Basse-Normandie, three of the five départements of today's Normandie. The map set and its address index are named
`FR-BN`, in the regional id shape discussed in #31. The setup manifest and the upgrade carry-over still accept
two-letter address-index ids only (`engine/setup/manifest.py`, `engine/setup/install.py`), so today this map set is
opened with `--data`, as below, not installed through Setup.

This is a builder and a testable map set, not an installer: nothing here touches `packaging/`, the release manifest or
the setup flow. A US map behaves as before; see "What changes in the app".

## Build it

```sh
python3 tools/build_region_fr_bn.py fetch    # downloads the sources, about 2.4 GB, into derived/regions/FR-BN/source/
python3 tools/build_region_fr_bn.py build    # unpacks them (about 12 GB) and writes derived/regions/FR-BN/data/
python3 tools/build_region_fr_bn.py check    # validates it; exits non-zero on any failure
python3 tools/build_region_fr_bn.py demo     # adds an empty library beside it for trying the map alone
python3 server.py --data derived/regions/FR-BN/demo --no-index
```

Python 3.11, with numpy, pyosmium and tifffile as the US map tools need, and either `py7zr` or a 7z program (`7zz`,
`7z`, `7za`) to unpack the IGN archives. None of these ships with the app. `fetch` is the only step that uses the
network. Everything is written under `derived/regions/FR-BN/`, so no existing map set changes. `build.json` there
records every source (URL, licence, size, SHA-256, the server's date for the file) and every output (size, SHA-256).

The IGN archives are dated editions: `fetch` and `build` refuse one whose SHA-256 is not the one written in the tool.
The Geofabrik, BAN and ROE files are the publishers' latest, so a later build holds newer data and slightly different
counts. `check` allows for that: counts have floors, and an address must stay within about 300 m under the same
name, compared without accents or case.

## Sources

| What | Source | Licence | Attribution |
|---|---|---|---|
| Streets, land use, railways, named places, help points | OpenStreetMap via Geofabrik, `basse-normandie-latest-free.gpkg.zip` | ODbL 1.0 | © OpenStreetMap contributors |
| Coastline and sea | OpenStreetMap via Geofabrik, `basse-normandie-latest.osm.pbf` and `guernsey-jersey-latest.osm.pbf` | ODbL 1.0 | © OpenStreetMap contributors |
| Street addresses | Base Adresse Nationale, `adresses-14`, `-50`, `-61.csv.gz` | Licence Ouverte 2.0 | Base Adresse Nationale |
| Buildings and heights, place names, lakes, ponds, springs, rivers | IGN BD TOPO 3.5, edition 2026-09-15, one GeoPackage per département | Licence Ouverte 2.0 | IGN |
| Elevation | IGN BD ALTI 25 m, one archive per département | Licence Ouverte 2.0 | IGN |
| Orchards and other perennial crops | IGN and ASP, Registre parcellaire graphique 2025, Normandie | Licence Ouverte 2.0 | IGN, ASP |
| Dams and weirs | Sandre ROE, WFS layer `ObstEcoul_FXX`, filtered by département | Licence Ouverte 2.0 | Sandre, OFB |

Each layer file names its source and licence in its own `meta` table (`check` verifies it), and the map's corner credits
are read from there. The Channel Islands' coastline is read so that the sea west of the Cotentin closes; the islands are
drawn as bare land, with no streets.

## What the build holds

Built on 22 November 2026 from OpenStreetMap data of 16 November 2026 and the BAN and ROE as served on 17 November.
With the sources fetched and unpacked, `build` took 86 seconds and `check` about one second on a laptop.

| File | Size | Holds |
|---|---|---|
| `derived/geo/national.sqlite` | 129.6 MB | 421,501 road features plus land use, water areas, railways, places and the sea; 13,916 help and supply points, among them 73 hospitals, 397 pharmacies and 386 fuel stations |
| `derived/geo/map.sqlite` | 37 KB | empty, as in a US state map |
| `derived/geo/addresses/FR-BN.sqlite` | 132.1 MB | 796,608 addresses, 893,713 rows: an address with a lieu-dit is also found under it |
| `derived/geo/buildings.sqlite` | 58.0 MB | 1,539,916 outlines; a height from the BD TOPO for 1,507,939, from a storey count for 3,298, from OpenStreetMap for 172, none for 28,507 |
| `derived/geo/terrain.sqlite` | 51.0 MB | 1,002 elevation tiles, zoom 4 to 12 |
| `derived/geo/water.sqlite` | 30.4 MB | 158 dams, 218 reservoirs, 272 lakes, 1,391 ponds, 1,283 springs, and the river lines |
| `derived/geo/places.sqlite` | 13.3 MB | 86,129 places: 1,352 communes with their population, hamlets, named sites, rivers, and 208 postcodes |
| `derived/geo/crops.sqlite` | 1.8 MB | 1,918 blocks of orchards and other perennial crops |
| `map-set.json` | 421 B | name `FR-BN` and the sizes of the map files; the address index is a sidecar beside them, as in the other regional builds, and is not listed |

416.3 MB in all. Full checksums are in `build.json`. They identify one build: the files record their build time, so
two builds of the same sources differ in those bytes, not in content.

The BD TOPO gives one postcode per commune, and the parent's for a delegated commune: Tourlaville, in
Cherbourg-en-Cotentin, shows 50100 there, where the post uses 50110. So each postcode of the address index is a place
of its own, set at the middle of its addresses and naming the communes it serves, the way a US ZIP code is a place.

## What changes in the app

Each change is switched on by the map files themselves, so a US map set never takes these paths.

- **Address search** (`engine/address_search.py`). An index whose `meta` says `norm = fr-1` is read with French
  rules: accents are folded (`Église` finds `eglise`), street words have their short forms (`r`, `bd`, `pl`, `st`,
  `gal`), `bis` and `ter` belong to the number, the postcode comes before the commune, and a delegated commune is found
  under both its names. An index named after a US state, and the legacy `addresses.sqlite`, are never opened for that
  check and are read as before. One thing changes with no French index installed: a comma after the number, then a
  French street word (`12, rue Haute`), now counts as an address query. A few of those words open a US street too
  (`1200, R Street`): such a query finds no house and goes on to the place finder, where it went before.
- **Postcode and commune** (`server.py`). `14000 Caen` starts with a number, so it was read as house 14000 and found
  nothing. With a region installed, five digits and words that match no address go on to the place finder.
- **Region display** (`server.py`, `web/map.js`, `web/terrain3d.js`). When `national.sqlite`'s `meta` names a `region`
  (`tools/build_map.py --region`), the map shows that region's own date, credits and bounds, distances and contours in
  metres, hectares for areas, springs from `water.sqlite`, and French water words in the place finder. All of it goes
  through one `metric()` function on each side, so a shared metric setting can replace it.

`tools/build_map.py` and `tools/build_coast.py` gain options; their defaults are the Southern California values they
had. One default did change: `build_map.py` now also reads fuel stations from Geofabrik's `traffic` tables, where
Geofabrik files them, so a rebuilt Southern California map gains those points.

## Checks

`check` reads only the built files. It verifies: every file's size and SHA-256 against `build.json`; SQLite
`quick_check` on each database; that `derived/geo` holds nothing but map set files; the region name and bounds in
`national.sqlite`; `norm = fr-1` and `region = FR-BN` in the address index, and that `map-set.json`, named `FR-BN`,
leaves it out; a floor for each layer's count; that every help point is inside the bounds; that each layer names its
source and licence; that no built file holds a path of the computer that built it; and these lookups:

- eight addresses of public buildings as a person would type them, each within about 300 m of where the trial build
  found it and under the same name: with and without postcode, short forms (`35 r st jean caen`, `5 pl gal de gaulle st
  lo`), a comma after the number, a delegated commune by either name (`10 place Napoléon 50100 Cherbourg-en-Cotentin`);
- three that must find nothing: a house number that does not exist, a street asked for in the wrong town, and a US
  address;
- five postcodes through the place finder's own statement, two of them a delegated commune's own (`50110` names
  Tourlaville, `50460` Querqueville), a postcode with its commune as on an envelope (`50100 Cherbourg`), and three place
  names.

`app/tests/test_address_search_fr.py` holds 15 tests on a small index it builds itself. Four of them run US text and
queries through the engine as it was before this change (read from git, skipped without history) and through the
current one, with and without a French index installed, and require the same answers and the same route.

## Limits

- **The sea stops at the edge of the data to the east and south-west.** The coast of Haute-Normandie and Bretagne is in
  other extracts. A straight edge shows east of longitude 0 and south of 48.75° N. Whole regions, as REGIONS-FR.md
  proposes, need each neighbour's coastline or a national coastline file.
- **3D view**: the terrain drops like a cliff at the edge of the elevation data.
- **Rivers**: BD TOPO's lines replace OpenStreetMap's, to avoid drawing each river twice; OpenStreetMap lines with no
  BD TOPO twin are lost.
- **Dams**: the ROE gives a drop height for few of them and no stored volume, unlike the US inventory.
- **Help points**: a place mapped in OpenStreetMap as both a point and an outline is counted twice.
- **Crops**: only what farmers declared as orchards, vines or other perennial crops; a grazed orchard declared as
  grassland is absent. The crop names shown were written for this trial and not checked against the RPG's own code
  list.
- **Addresses**: rows whose repetition index holds a flat number instead of `bis` or `ter` are left out (152 in this
  build).
- **Postcode search** also matches a commune's INSEE code, which sits in the same text: `14123` finds Ifs, whose
  postcode it is, and Cairon, whose INSEE code it is. The postcode itself comes first.
- **Credits**: the region's line of credits is longer than the US one and runs under the "places in view" label on a
  narrow map.
- **The app's words** are still American in places: "ZIP" and "state" in setup, the map opening over the US when no
  pack names the area.
- **Names and codes** follow the shape discussed in #31 and used by the Berlin and Istanbul builds: `FR-BN` for the
  region (a trial area, not an ISO 3166-2 code), `norm = fr-1` for the index's rule. Both are one line here if the
  shared contract settles otherwise.
- Not tried: the installed app (only `server.py` from source), Windows, and `packaging/scan_pack.py`, which needs a
  sample pack.
