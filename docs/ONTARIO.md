# Ontario: build and install an offline map

This contribution adds an Ontario-first OpenStreetMap map pack and optional
street-address pack, identified as `CA-ON`. `CA` remains California. It relates to
[the regional design discussion #31](https://github.com/Immortal-Protocols/lastbook/issues/31)
and [the broader Ontario/BC proposal #39](https://github.com/Immortal-Protocols/lastbook/pull/39).
The OSM-only path here is a smaller complete-province option for that shared
integration effort; it does not implement the official terrain/water/crop layers
proposed there. No generated data is committed or automatically published.

## Coverage

Included: mapped streets, building outlines, waterways, land shapes, towns and
services such as hospitals, pharmacies and fire stations. OSM coverage varies;
Geofabrik's extract may include features across Ontario's borders. A mapped
shelter may be a shelter structure, including a bus shelter; mapped services are
not confirmation of current availability. The map reports its source date and
OpenStreetMap attribution. Addresses are a separate optional download.

Place-name search includes settlements stored as points or polygons. For a
polygon name, the builder prefers a matching mapped town centre inside that
area, including a multilingual point such as `ᒨᓱᓂᔾ Moosonee`. Original names
and existing point locations are preserved. If no unambiguous centre is available,
the builder uses an interior point that avoids holes and gaps between islands.

Elevation/contours, aerial photos, crop surveys, official dam inventories, postal
area centroids and Ontario-specific survival-guide curation are separate work.
Unit preferences belong to the upstream units work; this PR keeps the existing
map distance display. Existing US state ids, address indexes and downloader host
restrictions are preserved.

## Build the map

Python 3.11+ with SQLite RTree and FTS5 is sufficient for the map builder.
Download a dated free OpenStreetMap GeoPackage from the
[Geofabrik Ontario page](https://download.geofabrik.de/north-america/canada/ontario.html),
extract the `.gpkg`, and read the archive's README for its snapshot date.
For example, `ontario-261116-free.gpkg.zip` says `2026-11-16T21:22:36Z`.

```bash
python3 -I -B packaging/build_ontario.py \
  --gpkg /path/to/ontario.gpkg --data-as-of 2026-11-16 \
  --out derived/ontario
```

Use the actual input's date; build time and filesystem modification time do not
establish source freshness. Completed output folders are never overwritten.

`derived/ontario/CA-ON/` contains:

- `Lastbook-Map-CA-ON.zip`: an independent map set in the existing install format;
- `manifest-v1.json`: a candidate setup manifest with measured sizes/checksums;
- `build-receipt.json`: raw input names, byte counts, SHA-256, snapshot/release,
  source/licence/attribution, output hashes, feature count and coverage gaps;
- `LastbookData/`: the unpacked map payload, **not a complete library**.

`map-set.json` also records the source receipt and hashes of its constituent files.
Current setup continues to use the existing archive SHA-256 and map-size checks;
this does not replace the separate upstream map-repair work.

## Optional addresses

Use a separate build environment with `duckdb==2.0.0`. Its `httpfs` and `spatial`
extensions run on the build machine only; the desktop app uses offline SQLite.

```bash
python3 tools/build_addresses.py --region CA-ON --release 2026-10-21.0 \
  --out derived/geo/addresses-CA-ON.sqlite
```

Pass `--addresses derived/geo/addresses-CA-ON.sqlite` to the map build command.
This adds `Lastbook-Addresses-CA-ON.zip`, its manifest entry, and an address-input
receipt. Postal codes retain six characters. Queries accept `ON`, `Ontario`, or
`CA-ON`, with spaced or compact postal codes. Missing/wrong house numbers, cities
or postal codes do not fall back to a neighbouring address. Existing US indexes
keep their old normalization, and a US-only installation still finds Ontario,
California as a city.

The pinned release's Ontario source is Statistics Canada's National Address
Register, 2024, via OpenAddresses. The builder stores the Statistics Canada Open
Licence and the adapted-data attribution in the SQLite metadata; the map's source
panel displays that notice. A different release requires reviewed
`--source-licence` and `--source-attribution` values. A release date is recorded as
an Overture release, not as the underlying address observation date.

## Try it locally

Use `--base-manifest /path/to/manifest-v1.json` when building to retain existing
library/model choices. For a source checkout, copy the resulting candidate
manifest to the existing source manifest location:

```bash
mkdir -p derived/release/setup
cp derived/ontario/CA-ON/manifest-v1.json derived/release/setup/manifest-v1.json
python3 -B app/main.py --data /path/to/LastbookData
```

Open **Library and local AI**, then **Choose a library or map zip, or AI model
file**, and select `Lastbook-Map-CA-ON.zip`. Keep the optional address ZIP beside
it: setup registers that separately pinned companion and checks both archives'
SHA-256. In first-run setup, select the local map ZIP, then choose a library and
start installation. Selecting Ontario replaces the All US map as well as other
state maps; it is not incorrectly counted as already included in All.

## Release and attribution

The generated manifest contains intended release URLs, not proof of hosted files.
Maintainers must upload accepted archives, independently verify the public sizes
and hashes, and merge the entries into the release manifest before offering an
official download. Source manifests and local input files do not widen the app's
network allowlist. Packaged releases use their bundled/published manifests as
before; no new environment override or Mac-specific build setting is required.

OSM data and derived databases use ODbL 1.0. Retain “© OpenStreetMap contributors”,
the licence and access to the distributed database under that licence. See
[OSM copyright and licensing](https://www.openstreetmap.org/copyright).
For Ontario addresses, retain the adapted-data notice required by the
[Statistics Canada Open Licence](https://www.statcan.gc.ca/en/reference/licence)
and the source listed in [Overture attribution](https://docs.overturemaps.org/attribution/).
Other countries/provinces on that page can have different sources and licences;
the Ontario notice is not a blanket licence for Canadian address data.

## Validation

```bash
python3 -B -m unittest app.tests.test_ontario app.tests.test_address_search
```

Tiny fictional fixtures need no download or socket. They cover building, input and
output receipts, safe archive layout, corrupt local files, installation over All
US, Canadian address preservation on upgrade, US compatibility, and actual map,
place and address routes. Node additionally exercises setup selection and size
calculations. Polygon-place tests cover exact-name search and map labels after
installation, multilingual town centres, concave areas, holes, separate islands,
distant namesakes, and extracts without a polygon-place table.
Run the full suite in CONTRIBUTING before proposing the change.
Real province checks and native-window checks should be reported separately from
fixture tests; Windows and Linux are not implied by a Mac result.
