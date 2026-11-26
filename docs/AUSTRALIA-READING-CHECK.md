# Check Australian readings after using Lastbook

The full composition verifier checks an exact creation snapshot. Normal app use
can change a log or add a file, so that check can report a difference even when
the Australian readings and index still match their sources.

Use the separate reading check to inspect the installed Australian sources after
normal use. It changes no library files, downloads nothing and does not repair
or replace anything:

```sh
python3 -B tools/verify_australia_readings.py --data "/path/to/LastbookData" \
  --require public --require personal --require trauma
```

Use only the collections you expect: `public` for the public Australian supplement,
`personal` for the six- or 35-original ANZCOR selection, and `trauma` for the
separate nonprofit MHFA original. Repeat `--require` as needed. For a public-only
library:

```sh
python3 -B tools/verify_australia_readings.py --data "/path/to/LastbookData" --require public
```

The command checks every recognised collection it finds. `--require` also catches
an expected collection that has been removed completely. Without it, the report
lists only the collections found; it does not infer what used to be installed.
A library with no recognised Australian collection is refused.

## What the two checks prove

| Check | What it checks | Effect of later app activity |
| --- | --- | --- |
| The matching composition tool's existing `--verify` | The full recorded snapshot, including base files, receipts, catalogue, index and listed app logs | Later edits or extra files remain differences; this behavior is unchanged |
| `verify_australia_readings.py` | Matching-version Australian source metadata, notices/conditions, original files, extracted text and every source search page; SQLite/FTS integrity on a temporary index copy | Unrelated logs/history can change; relevant source or index changes during checking stop the check |

A successful reading check does not clear a full-snapshot difference in another
file. Review that difference according to the files it concerns. Maps, other
base-library files, app/guide assets, source currency and clinical approval are
outside this command's source comparison.

## Source and search verification

The check reconstructs expected collections offline from the matching checked-out
source metadata. Public readings use the reviewed repository snapshots. Personal
and nonprofit originals are read from their existing library locations and
checked against the pinned original hashes. Their PDF text is extracted again;
all expected physical-page search rows are compared with that reconstruction.
The personal source directory is regenerated too, so its catalogue hash is not
used as its own independent authority.

The comparison checks catalogue fields and source restrictions, original bytes,
source conditions/credits, page numbers, titles, collection/category/path and
search text. Source search wording, ordering and page boundaries remain exact;
only line-ending form is normalised. Flat text-file comparison tolerates whitespace
layout differences, including platform newline conversion; it cannot replace the
per-page search comparison or original-file hash check.

The target search database is copied as an ordinary read-only file. SQLite opens
only the private temporary copy. Its
[FTS5 integrity check](https://www.sqlite.org/fts5.html#the_integrity_check_command)
checks index consistency, including agreement with stored content. No special
SQLite command or database write is issued against the library.

The temporary directory is outside the library and private to the current user.
It briefly contains a copy of the search index and reconstructed readings, which
can include private base text and personal-use sources. It is removed on normal
completion or a handled failure. Nothing is uploaded or made public. A temporary
directory configured inside the library is refused before the check creates it.

Use the tool revision that matches the installed source manifests. A newer source
manifest, different PDF text-extraction version or an intentional local source
edit can produce a mismatch; the command does not silently accept it as a new
reference. PDF checking uses the existing `pypdfium2` platform dependency. Public
HTML-only checking needs no PDF renderer.

## If a check fails

Missing, changed or unreadable originals, altered source conditions, stale or
malformed source search pages, mismatched manifests and damaged search structures
are errors. Source files and metadata must be ordinary files; links, hard links
and unsafe path components are refused. Active SQLite journals, concurrent
relevant edits or an index changing during the copy require closing Lastbook and
other SQLite users and retrying from a stable library. Empty recognised journal
sidecars remain supported.

Keep the original library and investigate the named difference. If rebuilding is
needed, use the matching composition instructions and a new output. The command
has no download, overwrite, repair or update mode. It is not official Setup
Check/Repair, which still cannot identify these unlisted local compositions.

All source rights remain. Personal originals and a mixed private library stay
private. The separate MHFA reproduction grant remains limited to nonprofit use
with credit and clears no other source. Source integrity is not current advice,
training, a clinical review or a guarantee of local services.

[Exact validation scope](AUSTRALIA-READING-CHECK-REVIEW-20261127.md).
