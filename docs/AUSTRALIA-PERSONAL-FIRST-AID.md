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
