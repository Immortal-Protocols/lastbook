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

After the shared reader-policy and personal-composition additions, the isolated
content branch passed 866 tests; the integrated map/place/runtime branch passed
1,014. Each reported five skips and eleven upstream expected failures. All 90
focused source/availability/personal/composition checks passed on development
Python 3.14 and the app-build Python 3.11.18. The separate native
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


The installed Mac review app was rebuilt with this same shared file predicate.
All four Australian guides remained available. The personal first-aid guide
opened its snakebite citation at physical PDF page 3; Page and Text views agreed,
Ask retained that page as context, and Back returned to the source. No question
or audio was submitted. This was a selected native check of the existing private
profile, not a native-window test of the separately composed output.

Post-native checks preserved 445 records, all 131 Australian content hashes,
42 personal search units, all 12,792 original non-public search rows, and Victoria
map hashes. The full app signature and outbound-IP-denial self-check passed.
No source content or public release archive changed.

## Optional originals in a full library

`tools/compose_au_personal_first_aid.py` now provides an explicit personal step
after public composition. A real closed 438-record library became a new
445-record copy using six already obtained originals (41 PDF pages plus the
source hub). All 1,507 retained files, all 12,874 base search row identities and
bodies, the public composition receipts and the existing personal-use marker
were preserved. The new private snapshot verified all 1,530 manifest files and
42 added search units. The reader resolved all seven added records and search
found all six PDFs with physical page references.

The tool requires either an explicit cache or `--download`; it does not fetch
implicitly. It refuses an existing destination, collisions, unsafe source trees
and active database journals. It creates a complete private-copy manifest and
source receipts. Base public receipts remain provenance for their original
snapshot; the new personal verifier checks the completed copy. Setup Check and
Repair remain unavailable for this local composition. Public pack selection
excludes the originals and personal hub at every pack size.

See [the personal-source workflow](AUSTRALIA-PERSONAL-FIRST-AID.md) for exact
commands and source restrictions. No personal PDF, extracted body, private index
or app/profile is included in this contribution or its release assets.
