# Australian offline reference supplement

This contribution adds a reviewed starting collection for Australian households and
rural properties. It does **not** make Lastbook complete for Australia. Its coverage
and remaining work are recorded below so missing information is visible.

## Included

- 43 dated official text readings: ACMA emergency calls, CB radio and locating devices; Queensland
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
  planning selections and complete mobility and low/no-vision written articles.
- Ten copyright statements, an original accessible-calling navigation note,
  the original Australian source hub and a directory
  covering all six states, ACT and NT: **56 searchable HTML records** altogether.
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
- CFA's July 2022 Version 6 survival PDF explicitly licenses text under CC BY 4.0,
  excluding imagery/branding. Current-catalogue edition confirmation and reliable
  transcription/layout QA remain incomplete; its text layer drops some ligatures.
  No CFA PDF or transcription is bundled here. VICSES commercial reuse needs
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
| Fire, flood, cyclone and heat | Dated NSW/Qld texts; six SA SES before/during/after storm/flood readings; current-source national fire-danger/No Rating explanation and warning-level definitions | More detailed regional manuals for ACT/NT/Tas/WA/Vic; hazard-specific and accessible/translated warnings materials |
| Food and water | Qld food-safety source and drinking-water section | Rainwater-tank/bore testing, extended remote supply and jurisdiction-specific recovery guidance |
| Health | Emergency calls, Qld poisons, references to existing SCHN videos | Permission-cleared current Australian snakebite/marine-stinger/adult CPR/anaphylaxis material and clinical review |
| Power, gas and repairs | ESV generator use, gas emergencies, flood electricity/solar/battery/gas, outdoor LPG cylinders and all nine LCC27 FAQ pairs | More jurisdiction-specific material; equipment-specific instructions, repairs and local professional assessment |
| Geographic directory | Six states, ACT and NT | External territories, including Jervis Bay's distinct arrangements |
| Maps | Separate #38 now has eight capital and eight broader extract definitions; #90 provides point-place sidecars alongside #63 | Official release/scanner/switch/repair integration and external-territory verification; this supplement contains no map files |

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
