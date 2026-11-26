# Australian capital and state/territory extract maps

This contribution proposes offline maps around Australia's eight state and territory capitals,
plus fourteen broader state/territory and external-territory extract areas.
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

The four-file map archives do not provide a street-address or searchable-town index, elevation tiles, crop classification,
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

Actual broader review builds cover all eight definitions. They use the dated 15 November 2026 sources, with input receipts, SQLite integrity checks, ZIP CRC checks and passing region-map scans. On 26 November, the combined Australian Mac review app also drew the full Victorian extract, found Mildura/Ballarat and showed metric nearby distances. A corrected ACT map displayed Canberra's city label at zoom 8. The other six broader extracts retain engine/data checks. No release manifest is silently changed by adding these definitions.

The regional CLI accepts the source and recorded snapshot date; an unknown date is `not recorded`, rather than the build date. The callable `build(src, dst, metadata, clip=None)` API used by Spain remains available without import-time argument parsing. The input receipt remains the authoritative provenance. Named-point place-finder sidecars are separate review artifacts from PR #90; the opt-in five-file lifecycle proposal is #101. Neither supplies street-address/postcode search.

The current branch combines #30 at `da577d0` with main `51658f5`, retaining optional map skipping, current country dispatch and separate Canadian provinces. The required suite plus regional checks passed: 809 tests, five skips and eleven upstream expected failures. Converter/API and Spain checks passed again after the capital-label fix. The combined Australian source passed 840 tests and the full Mac build recipe, including TLS, i18n, package/privacy scan and strict ad-hoc signature verification. Its frozen private review app was installed and checked natively. No Windows, notarization or upstream-release claim is made.

Geofabrik classifies Canberra as `national_capital`; the converter now normalizes that to the renderer's `city` class for city font, priority and minimum zoom. The cached source population puts Canberra at zoom 5 rather than the old fallback 14. [Separate corrected ACT/NSW integrated review maps](https://github.com/pilkster/lastbook/releases/tag/australia-map-label-review-2026-11-26) retain the 15 November snapshot and feature/place counts. Both passed privacy/inventory, SQLite/FTS/bounds, per-file SHA, full Setup unpack/CRC and zoom-8 city-label engine checks with sockets forbidden. Only ACT received this native capital-label check. Earlier releases below remain unchanged.

### Original four-file whole-extract review results

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

[Whole-extract review downloads, source receipts and checksums](https://github.com/pilkster/lastbook/releases/tag/australia-state-maps-review-2026-11-17) are separate from the earlier three capital-area ZIPs. Named-place sidecars are included as a separate archive; integrating them into the release scanner, map switching and repair remains a maintainer decision alongside #63 and #90.

Read-only checks through the existing application engine also passed with sockets forbidden: 30 capital/regional-town queries across all eight broader maps returned the exact named place and a nonempty detailed zoom-15 tile; nearby-point queries executed. `AUSTRALIA-STATE-ENGINE-CHECKS.json` in the release records these checks. They do not replace native window verification.


## Separate external-territory extracts

Six further definitions use Geofabrik's own external-territory polygons and
dedicated extracts,reviewed26 November2026. They are offered under Australia in
the region grouping; their short ids are build ids,not assertions that every
territory has an ISO3166-2 subdivision code. Rounded-out source envelopes,polygon
hashes and the dated24 November review-source receipts are recorded in
`AUSTRALIAN-EXTRACT-BOUNDS.json`.

| Id | Extract | West,south,east,north |
| --- | --- | --- |
| au-ac | Ashmore and Cartier Islands extract area | 122.56, -12.85, 124.05, -11.89 |
| au-cx | Christmas Island extract area | 105.29, -10.83, 106.0, -10.17 |
| au-cc | Cocos (Keeling) Islands extract area | 96.45, -12.56, 97.25, -11.54 |
| au-csi | Coral Sea Islands extract area | 146.86, -30.58, 160.43, -14.98 |
| au-hm | Heard Island and McDonald Islands extract area | 71.99, -53.55, 74.46, -52.66 |
| au-nf | Norfolk Island extract area | 167.62, -29.47, 168.35, -28.75 |

These sources vary greatly in detail. Ashmore/Cartier and Coral Sea contain no
eligible named POINT places; this is not proof that islands,settlements,services
or geographic names are absent. Places held only as polygons are not inferred
as points. Geometry-only maps remain valid four-file sets; the separate #101
integration can add a finder only where its source supplies named points.
Heard/McDonald map labels,including old station names,do not establish occupancy
or services. The free extract schema does not establish complete shorelines,
reefs,depths,tides,marine hazards,landing rights or safe navigation. No access,
permit,rescue,facility-availability or emergency-contact assumptions follow from
a feature on the map. Australian Antarctic Territory remains a separate gap.
Jervis Bay remains included with the NSW extract; it is a distinct internal
territory,not part of ACT and not an external territory.


## External-territory review results — 26 November 2026

The six separate24 November Geofabrik snapshots build7,776 feature rows and42
eligible named points in total. Four have place indexes; Ashmore/Cartier and
Coral Sea remain geometry-only sets. All six actual ZIPs pass privacy/inventory,
SQLite/FTS/bounds,full Setup unpack/CRC and per-file SHA checks,plus real engine
tile/search queries with sockets forbidden. A real five-file→four-file→five-file
map switch removes stale place data and restores the new index without changing
the library catalog. These are source envelopes and sparse mapped features,not
complete island names,shorelines,reefs,marine navigation,access rights,operating
facilities or rescue arrangements. Australian Antarctic Territory remains a gap.

Native review caught and corrected two display defects before publication:
source island/islet polygons now supply ground where Natural Earth's coarse
world base omits an island; populated-place polygons are not treated as land.
Protected-area polygons use a separate boundary layer,rendered as dashed outlines
without land fill,so marine reserves cannot recolour ocean as land. The server
keeps their polygon/hole clipping. Older sources without the optional places-area
layer remain supported; the callable converter API used by Spain is retained.
The matching renderer/server source is needed for protected-area outlines.

The required contribution/regional suite passed831 tests(five skips,eleven
upstream expected failures) under PYTHONUTF8=0 after the corrections. Integration
and converter checks passed9 tests; the upstream PBF-builder suite passed9 with
its optional development dependency. No new shipped dependency or runtime
connection was added. Web syntax,ship-app files,i18n,package/privacy scan,strict
ad-hoc signature and outbound-IP-denial self-check passed for the matching private
frozen Mac app. TLS/setup inputs are unchanged from their verified predecessors.

Final Norfolk,Bantam on Cocos and Flying Fish Cove on Christmas Island were
checked natively at street zoom:finder,streets/buildings,land/ocean rendering,
protected boundaries,source attribution and metric nearby distances. Victoria
was restored byte-for-byte,with its3,054 named points and seven original layers.
The private377-record library and237 guide references remain intact. Other three
new territory maps have archive/engine checks,not native-window review. These
checks do not establish complete coastal coverage,facility operation,Windows,
notarization or long-idle stability; the earlier idle-page incident is unresolved.

[Six external-territory review downloads,provenance and checksums](https://github.com/pilkster/lastbook/releases/tag/australia-territory-maps-review-2026-11-26)
are contributor files,not official Setup downloads. All earlier state/capital
review downloads remain unchanged. Official scanning/publication/manifest listing
still belongs to the release maintainer.
