/* Check for updates, in About (desktop app only). A check runs when the person presses Check for updates, or chooses
   Lastbook > Check for Updates… (the menu calls LBUpdate.fromMenu; no address starts it). It only says whether a newer version
   is on the website, and no system notification is shown. engine/update.py does the check.

   When a newer version is known, About offers Update now only where the app can update itself (a Mac build with a trusted Sparkle
   setup: can_update_now). Pressing it starts the native updater, which asks before installing and relaunches Lastbook; this page
   sends no address or file. Everywhere else, and whenever that fails, the button is Open download page (the system browser).

   Opt-in notices (watch): the sidebar's "Update available" row, shown only while "Notify me about app updates" is on (Setup,
   Settings) and a check found a newer version for this system. This page only nudges the engine (POST /api/update/auto) soon after
   it opens, every hour, and when the system says it is online again; the engine decides whether a check is due (at most one a day,
   and none at all unless the setting is on). Failures say nothing. */
(() => {
  function tr(key, params, fallback) {
    const text = globalThis.LastbookI18n?.t?.(key, params);
    if (text != null) return text;
    if (params && typeof fallback === 'string') {
      return fallback.replace(/\{([A-Za-z_][A-Za-z0-9_]*)\}/g, (_, n) => (params[n] != null ? String(params[n]) : '{' + n + '}'));
    }
    return fallback;
  }
  const E = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const HOUR = 60 * 60 * 1000, FIRST = 5000, POLL = 2000;
  let timer = null, menuAsked = false, row = null, rowTimer = null;

  async function call(action) {
    const get = action === 'state' || action === 'notice';
    const r = await fetch('/api/update/' + action, get ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
    return r.json();
  }

  function view(s) {
    const btn = (t) => `<button class="btn plain" data-upd="check">${t}</button>`;
    const ver = s.current ? tr('update.version', { version: E(s.current) }, 'Version {version}.') : tr('update.noVersion', null, 'This copy has no version number (it was not built as an app).');
    switch (s.state) {
      case 'checking': return `${ver} ${tr('update.checking', null, 'Checking for updates…')}`;
      case 'up_to_date': return `${ver} ${tr('update.upToDate', null, 'Lastbook is up to date.')} ${btn(tr('update.checkAgain', null, 'Check again'))}`;
      case 'available': return `${ver} ${tr('update.available', { version: E(s.version), website: E(s.website) }, 'Version {version} is available. Download it from {website}. Your library, local AI and chats stay.')} ${btn(tr('update.checkAgain', null, 'Check again'))}`;
      case 'not_published': return `${ver} ${tr('update.noInfo', null, 'No update information yet.')} ${btn(tr('common.tryAgain', null, 'Try again'))}`;
      case 'too_old_os': case 'error': return `${ver} ${E(s.message)} ${btn(tr('common.tryAgain', null, 'Try again'))}`;
      default: return `${ver} ${btn(tr('update.checkFor', null, 'Check for updates'))}`;
    }
  }

  function paint(el, s) {
    el.innerHTML = view(s);
    clearTimeout(timer);
    if (s.state === 'checking') timer = setTimeout(() => refresh(el), 400);
    else sync('notice');     // a check of the person's own also updates the sidebar (when notices are on)
  }

  async function refresh(el) {
    if (!el.isConnected) return;
    try { paint(el, await call('state')) } catch { el.textContent = tr('update.failed', null, 'Lastbook could not ask about updates.') }
  }

  async function check(el) {
    try {
      const s = await call('check');
      if (s.error && !s.state) { el.textContent = s.error; return }
      paint(el, s);
    } catch { el.textContent = tr('update.failed', null, 'Lastbook could not ask about updates.') }
  }

  async function copyLink(button, el) {
    try {
      await navigator.clipboard.writeText(button.dataset.url);
      button.textContent = 'Link copied';
    } catch {
      const address = el.querySelector('[data-upd-address]');
      address.hidden = false;
      const range = document.createRange();
      range.selectNodeContents(address);
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
      button.textContent = 'Address selected';
    }
  }

  async function openDownload(button, el) {
    const status = el.querySelector('[data-upd-status]');
    button.disabled = true;
    status.textContent = '';
    try {
      const result = await call('open');
      if (result.opened) {
        status.textContent = 'Download page opened in your browser.';
        return;
      }
      status.textContent = result.error;
    } catch {
      status.textContent = 'Lastbook could not open the download page. Try copying the download link.';
    } finally {
      button.disabled = false;
    }
    const copy = el.querySelector('[data-upd=copy]');
    if (copy) copy.hidden = false;
  }

  async function updateNow(button, el) {
    const status = el.querySelector('[data-upd-status]');
    button.disabled = true;
    status.textContent = '';
    try {
      const result = await call('now');
      if (result.started) {
        status.textContent = 'The updater is opening. Confirm in its window to install; Lastbook restarts when it is done.';
        setTimeout(async () => {      // the updater starts on the app's side: a failure to start comes back in state
          try {
            const s = await call('state');
            if (s.update_now_error) { status.textContent = s.update_now_error; button.hidden = true }
          } catch { }
          button.disabled = false;
        }, 1500);
        return;
      }
      status.textContent = result.error || 'Lastbook could not start the update.';
      if (result.fallback) button.hidden = true;
    } catch {
      status.textContent = 'Lastbook could not start the update. Use the download page instead.';
    }
    button.disabled = false;
  }

  /* ---- the sidebar's notice */
  function showRow(n) {
    if (!row) return;
    const v = n && n.notify && n.available ? String(n.available) : '';
    row.hidden = !v;
    row.setAttribute('aria-label', v ? `Update available: version ${v}` : 'Update available');
  }
  async function sync(action) {
    if (!row) return;
    clearTimeout(rowTimer);
    try {
      const n = await call(action);
      showRow(n);
      if (n && n.notify && n.checking) rowTimer = setTimeout(() => sync('notice'), POLL);   // until the check under way has ended
    } catch { }      // quiet: the row stays as it was
  }
  const nudge = () => sync(navigator.onLine === false ? 'notice' : 'auto');

  window.LBUpdate = {
    card: () => `<div class="card"><b data-i18n="update.appName">${tr('update.appName', null, 'Lastbook app')}</b><small id="updBox">…</small></div>`,
    mount(root) {
      const el = root.querySelector('#updBox'); if (!el) return;
      el.addEventListener('click', e => {
        const button = e.target.closest('[data-upd]');
        if (button?.dataset.upd === 'check') check(el);
        if (button?.dataset.upd === 'copy') copyLink(button, el);
        if (button?.dataset.upd === 'open') openDownload(button, el);
        if (button?.dataset.upd === 'now') updateNow(button, el);
      });
      if (menuAsked) { menuAsked = false; return check(el) }
      refresh(el);
    },
    fromMenu() {     // Lastbook > Check for Updates…: About, then one check
      const el = document.getElementById('updBox');
      if (el && location.hash.startsWith('#/about')) return check(el);
      menuAsked = true;
      location.hash = '#/about';
    },
    watch(el) {      // app.js, in the desktop app's window only
      if (!el || row || document.documentElement.classList.contains('lb-embed')) return;   // the iPad app embeds these pages under lastbook: too: not there
      row = el;
      sync('notice');                       // what an earlier check found shows at once; no network
      setTimeout(nudge, FIRST);
      setInterval(nudge, HOUR);
      addEventListener('online', nudge);
      document.addEventListener('visibilitychange', () => { if (!document.hidden) sync('notice') });   // turned off elsewhere: gone when this window is seen again
    },
  };
})();
