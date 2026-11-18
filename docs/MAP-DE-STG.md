# Stuttgart (DE-STG): how this map set is built

`tools/build_region_de_stg.py` builds one city's offline map set from OpenStreetMap: streets, water, land use,
buildings, named places, help points and street addresses, all cut to the Stuttgart city boundary. The app reads the
same files it reads for a US state map (`docs/MAPS.md`), so nothing in the engine or `web/` needs to change for the
map itself. Address search is the one piece that did need engine support: German addresses are written street first
with the house number after the street, so the index carries a `de-1` normalization scheme that
`engine/address_search.py` dispatches to.

## Commands

```bash
python3 tools/build_region_de_stg.py fetch    # ~654 MB Baden-Württemberg extract, city boundary, extract, export
python3 tools/build_region_de_stg.py build    # writes derived/regions/DE-STG/data/
python3 tools/build_region_de_stg.py check    # integrity, counts, sample address and place lookups
python3 tools/build_region_de_stg.py demo     # prints the server command below
python3 server.py --data derived/regions/DE-STG/demo --no-index
```

`fetch` needs `osmium` (`brew install osmium-tool` on macOS, `apt install osmium-tool` on Ubuntu) and the network.
`build`, `check` and `demo` are offline and use the Python standard library only.

## Sources

| What | Source | Licence |
|---|---|---|
| Streets, water, land use, buildings, places, help points, addresses | OpenStreetMap via Geofabrik, `baden-wuerttemberg-latest.osm.pbf` | ODbL 1.0, © OpenStreetMap contributors |
| City boundary (relation 62375) | OpenStreetMap through Nominatim, `polygon_geojson=1` | ODbL 1.0, © OpenStreetMap contributors |

Everything in the output derives from OpenStreetMap. `build.json` records the source URLs, the file sizes and the
SHA-256 of each download and output, and the data date of the extract.

## What the data folder holds

| File | Contents |
|---|---|
| `derived/geo/national.sqlite` | `feat` and `feat_idx` (roads, water, wetland, land use, buildings, railways, waterways, named places), `poi` (help points), `meta` (`source`, `data_as_of`, `bounds`, `region`, `help_points`) |
| `derived/geo/map.sqlite` | Empty schema, as for Istanbul; the app opens it for compatibility |
| `derived/geo/places.sqlite` | Place finder rows: the city, Stadtbezirke seen in addresses, streets, postcodes and named points of interest, with the FTS index |
| `derived/geo/addresses/DE-STG.sqlite` | Street addresses with `meta.norm = 'de-1'` |
| `map-set.json` | Names and sizes of the three map files above |

## What one build holds (18 November 2026)

| | |
|---|---|
| Extract data date | 2026-11-17 21:24 UTC (`osmosis_replication_timestamp`) |
| Features | 204,905 (69,596 road ways, 122,901 building outlines, water, land use, railways, named places) |
| Help points | 3,808 (27 hospitals, 109 pharmacies, 67 fire stations, 48 police, 21 clinics, 87 drinking-water taps) |
| Addresses | 85,593, all with a five-digit postcode where one is mapped |
| Places | 4,414 streets, 39 postcodes, 55 Stadtbezirke, 260 OSM place names |
| Data folder | 44 MB |

## Why the code and not DE-BW

ISO 3166-2:DE stops at the 16 states, so a city needs its own short code. `DE-STG` does not collide with any US state
code (which are the two-letter keys in `engine/address_search.py`) and reads as the city rather than the state. A
state-wide Baden-Württemberg set would be `DE-BW` under the proposal in `docs/REGIONS-DE.md`; this builder cuts the
same extract to the city boundary instead, which keeps the output small enough to build on a laptop.

## German address matching (`de-1`)

- `normalize_de()` expands `ä ö ü ß` to `ae oe ue ss`, strips other accents, and folds street words:
  `straße`/`strasse`/`str.` → `str`, `platz` → `pl`, `sankt` → `st`.
- The query is read street first: everything before the house number is the street, the first number that is not a
  five-digit postcode is the house number, a detached letter (`12 a`) is joined to it, and the second half of a range
  (`5-7`) is dropped: the first endpoint is the address.
- A leading postcode (`70173 Stuttgart`) stays a place query, and a query whose street or city does not match returns
  nothing rather than a nearby house.
- `engine/address_search.py` tries the US scheme first for number-first queries, then `de-1` when such an index is
  installed, then `tr-1`. A German query with both Istanbul and Stuttgart installed therefore still resolves to the
  German index, and a Turkish query falls through to the Turkish one.

## Limits

- OpenStreetMap only. There is no elevation (contours and 3D are absent), no crop layer, no dam inventory and no
  federal help-point register: Germany has no open nation-wide equivalents of USGS 3DEP, the USDA Cropland Data Layer
  or the National Inventory of Dams (see `docs/REGIONS-DE.md`).
- Addresses are the ones mapped in OpenStreetMap; a house with no `addr:*` tags cannot be found. `check` reports the
  count.
- The extract strategy is `complete_ways`, so streets and buildings that cross the city line appear whole; the map
  shows a little of the neighbouring municipalities at the edge, which is the same behaviour as a US state map's
  0.15° margin.
- Setup's map picker still lists US states only (`packaging/state_maps.py`, `NAMES`). This set is opened with
  `--data` or the library server until the region-aware picker (#146) lands.
