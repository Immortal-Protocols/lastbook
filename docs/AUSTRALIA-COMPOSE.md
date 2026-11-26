# Add Australian readings to a copy of your library

The reviewed supplement contains 121 public Australian readings. You can build it
as a separate small library, or add it to a **new copy** of an existing Lastbook
library. The latter keeps your existing documents, search rows, maps, models and
other files. It never replaces the original library or changes app settings.

Use Python 3.11 or later and this contribution's source checkout. The tool uses
only the Python standard library and the committed, reviewed Australian snapshots;
it downloads nothing. Close Lastbook and any SQLite tools using the base first.

```sh
python3 -B tools/compose_australia_reference.py \
  --base "/path/to/existing/LastbookData" \
  --output "/path/to/new/AustralianLastbookData"

python3 -B tools/compose_australia_reference.py \
  --verify "/path/to/new/AustralianLastbookData"
```

Choose a new output folder outside the base. The tool refuses an existing output,
catalog or search-id collisions, conflicting source paths, symbolic links, special
files and SQLite journals/WAL files containing data. It checks for base changes during the build, assembles
the copy in a temporary sibling folder, and publishes the finished directory.
Failures remove its temporary work. Keep other processes from changing either
path while it runs. The original library remains the rollback copy.
Publication uses an exclusive directory rename on macOS, Windows, and Linux with
`renameat2`; systems lacking that operation refuse publication safely.

SQLite may leave a zero-byte WAL and its shared-memory index after a read-only
connection closes. These checkpointed pairs are accepted only beside a SQLite
database; non-empty WAL/journal files and unpaired shared-memory files are refused.
Other databases and their accepted empty sidecars are retained byte for byte. The
search index is rebuilt as a self-contained database without its old sidecars.
This does not replace the requirement to close the app and other SQLite users.

This is an **initial addition**. A library already containing Australian supplement
metadata is refused, including an older version. It is not an update/migration tool
and does not silently replace similarly named records. To use a newer supplement,
compose again from your retained original library into another new folder.

On APFS, files use copy-on-write clones when available. Other systems make full
copies and need enough free space for the complete base plus the supplement.
No hard links are made. A copy failure, including insufficient space, leaves the
base untouched. Reading and hashing a large library can take time.

## Open the combined copy

```sh
python3 -B app/main.py --data "/path/to/new/AustralianLastbookData"
```

Use the matching contribution runtime for the Australian guides and ordinary
guide links. A data folder does not update the guide JSON bundled inside an old
app. The tool adds readings; it does not download/install Australian maps or merge
the separate map/place runtime PRs. Maps already in the base are copied unchanged.

Search for `Australian household`, `livestock`, `Triple Zero` or `CB radio`.
Household and rural guides have equal coverage. Source cards retain jurisdiction,
dates, licences and limits. The tool adds no personal first-aid PDFs: cards for
separately installed originals appear only if those records are present.

## Integrity, Setup and privacy

The output's `pack.json` identifies it as `local-australia-reference`, records its
original pack identity and uses a local content revision. It must not pretend to
be the original official download. **Setup Check/Repair are unavailable for this
local pack.** Choosing an official replacement library is not a way to preserve
these additions. Use the read-only `--verify` command for this copy, or recreate it
from the retained original. The production manifest and downloader are unchanged.

`pack-manifest.tsv` covers every regular file in the combined copy except itself.
`--verify` checks those sizes/hashes, rejects unlisted files and unsafe paths, and
checks the catalog count, local identity, SQLite integrity and search-row count.
Run it with the app closed. It detects differences from the recorded composition;
it does not authenticate a publisher, certify an already damaged base, or supply
missing updates. User edits made after composition will be reported as changes.

`AUSTRALIA-SHA256SUMS.tsv` covers only the added Australian source HTML/text and
`AUSTRALIA-REFERENCE.json`; it does not describe a standalone catalog or index.
`AUSTRALIA-COMPOSITION.json` records counts, the base catalog hash and these limits.
The catalog, index, summary, pack identity, contents list and full checksum manifest
are rebuilt; other base files are retained. Existing search row ids, unrelated
SQLite tables, summary diagnostics and private-use markers are preserved.

**The complete output inherits the base's privacy and redistribution restrictions.**
It can contain private PDFs, extracted text, search material, notes, models and
other personal files. The public licence of the added readings does not license
the rest of the library. This tool does not create or publish a shareable archive.
Do not redistribute a composed private library. Public supplement downloads remain
separate and exclude private originals and personal index material.

This contributor workflow is available before upstream acceptance. It does not
make the supplement an official Setup download or imply maintainer endorsement.
