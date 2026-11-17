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
