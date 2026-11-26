# Guide source availability and review scope

The reported failure left `catalog.json` in place but moved the Australian source
folder out of the library. The catalogue cache only followed catalogue mtime, so
all three public regional guides and their links still appeared.

`server.doc_here` now checks the actual file on every guide resolution. Both
individual readings and `requires_docs` use it. Moving files back restores their
links without a catalogue rewrite or index rebuild. Source-free ordinary warning
text remains; unavailable citations are omitted. Explicit configured remote videos
retain their existing availability behavior.

The regression builds all 124 public records offline and uses the actual
`server.catalog` cache. It warms that cache, moves/restores a non-required bat
factsheet, then moves/restores the complete `pages/au` folder, leaving catalogue
bytes and nanosecond mtime unchanged. It verifies individual link filtering,
hiding all three public regional guides, preserving ordinary guide warning text
and restoring the original resolved guide output. It uses only temporary output.

Run the exact regression:

```sh
python3 -B -m unittest tools.test_build_australia_reference.Reference.test_built_guides_follow_moved_sources_with_catalogue_left_intact
```

The current content diff excludes the independent runtime changes:

- [#487: HTTP linked-reading context](https://github.com/Immortal-Protocols/lastbook/pull/487)
- [#497: desktop linked-reading context](https://github.com/Immortal-Protocols/lastbook/pull/497)
- [#491: Mac modal heartbeat timing](https://github.com/Immortal-Protocols/lastbook/pull/491)
- [#493: document language/read-aloud](https://github.com/Immortal-Protocols/lastbook/pull/493)
- [#494: Arabic/Han search](https://github.com/Immortal-Protocols/lastbook/pull/494)

Australian data and guides can be reviewed and built independently. The relevant
runtime PR supplies each optional reader/search/speech behavior. Historical
release/runtime check notes in AUSTRALIA-CONTENT.md remain historical evidence;
they do not describe code still included in the content diff.

## Validation on 27 November 2026

The isolated content branch passed 849 tests; the integrated map/place/runtime
branch passed 985. Each reported five skips and eleven upstream expected
failures. All 73 focused source/availability/personal/composition checks passed
on development Python 3.14 and the app-build Python 3.11.18. The separate native
reader patch passed all 204 bridge tests on both interpreters. No source corpus
or data archive bytes changed for this availability repair.

## Shared reader path policy

The follow-up review found that an existing catalogue path could still be offered
when the reader would refuse it. The reader's on-disk checks now live in
`engine.library.library_file_ok`; the reader method delegates to that same
function and guide availability uses it with the reader's served-folder policy.
The reader's existing file policy is preserved, including hard-link refusal and
checks on requested and resolved paths. Guide paths also stay within the reader's
library URL scope; explicit remote-video records do not bypass these checks.

A filesystem control exercises the actual reader's path/translation methods and
resolved guides together. It verifies ordinary files, an allowed internal link
and an explicitly served external folder, then refuses escaping/hidden links,
hard links, root tools, hidden folders, cookie/auth metadata, parent traversal and
missing files. Refused sources disappear from ordinary readings and required
regional guides while source-free warning text remains. The regional fixture now
uses files under pages/, where the reader can actually open them.
