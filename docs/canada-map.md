# Canada maps from a local OpenStreetMap extract

Canada is an additional offline map database, not a replacement for the US pack.
The renderer, service pins, nearest-place search and place finder use both when
installed. A Canada-only map also works. The Map area control retains the US
lower-48 overview and offers all Canada plus all ten provinces and three
territories. Choosing an area changes the view; it never filters available data.
Saved personal areas continue to take precedence when opening the map.

The all-Canada view includes the Arctic islands. On a small screen, select a
province/territory or search for a town to reach useful street detail. Region
views are conservative extract envelopes rather than precise border boundaries.
Their public source is [Geofabrik's extract index](https://download.geofabrik.de/index-v1.json).
The country overview follows the Natural Earth country outline already used by
the map. Extract bounds remain separately exposed in `/api/map/info`: neighboring
features may extend beyond Canada and should not distort the country overview.

## What is included

The converter streams a local OSM extract into the existing `feat`, RTree and
`poi` contracts. It keeps selected roads/paths, rail, inland water, coastline
lines, land areas, buildings, places and services. Multipolygon outer and inner
rings remain separate for the renderer's even-odd fill. OSM node/way/relation IDs
are retained in lineage tables. UTF-8 names and province tags are searchable
through SQLite FTS5. Map metadata records the extract SHA256, replication date,
converter, attribution and limitations. Pins and nearby records show their source
and data date; these are mapped records, not confirmation of an operating service.

This does not add Canadian aerial imagery, elevation, routing, comprehensive
addresses/postcodes, or live opening/closure information. Area POI positions are
approximate bounding-box centers; named-water search uses the same approximation
and does not identify a safe shoreline or access point. Coastlines are outlines,
not generated ocean fill polygons. OSM coverage varies, particularly in remote
areas. US government resource layers keep their original geographic coverage.

## Build and validate without changing an installed library

Obtain a Canada `.osm.pbf` extract separately from a trusted source such as
[Geofabrik](https://download.geofabrik.de/north-america/canada.html). Record its
replication timestamp and independently recorded SHA256. No tool below downloads
data or installs it into a library. The full-country build needs substantial free
disk space for the source, output, node-location index and staged copies. Output
size and time depend on the extract. Choose a node index explicitly; the tool
does not guess usable RAM from the operating system or choose a backend silently.

- `--node-index sparse_mem_array` keeps the location index in RAM and avoids the
  disk-index bottleneck when sufficient memory is available. Budget up to roughly
  **32 bytes per input node for the index**, plus multipolygon assembly, SQLite,
  Python and system headroom. Use an independently measured input node count,
  not the number of rendered map features, to estimate this. Keep enough RAM
  free to avoid swapping.
- `--node-index sparse_file_array` stores the index in the staging directory
  (roughly **16 bytes per input node**), but still relies on filesystem caching
  and memory for the rest of the build. Use fast local SSD storage. File-backed
  does not mean low RAM is automatically practical: a full-Canada build can
  thrash badly on a low-memory machine, particularly with a slow disk. Use a
  better provisioned build machine or a smaller extract instead of expecting
  this mode to solve insufficient RAM.

These index estimates and the warning that file-backed indexes trade performance
for memory follow the [official Osmium index documentation](https://docs.osmcode.org/osmium/latest/osmium-index-types.html).
They are not a whole-build RAM guarantee. No full-country rebuild is performed
by the regression tests.

Use Python 3.11+ on macOS/Linux in a separate build environment:

```sh
python3 -m venv /path/to/map-build-env
/path/to/map-build-env/bin/pip install osmium==4.3.2
/path/to/map-build-env/bin/python tools/build_canada_map.py \
  /path/to/canada.osm.pbf /path/to/new-staging-directory \
  --source-sha256 RECORDED_64_CHARACTER_SHA256 \
  --data-date REPLICATION_TIMESTAMP_WITH_TIMEZONE \
  --node-index sparse_mem_array
```

The output directory must not exist. The digest is verified before output is
created. An interrupted or unsuccessful build leaves diagnostic staging files;
it never replaces installed data. A completed conversion writes
`canada-map.sqlite.building`, `canada-places.sqlite.building`, progress and a build
receipt. The `.building` names deliberately do not imply validation or installation.

Before creating the staging directory, the builder checks free space on the
output filesystem. Its baseline headroom is the greater of 1 GiB or five times
the compressed input size for the memory index, eight times for the file index.
These are conservative planning heuristics, not a bound on arbitrary extracts;
`--min-free-gib N` raises the required reserve when source/node-count estimates
call for more. Source input, staged copies and other workloads need their own
space. Filesystem quotas and concurrent writers can still exhaust space later.

SQLite spills to the owned `sqlite-tmp/` subdirectory inside the new staging
directory. `SQLITE_TMPDIR` and `TMPDIR` are set before either database opens,
with `temp_store=FILE`; external temporary directories are not used for those
spills. Indexing does not need an accidental writable system `/tmp` or a large
RAM-backed temporary filesystem. Out-of-space errors identify the scratch
filesystem and retain the incomplete staging directory for inspection. Free
space or choose another filesystem, then restart into a **new** directory.

```sh
python3 tools/validate_canada_map.py \
  /path/to/new-staging-directory/canada-map.sqlite.building \
  /path/to/new-staging-directory/canada-places.sqlite.building
```

The validator opens both databases read-only. It checks SQLite integrity,
matching provenance, lineage, RTree/index membership, FTS lookup and deterministically
samples about 1,000 decoded features. `--all-geometry` checks every geometry and
polygon ring. It reports `VALIDATED_NOT_INSTALLED` and changes no names or files.
National counts alone are not evidence of coverage in every region: inspect
representative towns, services and tiles in all 13 provinces/territories, including
the Arctic, against the input extract before distributing an actual dataset.

For an existing US place finder, merge into another new staged database:

```sh
python3 tools/merge_canada_places.py \
  /path/to/pristine-us-places.sqlite \
  /path/to/validated-canada-places.sqlite \
  /path/to/new-merged-places.sqlite \
  --base-sha256 TRUSTED_PRISTINE_BASE_SHA256 \
  --canada-map /path/to/validated-canada-map.sqlite
```

The original US place rows and metadata are preserved. Canadian IDs are remapped
and their OSM lineage is retained; the optional map adds named-water search.
Inputs with active WAL contents, an augmented Ontario/Canada base, a mismatched
digest or an existing destination are rejected. Publication uses an atomic link
to a completely closed staged database; rerunning cannot append duplicates or
overwrite a destination. The base digest must come from a trusted pristine pack,
not from hashing an already augmented database. Canada-only libraries can use the
validated Canadian places database directly instead of merging.

Installation is a separate, reviewed data operation: retain backups, close the
app, and install the validated map as `derived/geo/canada.sqlite` and the selected
standalone or merged places database as `derived/geo/places.sqlite` in the chosen
data folder. The pack scanner accepts the optional `canada.sqlite` under the same
privacy/file checks as the US map; it still rejects WAL and staging files. No
setup manifest, automatic download or published Canada pack is added by these
tools. Keep the existing US `map.sqlite`, `national.sqlite`, resource,
terrain and imagery files. Never distribute source extracts or generated
databases in the source repository. Attribute OpenStreetMap contributors and
Geofabrik and follow the [ODbL](https://opendatacommons.org/licenses/odbl/1-0/).

## Regression checks

```sh
python3 -B -m unittest app.tests.test_canada_map
```

Standard-library tests cover Canada-only rendering, mixed US/Canada sources,
metadata fallback, provenance, high-latitude nearest results, date-line geometry,
local search beyond the rank candidate limit, staged merge preservation/rejection,
and read-only validation. With osmium installed, an invented PBF fixture additionally
exercises the real parser, split multipolygon assembly/holes, native geometry
decoder, Unicode FTS, road link zoom and SHA mismatch rejection. No real household
coordinates, downloaded country dataset, local server or inference runner is used.
The invented PBF is built with both node-index backends and their map/place rows
are compared. Tests also verify owned scratch is configured before database
connections, file-backed SQLite temporary storage, disk-headroom rejection and
required backend selection. Place-source labels are checked for Canada-only
and mixed gazetteers so absent US providers are never claimed.
