# Australian offline reference supplement

This contribution adds a reviewed starting collection for Australian households and
rural properties. It does **not** make Lastbook complete for Australia. Its coverage
and remaining work are recorded below so missing information is visible.

## Included

- 51 dated official text readings: ACMA emergency calls, CB radio and locating devices; Queensland
  household planning, emergency kit, home and pet preparation, cyclone/storm,
  food safety, drinking-water safety and poisons; NSW bushfire, flood, heatwave,
  evacuation, rural bushfire, rural flood and animal preparation; South Australian
  emergency contacts; Energy Safe Victoria's complete generator-use section; and
  myGov's remote-travel preparation and emergency-help sections; NEMA's complete
  written fire-danger rating and AusAlert articles; the complete 10 November 2026
  AusAlert operational announcement; NSW's warning-level definitions; six SA SES
  before/during/after storm and flood pages; and SA CFS property and animal-planning
  sections; four Victorian energy/gas/LPG readings; two Safe Work Australia
  remote-work readings; Queensland road-trip preparation; disability-inclusive
  planning selections and complete mobility and low/no-vision written articles;
  four text-only parts of CFA's currently linked Victorian survival guide;complete NSW Health rainwater,groundwater,flooded-tank and non-potable written readings.
- Twelve copyright statements, an original accessible-calling navigation note,
  the original Australian source hub and a directory
  covering all six states, three internal territories and seven external territories:
  **66 searchable HTML records** altogether. Four remote entries provide management
  references, without establishing local emergency numbers or services.
- Three optional guides: Australian household preparation, rural isolation and
  emergency-health sources. They appear only when both supplement directory
  documents are installed. The health guide also points to the library's existing
  SCHN child/baby CPR videos, when present; no video is redistributed here.
- A build tool which uses only reviewed, committed snapshots, makes an FTS5 search
  index and checksums, and never downloads or overwrites an installed library.

Household and rural sections have their own choices and preparation readings. The
national directory is **directory coverage**, not a claim to carry every
jurisdiction's detailed manuals. Regional source laws, numbers, advice and services
are labelled as regional throughout. In particular, South Australian local service
numbers are not presented as national contacts.

## Build and inspect without a connection

Use Python 3.11+ with SQLite FTS5; no extra dependency is needed by this tool.

```sh
python3 -B tools/build_australia_reference.py --output /path/to/new/LastbookData
python3 -B -m unittest tools.test_build_australia_reference
```

The output must not exist. It contains `library-data/catalog.json`, `search.sqlite`,
`pages/au/`, extracted searchable text, the reviewed manifest and a checksum list.
The hub catalog id is `au-reference`. Search for `Australian household`, `livestock`,
`Triple Zero` or `CB radio`. A source runtime can open the separate library:

```sh
python3 -B app/main.py --data /path/to/new/LastbookData
```

This is a separate text reference library, **not an official Setup pack**. It has no
maps, videos, encyclopedias or AI model. It does not edit an existing library and is
not advertised to the production downloader. Maintainers can incorporate its catalog
and search rows in a release snapshot, then rebuild normal packs using the existing
pack pipeline. Do not replace an installed library's catalog with this small catalog.
An arbitrary user-document import feature is a separate upstream proposal (#70).

The app-side guides need the matching source version from this branch. Older apps
can search and open the documents, including the hub, but do not acquire new guide
JSON from a data download. Individual health-video cards remain optional.

## Source and permission review

`content/regions/au/manifest.json` pins every adapted file's size and SHA-256,
original URL, retrieval date, publisher, jurisdiction and licence. Official records
also retain the downloaded raw response's SHA-256 as provenance. These are retrieval
hashes, not claims that a live web page will return identical bytes later.

The official text retains the licence from its exact site's copyright statement:
CC BY 4.0 for the earlier sources and Energy Safe Victoria; CC BY 3.0 Australia
for myGov (including its copyright statement). The manifest records each version
and licence URL. The builder accepts those explicitly reviewed licence identifiers.
Those statements are included offline. All publisher credits, original addresses,
licence references, changes and non-endorsement notices appear on the adaptations.
Original hub/directory text is also CC BY 4.0. Source content is not relicensed under
the source code licence. Logos, images, third-party files, scripts, forms and web
link destinations are excluded. No third-party download is assumed covered by a
parent government site's licence. Hyperlink labels remain source text, with a notice
that their targets are not bundled. List order, headings, tables and warnings remain.

Only the drinking-water section of Queensland's *Food and drinking water* is
included. Its food-cleaning recipe differs from the separate food-safety source;
the collection does not silently combine those recipes. Source wording within the
selected sections has not been rewritten, and source update dates remain where
present. Retrieval in 2026 does not mean a source was authored or medically reviewed
in 2026.

The separately reviewed Energy Safe Victoria page is included under its own
  explicit CC BY 4.0 statement. Only its complete “Using a generator” section is
  selected; selection/capacity advice, illustrations and translated PDFs are not
  included. All cautions within that section remain. Its page review date is
  16 March 2026; that is a source date, not our independent electrical review.
The myGov selection supplies basic national remote-travel preparation; it is not
a detailed outback driving, water/fuel calculation or PLB manual. Its page update
date is 16 January 2025.

The warning-system readings distinguish three subjects: warning severity,
forecast fire behaviour and delivery of warnings to mobile devices. They are
static explanations, not current warnings or forecasts. NEMA's source pages were
updated 11 and 12 November 2026; its operational announcement is dated
10 November 2026. The full written article bodies are retained without changing
their wording. NSW's selection contains only the warning-level definitions; media,
hazard-specific action examples and an older paragraph describing an October 2026
AusAlert launch as a future event are excluded. Current launch/transition context
comes from NEMA's dated operational announcement instead.

Both NEMA and AusAlert footers link to NEMA's shared privacy/disclosures policy,
which contains its CC BY 4.0 grant, requested “Australian Government: NEMA” credit,
third-party/branding exceptions and request not to alter source content. That
copyright/disclaimer section is copied offline. Source wording is unchanged;
only HTML display and active/remote elements are simplified. No logos, imagery,
branded service presentation or endorsement are supplied. Frozen text was compared
with the selected source blocks. The copyright/source review does not certify
every statement for a particular emergency or make this a live warning service.

The 26 November additions retain the complete SA SES written introduction and
phase-specific body for each before/during/after storm and flood page. All cautions
within those bodies remain, including fallen powerlines, floodwater, and qualified
inspection of damaged electrical equipment. The CFS property selection retains its
introduction and complete house, garden and seasonal-preparation sections; new-build
siting/design/landscaping sections are excluded. The animal selection retains its
introduction, complete Small animals section and Larger animals Forward planning;
the separate response/veterinary and horse-owner sections are excluded. It is
preparation reading, not an animal-treatment protocol. SA contacts and requirements
remain labelled as SA. Both household and rural guides expose all nine new readings.

The exact current SES and CFS copyright statements explicitly grant CC BY 4.0 with
exceptions for images, emblems, trademarks and third-party material. Both statements
are retained offline, with their requested Government of South Australia attribution
form on each selected page. CFS's current linked privacy, copyright and disclaimer
pages were checked directly. The ACMA locating-device article and current copyright
statement were also checked; its required Commonwealth attribution is retained.
The complete written ACMA article distinguishes satellite distress beacons from
short-range locating aids. It is not an activation manual or device recommendation;
its linked 2026 class licences and AMSA pages are not included.

`content/regions/au/COVERAGE-SOURCE-AUDIT-20261126.json` records the raw-response
hashes, exact selectors and normalized selected-text hashes. The selected source
wording was compared before and after technical HTML simplification. Source files
are pinned separately by the main manifest. All logos, imagery, media, remote
resources and active external links are excluded; referenced brochures, maps,
translations and manufacturers' instructions are not silently bundled. Retrieval
dates are not authoring or independent clinical-review dates.

The energy/remote expansion retains complete ESV gas-emergency, flood-energy,
outdoor-cylinder and LCC27 FAQ written selections. The gas page keeps its
safe-to-do-so conditions and Victorian distributor contacts. The four-column
contact table is displayed as three distributor sections to keep phone numbers
readable; all twelve source label/value pairs are retained and tested against
the original matrix in the audit receipt. The flood page keeps
all before/after sections, including solar/battery live-system cautions and
qualified inspection; translation lists/downloads are excluded. The cylinder
page keeps written compatibility/no-adaptor cautions; artwork and third-party
videos are excluded. All nine FAQ questions are retained as headings with their
complete answers, preserving the direction of compatibility between old cylinders
and new appliance connectors. The dated 2021/2022 transition is not relabelled as
a new change. Manufacturer instructions and regional requirements still apply.

Safe Work Australia's complete remote/isolated-work overview and risk-management
article are workplace/PCBU readings, including farms and home-based work. They
are model-WHS guidance, not a claim that laws are identical in every jurisdiction.
SWA is not a regulator. Its exact-site CC BY 4.0 copyright statement is included;
linked model Codes have separate publication rights and are not bundled.

The Get Ready Queensland travel article's written content is retained while its
interactive hotspots are flattened to one copy each: nine vehicle-check points,
18 kit points and five severe-weather tips. Map-position percentages, repeated
responsive copies, hover/print controls and imagery are excluded. Source typos
and quantities remain unchanged. These regional reference amounts are not a
route/climate-specific supply calculation. The page links directly to the
Queensland CC BY 4.0 copyright statement. Raw hashes, selectors, FAQ/point counts,
selected-text hashes and exclusions are recorded in
`ENERGY-REMOTE-SOURCE-AUDIT-20261126.json` beside the snapshots.

Reviewed but **not bundled**:

- ANZCOR full guidelines: its copyright page limits public redistribution without
  written permission. Seek permission and clinical review for Australian first aid;
  do not substitute overseas envenomation guidance. The separate personal-use
  source tool does not grant public redistribution rights.
- Queensland's older general bites-and-stings page: not selected after review.
- The Queensland Health alternative-fuel/generator page includes third-party
  Victorian content; permission scope needs checking. The distinct Electrical
  Safety Office site links to Office of Industrial Relations CC BY 4.0 terms;
  those terms must be checked directly rather than inferred from qld.gov.au.
- NSW Parks outback text: its copyright page labels content CC BY but also asks
  for permission to modify it and for commercial uses. It is not included while
  that permission scope remains unresolved.
- AMSA remote land-travel material: candidate primary source; full source/permission
  snapshot acquisition still needed. Its address appears as an unbundled reference.
- WorkSafe ACT's own policy permits narrower unaltered personal/educational or
  organisational uses; it does not inherit the general ACT portal's open grant.
  WorkSafe WA links noncommercial WA terms; no separate open grant was established
  in the remote-tour PDF. Neither is bundled. The older WA bulletin also describes
  a usually-24-hour contact delay and was not adopted as current missing-person advice.
- CFA's July2022 Version6 survival guide is now included as four text-only
  practical readings and a written source-rights/contact record. The current
  resource page links a different PDF from the older candidate; exact bytes and
  all20 rendered pages were checked. The original PDF and excluded imagery are
  not bundled. See the detailed CFA audit below. VICSES commercial reuse needs
  written permission; its general site grant was not treated as open CC material.

To refresh: retrieve the official source and its exact site's copyright statement,
check changed instructions, dates, attribution and third-party notices, review the
selected body against the original, strip active/external content, update the frozen
adaptation and manifest hashes, then rerun source-integrity tests, guide validation
and actual offline search/reader checks. A checksum change is a review trigger, not
an instruction to accept a new live page automatically.

## Coverage audit and remaining work

| Area | Current contribution | Still needed |
| --- | --- | --- |
| Emergency calls and communications | ACMA 000/112/106, coverage/accessibility/power loss, CB class licence; NEMA AusAlert explanations and operational notice | Satellite phone/PLB operation, detailed device support and local radio frequency coverage |
| Household planning and supplies | Qld plans, kit, home and pets; NSW evacuation; SA property and animal-planning selections | Licensed detailed local guides for remaining jurisdictions; disability and translated materials |
| Rural preparation | NSW rural bushfire, flood/isolation, animals; SA CFS property and larger-animal planning; myGov basics; Qld trip/kit source; SWA remote-work risks; ACMA locating-device explanation | More detailed remote driving, route-specific water/fuel calculations, beacon activation manuals, pastoral and First Nations community-specific sources |
| Fire, flood, cyclone and heat | Dated NSW/Qld texts;six SA SES storm/flood readings;national warning/rating explanations;CFA Version6 text-only risk/preparation/warning/fire/last-resort source parts | More detailed regional manuals for ACT/NT/Tas/WA;hazard-specific and accessible/translated warning material;current local plans/services |
| Food and water | Qld food-safety/drinking-water section; complete NSW rainwater maintenance, groundwater risks/testing, flooded tanks and non-potable advice | Actual site-specific testing/treatment and extended remote supply; more jurisdiction-specific recovery guidance |
| Health | Emergency calls, Qld poisons, references to existing SCHN videos | Permission-cleared current Australian snakebite/marine-stinger/adult CPR/anaphylaxis material and clinical review |
| Power, gas and repairs | ESV generator use, gas emergencies, flood electricity/solar/battery/gas, outdoor LPG cylinders and all nine LCC27 FAQ pairs | More jurisdiction-specific material; equipment-specific instructions, repairs and local professional assessment |
| Geographic directory | Six states,ACT,NT,Jervis Bay and all seven external territories; four remote entries are management references | Detailed territory manuals,field communications and verified current service availability |
| Maps | Separate #38 now has eight capital,eight broader and six external extract definitions; #90/#101 provide point-place build/lifecycle support alongside #63 | Official publication/Setup listing; Antarctic coverage and detailed coastal/navigation data; this supplement contains no map files |

All snapshots are static. Lastbook does not use this directory to fetch warnings,
make phone calls, find current evacuation centres or decide that a road is safe.
No data-folder content introduces a runtime connection or changes the downloader
allowlist. Map POIs do not verify opening, capability or emergency-shelter status.

## Validation

Run the normal contribution suite and the new builder tests. Validate the two
preparation guides against the built supplement, and all three against a full review
library containing the supplement and the two already-installed SCHN videos:

```sh
python3 tools/validate_topics.py --data /path/to/new/LastbookData content/topics/au-household.json content/topics/au-rural.json
python3 tools/validate_topics.py --data /path/to/full/review/LastbookData content/topics/au-household.json content/topics/au-rural.json content/topics/au-health.json
```

`requires_docs` keeps the entire regional guide (including its warnings and intro)
out of libraries without the supplement; ordinary missing optional readings are
still hidden by the existing resolver. No platform packaging script is changed.

Native review on 26 November 2026 used the separate 354-record Australian review
library and combined runtime commit `5c5e501`. Both household and rural guides
exposed all four warning readings. All four warning pages, the Victorian
generator-use page and myGov remote-travel page opened with their source dates,
credits and selection limits. The personal first-aid guide opened the original
snakebite PDF at its cited physical page in Page, Text and Whole PDF views, with
the personal-use restriction visible in source details. The integrated Victorian
map found Mildura, drew street detail and displayed nearby distances in metres
and kilometres. This does not claim native checks of the other seven broader
extracts, clinical review, or a platform release build of the current-main rebase.

Later that day, the current-main combined source (`76ab539`) passed 840 tests
(five skips, eleven upstream expected failures) and the complete Mac build recipe:
TLS roots, i18n, package/privacy scan and strict ad-hoc signature verification.
A self-contained private frozen review app was installed with the same separate
354-record library and outbound IP denied before startup. Native checks showed
all four Australian guide cards, the original CPR PDF, NSW warning-level reader,
and Ballarat's finder/street detail/metric nearby distances. All four installed
guides resolve 116 references with zero errors after moving to the durable
profile. A corrected ACT map also displayed Canberra's underlying city label at
zoom 8; Victoria was restored afterward. This does not establish clinical review,
all-six-PDF native coverage, Windows support, notarization or complete Australia
coverage. The private library and personal-use PDFs are not published.

After the regional expansion, the required contribution suite and both Australian
builders passed 793 tests (five skips, eleven upstream expected failures); the two
personal-distribution guards passed separately. Four final source-integrity tests
passed after matching each SA attribution to its exact original work title. A fresh
44-record offline build passed actual public/private engine search and guide
resolution with socket construction forbidden. Household/rural references are
66/71 (137 public); the four-guide private library has 171 valid references.

The refreshed frozen private Mac app (`79fd960`) contains 365 records (314 base,
44 public Australian and seven personal-use). TLS, i18n, package/privacy scan,
strict ad-hoc signature and actual outbound-IP-denial self-check passed. Native
checks opened the household six-reading SA weather choice, during-storm and
after-flood readers, rural property and animal-planning sections, and ACMA's
locating-device article with credits/dates/scope visible. The whole previous
354-record library and frozen app were retained for rollback; Victoria is unchanged.
These are selected native reader checks, not all-article or clinical verification.

[The separate 44-record regional review](https://github.com/pilkster/lastbook/releases/tag/australia-regional-reference-review-2026-11-26)
excludes personal-use material. Its actual extracted ZIP passed CRC, all 44 source
size/hash checks and SQLite/FTS checks. Earlier 24/28/33-record reviews are unchanged.


The later energy/remote expansion contains **52 public records**: 40 official
readings, ten copyright statements and two original hub/directory records.
Both household and rural guides include all seven new readings. The required
contribution/build suite including personal-distribution guards passed 796 tests
(five skips, eleven upstream expected failures) under `PYTHONUTF8=0`. Five final
source-integrity tests passed after the contact-layout fix. The fresh public
52-record build has 179 valid household/rural references; the actual private
373-record library has 213 valid references across four guides. Actual public
and private engine searches, guide resolution and all public reader hashes pass
with socket creation forbidden.

The updated frozen private Mac app (`83d467e`) passed i18n, package/privacy scan,
strict ad-hoc signature and an outbound-IP-denial self-check. The unchanged TLS
roots and pinned setup manifest retain the preceding verified build inputs.
Native checks opened all seven new readers: gas contacts (visually checked after
reformatting), flood electricity/solar/battery cautions, outdoor LPG, all nine
valve FAQ questions, both remote-work articles and the flattened Queensland
travel checklists (visually checked). Attribution, retrieval dates and regional
scope are present. Full predecessor app/data copies remain available; Victoria
is unchanged. Before this update, the preceding app recovered from one
unresponsive-page watchdog event after long inactivity; its cause remains
unresolved. Short reader checks do not establish long-idle reliability.

[The 52-record energy/remote review](https://github.com/pilkster/lastbook/releases/tag/australia-energy-remote-review-2026-11-26)
contains only public material. Earlier 44-record and other review releases remain
unchanged. These are contributor reviews, not official Setup releases, all-reader
native verification or independent clinical/electrical/engineering review.


## Disability preparedness and accessible calling

The collection now contains **56 public records:43 official readings,ten copyright
statements and three original hub/directory/navigation records**. Both household
and rural guides expose all four new readings in choices, prepare and learn.

Queensland's September 2026 disability-inclusive page is selected at its
introduction,all four immediate-support cards,network-learning text and prompts,
strengths/planning text and all eight support areas. Named lived-experience
profiles,resource cards and the contact directory are excluded; the third-party
P-CEP workbook,NDIS downloads,images and Auslan/video content are not bundled.
The complete written mobility and low/no-vision articles retain all ten tips,
service descriptions and five decision rows each. Tables become question sections
with both column-label/value pairs preserved. Service statements remain regional
source descriptions,not a guarantee of eligibility,transport,alerts or availability.
These texts are not an independently validated Easy Read,braille or Auslan edition.
The exact linked Queensland copyright policy was checked and CC BY4.0 attribution
is retained.

A separately authored factual service-navigation note distinguishes TTY106 from
NRS SMS Relay and 000/112 direct-SMS limits,with current ACMA/Access Hub URLs and
dates. It does not reproduce the complete NRS operating manual. Access Hub's
linked departmental policy grants CC reuse where material is identified; no CC
marker was established on those two pages,so their bodies are not bundled. The
regional hearing page's save106inphone tip is not selected because its TTY context
is easy to miss. The cognitive-support page's simplified warning translations
need further review and are not bundled. Two disability-index links redirect to
generic disaster indexes; they are not represented as disability manuals.

`ACCESSIBILITY-SOURCE-AUDIT-20261126.json` records exact selections,raw/selected
hashes,original decision matrices,licence evidence,factual-note references and
exclusions. This expansion improves preparation reading; person-specific support,
service readiness,more disability audiences and accessible translations remain
incomplete.


After this expansion,the complete required contribution suite,both Australian
builders and personal-distribution guards passed **797 tests** (five skips,eleven
upstream expected failures) under `PYTHONUTF8=0`. All six source-integrity tests
pass. A fresh56-record public build resolves99 household and104 rural references
(203 total); all four actual private guides resolve237 references without errors.
Actual public/private engine searches and all56 public reader hashes pass with
socket creation forbidden.

The updated frozen private Mac app (`426c481`) contains377 records:314 base,
56 public Australian and7 personal-use. I18n,package/privacy scan,strict signature
and actual outbound-IP-denial self-check pass,using unchanged verified TLS/setup
inputs. Native checks opened both support-needs choices and all four new readings;
the calling note and both decision layouts were visually checked. This verifies
selected reading/navigation,not an independent assistive-technology/disability
audit or actual emergency service operation. Full predecessor copies are retained;
Victoria is unchanged. The earlier idle-page watchdog issue remains unresolved.

[The56-record disability-preparedness review](https://github.com/pilkster/lastbook/releases/tag/australia-disability-preparedness-review-2026-11-26)
excludes all personal-use material. Earlier52-record energy/remote and other
review downloads remain unchanged. Contributor reviews are not official Setup
releases or complete Australian coverage.


## Territory directory expansion — 26 November 2026

The existing original directory now has16 entries: six states, ACT, NT, Jervis Bay
and all seven external territories. The public library remains56 HTML records;
43 official readings and10 copyright statements are unchanged. Original hub and
directory remain CC BY4.0; the accessible-calling note alone is CC0.

Jervis Bay is a distinct internal territory. Its official28August2023 resident
contact list supports000 and NSW SES132500. Norfolk's official government-service
page supports000 for fire/policing. Christmas's June2024 emergency plan identifies
000 and outages that can disable it. Cocos's February2025 official boating guide
lists000 for a police emergency. Those PDFs were inspected locally, but neither
the files nor their extracted text are redistributed. No local SES132500 service
arrangement is inferred for Christmas,Cocos or Norfolk.

Indian Ocean Territories Health Service numbers retain their clinic labels:
Christmas Health Centre,West Island Clinic and Home Island Clinic. They are not
relabelled as emergency numbers; hours,capacity and evacuation descriptions are
source facts,not a current availability test. Heard/McDonald,Ashmore/Cartier,Coral
Sea and the Australian Antarctic Territory provide official management entry
points without assigning local000 or SES contacts. Map/station labels cannot
establish rescue capability. Antarctic field procedures/maps are not supplied.

Existing eight entries retain their17November check dates. New entries use
26November retrieval dates and retain older publication dates where known. The
machine-readable directory and linear heading/definition-list reader agree;
there is no wide contact table. Written online addresses remain inert. The
TERRITORY-DIRECTORY-SOURCE-AUDIT-20261126.json receipt pins exact official HTML/PDF
response hashes and distinguishes original facts from licensed source-body
reproduction. No runtime downloader,guide JSON or shipped dependency changes.

Seven source-integrity/build tests passed,including jurisdiction classification,
per-entry dates,clinic/number associations and preventing unsupported SES/000
assignments. Both existing household/rural directory choices resolve the refreshed
reader. Actual public/staged-private engine queries for all eight added territories
and both Cocos clinics pass with sockets forbidden; all56 public reader hashes,
private377 records/personal7 and Victoria map hashes remain valid. The matching
source runtime is unchanged; this update only replaces data.

Required contribution/build suite: **798 tests OK**,five skips and eleven upstream
expected failures under PYTHONUTF8=0. Final reader wording then passed all seven
focused source tests and fresh public/private builds. The first sandbox-only full
run could not bind its localhost test fixtures; the permission-scoped rerun passed.
The unchanged regional runtime retains its prior864-test combined-source check.


## Victorian bushfire survival text — 26 November 2026

CFA's current Backup plans page links a20-page guide at
ArticleDocuments/6528/your-guide-to-survival.pdf.aspx. It differs from the older
ArticleDocuments/335/CFA-Your-Guide-to-Survival-V6.pdf candidate. The current file
is1,455,205bytes,SHA-256 de37f989a65b529351f3fe87685bc70a1d84a5d543cb5fef905e5458f90d1918.
Its visible edition remains **Version6,July2022**. A complete text-layer diff found
only the page20 department address change from delwp to deeca. The PDF metadata's
2025 modification date is not presented as a new edition or advice review date.
The resource-listing/plan/defending pages and exact bytes are pinned in
CFA-SURVIVAL-SOURCE-AUDIT-20261126.json.

Page20 explicitly licenses text under CC BY4.0 and requests the credit
“© State of Victoria (Country Fire Authority)2022”. Images,photographs,branding
and third-party rights are excluded. No original PDF,image,map,diagram,logo or
cover slogan is distributed. Four practical HTML parts cover the written body,
checklists and table cells on pages2-19,plus a separate written copyright/contact
record from page20. District/risk/property annotation text becomes lists; a list
of district names does not provide geographic boundaries. Diagram-only labels are
excluded. Source page numbers remain explicit in every part.

All20 rendered pages were visually inspected.359 individual transcribed blocks
match the actual PDF extraction after only visually verified missing-character
repairs and comparison whitespace/punctuation normalization. The text layer loses
characters in words such as fire,flammable,traffic and off; the display restores
the printed words. Genuine printed “Bushifre” and “health,life” spellings remain.
The audit stores page-text hashes,repair mappings and independent source matrices
for all eight rating cells and all four WHEN/WHAT TO DO rows. The source's ten
planning decisions,twelve before-summer items,both leaving checklists,conditional
phrases,building/car procedures and all three last-resort risk qualifications
remain. Tables become labelled sections rather than wide grids.

The warning part retains2022 Emergency Alert,relay,broadcaster/social-media
wording,with visible links to the existing NEMA10November2026 operational and
accessible-calling readings. Current CFA22September2026 defending-property context
is separated from the older guide text: CFA does not recommend defending a home.
No later website article body is copied under the PDF's grant. All readings are
dated Victorian sources,not live warnings,current service/reception tests or an
independent fire-safety/clinical/accessibility audit.

Both household/rural guides expose the same four-reading Victorian choice and
preparation/learning cards. The collection now has **61public records:47official
readings,11copyright statements and3original records**. Hub/directory remain
CC BY4.0; the original accessible-calling note alone is CC0. Personal-use material
remains separate and excluded from public downloads.

Validation: **799 required contribution/build tests OK**,five skips/eleven
upstream expected failures under PYTHONUTF8=0. Eight focused source/build tests
cover actual offline61-record construction,source integrity,all table-cell
associations,checklist counts and last-resort qualifiers.


### Linked-reading source context

Native review reproduced an existing HTML-reader problem:following an in-page
link replaced the frame content while the outer title,source details and Ask
context still named the earlier record. The desktop shells now send a user-clicked
link to a different catalogued reading through the app's ordinary reader route.
The current reader is retained as the back destination. The visible source,title,
Ask,Saved and history then use the destination record.

The shared bridge accepts only an active HTML reader,a real user link action and
a different supported record already in the library. Initial loads,same-record
anchors,PDF/encyclopedia browsing,unknown/external addresses and frame popups
retain their existing rules. No saved-page origin/script/CSP permissions,network
policy or download host changed. Both bridge modes passed204 tests,including
Unicode/encoded ids,PDF page targets,back context,initial/self-link exclusions
and refusal cases. Windows/Linux hooks are included;their native behaviour has
not been verified here. This desktop-policy repair does not cover the optional
browser-over-HTTP reader;that remains a separate navigation gap.

The five CFA records also use the standard edition field,so the source details
show Version6,July2022 and the year2022 alongside the distinct retrieval date.
Final source repair suite:805 required contribution/build tests OK,five skips and
eleven upstream expected failures. The61 source bodies remain unchanged.


Final combined source verification passed **872 tests**,five skips and eleven
upstream expected failures,including the required suite,Australian builders and
distribution guards,and regional map/place lifecycle tests. The matching private
Mac build passed package/privacy scan,i18n,strict signature and installed
382-record/7-personal-record outbound-IP-denial self-check. All261 Australian
guide references resolve;61 public source hashes and the preserved Victoria map
hashes pass. No new TLS verification is claimed.

Installed Mac review opened both four-reading guide choices and all five CFA
readers. Following risk → preparation → warnings → last-resort → rights updated
the outer title,source panel and Ask record each time. Back returned preparation
to risk. Source details show the July2022 edition/year separately from retrieval.
Selected screenshots checked rating cells,monitoring rows,last-resort danger text
and concise rural cards. This is selected native review,not all61 native readers,
Windows/Linux native verification or independent professional/accessibility review.
The earlier unexplained idle watchdog event remains unresolved.

[61-record Victorian bushfire contributor review and checksums](https://github.com/pilkster/lastbook/releases/tag/australia-victorian-bushfire-review-2026-11-26)
provides public HTML,audits and engine evidence only. No original CFA PDF,excluded
imagery or personal-use first-aid material is distributed.


## NSW private drinking-water source expansion

Four complete written readings add rainwater maintenance/all19FAQ answers,
groundwater protection/testing,flooded tanks,and non-potable supply advice. Their
source dates are11September2026,18October2022,4April2023 and21April2026 respectively;
older regional contact/agency labels remain dated. A fifth record preserves the
complete NSW Health copyright body,including the explicit CC BY4.0 grant,excluded
material,requested credit and formal-permission enquiry paragraph. Excluded logos,
trademarks,third-party files,PDFs,standards and linked manuals are not redistributed.
No enHealth/Queensland Health/Victorian Health grant is inferred from a NSW link.

All selected written blocks compare exactly before/after HTML simplification.
Accordion controls become19 visible question headings with full ordered answers.
The rainwater source has different daily tap-flushing durations in its introduction
and FAQ:2–3minutes versus10seconds,with at least2minutes after48hours without use.
Both remain,with a visible source-variation note. Chlorine products,strengths,
volumes,waiting times and precautions remain in their original contexts. No new
calculation or merged treatment recipe is introduced. The non-potable reading
retains chemical/radiological do-not-drink and toxic-algal do-not-use distinctions,
including the explicit limit that boiling will not make those supplies safe.
Groundwater's Naegleria/specialist advice,testing,250metre separation and dated
contacts remain. Flood guidance keeps electrical,structural/entry/clean-safe-refill
conditions and all tap-cleaning steps. Water quality remains site-specific.

Both household and rural guides expose the same four water readings in choices,
prepare and learn. The collection now has66public records:51official readings,
12copyright statements and3original hub/directory/navigation records.
`WATER-SOURCE-AUDIT-20261126.json` pins exact primary responses,selected block hashes,
all19source question/answer pairs and exclusions. Linked2019fire-retardant and2020
bushfire bodies are not bundled or silently combined with2026treatment instructions.
This is source comparison,not independent clinical/water-safety validation,actual
water testing or verification of current local contamination/service availability.

AMSA main land/trip/copyright acquisition was retried26November and returned403;
its separate beacon site's policy requires written permission. Those search snippets
and restricted pages are not copied into an offline operating manual. Victorian
Health's own current copyright policy prohibits adaptation without permission;
Queensland Health has a separate BY-NDpolicy. Those grants are not inferred from
other departments' general CCpolicies. Remote/beacon operation and more jurisdictions
remain work for the full Australian objective.
