# Azores (PT-20): a working offline map

The second Portugal region built on the plan in [REGIONS-PT.md](REGIONS-PT.md): streets, named places, help
points and street addresses for the whole autonomous region, built from redistributable sources by one command,
kept in its own folder. It follows the file formats in [MAPS.md](MAPS.md). The region is one install, `PT-20`:
the ISO 3166-2:PT code and the NUTS II code coincide, and one Azores download is easier to find than two (#31).
The proposal had split the islands into `pt-20w`/`pt-20e` only because that is how the INE address register
groups them (AC25 Corvo and Flores, AC26 the rest); the split stays documented in REGIONS-PT.md and both groups
ride in this one map and index (the case is #31's call, and its answer is recorded there).

This is a builder and a testable map set, not an installer: the shared region format and the regional
address-index IDs are still being designed (#31), and the shared map builder work is #25 — nothing here touches
`engine/`, `server.py`, `web/`, `packaging/`, the release manifest, the setup flow or the search runtime, because
`tools/build_map.py` runs unchanged. The sidecar carries its normalisation rule in `meta.norm = pt-1`; the
address fixtures at the end are what a future runtime path can be checked against.

## Build it

```sh
python3 tools/build_region_pt_20.py fetch    # downloads the sources, about 1.03 GB, into derived/regions/PT-20/source/
python3 tools/build_region_pt_20.py build    # stages derived/regions/PT-20/data.new/, checks it, then swaps it into data/
python3 tools/build_region_pt_20.py check    # validates data/; exits non-zero on any failure
python3 tools/build_region_pt_20.py demo     # adds an empty library beside it for trying the map alone
python3 server.py --data derived/regions/PT-20/demo --no-index
```

Python 3.9 or newer and its standard library; no GDAL, no other packages. `fetch` is the only step that uses
the network, and it keeps files whose SHA-256 matches the previous fetch. Everything is written under
`derived/regions/PT-20/`, so no existing map set changes. A build never rewrites a good output: it stages into
`data.new/`, checks the staging, and only then replaces `data/` — a rebuild that fails or stops leaves the last
good `data/` (with its `build.json`) as it was, and one that stops between the two final renames is repaired by
the next build. An output kept from the earlier builder carries its report beside `data/` rather than inside it;
`check` reads that legacy report for the live map until a successful build replaces it — a staging folder without
its own report is reported as missing, never validated against another output's report.
`data/build.json` records every source (URL, dated file name, data date, licence, size,
SHA-256) and every output (size, SHA-256).

## Sources

| What | Source | Licence | Attribution |
|---|---|---|---|
| Streets, water, land use, buildings, named places and points | OpenStreetMap via Geofabrik, `portugal-261121-free.gpkg.zip` (data of 21 November 2026; the dated name is recorded). No Azores subregion exists, so the country extract is cut to the region box at build time | ODbL 1.0 | © OpenStreetMap contributors (already on the map) |
| Street addresses (house, street, postcode, locality) | INE address register, distributed by OpenAddresses as `pt_addresses.csv.zip` (5,911,139 rows; the 110,897 inside the region box are the ones kept — AC26, 108,523, plus AC25 Corvo and Flores, 2,374) | CC BY 4.0 | Instituto Nacional de Estatística, I.P. |
| Region box, municípios and freguesias | CAOP 2025, Região Autónoma dos Açores, `CAOP_RAA_2025-gpkg.zip` (served 2 February 2026; one geopackage per island group — the western group on UTM zone 25N, the central+eastern group on zone 26N) | CC BY 4.0 | Direção-Geral do Território |

The CAOP register is a high-value dataset under Regulation (EU) 2023/138 of the Open Data Directive, and DGT's
open-data page states the licence: CC BY 4.0, with naming the Direção-Geral do Território as the only duty.
The two island-group geopackages carry different projections, and the builder reads each file's central
meridian from its own WKT rather than assuming it: zone 25N for Corvo and Flores, zone 26N for the rest.
The vertex conversion is the same series `tools/build_region_pt_30.py` validated against pyproj on UTM 28N.

## The region box

The box is the exact WGS84 extent of the official CAOP 2025 NUTS II polygons — the union of both island-group
geopackages' extents, every vertex converted and rounded outward to 6 dp — plus the 0.15° margin and the outward
rounding REGIONS-PT.md uses:

| Edge | Official extent (raw) | Published box (with margin) | GISCO raw (REGIONS-PT.md) |
|---|---|---|---|
| West | −31.268816 | −31.42 | −31.2679 |
| South | 36.927630 | 36.77 | 36.9305 |
| East | −25.013179 | −24.86 | −25.0142 |
| North | 39.726185 | 39.88 | 39.7262 |

All four edges agree with GISCO within 0.0029° — the western island group's west edge and the central+eastern
group's east edge match to under 0.001°, and the south edge moves 0.0029° below GISCO: the detailed polygon
reaches past the register's southernmost row, the Farol de Gonçalo Velho point on Santa Maria at 36.929549° N
that the #297 cross-checks located. That row carries no house number, so it stays out of the address index; its
parish's indexed doors (SANTO ESPÍRITO, postcode 9580-238) are in. Every one of the 110,897 INE address rows
sits inside the official box, and the count measured in REGIONS-PT.md reproduces exactly.
The build updates the region rows of [regions-pt-proposed.json](regions-pt-proposed.json) to the CAOP figures.

## What the build holds

Built on 25 November 2026 from the sources above. A full `fetch`, `build`, `check` takes about 12 minutes, most
of it downloading; the build itself runs in about 40 seconds, most of that reading the 1.7 GB country extract to
cut it.

| File | Size | SHA-256 (this build) | Holds |
|---|---|---|---|
| `derived/geo/national.sqlite` | 54.1 MB | `d6cf5f39…becc` | 39,827 road features plus water, land, rail, buildings and places from OpenStreetMap, cut to the region box; 2,377 help and supply points across 36 classes |
| `derived/geo/map.sqlite` | 0.03 MB | `b6ba78e8…27b0` | empty map tables with the source and bounds metadata, as in a US state map |
| `derived/geo/places.sqlite` | 1.7 MB | `aee658ed…c706` | 19 municípios and 156 freguesias from the CAOP (both island-group geopackages), 27 postcode areas (the CP4 prefixes) and 9,075 street names from the addresses, 518 named OpenStreetMap places and 1,291 named points |
| `derived/geo/addresses/PT-20.sqlite` | 12.6 MB | `aa1a479b…76f3` | 92,027 indexed addresses, `meta.norm = pt-1` |
| `map-set.json` | 189 B | `a56b0652…fef7` | the file list and sizes, as every map set carries |

Full checksums are in `data/build.json`, which also records every source (URL, dated file name, data date, licence,
size, SHA-256).

Every place in the place finder answers through the app in `--data` mode: "Ponta Delgada" returns the CAOP
município and the OpenStreetMap city; "Corvo" the município and the island's town; "9500" the postcode area;
"Almagreira" (Santa Maria) and "Lajedo" (Flores) the freguesias of both CAOP geopackages.

## The pt-1 rule

Portuguese street names in the INE register are uppercase with an abbreviated leading type (`AV INF D HENRIQUE`,
`R DR ARMAS DA SILVEIRA`, `ESTR REGIONAL`), and many carry accents. `pt-1` folds the accents, lowercases,
collapses spaces, expands the leading street type (`R`→`rua`, `AV`→`avenida`, `ESTR`→`estrada`, `TV`→`travessa`,
`BC`→`beco`, `LG`→`largo`, and the rest of the ~30 types the Azores rows carry) and the name abbreviations in any
position (`S`→`sao`, `STA`→`santa`, `STO`→`santo`, `D`/`DA`/`DO`→`de`, `DR`→`doutor`, `CMDT`→`comandante`).
`AV INF D HENRIQUE` shares one key with `Avenida Infante D. Henrique`-style spellings (the `INF` abbreviation
stays as written), and `1 BECO DO CALHAU DA AREIA` stores as `1 beco de calhau de areia` — the leading digit
belongs to the street name, and the particles `DO`/`DA` expand to `de`. Separated accents compose first (NFC),
so a Mac or iOS paste folds the same way, as `de-1` does. The house label keeps the register's spelling: a plain
numeral carrying a non-zero digit loses its leading zero (`007` becomes `7`), while composite labels (`0E`,
`2A`, `38 40`) and an all-zero label (`000`) stay as written, so what a door shows is what a query finds. The
rule lives in the builder and travels to the runtime with the index; nothing in the US search path changes.

The expansions do real matching work across spellings the register itself doubles: `R PROF ANTÓNIO JOSÉ DE MELO`
and `R PROF ANTONIO JOSE DE MELO` (Ribeirinha, Angra do Heroísmo) share one key, and `TV STO ANTONIO` meets
`TV Santo António` in the same way.

## What the build lacks

- **Help points come from OpenStreetMap only.** Berlin's build replaced four kinds with an official register;
  Portugal has no equivalent national register with terms the pilot could confirm, so hospitals, pharmacies,
  police and fire stations are OSM points here and the map's `help_points` meta says so.
- **The base map.** `national.sqlite` covers the US only; the Azores draw from the detailed map once you zoom in
  past the base map, as with every regional build so far (#31, Berlin, FR-BN).
- **Address search through the app.** The sidecar opens with `--data` today; installing it from Setup and
  searching it needs the shared regional address-index work tracked in #31. The fixtures below are the check.
- **Terrain, crops and the water inventory.** The US sources do not apply; Portugal replacements are listed in
  REGIONS-PT.md ("What was checked, and what was not") and stay out of this first build.

## Data quirks, measured

These are properties of the INE register worth knowing before using the index:

- **18,870 of the 110,897 rows have no usable house number** (17.0%, against Madeira's 32.3%): doors registered
  without one or with a word where the number goes. They stay out of the address index and are counted; their
  streets still appear in the place finder, which is the way to find them today.
- **Street names start with a digit, and the digit is the name**: `1 BECO DO CALHAU DA AREIA` and
  `2 BECO DO CALHAU DA AREIA` are two different streets in Lagoa whose keys differ only in that digit. Both are
  kept as written, and the fixtures test that a query for one never answers with the other's houses.
- **The same spelling rule doubles the register's own spellings.** Ribeirinha's `R PROF ANTÓNIO JOSÉ DE MELO`
  and `R PROF ANTONIO JOSE DE MELO` are two rows of one street; the accented spelling carries composed accents.
  One norm key holds both, and the fixtures check each query finds its own house.
- **Locality names carry a municipality or island suffix**: `RIBEIRINHA AGH` (Angra do Heroísmo),
  `LAGOA (SÃO MIGUEL)`, `ALMAGREIRA VPT` (Vila do Porto). The suffix travels in the city field and the detail
  line, kept as written.
- **House labels keep composite forms**: `2A` (R BARCELOS, which also carries a plain 2 beside it), `32 A`,
  `74B`, `38 40`. Both are kept verbatim; the future search rule reads the label exactly.
- **Postcodes are stored without the hyphen** (`9500-150` becomes `9500150`) in the index; every Azores postcode
  starts 95–99 (the check pins 9500–9980, Corvo's 9980 the highest). The place finder's postcode areas are the
  CP4 prefixes people search (27 of them).
- **No railways**: the cut holds zero railway rows, as on Madeira — the archipelago has none in OpenStreetMap.

## Offline search check

`check` runs without the network and exits non-zero on any failure: SHA-256 of every output as built, SQLite
integrity, road and help-point counts, every help point inside the box plus the 0.15° margin, the address
arithmetic (92,027 indexed + 18,870 without a number = the 110,897 REGIONS-PT.md measured), every address
inside the official box with a 9500–9980 postcode, the pt-1 keys against the rule on a 500-row sample, the
house labels against the register's forms (nothing reduced to a fragment, no plain numeral still padded), and
the place finder answering for three municípios, two freguesias — one from each CAOP geopackage — and a postcode.
The place finder was also exercised through the running server in `--data` mode ("Ponta Delgada", "Corvo",
"9500", "Almagreira", "Lajedo").

Address fixtures for the future runtime path — each is a register row of the built index, chosen to span both
INE island groups: Corvo and Flores in the western group (AC25), and São Miguel, Terceira and Santa Maria — the
eastern island of the Farol de Gonçalo Velho row — in the central+eastern group (AC26). The same expectations
live as `app/tests/fixtures/pt_20_queries.json` with the contract tests in `app/tests/test_build_region_pt_20.py`,
in the `de_be_queries.json` form (#433): twelve verbatim rows of this index, the queries with their lookups, and
the rule that derives every expected answer from the rows, so `FixtureContractTests` fails if a row, a lookup
or an expectation stops following from what the file states — and a coverage test holds the two groups in:

| Query | Should find | Why it also tests the rule |
|---|---|---|
| `LG VIGIA 61` (or `Largo Vigia 61`) | `LG VIGIA 61` | the only indexed door on Corvo (AC25); `LG`→`largo` |
| `R DR ARMAS DA SILVEIRA 5` | `R DR ARMAS DA SILVEIRA 5` | `DR`→`doutor`, `DA`→`de` in the key |
| `AV INF D HENRIQUE 1` and `… 2` | the Ponta Delgada and the Lagoa houses | one norm key in two islands' cities; the city suffix tells them apart |
| `1 BECO DO CALHAU DA AREIA 5` | `1 BECO DO CALHAU DA AREIA 5` | the leading 1 is the street's; `DO`/`DA`→`de` |
| `2 BECO DO CALHAU DA AREIA 5` | nothing | the sister street holds no 5 — exact match only |
| `R PROF ANTÓNIO JOSÉ DE MELO 5` | `R PROF ANTONIO JOSE DE MELO 5` | the accented query reaches the unaccented row, same key |
| `R BARCELOS 2A` / `R Barcelos 2` | each its own house | the composite label and the plain numeral never answer for each other |
