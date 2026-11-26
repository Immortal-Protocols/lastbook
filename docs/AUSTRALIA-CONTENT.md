# Australian offline reference supplement

This contribution adds a reviewed starting collection for Australian households and
rural properties. It does **not** make Lastbook complete for Australia. Its coverage
and remaining work are recorded below so missing information is visible.

## Current scope audit — 27 November 2026

The [requirement-by-requirement audit](AUSTRALIA-SCOPE-AUDIT-20261127.md) reconciles
installation, maps, public/personal source access and equal household/rural coverage
against current files and published contributions. Its coverage table below
supersedes the initial supplement's table. The latest ordinary-guide extension and
874 content / 1,022 combined checks are recorded in
[the routing review](AUSTRALIA-ORDINARY-FIRST-AID-REVIEW-20261127.json).
The broad Australian objective remains incomplete; source counts and passing
software checks do not establish local arrangements, reuse permission or nationwide
practical completeness. Dated reviews later in this document remain historical.

## Current review scope — 27 November 2026

This branch contains Australian content, offline builders/composition, personal-use
handling and guide availability checks. It no longer includes the independently
reviewed HTTP reader (#487), Mac modal heartbeat (#491), document language (#493),
Arabic/Han search (#494) or native linked-reading navigation changes. The native
reader extraction is [PR #497](https://github.com/Immortal-Protocols/lastbook/pull/497).
Other companion runtime PRs: [HTTP #487](https://github.com/Immortal-Protocols/lastbook/pull/487),
[Mac timing #491](https://github.com/Immortal-Protocols/lastbook/pull/491),
[document language #493](https://github.com/Immortal-Protocols/lastbook/pull/493),
[Arabic/Han search #494](https://github.com/Immortal-Protocols/lastbook/pull/494).
Historical runtime/build notes below describe the dated review releases, not the
current content diff. The 125-record data remains usable without those fixes;
matching language search, read-aloud and linked-reader context need the relevant
runtime PRs (or the existing integrated private review build).

Guide links and `requires_docs` now check each actual source file on every
resolution. A catalogue entry alone is insufficient. A regression builds the full
public library, warms the real catalogue cache, removes/restores an individual
reading, then moves/restores the entire `pages/au` folder while leaving catalogue
bytes and mtime unchanged. Missing links disappear, the three public regional
guides hide, ordinary warning text remains, and restoration is immediate. Existing
explicit remote-video storage keeps its established availability semantics.

## Optional expanded personal first-aid originals — 27 November 2026

The public collection remains **125 readings**. A new explicit
`--collection bls-first-aid` option selects 35 unchanged ANZCOR originals / 263 pages,
covering the 7 Basic Life Support and 28 First Aid entries on the checked indexes.
The original six-source default,its metadata and original PDF hashes are unchanged.
No PDF,extracted source body or private index is included in public source/assets.
Five conditional personal-guide groups add 87 references; the original 5 choices remain.
Actual-file checks hide missing additions without altering the basic routes.

Both the separate-library builder and out-of-place full-library composer accept
the selection,using an explicit cache or download choice. Existing output and
personal-ID/path collision rules remain;this is not an updater for an earlier
personal copy. From the retained original,the full workflow gives 314 + 125 + 36 = 475
records and 264 personal search units. See the
[exact commands and restrictions](AUSTRALIA-PERSONAL-FIRST-AID.md).

Source acquisition verified all six prior hashes still match. All 263 pages render
and yield text;all 35 first pages and selected full pages were inspected,including
a Poppler cross-render of the airway diagram. Original audiences, training conditions,
review dates,illustrations and external-reference limits remain in each PDF.
The collection is not training or independent clinical approval.

**872 content / 1,020 combined checks pass**,each 5 skips / 11 upstream expected failures;
**29 focused checks pass on Python 3.14 and 3.11.18**. Real CLI composition 439→475,
all 35 physical-page sequences,161 AU reader hashes,search/snippets,scoped retrieval
and libq pass. All 725 AU guide refs resolve. Public pack selection excludes all 35 PDFs
at every size,even when guides cite them. Actual default-build 7 reader files and
its personal marker remain byte-identical to the previous installed basic set.

The private installed upgrade preserves all 12,875 base/public search rows and all
41 default PDF-page rows,adds 29 PDFs,and replaces only the personal source-directory
entry among existing search rows. Victoria’s 3,054 names/map hashes and infant video
hash are preserved. The personal marker retains its restrictions and updates the
source list to 35; the complete previous 446 app/library is retained. Native selected
checks cover the new groups,bleeding,burns Page 3 Text/Ask/Back, and Airway Page 9 diagram,
source date/footer and Ask/Back. Only one bundled guide asset changes;reader/map
runtime and all 125 public data/archive bytes remain unchanged.
[Exact validation scope](AUSTRALIA-PERSONAL-EXPANSION-REVIEW-20261127.json).

## Aboriginal-led public health planning in NSW — 27 November 2026

The public collection now has **125 records: 100 official practical readings,
16 rights readings and nine original records**. The new complete NSW Health
web overview is dated 28 October 2025. Its introduction, five planning
considerations, four additional strategies and six resource labels retain their
wording and order. Aboriginal leadership, self-determination across all four
emergency stages, cultural governance, local Lore, family/housing/mobility and
formal partnerships with the Aboriginal Community Controlled sector remain in
context. The source's supporting-plan status of "under review" is retained.

Both household and rural guides expose the same new planning choice and the
same prepare/learn reading. The health-source guide also adds prepare/learn
access: eight conditional references in total. Existing guide content is
preserved. The source disappears from guide readings if its file is absent and
returns on restoration without rewriting the catalogue.

This is a dated NSW government overview. It does not establish community
endorsement, supply a locally agreed community plan or replace community
leadership. The linked GL2024_016 guideline, other policies and AH&MRC toolkits
are not bundled. Their source labels remain, with online addresses clearly
separated after the body. No linked-resource licence, cultural imagery or
community-owned knowledge is inferred from the NSW website grant.

The exact page's footer links to NSW Health's own copyright policy. Its complete
written policy body was reacquired and matched the existing bundled notice,
including the explicit CC BY 4.0 grant, exclusions and separate formal-permission
enquiry paragraph. The new reading retains requested credit and states the
technical changes. All prior source snapshots remain unchanged except the
contributor-authored hub's new navigation paragraph. Exact raw and selected-body
hashes, source lists, exclusions and pre-change guide/source baselines are in
`ABORIGINAL-PLANNING-SOURCE-AUDIT-20261127.json`.

Broader community-led and jurisdiction-specific planning, language/accessibility
coverage, actual service partnerships and public first-aid rights remain work for
the full Australian objective. The government overview alone does not close those
gaps. This increment changes content and bundled guide assets, not production
Setup, downloader, network policy or dependencies.

Final validation for this increment: **868 content / 1,016 combined checks
pass**, each five skips and eleven upstream expected failures. A subsequent
one-space HTML layout cleanup leaves normalized source text unchanged; all
**72 focused source/composition checks pass on Python 3.14 and 3.11.18** for
the final bytes. Actual public125/private446 engine checks pass, including all
125 public reader hashes, search snippets, scoped retrieval, libq and all638
private Australian guide references. Native Mac checks open both new choices,
the dated reading in Page/Text, correct Ask/Back context and the local rights
notice. All132 AU hashes,42 personal search units,12,792 original non-public
rows and Victoria map hashes are retained. The installed review remains private.
The current real personal workflow also verifies439→446records, preserving all
1,509retained files and12,875base search rows while adding42units. All1,532
completed manifest files verify;public receipts remain unchanged. That separate
private copy is not installed or published and has no native-window claim.
[Exact validation scope](AUSTRALIA-COMMUNITY-PLANNING-REVIEW-20261127.json).

## Bat-exposure factsheet and unchanged-source terms — 27 November 2026

The public collection now has **124 records:99 official practical,16 rights and
9 original records**. The complete NSW Health rabies/Australian bat lyssavirus
factsheet is dated27 November2025. Ten conditional cards give identical household/
rural access, health-guide access and an ordinary animal-bite destination. Original
sources, choices and source conditions remain. No treatment methods are combined.

Queensland Health's unchanged copyright notice and the full CC BY-ND4 English
legal code/notices are also readable offline. A separate audited unchanged-body
path protects ND wording and formatting against silent changes; it is not general
adaptation permission. Only the copyright-policy text uses it. Reviewed Queensland
medical candidates remain unbundled because of source-context differences or a
failed exact-source retrieval. No private ANZCOR body is published.

[Source selection and builder contract](AUSTRALIA-VERBATIM-SOURCES.md) explain
exact-site rights, technical changes, preserved legal numbering and the review
boundaries. The earlier composition evidence below covers the preceding121-record
snapshot; its historical counts do not describe the new124-record source build.
The [bat-exposure review](AUSTRALIA-BAT-EXPOSURE-REVIEW-20261127.json) records
911/983full suites, followed by62focused checks on3.14/3.11 and current engine
validation after the own-directory date-only correction. Code,guide and third-party
source bodies did not change in that correction. The installed private review is445records with630AUguide refs;
the [new public124 download](https://github.com/pilkster/lastbook/releases/tag/australia-bat-exposure-review-2026-11-27)
excludes that private app/library and all restricted originals.

## Compose a new full library — 27 November 2026

The offline [composition tool](AUSTRALIA-COMPOSE.md) can now add these readings to
a new copy of an existing closed library, retaining its sources, maps, models,
search rows and private-use markers. It refuses collisions, detects base changes,
uses an exclusive rename and gives the copy a local identity and full integrity
manifest. A read-only verification command replaces official Setup Check/Repair
for this local composition. All base privacy/reuse restrictions still apply.

The [composition review](AUSTRALIA-COMPOSITION-REVIEW-20261127.json) records 904
contribution and 976 combined tests, plus all 22 focused cases on Python 3.14/3.11.
A real 314-record base becomes a separate 435-record library; its original 12,750
search rows and 1,256 retained files (9,287,617,106 bytes) are unchanged. All 121 new
reader hashes and the 1,506-file manifest verify. No private copy is published.
The installed 442-record Mac review remains unchanged. This is contributor tooling,
not an official Setup listing or a new runtime/data release.

## First-aid source navigation and selection — 27 November 2026

The ordinary injury/illness guide now adds nine source links across six existing
choices: two existing public calling/poisoning readings and seven conditional links
to six separately installed ANZCOR originals. Original PDFs and extracted text
remain personal-use only. Public121 and base314 libraries hide the missing personal
cards. Source links do not cause restricted originals to enter any public pack.

The snakebite choice now identifies the difference between IFRC's limited-resource
washing advice and ANZCOR's Australian source. The actual IFRC physical page342 and
unchanged Australian PDF page3 were checked; the current official ANZCOR HTML was
also reviewed. This is source context,not a newly authored treatment procedure.
Six cited original pages were rendered and inspected. Original audience,approval/
review dates,continuations and medication/training conditions remain in each PDF.

The separate public-source selection audit records exact candidate/policy URLs,
raw hashes or explicit403 retrieval failures,and observed footer links. SCHN,
Better Health Channel and HealthyWA have their own reserved-site terms; they do
not inherit another agency's open licence. Queensland Health expressly covers its
subdomains with CC BY-ND4.0. That licence permits unmodified sharing and technical
format changes; ND is not a blanket ban on offline copies. No new ND-format import
or medical wording adaptation is approved by this audit. Bandage/CPR source
variations require further review. No new government first-aid body,source image,
raw research page or private guideline text is imported into the public collection.
The builder's existing licence allow-list remains unchanged.

See `docs/AUSTRALIA-FIRST-AID-SELECTION-20261127.json` for the nine placements and
source decisions. ARC enquiry remains unsent; no permission,endorsement or
independent clinical/legal approval is claimed.

Validation: **882 contribution/build and 954 combined tests pass**, each five skips
and eleven expected failures.33 focused source/personal/distribution tests pass on
Python3.14 and frozen3.11;27 topic-search tests also pass on3.14. Frozen3.11 runs
distribution tests as a script because its installed `packaging` dependency owns
that import name; this is a test invocation detail,not a product change.

Actual442-record engine checks forbid sockets,verify all9new references,original
hashes and physical PDF page text,and check public121/base314 views. The7personal
cards disappear without their originals;2public cards remain in the public-only
view. The9added references validate with zero errors;the4AUguides retain621refs.
Public small,medium and all pack selectors exclude every real personal manifest
record even though shipped guides reference them.

Frozen combined source `02b642c` passes package/i18n/privacy/signature and installed
442/7 offline-IP-denial checks. Exactly2of58 bundled JSON assets change;all121public
records,128AUcontenthashes,42personalFTS,Victoria and five data hashes are unchanged.
The previous442app remains for rollback. Native checks observe all9cards,open all6
unique original PDFs at their cited pages and both public sources,and check
snakebite Page/Text and Ask/Back context. No question submitted or audio tested.
These checks establish source navigation,not independent clinical/legal review.
Existing public data-release assets remain unchanged;updated PRsource/runtime is
needed for the bundled guide links. ARC enquiry remains unsent.

## Australian readings in ordinary needs — 27 November 2026

Forty links across 25 existing choices in seven ordinary guides now expose relevant
Australian sources when installed: water, food, power, shelter, sanitation, disasters
and communications. There is no inferred location or new country setting. Existing
source-availability filtering hides absent records; original choices, ranking
fields and source order remain after the added cards. Household/rural guides and
all 121 public reader bytes are unchanged.

Cards label jurisdiction and dates. NSW septic assessment is not presented as a
sewer-cleanup or emergency-toilet procedure; flooded tank cleaning is not a method
for chemically contaminated river water. Generator source differences and NSW
tank-source variations remain visible. Existing overseas sources remain separate;
no new combined medical, electrical or water-treatment procedure is written.
The placement audit is `docs/AUSTRALIA-GUIDE-LINKS-20261127.json`.

Local validation: **879 contribution/build and 951 combined tests pass**, each
with five skips and eleven expected failures. All24 source/guide tests pass on
Python3.14 and frozen-build3.11. Availability tests cover full,absent and partial AU
source sets; frozen pre-change guide hashes protect all original choices and ranking
fields. Actual442-record engine checks forbid sockets, resolve all40 new links and
verify source hashes, then remove all AU records to check the actual314-record
fallback. The validator checks the40 added references with zero errors; this does
not claim every raw pre-existing guide reference exists in Small. The four AU guides
still resolve621references,zero errors.

Frozen combined source `93ab7d6` passes package/i18n/privacy/signature and installed
442/7 outbound-IP-denial checks. Exactly8of58 bundled assets change: seven ordinary
guide JSON files and gaps.json. Core code,121public source records,all128AU content
hashes,42personalFTS,Victoria/map hashes and five data hashes remain unchanged.
The previous442app is retained for rollback; the prior full438app/data copies remain.
Native selected checks open a representative choice and matching reader/source panel
in each of the7guides and verify smoke Ask/Back context. Engine checks cover all40;
no all-links visual,all-browser,clinical,engineering,accessibility/audio/community or
historical long-idle approval is inferred.

The121-record smoke/sanitation data archive and its three uploaded assets remain
byte-identical. These additional guide links require the matching updated source/
runtime from PR89; there is no new data release or production Setup change.

## Smoke health and flooded wastewater — 27 November 2026

Four additional NSW Health readings cover smoke exposure reduction, higher-risk
groups (all five expanded FAQ answers), P2/N95 mask suitability and flooded septic
or on-site wastewater systems. Both household and rural guides have the same four
readings in a choice and their prepare/learn lists. Smoke sources are dated
17 March 2025; wastewater is dated 4 April 2023. Live air quality, warnings,
third-party resources and actual system approval are outside this offline copy.

All selected written blocks compare before/after technical HTML simplification.
The source-specific audit retains exact URLs, raw hashes, dates, text, and the
individually checked copyright links. NSW Health's current policy body matches the
already bundled full CC BY 4.0 notice; its exceptions and separate permission
paragraph remain. Images, video, branding, third-party files and linked pages are
excluded. Source wording, nested water-use list, professional/council approval and
undamaged holding-tank conditions remain. No independent clinical or engineering
review is claimed.

Local validation: **877 contribution/build and 949 combined-source tests pass**,
each five skips and eleven expected failures. All22 focused source tests pass on
Python3.14 and frozen-build Python3.11. Socket-forbidden public121/private442
search, highlighted snippets, scoped assistant and libq checks pass. All621 private
Australian references resolve (291household,296rural,13health,21personal), zero
errors. Native Mac checks expand both choices, open all four readers/source panels,
follow companion links, inspect selected mask and wastewater conditions, and verify
search plus Ask/Back. No question was submitted or audio tested.

Frozen combined source `4adb657` passes package/i18n/privacy/signature and the
installed442/7 outbound-IP-denial self-check. All128 AU content hashes,42personal
FTS units, Victoria3,054names/map hashes and exact infant video are preserved. Full
prior438 app/data rollback copies remain. Runtime code is unchanged by this content
increment; earlier Arabic/Chinese search, document language and Mac fixes remain.
These are local selected checks, not hosted CI or independent clinical,engineering,
accessibility/community or historical long-idle approval.

[121-record public contributor review](https://github.com/pilkster/lastbook/releases/tag/australia-smoke-sanitation-review-2026-11-27):
ZIP1,493,993bytes; SHA256 `c4cbe0c36d55140162660bf76a115027c15871755004acd7cdf58bbb1b39fffe`.
CRC/extraction,reader hashes,SQLite/FTS and private-term/path checks pass. Data only;
use matching updated source/runtime for guide choices. Extract into a new folder;
never replace a full installed catalog with this smaller supplement. Earlier
release assets remain unchanged; this is not official Setup or maintainer acceptance.

## Included

- 98 dated official text readings: ACMA emergency calls, CB radio and locating devices; Queensland
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
  four text-only parts of CFA's currently linked Victorian survival guide;complete NSW Health rainwater,groundwater,flooded-tank and non-potable written readings;four complete ACT portal hazard articles.
- Fourteen copyright/source-rights statements, an original accessible-calling navigation note,
  the original Australian source hub and a directory
  covering all six states, three internal territories and seven external territories:
  plus three original journey, isolation and beacon planning aids:
  plus four published-language poster texts in Yumplatok and Wik-Mungkan:
  plus seven complete national Get Ready standard English factsheet texts:
  plus four Queensland driving, breakdown, recovery-strap and selected vehicle/packing readings:
  plus fourteen publisher-written Chinese hazard factsheet texts:
  plus seven publisher-written Arabic hazard factsheet texts:
  plus one original Northern Territory local planning worksheet:
  plus three complete FSANZ consumer food-safety readings and a rights/disclaimer record:
  plus two original Western Australian and Tasmanian local planning readings:
  **121 searchable HTML records** altogether. Four remote entries provide management
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
For an offline, out-of-place addition that retains an existing full library, see
[Add Australian readings to a copy of your library](AUSTRALIA-COMPOSE.md).
The composition tool gives the new copy a local identity and full integrity
manifest; it is still not an official Setup pack and inherits all base restrictions.
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
Original hub/directory and planning-aid text is also CC BY 4.0. Source content is not relicensed under
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
| Emergency calls and communications | ACMA 000/112/106 and CB sources; accessible calling note; NEMA AusAlert explanations; locating-device and beacon preparation readings | Device-specific satellite/beacon instructions, local radio coverage and actual check-in/rescue arrangements |
| Household planning and supplies | Qld plan/kit/home/pets; NSW evacuation; SA property/animals; NT/WA/Tas planning worksheets; original isolation-dependency worksheet | Full licensed local manuals where absent, actual support/destination/animal arrangements and completed suitable plans |
| Rural preparation | NSW rural fire/flood/animals; SA property/livestock; myGov remote basics; SWA isolated-work risks; Qld road/recovery/packing texts; route/supply/check-in and beacon worksheets | Assessed route and supply requirements, model-specific equipment/recovery manuals, broader pastoral and community-specific planning |
| Fire, flood and other hazards | NSW/Qld/SA readings; four Victorian CFA survival-guide sections; four ACT hazard articles; seven national standard English hazard factsheets | Detailed local operating manuals where absent, current local access/conditions and source-appropriate local arrangements |
| Accessibility and languages | Qld inclusive/mobility/vision readings; accessible-call navigation; four Yumplatok/Wik-Mungkan poster texts; seven hazards each in Simplified Chinese, Traditional Chinese and Arabic | Independent language/accessibility/community review, accessible audio/Easy Read where absent, further needs/languages and actual support arrangements |
| Food, water, smoke and sanitation | FSANZ basics/emergency/flood food texts; Qld food/water; NSW tank/groundwater/non-potable sources, smoke/mask/higher-risk and flooded-wastewater readings | Site-specific testing/treatment/system assessment, equipment conditions and extended remote supply needs; further licensed local procedures |
| Health | Emergency calls/poisons, existing SCHN videos and NSW bat-exposure factsheet; optional 35 personal ANZCOR originals with dedicated and ordinary-guide links | Public first-aid reuse permission, remaining source/context coverage and qualified review; individual care plans are not established |
| Power, gas and repairs | ESV generator, gas, flood energy/solar/battery, LPG cylinder and LCC27 compatibility source texts | Relevant equipment-specific instructions, other jurisdictional material where needed and site-specific professional assessment |
| First Nations and community planning | Four published-language poster texts; complete NSW Health Aboriginal-led public-health planning overview with linked-resource labels | Community-led local plans, consent/partnerships, jurisdiction-specific material and actual culturally appropriate services; linked toolkits are not bundled |
| Geographic directory | Six states, ACT, NT, Jervis Bay and seven external territories; remote management entries retain their limited scope | Detailed local/territory arrangements and verified current services; a directory is not an operational service inventory |
| Maps and places | Separate #38 provides eight capital, eight broader and six external extract definitions and review downloads; #90/#101 provide place-build/lifecycle work. Installed Victoria has 3,054 named points | Maintainer acceptance and official Setup publication; full address/coastal/navigation and Antarctic coverage remain absent |

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


Final water validation: **804 required contribution/build tests plus2 separately
run personal-distribution guards passed**,five skips/eleven upstream expected
failures in the required suite. The final combined source command passed **878
tests**,five skips/eleven expected failures,including both Australian builders,
personal-distribution guards,regional sources,state maps,map conversion,regional
place lifecycle and the GeoPackage place builder. Nine focused source tests pass.
An initial combined invocation used four wrong module paths and failed only those
imports;the corrected command is the878-test result. System Python's earlier792
pass skipped dependencies;the current result uses the existing development venv.

Actual public66/private387 engine searches and66 public reader hashes pass with
socket creation forbidden. Public household/rural251 references resolve;all four
installed private Australian guides resolve285 references,zero errors. Seven
personal-use records/42FTS units and Victoria's3,054names/per-file hashes remain.
The self-contained Mac build passes i18n,package/privacy scan,strict signature and
actual installed387/7 outbound-IP-denial self-check. Its roots/setup manifest are
unchanged,pinned inputs;no newTLS rerun claim.

Selected installed Mac review opens both water choices and all five new readers.
All19FAQ headings appear;selected screenshots check product/quantity conditions,
flooded-tank cautions,chemical/radiological do-not-drink limits and rural cards.
Source panels keep2022/2023/2026 dates distinct. User-clicked links update outer
title/source/Ask;Back from non-potable returns flooded-tanks. This is selected native
review,not all66 readers,actual testing/contamination/service availability or an
independent water-safety/clinical/accessibility audit. Windows/Linux native hooks,
HTTP-browser navigation and the earlier idle-watchdog issue retain their limits.

[66-record rainwater and groundwater contributor review](https://github.com/pilkster/lastbook/releases/tag/australia-rainwater-groundwater-review-2026-11-26)
contains public HTML,audits and engine evidence only. Personal-use material and
original PDFs remain excluded;earlier asset files remain unchanged.


## ACT hazard preparation,response and recovery

Four complete written ACT portal articles add bushfire,flood,severe storm and
heatwave causes,effects,risk and before/during/after phases. All36 accordion
label/full-answer pairs are expanded into ordered headings. Full introductions,
hero summaries and related-link labels remain. Normalized selected written text
compares exactly before/after technical HTML simplification. No source wording or
printed typos are rewritten. Maps,images,logos,icons,forms,PDFs,apps,medical manuals
and third-party destinations are not bundled or licensed by following a link.

The exact ACT portal policy grants CC BY4.0 with requested © Australian Capital
Territory credit,exceptions for third-party/separately conditioned material and
State/directorate/agency symbols/logos/trademarks/Coat of Arms. Its complete written
reuse/external-site/translation/security/liability/contact body is included as a
fifth record. ESA /copyright currently presents privacy/disclaimer text without an
explicit reuse grant;the ACT portal grant is not inherited by ESA,WorkSafe ACT or
linked manuals. SecureNT's current footer points to /page/copyright-and-disclaimer;
that exact acquired policy retains a no-reuse default except fair dealing/specific
CCgrants. No specific CCmarker was established on its cyclone page;NT body is not
bundled. The older NT policy address returned403 and is not treated as the current
policy. Exact response hashes and decisions are in ACT-HAZARDS-SOURCE-AUDIT-20261126.json.

Page metadata dates remain explicit:the three July pages were created January2025
and last updated1July2026;heatwave was created January2025 and updated16November2026.
Copyright metadata is17November2023/9September2026. These metadata dates are not
independent clinical/engineering review or a certified new advice edition. Today's
retrieved heatwave body differs from a stale search preview:it names1800MEDICARE
1800633422/noMedicarecard;July bushfire/storm retain healthdirect1800022222. Exact
source bodies and their contact lists remain separate. The national Health page
confirms the newer service;its body is not reproduced. Source emergency000
instructions remain. No actual service access,eligibility or clinical validation
is claimed. Phone-call/message warning descriptions remain dated and link the
existing10November2026 NEMA operational reading;no live warning capability is added.

Both household and rural guides expose the same four-reading ACT choice,prepare
and learn references. Rural-landowner Farm FireWise labels,outdoor workers,
animals,medical/medication/leave-early/stay-leave/floodwater/powerline and recovery
conditions remain. Linked detailed manuals/maps are excluded,so this does not
establish complete ACT operating-manual coverage. Public collection71records:
55official practical readings,13copyright statements,3original navigation records.


Final ACT verification passed **807 required contribution/build tests**,including
both Australian builders and personal-distribution guards,five skips/eleven
upstream expected failures. The full combined source command passed **879 tests**,
with the same skips/expected failures,including regional sources,state maps,map
conversion,regional place lifecycle and GeoPackage place construction. Ten focused
source tests passed. Actual public71/private392 engine checks and71 reader hashes
pass with socket creation forbidden. Public household/rural275 references resolve;
all four installed private Australian guides resolve309 references,zero errors.
Seven personal-use records/42FTS units and Victoria's3,054names/per-file hashes remain.

The matching self-contained Mac build passes i18n,package/privacy scan,strict
signature and actual installed392/7 outbound-IP-denial self-check. Existing pinned
roots/setup inputs remain unchanged;no newTLS rerun claim. Selected installed Mac
review opens both four-reading choices and all five ACT records. All36 expanded
section headings and before/during/after phases appear;selected screenshots check
bushfire escalation/leave-early/powerline text,heatwave contact/emergency000
separation,distinct July/November metadata and rural cards. Linked readers update
outer title/source/Ask;Back heatwave→storm passes. This is selected native review,
not all71 readers,actual calls/road-shelter-service availability or independent
clinical/fire/engineering/accessibility review. Windows/Linux-native behaviour,
HTTP-browser navigation and the earlier idle-watchdog issue retain their limits.

[71-record ACT hazard contributor review](https://github.com/pilkster/lastbook/releases/tag/australia-act-hazards-review-2026-11-26)
contains public HTML,audits and engine evidence only. Personal-use material and
original PDFs remain excluded;earlier release assets remain unchanged.


## Original practical planning aids — 26 November 2026

Three contributor-authored readings add a remote land-journey worksheet, a
home/property isolation dependency worksheet and a land-trip beacon checklist.
Both guides expose the same three-reading choice plus prepare/learn references.
The collection now has **74 records: 55 official practical readings, 13 copyright
statements and 6 original records**. The original planning aids are CC BY 4.0;
this grant covers the new writing, prompts and organisation, not cited agencies'
manuals, wording, imagery or branding. No new agency body is reproduced.

The journey worksheet records legs, verified resupply, chosen consumption and
water inputs, check-ins, missed-contact action and changed-plan decisions.
Its simple arithmetic gives no safe allowance, default reserve, route approval
or universal drinking-water minimum. Concern for a missing person's welfare
must not be postponed to a planned deadline or a presumed 24-hour waiting period.
The isolation worksheet follows essential activities through dependencies,
verified backups, actual duration, help and departure triggers. It does not
prescribe medical runtime, medication changes, wiring or generator size.

The beacon checklist distinguishes registration from battery expiry, borrowed
units from owner information, manufacturer-approved self-test from distress
activation, genuine distress from accidental cancellation, and one group from
separated groups. It preserves model-specific operating requirements, land scope,
rescue-authority keep-on instructions and variable rescue time. It provides no
button sequence, fixed test interval, marine/aviation compliance or overseas
permission. The exact factual source URLs/raw-response hashes and claim scopes
are in PLANNING-TOOLS-SOURCE-AUDIT-20261126.json. Queensland Parks' remote
breakdown context was available through the primary search result; the direct
raw fetch returned403, which is recorded rather than assigned a fabricated hash.

AMSA's beacon-site policy requires permission to reproduce its material. The
new writing summarises facts in original language and cites the sources; it
is not an agency-licensed adaptation or a copied operating manual. Tasmania SES's
general non-commercial policy and DFES's permission requirement also do not grant
redistribution of their manuals. Their bodies are excluded. Earlier licensed
agency readings retain their exact credits and source wording.

These are reading-only planning aids. They do not save a completed personal plan,
register a beacon, lodge an itinerary, place a call or check live roads/services.
Detailed remote driving/recovery, person/route/device-specific validation,
translated/First Nations planning and public first-aid rights remain incomplete.


Planning validation: **808 required contribution/build tests**, including both
Australian builders and personal-distribution guards, and **880 combined-source
tests** pass, each five skips/eleven upstream expected failures. Eleven focused
source tests pass. The initial sandbox run could not open the temporary localhost
test servers; the corrected complete runs used approved local-server access.
Actual public74/private395 engine searches,74 reader hashes and SQLite/FTS pass
with socket creation forbidden. Household144/rural149 references resolve (293
public); all four private Australian guides resolve327,zero errors.

The installed private Mac app contains395records:314base,74public Australian
and7personal. Runtime source d07a089c8dd8be9acaa8d22622a3ade5c0c20c8e passes
package/privacy scan,i18n,strict signature and actual395/7outbound-IP-denial
self-check. All81Australian record hashes,42personal FTS units and unchanged
Victoria map hashes/3,054names remain. Full previous392app/library copies are
retained. Pinned roots/setup inputs are unchanged;no newTLS rerun is claimed.

Selected installed Mac review opens both three-card choices and all three new
readings. Journey fuel/water arithmetic and its limits,check-in/missing-person
conditions,the six isolation dependency prompts and separate beacon genuine-
distress/accidental-cancellation sections appear. Screenshots check supply text,
dependency layout,beacon condition/number separation and both choice layouts.
Journey→beacon linked navigation updates reader/source/Ask;Back returns to the
journey reader. This is selected native verification,not all74readers,actual
calls/routes/services,independent professional/accessibility validation,
Windows/Linux-native,notarization or long-idle proof. Earlier idle-watchdog and
HTTP-browser navigation limits remain.

[74-record practical planning contributor review](https://github.com/pilkster/lastbook/releases/tag/australia-practical-planning-review-2026-11-26)
contains public HTML,audits and engine evidence only. Personal-use material and
original agency PDFs are excluded. Previous release assets remain unchanged.


## Published-language poster text — 26 November 2026

Four short Queensland Government posters add **Yumplatok (Torres Strait Creole)**
and **Wik-Mungkan** source text for bushfire/heatwave and cyclone/flood preparation.
Each language receives a two-reading choice in both household and rural guides,
with all four readings also in prepare/learn. The public collection now contains
**78 HTML records: 59 official practical readings, 13 copyright statements and
6 original records**.

All four original one-page PDFs were rendered and inspected. Complete practical
wording, five bullets per poster, order, punctuation and the source contact footer
compare exactly with normalized PDF extraction. Wrapped lines are joined; no new
translation, spelling correction or cross-language rewriting was performed. The
Wik cyclone bullet's “aak” and bushfire “ak”, and Yumplatok “Meke”/“Mek” source
variation remain. Source body language tags are tcs/wim; English metadata/context
remain separate. This does not establish fluent-speaker, cultural or accessibility
validation. These are short text-only preparedness posters, not full response
manuals or independently validated Easy Read editions.

The exact official listing's metadata is updated13October2026; its printed review
date is4January2024. Each PDF's metadata records creation19March2024 and
modification20March2024. These dates are retained separately from November2026
retrieval; none is a new advice or translation review date. The printed Queensland
Community Recovery contact1800173349 remains separate from emergency000. Printed
website/social references are inert source text; no call, registration, warning
or service availability is established by the app.

The current qld.gov.au copyright policy explicitly covers material on or through
that site unless otherwise noted, under CC BY4.0 with State of Queensland credit.
All four files identify Queensland Government in PDF metadata, are directly
linked under the named-language headings and show no separate text licence or
third-party text credit. Artwork, culturally specific design, pictograms, logos,
Coat of Arms, trademarks and original PDFs are excluded. The complete source text,
raw response hashes, metadata and exclusions are recorded in
LANGUAGE-POSTERS-SOURCE-AUDIT-20261126.json. No licence is inferred for the separate
getready.gov.au national resource site from its branding or NEMA announcement;
that resource guide and its manual bodies remain to be reviewed.

This starts published-language coverage; it does not cover every First Nations
community/language or supply locally agreed plans. More detailed translated
manuals, fluent-speaker/community review, accessible formats and offline audio
remain incomplete. Earlier source rights, personal-use distribution boundaries,
map assets and remaining remote/clinical gaps are unchanged.

Native review prompted a source-first layout: each complete published-language
quote now precedes the English date, attribution, licence and context notes.
The brief opening label identifies the language and excluded artwork. Source
wording and metadata are unchanged.


Final poster verification: **809 required contribution/build tests** and
**881 combined-source tests** pass, each five skips/eleven upstream expected
failures;12 focused source tests pass. Both suites were rerun on the final
source-first reader order. Actual public78/private399 engine checks and all78
reader hashes pass with sockets forbidden. Household156/rural161 references
resolve (317 public); all four private Australian guides351,zero errors.

The installed Mac runtime a1847f8 passes i18n,package/privacy scan,strict signature
and actual399/7outbound-IP-denial self-check. The source-first layout is data-only
at combined c98c236; no shipped code/guide path changed,so the scanned binary was
preserved. All85Australian hashes,42personal FTS units and unchanged Victoria map
hashes/3,054names pass. Full395app/library and subsequent pre-layout399data copies
are retained. Pinned roots/setup inputs remain unchanged;no newTLS rerun claim.

Selected final installed Mac review opens both language choices in both guides
and all four readers. Complete five-bullet sets,source spelling/Unicode punctuation,
printed footer and separate metadata/context appear. Screenshots inspect source-
first Yumplatok/Wik bushfire readers and rural cards. Outer title/source/Ask follow
the target;Back returns to the choice. This does not establish all78-native,
fluent-speaker,cultural/accessibility validation,actual calls/services,Windows/
Linux-native,notarization or long-idle reliability. Earlier idle-watchdog and HTTP-
browser navigation limits remain.

[78-record published-language contributor review](https://github.com/pilkster/lastbook/releases/tag/australia-published-language-review-2026-11-26)
contains public HTML,audits and engine evidence only. Original PDFs/artwork and
personal-use material are excluded;earlier release assets remain unchanged.


## National Get Ready standard factsheet texts — 26 November 2026

Seven complete two-page standard English factsheet texts add national bushfire,
cyclone, earthquake, flood, heatwave, storm and tsunami preparedness. Both guides
expose the same seven-reading choice plus prepare/learn references. The public
collection now has **85 records: 66 official practical readings, 13 copyright
statements and 6 original records**. These are standard English factsheets, not
the separate illustrated Easy Read editions or new translations.

The permission review established a direct licensed source rather than inheriting
terms from the national microsite. All seven PDFs are served byte-for-byte
identically on getready.qld.gov.au. Its current footer explicitly links to
qld.gov.au/legal/copyright, whose CC BY4.0 grant covers material on or through
that site unless otherwise noted. The exact copies identify Queensland
Reconstruction Authority as author and show no separate text licence/third-party
text credit. State/QRA credit and exclusions are retained. All photos, artwork,
branding, diagrams, icons, QR codes and original PDFs are excluded. No blanket
licence is inferred for all getready.gov.au assets or for another agency.

The 55-page national resource guide was acquired and its sharing guidance
inspected. Pilot cyclone/flood Easy Read originals explicitly reserve stock/custom
image reuse to permission from Information Access Group. Those originals/images,
Easy Read text adaptations, other translations, videos and audio are excluded
from this addition. Further language/community and accessible-format review
remains incomplete.

All14standard factsheet pages were rendered at1800px and inspected. All4,944
nonbranding source word tokens compare between raw extraction, coordinate-based
panels and final HTML. Column/panel reading order becomes linear; lists/questions
remain distinct. Checkboxes become lists; earthquake graphic step numbers retain
their action associations. Typography/line-wrap artifacts are normalized without
correcting source spelling, quantities or conditions. An overlapping fi ligature
and fragmented checklist initials were caught by the independent comparison.
The tsunami source's printed “eastern costs” typo remains. Source statistics and
simple hazard descriptions remain source statements, not independent research.

Complete warning labels, planning prompts, leaving/floodwater/aftershock
conditions, heat-stroke escalation and alert/responsive-only drinking condition,
tsunami immediate-action/route/distance/last-resort building conditions, kit lists
and TIS/emergency distinctions remain. Source three-day/3litre assumptions stay
separate from other readings and person/place-specific needs. These short
preparedness readings do not establish detailed property defence, clinical or
engineering review, safe local roads, open shelters or actual service access.

PDF metadata records creation19February2026; modification is20February for six
factsheets and6March for tsunami. The national project was announced in September;
November retrieval does not mean a new clinical or engineering review. Exact raw
response hashes, licensed-host equality, footer/policy chain, all source panels
and exclusions are in NATIONAL-HAZARDS-SOURCE-AUDIT-20261126.json. The four earlier
language posters' English context now says “quoted words” after their source-first
layout; no published-language wording changed.


Final verification of this national-hazard addition: **810 contribution/build tests
and882 combined-source tests pass**, each five skips/eleven upstream expected
failures;13focused source tests pass. Both final full suites include the native
review's tsunami-heading correction. Public85/private406 engine searches and all85
public reader hashes pass with socket creation forbidden. Household/rural177/182,
health13and personal21references resolve393total with zero errors. Personal7/42FTS,
all92AUcontent hashes and Victoria's3,054names/per-file map hashes remain intact.

The private Mac app freezes combined725dee3. Reader-only data correction is at
combineda497514; no shipped runtime or guide path changed, so that scanned and
strictly verified binary is preserved. i18n, package/privacy scan and actual
installed406/7 IP-denial self-check pass. Pinned roots/setup manifest are unchanged;
no new TLS rerun is claimed. Previous full399app/data and pre-layout406data remain
available privately for rollback. The entire private library is PERSONAL USE ONLY.

Selected installed Mac checks open both seven-reading choices and all seven
readers. Screenshots inspect earthquake steps/fallback, heatstroke conditions,
final tsunami signs/immediate action/conditional building fallback and rural cards.
Native review found three tsunami labels running into their answers; separate
headings now preserve all original words/order and have been rechecked. Reader
source/Ask targets and Back-to-guide context remain. No all85reader/native-platform,
professional/accessibility,live-service,notarization,newTLS or long-idle claim.
Earlier idle-watchdog and HTTP-browser navigation gaps remain unresolved.

The matching public85HTML-only contributor prerelease is
https://github.com/pilkster/lastbook/releases/tag/australia-national-hazards-review-2026-11-26
with source audits/checksums. It is not an official Setup pack or maintainer
acceptance. Extract supplements into a new folder; never replace an existing
installed catalog with this smaller collection. No personal-use PDFs/text or
original agency PDFs are distributed. Earlier assets remain unchanged.


## Queensland driving, breakdown and recovery-strap sources — 26 November 2026

Four dated readings add complete written road-condition and motorway-breakdown
articles,all seven recovery-strap steps,and three selected vehicle/towing/outback
packing sections. Household and rural guides receive identical additions.
The breakdown article includes both full written video transcripts,not video files.
All selected source words,lists and conditions compare in order;metadata dates
remain2023,2024,2020and2014 respectively. The2014introductory driving-hour limit
and tyre/brake/windscreen/stalling procedures are deliberately outside the selected
checks/packing reading;current vehicle-specific instructions still need review.

Every selected page explicitly supplies CC BY4.0 metadata and links the Queensland
copyright policy. State credit/exclusions remain. ROAD-RECOVERY-SOURCE-AUDIT-20261126.json
pins raw responses,source text,headings,transcripts,licences and selection scope.
Motorway exit/stay conditions and Queensland13 19 40contact are separate from
remote-survival guidance and national000. Strap rating/attachment/bystander/training
conditions remain source-specific,not legal certification or a verified recovery
plan. Source packing quantities do not establish adequate supplies for an actual
route/person/vehicle. No original images/video/PDFs,permits,maps or manufacturer
manuals are bundled. AMSA beacon reproduction still requires permission;Main Roads
WA's general terms are insufficient for unrestricted public redistribution.


Final road/recovery validation: **811 contribution/build tests and 883 combined
source tests pass**, each five skips and eleven upstream expected failures;
14 focused source tests pass. Offline engine checks forbid sockets and verify
public89/private410 searches, all89 public reader hashes and both four-reading
choices, while retaining prior choices. Household/rural189/194, health13 and
personal21 references resolve417total with zero errors. All96Australian content
hashes, personal42FTS units and Victoria per-file map hashes pass.

Private Mac runtime2edf215 passes i18n, package/privacy scan, strict signature and
actual installed410/7IP-denial self-check. Full prior406app/data retained for
rollback. Pinned roots/setup inputs unchanged; no newTLS rerun claim. Selected
native review opens both choices/all4readers; screenshots inspect motorway
exit/stay conditions, recovery attachment/exclusion/bystander/training text,
2014packing scope/quantities and rural cards. No all89native, independent
mechanical/recovery/legal/accessibility review,live-service,notarization or
long-idle claim. Earlier idle-watchdog and HTTP-browser navigation gaps remain.

The public89HTML-only contributor prerelease is
https://github.com/pilkster/lastbook/releases/tag/australia-road-recovery-review-2026-11-26
with source audits/checksums. Extract into a new folder; never replace an installed
catalog with this smaller supplement. No personal-use PDFs/text, original agency
PDFs, images/video or manufacturer manuals are distributed. Contributor review,
not officialSetup/maintainer acceptance. Earlier release assets remain unchanged.


## Chinese national hazard factsheets — 26 November 2026

Fourteen complete publisher-written standard factsheet texts add all seven national
hazards in Simplified Chinese and Traditional Chinese, equally in household/rural
guides. Each PDF has a byte-identical direct Get Ready Queensland copy; linked
Queensland CC BY 4.0 policy, State/QRA credit and exclusions are documented. No
original PDFs, imagery or branding are bundled. CHINESE-HAZARDS-SOURCE-AUDIT-20261126.json
pins source receipts, 28 visually inspected pages, panel associations, character
counters and individual March/April file dates. Source text is not newly translated,
corrected or converted. The interface and contributor notes remain English.

Han substring search fixes short Chinese terms inside unsegmented text in reader
search, assistant keyword retrieval and libq without replacing the index or Latin
FTS behavior. Use the matching updated runtime: a data-only supplement cannot add
this search behavior to an older application. No script conversion, Chinese word
segmentation or independent translation/accessibility review is claimed. Other
languages, community review and accessible/offline audio formats remain gaps.

Chinese reading validation: **820 contribution/build and 892 combined-source tests
pass**, each five skips and eleven upstream expected failures. Fifteen focused
source tests and eight Han-search tests pass. All 20,838 non-whitespace source
characters compare through independent raw extraction, coordinate panels and
final HTML. This protects text completeness; it is not fluent-speaker review.

Actual public103/private424 engine checks forbid sockets and verify all14 Chinese
queries, scoped keyword retrieval, libq, highlighted snippets and all103 public
reader hashes. Household/rural231/236, health13 and personal21 references resolve
501 total, zero errors. Private all110 Australian content hashes, personal42 FTS
units and Victoria per-file map hashes pass. On this staged library the first
observed Han query took0.5828s; other uncached single-Han checks were under0.09s.
Some repeated queries were cached; this is not a general performance guarantee.

Installed Mac runtime bc4a93a passes package/i18n/privacy scan, strict signature
and actual424/7 outbound-IP-denial self-check. Full prior410 app/data copies remain.
Pinned roots/setup inputs are unchanged. Selected native checks opened all14 new
readers, both script choices in both guides, Chinese substring searches, result
highlighting, source/Ask targets and Back context. Screenshots inspected Chinese
fonts, tsunami conditions and Traditional Chinese heatstroke drinking conditions.
The app remains open on the rural Traditional Chinese choice. This does not claim
all103-reader visual QA, independent translation/accessibility review, new TLS,
Windows/Linux-native, notarization or long-idle validation. Earlier watchdog and
HTTP-browser navigation gaps remain.

Public103 text-only review, audits and checksums:
https://github.com/pilkster/lastbook/releases/tag/australia-chinese-hazards-review-2026-11-26
Extract into a new folder; never replace an installed catalog with this smaller
supplement. Use matching updated source/runtime for Han substring search; this
data-only archive cannot update an old application's search code. No private-use
ANZCOR PDFs/text, original source PDFs, imagery or maps are distributed. Contributor
prerelease, not official Setup availability or maintainer acceptance. Earlier
release assets are unchanged. Remaining language/community/accessibility, remote
operations, local/territory and public first-aid rights/review work stays open.


## Northern Territory local planning — 26 November 2026

An original contributor worksheet connects factual NT contact/warning references
to separate cyclone wind,surge,flood,bushfire,shelter,animal and isolation planning.
Both household and rural guides receive the same worksheet and three existing
national hazard readings. Agency texts are reserved: SecureNT links the NT general
copyright policy,and PFES has a limited internal/noncommercial permission,not an
unrestricted redistribution grant. No agency article,official plan,PDF,shelter map,
translation or branding is bundled or relicensed. NT-PLANNING-SOURCE-AUDIT-20261126.json
pins successful raw receipts,reported403acquisition limits,web-reviewed official
factual sources and the original worksheet's CC BY4.0 scope.

The contact reference retains its displayed2024date;other retrieved planning
pages have November2026metadata. Opening announcements govern public shelter use.
Designated Darwin car-park pet options are distinct from public emergency shelters;
ordinary car parks are not inferred safe. Source72hour/10litre household quantities
are separate from actual supply adequacy. No completed plan is stored. The NT
directory check is refreshed to26November;the other original state/ACT dates remain.
Public collection now104=84official practical+13copyright+7original records. Full
NT/local manuals,professional/community review and actual routes/shelters/supplies
remain open work.

NT planning validation: **821 contribution/build and 893 combined-source tests
pass**, each five skips and eleven upstream expected failures;16 focused source
and8 Han tests pass. Actual public104/private425 engine checks forbid sockets and
verify NT searches,all104 public reader hashes,the same four-reading NT choice
in household/rural guides and retained Chinese query/retrieval/libq behavior.
Guide references resolve237 household,242 rural,13 health,21 personal:513 total,
zero errors. Private all111 Australian content hashes,42 personal FTS units and
Victoria's3,054 names/per-file map hashes pass.

Installed Mac runtime22942c1 passes package/i18n/privacy scan,strict signature
and actual425/7 outbound-IP-denial self-check. Full prior424 app/data retained;
pinned roots/setup inputs unchanged. Selected native review inspects the new
worksheet's contact table,shelter-opening/car-park distinction,supply conditions,
source/authorship notes and both guide choices;actual search,reader,Ask and Back
context pass. App remains open on rural NT choice. No all104-reader visual QA,
independent fire/building/veterinary/clinical/accessibility/community review,
actual local opening/route/service assessment,Windows/Linux-native,notarization,
newTLS or long-idle claim. Earlier watchdog/HTTP-browser navigation gaps remain.

Public104 original-NT/text-only review,audits and checksums:
https://github.com/pilkster/lastbook/releases/tag/australia-nt-planning-review-2026-11-26
Extract into a new folder;never replace a full installed catalog with this smaller
supplement. Matching updated runtime is still required for short-Han search.
No reserved NT agency article,PDF,shelter map,translation or branding is bundled;
CC BY4.0 covers only the new original contributor worksheet. Personal-use ANZCOR
PDFs/extracted text,private profile,maps,models and videos are excluded. Contributor
prerelease,not official Setup availability or maintainer acceptance;earlier assets
unchanged. Broader NT/local manuals,language/community/accessibility,remote and
public first-aid rights/review remain open work.


## HTTP browser linked-reader context — 26 November 2026

The browser reader now opens supported local links through the outer reader,
keeping the current title,publisher,source details,Ask,Save and history together.
Previously an NT worksheet link could display Emergency calls inside the iframe
while its outer source context still described the worksheet. A trusted relay
validates the active iframe,origin,source,random token and route. Saved-page CSP,
opaque origin and script prohibition are unchanged. Missing user-activation
metadata produces a trusted Open reading button. Native desktop routing remains
separate. See BROWSER-READING-LINKS.md for limits and the implementation contract.

Nine focused tests pass. Required upstream suite on main plus this independent
fix passes792;Australian contribution/build passes830;combined source passes902.
Each full suite has five skips and eleven upstream expected failures. Three setup
fixture failures reproduced on unchanged main;mocked disk capacity fixes the
fixtures without changing production storage reserves. Selected actual Chrome
checks cover source/Ask,Back/Forward,Save and fallback;an actual host-page console
probe confirmed DOM isolation and was removed before final tests/build. Installed
Mac linked-reader/Back checks retain the native path without the HTTP nonce.

Installed frozen runtime f8a124aa3b9107dabb8cea5f3f8a134b9bd5977d passes packaging,
i18n,privacy,strict signature and actual425/7 outbound-IP-denial self-check. All111
Australian content hashes,42 personal FTS units,513 guide references and Victoria
map hashes/3,054 names remain. Full previous425 app/data copies are retained.
The public104-record collection and NT release assets are unchanged;no new content
ZIP is needed. Data-only supplements cannot update an older reader runtime.

This closes the reproduced HTTP linked-reader source-context gap for the stated
scope. It does not establish every browser,encoding,document or long-idle behavior;
the earlier idle-watchdog issue remains unresolved. Community/professional review,
broader language/accessibility/local/remote coverage,public first-aid rights and
official maintainer acceptance remain open. The entire installed private profile
remains PERSONAL USE ONLY;no private ANZCOR material is published.


## FSANZ consumer food safety — 26 November 2026

Three complete consumer articles now cover food-safety basics, emergency/outage
preparation and disposal, and flood contamination/cleanup. Both household and rural
guides receive the same three-reading food-safety choice and prepare/learn entries.
A fourth record preserves the complete exact-site copyright and disclaimer texts.
The collection is now **108 records: 87 official practical readings, 14 source-rights
records and 7 original records**. All previous readers and choices remain.

Each source page links FSANZ's exact-site policy. It grants CC BY 4.0 reuse except
logos and third-party material, requires © Food Standards Australia New Zealand
and prohibits implied endorsement. The policy's “Attribution 4.0 Australia” wording
is retained; its actual licence link is CC BY 4.0 International. Images, logos,
videos, external source bodies and linked downloads are excluded. The source audit
pins five raw responses, displayed dates, article boundaries and complete text in
source order. This is not independent food-safety or clinical review.

Dates remain July/October 2025 for the consumer articles, October 2026 for copyright
and February 2025 for the disclaimer. Source-specific cooking temperatures retain
their associated food lists; room-temperature periods are distinct from the
closed-fridge/freezer estimates. Floodwater exclusions, the not-touched-floodwater
condition for potentially salvageable cans/pouches, cleaning/sanitising sequences,
water advice and separate food-business restrictions remain. Source sanitising
quantities are preserved, not recast as universal product instructions. No current
recall, local water declaration or actual appliance performance is established.
The separate business 2-hour/4-hour article is not substituted for consumer text.

**831 contribution/build and 903 combined-source tests pass**, each five skips and
eleven upstream expected failures; 17 focused source, 8 Han and 9 browser-link tests
pass. Actual public108/private429 engine checks forbid sockets and verify every
public reader hash, food queries/scoped retrieval, both choices, retained Chinese
queries and earlier additions. The four private Australian guides resolve 531
references: 246 household, 251 rural, 13 health and 21 personal; zero errors.
Private staging preserves all115 Australian content hashes,42 personal FTS units
and Victoria's3,054 names/per-file hashes. Frozen source fb86dfb passes package,
i18n,privacy and strict signature checks with unchanged pinned roots/setup inputs.

The public supplement remains data-only. Updated runtime is required for Han
substring search and HTTP linked-reader source context. Extract into a new folder;
never replace an installed full catalog with the supplement. Personal ANZCOR
PDFs/text are excluded. Broader local/language/accessibility and community review,
remote operations, public first-aid rights/clinical review, maintainer acceptance
and the earlier idle-watchdog issue remain open.


The installed429/7 offline-IP-denial self-check and strict signature pass. Selected
native Mac review opens all four new readers,inspects food-specific cooking and
cold-storage lists,flood disposal/salvage/business conditions and cleaning steps,
and verifies source dates,Ask,local policy-link context,actual retort-pouches
search and Back. Both guide choices show the same three source cards. The app is
left open on rural food-safety. Full previous425 app/data copies are retained.
These checks do not establish all108-reader visual QA,independent food-safety,
clinical,community or accessibility review,every browser/encoding,Windows/Linux,
notarization,newTLS or long-idle reliability. Public review release:
https://github.com/pilkster/lastbook/releases/tag/australia-food-safety-review-2026-11-26


## Public first-aid source-rights review — 26 November 2026

`AUSTRALIA-FIRST-AID-SOURCE-REVIEW.md` and its JSON receipt document 15 successful
primary acquisitions. Exact-site policies differ: NSW Ministry CC terms do not
clear SCHN or NSW Ambulance. Conditional unchanged-resource licences from St John,
ACSQHC and AWFA are recorded accurately rather than labelled categorically unusable.
AWFA's specific v7.4 manual has a restrictive internal-copy notice, independently
rendered/inspected, so its general website grant is not applied to that manual.
Ambulance Victoria has an explicit website CC grant, but campaign/transcript
recognition wording and hands-only CPR scope need qualified review. No newly
combined treatment algorithm or candidate clinical source is added to the pack.

ANZCOR directs Australian enquiries to ARC; info@resus.org.au was rechecked against
the official contact page. A six-guideline distribution/indexing/accessibility/
clinical-review enquiry is prepared locally and remains unsent. No permission or
endorsement is claimed. Approval, review, generation and retrieval dates are
separate; a 2026 generated timestamp does not establish a 2026 clinical review.

This increment changes review documentation only. Public108/private429 records,
frozen runtime fb86dfb,531 guide references and all prior release assets remain
unchanged. The 831/903 source-suite results above remain evidence for that unchanged
product; no new clinical or full-suite validation is claimed from this rights audit.


## Dated infant CPR source status — 26 November 2026

The stored SCHN 2025 infant demonstration uses a different compression technique
from the checked current ANZCOR Guideline 6. Captions and an actual decoded frame
were verified. Its guide card, choice hint and intro identify the source date,
comparison date and pending qualified review. The original source hub contains a
dated status note and primary URL. The video remains unchanged. No replacement
treatment protocol or clinical PDF is introduced.

Three exact AWFA posters were acquired, rendered and inspected as potential
unchanged-PDF resources. They remain research only. Adult depth descriptions were
resolved against ANZCOR's own text and are not classified as a conflict. The
all-ages poster's infant method remains a review item; an EpiPen usage poster is
not automatically a complete anaphylaxis plan. Conditional reuse and clinical
completeness are separate questions. See [source-status review](AUSTRALIA-INFANT-SOURCE-STATUS.md)
and `content/regions/au/INFANT-CPR-SOURCE-REVIEW-20261126.json`.
The ARC enquiry remains unsent; no grant is claimed.

Public 108/private 429 record counts and 531 guide references remain unchanged.
**832 contribution/build and 904 combined-source tests pass**, each with 5 skips
and 11 expected failures. Eighteen focused source, 8 Han and 9 browser-link tests
pass. Actual public/private engine checks forbid sockets and verify source-status
search, private health-card resolution, all 108 reader hashes and retained
food/Chinese/NT choices. Staging preserves all 115 Australian hashes, 42 personal
FTS units, Victoria's 3,054 names/map hashes and the infant video's exact hash.
Frozen source `2f4dbbd` passes package/i18n/privacy, strict signature and the actual
installed 429/7 outbound-IP-denial self-check. Pinned roots/setup inputs remain
unchanged. Full previous 429-record app and library backups remain.

Selected installed Mac checks verify the health intro, expanded child/baby hint,
infant card note and source-hub reader; Back restores the expanded choice. A native
screenshot confirms the inspected card/hint are readable. No clinical approval,
all-reader/all-browser check or long-idle reliability is claimed.

Matching updated runtime/guide assets are needed for the card/hint; a data-only
pack cannot update an older executable's bundled guide JSON. The hub note is data.
The [108-record source-status review](https://github.com/pilkster/lastbook/releases/tag/australia-infant-source-review-2026-11-26) includes the updated hub and
checksums. Earlier release assets remain unchanged. Contributor prerelease,
not official Setup publication or maintainer acceptance.


## Western Australia and Tasmania local planning — 26 November 2026

Two original contributor readings fill a local-planning gap equally in household
and rural guides. WA covers the 15 July 2024 warning-system transition, separate
cyclone wind/water risks, departure, animal accommodation and service purposes.
Tasmania covers access/service dependencies, distinct evacuation/last-resort
arrangements, map-symbol limits, warning backups and human/animal support.
Each choice also links three retained national factsheets. The hub links both.

DFES requires written reproduction permission. Tasmania's general grant is
noncommercial; no unrestricted manual grant is inferred. No DPIRD grant is assumed.
Only original writing and brief attributed facts are published; agency bodies,
manuals, plans, images and maps remain research only. Eleven successful raw
acquisitions and the reported Tasmanian policy403 are pinned in the source audit.
That policy was separately read on the official site through the web tool.
TFS's dynamically generated footer time is not treated as a substantive review date.

Public collection:110 =87 official practical+14 rights+9 original records.
Full WA/Tas manuals, local/professional/community review and actual warnings,
access, centres, animal places and completed plans remain outstanding.

Validation: **833 contribution/build and 905 combined tests pass**, each with
5 skips and 11 upstream expected failures. Nineteen focused source, 8 Han and
9 reader-link tests pass. Actual public110/private431 engine checks forbid sockets;
all110 reader hashes, new WA/Tas queries/scoped retrieval, both local choices and
retained earlier choices pass. All555 guide references resolve without errors:
258 household,263 rural,13 health,21 personal. All117 AU content hashes,42 personal
FTS units,Victoria3,054 names/map hashes and exact infant video hash are preserved.
Frozen source `ca150fa` passes package/i18n/privacy, strict signature and installed
431/7 outbound-IP-denial self-check. Pinned roots/setup inputs are unchanged.
Full429 predecessor app/library backups remain.

Selected native Mac checks verify both new readers and matching source details,
current WA warnings/contact purposes, Tasmanian last-resort/evacuation distinctions,
both local choices in both guides, Tasmanian Ask context and Back navigation.
Native screenshots inspect readable text and source panels. App remains open on
rural planning with both new choices expanded. No independent local/professional/
community/accessibility review or long-idle reliability is established.

[110-record public local-planning review](https://github.com/pilkster/lastbook/releases/tag/australia-wa-tas-planning-review-2026-11-26):
archive extraction, CRC, hashes, FTS, Han and privacy checks accompany the download.
New choices require matching bundled guide JSON/runtime; a data-only archive
cannot update an older executable's guide assets. No production manifest, new
dependency, downloader, TLS or network-policy change. Earlier assets are unchanged.


## Mac modal heartbeat accounting — 26 November 2026

A stand-in WebKit completion test reproduced a separate false watchdog verdict:
three heartbeat answers delayed across app-owned modal waits counted as three
slow answers after the dialogs had closed. The Mac shell now measures
heartbeat latency on a clock that excludes only app-owned modal time. Active
delay before and after a modal still counts toward the original slow threshold.
A queued answer must still arrive before releasing its byte acknowledgements.
Twenty-one focused Mac tests cover modal timing/nesting, ordinary slow/unanswered
termination, byte budgets, stale callbacks and sheet callback order on both the
development Python and frozen-build Python. These tests create no real window or
WebKit process. Thresholds, memory/network/frame protections and source data are
unchanged. No background scheduling policy change is made.

This is not an established cause or complete fix for the historical idle event.
That single not-answering log event remains unexplained. New native checks must
retain their selected scope; no long-idle or all-modal WebKit guarantee follows
from the deterministic completion-order tests.

Independent main-based fix: [PR491](https://github.com/Immortal-Protocols/lastbook/pull/491).
Final required suite792 passes; Australian contribution842 and combined914 pass,
each5skips/11upstream expected failures. Nine new heartbeat cases are included.
The standalone PR also carries the test-only synthetic disk-capacity fixture
correction already in PR487. The three fixture failures were reproduced against
unchanged upstream; production storage reserves are unchanged.

Frozen source `f2fb94d` passes package/i18n/privacy, strict signature and the actual
installed431/7 outbound-IP-denial self-check. All58 bundled content/web/setup assets
are byte-identical to the prior WA/Tas runtime. All117 Australian content hashes,
42 personal FTS units,Victoria3,054 names/map hashes and exact infant video hash
are retained. Catalog,search index,reference manifest,map-set and personal marker
remain byte-identical even after selected native navigation. Public110/private431
counts and555 guide references are unchanged. No new data release or asset edits.
Full prior app is retained for rollback; library data is unchanged.

Selected installed Mac navigation opens rural WA→reader→linked isolation reader,
sets the matching Ask context and returns through reader history to the expanded
guide choice. No new page-kill event appears. Actual modal WebKit timing,controlled
sleep/background behavior and long-idle reliability are not established by these
selected checks. The earlier one-event idle failure remains unexplained.


## Document language and plain-text direction — 27 November 2026

[Independent PR493](https://github.com/Immortal-Protocols/lastbook/pull/493) forwards
the declared document language to plain text and Read aloud. An exact locale is
preferred, then a matching local language-family voice. Without a matching local
voice the button stays hidden; unlabelled records retain the computer-language
fallback. LocalService-only speech is retained. English interface text is unchanged.

Plain-text paragraphs use automatic direction independently. Numeric runs have
left-to-right isolates so groups in 131 450 retain their printed order in Arabic.
Language attributes and text are escaped; digits and indexed/spoken text remain
unchanged. The Australian HTML builder accepts only rtl/ltr/auto direction and
text-only bdi elements. No new translation, voice download or dependency is added.

Final stable-source suites pass **801 standalone, 861 Australian contribution and
933 combined tests**, each with five skips and eleven upstream expected failures.
Ten new language tests exercise actual API/reader/speech code; eight existing
speech tests and twenty focused Australian source tests pass. The shared setup
fixtures mock synthetic capacity as in PR487/491; production disk reserves remain.
Combined server AST outside public() matches the prior integrated map server.

Frozen source `1a291fadaab4a3c8564cc54cd30b6804f2d648b4` passes package/i18n/privacy,
strict signature and installed431/7 outbound-IP-denial self-check. Of58 bundled
content/web/setup assets, only web/app.js,web/app.css,web/speak.js differ from the
modal-fix runtime. All431 records,110 public AU records,555 guide references,
117 AU hashes,42 personal FTS units,Victoria3,054 names/map hashes and exact infant
video remain. Catalog/search/reference/map-set/personal marker are byte-identical
after selected native checks. A full prior app rollback copy is retained.

Chrome synthetic loopback fixtures show Arabic paragraphs right-aligned, English
paragraphs left-aligned and 131 450 in order. Installed Mac checks open existing
Chinese floods in Page/Text views, observe Read aloud→Stop reading→Read aloud,
then matching Ask context and Back. No audio/pronunciation quality is established;
the browser Arabic click did not establish sustained playback. These are selected
render/control checks, not professional translation/accessibility or long-idle
approval. The historical idle cause remains unproven. Temporary preview stopped.

Seven Arabic publisher factsheets are research drafts only; extraction and all
source/HTML reading-order reviews are still pending. They are absent from this
catalog and release. Public110/private431 counts and the existing WA/Tas data
release remain unchanged. No original PDF/media, private first-aid source or
installed profile data is included in the public contribution. Broader rights,
clinical/community/local/accessibility review and official acceptance remain open.


## Arabic national hazard factsheets — 27 November 2026

Seven complete publisher-written Arabic standard factsheet texts cover bushfire,
cyclone,earthquake,flood,heatwave,storm and tsunami preparation, equally in both
household/rural choices and preparation/deeper-reading lists. Sources were acquired
26 November; all14 original pages were visually inspected and the exact licensed
site footer/policy refreshed27 November. Each directly hosted Get Ready Queensland
PDF is byte-identical to its national counterpart. QRA author metadata, State/QRA
credit, CC BY4.0 policy link and exceptions are recorded in
ARABIC-HAZARDS-SOURCE-AUDIT-20261127.json. Original PDFs,imagery,diagrams,icons,QR,
branding,Coat of Arms,trademarks and third-party/separately licensed assets are
excluded. No blanket licence for other national-site material is implied.

Ordinary PDF extraction corrupts some Arabic glyph order,word spacing and accents.
Research-only glyph recovery uses font maps,position and tagged structure,repairs
four exact malformed replacement-text patterns (including one extra alef mapping),
places/deduplicates combining marks and restores a visible header word gap.
Publisher wording and spelling are retained; no new translation or grammar editing.
The research parser and its dependencies are not shipped. Ordered source text and
final HTML agree after documented encoding/formatting recovery; character counts
alone are not proof of correct reading order or an independent translation review.

HTML declares Arabic/right-to-left direction, English source notes declare English/
left-to-right direction and numeric runs retain their printed order in isolates.
Earthquake numbered action labels remain paired; warning labels,planning questions,
heatstroke consciousness/response condition,tsunami last-resort height,water quantity,
flood exclusions and service references remain. The English interface is unchanged.
Matching-runtime document-language speech requires an installed local voice; no
voice download,independent audio/pronunciation/accessibility/community or clinical
review is claimed. These static readings do not establish local warnings,routes,
services,shelters or adequate supplies for any individual trip/person.


Arabic release verification: **862 contribution/build and934 combined-source tests
pass**,each5skips/11upstream expected failures.21source,10document-language,8speech
tests pass. Actual public117/private438 engine checks forbid sockets and verify
seven Arabic reader searches,highlighted snippets,scoped assistant retrieval and
libq. Both guides retain all earlier choices. All597 private AU references resolve:
279 household,284 rural,13health,21personal;zero errors.

Installed frozen source`da6961948b0d3e8a68afb5156ba0c460ff1ffdd2` passes packaging,
i18n,privacy,strict signature and438/7 outbound-IP-denial self-check. All124 AU
hashes,42personalFTS,Victoria3054names/map hashes and exact infant video remain.
Full prior431 app/data rollback copies retained;vendor/original library separate.
Native checks open all7 source panels;selected screenshots inspect RTL,earthquake
action pairs,heatstroke response/consciousness condition,tsunami departure/
conditional height,131450/000 and English note direction. Plaintext,Arabic search
to matching floods reader,Ask/Back and both guide choices pass. No Arabic playback
or pronunciation test is claimed;no all-reader/every-browser/professional approval.

[117-record Arabic review](https://github.com/pilkster/lastbook/releases/tag/australia-arabic-hazards-review-2026-11-27):
ZIP1450185bytes,SHA256`1c24694dc931214c400e5aa798a3807ed45dbc146280716b9bc9e68a45596e30`.
CRC/inventory/extraction,117readerhashes,SQLite/FTS and privacy checks pass. Data
only;matching updated runtime is needed for new guide choices and existing
language/speech/Han/HTTP behavior. Extract into a new folder. Earlier releases
unchanged;official Setup/maintainer acceptance remains pending.


## Arabic diacritic search and independent Chinese search — 27 November 2026

[Independent PR494](https://github.com/Immortal-Protocols/lastbook/pull/494) makes
unmarked Arabic words find marked source words and retains short Han substring
matching. For example, مبكرا and مبكرًا now find the same bushfire reading instead
of a miss versus fragmented broad matches. The query parser preserves Arabic
combining marks inside words; matching ignores only U+064B–U+0652 and U+0670.
Hamza, maddah and different letters remain distinct. There is no stemming,
translation, spelling correction or general Unicode normalization.

Reader snippets highlight the original source word with its marks. Overlapping
matches merge; saved markup is escaped. Scope/ID filters apply before LIMIT,
including an empty scope; video/transcript mapping and existing group relaxation
remain. Mixed Han/Arabic/Latin queries use Han substrings, Arabic whole words and
the existing FTS path for other terms. SQL parameters and escaped literal patterns
retain query safety. No source/index/schema/dependency/network change is made.
The read-only title/body scan can cost more than indexed FTS on larger libraries.

Final stable-source suites pass **805 standalone, 876 contribution/build and948
combined tests**, each5skips/11upstream expected failures. Fourteen Arabic/eight Han
tests are required; all29 Arabic/Han/libq tests pass on development and frozen-build
Python3.11. The setup capacity-fixture correction is shared with PR487/491/493;
production disk reserves remain. A source-AST audit proves unrelated server,
library and assistant logic matches the prior baselines, including map provenance.
The independent PR adds both script paths against current main51658f5; #89 had
already carried the earlier Han-only path.

Actual public117/private438 checks forbid sockets and compare four marked/unmarked
query pairs through reader search, original marked highlights, scoped assistant
retrieval and libq. The private queries took approximately50–70ms on this host;
these are local observations, not a general performance guarantee. All124 AU hashes,
42personalFTS,Victoria3054names/map hashes and exact infant video remain verified.
All438/117 records and597 AU guide references remain; no new content/data release.

Installed frozen code`fc75c0eb18f228b364e296dce8520409cdceaf4b` passes package/i18n/
privacy, strict signature and438/7 outbound-IP-denial self-check. All58 bundled
web/content/setup assets are byte-identical to the prior Arabic runtime. The five
catalog/search/reference/map/personal-marker hashes remain identical after native
checks; a complete prior438app is retained for rollback, without changing data.

Selected native Mac checks compare marked/unmarked مبكرا/مبكرًا, inspect the original
marked highlight, find دوّار from دوار and Arabic readings from تعرف, retain 飲水's
Traditional Chinese result, then open the cyclone source and follow matching Ask/
Back context. No audio or all-query/browser/language/accessibility review is claimed.
Historical idle cause and broader rights/clinical/community/local/remote coverage
remain open. The prior117-record Arabic review assets are unchanged; matching
updated runtime supplies this fix. The older data-only archive cannot update code.
