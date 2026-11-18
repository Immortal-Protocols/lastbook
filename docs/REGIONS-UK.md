# Detailed maps for the United Kingdom: a proposal

This is a proposal for discussion, not a decision. It answers, for the United Kingdom, the questions [MAPS.md](MAPS.md) asks
before coverage can go beyond the United States: which open source replaces each US list, under what licence, what a
"state" is there, and how addresses are written. It follows the shape of [REGIONS.md](REGIONS.md),
[REGIONS-DE.md](REGIONS-DE.md) and [REGIONS-AR.md](REGIONS-AR.md) and is meant to feed the same design discussion
(issues #23, #25 and #31). The machine-readable version is [regions-uk-proposed.json](regions-uk-proposed.json).

Nothing here changes the app, the engine or a build. No code reads the JSON, and nothing here ships: builds package
`web/` and `content/` only.

**How things were checked.** Research was done on 17 November 2026 with AI research agents reading the publishers' own
pages. **A person has not yet reviewed it.** Each source carries one of three marks:

- **opened**: the dataset or licence page itself was fetched and read;
- **search only**: the fact was seen in a search result, not on the publisher's page;
- **not checked**: the page could not be reached or read (several returned 403 or 404); the row says what is missing.

One limit applies to every "opened": the fetch tool returns a summary of a page, not its exact text. Licence clauses
need to be read in full before anyone relies on them. Several publisher pages (the National Archives, Royal Mail, the
ISO site, OpenDataNI, the Environment Agency's data portal) refused or rendered empty, so a fair number of rows are
"search only" or "not checked".

## Why the UK is a different case

For Germany the question was which of 16 state sources to use. For the UK it is nearly the opposite: two national
bodies, Ordnance Survey (OS) and the Office for National Statistics (ONS), publish open products that cover **Great
Britain** in one piece: places, postcodes, rivers, terrain and buildings. The gaps are elsewhere:

- **Northern Ireland** is outside most of them. OS products are Great Britain only, and the ONS postcode file carries a
  separate licence condition for Northern Ireland postcodes.
- **Addresses.** No open UK dataset with address text and coordinates was found. This is the biggest difference from the
  US, where Overture supplies addresses.
- **Terrain** is either coarser than the US source (OS Terrain 50, 50 m) or a surface model (Copernicus GLO-30). The South
  West pilot used GLO-30.
- **Crops.** No open source with orchard, vineyard or berry classes was confirmed. The South West pilot used OSM
  `landuse=orchard` and `landuse=vineyard` instead, which has no crop types and no berries.

## What a region is

The proposal is one region per **ONS ITL1 region** (formerly NUTS 1): nine in England plus Wales, Scotland and Northern
Ireland, 12 in all. That is the closest match to a US state in size. Geofabrik's extracts show why England should not
be one region: England is 1.6 GB of OSM data, Scotland 314 MB and Wales 144 MB. The alternative, four regions (the
nations), is a decision for the maintainers (see "Still undecided").

### Codes

ISO 3166-2:GB gives the three non-English nations and England their codes: `GB-ENG`, `GB-SCT`, `GB-WLS` and
`GB-NIR` (seen on Wikipedia; the ISO page refused the fetch). ISO has no code for the nine English regions at this level,
so those are **invented here** and flagged as such. ONS's own ITL1 codes (`TLC` to `TLN`) are the alternative.

| Code | ITL1 | ONS key | Name |
|---|---|---|---|
| `GB-NE` | TLC | E12000001 | North East |
| `GB-NW` | TLD | E12000002 | North West |
| `GB-YH` | TLE | E12000003 | Yorkshire and The Humber |
| `GB-EM` | TLF | E12000004 | East Midlands |
| `GB-WM` | TLG | E12000005 | West Midlands |
| `GB-EE` | TLH | E12000006 | East of England (ONS's ITL1 list calls it "East") |
| `GB-LON` | TLI | E12000007 | London |
| `GB-SE` | TLJ | E12000008 | South East |
| `GB-SW` | TLK | E12000009 | South West |
| `GB-WLS` | TLL | W92000004 | Wales |
| `GB-SCT` | TLM | S92000003 | Scotland |
| `GB-NIR` | TLN | N92000002 | Northern Ireland |

- A hyphenated code is needed, and none fits today. Address index ids (`engine/setup/manifest.py:72`), installed index and
  map-set files (`engine/setup/install.py:267`) and the map build (`packaging/build_packs.py:1471`) each accept only two
  capital letters (checked in this repository on 17 November 2026), so a code of the form `GB-XXX` would be refused. The
  same is true of `DE-BY` in REGIONS-DE.md. A bare `GB` would pass those checks and is not a US code, but it cannot tell 12
  regions apart.
- **One part after the hyphen collides with a US state:** `GB-NE` ends in `NE`, which is Nebraska in `STATE_CODES`
  (`engine/address_search.py`). The other eleven (`NW`, `YH`, `EM`, `WM`, `EE`, `LON`, `SE`, `SW`, `WLS`, `SCT`, `NIR`)
  are not US codes. If the part after the hyphen is ever read on its own, `GB-NE` needs a different spelling, or ONS's
  `TLC` codes could be used instead.

### Overlaps

- **London inside the South East.** The `GB-LON` box lies wholly inside the `GB-SE` box, as Berlin lies inside
  Brandenburg in REGIONS-DE.md. A South East map would show London's streets and help points without any extra rule.
  Address search reads one index per region, so a `GB-SE` map would find London's streets but not its addresses unless
  the index is cut by box.
- **Other boxes overlap their neighbours**, as US state boxes do; for example the `GB-WLS` box reaches into Bristol and
  Shrewsbury, and the `GB-NIR` box takes in border counties of the Republic of Ireland. A Northern Ireland map would
  therefore show part of the Republic; the map should say so plainly.
- **Islands.** Shetland is in `GB-SCT`, St Kilda too, the Isles of Scilly in `GB-SW` and the Isle of Wight in `GB-SE`.
  The Isle of Man, Jersey and Guernsey are Crown Dependencies, not part of the UK, and are not proposed.

### Related proposals

Two other proposals in this folder cover part of the same ground. This document has not been reconciled with them; it
only says where they meet. Both were read for this note, not checked against their sources.

- **[REGIONS-GB-LONDON.md](REGIONS-GB-LONDON.md)** proposes Greater London alone, under the same code, `GB-LON`, and from
  the same ONS "London" row (Regions December 2024). Its box is the service's extent-only answer, `-0.5160, 51.2788,
  0.3414, 51.6976`; this document's is the minimum and maximum of every vertex, `-0.5102, 51.2868, 0.3340, 51.6919`.
  With the 0.15° margin the two differ by 0.01° in the south (51.12 and 51.13) and the east (0.50 and 0.49). Its own
  text says the rest of the United Kingdom is left for a later proposal, which is this one. If both are accepted, one
  box for `GB-LON` has to be chosen.
- **[REGIONS-IE.md](REGIONS-IE.md)** proposes one region for the whole island of Ireland, Northern Ireland included
  (named "Ireland and Northern Ireland", no code chosen). This document proposes Northern Ireland as `GB-NIR`, one of 12.
  Both take Northern Ireland's east edge, -5.4328°, from the same ONS layer. If both are accepted, Northern Ireland would
  be in two map sets, as REGIONS-IE.md already notes for another overlap, and the maintainers would have to say which
  one setup offers.

### Boxes

The boxes were computed from the ONS **Regions (December 2024) Boundaries EN BGC** (the nine English regions) and
**Countries (December 2024) Boundaries UK BGC** (Wales, Scotland, Northern Ireland), both read from ONS's ArcGIS feature
services on 17 November 2026 with the geometry requested in WGS 84 (EPSG:4326), so the service transformed every vertex
from the British National Grid. The minimum and maximum of all vertices give the box. Each box was then widened by 0.15°
and rounded outward to 0.01°, the same margin `map_sets.state` uses for US states.

Two cautions: "BGC" is ONS's generalised, coastline-clipped version of the boundaries; the layers' own metadata pages
were not opened, and the expansion of "BGC" is from background knowledge. A full-resolution boundary could move an edge by
a small amount, which the 0.15° margin absorbs. The first attempt used the services' extent-only query, which returns
the box of the *projected* rectangle and over-covers in the far west (it put Scotland's west edge at -9.23° instead of
-8.65°); it was discarded.

| Code | ONS key | Name | Box (west, south, east, north) | Box with 0.15° margin |
|---|---|---|---|---|
| `GB-NE` | E12000001 | North East | -2.6898, 54.4511, -0.7886, 55.8111 | -2.84, 54.30, -0.63, 55.97 |
| `GB-NW` | E12000002 | North West | -3.6398, 52.9472, -1.9096, 55.1890 | -3.79, 52.79, -1.75, 55.34 |
| `GB-YH` | E12000003 | Yorkshire and The Humber | -2.5647, 53.3016, 0.1469, 54.5602 | -2.72, 53.15, 0.30, 54.72 |
| `GB-EM` | E12000004 | East Midlands | -2.0341, 51.9773, 0.3556, 53.6164 | -2.19, 51.82, 0.51, 53.77 |
| `GB-WM` | E12000005 | West Midlands | -3.2356, 51.8261, -1.1721, 53.2262 | -3.39, 51.67, -1.02, 53.38 |
| `GB-EE` | E12000006 | East of England | -0.7457, 51.4511, 1.7637, 52.9879 | -0.90, 51.30, 1.92, 53.14 |
| `GB-LON` | E12000007 | London | -0.5102, 51.2868, 0.3340, 51.6919 | -0.67, 51.13, 0.49, 51.85 |
| `GB-SE` | E12000008 | South East | -1.9572, 50.5749, 1.4496, 52.1964 | -2.11, 50.42, 1.60, 52.35 |
| `GB-SW` | E12000009 | South West | -6.4187, 49.8648, -1.4856, 52.1126 | -6.57, 49.71, -1.33, 52.27 |
| `GB-WLS` | W92000004 | Wales | -5.6691, 51.3750, -2.6499, 53.4357 | -5.82, 51.22, -2.49, 53.59 |
| `GB-SCT` | S92000003 | Scotland | -8.6500, 54.6333, -0.7246, 60.8608 | -8.80, 54.48, -0.57, 61.02 |
| `GB-NIR` | N92000002 | Northern Ireland | -8.1775, 54.0228, -5.4328, 55.3129 | -8.33, 53.87, -5.28, 55.47 |

## Sources, layer by layer

### Nationwide

| Layer (file) | US source today | Proposed for the UK | Publisher | Licence | Checked |
|---|---|---|---|---|---|
| Terrain (`terrain.sqlite`) | USGS 3DEP, 1 arc-second | Copernicus DEM GLO-30, one source for the whole UK including Northern Ireland, resampled as needed; OS Terrain 50 (GB, 50 m) as a bare-earth cross-check | ESA / Airbus; OS | Copernicus licence as in REGIONS.md; OS OpenData (see licence notes) | both pages opened; GLO-30 tile completeness for the UK not checked |
| Water (`water.sqlite`) | NHD | OSM waterways and water areas from Geofabrik's United Kingdom extract; OS Open Rivers (GB) as a cross-check | OSM contributors; OS | ODbL; OS OpenData | Geofabrik and OS pages opened |
| Dams | NID | OSM `waterway=dam` and reservoir areas; the NERC/UKCEH list of 273 reservoirs (90 % of UK storage) as a cross-check | OSM contributors; NERC | ODbL; OGL | both opened; the list is from 2018 |
| Crops (`crops.sqlite`) | USDA Cropland Data Layer | **No open crop map confirmed**; see notes. South West pilot: OSM `landuse=orchard` and `landuse=vineyard` areas, drawn as an overlay with a record per area (no crop type, no berries) | OSM contributors | ODbL | CROME and UKCEH opened; OSM landuse tried in the pilot |
| Buildings (`buildings.sqlite`) | Microsoft US footprints, OSM heights | OSM buildings, or Microsoft's footprints taken directly; OS OpenMap - Local (GB, generalised) as an alternative | OSM contributors; Microsoft; OS | ODbL; CDLA Permissive 2.0; OS OpenData | all opened; UK coverage by source not measured |
| Places (`places.sqlite`) | GNIS, Census gazetteers, OSM | OS Open Names (settlements, roads, postcode points; GB only); OSM named places for Northern Ireland | OS; OSM contributors | OS OpenData (OGL claimed, see notes); ODbL | Open Names opened |
| Postcodes | Census ZIP code areas | Code-Point Open (GB, about 1.7 million postcodes); Northern Ireland **unresolved** | OS; ONS | OS OpenData plus a Royal Mail notice | opened |
| Addresses (`addresses/<code>.sqlite`) | Overture addresses | **No open address text found.** Proposed instead: postcode and road-name search from Open Names and Code-Point Open, plus OSM `addr:*` where mapped | OS; OSM contributors | see above; ODbL | see notes |
| Points of interest (`poi` rows) | OSM | OSM, as today | OSM contributors | ODbL | taginfo counts read |

**Terrain.** The US map uses USGS 3DEP at 1 arc-second, about 30 m. OS Terrain 50 is 50 m on a 10 km tile grid, updated
each July, with a 162 MB grid download (opened; it excludes Northern Ireland). Copernicus GLO-30 is 30 m and global, a
surface model that includes buildings and trees (opened, vertical accuracy below 4 m at 90 %), with the same
canopy-and-roofs caveat REGIONS-DE.md describes; the AWS page says some countries' tiles are unreleased, and whether the
UK's are complete was not checked. Bare-earth laser-scan models at 1 m or better exist for England (Environment Agency
National LIDAR Programme: 302 survey blocks, 2017 to 2023, 1 m, OGL, per-tile download), Scotland (Phase 6: 0.5 m, OGL;
whether all Scotland is covered across phases was not checked), and Wales (Welsh Government tile catalogue 2020 to 2023,
1 m, no login; licence wording not shown on its page). **Northern Ireland has no confirmed national open DTM**: the 50 m
model's OpenDataNI page refused the fetch, and the one LiDAR set opened covers about 130 km² across 39 sites. Using four
nations' lidar would also mean four downloads, four licences and an unconfirmed Northern Ireland; GLO-30 avoids that.

**Water.** Geofabrik's `united-kingdom-latest.osm.pbf` is 2.1 GB (the dated file of 16 November 2026 is 2,287,716,144
bytes) and includes Northern Ireland. The `great-britain` file excludes it. There is no separate Northern Ireland
extract; the `ireland-and-northern-ireland` file (398 MB) includes the whole of Ireland. OS Open Rivers (opened) is
GB only, 52 MB as GeoPackage, updated each April and October. No current official Environment Agency reservoir register
was found; a search summary says one was released under the OGL in 2023 (not confirmed). Scottish Water's data was not
checked.

**Crops.** `tools/build_crops.py` keeps orchards, vineyards and berries. Nothing open and UK-wide was found:

- The Rural Payments Agency's Crop Map of England (CROME, 2024) is under the OGL on data.gov.uk (its CKAN mirror says "no
  licence provided") but covers England only, and the 2022 class lookup lists strawberry, tomato, "perennial crops and
  isolated trees" and "nursery crops" but **no orchard or vineyard class**.
- The UKCEH Land Cover Map 2023 is **not open**: its licence (opened) allows non-commercial use only, forbids putting the
  data on any internet site or passing it to third parties, and needs a reseller agreement for commercial use.
- Scotland's 2019 crop map page (opened) names no fruit class and no download; Wales was not checked; no Northern
  Ireland crop map was found.
- OSM `landuse=orchard` and `landuse=vineyard` were tried in the South West pilot (see "The South West pilot" below): 3,128
  orchards and 236 vineyards, with no crop type and no berries, and only what volunteers have mapped.

**Buildings.** Overture's buildings theme is under the ODbL because it includes OSM; it lists Microsoft footprints under
the ODbL too. Microsoft's own repository says CDLA Permissive 2.0 and lists a 2023 update with 7.6 million UK
footprints. That is the same licence question REGIONS.md raises for Guyana and REGIONS-DE.md for Germany: take
Microsoft's data directly or through Overture, not both. OS OpenMap - Local (opened) is GB only, 1:10,000, generalised
buildings from OS MasterMap; the GB GeoPackage is 3.5 GB.

**Places and postcodes.** OS Open Names (opened) is GB only: settlements, named and numbered roads, and postcodes as
points, with some Welsh and Gaelic names. The CSV is 103 MB, the GeoPackage 210 MB, the current version is 2026-10, and
OS updates it every three months. Code-Point Open (opened) has about 1.7 million postcodes, is Great Britain only
(**Northern Ireland is not included**), updates each February, May, August and November, and is 14.5 MB as CSV. Whether
it carries coordinates and in which reference system was not read from the technical specification. GeoNames offers a GB
postcode file (14 MB) under CC BY 4.0 that still carries a Royal Mail notice, so it is no easier on licensing. The ONS
Postcode Directory (opened through the data.gov.uk mirror) includes Northern Ireland, but ONS's licence page says
commercial use of Northern Ireland (BT) postcodes needs a separate licence from Land and Property Services, so it cannot
be assumed redistributable inside the app.

**Addresses.** What was found, all opened unless marked:

- **Overture** carries over 475 million addresses in 41 countries; the United Kingdom is not in its country list, and no
  UK source appears on its attribution page.
- **OS Open UPRN** is about 40 million coordinates with no address text on any page read (GB only, 620 MB as CSV).
- **OS AddressBase and Royal Mail's PAF** are licensed products, not open (PAF's own page says organisations must license
  it; AddressBase reaches end of life in autumn 2027, per OS).
- **Northern Ireland's Pointer** is licensed for a fee (Finance NI's page gives no terms; search results show a price).
- **OpenAddresses**: no GB listing could be read; the OSM wiki calls the "Open Addresses UK" project dead (search only).
- **Council Tax address lists** that councils released under the OGL are in a legal dispute. A directory page (datadaptive.com)
  quotes a legal email of 8 May 2026 from OS and GeoPlace saying the data contains OS, GeoPlace and Royal Mail rights and
  cannot be used without consent, after which many download links were removed. Not proposed.
- **OSM `addr:*`**: tagged under the Royal Mail model (premises, thoroughfare, locality, postcode); the wiki says locality
  tags are often missing. No completeness figure was found.

So the realistic UK search is: a postcode finds its point (Code-Point Open, Great Britain); a road name finds its place
(Open Names); a house number plus street is found only where OSM has it. An honest map says "address not found" rather than
guessing, as the US search already does.

**Not open, and so not proposed:** OS AddressBase, Royal Mail PAF, Northern Ireland's Pointer, the UKCEH Land Cover Map, and the British Heart Foundation's defibrillator register (its terms forbid use "for
the creation of an app or other service" without written consent).

## Help points

OSM is the practical source across the UK. Counts are from the Geofabrik taginfo instance for the **Great Britain**
extract (England, Scotland and Wales; Northern Ireland is not in it), opened on 17 November 2026; the extract date was
not shown. Each count is every OSM object, nodes, ways and relations together, and ways and relations need a centre point
to plot as pins.

| Tag | Count in Great Britain | Nodes / ways / relations | Notes |
|---|---|---|---|
| `amenity=pharmacy` | 9,129 | 6,520 / 2,601 / 8 | |
| `amenity=fire_station` | 2,041 | 283 / 1,754 / 4 | mostly areas; needs one pin per station |
| `amenity=police` | 1,793 | 575 / 1,179 / 39 | |
| `amenity=hospital` | 1,797 | 230 / 1,476 / 91 | |
| `amenity=doctors` | 6,786 | 2,517 / 4,158 / 111 | |
| `amenity=drinking_water` | 2,434 | 2,431 / 3 / 0 | |
| `man_made=water_well` | 1,291 | 1,164 / 127 / 0 | likely includes historic or decorative wells; check tags before treating as water |
| `emergency=water_tank` | 116 | 7 / 108 / 1 | too sparse to be a useful UK layer |
| `emergency=defibrillator` | 23,034 | 23,031 / 3 / 0 | about 13 % of the global count |
| `amenity=shelter` | 11,307 | 3,019 / 8,282 / 6 | mostly bus and picnic shelters; filter on `shelter_type` |

Three kinds of point are worth a decision:

- **Defibrillators.** OSM has 23,034 in Great Britain (ODbL). The British Heart Foundation's register, The Circuit, is not
  open: its monthly file is offered to councils, charities and researchers, and its terms forbid use for an app without
  written consent. A defibrillator layer from OSM fits a survival map well; Lastbook would need to say it is only as complete
  as OSM.
- **Flood warning areas.** The Environment Agency's real-time flood-monitoring API (opened) is under the OGL, needs no
  registration, covers England only, and gives each flood area a centre point and a WGS 84 polygon. The polygons could be
  stored; live warnings need a connection, so the map would show the last-fetched time. Wales (Natural Resources Wales)
  and Scotland (SEPA) were not confirmed as open feeds.
- **Rest centres and emergency shelters.** None found: a national list does not exist; they are designated locally, and a
  few councils name sites. Not proposed, as for German shelters.

Official lists for hospitals, GPs and pharmacies come from the NHS Organisation Data Service (OGL; opened). The pages read
mention addresses but not coordinates, so coordinates were not confirmed; it could cross-check OSM, as Germany's
hospital register could. No national official list with coordinates was found for fire stations (a Home Office dataset of
2018 and an MHCLG one of January 2026 appeared in search only) or for police stations.

## Guides for the UK

The urgent-needs guides in `content/topics/` cite US sources (FEMA, the Red Cross, CDC, USDA, NOAA Weather Radio,
911). This section is only about which UK sources could replace them; it does not change any guide.

| UK source | Use | Licence found | Checked |
|---|---|---|---|
| Be Ready, the UK Government's preparedness site (`gov.uk/prepare` redirects to it) | household preparedness, hazards, emergency kit | OGL v3.0 unless stated; branding and graphics not covered | opened |
| Ready Scotland | Scottish variant: flooding, cold and snow, emergency plan | mostly OGL v3.0; graphics excluded | opened |
| Environment Agency flood guidance and Floodline | flood preparation | OGL v3.0, Crown copyright | opened |
| UK Emergency Alerts (gov.uk/alerts) | what the alert is | OGL v3.0, Crown copyright | opened |
| NHS website | health and first aid | OGL v3.0 **plus extra conditions**: no NHS logos, no fee for access, no third-party material, "refresh every 24 hours to 7 days", England only | opened; page last reviewed January 2021 |
| Food Standards Agency, home food preservation | food safety | OGL v3.0 | opened; general advice only |
| British Red Cross | first aid | **not reusable** without prior authorisation | opened |
| St John Ambulance, RHS growing calendars, UKHSA's individual guidance pages | | | not checked |

What this means for the replacements:

- **Canning.** The FSA page gives general safety advice and says home canning is hard to do safely; it has no tested process
  times, so there is no UK equivalent of the USDA canning guide to adapt. None was found elsewhere.
- **NOAA Weather Radio.** No UK equivalent was found (not the same as saying none exists). Be Ready lists a battery or
  wind-up radio in its kit (search only). The UK Emergency Alerts page was opened; whether it describes cell broadcast was
  not confirmed.
- **Emergency numbers.** 999 and 111 are described on an NHS page (opened). 105 (power cuts) and the gas emergency line
  0800 111 999 were seen in search only. 112 and 101 were not checked.
- **Weather warnings.** The Met Office's warnings feeds are **not under an open licence**: the RSS terms require a working
  link to the full article, let the Met Office stop the feed, and keep all rights. They suit live display, not an offline copy.
- **Units.** UK guides would use metric measures. The map code shows contours in feet unless the map set's `map-set.json`
  says `units: metric`, which the South West pilot does.

## Licence notes and attribution

- **Open Government Licence v3.0 (OGL).** Used by GOV.UK content, the Environment Agency, the Rural Payments Agency and
  Scotland's remote sensing data. The licence text itself was not opened (the National Archives refused the fetch).
  Standard wording, seen in search only: "Contains public sector information licensed under the Open Government Licence
  v3.0." Providers may set their own credit line, for example the Environment Agency's and the Rural Payments Agency's.
- **OS OpenData** (Open Names, Code-Point Open, Terrain 50, Open Rivers, OpenMap - Local, Open UPRN). Every OS product page
  read says "free to use for everyone" and names no licence; that OS OpenData is under the OGL v3 is from search results
  only. OS's copyright page (opened) gives the credit: "Contains OS data © Crown copyright and database right [year]."
- **Royal Mail line.** The ONS licence page (opened) requires, for postcode products: "Contains Royal Mail data © Royal Mail
  copyright and database right [year]", the OS line above, and "Source: Office for National Statistics licensed under the
  Open Government Licence v.3.0." The Code-Point Open pages did not state the wording; a search snippet quotes the Royal
  Mail line. Whether Open Names needs the Royal Mail line was not found; its postcode points probably derive from
  Code-Point Open (an inference). The licence file inside each download should settle both.
- **Northern Ireland.** Land and Property Services data (BT postcodes, OSNI-branded mapping, which one search summary says
  falls outside the OGL) needs its own check before use.
- **ODbL** (OSM, Overture buildings): as for the US map; credit "© OpenStreetMap contributors".
- **Copernicus GLO-30:** the DLR/Airbus credit, plus "produced using Copernicus WorldDEM-30" if the data is modified.
- **CDLA Permissive 2.0** (Microsoft footprints taken directly): a different licence from the ODbL Overture applies to the
  same data. Pick one route.
- **NHS content:** the extra conditions above apply on top of the OGL.

These notices would belong wherever the map already credits its sources, and in `THIRD_PARTY_NOTICES.md` if that is where
the maintainers keep data licences.

## How addresses are written

- **Order.** Premises (number or name), thoroughfare, locality, post town, postcode: "10 Downing Street, London SW1A 2AA".
  The post town is part of a postal address but not of the postcode (OSM wiki, opened). A postcode comes **last**; a US
  ZIP code also comes last, but a UK postcode has two parts.
- **Postcode.** One of six patterns (`A9 9AA`, `A99 9AA`, `A9A 9AA`, `AA9 9AA`, `AA99 9AA`, `AA9A 9AA`), always with a
  space before a three-character inward code; about 1.7 million are in use; Northern Ireland is the single area `BT`
  (Wikipedia, opened). A practical pattern, **suggested here and not taken from a publisher**, is
  `^[A-Z]{1,2}[0-9][A-Z0-9]? ?[0-9][A-Z]{2}$`; it needs testing.
- **Premises** are often a name ("Rose Cottage") or a flat ("Flat 2, 10 High Street"; OSM tags `addr:housename`,
  `addr:unit`, `addr:flats`).
- **Bilingual names.** Open Names carries Welsh and Gaelic names beside English ones (opened); the rules for street names
  were not read.
- **What the code on `main` does with that** (read in this repository and tried against examples on 17 November 2026; this
  branch adds accent folding as a retry, UK postcode reading in `_parts()`, and a town-not-state reading in
  `find_addresses()` when no US index is installed; the other points are unchanged):
  - `normalize()` in `engine/address_search.py` keeps only `a-z` and `0-9`, so Welsh circumflexed letters (â ê î ô û ŵ ŷ)
    become spaces; they need folding on both sides, as umlauts do in REGIONS-DE.md.
  - `is_address_query()` needs a number first, so "10 Downing Street" is an address, "Flat 2, 10 High Street" and "Rose
    Cottage, Church Lane" are not, and a bare postcode ("SW1A 2AA") goes to the places finder.
  - `_parts()` takes a postcode only as one five-digit last word and a state from the US list, so a UK postcode is not
    recognised and its words would be read as a street or town.
  - `find_addresses()` opens one `addresses/<code>.sqlite` by file name matching a US state code, and the result schema has
    `state` and `zip` columns.
  - `tools/build_addresses.py` keeps only `country = 'US'`, cuts the postcode to five characters and the region to two
    letters.
  - The word list shortens "street", "road", "lane", "terrace", "place", "court" and the compass points; it has no "close",
    "crescent", "gardens" or "mews". Whether that matters depends on how matching is done, and was not tested.

## Still undecided

Each of these needs the maintainers' decision before any code changes. The first two are shared with REGIONS.md and
REGIONS-DE.md.

1. **Codes in setup.** Whether `GB-NE` and the others are acceptable as a manifest `id`, in `map-set.json` and in
   `Lastbook-Map-<id>.zip`, and how setup groups 12 UK regions. `GB-NE` needs a different spelling if the part after the
   hyphen is ever read alone.
2. **The box rule**, as in REGIONS.md, here from ONS generalised boundaries.
3. **12 regions or 4.** Nine English regions give maps comparable to a US state; four nations would give a 1.6 GB England.
4. **London.** Whether the South East map should also carry London's addresses.
5. **Terrain.** The South West pilot used one surface model (GLO-30), which includes trees and buildings in its heights.
   Whether to use it for the whole UK, or OS Terrain 50 for Great Britain, or bare-earth lidar for England, Scotland and
   Wales with something else for Northern Ireland.
6. **Crops.** The pilot shows OSM orchards and vineyards, which has no crop types and no berries. Whether that is good
   enough to ship, or the layer is left out until an open crop map exists.
7. **Addresses.** The pilot's OSM address search finds houses by number, street, town or postcode, but only where a volunteer
   mapped the house (about 79 % of its 805,786 addresses carry a postcode). Whether that is acceptable in place of full
   address search, and whether Northern Ireland's postcodes can be had under a licence.
8. **Northern Ireland as a whole.** It is outside OS's open products, has its own postcode licence, and its map box takes
   in part of the Republic.
9. **New help-point kinds**: defibrillators from OSM, and flood warning areas from the Environment Agency.
10. **Units.** Done on this branch for a map set that says `units: metric`: metres for contours, distances and the scale bar.
    Whether UK roads should show miles is not decided; the pilot shows kilometres throughout.
11. **London and Northern Ireland in two proposals.** [REGIONS-GB-LONDON.md](REGIONS-GB-LONDON.md) proposes `GB-LON` on its
    own, and [REGIONS-IE.md](REGIONS-IE.md) proposes Northern Ireland as part of an island-wide region. See "Related
    proposals" above for what differs.

## What was checked, and what was not

- **Opened on 17 November 2026:** OS product pages and download API listings for Open Names, Code-Point Open, Open UPRN,
  Terrain 50, Open Rivers and OpenMap - Local, and OS's copyright acknowledgements page; ONS's licence page and its ITL1
  feature service; ONS's Postcode Directory record on data.gov.uk; GeoNames' postcode folder; Overture's address, building
  and attribution pages; Royal Mail PAF's licensing page; Finance NI's Pointer page; datadaptive.com's address directory;
  the OSM wiki pages on UK addresses and dams, and OSM's copyright page; Geofabrik's Europe, Great Britain and United
  Kingdom pages; taginfo (Geofabrik and global); the data.gov.uk records for the National LIDAR Programme, CROME 2024 and
  Northern Ireland's Historic Environment Division LiDAR; the Scottish Government's Phase 6 DTM record and Scottish Crop
  Map 2019 page; the Welsh Government LiDAR record; the NERC reservoir inventory; the UKCEH Land Cover Map licence;
  Copernicus DEM pages at Copernicus and AWS; Microsoft's building footprints repository; the NHS ODS, NHS website
  datasets and NHS terms pages; the British Heart Foundation and The Circuit pages; the Environment Agency flood-monitoring
  reference; the Met Office warnings RSS and API pages; the GOV.UK terms; the Be Ready, Ready Scotland, UK Emergency
  Alerts, UK Resilience Framework, UKHSA, flood and FSA preservation pages; the British Red Cross terms; the NHS 999 page.
- **Computed on 17 November 2026:** the 12 boxes, from the ONS services as described above, and the London-in-South-East
  containment.
- **Seen only in search results:** that OS OpenData is under the OGL v3; the Code-Point Open Royal Mail wording; the OS
  AddressBase replacement; Northern Ireland Pointer's price; the 2018 Home Office and January 2026 MHCLG fire station
  datasets; the 105 and gas emergency numbers; the NRW and SEPA data licences; the Environment Agency's 2023 reservoir
  data release.
- **Built and tried on 17 and 18 November 2026** (the South West pilot, `GB-SW`): see the next section.
- **Not checked:** the OGL v3.0 text; the Open Names and Code-Point Open licence files; Code-Point Open's coordinate fields;
  the ONS Postcode Directory's coordinates and postcode count; GLO-30 completeness for the UK outside the South West; the Environment Agency DTM
  page itself and a single national download; Scotland's full lidar coverage; Wales's completeness and licence wording;
  Northern Ireland's 50 m DTM licence (OpenDataNI refused the fetch); Wales and Northern Ireland crop data; Scottish
  Water's reservoir data; Scottish address sources; how complete OSM addresses are against a reference list; the Royal Mail addressing guidance; St John
  Ambulance and RHS terms; the numbers 112 and 101; the ISO 3166-2:GB page; and whether ITL January 2025 is the latest ITL
  edition.

## The South West pilot

A South West (`GB-SW`) map set was built on 17 and 18 November 2026 to see what the proposal's sources give in practice. It
is one region, built from public sources on one machine, and none of its data is in this repository. Figures are counts of
what was built, not measures of how complete the data is.

| Layer | Source used | What came out | Limits found |
|---|---|---|---|
| Streets, places, help points | Geofabrik England extract, cut to the box | 4.3 million features, 33,000 help points | Needs an empty `map.sqlite` beside `national.sqlite` for street tiles |
| Addresses | OSM house numbers, from Geofabrik's England `.osm.pbf` | 805,786 addresses, 79 % with a postcode | Only houses a volunteer mapped; the other 21 % cannot be found by postcode |
| Terrain | Copernicus GLO-30, 17 one-degree tiles | 4,979 tiles; a Dartmoor tile reads 155-617 m against High Willhays at about 621 m | A surface model: heights include trees and buildings |
| Water | OSM lakes and reservoirs, OSM `waterway=dam` | 112 reservoirs, 1,530 named lakes, 147 dams | No ponds layer; dams carry a name and owner at most |
| Crops | OSM `landuse=orchard` and `landuse=vineyard` | 3,128 orchards, 236 vineyards | No crop type, no berries, volunteer-mapped |
| Buildings | OSM buildings with a height or storey count (the file the 3D view reads); outlines come from the street map | 419,263 buildings with heights, about one in six of the outlines | Only buildings a volunteer gave a height or storeys to are extruded in 3D; Microsoft's footprints were not used |
| Place finder | Named places and help points from the map file; postcodes and postcode districts from the OSM address index | 8,668 places, 23,049 named points, 52,310 postcodes, 349 postcode districts | A postcode exists only if an OSM address carries it, and its point is the middle of those addresses; OS Code-Point Open and Open Names (every postcode) not used, as their licence files were not read |
| Aerial photos | none | not built | No open source that may be saved offline was found. Environment Agency vertical aerial photography is patchy (project by project since 2006), comes as ECW tiles on the British National Grid through a Defra platform with no documented interface, and its licence is inconsistent (the data.gov.uk record says OGL, one resource page says no licence provided). APGB imagery is free only to public bodies and is live-only; Aerial Digimap is for subscribing universities. A 10 m Sentinel-2 mosaic would be open but is not aerial photography and was not built |
| Atlas | OSM mines, quarries, mine shafts and adits; slipways and marinas | 1,169 mineral records and 737 boat launches | OSM says what a place is, not whether it is safe or in use; quarries mapped only as relations are missed; no fish-stocking or oil and gas well records |

The tools are `tools/build_map.py` (box cut), `tools/build_addresses_osm.py`, `tools/build_terrain.py`,
`tools/build_water.py`, `tools/build_crops_osm.py`, `tools/build_atlas_osm.py`, `tools/build_places_osm.py` and `tools/build_osm_heights.py` (with a box). Source extracts for a region as large as England are 1.7 GB (PBF)
and 3.2 GB (GeoPackage) because Geofabrik has no South West extract; the box is cut during the build.
