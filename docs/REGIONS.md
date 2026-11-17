# Detailed maps outside the United States: a proposal

This is a proposal for discussion, not a decision. It answers, for three places, the questions
[MAPS.md](MAPS.md) asks before coverage can go beyond the United States: which open source replaces each federal list,
under what licence, what a "state" is there, and how addresses are written. The three places are Ontario and British
Columbia in Canada, and Guyana in South America.

Nothing here changes the app, the engine or a build. The machine-readable version is
[regions-proposed.json](regions-proposed.json). No code reads it, and it does not ship: builds package `web/` and
`content/` only. Everything below was checked on 16 November 2026 by opening the page named. Where something could not
be checked, it says so. It should wait for the maintainers' design issue before any code follows it.

## What a region is

A US state map is cut by `packaging/build_packs.py map <ST>` from the base map plus every row inside the state's box
(`derived/packs/pack-spec.json`, `map_sets.state`). The box comes from ZIP code (ZCTA) centroids, plus or minus 0.15
degrees. There are no ZCTAs outside the US, so the proposal takes each box from an official boundary instead, and keeps
the same 0.15 degree margin.

| Code | Name | Country | Level | Box (west, south, east, north) | Box with 0.15° margin | Box taken from |
|---|---|---|---|---|---|---|
| `CA-ON` | Ontario | Canada | province | -95.1537, 41.6766, -74.3201, 56.8594 | -95.31, 41.52, -74.17, 57.01 | Government of Ontario, "Province" layer (OGL – Ontario) |
| `CA-BC` | British Columbia | Canada | province | -139.0613, 48.2968, -114.0541, 60.0048 | -139.22, 48.14, -113.90, 60.16 | GeoBC, "Boundary Terrestrial" (OGL – British Columbia) |
| `GY` | Guyana | Guyana | country | -61.3939, 1.1714, -56.4808, 8.5576 | -61.55, 1.02, -56.33, 8.71 | OCHA, Guyana COD-AB level 0 (CC BY-IGO) |

- Ontario's boundary runs through the Great Lakes to the international line, so its south edge is in Lake Erie.
- British Columbia's box is the terrestrial boundary. The legal boundary is marked "Access Only" in the BC catalogue, so
  it is not cited; it agrees to 0.001° except that it reaches further south into the Juan de Fuca Strait.
- Guyana is small enough to be one region. Its box follows the boundary as Guyana administers it and as OCHA publishes
  it.

### Codes

US state maps use two-letter codes, and `CA` already means California: in `STATE_CODES` in
`engine/address_search.py`, in `NAMES` in `packaging/state_maps.py`, in `Lastbook-Map-CA.zip` and in
`derived/geo/addresses/CA.sqlite`. `ON`, `BC` and `GY` do not collide with any US code, but a bare `CA` for Canada would.
The proposal is ISO 3166-2 style codes: `CA-ON`, `CA-BC`, and `GY` for the whole country. The hyphen also keeps them
apart from US codes at a glance.

## Sources, layer by layer

Each map file a state map holds needs a replacement for its US source. "OGL" is an Open Government Licence.

### Ontario and British Columbia

| Layer (file) | US source today | Proposed for Canada | Publisher | Licence |
|---|---|---|---|---|
| Terrain (`terrain.sqlite`) | USGS 3DEP | Medium Resolution DEM (MRDEM), 30 m; High Resolution DEM (HRDEM) where lidar exists | Natural Resources Canada | OGL – Canada |
| Water (`water.sqlite`), Ontario | NHD, NID | Ontario Hydro Network (lines and polygons); Ontario Dam Inventory | Government of Ontario | OGL – Ontario |
| Water (`water.sqlite`), BC | NHD, NID | Freshwater Atlas (stream network, lakes); BC Dams | Government of British Columbia | OGL – British Columbia |
| Water, either province | | National Hydro Network (NHN), as a national alternative | Natural Resources Canada | OGL – Canada |
| Crops (`crops.sqlite`) | USDA Cropland Data Layer | Annual Crop Inventory, 30 m | Agriculture and Agri-Food Canada | OGL – Canada |
| Buildings (`buildings.sqlite`) | Microsoft US footprints, OSM heights | Open Database of Buildings; Microsoft Canadian Building Footprints to fill gaps; OSM heights | Statistics Canada; Microsoft; OSM contributors | OGL – Canada; ODbL; ODbL |
| Places (`places.sqlite`) | GNIS, Census gazetteers, OSM | Canadian Geographical Names (CGN); census boundary files; OSM named places | Natural Resources Canada; Statistics Canada; OSM contributors | OGL – Canada; OGL – Canada (see below); ODbL |
| Addresses (`addresses/<code>.sqlite`) | Overture addresses | Overture addresses (the Canadian rows are Statistics Canada's National Address Register); the Open Database of Addresses as an alternative | Overture Maps Foundation / Statistics Canada | Statistics Canada Open Licence; OGL – Canada |
| Points of interest (`poi` rows) | OSM | OSM; Open Database of Healthcare Facilities; Open Database of Educational Facilities | OSM contributors; Statistics Canada | ODbL; OGL – Canada |

Notes:

- MRDEM replaces the Canadian Digital Elevation Model (CDEM), which Natural Resources Canada says is no longer supported.
- The Annual Crop Inventory has its own class list. `tools/build_crops.py` keeps orchards, vineyards and berries from the
  Cropland Data Layer, so it would need a mapping from one list to the other.
- Microsoft's Canadian footprints repository was archived on 8 October 2026. The data is still there; it will not be
  updated.
- `tools/build_addresses.py` already reads Overture's address theme. For Canada it would need a different country filter,
  and the postcode and province handling described under "Still undecided".
- BC Geographical Names is marked "Access Only" in the BC catalogue, so it is not proposed. CGN covers British Columbia.
- The BC Address Geocoder is an online service, not a file, so it does not fit an offline build.

### Guyana

| Layer (file) | Proposed | Publisher | Licence |
|---|---|---|---|
| Terrain | Copernicus DEM GLO-30 | ESA / Airbus Defence and Space | Copernicus WorldDEM-30 licence (free and open, with fixed notices) |
| Water | OSM waterways and water areas | OSM contributors | ODbL |
| Crops | ESA WorldCover 2021, 10 m (land cover, not crop types) | ESA WorldCover consortium | CC BY 4.0 |
| Buildings | Microsoft Global ML Building Footprints; Overture buildings as an alternative | Microsoft; Overture Maps Foundation | CDLA Permissive 2.0 (see below); ODbL |
| Places | OSM named places; OCHA COD-AB regions (10) and sub-regions (27) | OSM contributors; OCHA | ODbL; CC BY-IGO |
| Addresses | none found | | |
| Points of interest | OSM; Overture places as a supplement | OSM contributors; Overture Maps Foundation | ODbL; mostly CDLA Permissive 2.0 |

Notes:

- Copernicus GLO-30 is a surface model. In forest, relief and contour lines will follow the tree canopy, not the ground.
- There is no open crop-type map or dam inventory for Guyana that we found. WorldCover shows cropland, tree cover,
  mangroves and so on, which is less than the crop layer shows in the US.
- HydroRIVERS (HydroSHEDS) has consistent river lines but is not proposed: its licence forbids distributing it on its
  own, requires an end-user licence at least as protective, can be ended by WWF at its discretion, and asks the licensee
  to keep records of end users. That does not suit a free library people copy for each other.
- Microsoft's Global ML Building Footprints lists 34 tiles for Guyana. Its README says CDLA Permissive 2.0; Overture's
  attribution page lists the same dataset under ODbL. Which one applies should be confirmed before a build.
- No open address points were found. Overture's list of address sources has no entry for Guyana, and the coverage of
  OSM `addr:*` tags there was not measured.

## Licence notes and attribution

All the proposed licences allow redistribution, including in a free offline library. What each asks in return:

- **OGL – Canada, OGL – Ontario, OGL – British Columbia.** Give the provider's attribution statement and, where
  possible, link the licence. Where several providers make that impractical, each licence gives a fixed sentence, such
  as "Contains information licensed under the Open Government Licence – Canada." The BC licence applies only to
  catalogue records that name it, so each BC source has to be checked one by one, as was done for the four here.
- **Statistics Canada Open Licence.** For adapted data: "Adapted from Statistics Canada, *product*, *reference date*.
  This does not constitute an endorsement by Statistics Canada of this product." Overture lists the National Address
  Register under this licence; the open.canada.ca record for the same register lists OGL – Canada. Both are permissive;
  the sentence to show differs.
- **ODbL** (OpenStreetMap, Microsoft's Canadian footprints, Overture buildings). Credit "© OpenStreetMap contributors",
  say the data is under the ODbL, and offer a database built from it under the ODbL too. The US map already carries
  ODbL data, so this is not new.
- **Copernicus WorldDEM-30.** A modified copy must say "produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and
  © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights
  reserved", and anyone who passes it on must also carry "The organisations in charge of the Copernicus programme by
  law or by delegation do not incur any liability for any use of the Copernicus WorldDEM-30", and pass both duties on.
- **CC BY 4.0** (ESA WorldCover). On a map: "© ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data
  (2021) processed by ESA WorldCover consortium".
- **CC BY-IGO** (OCHA boundaries). Credit OCHA and its source.

These notices would belong wherever the map already credits its sources, and in `THIRD_PARTY_NOTICES.md` if that is
where the maintainers keep data licences.

## How addresses are written

- **Canada.** A civic number and street, then the municipality, the province abbreviation and the postal code on the last
  line. The postal code has six characters in the form `A1A 1A1`: letter, digit, letter, a space, digit, letter, digit,
  in capitals with no hyphen. Ontario codes begin with K, L, M, N or P; British Columbia codes begin with V (Canada
  Post). French street types such as *rue* and *chemin* also occur.
- **Guyana.** Guyana now has postcodes: seven digits, giving region, locality, district, post office and sub-locality
  (Guyana Post Office Corporation, and the UPU addressing sheet of August 2025). Many address guides elsewhere still say
  Guyana has none; they are out of date. How widely the codes are used day to day is not known. UPU examples write a lot
  or premises and road, a village or sub-locality, a locality such as "East Coast Demerara", and the code on its own line.

## Still undecided

Each of these needs the maintainers' decision before any code changes:

1. **Codes and names in setup.** How setup's map picker lists places that are not US states: one list or grouped by
   country, and whether a hyphenated code is acceptable as a manifest `id`, as `map-set.json`'s `name`, in
   `state.current.map` and in the zip name `Lastbook-Map-<id>.zip`.
2. **The box rule.** Whether a box from an official boundary may stand in for ZCTA centroids, and whether 0.15 degrees
   is still the right margin for a whole country such as Guyana.
3. **Address search.** `engine/address_search.py` knows US state names and codes only, reads a postcode only as five
   digits, and picks index files by a two-letter stem. `tools/build_addresses.py` keeps only `country = 'US'`, cuts
   postcodes to five characters (a Canadian `K2G 0P7` would become `K2G 0`) and keeps two letters of the region. Each
   would need a change for Canadian and Guyanese addresses, and the street words would need French forms.
4. **Crop classes.** Which Annual Crop Inventory classes map to the orchard, vineyard and berry kinds, and whether
   Guyana gets a land-cover layer at all.
5. **Licences in the app.** Where the extra attribution sentences are shown.
6. **Boundaries in dispute.** Whether Lastbook says anything on the map where a boundary is claimed by a neighbour.
7. **The California-only layers.** The fish, boating and well layers are labelled California in `web/map.js`; they would
   stay empty outside it.

## What was checked

- Every licence and dataset page in the tables was opened on 16 November 2026, through the page itself or the
  catalogue's own record for it (open.canada.ca and the BC Data Catalogue). The exact URLs are in
  [regions-proposed.json](regions-proposed.json).
- The boxes were computed from the boundary data itself, as described in the JSON for each region.
- Not checked: the 2021 Statistics Canada boundary files (the download page refused the build machine), the CDLA
  Permissive 2.0 and CC BY-IGO licence texts themselves, the Copernicus DEM collection page (its licence was read in
  full), and the ISO 3166-2 codes against the ISO site.
