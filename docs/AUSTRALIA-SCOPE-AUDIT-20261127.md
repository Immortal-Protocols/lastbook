# Australian scope and completion audit — 27 November 2026

The requested scope is to install Lastbook, contribute Australian maps and
information, and give household and rural use equal depth. The broader request
also asks for it to be complete for the user and other Australians. This audit
checks that scope against current contributions; it does not replace it with a
smaller completion target.

## Requirements and evidence

| Requirement | Current evidence | Result and limit |
| --- | --- | --- |
| Install and run Lastbook locally | Installed Mac review self-check verifies 476 records, 36 personal records and one nonprofit original and outbound-IP denial. Selected native reader, guide, map and source-context checks are recorded in the dated reviews. Original vendor app and rollback copies are retained privately. | Working local installation verified for the recorded Mac scope. This does not establish a public production app release. |
| Contribute Australian maps | [PR38](https://github.com/Immortal-Protocols/lastbook/pull/38) supplies 22 exact build definitions: eight capital areas, eight broader extracts and six external-territory extracts. [Broader map downloads](https://github.com/pilkster/lastbook/releases/tag/australia-state-maps-review-2026-11-17), [corrected ACT/NSW maps](https://github.com/pilkster/lastbook/releases/tag/australia-map-label-review-2026-11-26) and [territory downloads](https://github.com/pilkster/lastbook/releases/tag/australia-territory-maps-review-2026-11-26) are published contributor prereleases. | Contribution and review downloads delivered. Definitions are extract envelopes, not complete administrative/coastal/navigation coverage. Antarctic coverage and official Setup publication remain absent. |
| Australian place search and map lifecycle | [PR90](https://github.com/Immortal-Protocols/lastbook/pull/90) and [PR101](https://github.com/Immortal-Protocols/lastbook/pull/101), with the source/build and lifecycle checks in their descriptions. Installed Victoria retains 3,054 named points and verified layer hashes. | Named-place search delivered for the reviewed datasets. These are not full street-address coverage or verified operating facilities. |
| Contribute reusable Australian information | Current manifest has 125 public records: 100 official practical readings, 16 rights readings and nine original records. The [public data download](https://github.com/pilkster/lastbook/releases/tag/australia-community-planning-review-2026-11-27) and PR89 source/build/composition tools are published. | Delivered for the listed sources. Per-source dates, jurisdictions, licence exclusions and boundaries remain; linked resources are not implicitly included. |
| Give household and rural use equal depth | The actual 476-record library resolves 300 household references and 305 rural references. Both guides expose the national/local planning, hazard, accessibility and language additions; specialised rural route, isolation, property and animal readings remain. | Both use cases have substantial verified coverage. Similar counts are navigation evidence, not proof of equal usefulness or complete content. |
| Australian first-aid source access | The optional explicit collection contains 35 unchanged ANZCOR PDFs / 263 pages plus a directory. All physical-page sequences and the 161 public/personal reader hashes remain verified; the additional nonprofit original brings the current Australian reader-hash total to 162. The dedicated guide has 108 references; ordinary Injury & illness has 21 further conditional links across ten choices. | Local personal-source access and opt-in tools delivered. Originals and their extracted bodies/index are excluded from public assets. Public redistribution permission for ANZCOR originals and independent clinical review remain unproven. |
| Work without an Internet connection | Actual engine checks forbid sockets; the installed private app denies outbound IP before imports. Readers, local search, guides and the installed map work with local files. | Verified for the recorded checks. Setup/acquisition remain explicit separate steps. Static warnings and directory entries do not establish current conditions. |
| Make contributions independently reviewable | Nine focused PRs separate maps, places, lifecycle, content, HTTP reader, Mac timing, document language, script search and native reader work. PR89 excludes the companion runtime changes except the shared existing reader-file predicate used for availability. | Delivered for the reviewed branch structure. Maintainer acceptance and official release/Setup listing remain pending. |
| Make it complete for the user and other Australians | Current source audits and coverage table still identify unavailable manuals, local/device/community needs, public first-aid rights and unverified use cases. The optional request for the user's remaining essential household/rural situations has no answer yet. | Completion is not proved. Neither green software checks nor a large source count proves nationwide practical completeness. |

## Adult traumatic-event source follow-up

The optional nonprofit source path now adds one unchanged seven-page MHFA adult
traumatic-event guideline with ten conditional guide references. Its physical-page-7
grant permits nonprofit reproduction with source acknowledgement. It remains
separate from the 125-record public manifest and is excluded from general packs.
This source does not clear the reserved ANZCOR or Australian Red Cross materials,
and is not the full Red Cross PFA manual. The installed mixed library has 476 records;
all 13,139 earlier search rows are preserved. See the [source workflow](AUSTRALIA-TRAUMA-REFERENCE.md)
and [latest exact review](AUSTRALIA-TRAUMA-REFERENCE-REVIEW-20261127.json).

## Current coverage and concrete gaps

The table in [AUSTRALIA-CONTENT.md](AUSTRALIA-CONTENT.md#coverage-audit-and-remaining-work)
now describes the current collection rather than the initial supplement. In
particular, ACT hazards, Victorian CFA sections, NT/WA/Tasmanian worksheets,
Queensland disability planning, four First Nations poster texts, Chinese and
Arabic national factsheets, NSW smoke/wastewater/bat readings and NSW
Aboriginal-led planning are present. Calling all of those absent would be wrong.
Their presence also does not imply a full local operating manual, independent
language/accessibility review, community endorsement or a completed household plan.

The remaining gaps have different evidence requirements:

- **Official availability:** the project maintainer must accept, scan, publish and
  list official downloads. Contributor prereleases and clean merge status do not
  prove this has happened. No production manifest is changed by these contributions.
- **Reusable source material:** full reserved local agency manuals and the
  personal ANZCOR originals need an applicable licence or permission before public
  bundling. The ARC enquiry remains unsent; no response or reuse consent exists.
- **A particular household or rural journey:** actual support needs, destination,
  device model, route, water/fuel requirements and local arrangements are not
  established by general worksheets. A named essential situation is needed to
  test that situation rather than silently inventing a household or trip.
- **Community and professional review:** a government overview is not a
  community-authored local plan or consent. Source/layout/software checking is
  not fluent-speaker, accessibility, clinical or site-specific professional review.
- **Data scope:** named places are not full addresses; extract bounds are not
  complete coastal or Antarctic coverage. A static offline library cannot verify
  current road access, warnings, evacuation-centre openings or facility capability.

These are not interchangeable. More generic readings would not establish a
rights grant, a working local arrangement or upstream acceptance. Conversely,
absence of live network requests is expected for this offline project and is not
itself an implementation defect.

## Verification scope

This documentation reconciliation reads the exact 125-source manifest, relevant
source audits, guide files, map-definition dictionary, latest native/data-preservation
receipts, published map release inventories and PR89 feedback. The three map
prereleases are confirmed present; this audit does not claim to download and
revalidate every map archive again. Installed data hashes still match the final
native-preservation receipt. No new maintainer request is present after the
already addressed reader-path-policy request.

Latest product checks are **888 content / 1,036 combined**, each five skips and
eleven upstream expected failures, plus **62 focused checks on Python 3.14 and
3.11.18**. Their exact scope and selected native observations are in
[AUSTRALIA-TRAUMA-REFERENCE-REVIEW-20261127.json](AUSTRALIA-TRAUMA-REFERENCE-REVIEW-20261127.json).
Other relevant evidence is in [the personal-source review](AUSTRALIA-PERSONAL-EXPANSION-REVIEW-20261127.json),
[composition instructions](AUSTRALIA-COMPOSE.md), [source reuse audit](AUSTRALIA-VERBATIM-SOURCES.md)
and [ordinary source-placement audit](AUSTRALIA-ORDINARY-FIRST-AID-ROUTING-20261127.json).
This audit reconciliation changes documentation only. The separate adult
traumatic-event implementation changes five bundled JSON assets and adds the
optional original as described in the latest review. The 125-record public data
archive remains unchanged; the nonprofit original has a separate review release.
Historical dated reviews remain historical and do not override this audit.
