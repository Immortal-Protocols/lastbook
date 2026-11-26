'use strict';
/* The browser reader delegates only through a fresh trusted UI document. Saved pages keep their opaque origin and no scripts. */
(() => {
  const type = 'lastbook-reading-link';
  const validRoute = r => typeof r === 'string' && /^#\/(?:read|watch)\/[^/?#]+(?:\?p=[0-9]{1,7}&view=pdf)?$/.test(r);
  const validToken = t => typeof t === 'string' && /^[0-9a-f]{32}$/.test(t);
  window.LastbookReadingLinks = {
    token() { return Array.from(crypto.getRandomValues(new Uint8Array(16)), n => n.toString(16).padStart(2, '0')).join('') },
    listen(frame, source, token, navigate) {
      const receive = e => {
        const data = e.data;
        if (!frame.isConnected || e.source !== frame.contentWindow || e.origin !== location.origin ||
            !data || data.type !== type || data.source !== source || data.token !== token || !validToken(token) || !validRoute(data.route)) return;
        window.removeEventListener('message', receive);
        navigate(data.route);
      };
      window.addEventListener('message', receive);
      return () => window.removeEventListener('message', receive);
    },
  };
  const button = document.getElementById('openReading');
  if (!button) return;
  const data = document.body.dataset;
  if (!validToken(data.token) || !validRoute(data.route) || !data.source) return;
  const open = () => {
    if (window.parent === window) { location.replace('/' + data.route); return }
    window.parent.postMessage({ type, source: data.source, token: data.token, route: data.route }, location.origin);
  };
  button.addEventListener('click', e => { if (e.isTrusted) open() });
  // Sec-Fetch-User proves activation where supported. Other browsers show the
  // trusted button above; they do not receive broader saved-page permissions.
  if (data.automatic === 'yes') open();
})();
