# Detailed maps for Costa Rica: a proposal

This is a proposal for discussion, not a decision. It answers, for Costa Rica, the questions [MAPS.md](MAPS.md) asks before
coverage can go beyond the United States: which open source replaces each federal list, under what licence, what a "state"
is there, and how addresses are written. It follows the shape of [REGIONS.md](REGIONS.md), [REGIONS-PY.md](REGIONS-PY.md)
and [REGIONS-LK.md](REGIONS-LK.md) and is meant to feed the same design discussion (issues #23, #25 and #31). The
machine-readable version is [regions-cr-proposed.json](regions-cr-proposed.json), and a Spanish translation is
[REGIONS-CR.es.md](REGIONS-CR.es.md).

Nothing here changes the app, the engine or a build. No code reads the JSON, and nothing here ships: builds package
`web/` and `content/` only.

**How things were checked.** Research was done on 18 November 2026. Each fact carries one of these marks:

- **opened**: the page, file or API response itself was opened and read;
- **computed**: the figure was computed here from a downloaded file (the file and method are named);
- **search only**: the fact was seen in a search result, but the page itself was not opened;
- **general knowledge**: stated from memory, with no source opened; it needs a local reader's check;
- **not checked**: the page could not be reached or read; the row says what is missing.

"None found" means none found by web search. Several Costa Rican government sites could not be read in full:
`geoportal-saracc.cne.go.cr` did not resolve, `www.cne.go.cr` answered 403, `www.sinac.go.cr` failed its certificate
check, and the one INVU address tried returned 404. The Overpass API was not used; OSM figures were counted from
Geofabrik's extract.

## What a region is

Costa Rica has 7 provinces, 84 cantons and 492 districts (the counts of features in OCHA's COD-AB, computed; the file
itself notes it lacks the canton of Caldera, created in 2014, opened). The proposal is **one region for the whole country**,
code `CR`, as REGIONS-PY.md proposes for Paraguay and REGIONS-LK.md for Sri Lanka. A bare `CR` collides with no code in
`STATE_CODES` (`engine/address_search.py` line 26, opened; the list has `CA`, `CO` and `CT` but no `CR`).

Why one region:

- **Size.** The COD-AB level 0 polygon covers 51,168 km² (its `area_sqkm` attribute, which includes Isla del Coco; the
  official figure is about 51,100 km², general knowledge). That is smaller than West Virginia (62,756 km², general
  knowledge), so it is well inside what Lastbook already ships as one state map. The whole-country OSM extract is
  37.4 MB, a quarter of Paraguay's 147 MB.
- **Provinces are not small, but people cross them.** The largest, Puntarenas, is 11,298 km² and the smallest, Heredia,
  2,664 km² (`area_sqkm` of COD-AB level 1). Most of the population lives in the Central Valley, where San José, Alajuela,
  Heredia and Cartago meet (general knowledge; not checked against the 2022 census). Someone there who picked one
  province's map would lose part of the city they live in, the same problem REGIONS-AR.md describes for Buenos Aires.
- **Few people live on the edges.** Large parts of Guanacaste, Limón and the south of Puntarenas are sparsely populated
  (general knowledge); a whole-country map should add little there.

If the maintainers prefer finer regions, the province boxes are listed below. The Central Valley question is handled as a
separate grouping at the end of this section.

### Box

The recommended box is the **mainland** box. Isla del Coco is Costa Rican territory (part of Puntarenas province in
COD-AB, opened) but lies far out in the Pacific, and a box that holds it more than doubles the area of the rectangle with
almost nothing but sea in it.

| Code | Name | Box (west, south, east, north) | Box with 0.15° margin | Box taken from |
|---|---|---|---|---|
| `CR` | Costa Rica, mainland (**recommended**) | -85.9503, 8.0402, -82.5528, 11.2196 | -86.11, 7.89, -82.40, 11.37 | OCHA COD-AB level 0, without the 24 Isla del Coco polygons (computed) |
| `CR` | Costa Rica, with Isla del Coco | -87.1019, 5.4991, -82.5528, 11.2196 | -87.26, 5.34, -82.40, 11.37 | OCHA COD-AB level 0, all vertices (computed) |
| (not a region) | Isla del Coco alone | -87.1019, 5.4991, -87.0278, 5.5635 | -87.26, 5.34, -86.87, 5.72 | the 24 polygons that lie west of 86°W (computed) |

The box is the extent of every vertex of OCHA's level 0 polygon (`cri_admin0.geojson`, source INEC, valid on 3 December
2024, HDX record last modified 14 August 2026; downloaded and computed on 18 November 2026), minus/plus 0.15° and rounded
outward to 0.01°, the same margin `map_sets.state` uses for US states. The level 0 file is one feature whose geometry has
polygons for the mainland, the Nicoya and other islands, and 24 for Isla del Coco and its islets (all west of 86°W;
split by longitude, computed).

Geofabrik's clipping polygon (`costa-rica.poly`, opened) has a box of -87.82473, 4.937746, -82.34952, 11.2237. It covers
Isla del Coco too, and is looser than any of the boxes above, as expected for a polygon drawn around the border.

**What to do with Isla del Coco.** The suggestion is the mainland box for `CR`, with Coco noted as left out of the
rectangle. The Geofabrik extract does include it (the polygon above reaches 87.8°W), so the island's OSM data would be
in a build and only dropped by the box clip. If the maintainers want the island kept, the clean way is a second, tiny
box (the third row), not widening `CR`. The island has no residents except park rangers (general knowledge), so it
matters for completeness more than for use. Whether `map_sets` can take two boxes for one id is a code question this
proposal does not answer.

**Neighbours inside the mainland box** (general knowledge; not measured). To the north, the south of Nicaragua: the
department of Rivas with San Juan del Sur, the south shore of Lake Nicaragua, and the south of the Río San Juan
department. To the south-east, a strip of Panama along the border (Chiriquí and the west tip of Bocas del Toro). The rest
is sea. Border crossings with a town on each side include Paso Canoas and Sixaola with Guabito. Geofabrik's extract is
cut outside the border, so a first build holds some of these places; how much was not measured. The suggestion is the
same as for Paraguay: keep the border as the edge for a first build and decide on a band later.

### A boundary in dispute: the northern part of Isla Portillos

Costa Rica and Nicaragua disputed a wetland of about 3 km² in the north of Isla Portillos, at the Caribbean mouth of the
San Juan River. On 16 December 2015 the International Court of Justice held, 14 votes to 2, that Costa Rica has
sovereignty over this "disputed territory", and that Nicaragua's dredging of caños and military presence there violated
that sovereignty (opened: the Court's summary of the judgment). The same page says Harbor Head Lagoon is agreed to be
Nicaraguan. A second judgment of 2 February 2018 settled the land boundary at the coast: Costa Rica has sovereignty over
the whole northern part of Isla Portillos including its coast, except Harbor Head Lagoon and the sandbar separating it
from the sea (search only, from the Court's press material; the 2018 judgment itself was not opened).

What this means for the map, plainly: COD-AB shows the area as Costa Rica (its district Colorado, in Pococí canton, Limón province, has vertices up to
10.9424°N, computed; whether its edge follows the 2018 line was not checked), which agrees with the Court. How OSM draws
it was not checked. Lastbook needs no special treatment here beyond drawing the border where the
Court put it; the point is listed so it is decided once for every region (REGIONS.md item 6).

### Provinces, if finer regions are wanted

ISO 3166-2:CR gives `CR-SJ` San José, `CR-A` Alajuela, `CR-C` Cartago, `CR-H` Heredia, `CR-G` Guanacaste, `CR-P` Puntarenas
and `CR-L` Limón (general knowledge; not checked against the ISO site). COD-AB's p-codes are `CR1` to `CR7` in the
order San José, Alajuela, Cartago, Heredia, Guanacaste, Puntarenas, Limón (computed), which is not the ISO order, so
anything joining the two must join by name.

The boxes were computed from OCHA's level 1 polygons (`cri_admin1.geojson`, 7 features) by the same rule as above.
Puntarenas is the only province with Isla del Coco in it, so it has two boxes.

| ISO code | COD-AB p-code | Name | Box (west, south, east, north) | Box with 0.15° margin | Area (km², `area_sqkm`) |
|---|---|---|---|---|---|
| `CR-SJ` | CR1 | San José | -84.5927, 9.0751, -83.4294, 10.1910 | -84.75, 8.92, -83.27, 10.35 | 4,971 |
| `CR-A` | CR2 | Alajuela | -85.4493, 9.8401, -84.1612, 11.0843 | -85.60, 9.69, -84.01, 11.24 | 9,773 |
| `CR-C` | CR3 | Cartago | -84.0882, 9.4841, -83.3119, 10.1475 | -84.24, 9.33, -83.16, 10.30 | 3,094 |
| `CR-H` | CR4 | Heredia | -84.2002, 9.9594, -83.7100, 10.7925 | -84.36, 9.80, -83.55, 10.95 | 2,664 |
| `CR-G` | CR5 | Guanacaste | -85.9503, 9.7269, -84.7661, 11.2196 | -86.11, 9.57, -84.61, 11.37 | 10,192 |
| `CR-P` | CR6 | Puntarenas, mainland | -85.2798, 8.0402, -82.7120, 10.3375 | -85.43, 7.89, -82.56, 10.49 | 11,298 (includes Coco) |
| `CR-P` | CR6 | Puntarenas, with Isla del Coco | -87.1019, 5.4991, -82.7120, 10.3375 | -87.26, 5.34, -82.56, 10.49 | |
| `CR-L` | CR7 | Limón | -83.9474, 9.0748, -82.5528, 10.9424 | -84.10, 8.92, -82.40, 11.10 | 9,177 |

The seven areas add up to the 51,168 km² of level 0 (computed). Boxes of neighbouring provinces overlap heavily: the
Central Valley sits where the San José, Alajuela, Heredia and Cartago boxes meet, so a single province's map cut by its
box holds a good part of the others' land.

### The Gran Área Metropolitana (GAM), as a separate grouping

The GAM is the urban region of the Central Valley. It is a planning region, not an administrative level. The Plan
Regional de Ordenamiento Territorial de la Gran Área Metropolitana, "Plan GAM 2013-2030", was approved by the Consejo
Nacional de Planificación Urbana on 20 January 2014 and made official by Decreto 38145 (a 2014 regulation numbered
38334-H also appears in search results) (search only, from CEPAL's Plataforma Urbana). The INVU's Dirección de Urbanismo
and the Council's secretariat follow its execution (search only). A search source puts it at 31 cantons and 165
districts (search only), spread across San José, Alajuela, Cartago and Heredia.

What is not known:

- **The exact list of cantons.** A partial list from the decree text includes San José, Escazú, Desamparados, Mora,
  Goicoechea, Santa Ana, Aserrí, Alajuelita, Vázquez de Coronado, Tibás, Moravia and Montes de Oca (search only,
  truncated). The full list, and whether some cantons count as wholly or partly inside, was not read.
- **A downloadable polygon.** None found. The plan's "Atlas Digital del Plan GAM 2013" has 83 maps and 172 layers and is
  listed in the Instituto Tecnológico de Costa Rica's repository (search only); how to get the files was not found. The
  INVU page tried returned 404, and CEPAL's page answered 403. Without a file there is no licence to quote.
- **Licence.** Not found, so none is assumed.

Two ways to make the grouping, if it is wanted. (1) The union of the cantons the plan names, taken from COD-AB level 2
(CC BY-IGO, opened), once the list is confirmed; that needs no file from the INVU. (2) The plan's own polygon, which
needs the INVU's permission. As with Bangkok in REGIONS-TH.md and Asunción in REGIONS-PY.md, it would be a separate
grouping with its own id (for example `CR-GAM`; the id is the maintainers' choice), not a `CR-SJ` that means more than
San José province. Its box was not computed because the canton list is not confirmed.

**Already in flight.** No open pull request proposes Costa Rica as a region (searched 18 November 2026). PR #35 has a
`cr-san` capital box, -84.39, 9.64, -83.79, 10.24, cut from the same Geofabrik extract. That square holds the cities of
San José, Alajuela, Heredia and Cartago, so it is close to the GAM's core, but it is a fixed 0.6° square and not the
plan's boundary. A whole-country region would contain it.

**Possible cross-check.** geoBoundaries' ADM1 file for Costa Rica could be used to check the boxes. It was not looked at.

## Sources, layer by layer

OpenStreetMap is the backbone for a first build. Costa Rica's statistics office (INEC) supplies the boundaries through
OCHA. The national geoportal (SNIT, run by the Instituto Geográfico Nacional inside the Registro Nacional) holds official
terrain, water and cadastral-style layers, but its terms were not found open. Overture's address theme does not list
Costa Rica, and its places theme gives no country figures.

| Layer (file) | US source today | Proposed for Costa Rica | Publisher | Licence | Mark |
|---|---|---|---|---|---|
| Roads, water, land (base map) | OSM extract | OSM extract `costa-rica-latest.osm.pbf` (37.4 MB; the free `.shp.zip` is 79 MB and the `.gpkg.zip` 81 MB), data up to 17 November 2026 21:24 UTC | OSM contributors via Geofabrik | ODbL 1.0 | opened |
| Points of interest (`poi`) | OSM | OSM (counts below) | OSM contributors | ODbL 1.0 | computed |
| Places (`places.sqlite`) | GNIS, Census gazetteers, OSM | OCHA COD-AB levels 1 to 3 (7 provinces, 84 cantons, 492 districts) and its `adminpoints`; OSM named places | OCHA, from INEC; OSM contributors | CC BY-IGO; ODbL 1.0 | HDX record, files and feature counts opened |
| Terrain (`terrain.sqlite`) | USGS 3DEP | Copernicus DEM GLO-30, as proposed for Guyana and Paraguay | ESA / Airbus | Copernicus WorldDEM-30 licence | collection page opened (free for the general public under the Copernicus licence); notices as in REGIONS.md |
| Terrain, national alternative | | SNIT / IGN contour lines (10 m and 2 m), digital elevation models | IGN, Registro Nacional | **not found**: the SNIT page shows "Todos los derechos reservados" and no open licence | search only for the layers; SNIT home page opened for the rights line |
| Water (`water.sqlite`) | NHD | OSM waterways and water areas; IGN 1:5000 hydrography, if its terms allow | OSM contributors; IGN | ODbL 1.0; unclear | search only (IGN layer) |
| Dams | NID | OSM `waterway=dam` and `water=reservoir`; no open dam inventory found | OSM contributors | ODbL 1.0 | computed |
| Crops (`crops.sqlite`) | USDA Cropland Data Layer | ESA WorldCover 2021 (10 m land cover, v200); no national crop map found | ESA WorldCover consortium | CC BY 4.0 | opened (AWS registry page) |
| Buildings (`buildings.sqlite`) | Microsoft US footprints, OSM heights | Microsoft Global ML Building Footprints (21 tiles, 1,460,785 rows for Costa Rica); Overture buildings as an alternative; OSM heights | Microsoft; Overture Maps Foundation; OSM contributors | CDLA Permissive 2.0 (Microsoft); ODbL (Overture) | tile list and rows computed; licence from the README, opened |
| Addresses (`addresses/<code>.sqlite`) | Overture addresses | **None found.** Overture's address theme lists 41 countries, and Costa Rica is not among them | | | opened |

### Help and resource points

Counts were made with pyosmium over the Geofabrik extract above (data up to 17 November 2026 21:24 UTC). Each count
includes nodes, ways and relations carrying the tag.

| Kind | OSM tag | Count | Other source | Mark |
|---|---|---|---|---|
| Hospitals | `amenity=hospital` | 119 | Ministry of Health / CCSS lists, not looked for | computed |
| Clinics and doctors | `amenity=clinic`, `amenity=doctors` | 1,576 (1,152 clinics, 424 doctors) | as above | computed |
| Pharmacies | `amenity=pharmacy` | 714 | none found | computed |
| Fire stations | `amenity=fire_station` | 80 | Cuerpo de Bomberos, not looked for | computed |
| Police | `amenity=police` | 690 | none found | computed |
| Ambulance stations | `emergency=ambulance_station` | 127 | Cruz Roja, not looked for | computed |
| Drinking water | `amenity=drinking_water`, `man_made=water_tap`, `amenity=water_point` | 91 (54, 28, 9) | none found | computed |
| Wells, water towers and tanks | `man_made=water_well`, `water_tower`, `storage_tank` | 491 (16 wells, 120 towers, 355 tanks, contents not checked) | none found | computed |
| Reservoirs and dams | `water=reservoir`, `waterway=dam` | 134 reservoirs (`landuse=reservoir` not counted), 25 dams | none found | computed |
| Fuel | `amenity=fuel` | 441 | none found | computed |
| Shelters and assembly points | `amenity=shelter`, `social_facility=shelter`, `emergency=assembly_point` | 393 (379, 14, 1) | CNE, see notes | computed |
| Schools | `amenity=school` | 4,442 | Ministry of Education (MEP), not looked for | computed |
| Ranger stations | `amenity=ranger_station` | 52 | SINAC, see notes | computed |
| Volcanoes and hot springs | `natural=volcano`, `natural=hot_spring` | 57 (35, 22) | OVSICORI, see notes | computed |
| Protected areas | `boundary=protected_area` | 111 | SINAC, see notes | computed |

Notes:

- **A count of rows is not a count of places.** OSM often has one hospital as a point and again as each of its buildings.
  The counts above are upper bounds; no grouping by distance was done here.
- **"Shelter" in OSM.** `amenity=shelter` marks small roofs, not emergency shelters. Of the 379 in Costa Rica, by
  `shelter_type` (computed): 138 public transport, 115 lean-to, 69 with no type, 26 picnic shelter, 20 gazebo, 5 pavilion,
  3 eruption shelter, 2 basic hut and 1 weather shelter. They should not be drawn as emergency shelters. The one OSM
  `emergency=assembly_point` is the only emergency assembly point in the extract. The 3 eruption shelters are a
  Costa Rican case worth looking at by hand.
- **Volcano tags.** 35 `natural=volcano` objects is more than the active volcanoes of the country (general knowledge:
  five or six are active); the tag includes extinct cones and craters. They are marked in OSM without a status here.
- **Terrain.** Copernicus GLO-30 is a surface model: under forest it follows the canopy, not the ground. Much of Costa
  Rica is forested (general knowledge), so the 3D view will show the tree tops there. The IGN's own contour lines and
  models might be better, but no open licence was found for them.
- **Crops.** WorldCover maps land cover classes (tree cover, cropland, built-up and so on), not crop types, so the
  class mapping for `tools/build_crops.py` needs a decision (as item 4 in REGIONS.md). No Costa Rican national crop or
  land-use layer was looked for beyond this; none appeared.
- **Buildings.** Microsoft's footprints are partitioned by country and level-9 quadkey; Costa Rica has 21 tiles in
  `dataset-links.csv` (computed), dated 23 February 2026, 1,460,785 lines in all (computed: each tile decompressed and
  its lines counted; a line is one footprint, as the README's line-delimited GeoJSON implies). One tile (quadkey
  `032221002`, 57.7 MB) holds 693,762 of them, 47%, which is where the Central Valley should be, but the tile's position
  was not mapped. OSM has 201,480 building ways in the same extract (computed, ways only; relations and nodes not
  counted), so Microsoft's file is much denser than OSM. Overture buildings put OpenStreetMap first in priority and add
  Microsoft and Google footprints (opened, Overture's buildings page), so an Overture build and a Microsoft build overlap.
  The footprints were not checked against real buildings.
- **Overture places.** Overture's places page (opened) gives counts by source but none by country, and says
  country-level figures will be published once confirmed. Costa Rica's share is therefore not known. Its licences are
  CDLA Permissive 2.0, Apache 2.0 and CC0, by source.
- **Official boundaries.** COD-AB says it contains two topological overlap errors and five gap errors, and lacks the
  canton of Caldera (opened, from the HDX record). Its ADM3 "Alfaro Ruiz" appears as Zarcero in COD-AB (same note).
- **Open data portal.** `datos.go.cr` is the national portal (opened). Its home page lists one dataset under "Ambiente",
  and no dataset from the CNE, SINAC, IGN or INVU appeared there; it states no default licence.
- **Addresses.** OSM has 11,803 objects with `addr:housenumber`, 33,402 with `addr:street` and 8,560 with
  `addr:postcode` (all computed). The low number for door numbers is not a gap in the map: most Costa Rican addresses
  have none (see below). A first Costa Rican map would ship as "street map, places and help points" without address
  search, as suggested for Paraguay and Sri Lanka.

### Hazards: an optional Costa Rica layer

Costa Rica has several hazards that matter for a survival library: earthquakes, volcanoes, floods, landslides and
tsunami (general knowledge). Nothing below is proposed for a first build. The point is to say what could feed such a
layer and be honest about the licence.

| Layer | Publisher | What was found | Licence | Mark |
|---|---|---|---|---|
| Hazard maps by canton (*amenazas*) | CNE (Comisión Nacional de Prevención de Riesgos y Atención de Emergencias) | Its geoportal `geoportal-saracc.cne.go.cr` is listed with OGC services (WMS, WFS, WCS, WMTS) and a catalogue; the host did not resolve from here. Hazard layers by canton are cited in studies; whether they can be downloaded was not found | **not found** | search only |
| Volcano and seismic data | OVSICORI-UNA | The site's menu shows a daily seismic count, historical seismicity, monthly bulletins and a "Descargas" section; what is in it was not read. The 2025 annual seismic report carries CC BY 4.0 on its own page, and other reports in the same repository carry CC BY-NC-SA 4.0 | The site footer says "Todos los derechos reservados" (opened); document licences differ (search only) | home page opened; rest search only |
| National seismic network | RSN (UCR-ICE) | Nothing found | **not found** | not checked |
| Protected areas (*áreas silvestres protegidas*) | SINAC | A newspaper puts the count at 169 (search only). The INVU holds a map of them for the GAM plan (2013). No downloadable boundary file found; `www.sinac.go.cr` failed its certificate check. OSM has 111 `boundary=protected_area` objects (computed) | **not found** | search only |
| Overture / OSM | | OSM volcanoes, hot springs and ranger stations (counts above) are available now under ODbL | ODbL 1.0 | computed |

So of the three layers asked about, none has an open licence found. The CNE's OGC services and OVSICORI's downloads would
need a licence or a written yes before any file is copied into a map set. For now OSM alone can show volcanoes, hot
springs and protected areas, with the caveat that the volcano tag mixes active and extinct.

## Licence notes and attribution

- **CC BY-IGO** (OCHA's COD-AB, opened through HDX's API: source "Costa Rica National Statistics Office (NSO)"; HDX
  record last modified 14 August 2026; boundaries valid on 3 December 2024). Credit OCHA and its source.
- **ESA WorldCover** is CC BY 4.0 (opened, AWS registry). A map must carry the credit given in REGIONS.md.
- **Copernicus GLO-30**: free for the general public under the Copernicus licence (opened, AWS registry);
  the notices to carry are in REGIONS.md.
- **Microsoft Global ML Building Footprints**: CDLA Permissive 2.0 (opened, the repository's README as summarised); an
  Overture build is ODbL because it includes OSM.
- **ODbL and CC BY 4.0:** as in REGIONS.md.
- **SNIT / IGN, CNE, OVSICORI, SINAC:** no open licence found. The SNIT page says "Todos los derechos reservados" and
  "La oficialidad es responsabilidad de la institución que la publique" (opened). Do not copy these layers without
  asking.

## How addresses are written

This part needs a Costa Rican reader's review.

- **Directions from a landmark.** Most addresses carry no street name and no number. They give a starting point, a
  direction and a distance, in blocks (*cuadras*) or metres: "De la pulpería La Chanchita, 400 al este, 200 al sur y 25
  al norte" (opened: a 1997 La Nación column), or "De la Iglesia de Zapote 200 mts al Sur" (search only: given as the
  postal service's own head-office address). The landmark is a church, a school, a shop or a vanished building. The
  address is not a unique string: the same landmark name occurs in many towns, so the district and canton matter.
- **Official attempts.** Correos and municipalities have tried to number streets and houses; a street-name project in San
  José started in 2012 (search only). A 2005 report says Correos planned new street addresses (search only). How far it
  got was not found. Correos estimates 40% of customer addresses are wrong (opened: La Nación, 2009).
- **Postal code.** Five digits: the first is the province, the next two the canton, the last two the district. For
  example `30502` is La Suiza (02), Turrialba (05), Cartago (3) (opened: La Nación, and Wikipedia gives the same
  structure). The numbers match INEC's territorial division, so there is one code per district, and 492 districts in
  COD-AB match the "492 codes" a search result gave (another database lists 487). It is free from Correos' website or any
  branch. **Two dates conflict:** La Nación's page is dated 28 April 2009 and Wikipedia says the codes were introduced in
  March 2013. How widely they are used was not found; Correos says a postal worker reads an address in about 7 seconds
  and a code halves that (opened, La Nación 2009), which is a claim, not a measurement. OSM carries `addr:postcode` on
  8,560 objects (computed).
- **What the current code does with that.**
  - The five digits fit what `engine/address_search.py` accepts (`\d{5}`, line 65), but they mean something else: in the
    US they are a ZIP; here they name a district. The place finder does not know that, so a Costa Rican code would be
    matched as a ZIP only if the index had such a row. REGIONS-PY.md's six-digit problem does not arise.
  - `_parts()` expects a house number as the first word of the query ("number, remainder = query.strip().split(None,
    1)"), which suits "10 Calle X" and not "200 m norte de la Iglesia". Costa Rican search would be by place name, not
    by address.
  - `normalize()` keeps only `a-z`, `0-9` and spaces, so every other letter becomes a space: "200 m norte de la Iglesia
    de Zapote, San José 10101" becomes `200 m norte de la iglesia de zapote san jos 10101`, and "Pérez Zeledón" becomes
    `p rez zeled n` (the regex of `normalize()` run on 18 November 2026). Folding is needed on both sides; REGIONS-PY.md
    and REGIONS-DE.md found the same, and #79 proposes that each index declares its own rule.
  - The place finder uses an FTS5 index with the `unicode61` tokenizer, which folds diacritics (as REGIONS-PY.md tested
    for Spanish and Guaraní). It was not re-run for Costa Rican names.

## Language

Spanish is the official language; indigenous languages are recognised (general knowledge). Place names are Spanish with
many indigenous names (Guanacaste, Turrialba, Irazú). Spanish accents (á, é, í, ó, ú, ñ) are the only special letters
most names need, which is the `normalize()` problem above. Which name the map shows where an indigenous or English name
also exists was not looked at; that is part of the language question in issues #3 and #54.

## Still undecided

Each of these needs the maintainers' decision before any code changes. Items 1, 2, 4 and 5 correspond to REGIONS.md
items 1, 2, 4 and 3, and item 9 to its item 7.

1. **Codes in setup.** Whether `CR` is acceptable as a manifest `id`, in `map-set.json` and in `Lastbook-Map-CR.zip`, and,
   if provinces are wanted, whether hyphenated codes such as `CR-SJ` are.
2. **The box rule.** Whether the mainland box is the edge of a first build, whether the border or a band is the clip, and
   what happens to Isla del Coco (a second tiny box, or left out).
3. **One region, seven, or one plus a GAM grouping.** The whole country (proposed), seven provinces, or the country plus
   a `CR-GAM` grouping (its id and its canton list are the maintainers' and need confirming).
4. **Crop classes.** How ESA WorldCover's classes map to the orchard, vineyard and berry kinds, as REGIONS.md item 4.
5. **Address search.** Whether to ship without it (proposed), whether a landmark address can be supported at all, and
   how a five-digit district code is told apart from a US ZIP.
6. **Help points with no open source.** Health facilities, fire stations, CNE shelters, hazard layers. Who to ask, and
   whether OSM alone is enough for a first build.
7. **Official layers with no licence.** Whether to ask the IGN, CNE, OVSICORI and SINAC in writing for terms.
8. **The GAM polygon.** Whether to ask the INVU for the plan's polygon or build the grouping from COD-AB cantons.
9. **The California-only layers.** As REGIONS.md item 7.

## Trial build

The recommended box was built with #80's `tools/build_region_map.py` unchanged (commit `a453274`), from the Geofabrik
extract above. The full build record, checksums and screenshots are in [MAP-CR.md](MAP-CR.md); the figures that bear on
this proposal are here.

| | |
|---|---|
| Source | `costa-rica-latest.osm.pbf`, 39,192,879 bytes, MD5 `f046e22921a2e1837a3bde4e8c00e3a0` (matches Geofabrik's), OSM data up to 2026-11-17T21:24:30Z |
| Box | -86.11, 7.89, -82.40, 11.37 (the mainland box with margin) |
| Built on | 18 November 2026, Ubuntu 24.04, Python 3.12.3, pyosmium 4.3.2 |
| Time and memory | 25 seconds, 0.78 GB peak resident memory |
| Map set | 99,123,261 bytes: `national.sqlite` 95.3 MB, `places.sqlite` 3.7 MB |
| Same bytes twice | two builds gave identical SHA-256 for all five files |

What it holds: 163,431 roads (78,843 with a name or number), 202,360 building outlines, 15,221 rivers and streams,
28,892 land-use areas, 1,541 water areas, 516 wetlands, 356 beaches, 275 railway lines and 8,847 place labels. Help
points: 22,246 in 40 classes, among them 119 hospitals, 1,152 clinics, 424 doctors, 714 pharmacies, 690 police, 79 fire
stations, 441 fuel, 1,345 supermarkets, 2,442 convenience shops, 4,441 schools and 241 shelters. The place finder has
27,435 rows.

`tools/check_region_map.py` passed all file checks and, with `--engine` and every connection blocked, all engine checks:
tiles at zoom 10, 13 and 16 in San José, pins, nearest help, and place search for "Calderón Guardia", "Hospital
México", "Cartago" and "Liberia". The engine reports the map's extent as -85.91, 8.09, -82.54, 11.22, so the extract
added almost nothing from Nicaragua or Panama: the edge of a first build is in practice the border.

What the build shows for this proposal:

- **The whole country is small.** 25 seconds and 99 MB for all of it. Splitting by province buys nothing in size, which
  supports one `CR` region (item 3 above).
- **Shelters.** The 241 `shelter` points are what is left of `amenity=shelter` after #80 drops bus shelters: mostly
  lean-tos, picnic roofs and gazebos (see "Shelter" in OSM above). Shown as "Shelter" in an emergency map they promise
  more than they are. This is not Costa Rica's problem alone.
- **Isla del Coco is left out.** The box clip drops it, as proposed.
- **What still assumes the US** (seen in the interface, light and dark): the map opens over the United States and has a
  "US" button; the search box says "address, town or ZIP"; the wide view gives distances in miles; the credits line
  names USGS, USDA, NOAA, USACE, CDFW and CalGEM, none of whose data is in this map. These are the same points MAPS.md
  lists under "What is tied to the United States".

## What was checked

- Opened on 18 November 2026: Geofabrik's Costa Rica page (file sizes, data date) and `costa-rica.poly`; OCHA's COD-AB
  record for Costa Rica through HDX's API (licence, source, dates, files, caveats); Overture's addresses guide (41
  countries, no Costa Rica), places page (counts by source, none by country) and buildings page (sources, ODbL);
  Microsoft's GlobalMLBuildingFootprints README (CDLA Permissive 2.0, organisation by country and quadkey) and
  `dataset-links.csv`; the AWS open-data registry pages for Copernicus DEM GLO-30 and ESA WorldCover (licences);
  the ICJ's summary of the 2015 judgment; La Nación's 2009 postal code article and its 1997 column on addresses;
  Wikipedia's postal code page; the SNIT home page (rights line, no download); `datos.go.cr`; OVSICORI's home page (rights
  line); `engine/address_search.py` and `tools/build_addresses.py`.
- Downloaded and computed on 18 November 2026: OCHA's COD-AB GeoJSON (levels 0 and 1 for the boxes, with and without Isla
  del Coco; levels 0 to 3 for feature counts and areas); Geofabrik's `costa-rica-latest.osm.pbf` (the OSM counts);
  Microsoft's 21 Costa Rica tiles (row counts).
- Search only: ISO 3166-2:CR codes (general knowledge in the table, not searched), the 2018 ICJ judgment, the GAM plan's
  approval, decree numbers, canton and district counts and partial list, the TEC atlas, the CNE geoportal and its OGC
  services, OVSICORI report licences, SINAC's count of protected areas, IGN layers, the 2005 and 2012 address and street
  projects, the Wikipedia/La Nación postal code numbers (492 and 487).
- General knowledge, for a local reader to confirm: the official area of the country, West Virginia's area, where people
  live, who lives on Isla del Coco, which neighbours fall in the box, the border towns, the number of active volcanoes,
  the official language, forest cover.
- Not checked: the ISO site, Correos de Costa Rica's own pages and look-up, the MEP and Ministry of Health sites,
  `geoportal-saracc.cne.go.cr`, `www.cne.go.cr`, `www.sinac.go.cr`, the SNIT services list, OVSICORI's download pages, the
  INVU site, any Plan GAM polygon, how much neighbouring land the box or the extract holds, whether COD-AB's Colorado edge
  follows the 2018 line, the position of Microsoft's largest tile, Overture's Costa Rica share for buildings or places,
  the accuracy of Microsoft's footprints, and font coverage.
