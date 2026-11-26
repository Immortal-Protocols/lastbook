# Australian public reference supplement

This follow-up contains127 public readings (102 official practical sources,16 rights readings
and nine original records), public guide links and the shared reader-file availability
fix. Personal/nonprofit source workflows and their guide links are separate follow-ups.
Their originals, extracted text and indexes are not in this supplement.

Two additional complete NSW Health water-alert/header-tank articles are described
in [the water-alert source review](AUSTRALIA-WATER-ALERTS.md). PR89 remains the
reviewed125-record dependency; this separate follow-up adds the two sources.

## Build and open offline

```sh
python3 -B tools/build_australia_reference.py --output /path/to/new/LastbookData
python3 -B app/main.py --data /path/to/new/LastbookData
```

Use Python 3.11 or later and matching source/runtime. The build uses only committed,
reviewed snapshots and the standard library; it makes no network request. Choose a
new directory. The data-only download cannot update guide JSON bundled in an older
app. To retain an existing library, use the separate [public composition command](AUSTRALIA-COMPOSE.md).

[Previous125-reading review download](https://github.com/pilkster/lastbook/releases/tag/australia-community-planning-review-2026-11-27).
Existing release assets and historical tags are unchanged by this review split.

## Source scope and reuse

The manifest and source-specific audits under content/regions/au pin source dates,
ordered text, hashes, jurisdictions, attribution and exclusions. Source conditions
remain in each reading. No live warning, current road/centre/facility status or
site-specific assessment is supplied. Original PDFs, logos, artwork, illustrations,
QR codes and third-party material are excluded unless expressly listed otherwise.
See [unchanged-source review](AUSTRALIA-VERBATIM-SOURCES.md),
[clinical-source exclusion review](AUSTRALIA-FIRST-AID-SOURCE-REVIEW.md) and
[dated infant-video source status](AUSTRALIA-INFANT-SOURCE-STATUS.md).

## Guide availability and companion contributions

The Household, Rural and Health source guides require their public source hub and
jurisdiction directory. Every reading is checked on disk with the reader's existing
library-path policy, even with an unchanged cached catalogue. Missing or refused
readings hide; missing required sources hide their guides. Ordinary guide warnings
remain. Moving/restoring the public source folder is covered by the real offline
build regression. [Availability review](AUSTRALIA-GUIDE-AVAILABILITY-REVIEW-20261127.md).

Companion runtime changes remain separately reviewed: HTTP reader #487, Mac timing
#491, document language #493, Arabic/Han search #494 and native linked reader #497.
Maps, place building and map/index lifecycle are #38, #90 and #101. No production
Setup manifest, downloader, TLS, network policy or shipped dependency is changed.

## Coverage audit and remaining work

| Area | Current contribution | Still needed |
| --- | --- | --- |
| Emergency calls and communications | ACMA 000/112/106 and CB sources; accessible calling note; NEMA AusAlert explanations; locating-device and beacon preparation readings | Device-specific satellite/beacon instructions, local radio coverage and actual check-in/rescue arrangements |
| Household planning and supplies | Qld plan/kit/home/pets; NSW evacuation; SA property/animals; NT/WA/Tas planning worksheets; original isolation-dependency worksheet | Full licensed local manuals where absent, actual support/destination/animal arrangements and completed suitable plans |
| Rural preparation | NSW rural fire/flood/animals; SA property/livestock; myGov remote basics; SWA isolated-work risks; Qld road/recovery/packing texts; route/supply/check-in and beacon worksheets | Assessed route and supply requirements, model-specific equipment/recovery manuals, broader pastoral and community-specific planning |
| Fire, flood and other hazards | NSW/Qld/SA readings; four Victorian CFA survival-guide sections; four ACT hazard articles; seven national standard English hazard factsheets | Detailed local operating manuals where absent, current local access/conditions and source-appropriate local arrangements |
| Accessibility and languages | Qld inclusive/mobility/vision readings; accessible-call navigation; four Yumplatok/Wik-Mungkan poster texts; seven hazards each in Simplified Chinese, Traditional Chinese and Arabic | Independent language/accessibility/community review, accessible audio/Easy Read where absent, further needs/languages and actual support arrangements |
| Food, water, smoke and sanitation | FSANZ basics/emergency/flood food texts; Qld food/water; NSW tank/groundwater/non-potable sources, smoke/mask/higher-risk and flooded-wastewater readings | Site-specific testing/treatment/system assessment, equipment conditions and extended remote supply needs; further licensed local procedures |
| Health | Emergency calls/poisons, existing SCHN videos and NSW bat-exposure factsheet | Public first-aid reuse permission, remaining source/context coverage and qualified review; individual care plans are not established |
| Power, gas and repairs | ESV generator, gas, flood energy/solar/battery, LPG cylinder and LCC27 compatibility source texts | Relevant equipment-specific instructions, other jurisdictional material where needed and site-specific professional assessment |
| First Nations and community planning | Four published-language poster texts; complete NSW Health Aboriginal-led public-health planning overview with linked-resource labels | Community-led local plans, consent/partnerships, jurisdiction-specific material and actual culturally appropriate services; linked toolkits are not bundled |
| Geographic directory | Six states, ACT, NT, Jervis Bay and seven external territories; remote management entries retain their limited scope | Detailed local/territory arrangements and verified current services; a directory is not an operational service inventory |
| Maps and places | Separate #38 provides eight capital, eight broader and six external extract definitions and review downloads; #90/#101 provide place-build/lifecycle work. The reviewed Victoria dataset has 3,054 named points | Maintainer acceptance and official Setup publication; full address/coastal/navigation and Antarctic coverage remain absent |

All snapshots are static. Lastbook does not use this directory to fetch warnings,
make phone calls, find current evacuation centres or decide that a road is safe.
No data-folder content introduces a runtime connection or changes the downloader
allowlist. Map POIs do not verify opening, capability or emergency-shelter status.

## Validation

Run the full command in CONTRIBUTING.md and tools/validate_topics.py against the
built public library. Current split validation and public-only full entry-point
views are recorded in AUSTRALIA-PUBLIC-SPLIT-REVIEW-20261127.md. Upstream acceptance
and official Setup publication remain pending.
