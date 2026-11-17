# Australian offline reference supplement

This contribution adds a reviewed starting collection for Australian households and
rural properties. It does **not** make Lastbook complete for Australia. Its coverage
and remaining work are recorded below so missing information is visible.

## Included

- 24 dated official text readings: ACMA emergency calls and CB radio; Queensland
  household planning, emergency kit, home and pet preparation, cyclone/storm,
  food safety, drinking-water safety and poisons; NSW bushfire, flood, heatwave,
  evacuation, rural bushfire, rural flood and animal preparation; South Australian
  emergency contacts; Energy Safe Victoria's complete generator-use section; and
  myGov's remote-travel preparation and emergency-help sections; NEMA's complete
  written fire-danger rating and AusAlert articles; the complete 10 November 2026
  AusAlert operational announcement; and NSW's warning-level definitions.
- Seven copyright statements, the original Australian source hub and a directory
  covering all six states, ACT and NT: **33 searchable HTML records** altogether.
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
| Household planning and supplies | Qld plans, kit, home and pets; NSW evacuation | Licensed detailed local guides for other jurisdictions; disability and translated materials |
| Rural preparation | NSW rural bushfire, flood/isolation, animals; myGov remote-travel basics | Detailed remote driving, route-specific water/fuel calculations, pastoral and First Nations community-specific sources |
| Fire, flood, cyclone and heat | Dated NSW/Qld texts; current-source national fire-danger/No Rating explanation and warning-level definitions | More detailed regional manuals outside NSW/Qld; hazard-specific and accessible/translated warnings materials |
| Food and water | Qld food-safety source and drinking-water section | Rainwater-tank/bore testing, extended remote supply and jurisdiction-specific recovery guidance |
| Health | Emergency calls, Qld poisons, references to existing SCHN videos | Permission-cleared current Australian snakebite/marine-stinger/adult CPR/anaphylaxis material and clinical review |
| Power, gas and repairs | Energy Safe Victoria generator-use section, with its complete cautions | Broader electrical and gas safety; equipment-specific instructions and local professional assessment |
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
