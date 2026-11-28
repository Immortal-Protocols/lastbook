# Detailed maps for Brazil: a proposal

This is a proposal for discussion, not a decision. It answers, for Brazil, the questions [MAPS.md](MAPS.md) asks before
coverage can go beyond the United States: which open source replaces each federal list, under what licence, what a
"state" is there, and how addresses are written. It follows the shape of [REGIONS-MX.md](REGIONS-MX.md) and
[REGIONS-AR.md](REGIONS-AR.md) and is meant to feed the same design discussion (issues #23, #25, #31 and #54). The
machine-readable version is [regions-br-proposed.json](regions-br-proposed.json), and a Portuguese translation is
[REGIONS-BR.pt.md](REGIONS-BR.pt.md).

Nothing here changes the app, the engine or a build. No code reads the JSON, and nothing here ships: builds package
`web/` and `content/` only.

**How things were checked.** Research was done on 20 November 2026. Each source carries one of three marks:

- **opened**: the dataset or licence page itself was opened and read;
- **search only**: the fact was seen in a search result or a search snippet, but the page itself was not opened;
- **not checked**: the page could not be reached or read, or it was not looked at in this proposal; the row says what
  is missing.

**Second check.** A second contributor checked the proposal again between 18 and 24 November 2026 (follow-up to #346),
partly with AI research agents reading publisher pages, files and APIs. Facts added by that pass carry the mark
**second check**, with **measured** where a file was parsed, a query was run or a count was made. Sentences that a new
fact supersedes were rewritten; everything else is as merged in #346. São Paulo state was worked through in the most
detail, so several counts below are for São Paulo only.

The state boxes were computed from IBGE's own state polygons. The second check recomputed them from IBGE's
full-resolution boundary file, which corrects eight boxes by up to 0.05° (see "Boxes"), and read IBGE's licence for the
boundaries: **CC BY 4.0** (see "Licence notes"; second check).

## Why Brazil is a useful case

Brazil has its own national scheme for emergency numbers (190, 192, 193 and 199, see "Help points"), and seven of its states use
two-letter codes that collide with US codes in this repository. Brazil has no open postal-code
(CEP) area layer that was checked for this proposal. Two things are different from the US and worth deciding once,
because other Portuguese- and Spanish-speaking countries will raise them too:

- **Two-letter codes collide with US codes.** Seven Brazilian codes are also US state codes in `STATE_CODES`
  (`engine/address_search.py`). This is the main reason for hyphenated codes below.
- **No checked CEP-to-state table.** The eight-digit CEP (*Código de Endereçamento Postal*) on an address is what address
  search needs, but no official CEP-to-state table was checked, so addresses cannot be split by state yet.

## What a region is

Brazil has 26 states (*estados*) and the Federal District (*Distrito Federal*, DF). The proposal is one region per
unit, 27 in all, the same level as a US state. DF is a federal unit with its own government, so it is kept as its own
region here; see the note on DF and Goiás below.

### Codes

ISO 3166-2:BR gives each unit the prefix `BR-` and two letters: `BR-SP` São Paulo, `BR-RJ` Rio de Janeiro, `BR-DF`
Distrito Federal, and so on (the 27 codes were read from the Wikipedia article "ISO 3166-2:BR", which lists the names as
in ISO 3166-2 from the ISO 3166/MA; the ISO Online Browsing Platform itself was not opened).

- **Seven two-letter codes collide with US codes.** The two-letter Brazilian codes `AL` (Alagoas), `MA` (Maranhão),
  `MS` (Mato Grosso do Sul), `MT` (Mato Grosso), `PA` (Pará), `PR` (Paraná) and `SC` (Santa Catarina) are also codes in
  `STATE_CODES` (`engine/address_search.py`) for Alabama, Massachusetts, Mississippi, Montana, Pennsylvania, Puerto
  Rico and South Carolina. A bare `PA` already means Pennsylvania in address search. A Brazilian `PA` would be read the
  same way, so the Brazilian codes cannot be used bare.
- **The hyphenated code is needed for the file name too.** `carry_over()` in `engine/setup/install.py` keeps only
  address indexes named `[A-Z]{2}.sqlite` or `.json` (line 335). An index named `BR-SP.sqlite` would be left behind in
  the old library without a message, as REGIONS-MX.md also notes for `MX-AGU`. The change to `carry_over` would be a
  maintainer's decision.

### Boxes

The boxes were computed from IBGE's state polygons (malhas territoriais, state layer, "malha estadual"), read through
IBGE's public malhas API at maximum quality (`qualidade=maxima`) on 20 November 2026 (opened). The API returns one
feature per unit: 27 features, with 1 to 17 polygons each (Pará has 17, and Rio de Janeiro 15). Every vertex of every
polygon was read; the bounding box was then widened by 0.15° and rounded outward to 0.01°, the same margin
`map_sets.state` uses for US states.

As a check, the outer edges match Brazil's known extreme points as recalled from memory (not checked against a published
list in this pass): the northern tip of Roraima (about 5.27° N), the southern tip of Rio Grande do Sul (about 33.75° S),
the eastern tip of Paraíba (about 34.79° W) and the western edge of Acre (about 73.99° W). Those four edges are set by
those states, and the table matches them.

**Recomputed from the full-resolution file (second check, measured).** The API's `qualidade=maxima` outline is a
simplified version of IBGE's boundary: it leaves out small islands and smooths the coast. The second check computed
every box again from IBGE's full-resolution state layer, **Malha Municipal Digital 2022** (`BR_UF_2022.zip`, 13,717,460
bytes, SHA-256 `282ec7f0…1c841bcb`, SIRGAS 2000, from
`geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais/municipio_2022/Brasil/BR/`,
downloaded on 18 and again on 24 November 2026), by the same rule. Every extent from that file equals, to four decimals,
the `regiao-limitrofe` (bounding region) that IBGE's API reports for the unit
(`servicodados.ibge.gov.br/api/v3/malhas/estados/{id}/metadados`, opened for all 27 on 18 November and for the eight
below again on 24 November). The table below holds the recomputed values. The margin box changes for eight units:

| Code | Edge | Merged in #346 | Second check | Edge set by, in the full-resolution file |
|---|---|---|---|---|
| `BR-MA` | south | -10.41 | -10.42 | the main polygon |
| `BR-RN` | north | -4.68 | -4.66 | a separate island polygon (5 vertices) missing from the API outline |
| `BR-PE` | east, north | -32.24, -3.68 | -32.22, -3.65 | a separate Fernando de Noronha polygon (335 vertices) |
| `BR-AL` | south | -10.65 | -10.66 | the main polygon |
| `BR-BA` | south | -18.49 | -18.50 | the main polygon |
| `BR-SP` | south | -25.46 | -25.51 | a separate islet (26 vertices) at -48.04, -25.36, near the Paraná border; the main polygon's edge is -25.3123, also south of the API's -25.3089 |
| `BR-PR` | west | -54.77 | -54.78 | the main polygon |
| `BR-SC` | east | -48.20 | -48.17 | a separate island polygon (83 vertices) |

The other 19 margin boxes are unchanged; their tight edges move by less than 0.003°. São Paulo's change is the largest,
about 5 km.

| Code | IBGE | Name | Box (west, south, east, north) | Box with 0.15° margin |
|---|---|---|---|---|
| `BR-RO` | 11 | Rondônia | -66.8103, -13.6937, -59.7744, -7.9759 | -66.97, -13.85, -59.62, -7.82 |
| `BR-AC` | 12 | Acre | -73.9904, -11.1456, -66.6236, -7.1118 | -74.15, -11.30, -66.47, -6.96 |
| `BR-AM` | 13 | Amazonas | -73.8016, -9.8180, -56.0976, 2.2466 | -73.96, -9.97, -55.94, 2.40 |
| `BR-RR` | 14 | Roraima | -64.8253, -1.5806, -58.8869, 5.2718 | -64.98, -1.74, -58.73, 5.43 |
| `BR-PA` | 15 | Pará | -58.8983, -9.8412, -46.0614, 2.5910 | -59.05, -10.00, -45.91, 2.75 |
| `BR-AP` | 16 | Amapá | -54.8763, -1.2362, -49.8757, 4.5088 | -55.03, -1.39, -49.72, 4.66 |
| `BR-TO` | 17 | Tocantins | -50.7421, -13.4682, -45.6993, -5.1684 | -50.90, -13.62, -45.54, -5.01 |
| `BR-MA` | 21 | Maranhão | -48.7552, -10.2618, -41.7961, -1.0493 | -48.91, -10.42, -41.64, -0.89 |
| `BR-PI` | 22 | Piauí | -46.0282, -10.9288, -40.3705, -2.7498 | -46.18, -11.08, -40.22, -2.59 |
| `BR-CE` | 23 | Ceará | -41.4235, -7.8582, -37.2527, -2.7843 | -41.58, -8.01, -37.10, -2.63 |
| `BR-RN` | 24 | Rio Grande do Norte | -38.5821, -6.9827, -34.9685, -4.8164 | -38.74, -7.14, -34.81, -4.66 |
| `BR-PB` | 25 | Paraíba | -38.7656, -8.3030, -34.7931, -6.0259 | -38.92, -8.46, -34.64, -5.87 |
| `BR-PE` | 26 | Pernambuco | -41.3583, -9.4829, -32.3778, -3.8046 | -41.51, -9.64, -32.22, -3.65 |
| `BR-AL` | 27 | Alagoas | -38.2376, -10.5004, -35.1519, -8.8131 | -38.39, -10.66, -35.00, -8.66 |
| `BR-SE` | 28 | Sergipe | -38.2450, -11.5686, -36.3959, -9.5150 | -38.40, -11.72, -36.24, -9.36 |
| `BR-BA` | 29 | Bahia | -46.5773, -18.3486, -37.3411, -8.5328 | -46.73, -18.50, -37.19, -8.38 |
| `BR-MG` | 31 | Minas Gerais | -51.0461, -22.9228, -39.8568, -14.2332 | -51.20, -23.08, -39.70, -14.08 |
| `BR-ES` | 32 | Espírito Santo | -41.8798, -21.3018, -39.6660, -17.8919 | -42.03, -21.46, -39.51, -17.74 |
| `BR-RJ` | 33 | Rio de Janeiro | -44.8893, -23.3689, -40.9579, -20.7632 | -45.04, -23.52, -40.80, -20.61 |
| `BR-SP` | 35 | São Paulo | -53.1101, -25.3580, -44.1614, -19.7797 | -53.27, -25.51, -44.01, -19.62 |
| `BR-PR` | 41 | Paraná | -54.6202, -26.7171, -48.0235, -22.5163 | -54.78, -26.87, -47.87, -22.36 |
| `BR-SC` | 42 | Santa Catarina | -53.8371, -29.3551, -48.3279, -25.9558 | -53.99, -29.51, -48.17, -25.80 |
| `BR-RS` | 43 | Rio Grande do Sul | -57.6497, -33.7512, -49.6914, -27.0823 | -57.80, -33.91, -49.54, -26.93 |
| `BR-MS` | 50 | Mato Grosso do Sul | -58.1687, -24.0686, -50.9229, -17.1663 | -58.32, -24.22, -50.77, -17.01 |
| `BR-MT` | 51 | Mato Grosso | -61.6334, -18.0416, -50.2248, -7.3490 | -61.79, -18.20, -50.07, -7.19 |
| `BR-GO` | 52 | Goiás | -53.2486, -19.4984, -45.9072, -12.3950 | -53.40, -19.65, -45.75, -12.24 |
| `BR-DF` | 53 | Distrito Federal | -48.2858, -16.0500, -47.3084, -15.5018 | -48.44, -16.20, -47.15, -15.35 |

Notes:

- **DF inside Goiás.** The DF box lies entirely inside the `BR-GO` box, the same case as CABA inside Buenos Aires in
  REGIONS-AR.md. The Brasília metropolitan area crosses the DF and Goiás border, so a person there who installs only one
  of the two maps misses part of their area. Options: keep the two maps separate (simple), or let the `BR-GO` map include
  `BR-DF` (matches how people move in the area, as REGIONS-AR.md suggests for CABA). This proposal does not decide it.
- **Large boxes.** Amazonas, Pará and Mato Grosso are the largest boxes. Their maps will be large, and the
  size of the download has not been estimated for this proposal.
- **Offshore islands.** The IBGE polygons were checked for every unit: any polygon more than 0.5° from the unit's largest
  polygon was listed. Two detached islands are in the polygons, and two offshore islands are not in them at all.
  - **Fernando de Noronha** (`BR-PE`, about 2.4° east of the mainland) is **kept** in the PE box, because it is a
    Pernambuco island with people living on it, and no other map would show it. Its tight edge is -32.38° W, so the PE
    box with margin reaches -32.22° W (second check, full-resolution file; the API outline gave -32.40 and -32.24).
    Without Noronha the box would end at -34.81° W; the cost is about 2.4° of mostly ocean. IBGE lists Fernando de
    Noronha as a *Distrito Estadual* (state district) with its own geocode, beside the 5,569 municipalities and the
    Federal District (IBGE's boundary note, opened; second check).
  - **Trindade and Martim Vaz** (`BR-ES`, about 10° east of the mainland, around 20.5° S) are **left out** of the ES
    box. Keeping them would stretch the ES box from -39.67° W to -28.85° W (the full-resolution file, which also holds
    Martim Vaz; the API outline stops at -29.30°; second check), about 13° wide and mostly ocean, so the
    box would stop being useful for the mainland. Whether they need a map of their own is an open question. No resident
    population was checked for them.
  - **Atol das Rocas** (RN) and **São Pedro e São Paulo** (PE) are **not in the IBGE state polygons**, so no box
    includes them and nothing has to be cut. Whether either should have a map is an open question.
  - The rule used here: an island goes in its state's box only if it is part of the state's IBGE polygon **and** either
    is close to the mainland or has people living on it. Only Noronha passes that test. This is a proposal, not a
    settled rule.
- **Overlapping boxes.** Boxes follow each state's own outline, so neighbouring boxes overlap along borders. The
  overlap is expected and is the same as for the US and Mexico.

## Sources, layer by layer

| Layer (file) | US source today | Proposed for Brazil | Publisher | Licence | Checked |
|---|---|---|---|---|---|
| Terrain (`terrain.sqlite`) | USGS 3DEP | **ANADEM v1.0** (second check): a 30 m bare-earth terrain model of South America, made by removing the vegetation bias from Copernicus GLO-30, on the EGM2008 geoid | IPH-UFRGS with ANA | CC BY 4.0 on OpenTopography's record (doi:10.5069/G9736P4G); the UFRGS page states none | opened (second check); vertical accuracy not read |
| Terrain, alternative | | **TOPODATA** (second check): 1″ (about 30 m) from SRTM, Brazil only, cloud-optimised GeoTIFF. A surface model, like Copernicus | INPE | CC BY 4.0 (the `license` field of INPE's STAC record) | opened (second check) |
| Terrain, fallback | | Copernicus DEM GLO-30, as for the fallback in REGIONS-AR.md and REGIONS-MX.md | ESA / Airbus | Copernicus licence | Copernicus as in REGIONS-AR.md |
| Water (`water.sqlite`) | NHD | OSM waterways and water areas, as for the US. ANA's BHO 6 is not proposed: its licence is only "free access" (see Water) | OSM contributors; ANA | ODbL (read 20 Nov 2026) | ODbL opened; ANA metadata opened, no licence named |
| Dams | NID | **SNISB** (second check), the national dam safety register, "Barragens Cadastradas": points with height, reservoir capacity, use, risk category and potential damage. 28,127 dams nationally, 1,515 in São Paulo, all with coordinates. OSM `waterway=dam` as a fallback | ANA, with data entered by each inspecting agency; OSM contributors | no licence on the item (`licenseInfo` empty); see "Water"; ODbL | opened; counts read from the SNISB FeatureServer on 19 November 2026 (second check, measured) |
| Crops (`crops.sqlite`) | USDA Cropland Data Layer | **MapBiomas Brasil Collection 11.0** (second check), annual land use and land cover 1985 to 2025, 30 m GeoTIFF. Classes include 46 Coffee, 47 Citrus, 48 Other perennial crops, 35 Palm oil, 20 Sugar cane, 39 Soybean, 40 Rice, 41 Other temporary crops and 9 Forest plantation; no separate vineyard or berry class (grapes fall under 48) | MapBiomas | CC BY 4.0 per MapBiomas' user toolkit README and Earth Engine's catalogue entry (Collection 10); a search result for the terms page said CC BY-SA, as REGIONS-PY.md also found | README and Collection 11 legend opened (second check); terms page refused connection, search only |
| Buildings (`buildings.sqlite`) | Microsoft US footprints, OSM heights | Google Open Buildings V3 (Brazil is in its country list; second check); Google Open Buildings 2.5D Temporal for building presence and **height**, 2016 to 2023 (Brazil listed; second check); Microsoft Global ML Building Footprints (1,152 Brazil tiles in its 24 July 2026 link list; second check); OSM to fill gaps | Google; Microsoft; OSM contributors | CC BY 4.0 or ODbL 1.0, at the user's choice (Google); **CDLA Permissive 2.0** (Microsoft, see "Licence notes"); ODbL | opened (second check); coverage not measured |
| Places (`places.sqlite`) | GNIS, Census gazetteers, OSM | IBGE malhas for states, municipalities and localities (the state layer was used for the boxes); IBGE **Localidades do Brasil 2022**, 96,163 named places as points with municipality code, 6,710 in São Paulo (second check); OSM named places | IBGE; OSM contributors | Malhas: **CC BY 4.0** (IBGE's boundary note, see "Licence notes"; second check). Localidades: no licence file in its zip; probably covered as a product derived from the malhas, not confirmed. ODbL | state layer opened; licence opened (second check); Localidades opened and counted (second check, measured) |
| Addresses (`addresses/<code>.sqlite`) | Overture addresses | Overture addresses: 89,887,635 Brazilian rows in the publisher's per-country table. Their source is IBGE's **CNEFE**, the 2022 census address register, which carries a state code on every record (second check, see "Addresses in Overture") | Overture Maps Foundation; IBGE | Overture's attribution page: "IBGE … Available under CC0" (second check); CEP not open | Overture guide opened 20 Nov 2026; attribution page opened (second check); Correios guide opened (second check) |
| Points of interest (`poi` rows) | OSM | OSM tags for drinking water, hospitals, clinics, fire and police stations (counts in "Water" and "Help points and counts"); CNES as a candidate for health establishments, with coordinates (second check) | OSM contributors; Ministério da Saúde (DATASUS) | ODbL (read); CNES dataset cc-by (read) | counted through Overpass, 20 Nov 2026; CNES file parsed (second check, measured) |

## Help points and counts

- **Health establishments: CNES (candidate).** The DATASUS CNES dataset page (dadosabertos.saude.gov.br, opened 20
  November 2026) gives its licence field as `cc-by` ("Creative Commons Atribuição"). That passes the test: commercial use
  and adaptation are allowed with credit. **The file has coordinates** (second check, measured): the full file
  (`cnes_estabelecimentos_csv.zip`, 57 MB holding a 233 MB CSV, `;`-separated, Latin-1, updated daily; the copy read was
  dated 18 November 2026) has `NU_LATITUDE` and `NU_LONGITUDE`. Of 643,594 rows, 584,475 have coordinates; 503,559 are
  active (no `CO_MOTIVO_DESAB`, the deactivation reason). The coordinates are entered by each establishment, so a few
  will be wrong. Type 22 (*consultório isolado*, a single doctor's office, about 312,000 rows) should be left out. A
  separate UBS file writes longitude with a decimal comma and latitude with a decimal point. Counts for São Paulo are
  under "São Paulo in detail".
- **Caveat on CNES.** The same portal's footer says the site's content is CC BY-ND 3.0 (no adaptation). That refers to the
  site's own text, not to the dataset. Maintainers should confirm that the dataset licence governs the data.
- **Fire and police stations.** The state fire and police lists were not checked. The OSM counts below are the only
  national figures in this pass. For São Paulo, the second check searched the state open data portal: no open list of
  the state fire department's stations (Corpo de Bombeiros da Polícia Militar) or of police stations was found; the
  Secretaria da Segurança Pública's datasets there are crime statistics (opened; second check).
- **Shelters.** No open national shelter list was found; OSM `amenity=shelter` is not counted here. In São Paulo,
  `amenity=shelter` marks small roofs, as REGIONS-PY.md found for Paraguay: of 899 counted on a second Overpass server
  whose data was from 1 June 2026, 318 are picnic shelters, 176 lean-tos, 159 have no type, 133 are pavilions, 63
  gazebos, 41 public transport and 9 other kinds. `social_facility=shelter` is mostly homeless shelters (13 of 29).
  Neither should be drawn as an emergency shelter (second check, measured).
- **Ministry of Health plan documents** are described in search results as CC BY-NC-SA (not opened). That licence is not
  used for any dataset here.

| Unit | `amenity=drinking_water` | `man_made=water_tap` | `natural=spring` | `man_made=water_well` | `amenity=hospital` | `amenity=clinic` | `amenity=fire_station` | `amenity=police` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `BR-AC` | 1 | 0 | 19 | 1 | 26 | 21 | 1 | 21 |
| `BR-AL` | 5 | 0 | 6 | 93 | 111 | 154 | 10 | 82 |
| `BR-AP` | 0 | 0 | 2 | 1 | 38 | 89 | 5 | 46 |
| `BR-AM` | 14 | 1 | 19 | 6 | 131 | 147 | 11 | 77 |
| `BR-BA` | 32 | 12 | 103 | 26 | 656 | 1,163 | 25 | 529 |
| `BR-CE` | 60 | 5 | 15 | 168 | 344 | 680 | 19 | 253 |
| `BR-DF` | 34 | 12 | 21 | 2 | 126 | 190 | 42 | 202 |
| `BR-ES` | 41 | 3 | 15 | 3 | 144 | 432 | 20 | 250 |
| `BR-GO` | 29 | 2 | 111 | 14 | 327 | 312 | 34 | 213 |
| `BR-MA` | 5 | 1 | 4 | 23 | 228 | 178 | 16 | 118 |
| `BR-MT` | 4 | 7 | not counted | 3 | 181 | 270 | 25 | 172 |
| `BR-MS` | 9 | 0 | 174 | 6 | 115 | 87 | 19 | 121 |
| `BR-MG` | 142 | 15 | 1,697 | 54 | 860 | 1,234 | 63 | 656 |
| `BR-PA` | 42 | 0 | 23 | 16 | 270 | 229 | 16 | 141 |
| `BR-PB` | 34 | 14 | 15 | 83 | 213 | 271 | 18 | 107 |
| `BR-PR` | 101 | 37 | 228 | 33 | 510 | 930 | 92 | 454 |
| `BR-PE` | 18 | 6 | 245 | 40 | 431 | 529 | 30 | 209 |
| `BR-PI` | 9 | 0 | 9 | 29 | 228 | 478 | 3 | 106 |
| `BR-RJ` | 71 | 22 | 727 | 54 | 603 | 797 | 118 | 541 |
| `BR-RN` | 33 | 2 | 5 | 55 | 191 | 439 | 8 | 180 |
| `BR-RS` | 88 | 30 | 84 | 38 | 560 | 1,056 | 132 | 583 |
| `BR-RO` | 3 | 0 | 3 | 0 | 52 | 41 | 6 | 71 |
| `BR-RR` | 12 | 0 | 4 | 2 | 23 | 65 | 6 | 55 |
| `BR-SC` | 34 | 3 | 484 | 20 | 252 | 1,240 | 193 | 459 |
| `BR-SP` | 470 | 92 | 2,411 | 136 | 1,370 | 2,663 | 234 | 2,195 |
| `BR-SE` | 7 | 1 | 7 | 4 | 72 | 274 | 10 | 146 |
| `BR-TO` | 7 | 0 | 11 | 0 | 52 | 75 | 2 | 28 |
| **Total (sum of the 27 units)** | **1,305** | **265** | **not counted** | **910** | **8,114** | **14,044** | **1,158** | **8,015** |

The counts are OSM objects as found by Overpass on 20 November 2026, per unit (ISO 3166-2 area); the last row is the sum
of the 27 units. A single country-wide query timed out on the Overpass server, so the country total was not counted
separately. Duplicates and closed features were not removed, so these are upper bounds for a usable map, not checked
totals.

Mato Grosso's `natural=spring` is **not counted**. Overpass gives 53,580 objects. To see where they come from, the IBGE
tight box for BR-MT (W -61.6334, S -18.0416, E -50.2248, N -7.3490) was cut in half at its midpoints, latitude -12.6953
and longitude -55.9291, and each quarter was intersected with the OSM BR-MT area. The quarters hold 31,074 (south-west),
19,825 (south-east), 40 (north-west) and 2,641 (north-east), which sum to 53,580; a whole-state query on 21 November
2026 gave the same total. Reading the object metadata of the two southern quarters, 50,807 springs (31,006 south-west
and 19,801 south-east) are in eight changesets made by one OSM user (`danctc`) on 6 November 2025 (174297625, 174297760,
174297826, 174297902, 174298479, 174298489, 174298500 and 174298643). All eight are tagged `source=SEMA-MT` (the Mato
Grosso environment department) and have no discussion comments. No permission for SEMA-MT data was found: the OSM wiki
Contributors page lists the Minas Gerais environment department but not SEMA-MT, the Import/Catalogue has no entry for
it, and the SEMA-MT website footer says "Todos os Direitos reservados" (all rights reserved). The points may be real
springs, but without a documented licence they should not be counted or shipped, so no number is shown for that column,
and the column total is not counted either.

### São Paulo in detail (second check)

São Paulo was worked through further, as one example of what a state map would hold. OSM counts are from the Overpass
API inside the same `BR-SP` area (nodes, ways and relations; data up to 18 November 2026 21:29 UTC; measured), so they
can differ by a few from the table above. Official counts are for active establishments in São Paulo.

| Kind | OSM tag | OSM, SP | Official source | Official, SP |
|---|---|---:|---|---:|
| General and specialised hospitals | `amenity=hospital` | 1,370 | CNES types 5 and 7 | 785 and 194 |
| Emergency care | `emergency=ambulance_station` | 136 | CNES types 73 (*pronto atendimento*, including UPAs), 20 (*pronto socorro*) and 42 (mobile emergency units, mostly SAMU) | 458, 85 and 1,086 |
| Primary care | `amenity=clinic`, `amenity=doctors` | 2,660 and 541 | CNES types 2 (*centro de saúde / UBS*) and 1 (*posto*) | 5,340 and 267 |
| Pharmacies | `amenity=pharmacy` | 3,403 | CNES type 43 | 4,932 |
| Fuel | `amenity=fuel` | 6,465 | ANP's register of fuel retailers: addresses and CEP, **no coordinates** | 8,389 |
| Schools | `amenity=school` | 9,046 | São Paulo state network (Secretaria da Educação, `ENDERECO_ESCOLAS`), with coordinates, CC BY 4.0 | 5,582 |
| Dams | `waterway=dam` | 305 | SNISB | 1,515 |
| Water towers, reservoirs | `man_made=water_tower`, `water=reservoir` | 3,319 and 5,465 | | |
| Supermarkets | `shop=supermarket` | 4,229 | | |
| Community centres, town halls | `amenity=community_centre`, `amenity=townhall` | 689 and 603 | | |
| Assembly points | `emergency=assembly_point` | 10 | | |

All 116,899 active CNES rows in São Paulo have coordinates, and all but one fall inside the São Paulo box (measured).
SNISB's São Paulo dams are registered by SP Águas, the state water agency that succeeded DAEE (1,256), ANEEL (169),
ANM (58), ANA (30) and CETESB (2) (measured). ANP's fuel register could be placed on the map by matching its addresses
against the address index; OSM's 6,465 can also be used as they are.

São Paulo city's geoportal, **GeoSampa**, has point layers for fire stations (40), civil police (93), military police
(159), the municipal guard (48) and civil defence (34), and polygons for geological risk (1,404) and flood risk (793)
with flood footprints for 5, 25 and 100 years (opened). They are CC BY-SA 4.0 (see "Licence notes"). The state
environment geoportal, **DataGeo**, has the Instituto Geológico's 2014 landslide and flood risk mapping for 41
municipalities and the 19 civil defence regions (polygons), with no licence stated (opened). Risk areas are a new kind
of layer for Lastbook, not a replacement for a US one; whether to show them is for the maintainers. No open list of
public drinking water points was found from the state, the city or the state water company (SABESP).

## Licence notes and attribution

- **gov.br content.** The footer of gov.br pages says all content is published under *Creative Commons
  Atribuição-SemDerivações 3.0 Não Adaptada* (CC BY-ND 3.0 Brazil) (opened, read on 20 November 2026 on the gov.br
  "Sobre o portal" page and on the federal SAMU page). The "no derivatives" part means a page cannot be adapted into a
  library guide, so gov.br pages are not proposed as copy sources. Quoting a single number with its source is a question
  for maintainers, not a decision made here.
- **IBGE malhas: CC BY 4.0** (second check, opened). The technical note "Malha Municipal Digital e Áreas Territoriais –
  Informações Técnicas e Legais" (Notas metodológicas 01/2025, `biblioteca.ibge.gov.br`, liv102169) says: "O IBGE
  disponibiliza a MMD e todos produtos e informações dela derivados sob licença Creative Commons BY 4.0" (IBGE makes the
  municipal boundaries and all products and information derived from them available under CC BY 4.0), and that using
  them means accepting its conditions and releasing IBGE from liability. The note read is the one for the 2024 edition;
  the 2025 zip's README points to the note. The state layer used for the boxes is part of the same product. This settles
  the licence the merged text left open, so the IBGE malhas can be **proposed for a build**, with credit to IBGE.
- **IBGE BC250** (second check, opened). The 1:250,000 base map's 2019 *Termo de Compromisso de Uso* forbids renting or
  selling it ("vedada a locação ou comercialização") without IBGE's written permission and limits use to "apoio a
  projetos de trabalho" (support for work projects). Its 2025 folder has no licence file. Not proposed: Localidades 2022
  and the malhas cover the same need.
- **IBGE CNEFE** (second check). No licence statement from IBGE was found on the CNEFE files. Overture's attribution page
  says "IBGE (Instituto Brasileiro de Geografia e Estatística). Available under CC0. Distributed by AddressForAll.
  Accessed: 2024-10-13" (opened). OpenAddresses marks the same file as attribution required, crediting IBGE (opened).
  The OSM wiki says IBGE has given no clear licence statement (opened). IBGE is a federal public body, and its published
  data fall under the federal open data policy below. The proposal is to use CNEFE, through Overture or directly, and
  credit IBGE, which satisfies CC0 and an attribution licence alike.
- **Federal open data policy** (second check, opened). Decreto 8.777/2016, article 4 as amended by Decreto 9.903/2019,
  says the open data of the federal executive are "de livre utilização pelos Poderes Públicos e pela sociedade" (free to
  use by government and the public); the definition of open data in article 2 asks only that the author or source be
  credited. `dados.gov.br`'s terms (CGINDA Resolution nº 2/2017) allow use "para qualquer finalidade" (for any purpose),
  including profit, copying and distribution, "desde que citada a devida fonte" (provided the source is cited), unless a
  dataset has its own licence, and list CC0, PDDL, CC BY 4.0 and ODbL as the licences agencies should choose from. The
  merged text saw this resolution in search only; it was opened in the second check. Whether the decree's scope covers
  each publisher (federal foundations and agencies such as IBGE and ANA) was not re-read in the decree's article 1.
- **Microsoft Global ML Building Footprints: CDLA Permissive 2.0** since 11 March 2026 (commit `ef94ee3d` in
  `microsoft/GlobalMLBuildingFootprints`; ODbL before that; opened, second check). Overture's attribution page still lists
  it as ODbL.
- **MapBiomas.** CC BY 4.0 per its user toolkit README and Earth Engine's catalogue, with the credit "MapBiomas Project –
  Collection [version] of the Annual Series of Land Use and Land Cover Maps of Brazil, accessed on [date] through the
  link: [link]" (opened, second check). A search result for its terms page said CC BY-SA, and the page refused connection
  (search only). To be confirmed with MapBiomas before a build.
- **ANADEM and TOPODATA: CC BY 4.0** (second check, opened). ANADEM's credit is "Distributed by OpenTopography.
  https://doi.org/10.5069/G9736P4G", with ANA (2025) and Laipelt et al. 2024, *Remote Sensing* 16, 2321.
- **São Paulo state and city** (second check, opened). The state open data portal (`dadosabertos.sp.gov.br`) has 456
  datasets, 338 of them CC BY 4.0 and the rest with no licence; the state schools file is CC BY 4.0. GeoSampa (São Paulo
  city) is **CC BY-SA 4.0** under the city's "Licença para uso de dados do GeoSampa" (process SEI 6066.2020/0003044-4):
  share-alike would bind a pack that holds it, and CC BY-SA 4.0 is not the ODbL, so mixing it into an OSM-based database
  needs a decision. DataGeo (state environment) states no licence on its About and FAQ pages or in a sample record. The
  state geographic institute (IGC) sells its maps and says "Todos os direitos reservados" (all rights reserved). Nothing in
  this proposal depends on GeoSampa, DataGeo or IGC.

## Water: drinking and clean water

This is the first priority for Brazil, so it is set out in full. For each source the question is the same as for the
rest of the map: can the library copy it, and can it be used offline?

**Proposed**

- **Water layer: OpenStreetMap, under the ODbL.** Waterways and water areas, as in the US build. The ODbL 1.0 text was
  read on its licence page on 20 November 2026 (opened): commercial use is allowed, a database built from OSM data is
  shared under the same licence, and the credit is "© OpenStreetMap contributors".
- **Drinking water points: OSM tags.** `amenity=drinking_water` (a public tap or fountain), `man_made=water_tap`,
  `natural=spring` and `man_made=water_well`. A tag does not say the water is safe to drink, so springs and wells get a
  plain "not checked for drinking" label, as REGIONS-ES.md proposes for Spain.
- **Counts per unit** are in "Help points and counts" below (Overpass API, 20 November 2026).

**Not proposed (the licence test fails)**

- **ANA Base Hidrográfica Ottocodificada (BHO 6).** The metadata record (metadados.snirh.gov.br, opened 20 November 2026)
  gives the licence as "O acesso ao dado é livre." ("access to the data is free"). That names no licence, and nothing says
  the data may be adapted or used commercially. Not proposed until ANA names one. Next step: ask ANA, and check the
  dataset page on dadosabertos.ana.gov.br.
  ANA's own open data page (`gov.br/ana/pt-br/acesso-a-informacao/dados-abertos/dados-abertos/`) says its data are
  "disponibilizados livremente … sem restrição de licenças, patentes ou mecanismos de controle" (made freely available,
  with no restriction of licences, patents or control mechanisms) (opened, second check). With the federal open data
  policy under "Licence notes", that may be enough for the maintainers to accept BHO 6 with credit to ANA; it is left to
  them. BHO 6 is v6.2.4 of 20 October 2022, as GeoPackage; its drainage file is 4.06 GB and its catchment file 20.1 GB, so
  a build would clip it per state. BHAE v1.0 (28 March 2023) is a lighter version with rivers draining 10 km² or more
  (opened, second check).
- **CPRM SIAGAS (groundwater wells).** The SIAGAS web portal (siagasweb.sgb.gov.br, opened 20 November 2026) has no
  licence or terms text. The agreements and reports found describe software licences, not data licences, and a 2008
  document says full data needs a written request. Not proposed; OSM water wells stand in for it. Next step: ask CPRM for
  the data licence.
- **Dams.** The merged pass found no open national list. The second check found **SNISB**, ANA's national dam safety
  register (open data item `dadosabertos.ana.gov.br/datasets/24d0145e38c545889fd5dd8d7aeaef32_0`, FeatureServer
  `snirh.gov.br/arcgis/rest/services/IG/SNISB/FeatureServer/0`; CSV, Shapefile, GeoJSON, KML), with coordinates for
  every dam: 28,127 nationally and 1,515 in São Paulo on 19 November 2026 (measured). The item's licence field is empty,
  so it stands where BHO 6 stands: ANA's open data statement above is the basis, and the decision is the maintainers'.

## Help points


The emergency numbers are the part people need most, and they are the same across the country. The primary numbers are
sourced to the Ministry of Communications. 112 and 911 are not emergency numbers in their own right: they are
conditional redirects (see the note below the table).

| Service | Number | Source for the number | Location data |
|---|---|---|---|
| Ambulance (SAMU) | 192 | Ministry of Communications, "Emergência: você sabe para quem ligar quando precisa de ajuda?", published 11 Sep 2026, updated 27 Oct 2026 (opened 21 Nov 2026), [link](https://www.gov.br/mcom/pt-br/noticias/2026/setembro/emergencia-voce-sabe-para-quem-ligar-quando-precisa-de-ajuda/) | not checked |
| Fire (Corpo de Bombeiros) | 193 | Ministry of Communications, "Emergência: você sabe para quem ligar quando precisa de ajuda?", published 11 Sep 2026, updated 27 Oct 2026 (opened 21 Nov 2026), [link](https://www.gov.br/mcom/pt-br/noticias/2026/setembro/emergencia-voce-sabe-para-quem-ligar-quando-precisa-de-ajuda/) | state fire services: not checked |
| Police (Polícia Militar) | 190 | Ministry of Communications, "Emergência: você sabe para quem ligar quando precisa de ajuda?", published 11 Sep 2026, updated 27 Oct 2026 (opened 21 Nov 2026), [link](https://www.gov.br/mcom/pt-br/noticias/2026/setembro/emergencia-voce-sabe-para-quem-ligar-quando-precisa-de-ajuda/) | state police: not checked |
| Conditional redirect to the Brazilian emergency service (mobile phones) | 112 and 911 | [Anatel Resolution 777, article 127](https://informacoes.anatel.gov.br/legislacao/resolucoes/2025/2022-resolucao-777) (opened 21 Nov 2026): redirected only "if technically feasible"; the Anatel codes page lists them as mobile only | state police: not checked |
| Civil defence (Defesa Civil) | 199 | Ministry of Communications, "Emergência: você sabe para quem ligar quando precisa de ajuda?", published 11 Sep 2026, updated 27 Oct 2026 (opened 21 Nov 2026), [link](https://www.gov.br/mcom/pt-br/noticias/2026/setembro/emergencia-voce-sabe-para-quem-ligar-quando-precisa-de-ajuda/) | not checked |

Notes:

- 112 and 911 are conditional redirects. Anatel Resolution 777, article 127, says that, "if technically feasible", a call
  to 112 or 911 is redirected to the matching Brazilian emergency service. A reader should dial 190, 192, 193 or 199
  first; 112 and 911 may not connect.
- The official lists were not checked: the national health register (CNES) and the state fire and police station lists.
  The second check has since parsed CNES and searched São Paulo's state lists; see "Help points and counts".
  OSM counts for hospitals, clinics, fire and police stations are given under "Help points and counts".
- The number table itself belongs to [issue #261](https://github.com/Immortal-Protocols/lastbook/issues/261), not to
  this map proposal. It is listed here so that the map and the number table agree.

## Checking a map change

- A change to a layer in `web/map.js` is a change you can see: include screenshots in light and dark mode.
- A change to a pack or map tool: `packaging/test_pack_tools.py` and `packaging/scan_pack.py` check what a map set may
  hold, and `scan_pack.py` lists the allowed files under `derived/geo/` (`GEO_FILES`).
- Nothing a contributor adds may make the app open a connection. New data comes in through a build tool and ships as a
  file.

Licences read for this proposal (20 November 2026):

- **ODbL 1.0** (OSM water and points): commercial use allowed; a derivative database is shared under the ODbL; credit
  "© OpenStreetMap contributors". Read on the opendatacommons.org licence page.
- **CC BY 4.0** (Google Open Buildings; the CNES dataset's `cc-by` field): adapt, including commercially, with attribution.
  Read on the creativecommons.org deed.
- **CNES dataset** (`cc-by`, from the dataset licence field): see the caveat under "Help points and counts".
- **Not licensed, so not proposed:** ANA BHO 6 ("free access" only); CPRM SIAGAS (no licence text); gov.br content
  (CC BY-ND 3.0, no adaptation).

## Addresses in Overture, from the publisher's guide

- **Brazil: 89,887,635 addresses**, in the per-country table of the Overture addresses guide
  (docs.overturemaps.org/guides/addresses/, opened 20 November 2026). This is the publisher's count, not one made for
  this proposal. The same table lists the US and Mexico (Mexico 30,726,687, as REGIONS-MX.md reads it).
- Per-state counts were not computed. The first digit of a CEP is not a state code (see below), so splitting on it
  would put addresses in the wrong state.
- **Source: IBGE's CNEFE** (second check, opened). Overture's attribution page names IBGE, distributed by AddressForAll,
  as the source of the Brazilian rows (see "Licence notes"). CNEFE (*Cadastro Nacional de Endereços para Fins
  Estatísticos*) is the address register IBGE built for the 2022 census. IBGE publishes it openly, one file per state
  (`ftp.ibge.gov.br/Cadastro_Nacional_de_Enderecos_para_Fins_Estatisticos/Censo_Demografico_2022/`; São Paulo's CSV is
  1.0 GB, dated 20 May 2024, and a GeoJSON version exists), with street type, title and name, number, CEP, locality,
  census tract, establishment name, latitude and longitude. Acre's file has 410,524 rows (measured). A coordinates-only
  file for São Paulo has **22,953,725 rows** (measured). IBGE reported 106.8 million addresses nationally, 22.8% with no
  number (search only); why Overture has fewer was not checked.
- **Splitting by state is possible without a CEP table** (second check). Every CNEFE record carries the state's IBGE
  code (`COD_UF`) and the municipality code, so a build that reads CNEFE directly can cut per state exactly. A build that
  reads Overture can use the state polygons, which are now CC BY 4.0 (see "Licence notes").
- **Coordinate quality** (second check, measured). Each CNEFE record has a level, `NV_GEO_COORD`: 1 is the original
  census point, 2 a point moved for flats sharing a number, 3 an estimate, and 4 to 6 only place it at the block face,
  the locality or the census tract. In Acre's file, 95% are level 1. An index could keep levels 1 to 3 and drop the rest.
- The Overture guide says address IDs are not stable enough to register in GERS, so IDs may change between releases.
  A build would need a fixed release.

## How addresses are written

Read from the Correios' *Guia Técnico de Endereçamento de Correspondências* (version 1.4, 2021) and the Correios
addressing guide page: **search snippets only**; the PDF was not opened. The second check opened the guide (version 1.4
of 3 May 2021), Correios' addressing guide page and its "Tudo sobre CEP" page; facts from them are marked below.

- **Postcode (CEP).** Eight digits, written `00000-000` with a hyphen after the fifth digit, for example `01311-000`
  (the Correios example). The Correios API accepts eight digits without the hyphen. Keep it as text, because leading
  zeros occur.
- **Order.** Street type, street name and number, then complement and neighbourhood, then city and state (UF), with
  the CEP last. The Correios guide puts the CEP alone on the last line of a hand-written address. The guide's own
  example is "Avenida Paulista 123, Loja B / Paraíso / 01311-000 São Paulo/SP", with city and state separated by "/"
  (opened, second check).
- **Street types** (second check). Correios lists 41 types, among them *rua*, *avenida*, *alameda*, *travessa*,
  *praça*, *estrada*, *rodovia*, *largo*, *viela*, *ladeira* and *vila* (opened), and publishes no table of
  abbreviations. The CNES file for São Paulo shows how they are written in practice: `RUA` (57,882), `AVENIDA`
  (15,325), `AV` (9,578), `R` (5,986), and `PRACA`, `ALAMEDA`, `AL`, `AVN`, `ROD`, `ESTRADA` and `TRAVESSA` (measured).
  Roadside addresses often carry a kilometre inside the street field, such as "ROD WASHINGTON LUIZ KM 234" (measured).
- **No number.** Correios writes `SN` (*sem número*, "no number"). The CEP complement is then `00000` (search snippet
  only). The guide itself recommends the abbreviation `s/n` ("Para os logradouros sem numeração recomenda-se a
  utilização da sigla s/n"; opened, second check); the data holds `S/N` and `SN`.
- **CEP structure** (second check, opened, Correios "Tudo sobre CEP"). The first digit is one of ten postal regions,
  numbered anticlockwise from São Paulo; the next four digits narrow it to sub-region, sector, subsector and subsector
  divisor. The three-digit suffix tells streets (000 to 899) from special codes (900 to 959), promotional codes (960 to
  969) and Correios units (970 to 989 and 999), with 990 to 998 for community post boxes. Correios' CEP database (DNE)
  is a licensed product sold under a price list ("Produto licenciado, com restrições de uso e proteção por direitos
  autorais"; opened), so it is not open. CNEFE carries a CEP on its records, so a separate CEP source is not needed.
- **The CEP is not a state code.** The first digit is a broad region, not a state, and no CEP-to-state table was
  checked. Address indexes cannot be split by state until one is found or a state polygon is used. The second check
  found that CNEFE's state code answers this (see "Addresses in Overture").
- **What the code does now** (read in this repository, 20 November 2026):
  - `tools/build_addresses.py` keeps only `country = 'US'`; the Brazilian rows would need the country changed.
  - `normalize()` in `engine/address_search.py` replaces every character outside `a-z` and `0-9` with a space, so
    Portuguese accents split words: "Ação" becomes "a o". Accent folding would be needed, as noted for Spanish in
    REGIONS-MX.md.
  - `is_address_query()` needs a number first, so "Rua do Lago 50, 01311" is not treated as an address today.
  - Tested on 18 November 2026 (second check, measured): "Av. Paulista, 1578, Bela Vista, São Paulo - SP, 01310-200" and
    "Rua Conceição, 233, Campinas, SP" are not treated as addresses; only the US order, "1578 Avenida Paulista", is.
  - Someone who types without accents, as many people do on a phone, gets `rua conceicao`, while the index holds
    `rua concei o`, so the two do not match (second check, measured).
  - The street words in `normalize()` are English: `av` becomes `ave`, but `avenida` stays `avenida`, so "Av Paulista"
    and "Avenida Paulista" do not match each other. Portuguese street types would need their own table (second check,
    measured).
  - A CEP is not read as a postcode: the parser looks for five digits at the end, and "01310-200" becomes `01310 200`.
    `build_addresses.py` keeps `left(postcode, 5)`, which for a CEP keeps the region to the subsector (`01310`), a useful
    key if the parser reads the same five digits. How Overture writes Brazilian postcodes was not checked (second
    check).
  - The place finder is already fine: its FTS5 index uses the `unicode61` tokenizer, which folds accents. Tested on 18
    November 2026: `sao paulo`, `ribeirao`, `sao jose campos`, `guaruja`, `conceicao`, `barbara oeste` and `embu guacu`
    found "São Paulo", "Ribeirão Preto", "São José dos Campos", "Guarujá", "Conceição de Macabu", "Santa Bárbara
    d'Oeste" and "Embu-Guaçu" (second check, measured).

## Still undecided

Each of these needs the maintainers' decision before any code changes.

1. **Codes in setup.** Whether `BR-AC` and the others are acceptable as a manifest `id`, and the `carry_over()` rule in
   `engine/setup/install.py` (line 335), which keeps only `[A-Z]{2}` index names.
2. **DF and Goiás.** Separate maps, or the Goiás map includes DF (the box overlap, as for CABA in REGIONS-AR.md).
3. **Trindade and Martim Vaz.** A separate small map, or no map. No resident population was checked.
4. **Atol das Rocas and São Pedro e São Paulo.** Not in the IBGE polygons; whether either should have a map.
5. **IBGE licence.** The malhas are CC BY 4.0 (second check). What remains: whether Localidades 2022 counts as a
   derived product under the same note, and how the map credits IBGE for CNEFE (Overture's CC0 line, an attribution
   line, or both).
6. **CEP.** No open CEP-area source was found, and Correios' DNE is sold. Splitting by state no longer depends on it:
   CNEFE carries the state code (second check). Address search still needs to read an eight-digit CEP, the number after
   the street, Portuguese street words and accent folding.
7. **Crop classes.** MapBiomas' classes are now known (second check: coffee, citrus, other perennial crops and more), and
   its licence is CC BY 4.0 per its toolkit, with a CC BY-SA reading to rule out. Which classes map to the orchard,
   vineyard and berry kinds in `tools/build_crops.py` is still to decide.
8. **Overlapping boxes.** Boxes follow each state's outline, so neighbours overlap along borders. Whether that is
   acceptable is the same question as in REGIONS-MX.md.
9. **Water sources.** ANA's licence for BHO 6 and CPRM's licence for SIAGAS data are both unanswered. Both fail the test
   until one is named. The second check adds ANA's open data statement ("sem restrição de licenças"), which covers BHO 6
   and the SNISB dam register alike; whether that statement is enough is the maintainers' call.
10. **CNES.** Confirm that the dataset licence (`cc-by`) governs the CNES data, not the portal footer (CC BY-ND). The file
    has coordinates (second check).

## What was checked, and what was not

- **Opened on 20 November 2026:** the IBGE malhas API, state polygons at maximum quality, for all 27 units; the gov.br
  "Sobre o portal" page and the federal SAMU 192 article (footer licence CC BY-ND 3.0 Brazil); the Anatel public-utility
  and emergency codes page (190, 192, 193, 199, and 112/911 listed as mobile only); on 21 November 2026, the Ministry of
  Communications emergency numbers article and Anatel Resolution 777, article 127 (112/911 redirected only if technically
  feasible); the Overture addresses guide
  (Brazil 89,887,635); the Wikipedia article "ISO 3166-2:BR" (27 codes, names from the ISO 3166/MA).
- **Computed on 20 November 2026:** the 27 tight boxes and the 0.15° margins (floor for west and south, ceiling for
  east and north, to 0.01°); the detached-island check across all 27 units; the Espírito Santo box without Trindade and
  Martim Vaz.
- **Seen only in search results:** the IBGE technical and legal note and the BC250 terms (restricted use); the Correios
  addressing guide; a 2017 federal open-data resolution that lists CC0, PDDL, CC BY 4.0 and ODbL as acceptable.
- **Opened on 20 November 2026 (water and help points):** the Overpass API (OSM counts, eight tags: the 27 unit queries
  completed; the country-wide query timed out); the ODbL 1.0 and CC BY 4.0 licence texts; the ANA BHO 6 metadata record;
  the SIAGAS web portal (no licence text); the CNES dataset page (licence field `cc-by`); the CNES portal footer (CC
  BY-ND 3.0 for the site).
- **Checked on 21 November 2026 (Mato Grosso springs):** the four-quarter Overpass count described under "Help points
  and counts" (31,074 + 19,825 + 40 + 2,641 = 53,580) and a whole-state count (53,580); the object metadata of the
  south-west and south-east quarters; the eight changesets on the OSM API (user, date, created count, `source=SEMA-MT`,
  no comments); the OSM wiki Contributors page and Import/Catalogue (no SEMA-MT entry); the SEMA-MT home page footer and
  the Mato Grosso open-data catalogue (no licence for spring data). The GeoDados MT portal did not load without a
  browser, so it was not read.
- **Seen only in search results:** the Ministry of Health open-data plans (CC BY-NC-SA); the CPRM SIAGAS agreements;
  the ANA open-data policy wording.
- **Not checked:** the ISO Online Browsing Platform (iso.org); the IBGE technical and legal note itself; the CNES health
  register; state fire and police station lists; MapBiomas licence and class list; Google Open Buildings coverage for
  Brazil; per-state Overture address counts; the populations of Trindade and Martim Vaz. (The second check, below, has
  since opened the IBGE note, the CNES register and MapBiomas' README and legend.)

### Second check, 18 to 24 November 2026

- **Opened:** IBGE's full-resolution state layer `BR_UF_2022.zip` and the `regiao-limitrofe` of all 27 units on the
  malhas API; IBGE's boundary note (Notas metodológicas 01/2025, CC BY 4.0); the BC250 2025 folder and its 2019 terms;
  IBGE's CNEFE 2022 folders, data dictionary and Acre file; IBGE's Localidades do Brasil 2022 file; Overture's addresses
  guide and attribution page; OpenAddresses' Brazilian source files; Google's Open Buildings and 2.5D Temporal pages;
  Microsoft's footprints repository and its licence history; OpenTopography's ANADEM record; INPE's TOPODATA STAC record;
  ANA's BHO 6 and BHAE metadata, ANA's open data page, and SNISB's open data item and FeatureServer; MapBiomas' toolkit
  README and Collection 11 legend; the full CNES file and the UBS file; ANP's fuel retailer dataset; the São Paulo state
  open data portal and the state schools file; GeoSampa's licence page and layers; DataGeo's pages and layers; IGC's
  site; Correios' addressing guide (v1.4), addressing page, "Tudo sobre CEP" page and DNE page; Decreto 8.777/2016 and
  Decreto 9.903/2019 (article 4); CGINDA Resolution nº 2/2017; `engine/address_search.py`, `tools/build_addresses.py`
  and `tools/build_places.py` on `main`.
- **Measured:** the 27 boxes from `BR_UF_2022.zip` and which polygon sets each changed edge; CNES rows, coordinates and
  São Paulo counts by type; SNISB counts for Brazil and São Paulo by agency; CNEFE rows in Acre's file (with `COD_UF`
  and `NV_GEO_COORD`) and in São Paulo's coordinates file; Localidades counts for São Paulo; the São Paulo OSM counts in
  "São Paulo in detail" (Overpass, data of 18 November 2026) and the `amenity=shelter` types (a second Overpass server,
  data of 1 June 2026); the address-parser and place-finder tests.
- **Search only:** the MapBiomas terms page (CC BY-SA); CNEFE's national totals; INEP's national school count (about
  226,000).
- **Not checked:** an IBGE licence statement on the CNEFE files or Localidades; MapBiomas' terms page itself; whether
  INEP's national school catalogue has coordinates; per-dataset licences on `dados.gov.br` (its API needs a token);
  article 1 of Decreto 8.777/2016 (the site dropped the connection); the state fire department's and police's own
  sites; S2iD and CEMADEN; a statewide São Paulo terrain model; ANADEM's vertical accuracy; Google Open Buildings
  coverage of Brazil; how Overture writes Brazilian postcodes; OSM address coverage in São Paulo (the Overpass count of
  `addr:housenumber` timed out); help-point counts beyond São Paulo.

