# Reading-maintenance follow-up

This follow-up adds the unchanged read-only source checker,20 controls and its
instructions after the public supplement and separate personal/nonprofit source
workflows. Dependency base73f12e106b172837e3dbd78b123ce09cf677e71d combines the exact
personal ac64921 and nonprofit0f5021b product revisions on public83662df. The linked
comparison isolates the maintenance layer from those unmerged dependencies.

908 required tests pass on Python3.14 (five skips/eleven upstream expected failures).
116 source/composition/maintenance controls and five distribution checks pass on
app-build3.11.18. The two distribution modules are invoked by their bare names with
PYTHONPATH=packaging to avoid collision with the installed PyPI packaging package.
The initial combined focused invocation passed116 cases but could not import the
two packaging modules; the corrected separate invocation passed all five controls.

Actual current476-record library:162 readings/396searchpages/331relevant files;
no sockets, no target SQLite connection, five core hashes retained. Only its source
location changes. Installed frozen app/source/data and all release assets remain.
See AUSTRALIA-READING-CHECK.md for commands, scope and unchanged exact-snapshot rules.

Water-source growth follow-up: two maintenance-fixture totals now derive from the
committed public manifest instead of assuming125 sources. All20 maintenance controls
pass again on Python3.14; checker implementation and tested behaviours are unchanged.
