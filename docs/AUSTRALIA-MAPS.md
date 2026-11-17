# Australian capital-area maps

This contribution proposes offline maps around Australia's eight state and territory capitals.
The design discussion is [#36](https://github.com/Immortal-Protocols/lastbook/issues/36).
It uses the region-map implementation proposed in #35 and the local review and extract-cache work in #30.
These definitions alone do not add downloads to the released app.

Each box extends at least half a degree from the city's published Natural Earth point, rounded outwards
to two decimal places. They are metropolitan areas, **not whole states**. The map may include nearby
settlements and cross an administrative boundary. Canberra uses the NSW extract, which includes ACT,
because its area extends beyond the ACT extract.

| Map id | Area | Geofabrik extract |
|---|---|---|
| `au-ade` | Adelaide | South Australia |
| `au-bri` | Brisbane | Queensland |
| `au-can` | Canberra | New South Wales (includes ACT and JBT) |
| `au-dar` | Darwin | Northern Territory |
| `au-hob` | Hobart | Tasmania |
| `au-mel` | Melbourne | Victoria |
| `au-per` | Perth | Western Australia |
| `au-syd` | Sydney | New South Wales (includes ACT and JBT) |

The exact boxes and input URLs are in `packaging/region_specs.py`. `au-can` is also used by #35;
if that PR lands first, retain one definition and agree its displayed coverage before merging.
Its generated file must also retain these manually supplied areas when regenerated.

## Sources and coverage

- Streets, water features, mapped buildings, place labels and help points: OpenStreetMap contributors,
  distributed by [Geofabrik's Australian extracts](https://download.geofabrik.de/australia-oceania/australia.html),
  under [ODbL 1.0](https://www.openstreetmap.org/copyright). Keep the attribution in the map and database metadata;
  distributed derived databases must meet ODbL's attribution and share-alike requirements.
- City points: [Natural Earth populated places](https://www.naturalearthdata.com/downloads/10m-cultural-vectors/10m-populated-places/),
  [public domain](https://www.naturalearthdata.com/about/terms-of-use/), downloaded on 17 November 2026.

These maps do not provide a street-address or searchable-town index, elevation tiles, crop classification,
current hazards, or authoritative emergency-facility inventories. Existing mapped help points are incomplete
and may be outdated. Australian four-digit postcodes and state abbreviations need a separate address proposal;
the US address builder and search rules must not be presented as Australian address support.

Map geometry is selected where its bounding box intersects the area's box; long features may extend beyond it.
Data completeness follows the corresponding Geofabrik extract, especially near borders and the coastline.
The app remains offline: only build tools fetch these inputs.

## Build a review archive

From the repository root, using a current build Python as described in the README:

```sh
python3 -I -B packaging/build_packs.py map au-mel
python3 -I -B packaging/region_maps.py --zip-only au-mel
```

Repeat with another id to build its area. The output is
`derived/packs/region-zips/Lastbook-Map-au-mel.zip`. Record the source date, archive SHA-256,
feature and help-point counts, and native-app checks with each review build. A successful build is
not evidence that the whole state is covered or that facilities are operational.

Official setup offers only archives scanned, published and listed by the release maintainer on
`downloads.lastbook.org`. A review archive on a contributor's fork does not make it an official download.


## Broader extract areas for rural coverage

Eight additional definitions cover the envelopes of Geofabrik’s state/territory extracts. These are source extract areas, not guarantees of administrative-boundary precision, complete feature coverage or safe access. The standalone ACT extract uses the filename `act`; Geofabrik also includes ACT and Jervis Bay with NSW. The ACT extract does not establish Jervis Bay or external-territory coverage.

Source polygon URLs, SHA-256 hashes, vertex counts and rounded-out envelopes, checked 17 November 2026, are recorded in `AUSTRALIAN-EXTRACT-BOUNDS.json`. The official source listing is https://download.geofabrik.de/australia-oceania/australia.html .

| Id | Extract area | West, south, east, north |
| --- | --- | --- |
| au-act | Australian Capital Territory extract area | 148.75, -35.93, 149.41, -35.12 |
| au-nsw | New South Wales extract area | 140.99, -37.76, 160.08, -28.13 |
| au-nt | Northern Territory extract area | 128.67, -26.01, 140.43, -9.97 |
| au-qld | Queensland extract area | 137.99, -29.19, 154.21, -8.84 |
| au-sa | South Australia extract area | 128.99, -39.84, 141.01, -25.99 |
| au-tas | Tasmania extract area | 143.47, -56.87, 161.68, -39.19 |
| au-vic | Victoria extract area | 140.95, -39.24, 150.47, -33.97 |
| au-wa | Western Australia extract area | 109.92, -41.17, 130.32, -12.83 |

Actual broader review builds now cover all eight definitions. They use the dated 15 November 2026 sources, with input receipts, SQLite integrity checks, ZIP CRC checks and passing region-map scans. New whole-extract native UI checks are pending; the earlier metro maps and Melbourne suburb finder were checked in the native Mac app. No release manifest is silently changed by adding these definitions.

The review ZIP metadata is set to its actual dated input, rather than the generic builder’s build-time `data_as_of` fallback. The input receipt remains the authoritative provenance. Named-point place-finder sidecars are separate review artifacts from PR #90; they are not street-address/postcode indexes and have not changed the existing four-file region-map release contract.

The required source suite and region-source tests are run before publication. A full Mac release-bundle attempt stopped at missing `uv`, and the checkout does not hold the release-baseline data required by that recipe. Map SQLite/ZIP integrity and region-map scans are separate checks, not a claim that a complete release app bundle/package scan ran.

### Whole-extract review results

| Id | Feature rows | Mapped POI rows | Named point sidecar | Map ZIP bytes |
| --- | ---: | ---: | ---: | ---: |
| au-act | 204902 | 3747 | 187 | 14795527 |
| au-nsw | 2491059 | 58132 | 12659 | 220438034 |
| au-nt | 139947 | 3848 | 1019 | 14871632 |
| au-qld | 1801743 | 42877 | 6136 | 163931859 |
| au-sa | 825663 | 13443 | 1652 | 63819563 |
| au-tas | 521092 | 5259 | 1276 | 47358168 |
| au-vic | 2683842 | 46851 | 3054 | 200698704 |
| au-wa | 1016535 | 21290 | 3373 | 104741123 |

All eight map ZIPs together are 830,654,610 bytes. The separate place indexes contain 29,356 named points. Counts are database rows, not verified emergency facilities or complete address coverage. All queries in the review manifest (capitals and selected regional towns) resolve within their map boxes. The tests include a fixture-only disk-capacity adjustment: synthetic Setup recommendations must not depend on the real host disk having the production 5–20 GB reserve. Low-space checks and production code remain unchanged.
