# Detailed maps for the Netherlands: a proposal

This is a proposal for discussion, not a decision. It answers, for the Netherlands, the questions [MAPS.md](MAPS.md)
asks before coverage can go beyond the United States: which open source replaces each federal list, under what
licence, what a "state" is there, and how addresses are written. It follows the shape of [REGIONS-DE.md](REGIONS-DE.md),
[REGIONS-DK.md](REGIONS-DK.md) and [REGIONS-FR.md](REGIONS-FR.md) and is meant to feed the same design discussion
(issue #31), as suggested in #95. The machine-readable version is [regions-nl-proposed.json](regions-nl-proposed.json).

Nothing here changes the app, the engine or a build. No code reads the JSON, and nothing here ships: builds package
`web/` and `content/` only.

**How things were checked.** Research was done on 26 and 27 November 2026, with an AI assistant reading the publishers'
own pages and public APIs, without an account, and a person reviewing the result. Separately, all twelve provinces were
built end to end in a trial build on 25 and 26 November (see "What a trial build showed"), and the figures marked
**measured** were read from that build's files on 27 November. Each source carries one of these marks:

- **opened**: the dataset page, licence page, API answer or download listing was opened and read;
- **search only**: the fact was seen in a search result, but the page itself was not opened or did not load;
- **not checked**: the question was not looked at; the row says what is missing;
- **measured**: counted with a query or script over the trial build's files, or by calling this repository's code.

## Why the Netherlands is a different case

- **One national source per layer, mostly public domain.** Addresses, buildings, crop parcels and boundaries are base
  registers (*basisregistraties*) of the state, published by Kadaster and other agencies through PDOK. The address and
  building register (BAG) and the crop parcels (BRP) carry the Public Domain Mark; boundaries and the topographic map
  are CC BY 4.0. No key or account is needed: PDOK's OGC APIs answer anonymously (opened).
- **Every address has a point.** The BAG holds every address in the country, 10,798,639 in the trial build, each with
  a WGS 84 point, a postcode where one is given, its place (*woonplaats*), municipality and province (measured).
- **Water means flood defences, not dams.** Much of the country lies below sea level. The national file of primary
  flood defences (dikes, dunes, dams and storm-surge barriers) is the nearer equivalent of the NID.
- **It has been built.** A trial builder for all twelve provinces exists, so the figures below are measured, not
  estimated. The code is not in this pull request.

## What a region is

The Netherlands has 12 provinces and 342 municipalities on 1 January 2026 (CBS; search only; the trial build counts
342 municipalities in the BAG, measured). The proposal is one map region per province, the level closest to a US state:
the twelve range from about 239,000 addresses (Flevoland) to 2.3 million (Zuid-Holland), the size of US state maps, and
Geofabrik already cuts its OpenStreetMap extracts by province (opened). A merged map of the whole country was also
built and works (see "What a trial build showed").

The Wadden islands belong to their provinces, in the BAG as in Geofabrik's extracts: Texel to Noord-Holland;
Vlieland, Terschelling, Ameland and Schiermonnikoog to Fryslân; Rottumeroog and Rottumerplaat, uninhabited, to
Groningen (measured).

The Caribbean parts of the Kingdom are not proposed here: Bonaire, Sint Eustatius and Saba (special municipalities)
and Aruba, Curaçao and Sint Maarten (countries in the Kingdom). Their sources were not looked at.

### Codes

ISO 3166-2:NL gives each province two letters after `NL-`: `NL-DR` Drenthe, `NL-FL` Flevoland, `NL-FR` Fryslân,
`NL-GE` Gelderland, `NL-GR` Groningen, `NL-LI` Limburg, `NL-NB` Noord-Brabant, `NL-NH` Noord-Holland, `NL-OV`
Overijssel, `NL-UT` Utrecht, `NL-ZE` Zeeland, `NL-ZH` Zuid-Holland (search only: secondary listings, not iso.org). The
Caribbean parts have `NL-AW`, `NL-CW`, `NL-SX` and `NL-BQ1` to `NL-BQ3`.

- **The prefix is needed.** Three of the twelve letter pairs are US state codes: `FL` (Flevoland and Florida), `NH`
  (Noord-Holland and New Hampshire) and `UT` (Utrecht and Utah), in `STATE_CODES` in `engine/address_search.py`. A
  bare `NL` is not.
- **Index names.** `engine/setup/manifest.py` line 97 accepts an address index id only as `[A-Z]{2}`, and
  `engine/setup/install.py` line 462 carries over only `[A-Z]{2}.sqlite` and `.json`. `NL-FL` does not fit, and `FL`
  would be Florida. The trial named its indexes `addresses/NL-FL.sqlite` and so on, and loaded the map set from a folder
  outside the library, so the manifest was not involved. This is the same question REGIONS-DK.md and REGIONS-TH.md
  raise.
- **Other codes in the data.** CBS numbers the provinces `PV20` (Groningen) to `PV31` (Limburg) (opened, StatLine).
  The BAG writes its own province code in mixed case: `ZH`, `NH` and `NB`, but `Gr`, `Fr`, `Dr`, `Ov`, `Fl`, `Ge`,
  `Ut`, `Ze` and `Li`, and Friesland's name as `Fryslân` (opened: one address per province, 25 November 2026).

### Boxes

Each box is the extent of the province's official boundary in **Kadaster's BRK Bestuurlijke Gebieden**, collection
`provinciegebied`, through PDOK's OGC API (`https://api.pdok.nl/kadaster/brk-bestuurlijke-gebieden/ogc/v1`; CC BY 4.0;
opened; served 2026-11-26T06:10:05Z). It is the national boundary register, so no Eurostat or OSM boundary is needed. A
province's area includes its inland and coastal waters, so Flevoland's box takes in part of the IJsselmeer and
Markermeer. Each box was then widened by 0.15° and rounded outward to 0.01°, the margin `packaging/build_packs.py`
gives US state boxes and country boxes.

| Code | CBS | Name | Municipalities | Box (west, south, east, north) | Box with 0.15° margin |
|---|---|---|---|---|---|
| `NL-GR` | PV20 | Groningen | 10 | 6.16743, 52.83820, 7.22750, 53.57642 | 6.01, 52.68, 7.38, 53.73 |
| `NL-FR` | PV21 | Fryslân | 18 | 4.81838, 52.76481, 6.42761, 53.53971 | 4.66, 52.61, 6.58, 53.69 |
| `NL-DR` | PV22 | Drenthe | 12 | 6.11982, 52.61220, 7.09274, 53.20383 | 5.96, 52.46, 7.25, 53.36 |
| `NL-OV` | PV23 | Overijssel | 25 | 5.77775, 52.11807, 7.07276, 52.85421 | 5.62, 51.96, 7.23, 53.01 |
| `NL-FL` | PV24 | Flevoland | 6 | 5.06043, 52.24953, 6.01730, 52.84398 | 4.91, 52.09, 6.17, 53.00 |
| `NL-GE` | PV25 | Gelderland | 51 | 4.99385, 51.73358, 6.83280, 52.52203 | 4.84, 51.58, 6.99, 52.68 |
| `NL-UT` | PV26 | Utrecht | 26 | 4.79204, 51.85736, 5.62731, 52.30368 | 4.64, 51.70, 5.78, 52.46 |
| `NL-NH` | PV27 | Noord-Holland | 44 | 4.47765, 52.16593, 5.37726, 53.21427 | 4.32, 52.01, 5.53, 53.37 |
| `NL-ZH` | PV28 | Zuid-Holland | 50 | 3.77368, 51.64378, 5.03142, 52.33251 | 3.62, 51.49, 5.19, 52.49 |
| `NL-ZE` | PV29 | Zeeland | 13 | 3.30794, 51.20016, 4.27742, 51.78152 | 3.15, 51.05, 4.43, 51.94 |
| `NL-NB` | PV30 | Noord-Brabant | 56 | 4.19012, 51.22091, 6.04812, 51.83075 | 4.04, 51.07, 6.20, 51.99 |
| `NL-LI` | PV31 | Limburg | 31 | 5.56605, 50.75037, 6.22677, 51.77863 | 5.41, 50.60, 6.38, 51.93 |

Municipalities are those with at least one BAG address in the province (measured); they add up to 342.

### Boxes that hold other provinces

Every BAG address of a province lies inside that province's box, all 10,798,639 of them (measured). But the provinces
are small and irregular, so each box also holds many addresses of its neighbours. Counted over the trial build's
address files (measured):

| Code | Own addresses | Other provinces' addresses in the box | With the 0.15° margin | Largest share |
|---|---:|---:|---:|---|
| `NL-GR` | 379,059 | 164,063 | 405,804 | Drenthe, 139,626 |
| `NL-FR` | 415,126 | 110,540 | 778,485 | Groningen, 36,934 |
| `NL-DR` | 299,633 | 213,054 | 707,184 | Groningen, 157,112 |
| `NL-OV` | 691,268 | 426,077 | 1,055,200 | Gelderland, 247,357 |
| `NL-FL` | 238,815 | 342,791 | 1,662,736 | Noord-Holland, 164,770 |
| `NL-GE` | 1,250,394 | 1,583,947 | 3,265,462 | Utrecht, 719,483 |
| `NL-UT` | 801,372 | 435,641 | 2,267,664 | Noord-Holland, 220,031 |
| `NL-NH` | 1,879,854 | 320,486 | 1,637,810 | Flevoland, 112,731 |
| `NL-ZH` | 2,293,923 | 506,007 | 2,514,526 | Noord-Holland, 266,411 |
| `NL-ZE` | 291,893 | 35,861 | 397,225 | Zuid-Holland, 25,581 |
| `NL-NB` | 1,556,918 | 465,411 | 2,111,684 | Zuid-Holland, 205,313 |
| `NL-LI` | 700,384 | 269,076 | 901,154 | Noord-Brabant, 258,369 |

Gelderland's box holds more addresses of other provinces than of its own, including 90 % of Utrecht's, and so does
Flevoland's. A province
cannot be cut from the BAG by its box. The trial asked the BAG by box and kept the records whose own province field is
the province's; OpenStreetMap came from Geofabrik's province extracts, which are cut by the province's outline. The
BAG holds no foreign addresses, so the boxes that reach into Belgium and Germany (Aachen lies inside Limburg's box)
add no foreign rows from it; sources cut by box would.

### Size of each region

Population is CBS's table 37230ned at 1 September 2026, the latest month published (read through
`https://opendata.cbs.nl/ODataApi/odata/37230ned`, opened). The twelve add up to the country's total, 18,171,612.
Addresses are the BAG rows in the trial build; the BAG also counts shops, offices, berths and caravan pitches, so it
is not a count of homes (measured).

| Code | Name | Population, 1 September 2026 | BAG addresses | without a postcode |
|---|---|---:|---:|---:|
| `NL-GR` | Groningen | 599,725 | 379,059 | 19,103 |
| `NL-FR` | Fryslân | 665,595 | 415,126 | 16,596 |
| `NL-DR` | Drenthe | 508,822 | 299,633 | 12,734 |
| `NL-OV` | Overijssel | 1,205,058 | 691,268 | 27,637 |
| `NL-FL` | Flevoland | 465,921 | 238,815 | 5,914 |
| `NL-GE` | Gelderland | 2,179,092 | 1,250,394 | 44,040 |
| `NL-UT` | Utrecht | 1,418,315 | 801,372 | 28,221 |
| `NL-NH` | Noord-Holland | 3,019,491 | 1,879,854 | 76,885 |
| `NL-ZH` | Zuid-Holland | 3,890,837 | 2,293,923 | 91,506 |
| `NL-ZE` | Zeeland | 396,156 | 291,893 | 21,836 |
| `NL-NB` | Noord-Brabant | 2,685,101 | 1,556,918 | 77,905 |
| `NL-LI` | Limburg | 1,137,499 | 700,384 | 31,531 |
| | **Netherlands** | **18,171,612** | **10,798,639** | **453,908** |

### OpenStreetMap extracts

Geofabrik has an extract for the Netherlands and one for each of the twelve provinces (opened). The trial used the
provinces' `<province>-latest-free.gpkg.zip`, data up to 2026-11-24T21:21:23Z. The sizes of the files it downloaded
(measured):

| Province extract | Bytes |
|---|---:|
| `groningen` | 97,105,295 |
| `friesland` | 175,240,993 |
| `drenthe` | 112,540,636 |
| `overijssel` | 204,277,632 |
| `flevoland` | 66,089,570 |
| `gelderland` | 326,350,300 |
| `utrecht` | 166,184,959 |
| `noord-holland` | 317,977,875 |
| `zuid-holland` | 348,713,912 |
| `zeeland` | 81,164,090 |
| `noord-brabant` | 356,991,247 |
| `limburg` | 169,695,298 |
| all twelve | 2,422,331,807 |

Geofabrik names Fryslân `friesland`. The free GeoPackage has no defibrillator layer, so the trial took AEDs from
OpenStreetMap through the Overpass API (see "Help points").

## Sources, layer by layer

These hold for the whole country. The detail is in the JSON.

| Layer (file) | US source today | Proposed for the Netherlands | Publisher | Licence | Checked | In the trial |
|---|---|---|---|---|---|---|
| Terrain (`terrain.sqlite`) | USGS 3DEP | AHN, Actueel Hoogtebestand Nederland: DTM at 0.5 m and 5 m, GeoTIFF | AHN (water boards, provinces and Rijkswaterstaat) | CC0 1.0 on data.overheid.nl; AHN's own page says only "open data" | dataroom opened; licence search only | no |
| Water (`water.sqlite`) | NHD | OpenStreetMap water; BRT TOP10NL water as alternative | OSM contributors; Kadaster | ODbL; CC BY 4.0 | opened | OSM |
| Dams | NID | No dam register; Nationale Basisbestanden Primaire Waterkeringen (dikes, dunes, dams, structures) | Informatiehuis Water | public domain ("Publiek domein") | search only; the page did not load | no |
| Crops (`crops.sqlite`) | USDA Cropland Data Layer | BRP Gewaspercelen, the declared crop parcels, reference date 15 May each year | RVO, through PDOK | Public Domain Mark 1.0 | opened | no |
| Buildings (`buildings.sqlite`) | Microsoft US footprints, OSM heights | BAG `pand` outlines; heights from 3DBAG | Kadaster; TU Delft 3D geoinformation and 3DGI | PDM 1.0; CC BY 4.0 | opened | no |
| Places (`places.sqlite`) | GNIS, Census gazetteers, OSM | BAG places and municipalities; OSM named places; CBS Wijken en Buurten for neighbourhoods | Kadaster; OSM; CBS | PDM 1.0; ODbL; CC BY 4.0 | opened | BAG and OSM |
| Addresses (`addresses/<code>.sqlite`) | Overture addresses | BAG, collection `adres`, through PDOK's OGC API | Kadaster | Public Domain Mark 1.0 (the API); CC0 1.0 (the downloads) | API opened; downloads search only | yes |
| Points of interest (`poi` rows) | OSM | OSM, as today; emergency departments from the RIVM | OSM contributors; RIVM | ODbL; PDM 1.0 | opened | yes |

Notes:

- **Terrain.** 0.5 m is far finer than zoom 12, the deepest zoom `tools/build_terrain.py` writes, so it would be
  resampled; the 5 m grid may be enough. AHN's dataroom lists AHN4, AHN5 and AHN6, which is being flown in 2025 and 2026
  (opened). The size of a whole-country download was not checked.
- **Water.** The risk is the sea and the rivers. The national file of primary flood defences is the nearer equivalent
  of the NID, but `water.sqlite` has no kind for a dike, as REGIONS-DK.md also notes. Rijkswaterstaat's legger of
  primary flood defences is listed under CC0 1.0 (search only). Neither file was opened.
- **Buildings.** A BAG `pand` has an outline and a construction year but no height; 3DBAG derives heights from AHN
  and asks for the credit "© 3DBAG by tudelft3d and 3DGI" (opened).
- **Places.** The BAG's places are the official *woonplaatsen*: 2,503 in the trial build, in 342 municipalities
  (measured). CBS's neighbourhood map is CC BY 4.0 on PDOK (opened); CBS's own explanation asks that CBS and Kadaster
  be named as the source (search only).
- **Addresses.** One record of the `adres` collection holds the street (`openbare_ruimte_naam`), house number, letter
  and addition, postcode, place, municipality, province and a point (opened). The API filters by box; a request
  filtered by province failed when tried, so the trial asked by box and filtered itself.

## Help points

OpenStreetMap stays the base. Counts for Geofabrik's Netherlands extract (taginfo, data until 2026-11-24T21:21:17Z;
opened), and in the trial build's merged map (measured):

| Tag | taginfo | In the trial map |
|---|---:|---:|
| `amenity=pharmacy` | 1,696 | 1,696 |
| `amenity=hospital` | 166 | 166 |
| `amenity=doctors` | 2,485 | 2,485 |
| `amenity=clinic` | 643 | 643 |
| `amenity=fire_station` | 1,014 | 1,014 |
| `amenity=police` | 463 | 463 |
| `amenity=drinking_water` | 2,778 | 2,778 |
| `amenity=shelter` | 12,007 | 12,007 |
| `amenity=ferry_terminal` | 864 | 860 |
| `emergency=defibrillator` | 4,370 | 4,260 (Overpass, the twelve province areas) |
| `emergency=siren` | 4,221 | none (no class) |
| Emergency departments (RIVM) | | 79 |

- **Shelters.** 10,510 of the 12,007 `amenity=shelter` carry `shelter_type=public_transport`: bus shelters (taginfo
  combinations; opened). The trial kept them all under one class, as `tools/build_map.py` does, so a Dutch map would
  need to drop them or give them their own word.
- **Emergency departments.** OSM's `hospital` does not say which hospitals have an emergency department (*SEH*). The
  RIVM's "Vragenlijst aanbod SEH's en Acute Verloskunde 2026", published 2 July 2026 on data.rivm.nl, lists every
  hospital location with acute care and what it offers, with "Geen beperkingen" and the Public Domain Mark (opened). The
  trial placed its 79 emergency departments at their BAG address.
- **Defibrillators.** The national register is HartslagNu (the Dutch Heart Foundation). It gives data for research on
  request under a data access policy (search only), and the foundation has said it may not publish exact AED locations
  (NOS; search only). The Red Cross closed its open AED database on 28 February 2020 (HartslagNu; search only). A NOS
  article reports 25,840 registered AEDs (search only; its date was not checked); OpenStreetMap has 4,370. Some
  municipalities publish their own list (Zoetermeer on data.overheid.nl; search only).
- **Sirens.** The national warning system (WAS) has about 4,278 sirens, placed in towns of 1,000 people or more (a
  municipal factsheet; search only), and in June 2026 the cabinet announced a new siren network to replace it
  (rijksoverheid.nl, 9 June 2026; search only). OpenStreetMap has 4,221 `emergency=siren`; whether they are the WAS
  sirens was not checked. `tools/build_map.py` has no siren class.

**Emergency numbers** do not differ by province: 112, the police's non-emergency number (0900 8844), 113 for suicide
prevention and the national gas and electricity outage number (0800 9009). They are proposed in #495
(`content/emergency/NL.json`). The out-of-hours GP posts
(*huisartsenposten*) each have their own number; they were not looked at.

## Licence notes and attribution

- **Public domain** (Public Domain Mark 1.0 or CC0 1.0): the BAG (API opened, downloads search only), BRP Gewaspercelen
  (opened), the RIVM's emergency departments (opened), the primary flood defences (search only) and AHN (search only).
  Nothing has to be credited, but "Kadaster, BAG" with a date is good practice and lets a reader find the source.
- **CC BY 4.0**: Kadaster's BRK Bestuurlijke Gebieden and BRT TOP10NL (opened), CBS Wijken en Buurten (opened; CBS asks
  for CBS and Kadaster to be named) and 3DBAG (opened, with the fixed credit above). No share-alike.
- **ODbL** (OSM). As for the US map; the app and the packs have no link to the ODbL text today, as REGIONS-FR.md notes.
- **Not open**: the HartslagNu AED register.

As in France and Denmark, public-domain or CC BY points merged with OSM points in one `poi` table probably make a
derived database under the ODbL; one file or table per licence avoids that (a question, not legal advice). The trial
wrote each help point's source into the map's `meta` table. `MAP_CREDIT` in `packaging/build_packs.py` is a fixed US
list.

## How addresses are written

- **Order.** Street, then the house number with its letter and addition, then the postcode and the place:
  "Rotterdamseweg 374A, 2629 HG Delft". Forms and parcels often ask for the postcode and house number alone ("2629 HG
  374"), which name one address.
- **Postcode.** Four digits, never starting with 0, then two capital letters, written with a space. The trial build
  has 4,086 four-digit areas and 471,730 full postcodes (measured). They follow province borders closely: 15 four-digit
  areas and 14 full postcodes have addresses in two provinces, the largest real case 7973 (335 addresses in Drenthe and
  24 in Overijssel) (measured). A few BAG rows carry placeholders such as `9999ZZ` in Zwolle and Rotterdam or `1234AB`
  in Finsterwolde, 19 in all; 9999 itself is real, in Stitswerd (measured).
- **House number.** In the trial build 8,463,881 numbers are digits only, 1,287,744 have a letter ("40A") and
  1,047,014 an addition after a hyphen ("4-2C4", "55-BEDR") (measured). 453,908 addresses, 4.2 %, have no postcode at
  all: outbuildings with an addition such as "ts", berths and caravan pitches (measured).
- **Places.** The place is the BAG's *woonplaats*, which is often not the municipality ("Ter Apel", in Westerwolde).
  2,503 places have 2,428 names, so 75 names are used in more than one municipality (measured). The Hague is
  "'s-Gravenhage" in the BAG and "Den Haag" in speech; 's-Hertogenbosch is "Den Bosch".
- **Streets.** 139,219 street names are used on 248,567 streets (name and place): Kerkstraat in 513 places,
  Schoolstraat in 459, Dorpsstraat in 319 (measured). A street and number alone rarely name one house.
- **Letters.** Names use accents and apostrophes: 2,729 street names have an accented letter ("Ruïnelaan") and 1,069
  an apostrophe ("'t Ompad", "'s-Gravendeel"); 1,846 abbreviate a title ("Burg.", "Mr.", "Dr."); 49,375 end in
  "straat", which people write as "str." (measured). Fryslân is also written Friesland.
- **What the current code does with that** (main at `51658f5`, on 27 November 2026, by calling its functions;
  measured):

| Query | What happens |
|---|---|
| `Rotterdamseweg 374A, 2629 HG Delft` | Read in the German order by `_parts_de`: the house number becomes `2629`, the postcode's digits, and `374a` joins the street. |
| `Spui 70, 2511 BT Den Haag` | The same: house number `2511`. |
| `2629 HG 374` | Taken as a US address by `is_address_query`: house `2629` on a street called "hg 374". |
| `Ruïnelaan 3`, `Fryslân` | `normalize()` and `normalize_de()` keep only `a-z` and `0-9`: "ru nelaan", "frysl n". |
| any Dutch query | `find_addresses` reads only indexes whose `meta` norm is `us` or `de-1`, so a Dutch index under its own rule is never searched. |

  `tools/build_addresses.py` also keeps only `country = 'US'`. So a Dutch address index needs its own rule, as #79 did
  for Berlin (`norm = de-1`): the trial uses `norm = nl-1` (lower case, accents off, punctuation to spaces, a word
  ending in "straat" shortened to "str"), reads a four-digit-and-two-letter postcode, the letter and addition, and the
  postcode-first form, and makes no US-state guess.

## What a trial build showed

All twelve provinces were built into map sets and shown in the app, run from the repository sources on macOS. **The
code is not in this pull request.** It is in a fork, at
[sodamos/lastbook, branch `nederland`](https://github.com/sodamos/lastbook/tree/nederland): `tools/build_region_nl.py`
(fetch, build, check, merge, AEDs, emergency departments), `engine/address_nl.py` (the `nl-1` search) and a `--map`
option in `server.py` that loads a map set kept outside the library. It was written against the current formats and
will be adapted to the common region format when the maintainers settle it. It was built from Geofabrik's extracts of
24 November 2026 and the BAG as PDOK served it on 25 and 26 November; every province passed the builder's own checks.

| Province | Addresses | Ferry terminals | Size |
|---|---:|---:|---:|
| `NL-GR` Groningen | 379,059 | 33 | 174 MB |
| `NL-FR` Fryslân | 415,126 | 95 | 259 MB |
| `NL-DR` Drenthe | 299,633 | 18 | 178 MB |
| `NL-OV` Overijssel | 691,268 | 54 | 348 MB |
| `NL-FL` Flevoland | 238,815 | 25 | 117 MB |
| `NL-GE` Gelderland | 1,250,394 | 143 | 590 MB |
| `NL-UT` Utrecht | 801,372 | 98 | 324 MB |
| `NL-NH` Noord-Holland | 1,879,854 | 207 | 669 MB |
| `NL-ZH` Zuid-Holland | 2,293,923 | 199 | 793 MB |
| `NL-ZE` Zeeland | 291,893 | 53 | 143 MB |
| `NL-NB` Noord-Brabant | 1,556,918 | 78 | 692 MB |
| `NL-LI` Limburg | 700,384 | 46 | 315 MB |
| **Netherlands** | **10,798,639** | | **about 4.5 GB** |

What the build showed:

- **The BAG through PDOK.** The API needs no key, but some pages deep into a busy cell answered HTTP 500, and the same
  page again hours later (25 and 26 November, in ten of the twelve provinces). The builder splits such a cell in four,
  down to boxes of about 200 m; in the end no box was left out. Fetching took most of a day, nearly all of it in the
  Randstad. BAG's bulk downloads were not tried and may be faster.
- **The islands.** A box or extract that missed an island would still look like a whole province, so the builder
  checks each inhabited island: Texel 15,615 addresses and 8 ferry terminals; Vlieland 1,654 and 3; Terschelling 5,391
  and 5; Ameland 4,939 and 6; Schiermonnikoog 1,748 and 1. Ferry terminals were added to the help points from OSM's
  transport layer, which `tools/build_map.py` does not read.
- **One map for the country.** The twelve provinces merge into one map set without fetching again: 10,798,639
  addresses, 4,260 AEDs and 79 emergency departments; `national.sqlite` is 3.4 GB.
- **Address search.** 60 BAG addresses were drawn at random, five per province, and each was written three ways: as
  on a letter ("street 12A, 1234 AB place"), postcode and number ("1234 AB 12A"), and lower case without accents or
  commas. The trial's search put the right house first for all 180 queries. With the street and number only it was
  among the first eight for 53 of the 60; the other seven were common names such as "Industrieweg 3". The median was
  82 ms, measured in a virtual machine reading the files over a shared folder, so not a performance figure (measured on
  27 November). The unchanged engine reads no `nl-1` index, and its reading above would miss these queries anyway.
- **Tests.** With the trial code in place the repository's tests ran 888 tests, against 826 on main, with the same three
  errors main has in that environment (a module and PDF rendering missing), on Python 3.13.

Known defects of the trial: it has no terrain, crops, building heights or flood defences; AEDs come from OSM only;
bus shelters are shown as shelters; Setup does not offer a province, so the map is loaded with `--map`; it was not tried
in the installed app.

## Still undecided

Each of these needs the maintainers' decision before any code changes.

1. **Codes and index names.** Whether `NL-ZH` style codes are acceptable as a manifest `id`, in `map-set.json` and in
   `Lastbook-Map-<id>.zip`, and how address indexes are named when `[A-Z]{2}` does not fit. A bare `FL`, `NH` or `UT`
   must not be used: they are US states.
2. **Provinces or the country.** Twelve maps, one map of the whole country (about 4.5 GB), or both. The trial built
   both.
3. **The cut.** Sources cut by the BAG's own province field and Geofabrik's province extracts, as the trial did, rather
   than by box, since the boxes overlap this much.
4. **Addresses.** The PDOK API, which needs patience in dense cells, or the BAG's bulk download; whether addresses
   without a postcode are kept, as the trial does; one shared `meta` key for the spelling rule (`norm = nl-1` here,
   `de-1` in #79, `country = 'FR'` in REGIONS-FR.md).
5. **Search.** Whether the engine reads Dutch addresses the way the trial does, including the postcode-first form and
   other names for places ("Den Haag").
6. **Credits.** One table or file per licence, or public-domain, CC BY and OSM points merged under the ODbL; the
   wording for CC BY sources (CBS, Kadaster, 3DBAG).
7. **Water.** Whether primary flood defences become a kind in `water.sqlite`.
8. **Help points.** Bus shelters dropped or named apart; classes for AEDs, sirens and emergency departments; the RIVM
   list as an official layer.
9. **The Caribbean Netherlands.** Whether to look at Bonaire, Sint Eustatius and Saba later, as their own regions.

## What was checked, and what was not

- Opened on 26 and 27 November 2026: the landing pages of PDOK's OGC APIs for the BAG, BRK Bestuurlijke Gebieden, BRT
  TOP10NL, BRP Gewaspercelen and CBS Wijken en Buurten 2025, with their licences; 3DBAG's copyright page; AHN's
  dataroom; the RIVM's record for the 2026 emergency-department questionnaire; Geofabrik's Netherlands page (on 25
  November).
- Read through public APIs: CBS StatLine (37230ned, population), taginfo for the Netherlands extract (help-point tags
  and shelter types), BRK `provinciegebied` (the boxes, 26 November), BAG `adres` (one address per province, 25
  November).
- Measured on 27 November 2026 over the trial build's files: municipalities, places, streets, postcodes, house numbers,
  addresses inside each box, help-point classes and the address-search queries; and the behaviour of
  `engine/address_search.py` at main `51658f5` on Dutch queries.
- Seen only in search results: the ISO 3166-2:NL codes (secondary listings), the CC0 licence of AHN and of the BAG
  downloads on data.overheid.nl, the primary flood defence file (its page did not load when opened), Rijkswaterstaat's
  legger under CC0, CBS's 342 municipalities and its terms for the neighbourhood map, HartslagNu's data policy, the Red
  Cross's closure of its AED database, the NOS figures, the WAS siren count and the June 2026 decision.
- Not checked: the Caribbean Netherlands; the BAG's bulk downloads; the size of AHN for the whole country; the contents
  of the flood defence file; open national lists of pharmacies, fire stations and police stations; whether OSM's sirens
  are the WAS sirens; the out-of-hours GP numbers; the installed app.
