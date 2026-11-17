# Regional maps with named-place search

This draft joins the Australian region definitions from #38 and GeoPackage place
builder from #90 to the map build/release/lifecycle proposed in #30. It complements
#63's richer PBF path; it does not add address/postcode search, alternate-language
name tags, new POI classifications or verified emergency facilities.

All sixteen Australian definitions declare `places: True`. Their normal map build
uses the same cached Geofabrik inputs and west/south/east/north box for both map
geometry and named-point search. The country is the public detail label, avoiding
a capital name matching every row. No second PBF download or spatial dependency
is needed. Other region definitions retain their existing build unless opted in.

```sh
python3 -I -B packaging/build_packs.py map au-act
python3 -I -B packaging/region_maps.py --zip-only au-act
```

Use the build Python documented in the repository. The source cache is under
`derived/packs/maps/region-source/`; output is `derived/packs/maps/au-act/` and
`derived/packs/region-zips/Lastbook-Map-au-act.zip`. A contributor review archive is
not an official Setup download: the maintainer still scans, publishes and lists
its whole-archive SHA-256 on the allowed release host.

## Archive and provenance

The legacy four-file contract remains valid. A set may additionally contain
`derived/geo/places.sqlite`, making five files in total. `map-set.json` lists every
actual geographic file and exact byte size; its byte total excludes itself. The
region scanner rejects missing/unlisted files, symbolic links, mismatched
inventories, invalid place schemas/search queries, out-of-box coordinates and the
existing private-path/household terms. The same set is zipped and sized for the
release manifest, so the finder cannot be omitted accidentally.

New opted-in builds add a `sha256` dictionary to map-set.json, covering every
listed geographic file. The scanner verifies these values against actual bytes.
Setup continues to verify the entire downloaded ZIP against its release manifest.
Ordinary staging/startup checks validate file sizes and checksum-metadata shape;
explicit repair also reads the per-file hashes. Legacy sets without those hashes
retain size checking, so they cannot detect same-size corruption this way.

The build records an input-archive receipt. A dated Geofabrik filename supplies
its snapshot date; a `latest` filename does not establish one. Reused caches may
carry a reviewed `source-receipt.json` with a snapshot date and matching extracted
file size. All inputs must supply the same recorded date for the map to claim
that date. Otherwise `data_as_of` is `not recorded`; the build timestamp is kept
separately. GeoPackage table-modification times are not treated as OSM snapshot
dates. Review manifests retain the exact input URLs and hashes.

## Install, refresh and repair

The existing Setup map-file rules already accept places.sqlite. Its inventory
moves that index with the map during staging, restart activation, content refresh
and rollback. A failed swap restores the prior index with the prior geometry.

Repair now has a separate installed-map item alongside content and optional AI.
A healthy set needs no map download. Missing/truncated files or a mismatch in a
new set's per-file hash fetch only the map archive when content is healthy. When
content also needs repair, the map is restored inside the same staged library.
Healthy maps are preserved during content repair, including valid custom sets
whose download is not currently listed. A damaged custom map without an available
source reports unavailability instead of reporting success or resetting to the
base map. The current library stays in place until normal restart activation.

Regional finder labels say towns/named places and do not offer US ZIP or address
support. A legacy regional map without an index disables that search visibly.
Australian nearby distances use metres/kilometres. Assistant map citations use
the installed map's or record's source, with no hardcoded US snapshot date.

## Validation scope

The required source suite plus place-builder, region-source and integration tests
passed: 356 tests run, two skips, on Apple Silicon macOS with Python 3.14.2.
The focused integration tests use a real synthetic GeoPackage through both actual
builders, privacy scan, ZIP, Setup unpack, map replacement, refresh and rollback.
The Setup HTTPS fixture covers healthy/no-download, missing, truncated, same-size
corrupt, content-only repair, both-components repair and unknown custom sets.
Source-date and incomplete-digest metadata cases are covered. JS syntax,
ship_app_files and diff checks pass.

Actual integrated Australian review builds and their receipts are recorded with
the review release separately. Native window checks remain pending while the Mac
is locked. Earlier metro map and Melbourne finder checks do not prove these new
runtime paths. No complete platform release bundle/package scan or Windows run
is claimed; the local release recipe still requires unavailable release-baseline
data and build tooling.

Original earlier review releases are retained unchanged. This proposal does not
silently replace their four-file map sets with incompatible downloads, alter
runtime network hosts, bundle personal-use first-aid PDFs or claim that mapped
POIs are working emergency facilities. Source data remains © OpenStreetMap
contributors, ODbL 1.0, via Geofabrik, with the original attribution retained.
