# Public supplement review split — 27 November 2026

PR89 now contains public references, public guide links, build/composition tools and
the shared reader-file availability fix. Personal and nonprofit original workflows,
their installer instructions, dedicated/ordinary source cards and maintenance tools
are moved to follow-up branches. Historical source and release tags remain intact.

The manifest and all 125 source HTML files are byte-identical to b240e57. The public
builder produces 125 records without originals, private extracted text or indexes.
The Household/Rural guides retain 297/302 resolved public references; Health has16.
Every resolved regional reference points to an existing public source. No personal
or nonprofit source card remains in this branch. The historical hurt baseline audit
retains its original hash and exact commit, with a documented public-only projection.

## Full entry-point views

These are six uncropped full-page browser screenshots of this branch's actual web
UI and engine on macOS, light mode,1280px width. The standalone125 public library
is the only material used. The absent case moves pages/au aside while preserving
catalogue bytes/mtime and index; it does not delete or rewrite source metadata.
No private library, model, original or account information is used.

| Entry point | Public sources absent | Public sources installed |
| --- | --- | --- |
| Household direct route | [Full view](review/au-public-entry-20261127/household-absent.jpg) | [Full view](review/au-public-entry-20261127/household-installed.jpg) |
| Rural direct route | [Full view](review/au-public-entry-20261127/rural-absent.jpg) | [Full view](review/au-public-entry-20261127/rural-installed.jpg) |
| Guides entry list | [Full view](review/au-public-entry-20261127/guides-absent.jpg) | [Full view](review/au-public-entry-20261127/guides-installed.jpg) |

Installed: both full guide entry pages show all public situation choices, source
limits and preparation/deeper-reading sections. Absent: regional guide tiles hide,
and direct routes show the existing “That page isn’t here” state. Source-free
ordinary guides remain. The existing move/restore regression additionally verifies
restoration with the actual catalogue cache warmed and unchanged catalogue mtime.
Browser history shown in the installed list contains only the two public guides.

The images were visually inspected from top to bottom. This is browser evidence,
not a new native Mac/Windows, dark-mode, clinical or community-review claim.
[Machine-readable source/appearance scope and image hashes](AUSTRALIA-PUBLIC-SPLIT-REVIEW-20261127.json).

## Validation

843 required public-branch tests pass on Python3.14, with five skips and eleven
upstream expected failures. All70 focused public-source, composition and guide-file
checks pass on Python3.14 and app-build Python3.11.18. Source was stable during the
full run; only validation documentation followed.
The first sandbox-only full attempt could not bind test sockets; it is not counted
as successful. The approved run uses unchanged production network rules.
No installed app/library migration, rebuild or release asset replacement occurs.
