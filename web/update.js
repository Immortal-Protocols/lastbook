/* Check for updates, in About (desktop app only). It runs only when the person presses Check for updates, or chooses
   Lastbook > Check for Updates… (the menu calls LBUpdate.fromMenu; no address starts it). It only says whether a newer version
   is on the website: nothing is downloaded or installed. engine/update.py does the check. */
(() => {
  const E = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  let timer = null, menuAsked = false;

  async function call(action) {
    const r = await fetch('/api/update/' + action, action === 'state' ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
    return r.json();
  }

  function view(s) {
    const btn = (t) => `<button class="btn plain" data-upd="check">${t}</button>`;
    const ver = s.current ? `Versão ${E(s.current)}.` : 'Esta cópia não possui número de versão (não foi compilada como aplicativo).';
    switch (s.state) {
      case 'checking': return `${ver} Verificando atualizações…`;
      case 'up_to_date': return `${ver} O Último Livro está atualizado. ${btn('Verificar novamente')}`;
      case 'available': return `${ver} A versão ${E(s.version)} está disponível. Baixe em ${E(s.website)}. Sua biblioteca, IA local e conversas são mantidas. ${btn('Verificar novamente')}`;
      case 'not_published': return `${ver} Ainda não há informações de atualização. ${btn('Tentar novamente')}`;
      case 'too_old_os': case 'error': return `${ver} ${E(s.message)} ${btn('Tentar novamente')}`;
      default: return `${ver} ${btn('Verificar atualizações')}`;
    }
  }

  function paint(el, s) {
    el.innerHTML = view(s);
    clearTimeout(timer);
    if (s.state === 'checking') timer = setTimeout(() => refresh(el), 400);
  }

  async function refresh(el) {
    if (!el.isConnected) return;
    try { paint(el, await call('state')) } catch { el.textContent = 'O Último Livro não conseguiu consultar atualizações.' }
  }

  async function check(el) {
    try {
      const s = await call('check');
      if (s.error && !s.state) { el.textContent = s.error; return }
      paint(el, s);
    } catch { el.textContent = 'O Último Livro não conseguiu consultar atualizações.' }
  }

  window.LBUpdate = {
    card: () => '<div class="card"><b>Aplicativo Último Livro</b><small id="updBox">…</small></div>',
    mount(root) {
      const el = root.querySelector('#updBox'); if (!el) return;
      el.addEventListener('click', e => { if (e.target.closest('[data-upd]')) check(el) });
      if (menuAsked) { menuAsked = false; return check(el) }
      refresh(el);
    },
    fromMenu() {     // Lastbook > Check for Updates…: About, then one check
      const el = document.getElementById('updBox');
      if (el && location.hash.startsWith('#/about')) return check(el);
      menuAsked = true;
      location.hash = '#/about';
    },
  };
})();
