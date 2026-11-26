# Linked readings in the HTTP browser

Following a local link inside a saved HTML reading previously changed only the
iframe. The reader title, source details, Ask target and Save state still belonged
to the previous document. For example, an NT planning worksheet could display
Emergency calls while its surrounding source details still named the worksheet.

The HTTP reader now gives each active iframe a fresh random token. The server
rewrites actual local anchor tags that name another supported, existing catalog
record through a small trusted UI document. That document asks the outer reader to
open the catalog route. The outer reader checks the connected iframe, origin,
source record, token and route before navigating, and removes the listener when
leaving. The normal reader then supplies title, publisher, Ask, Save and history.

Saved pages retain the original opaque-origin CSP with scripts disabled. No code
is injected into them. The trusted relay has its own restrictive CSP and no-store
response. Fetch Metadata indicating a user-activated iframe navigation enables
immediate opening; otherwise a real click on the trusted Open reading button is
required. This does not change POST origin checks, LAN access, TLS, downloader
policy, production manifests or the native desktop link policy.

Only UTF-8 HTML within the 16 MiB input and expanded-output limit is rewritten.
Anchor text is preserved. Raw-text elements and comments are ignored. External,
self-anchor, missing, unsupported and ambiguous links retain their existing
behavior. PDF page fragments and encoded Unicode record IDs are supported. No new
dependency or data migration is required. An existing data-only supplement cannot
update an older application's reader code.

`app.tests.test_reading_links` contains nine focused tests, including real HTTP
headers, HEAD, invalid requests, target availability, bounded rewriting, many-link
processing and JavaScript message/button validation. It is included in the
required CONTRIBUTING command. Existing setup recommendation fixtures also mock
disk capacity: three failures reproduced on unchanged main when the host was below
the production reserve. Production storage checks remain unchanged.

Selected actual Chrome checks used a local Australian collection: NT worksheet
to Emergency calls updated the reader title, ACMA source details and Ask target;
Back, Forward and Save state followed the current record. A separate test server
with activation metadata removed exercised the Open reading fallback. A temporary
host-page console probe confirmed saved-page DOM isolation; the probe was removed
before the final tests and build. Actual installed Mac navigation retained its
native path and Back behavior. These checks do not establish every browser,
encoding, document or long-idle behavior.
