# Reading-maintenance verification — 27 November 2026

The installed library's exact snapshot check reports a change to
`derived/logs/lastbook.log` after normal app use. Its five previously recorded core
data hashes still match. The new reading check verifies source integrity after
such activity without weakening or replacing the full snapshot verifier.

## Software checks

- **908 isolated-content tests and 1,056 combined tests pass**, each with five
  skips and eleven upstream expected failures.
- The **20 new controls pass on Python 3.14**. All **82 focused source,
  distribution and maintenance cases pass in that full suite and in the focused
  Python 3.11.18 app-build run**.
- The new controls cover a changed app log, unchanged library bytes/metadata,
  read-only target files/directories, no target SQLite connection, source loss,
  altered originals despite a rewritten catalogue hash, changed text/index
  content, page boundaries, duplicate pages and titles, source restrictions,
  credit/nonprofit declarations, public/personal notices, an entirely removed
  required collection, unrelated base edits, links/hard links, active journals,
  damaged FTS structures, concurrent edits, malformed metadata/index text and a
  temporary directory configured inside the library.

The full test commands are in CONTRIBUTING.md. The existing composition and
snapshot verifiers are unchanged. The source comparison uses the existing
builders and pinned metadata, rather than accepting a catalogue's own hash as
independent proof of the expected reading or source directory.

## Actual installed library

The real check passes on **Python 3.11.18 and 3.14.2**:

| Collection | Readings | Search pages |
| --- | ---: | ---: |
| Public Australian supplement | 125 | 125 |
| Personal Basic Life Support / First Aid selection | 36 | 264 |
| Nonprofit MHFA adult traumatic-event original | 1 | 7 |
| Total | 162 | 396 |

Both runs inspect 331 relevant files, make zero Python socket attempts and make
zero SQLite connections to the target database. SQLite operates on the private
temporary copy. All five core data hashes remain byte-identical before and after.
The documented direct CLI command with all three `--require` options also passes.
No original, index, metadata or source restriction is repaired, rewritten or fetched.

The installed library remains 476 records. Its private and nonprofit source
conditions remain in force. Other base files, maps, app/guide assets and mutable
logs/history are outside the source comparison; the copied search database still
receives SQLite and FTS integrity checks. Source currency and clinical approval
are not established by this check.

## Deployment and publication scope

Only tools, tests, documentation and CONTRIBUTING.md change. All 57 ordinary ship
assets are byte-identical to the preceding frozen app's assets; its additional
pinned Setup manifest is unchanged. No app rebuild, library migration or new
native-window check is needed. The installed signed app, source data and existing
125-record / nonprofit-source release assets and tags remain unchanged.

The new command is available from current PR89 source. Earlier release tags remain
historical and do not implicitly acquire this later tool. No private original,
extracted body/index, full database, app/profile or raw research is published.

[Commands, scope and failure handling](AUSTRALIA-READING-CHECK.md)
