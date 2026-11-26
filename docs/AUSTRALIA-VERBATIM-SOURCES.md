# Bat-exposure source and unchanged-source reuse

The public collection now has 124 HTML records: 99 official practical readings,
16 source-rights readings and nine original records. The new practical reading is
NSW Health's complete *Rabies and Australian bat lyssavirus infection* factsheet,
current as at 27 November 2025. Its summary, prevention, exposure circumstances,
advice about previous vaccination and uncertain exposure, public-health response and
further-information text remain together. NSW service arrangements are identified.
Retrieval on 27 November 2026 does not make its author or clinical review date 2026.
The source uses four recorded cases in its introduction and retains three-case
wording in its symptoms discussion. Both are preserved, with a visible editorial
source note; they are not presented as live statistics.

The same source is available in household, rural and health prepare/learn lists
and choices, and the ordinary injury guide's animal-bite choice. Ten conditional
cards use existing record-availability filtering. Original choices and references
are preserved. The household and rural placements are identical. The source does
not replace medical assessment, and no treatment methods are combined.

## Exact-site rights and source selection

The selected NSW page links to the Ministry's explicit CC BY 4.0 policy. Its full
policy text matches the rights reading already bundled, including exclusions,
requested credit and its separate formal-permission paragraph. Selected written
blocks retain wording, order, headings and lists. Images, videos, branding,
third-party downloads and external link destinations are excluded. Zero-width
layout characters and line endings are technically normalized. Source medical
wording is not rewritten or translated. Original link labels remain source text.

Queensland Health's own policy is different: **CC BY-ND 4.0**. It expressly covers
that website and its subdomains, subject to exclusions. Its unchanged written
copyright notice is now bundled with the complete English CC BY-ND legal code
and accompanying Creative Commons notice. The legal-tool text itself is available
under CC0, as stated in Creative Commons' published policies. That CC0 status does
not relicense Queensland material. No logos or licence icons are copied.

CC BY-ND sections 2(a)(1) and 2(a)(4) permit unmodified sharing in whole or part
and technical format changes; they do not grant general adaptation permission.
The contribution uses that distinction for the **copyright-policy text only**.
It does not import the reviewed Queensland clinical pages. The older tick page
lacks sensitive-site and remote-removal context present in ANZCOR 9.4.3. The bat
page's live/dead-bat intervention suggestions differ from the selected NSW and
current national avoid-handling advice. A raw insect-page request returned 403;
an exact-body copy was not inferred from search results. No instructions from
those candidates are mixed into the NSW factsheet.

Raw response hashes, exact selectors, selected written blocks, policy footer links,
technical changes, clinical-selection reasons and guide baselines are recorded in
`content/regions/au/VERBATIM-REUSE-AUDIT-20261127.json`. Raw site responses and the
ANZCOR comparison body are excluded from public artifacts. This is a source and
licence review, not independent clinical or legal certification. The ANZCOR rights
enquiry remains unsent; no permission is inferred for its restricted originals.

## Builder guard for no-derivatives sources

The existing BY 4.0, BY 3.0 AU and CC0 paths retain their behavior. A record using
`CC-BY-ND-4.0` must additionally declare:

```json
{
  "reuse_mode": "unchanged-source-text",
  "verbatim_audit": "VERBATIM-REUSE-AUDIT-20261127.json"
}
```

The audit filename must stay within the source directory. It must contain a matching
record id, licence, original source URL and raw response hash. The source snapshot
must contain exactly one ordered pair of unchanged-body markers. The builder checks
the complete marked HTML body hash, its original text projection and that projection's
hash. Only whitespace layout is normalized in the text projection; spelling, case,
punctuation and wording are preserved. A snapshot hash update alone cannot approve
a changed ND body. Even a changed body-hash field still fails against the reviewed
source text. Active content and nonlocal/broken links retain the existing rejection.

The audit is an explicit review record, not cryptographic proof that a publisher
granted rights. Anyone changing the source, excerpt, formatting or audit must review
the primary source and exact terms again. It must not become an escape hatch for
rewritten or translated ND content. Only the Queensland copyright notice currently
uses this path; all clinical bodies retain their separately reviewed licences.

Original ordered-list numbering types are preserved for the legal code. The passive
HTML checker accepts only `1`, `a`, `A`, `i`, or `I` on `ol`; other `type` attributes
remain refused. The licence's lettered cross-references therefore remain readable.

## Build and distribution

Use the offline builder or [out-of-place composition tool](AUSTRALIA-COMPOSE.md).
Never replace a full installed catalog with the smaller supplement catalog. The
matching runtime supplies the new guide cards. A composed full library inherits
every base privacy/reuse restriction; this public addition does not license private
PDFs, text/index, notes or models. No new private clinical body is published, and
no production Setup/downloader, TLS/network policy or shipped dependency changes.
