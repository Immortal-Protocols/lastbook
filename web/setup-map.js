/* Which detailed maps are already covered by the installed map set. */
(function (root) {
  'use strict';
  function included(current, candidate) {
    return !!candidate && (candidate.id === current || (current === 'us' && (candidate.kind || 'state') === 'state'));
  }
  function packMap(id, pack) {
    if (pack && pack.map === 'base') return null;
    return (pack && pack.map) || ({ medium: 'CA', all: 'us' })[id] || null;
  }
  function followManifest(read, apply, schedule = setTimeout) {
    let stopped = false;
    async function refresh() {
      if (stopped) return;
      let state;
      try { state = await read() } catch { if (!stopped) schedule(refresh, 1000); return }
      if (stopped) return;
      apply(state);
      if (state && state.manifest && state.manifest.fetching) schedule(refresh, 500);
    }
    schedule(refresh, 500);
    return () => { stopped = true };
  }
  root.SetupMap = Object.freeze({ included, packMap, followManifest });
})(globalThis);
