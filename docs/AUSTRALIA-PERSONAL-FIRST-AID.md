# Personal-use Australian first-aid references

ANZCOR permits viewing, downloading and printing its documents for personal or
educational use, but restricts public redistribution and modification without
written consent. Its terms are at https://www.anzcor.org/disclaimer-and-copyright .
The public Australian reference supplement therefore does not bundle these PDFs.

`tools/build_au_personal_first_aid.py` offers a separate personal-use path: it
downloads hash-pinned, unmodified official originals only when explicitly run,
then makes a local catalog and page-level search index. The **tool and source
metadata** can be contributed; its output is **not a redistributable library**.
No ANZCOR PDF or extracted guideline text is committed to this repository.

```sh
python3 -B tools/build_au_personal_first_aid.py --download --output /path/to/new/LastbookData
```

This needs `pypdfium2`, already in the platform requirements. With previously
downloaded, unchanged originals named `<catalog-id>.pdf`, the build stays offline:

```sh
python3 -B tools/build_au_personal_first_aid.py --pdf-cache /path/to/originals --output /path/to/new/LastbookData
python3 -B -m unittest tools.test_build_au_personal_first_aid
```

The output must be a new folder. It contains six original PDFs and 41 PDF file
pages, their extracted text, a searchable catalog, a small local source directory
and `PERSONAL-USE-ONLY.json`. It does not modify an installed library, create a ZIP
for redistribution, add runtime network code, or change Setup's allowed hosts.
The normal public-reference builder reads its own separate manifest and continues
to exclude all personal sources. The normal pack selector also excludes every
record marked `distribution: personal-only`, and its guide check reports these as
intentional non-redistributable absences. Do not upload the personal PDF/text files.

The selected originals are ANZCOR Guidelines 8, 9.4.1, 9.4.2, 9.4.5, 9.4.8 and 9.2.7.
Their original publication, approval/review dates, audience statements, diagrams,
attribution and disclaimers remain inside each unchanged PDF. A retrieval date or
PDF header date is not an independent clinical review. This is a source collection,
not a claim to provide every first-aid topic or replace training.

The metadata in `content/regions/au/personal-sources.json` records the official
source/download addresses, exact bytes, SHA-256, file page counts and personal-use
restriction. A changed download is refused; source changes need fresh review and
updated hashes. No medical procedure is synthesized or rewritten by the tool.

For review, all six real originals were opened, all 41 pages extracted, and their
first pages rendered with Poppler and visually inspected. The separate built
library's hashes, page counts and searches were checked. Native app checks remain
separate; an offline build test does not claim a native platform release test.

On 26 November 2026 the native Australian review app displayed the optional
first-aid guide and opened its cited snakebite PDF page 3 in Page, Text and Whole
PDF views. The source details showed the unmodified-original and personal-use
restriction. This was the combined runtime at `5c5e501`, not a frozen production
bundle or clinical review; it does not extend the native check to all six PDFs.

Public redistribution still needs explicit rights-holder permission. Any proposed
public guide should cite verified physical PDF pages and undergo content/clinical
review. Do not treat the existence of this fetch tool as permission to redistribute
its output or as approval from ANZCOR or the Lastbook maintainers.


## Add the originals to a full library

`tools/compose_au_personal_first_aid.py` adds the six pinned originals and their
source directory to a **new complete copy** of a closed Lastbook library. It also
works when the base already contains the public Australian supplement. It preserves
existing records, search row ids, unrelated index tables, maps, models, notes,
summary diagnostics and any existing personal-use marker. It does not replace
similarly named records or update an earlier personal composition.

Use the build Python with `pypdfium2` from the platform requirements. Close the app
and other SQLite users of the base. With your already obtained originals named
`<catalog-id>.pdf`, the complete operation stays offline:

```sh
python3 -B tools/compose_au_personal_first_aid.py \
  --base "/path/to/full/LastbookData" \
  --pdf-cache "/path/to/my/originals" \
  --output "/path/to/new/PersonalLastbookData"

python3 -B tools/compose_au_personal_first_aid.py \
  --verify "/path/to/new/PersonalLastbookData"

python3 -B app/main.py --data "/path/to/new/PersonalLastbookData"
```

To request the exact pinned official originals, replace `--pdf-cache` and its
argument with the explicit `--download` flag. Neither source mode is implicit.
Changed downloads are refused. Source snapshot dates stay with the pinned
selection; downloading again is not a new clinical review or guideline update.
No source procedure or original PDF is rewritten.

If you also need the public readings, first use the
[public composition command](AUSTRALIA-COMPOSE.md), then pass that new full copy as
`--base` here. A 314-record base becomes 439 after the public addition, then 446
after the six originals and their directory. The personal step adds 42 searchable
units: 41 physical PDF pages and one directory entry. This is an explicit personal
workflow; the public builder and public downloads still exclude these originals.

Choose an output outside the base. Existing outputs, source ids/paths, unsafe tree
entries and active SQLite journals are refused. A failed build removes its own
staging directory; exclusive publication protects a concurrently created output.
APFS clones are used where available; other filesystems require space for a full
copy. Keep the original as the rollback. The tool changes no installed profile,
app setting, runtime downloader or production Setup policy.

The output uses the local identity `local-australia-personal-first-aid`.
**Setup Check/Repair are unavailable for this local composition.** Use its matching
`--verify` command with the app closed, or recreate it from the retained original.
The full manifest records a creation snapshot; subsequent user edits or new files
are reported as differences. Verification checks local integrity, personal flags,
original PDF hashes and physical page numbers; it is not publisher authentication.

The whole output is **PERSONAL USE ONLY**, including its extracted text and index.
`PERSONAL-USE-ONLY.json` is added if absent, or preserved byte-for-byte if the base
already has one. The new `AUSTRALIA-PERSONAL-FIRST-AID-SOURCES.json` retains the
ANZCOR notice and six source records in either case. The new composition receipt
records source restrictions, counts and base hashes; personal checksums cover the
added files, and `pack-manifest.tsv` covers the complete private copy.

Existing public Australian manifests and receipts remain unchanged as provenance
of the base snapshot. They do not claim to describe the new private total. The
public verifier directs this output to the personal verifier. Public pack selection
continues to reject the original PDFs and directory even when a guide cites them.
Do not upload or redistribute the composed library, PDFs, extracted text or index.
Public redistribution still requires the rights holder's permission.

## Ordinary first-aid choices — 27 November 2026

The injury/illness guide now links installed originals from its breathing,
anaphylaxis,snakebite and sting choices. Seven cards reference six originals;
the pressure-immobilisation source is relevant in both snake and sting choices.
Each card says personal use only and retains source/audience limits. Anaphylaxis
opens its first page and directs readers to the complete four-page source;
management is not presented as a complete procedure on one PDF page. The snakebite
card opens physical page3; pressure-immobilisation opens its uses/exclusions page.

These cards use existing per-document availability filtering. They disappear in
libraries without the separately installed originals. The ordinary guide's two
public Australian calling/poisons additions remain available when their records
are installed. No PDF,extracted text,index or medical procedure is added to the
public supplement by these links. Public pack-selection checks retain the explicit
personal-use exclusions,even when shipped guides cite all six originals.


The 27 November2026 first-aid-link update passes882contribution/954combined tests.
Native checks open all six unique original PDFs from the ordinary guide at their
cited physical pages,and verify snakebite Page/Text and Ask/Back context. The source
PDFs,index and library are unchanged. This remains navigation evidence,not a new
clinical review. Exact candidate policies and source differences are recorded in
`docs/AUSTRALIA-FIRST-AID-SELECTION-20261127.json`;raw research/private renders are
not contributed.
