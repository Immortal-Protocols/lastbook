# Linked readings in the desktop app

Following a link inside a saved HTML reading could replace the inner page while
the reader title, source details and Ask target still named the previous record.
The bridge now resolves a user-clicked link to a different installed catalogue
record into the ordinary reader route, retaining the current reader as its Back
destination. Mac, Windows and Linux navigation delegates use that route.

Only an active HTML reader, a genuine link action and a different supported local
record qualify. Initial iframe loads, same-document anchors, PDF/encyclopedia
navigation, unknown/external addresses and popups retain their existing policy.
Saved pages remain opaque and script-free; no CSP or network permission changes.

## Desktop observation

The original selected Mac check on 26 November 2026 reproduced the stale outer
source/title/Ask while following an in-page link before this fix. After the fix,
following the CFA risk → preparation → warnings → last-resort → rights chain
updated the outer title, source panel and Ask record at every destination. Back
returned preparation to risk. Later selected Mac checks also followed the NT
worksheet → Emergency calls link using the plain native page URL (without an
HTTP-reader nonce); title/source/Ask followed Emergency calls and Back returned
to the worksheet. These observations used the integrated Australian review app;
they are not a new isolated-app build or Windows/Linux native UI verification.

## Automated check

Run `python3 -B -m unittest app.tests.test_bridge`. Both bridge modes exercise
encoded/Unicode record identifiers, PDF page targets, source/Back context, initial
loads, self anchors, unrelated views, external/unknown paths and popup refusals.
The native patch is extracted without Australian data or guide changes onto
upstream main `51658f5c0d442c19c36184794fce511dc5aaf95a`. The exact commit is
recorded by Git; the abbreviated base is `51658f5`.

The separately reviewed [HTTP reader fix](https://github.com/Immortal-Protocols/lastbook/pull/487)
handles browser iframe navigation. This PR does not depend on that helper.
