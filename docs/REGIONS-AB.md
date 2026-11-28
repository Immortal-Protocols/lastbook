# Detailed maps for Alberta: a proposal

This is a proposal for discussion, not a decision. It answers, for Alberta, the questions [MAPS.md](MAPS.md) asks before coverage can go beyond the United States: which open source replaces each federal list, under what licence, what a “state” is there, and how addresses are written. Alberta is a Canadian province.

Nothing here changes the app, the engine or a build. A machine-readable version could live alongside [regions-proposed.json](regions-proposed.json). No code reads it, and it does not ship: builds package `web/` and `content/` only. Everything below was checked on 27 November 2026 by opening the page named or computing from the published boundary. Where something could not be checked, it says so. It should wait for the maintainers’ design issue before any code follows it.

## What a region is

A US state map is cut by `packaging/build_packs.py map <ST>` from the base map plus every row inside the state’s box (`derived/packs/pack-spec.json`, `map_sets.state`). The box comes from ZIP code (ZCTA) centroids, plus or minus 0.15 degrees. There are no ZCTAs outside the US, so the proposal takes the box from an official boundary instead, and keeps the same 0.15 degree margin.

| Code | Name | Country | Level | Box (west, south, east, north) | Box with 0.15° margin | Box taken from |
|---|---|---|---|---|---|---|
| `CA-AB` | Alberta | Canada | province | -120.0014, 48.9967, -110.0048, 60.0005 | -120.16, 48.84, -109.85, 60.16 | Government of Alberta, Alberta Provincial Boundary ATS v4.1 (Open Government Licence – Alberta) |

- The box was computed from the official ATS v4.1 polygon on the Government of Alberta feature service (layer “ATS v4_1 Alberta Provincial Boundary”), queried in WGS84 on 27 November 2026 (item `gda-ac2c86a0-e7d5-4e90-9e5b-f8a32b957563` on [open.alberta.ca](https://open.alberta.ca/dataset/gda-ac2c86a0-e7d5-4e90-9e5b-f8a32b957563); [metadata](https://geodiscover.alberta.ca/geoportal/rest/metadata/item/d14db2d35397413b96710e0699acaf3d/html); [feature service](https://geospatial.alberta.ca/titan/rest/services/boundary/goa_administrative_area/MapServer)). The south edge is the international boundary with the United States, near the 49th parallel (southernmost vertex 48.9967°). The north edge is at the 60th parallel. The west edge follows the British Columbia boundary; the east edge follows the Saskatchewan boundary, near 110°W.

### Codes

US state maps use two-letter codes, and `CA` already means California: in `STATE_CODES` in `engine/address_search.py`, in `NAMES` in `packaging/state_maps.py`, in `Lastbook-Map-CA.zip` and in `derived/geo/addresses/CA.sqlite`. A bare `AB` does not collide with any US code, but the proposal uses the ISO 3166-2 style code `CA-AB` for consistency with the codes already proposed for Ontario (`CA-ON`), British Columbia (`CA-BC`) and Manitoba (`CA-MB`). The hyphen keeps it apart from US codes at a glance.

## Sources, layer by layer

Each map file a state map holds needs a replacement for its US source. “OGL” is an Open Government Licence.

### Alberta

| Layer (file) | US source today | Proposed for Alberta | Publisher | Licence |
|---|---|---|---|---|
| Terrain (`terrain.sqlite`) | USGS 3DEP | Medium Resolution DEM (MRDEM), 30 m; High Resolution DEM (HRDEM) where lidar exists | Natural Resources Canada | OGL – Canada |
| Water (`water.sqlite`) | NHD, NID | National Hydro Network (NHN); Alberta Base Features hydrography (streams, waterbodies, and hydrography point events including dams) | Natural Resources Canada; Government of Alberta | OGL – Canada; OGL – Alberta |
| Crops (`crops.sqlite`) | USDA Cropland Data Layer | Annual Crop Inventory, 30 m | Agriculture and Agri-Food Canada | OGL – Canada |
| Buildings (`buildings.sqlite`) | Microsoft US footprints, OSM heights | Open Database of Buildings; Microsoft Canadian Building Footprints to fill gaps; OSM heights | Statistics Canada; Microsoft; OSM contributors | OGL – Canada; ODbL; ODbL |
| Places (`places.sqlite`) | GNIS, Census gazetteers, OSM | Canadian Geographical Names (CGN); census boundary files; OSM named places | Natural Resources Canada; Statistics Canada; OSM contributors | OGL – Canada; OGL – Canada; ODbL |
| Addresses (`addresses/CA-AB.sqlite`) | Overture addresses | Overture addresses (including Statistics Canada’s National Address Register); the Open Database of Addresses as an alternative | Overture Maps Foundation / Statistics Canada | Statistics Canada Open Licence; OGL – Canada |
| Points of interest (`poi` rows) | OSM | OSM; Open Database of Healthcare Facilities; Open Database of Educational Facilities | OSM contributors; Statistics Canada | ODbL; OGL – Canada |

Notes:

- MRDEM replaces the Canadian Digital Elevation Model (CDEM), which Natural Resources Canada says is no longer supported. The same source is proposed for Ontario, British Columbia and Manitoba. NRCan states that MRDEM is in part produced from Copernicus WorldDEM-30, so the Copernicus notice is carried too.
- The National Hydro Network remains the national fallback, as for the other Canadian provinces. Alberta Base Features hydrography — Base Stream and Flow Representation (SLNET), Base Hydrography Point Event (tagged for dams and water-control devices), and the Base Waterbody polygons described on the official `base_water_feature` map service — is listed under OGL – Alberta for the whole-province envelope. No separate catalogue record for those waterbody polygons (as opposed to the 2010 polygon *arcs*) was found; the 2025 “Update” waterbody and stream records cover only central and southern Alberta. A downloadable GIS dam inventory was not found (the [2020 inventory](https://open.alberta.ca/publications/inventory-of-regulated-dam-projects) is a PDF fact sheet; the [Dam Safety Map](https://damsafetymap.alberta.ca/) is a web app). Completeness of the Point Event dam tags was not checked.
- The Annual Crop Inventory has its own class list. `tools/build_crops.py` keeps orchards, vineyards and berries from the Cropland Data Layer, so it would need a mapping from one list to the other (same issue as for Ontario, British Columbia and Manitoba).
- Microsoft’s Canadian footprints repository was archived on 8 October 2026. The data is still there under the ODbL; it will not be updated.
- `tools/build_addresses.py` already reads Overture’s address theme. For Alberta it would need the Canadian country filter and postcode/province handling described under “Still undecided.”
- No Alberta-only address geocoder that publishes a downloadable file was found; Overture + the Open Database of Addresses are the proposed offline sources. No Alberta-only geographical-names GIS file with a confirmed open download was found either; CGN is the national names source and covers Alberta.

## Licence notes and attribution

All the proposed licences allow redistribution, including in a free offline library. What each asks in return:

- **OGL – Canada** ([licence](https://open.canada.ca/en/open-government-licence-canada)). Give the provider’s attribution statement and, where possible, link the licence. Where several providers make that impractical, the licence gives a fixed sentence, such as “Contains information licensed under the Open Government Licence – Canada.”
- **OGL – Alberta** ([licence](https://open.alberta.ca/licence), version 2.2). The same rule, with the fixed sentence “Contains information licensed under the Open Government Licence – Alberta.” The licence does not grant use of names, crests, logos or other official symbols.
- **Statistics Canada Open Licence** ([licence](https://www.statcan.gc.ca/en/terms-conditions/open-licence)). For adapted data: “Adapted from Statistics Canada, *product*, *reference date*. This does not constitute an endorsement by Statistics Canada of this product.”
- **ODbL** (OpenStreetMap, Microsoft’s Canadian footprints, Overture buildings). Credit “© OpenStreetMap contributors”, say the data is under the ODbL, and offer a database built from it under the ODbL too. The US map already carries ODbL data, so this is not new.
- **Copernicus WorldDEM-30**, for the part of MRDEM produced from it: a modified copy must say “produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved”, and anyone who passes it on must also carry “The organisations in charge of the Copernicus programme by law or by delegation do not incur any liability for any use of the Copernicus WorldDEM-30”, and pass both duties on.

These notices would belong wherever the map already credits its sources, and in `THIRD_PARTY_NOTICES.md` if that is where the maintainers keep data licences.

## How addresses are written

- **Canada (Alberta).** A civic number and street, then the municipality, the province abbreviation and the postal code on the last line. The postal code has six characters in the form `A1A 1A1`: letter, digit, letter, a space, digit, letter, digit, in capitals with no hyphen. Alberta codes begin with T (Canada Post). French street types such as *rue* and *chemin* also occur, though less frequently than in Quebec or parts of Ontario.

## Still undecided

Each of these needs the maintainers’ decision before any code changes (the same list as in the Manitoba proposal):

1. **Codes and names in setup.** How setup’s map picker lists places that are not US states: one list or grouped by country, and whether a hyphenated code is acceptable as a manifest `id`, as `map-set.json`’s `name`, in `state.current.map` and in the zip name `Lastbook-Map-<id>.zip`.
2. **The box rule.** Whether a box from an official boundary may stand in for ZCTA centroids, and whether 0.15 degrees is still the right margin.
3. **Address search.** `engine/address_search.py` knows US state names and codes only, reads a postcode only as five digits, and picks index files by a two-letter stem. `tools/build_addresses.py` keeps only `country = 'US'`, cuts postcodes to five characters (a Canadian `T5K 2J6` would become `T5K 2`) and keeps two letters of the region. Each would need a change for Canadian addresses, and the street words would need French forms.
4. **Crop classes.** Which Annual Crop Inventory classes map to the orchard, vineyard and berry kinds.
5. **Licences in the app.** Where the extra attribution sentences are shown.
6. **Boundaries in dispute.** Whether Lastbook says anything on the map where a boundary is claimed by a neighbour. (Alberta’s boundaries are not disputed.)
7. **The California-only layers.** The fish, boating and well layers are labelled California in `web/map.js`; they would stay empty outside it.

## What was checked

- The Alberta Provincial Boundary ATS v4.1 polygon was read from the Government of Alberta feature service in WGS84 on 27 November 2026, and the bounding box computed from it. The catalogue record, metadata page and OGL – Alberta licence (version 2.2) were opened the same day.
- Licence and dataset pages for the national sources in the table, [Overture’s attribution page](https://docs.overturemaps.org/attribution/), Microsoft’s Canadian Building Footprints (archived; ODbL), the Alberta hydrography records named above, the 2020 dam-inventory fact sheet, the `base_water_feature` map service, and Canada Post’s addressing guidelines were opened or confirmed from the catalogue record on 27 November 2026. The Ontario / British Columbia / Guyana proposal is [REGIONS.md](REGIONS.md). The Manitoba proposal, which this document follows, is [REGIONS-MB.md](REGIONS-MB.md).
- Not checked: completeness of dam points in Base Hydrography Point Event against the 2020 regulated-dam list; the individual municipal licences compiled into the Open Database of Buildings; and the current (non-archived) detail pages for later versions of the educational and healthcare open databases. The educational-facilities page opened on this date is marked archived; both that page and the healthcare-facilities page name OGL – Canada.
