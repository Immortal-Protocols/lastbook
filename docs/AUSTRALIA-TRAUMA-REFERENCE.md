# Optional nonprofit adult traumatic-event source

This separate source path uses the unchanged seven-page **Traumatic Events
(Adults): Mental Health First Aid Guidelines**, revised 2019, Version 2.3 (2022),
from Mental Health First Aid International. Its official index was checked on
27 November 2026. The nonprofit reproduction grant and requested citation are on
physical page 7. The exact original is 223,480 bytes, SHA-256
`4001b126c7940bd75581f7ac5217846646536c5a4bcbfa0907aae2506767b560`.

[Publisher index](https://mhfainternational.org/guidelines/) ·
[Official original PDF](https://mhfainternational.org/wp-content/uploads/Traumatic-Events-Adult-Mental-Health-First-Aid-Guidelines-2019-1.pdf)

The source permits reproduction for nonprofit purposes with source acknowledgement.
It is not CC BY or public domain; commercial reuse permission is not inferred.
The repository's MIT licence does not relicense it. The original PDF, including
branding, source conditions, attribution and references, remains unchanged. Branding
is retained only inside the source and does not imply endorsement of Lastbook.

Required credit:

> Mental Health First Aid Australia. Traumatic Events: Mental Health First Aid
> Guidelines (revised 2019). Melbourne: Mental Health First Aid Australia; 2019.

This is an adult traumatic-event source with adolescent considerations, not a
complete Australian Red Cross psychological first-aid manual or a child disaster
manual. It describes general recommendations most suitable for high-income
countries with developed health systems. Its audience, professional-help conditions,
development method, source dates and companion references remain together in all
seven pages. A source acquisition or rendering check is not a new clinical review.
No treatment wording is rewritten or combined with another manual.

The Australian Red Cross guide was separately checked and requires prior written
consent for reproduction/storage/transmission. Its later URL filename does not
change its third-edition 2020 publication statement. It is not bundled or published.
The source/reuse metadata audit is
[TRAUMA-SOURCE-AUDIT-20261127.json](../content/regions/au/TRAUMA-SOURCE-AUDIT-20261127.json).

## Build a new separate library

The tool requires an explicit nonprofit purpose and exactly one acquisition mode.
For an already obtained original named `au-mhfa-adult-traumatic-events.pdf`:

```sh
python3 -B tools/build_au_trauma_reference.py --nonprofit-purpose \
  --pdf-cache "/path/to/original-cache" --output "/new/TraumaReferenceData"
```

Alternatively, explicitly request the pinned official original:

```sh
python3 -B tools/build_au_trauma_reference.py --nonprofit-purpose \
  --download --output "/new/TraumaReferenceData"
```

The output has one unchanged PDF, seven physical-page search units, source metadata,
its credit/restrictions and a full-file checksum manifest. The app's existing PDF
reader opens the original; the local index supplies exact-page search. No new
shipped dependency is required. Acquisition is a build-time action; opening a guide
or reader does not download anything. The original host, redirects, maximum size,
exact bytes/hash, page count and nonempty extraction are checked. Changed sources
stop for review.

## Add it to a full library without replacing the base

Close Lastbook and other SQLite users first. Keep the original library and choose
a **new, separate output**:

```sh
python3 -B tools/build_au_trauma_reference.py --nonprofit-purpose \
  --base "/existing/LastbookData" --pdf-cache "/path/to/original-cache" \
  --output "/new/WithAdultTraumaSource"
python3 -B tools/build_au_trauma_reference.py --verify "/new/WithAdultTraumaSource"
```

Use `--download` instead of `--pdf-cache` only to request the official original.
`--verify` takes only its library path and makes no network request. It reads the
source conditions and complete snapshot; it does not confer a new licence or
publisher authentication. Existing outputs, duplicate source IDs/paths, unsafe
source trees, active journals and overlapping base/output directories are refused.
Concurrent base edits and publication races leave the base and competing output
intact. This is an initial addition, not an updater; recreate from the retained
base to change the selection.

All base material and restrictions remain. A private mixed library stays private:
**do not share a composed personal library**, its other PDFs, extracted text/index
or private metadata. The nonprofit source grant does not clear the base. Local
compositions are not official Setup packs; Setup Check/Repair are unavailable.
Use the matching read-only verifier or recreate from the retained closed base.
The full checksum verifier describes the composition snapshot. Later app-written
logs or other changes can produce a mismatch; a snapshot mismatch alone does not
establish that the original PDF changed. Earlier composition receipts describe
their earlier snapshots; use this matching
verifier for the newly composed snapshot.

## Guide and general-pack behavior

The current guide assets add the same choice/prepare/learn source to household
and rural guides. The Australian health guide also links it, and the ordinary
health guide's stress/fear/grief choice can open it. All ten new references open
physical page 1 and retain the source's nonprofit, audience and date conditions.
Each link requires the actual source file; it disappears if the file is missing
while its catalogue remains. All pre-existing guide content is preserved.

The public 125-reading supplement and its archive are unchanged. This original is
not added to that manifest. Every general pack size excludes records marked
`nonprofit-only`, even if a guide cites them, just as it already excludes
`personal-only` originals. The general-pack verifier treats those absences as
intentional while still detecting missing public readings. A nonprofit original
must be distributed separately with its acknowledgement and conditions; it must
not silently enter an unrestricted pack.

Software, source/layout checking and selected native observations are separate
from independent clinical review, training, local service availability and public
permission for the restricted ANZCOR/Red Cross sources.

[Exact software, source/layout, native and preservation checks](AUSTRALIA-TRAUMA-REFERENCE-REVIEW-20261127.json).

## Check readings after normal app use

For the Australian readings, source conditions and stored search pages, use the
[separate offline reading check](AUSTRALIA-READING-CHECK.md). It tolerates unrelated
app-log/history changes while retaining source and index checks. The existing
matching `--verify` command still checks the exact full creation snapshot.
