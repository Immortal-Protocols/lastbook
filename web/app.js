'use strict';
/* Lastbook front end. Plain JS, no external resources. Talks only to the local server. */
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fileUrl = p => '/' + String(p || '').split('/').map(encodeURIComponent).join('/');
const main = $('#main'), pageTop = $('#pageTop');
const i18n = globalThis.LastbookI18n;
function tr(key, params, fallback) {
  const text = globalThis.LastbookI18n?.t?.(key, params);
  if (text != null) return text;
  if (params && typeof fallback === 'string') {
    return fallback.replace(/\{([A-Za-z_][A-Za-z0-9_]*)\}/g, (_, n) => (params[n] != null ? String(params[n]) : '{' + n + '}'));
  }
  return fallback;
}
globalThis.lastbookTr = tr;
function trLang(key, params, fallback) {
  const result = globalThis.LastbookI18n?.resolve?.(key, params);
  const text = result?.text ?? tr(key, params, fallback);
  const locale = result?.locale || 'en';
  const direction = globalThis.LastbookI18n?.direction?.(locale);
  return `<span lang="${esc(locale)}"${direction === 'rtl' ? ' dir="rtl"' : ''}>${esc(text)}</span>`;
}
function trLocale(key, params) { return globalThis.LastbookI18n?.resolve?.(key, params)?.locale || 'en' }
const i18nParams = params => params ? ` data-i18n-params='${esc(JSON.stringify(params))}'` : '';
const IN_WINDOW = location.protocol === 'lastbook:' || location.hostname === 'lastbook.invalid';   // the desktop app, not a browser over the server
if (IN_WINDOW) $('#sideSettings').hidden = false;   // Library and local AI (web/setup.html) is in the desktop app only
const CAN_CONTRIBUTE = IN_WINDOW && !document.documentElement.classList.contains('lb-embed');
if (CAN_CONTRIBUTE) $('#sideContribute').hidden = false;
if (IN_WINDOW && window.LBUpdate) LBUpdate.watch($('#sideUpdate'));   // the opt-in "Update available" row (web/update.js); hidden unless notices are on and found one
$('.skip').addEventListener('click', e => { e.preventDefault(); main.focus() });

/* ---------------------------------------------------------------- icons -- */
const I = {
  water: '<path d="M12 3s6 6.5 6 11a6 6 0 0 1-12 0c0-4.5 6-11 6-11z"/><path d="M9 14a3 3 0 0 0 3 3"/>',
  hurt: '<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M9 7V5h6v2M12 10v7M8.5 13.5h7"/>',
  food: '<path d="M4 11h16a8 8 0 0 1-16 0zM8 7c0-1 1-1 1-2M12 7c0-1 1-1 1-2M16 7c0-1 1-1 1-2"/>',
  power: '<path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-4 10.5c.7.7 1 1.5 1 2.5h6c0-1 .3-1.8 1-2.5A6 6 0 0 0 12 3z"/>',
  shelter: '<path d="M14 14.8V5a2 2 0 0 0-4 0v9.8a4 4 0 1 0 4 0zM12 9v8"/>',
  sanitation: '<path d="M7 3h10v6H7zM5 9h14l-2 6H7zM9 15l-1 6h8l-1-6"/>',
  disaster: '<path d="M12 3 2 20h20zM12 10v4M12 17h.01"/>',
  comms: '<path d="M5 12a7 7 0 0 1 14 0M8 12a4 4 0 0 1 8 0"/><circle cx="12" cy="12" r="1.5"/><path d="M12 13.5V21M9 21h6"/>',
  grow: '<path d="M12 21v-9M12 12c0-4 3-7 8-7 0 5-3 7-8 7zM12 14c0-3-2-5-7-5 0 4 2 5 7 5z"/>',
  preserve: '<path d="M8 3h8v3H8zM7 6h10l1 3v10a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V9z"/><path d="M6 12h12"/>',
  health: '<path d="M12 21s-8-4.5-8-11a4.5 4.5 0 0 1 8-2.8A4.5 4.5 0 0 1 20 10c0 6.5-8 11-8 11z"/><path d="M8 12h2l1-2 2 4 1-2h2"/>',
  energy: '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>',
  land: '<path d="M3 20 9 9l4 6 3-4 5 9z"/><circle cx="17" cy="6" r="2"/>',
  repair: '<path d="M14.7 6.3a4 4 0 0 0 5 5L21 13l-8 8-3-3 6.3-6.3a4 4 0 0 0-5-5L9 9 6 6l2-2"/><path d="M4 20l5-5"/>',
  map: '<path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2zM9 4v14M15 6v14"/>',
  pin: '<path d="M12 21s-7-6.2-7-11.5a7 7 0 0 1 14 0C19 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.5"/>',
  book: '<path d="M4 4h6a3 3 0 0 1 3 3v13a2 2 0 0 0-2-2H4zM20 4h-6a3 3 0 0 0-1 .2"/><path d="M20 4v14h-7"/>',
  video: '<rect x="3" y="5" width="18" height="14" rx="3"/><path d="m10 9 5 3-5 3z"/>',
  wiki: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
  page: '<path d="M6 2h9l5 5v15H6z"/><path d="M14 2v6h6M9 13h7M9 17h7"/>',
  up: '<path d="M12 19V5M6 11l6-6 6 6"/>', back: '<path d="M15 18 9 12l6-6"/>', right: '<path d="m9 18 6-6-6-6"/>', down: '<path d="m6 9 6 6 6-6"/>',
  warn: '<path d="M12 3 2 20h20zM12 10v4M12 17h.01"/>', save: '<path d="M6 3h12v18l-6-4-6 4z"/>',
  ext: '<path d="M14 4h6v6M20 4l-9 9M18 14v6H4V6h6"/>', prep: '<path d="M9 11l3 3 8-8"/><path d="M20 12v7a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h9"/>',
  shelf: '<path d="M4 4v16M9 4v16M14 5l4 15M3 20h18"/>', search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>',
  play: '<path d="M7 4v16l13-8z"/>', speak: '<path d="M4 9v6h4l5 4V5L8 9z"/><path d="M16 9a3 3 0 0 1 0 6M18.5 6.5a7 7 0 0 1 0 11"/>', stopsq: '<rect x="6.5" y="6.5" width="11" height="11" rx="2"/>', clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  insp: '<rect x="3" y="5" width="18" height="14" rx="3"/><path d="M15 5v14"/>',
  ask: '<path d="M4 5h16v11H9l-5 4z"/><path d="M9 9.5h6M9 12.5h4"/>', spark: '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6"/>',
};
const ico = (n, cls = '') => `<svg viewBox="0 0 24 24" aria-hidden="true" class="${cls}">${I[n] || I.book}</svg>`;
const KIND_ICO = { pdf: 'page', html: 'page', video: 'video', transcript: 'video', pptx: 'page', zim: 'wiki' };
// One colour per guide, used for its tile, header and cards.
const TC = { hurt: '#c62828', water: '#1565c0', power: '#c77700', food: '#d4570f', shelter: '#7b3fa0', sanitation: '#7a5232', disaster: '#b23c17', comms: '#00796b',
  grow: '#2e7d32', preserve: '#a0661a', health: '#c2185b', repair: '#455a64', energy: '#e09400', land: '#5d7a2e' };
// Short names for tiles; the full title shows on the guide page.
const SHORT_EN = { hurt: 'Injury & illness', water: 'Drinking water', power: 'Power is out', food: 'Food & cooking', shelter: 'Too hot or cold', sanitation: 'Toilets & hygiene',
  disaster: 'Quake, fire, flood', comms: 'Contact & find way', grow: 'Grow food', preserve: 'Preserve food', health: 'Health care', repair: 'Repair & build', energy: 'Power systems', land: 'Land & resources' };
const shortName = id => tr('topic.' + id, null, SHORT_EN[id] || '');
const topicShort = t => tr('topic.short.' + t.id, null, t.short || '');
const topicResult = (id, field, fallback) => {
  const key = field === 'short' ? 'topic.short.' + id : 'topic.' + id;
  return globalThis.LastbookI18n?.resolve?.(key) || {text: tr(key, null, fallback), locale: 'en'};
};
const topicResultHtml = result => {
  const direction = globalThis.LastbookI18n?.direction?.(result.locale);
  return `<span lang="${esc(result.locale)}"${direction === 'rtl' ? ' dir="rtl"' : ''}>${esc(result.text ?? '')}</span>`;
};
const topicLabelHtml = (id, field, fallback) => topicResultHtml(topicResult(id, field, fallback));
// chat.js and other scripts still read SHORT[id] for the short tile name.
const SHORT = Object.fromEntries(Object.keys(SHORT_EN).map(id => [id, SHORT_EN[id]]));
function refreshShort() { for (const id of Object.keys(SHORT_EN)) SHORT[id] = shortName(id); }
refreshShort();
document.addEventListener('lastbook:languagechange', refreshShort);
const tcStyle = id => `style="--tc:${TC[id] || '#1a6b55'}"`;

/* ------------------------------------------------------------ storage -- */
const store = {
  get(k, d) { try { return JSON.parse(localStorage.getItem('sg.' + k)) ?? d } catch { return d } },
  set(k, v) { try { localStorage.setItem('sg.' + k, JSON.stringify(v)) } catch { } },
};
// A row as the lists show it: its title and the subtitle under it. Two rows that read the same are one row, whatever their keys.
const rowSub = x => x.sub && x.sub !== x.title ? x.sub : x.key[0] === 'w' ? tr('saved.encyclopedia', null, 'Encyclopedia') : '';
const rowId = x => x.title + '|' + rowSub(x);
function remember(item) {  // {key,title,href,sub}
  const r = store.get('recent', []).filter(x => x.key !== item.key && rowId(x) !== rowId(item));
  r.unshift({ ...item, at: Date.now() });
  store.set('recent', r.slice(0, 40));
}
const isSaved = key => store.get('saved', []).some(x => x.key === key);
function savedCount() { const el = $('#savedN'); if (el) el.textContent = store.get('saved', []).length || '' }
function toggleSave(item, btn) {
  let s = store.get('saved', []);
  if (s.some(x => x.key === item.key)) { s = s.filter(x => x.key !== item.key); toast(tr('saved.toastRemoved', null, 'Removed from Saved')) }
  else { s.unshift({ ...item, at: Date.now() }); toast(tr('saved.toastAdded', null, 'Saved on this device')) }
  store.set('saved', s);
  savedCount();
  if (btn) { btn.setAttribute('aria-pressed', isSaved(item.key)); const sp = $('span', btn); if (sp) { sp.dataset.i18n = isSaved(item.key) ? 'saved.actionOn' : 'saved.action'; sp.textContent = isSaved(item.key) ? tr('saved.actionOn', null, 'Saved') : tr('saved.action', null, 'Save') } }
}
const saveButton = item => `<button class="btn plain" title="${esc(tr('saved.action', null, 'Save'))}" data-i18n-title="${isSaved(item.key) ? 'saved.actionOn' : 'saved.action'}" data-save='${esc(JSON.stringify(item))}' aria-pressed="${isSaved(item.key)}">${ico('save')}<span data-i18n="${isSaved(item.key) ? 'saved.actionOn' : 'saved.action'}">${isSaved(item.key) ? tr('saved.actionOn', null, 'Saved') : tr('saved.action', null, 'Save')}</span></button>`;
const watchedButton = (id, d) => {
  const w = isWatched(id, null, d);
  const translate = globalThis.lastbookTr || ((_key, _params, fallback) => fallback);
  const titleKey = w ? 'videos.markUnwatched' : 'videos.markWatched';
  const labelKey = w ? 'videos.watched' : 'videos.markWatched';
  return `<button class="btn plain" id="markWatched" title="${esc(translate(titleKey, null, w ? 'Mark as unwatched' : 'Mark as watched'))}" data-i18n-title="${titleKey}" aria-pressed="${w}">${ico('check')}<span data-i18n="${labelKey}">${translate(labelKey, null, w ? 'Watched' : 'Mark watched')}</span></button>`;
};
document.addEventListener('click', e => { const b = e.target.closest('[data-save]'); if (b) toggleSave(JSON.parse(b.dataset.save), b) });
let toastT;
function toast(msg) {
  let t = $('.toast'); if (!t) { t = document.createElement('div'); t.className = 'toast'; t.setAttribute('role', 'status'); document.body.append(t) }
  t.textContent = msg; t.hidden = false; clearTimeout(toastT); toastT = setTimeout(() => t.hidden = true, 2200);
}
// Video watch progress: {id: {t, d, title, thumb, at}}
const vprog = () => store.get('vprog', {});
// Explicit watched states survive beyond vprog's 60-video limit: {id: boolean}
const vwatched = () => store.get('vwatched', {});
function setWatched(id, state) {
  const w = vwatched();
  if (state == null) delete w[id]; else w[id] = !!state;
  store.set('vwatched', w);
}
function isWatched(id, p, v) {
  const w = vwatched();
  if (w[id] !== undefined) return w[id];
  p = p || vprog()[id];
  const dur = (v && v.duration) || (p && p.d);
  return Boolean(p && p.t && dur && p.t >= dur * 0.9);
}
// This device's history is kept for every library opened on it (each download is its own library): show only what the open one holds
const HELD = {};
const held = ids => Promise.all(ids.map(id => HELD[id] ?? (HELD[id] = fetch('/api/doc/' + encodeURIComponent(id)).then(r => r.status !== 404 && r.status !== 400).catch(() => true)))).then(ok => ids.filter((_, i) => ok[i]));
async function resumable(n = 60) {
  const list = Object.entries(vprog()).filter(([id, v]) => !isWatched(id, v) && v.t > 10 && (!v.d || v.t < v.d - 15)).sort((a, b) => b[1].at - a[1].at).slice(0, n);
  const ok = new Set(await held(list.map(([id]) => id)));
  return list.filter(([id]) => ok.has(id));
}
async function recents() {   // documents and videos from another library leave the list; guides and articles stay
  const r = store.get('recent', []), ids = r.filter(x => /^[dv]:/.test(x.key)).map(x => x.key.slice(2));
  const ok = new Set(await held(ids)), seen = new Set();
  return r.filter(x => (!/^[dv]:/.test(x.key) || ok.has(x.key.slice(2))) && !seen.has(rowId(x)) && seen.add(rowId(x)));
}
function setVprog(id, data) { const p = vprog(); p[id] = { ...(p[id] || {}), ...data, at: Date.now() }; const keys = Object.keys(p).sort((a, b) => p[b].at - p[a].at).slice(0, 60); store.set('vprog', Object.fromEntries(keys.map(k => [k, p[k]]))) }

/* --------------------------------------------------------------- data -- */
async function api(u, opts) {
  const r = await fetch(u, opts);
  let d; try { d = await r.json() } catch { throw new Error(tr('app.pageUnreadable', null, 'The library sent an unreadable reply.')) }
  if (!r.ok || (d && d.error && !Array.isArray(d))) throw new Error(d && d.error || tr('app.serverError', { status: r.status }, 'Server error {status}'));
  return d;
}
let LIB = null;
const libInfo = () => LIB || (LIB = api('/api/library').catch(() => { LIB = null; return {} }));   // what this library holds; a failed ask is asked again. An older server leaves out zims, pins and sources: then everything stays offered.
let TOPICS = null;
async function topics() {
  if (TOPICS) return TOPICS;
  try { TOPICS = await api('/api/topics'); store.set('topicsCache', TOPICS) }
  catch (e) { TOPICS = store.get('topicsCache', null); if (!TOPICS) throw e }
  return TOPICS;
}
const topicById = id => (TOPICS || []).find(t => t.id === id);
const NOW_ORDER = ['hurt', 'water', 'power', 'food', 'shelter', 'sanitation', 'disaster', 'comms'];
const LEARN_ORDER = ['grow', 'preserve', 'health', 'repair', 'energy', 'land'];
const nowTopics = () => NOW_ORDER.map(topicById).filter(Boolean).concat((TOPICS || []).filter(t => t.mode === 'now' && !NOW_ORDER.includes(t.id)));
const learnTopics = () => LEARN_ORDER.map(topicById).filter(Boolean).concat((TOPICS || []).filter(t => t.mode === 'learn' && !LEARN_ORDER.includes(t.id)));

/* ------------------------------------------------------------ helpers -- */
const fmtDur = s => { if (!s) return ''; s = Math.round(s); const h = s / 3600 | 0, m = (s % 3600) / 60 | 0; return h ? tr('time.hoursMinutes', { hours: h, minutes: m }, '{hours} h {minutes} min') : m ? tr('time.minutes', { minutes: m }, '{minutes} min') : tr('time.seconds', { seconds: s }, '{seconds} s') };
const clock = s => { s = Math.max(0, Math.round(s || 0)); const h = s / 3600 | 0, m = (s % 3600) / 60 | 0, x = s % 60; return (h ? h + ':' + String(m).padStart(2, '0') : m) + ':' + String(x).padStart(2, '0') };
const here = () => location.hash || '#/videos';
const fromQ = () => 'from=' + encodeURIComponent(here());
const pageImg = (id, p, w) => `/api/page/${encodeURIComponent(id)}/${p || 1}.png?w=${w}`;
const hostOf = u => { try { return new URL(u).host } catch { return u } };   // a web address shown as its site only
const askLink = (about, key, fallback) => { const label = tr(key || 'saved.askAboutThis', null, fallback || tr('saved.askAboutThis', null, 'Ask about this')); return `<a class="btn plain" title="${esc(label)}" href="#/ask?about=${encodeURIComponent(about)}&${fromQ()}">${ico('ask')}<span data-i18n="${key || 'saved.askAboutThis'}">${esc(label)}</span></a>`; };

function hrefFor(item, src) {
  src = src || item.src || item;
  if (item.zim) return '#/wiki/' + item.zim.replace(/^\/?zim\//, '') + '?' + fromQ();
  if (!src || !src.id) return '#/';
  if (src.kind === 'video') return `#/watch/${encodeURIComponent(src.id)}?${item.t ? 't=' + item.t + '&' : ''}${fromQ()}`;
  return `#/read/${encodeURIComponent(src.id)}?${item.page ? 'p=' + item.page + '&' : ''}${fromQ()}`;
}
function srcText(s, page) {
  if (!s) return tr('saved.sourceMissing', null, 'Source not found in this library copy');
  const bits = [`<strong>${esc(s.publisher || s.collection || tr('saved.unknownPublisher', null, 'Unknown publisher'))}</strong>`];
  if (s.year) bits.push(esc(s.year));
  if (page) bits.push(s.pages ? tr('saved.pageOf', { page, total: s.pages }, 'page {page} of {total}') : tr('saved.pagePrefix', { page }, 'page {page}'));
  else if (s.kind === 'pdf' && s.pages) bits.push(tr('saved.pages', { count: s.pages }, '{count} pages'));
  if (s.duration) bits.push(fmtDur(s.duration) + (s.transcript ? ' ' + tr('saved.transcriptMark', null, '· transcript') : ''));
  return bits.join(' · ');
}
// A reading card shows a picture of what you'll open: the actual page, the video frame, or an encyclopedia mark.
function rcard(item) {
  const s = item.src;
  let pv;
  if (item.zim) pv = `<span class="pv w">${ico('wiki')}</span>`;
  else if (s && s.kind === 'video') pv = `<span class="pv v">${s.thumb ? `<img loading="lazy" alt="" src="${fileUrl(s.thumb)}">` : ''}<span class="play"><span>${ico('play')}</span></span>${s.duration ? `<span class="pg">${clock(s.duration)}</span>` : ''}</span>`;
  else if (s && s.kind === 'pdf') pv = `<span class="pv"><img loading="lazy" alt="" src="${pageImg(s.id, item.page, 360)}" onerror="this.remove()"><span class="pg">${item.page ? tr('saved.pageAbbr', { page: item.page }, 'p. {page}') : tr('saved.pdf', null, 'PDF')}</span></span>`;
  else pv = `<span class="pv w">${ico('page')}</span>`;
  const label = item.label || item.title || (s && s.title);
  const src = item.zim ? esc(tr('saved.encyclopediaItem', { title: item.title || '' }, 'Encyclopedia · {title} · community-written')) : `${s ? esc(tr('saved.fromTitle', { title: s.title }, 'From “{title}”')) + ' · ' : ''}${srcText(s, item.page)}<br>${esc(s ? s.trust : '')}`;
  return `<a class="rcard" href="${hrefFor(item)}">${pv}<span><b>${esc(label)}</b>${item.note ? `<p>${esc(item.note)}</p>` : ''}<span class="src">${src}</span></span></a>`;
}
function rowItem(item) {
  const s = item.src || null;
  let k = ico(item.zim ? 'wiki' : s ? KIND_ICO[s.kind] : 'page');
  if (s && s.kind === 'video' && s.thumb) k = `<img loading="lazy" alt="" src="${fileUrl(s.thumb)}">`;
  else if (s && s.kind === 'pdf' && (item.page || item.preview)) k = `<img loading="lazy" alt="" src="${pageImg(s.id, item.page, 200)}" onerror="this.remove()">`;
  const sub = item.zim ? tr('saved.encyclopediaArticle', null, 'Encyclopedia article · community-written') : srcText(s, item.page);
  return `<li><a class="row" href="${hrefFor(item)}"><span class="k">${k}</span><span><b>${esc(item.label || item.title || (s && s.title))}</b><small>${sub}</small></span></a></li>`;
}
function vcard(v, opts = {}) {
  const p = vprog()[v.id];
  const pct = p && p.t && (v.duration || p.d) ? Math.min(100, 100 * p.t / (v.duration || p.d)) : 0;
  const watched = isWatched(v.id, p, v);
  const translate = globalThis.lastbookTr || ((_key, _params, fallback) => fallback);
  return `<a class="vcard" href="#/watch/${encodeURIComponent(v.id)}?${fromQ()}" ${opts.style || ''}>
    <span class="vthumb">${v.thumb ? `<img loading="lazy" alt="" src="${fileUrl(v.thumb)}" onerror="this.remove()">` : `<span class="ph">${ico('video')}</span>`}
      ${watched ? `<span class="vcheck" title="${esc(translate('videos.watched', null, 'Watched'))}" aria-label="${esc(translate('videos.watched', null, 'Watched'))}" data-i18n-title="videos.watched">${ico('check')}</span>` : ''}${v.transcript ? `<span class="cc" title="${esc(translate('video.hasTranscript', null, 'Has a transcript'))}" data-i18n-title="video.hasTranscript">CC</span>` : ''}${v.duration ? `<span class="dur">${clock(v.duration)}</span>` : ''}${pct > 2 ? `<span class="prog" style="width:${pct}%"></span>` : ''}<span class="play">${ico('play')}</span></span>
    <b>${esc(v.title)}</b><span class="vm">${esc(opts.sub || v.publisher || '')}</span></a>`;
}
function rail(html, cls = '') {
  return `<div class="rail-wrap"><button class="rail-btn l" aria-label="${tr('nav.scrollLeft', null, "Scroll left")}" data-i18n-aria-label="nav.scrollLeft" data-i18n-lang hidden>${ico('back')}</button><div class="rail ${cls}">${html}</div><button class="rail-btn r" aria-label="${tr('nav.scrollRight', null, "Scroll right")}" data-i18n-aria-label="nav.scrollRight" data-i18n-lang>${ico('right')}</button></div>`;
}
// Translate the marked interface text inside markup that was just rendered into `root`
// (a page, or one section filled in later). Static page chrome is translated by the language policy itself.
function translateRendered(root = main) { i18n?.apply(root) }
function wireRails(root = main) {
  $$('.rail-wrap', root).forEach(w => {
    const r = $('.rail', w), l = $('.rail-btn.l', w), rb = $('.rail-btn.r', w);
    const upd = () => { l.hidden = r.scrollLeft < 10; rb.hidden = r.scrollLeft + r.clientWidth > r.scrollWidth - 10 };
    l.onclick = () => r.scrollBy({ left: -r.clientWidth * .85, behavior: 'smooth' });
    rb.onclick = () => r.scrollBy({ left: r.clientWidth * .85, behavior: 'smooth' });
    r.addEventListener('scroll', upd, { passive: true }); upd();
  });
}
const secHead = (title, sub, link) => `<div class="sec-head"><div><h2>${title}</h2>${sub ? `<span class="sub">${sub}</span>` : ''}</div>${link || ''}</div>`;
function crumbs(list) {
  return `<nav class="crumbs" aria-labelledby="crumbLabel"><span class="sr" id="crumbLabel" data-i18n="nav.currentPath">You are here</span>${list.map((c, i) => { const label = c[0] && typeof c[0] === 'object' ? topicResultHtml(c[0]) : esc(c[0]); return i < list.length - 1 ? `<a href="${c[1]}">${label}</a><span aria-hidden="true">›</span>` : `<span aria-current="page">${label}</span>` }).join('')}</nav>`;
}
// A label is [message key, English text]. A plain string is still accepted: it keeps its text, and the few
// common ones keep their translation.
const KNOWN_LABELS = { Back: 'nav.back', Videos: 'nav.videos', Library: 'nav.library', Search: 'search.label', Go: 'search.go', Filter: 'search.filter' };
const labelPair = (label, fallback) => Array.isArray(label) ? label : typeof label === 'string' ? [KNOWN_LABELS[label] || null, label] : fallback;
function backButton(from, fallback) {
  let [key, label] = labelPair(fallback, ['nav.back', tr('nav.back', null, 'Back')]);
  const href = from?.startsWith('#') ? from : '#/';
  const m = /^#\/t\/([\w-]+)/.exec(href);
  if (m && topicById(m[1])) [key, label] = [null, topicResult(m[1], 'title', topicById(m[1]).title)];
  else if (href.startsWith('#/search')) [key, label] = ['search.results', tr('search.results', null, 'Search results')];
  else if (href.startsWith('#/ask')) [key, label] = ['nav.backToChat', tr('nav.backToChat', null, 'Back to chat')];
  else if (href.startsWith('#/saved')) [key, label] = ['nav.saved', 'Saved'];
  else if (href.startsWith('#/map')) [key, label] = ['nav.map', 'Map'];
  else if (href.startsWith('#/videos')) [key, label] = ['nav.videos', 'Videos'];
  else if (href.startsWith('#/guides')) [key, label] = ['nav.guides', tr('nav.guides', null, 'Guides')];
  else if (href.startsWith('#/watch')) [key, label] = ['nav.video', tr('nav.video', null, 'Video')];
  else if (href.startsWith('#/read')) [key, label] = ['nav.backToPage', tr('nav.backToPage', null, 'Back to page')];
  else if (href.startsWith('#/library') || href.startsWith('#/shelf') || href.startsWith('#/collection') || href.startsWith('#/encyclopedias') || href.startsWith('#/prepare')) [key, label] = ['nav.library', 'Library'];
  else if (href === '#/' || href === '#') [key, label] = ['nav.videos', 'Videos'];
  const labelHtml = label && typeof label === 'object' ? topicResultHtml(label) : esc(label);
  return `<a class="back" href="${esc(href)}" data-back>${ico('back')}<span${key ? ` data-i18n="${key}"` : ''}>${labelHtml}</span></a>`;
}
// Links into readers carry where you came from; refresh it at click time (sections may have opened since render).
document.addEventListener('click', e => {
  const a = e.target.closest('a[href^="#/read/"],a[href^="#/watch/"],a[href^="#/wiki/"],a[href^="#/collection"],a[href^="#/ask?about"]');
  if (!a || a.hasAttribute('data-back')) return;
  const h = a.getAttribute('href'), i = h.indexOf('from=');
  if (i > -1) a.setAttribute('href', h.slice(0, i) + 'from=' + encodeURIComponent(here()));
}, true);
// Prefer real history so scroll position and open sections come back exactly (not inside encyclopedia frames).
document.addEventListener('click', e => {
  const a = e.target.closest('a[data-back]');
  if (a && !location.hash.startsWith('#/wiki/') && navAt > 0 && navStack[navAt - 1] === a.getAttribute('href')) { e.preventDefault(); history.back() }
});
function errorBox(e, what) {
  const message = e && (e.error_key || e.key) ? tr(e.error_key || e.key, e.error_params || e.params || null, e.message || e.error || '') : e && (e.message || e.error) || e;
  return `<div class="err" role="alert"><b>${esc(what || tr('app.errorGeneric', null, 'Something went wrong.'))}</b><br>${esc(message)}
  <br><span class="small" data-i18n="app.errorReload">If this keeps happening, close Lastbook and open it again.</span></div>`;
}
// The window title, and on reading pages the toolbar's title and the line under it.
// bar: what the toolbar shows when it is not the page's own title (an article names itself; the toolbar names the encyclopedia).
let uiTitleKey = null, uiTitleFallback = '';
const setTitle = (t, sub, bar) => { uiTitleKey = null; document.title = t ? t + ' · Lastbook' : 'Lastbook'; const b = $('#tbTitle'); b.textContent = b.title = bar ?? t ?? ''; if (sub !== undefined) $('#tbSub').textContent = $('#tbSub').title = sub };
function setUiTitle(key, fallback, sub, bar) {
  uiTitleKey = key; uiTitleFallback = fallback;
  setTitle(tr(key, null, fallback), sub, bar);
  uiTitleKey = key;
}
function applyChromeLanguage() {
  railTitles(); searchPlaceholder();
  if (uiTitleKey) setUiTitle(uiTitleKey, uiTitleFallback);
  const meta = document.querySelector('meta[name="description"]');
  if (meta) meta.setAttribute('content', tr('app.description', null, meta.getAttribute('content')));
}


/* ------------------------------------------------------------- router -- */
// Where this tab is in its history. Each entry carries its own index in history.state, so Back and Forward are known exactly:
// after going back several steps, after a page rewrote its address in place, and when a link leads to the page just left.
const navStack = JSON.parse(sessionStorage.getItem('sg.stack') || '[]');   // navStack[i]: the address at history index i
let navAt = +(sessionStorage.getItem('sg.at') || 0), navEnd = +(sessionStorage.getItem('sg.end') || 0), swapping = false;
const keepNav = () => { try { sessionStorage.setItem('sg.stack', JSON.stringify(navStack.slice(0, navEnd + 1))); sessionStorage.setItem('sg.at', navAt); sessionStorage.setItem('sg.end', navEnd) } catch { } };
const _replace = history.replaceState.bind(history);
// A page that rewrites its own address (the map, search as you type, an opened situation, a new chat) keeps its place.
history.replaceState = (state, title, url) => { _replace({ ...(state || {}), lb: navAt }, title, url); if (url != null) { navStack[navAt] = current = here(); keepNav() } };
const swap = h => { swapping = true; location.replace(h) };   // this entry becomes another page, in place
const _push = history.pushState.bind(history);
const pushHere = url => { navAt++; navEnd = navAt; navStack.length = navAt; _push({ lb: navAt }, '', url); navStack[navAt] = current = here(); keepNav(); barState() };   // a new entry, without loading the page again
const scrolls = JSON.parse(sessionStorage.getItem('sg.scroll') || '{}');
try { history.scrollRestoration = 'manual' } catch { }   // the page restores its own place (restoreScroll), once it is built
let current = null;
window.addEventListener('scroll', () => { if (current && !$('#wframe')) scrolls[current] = scrollY }, { passive: true });   // an article scrolls in its frame, which keeps its own place (wiki)
window.addEventListener('pagehide', () => sessionStorage.setItem('sg.scroll', JSON.stringify(scrolls)));
function parse() {
  const h = here().slice(1) || '/';
  const [path, qs] = h.split('?');
  return { parts: path.split('/').filter(Boolean).map(decodeURIComponent), q: new URLSearchParams(qs || '') };
}
// The sidebar row each page belongs to. Reading pages stay under Library, articles under Encyclopedias; search results select no row.
const NAV_OF = { '': 'videos', guides: 'guides', t: 'guides', ask: 'ask', videos: 'videos', watch: 'videos', map: 'map', library: 'library', learn: 'library', browse: 'library', shelf: 'library', collection: 'library', read: 'library', wiki: 'encyclopedias', search: '', saved: 'saved', 'not-found': 'library', encyclopedias: 'encyclopedias', prepare: 'prepare', about: 'about', contribute: 'contribute' };
let leaving = null;  // cleanup hook for the current view (player, chat stream…)
async function route() {
  searchSeq++;   // invalidate asynchronous results from the view being left
  const cameFromSide = !!(document.activeElement && document.activeElement.closest && document.activeElement.closest('.side,.tabbar'));
  const { parts, q } = parse();
  const h = here();
  const wf = $('#wframe'), wd = wf && wf.contentDocument;
  if (current) { if (!wf) scrolls[current] = scrollY; else if (wd && wd.readyState === 'complete') scrolls[current] = wf.contentWindow.scrollY }   // an article's place is its frame's
  const at = history.state && history.state.lb;
  if (typeof at === 'number') { navAt = at; navEnd = Math.max(navEnd, at) }   // back, forward, or a reload
  else {
    if (swapping) swapping = false;
    else if (current !== null || navStack.length) { navAt++; navEnd = navAt; navStack.length = navAt }   // a new page: what was ahead is gone
    else navAt = navEnd = 0;   // the first page of this tab
    _replace({ ...(history.state || {}), lb: navAt }, '');
  }
  navStack[navAt] = h; keepNav();
  sessionStorage.setItem('sg.scroll', JSON.stringify(scrolls));
  current = h;
  const y = typeof at === 'number' ? scrolls[h] : null;   // read now: while the page is rebuilt it scrolls (shorter, then taller), and those scrolls are recorded too
  const v = parts[0] || 'videos';
  document.body.className = v ? 'v-' + v : 'home';
  const showUpdate = v === 'about' && q.has('updates') && !$('#sideUpdate').hidden;
  const nav = showUpdate ? 'update' : v === 'read' && (q.get('from') || '').startsWith('#/about') ? 'about' : NAV_OF[v] || '';
  $$('[data-nav]').forEach(a => nav && (a.dataset.nav === nav || (a.dataset.also || '').split(' ').includes(nav)) ? a.setAttribute('aria-current', 'page') : a.removeAttribute('aria-current'));
  const rows = $$('.side a.row-s'); rows.forEach(a => a.tabIndex = a.hasAttribute('aria-current') || (!nav && a === rows[0]) ? 0 : -1);   // the sidebar is one Tab stop; arrows move inside it
  savedCount();
  html.classList.remove('side-open', 'h1-gone'); h1seen.disconnect();
  railTitles();
  $('#tbActs').replaceChildren(); $('#tbTitle').textContent = $('#tbSub').textContent = ''; $('#tbTitle').title = $('#tbSub').title = ''; searchLive = null; main.classList.remove('own-title');
  if (leaving) { try { leaving() } catch { } leaving = null }
  window.onresize = null; main.onkeydown = pageTop.onkeydown = null;
  try {
    if (v !== 'map') MapView.stop();
    await topics().catch(() => { });
    if (!v || v === 'guides') await home();
    else if (v === 't') await topicPage(parts[1], parts[2]);
    else if (v === 'ask') await Chat.page(main, parts.slice(1), q);
    else if (v === 'videos') await (parts[1] ? videoRow(parts[1], q) : videosHome());
    else if (v === 'watch') await watch(parts[1], q.get('t'), q.get('from'));
    else if (v === 'read') await reader(parts[1], +q.get('p') || 0, q.get('from'), q.get('view'));
    else if (v === 'wiki') await wiki(parts.slice(1).join('/'), q.get('from'), y);
    else if (v === 'search') await searchPage(q.get('q') || '', q.get('kind') || 'all');
    else if (v === 'library' || v === 'learn' || v === 'browse') await library();
    else if (v === 'prepare') await prepareHub();
    else if (v === 'encyclopedias') await encyclopedias(q.get('q') || '');
    else if (v === 'map') await MapView.page(main, q);
    else if (v === 'saved') await savedPage();
    else if (v === 'not-found') await notFoundPage();
    else if (v === 'shelf') await shelfPage(parts[1], q.get('kind') || 'all', q.get('q') || '');
    else if (v === 'collection') await collectionPage(q.get('name') || '', q.get('from'));
    else if (v === 'contribute' && CAN_CONTRIBUTE) contributePage();
    else if (v === 'about') await about(q.has('updates'));
    else notFound();
  } catch (e) { setTitle(''); document.body.className = 'v-error'; main.innerHTML = emptyState('warn', tr('app.pageOpenFailed', null, 'This page could not be opened'), e.message || e) }   // v-error: not a reading page, so a phone keeps its tab bar
  translateRendered(); wireRails(); dock(); barState();
  $('#topQ').value = '';
  const big = $('main h1'); if (big) h1seen.observe(big);
  if (v === 'ask') { bandState(); return }  // the chat manages its own scroll position
  if (y != null && v !== 'wiki') restoreScroll(h, y); else if (v !== 'wiki') requestAnimationFrame(() => { if (!$('.sit.open', main)) scrollTo(0, 0) });
  if (y == null) startHere(cameFromSide);
  bandState(); alignTitle();
}
// Back, Forward or a reload return to the place the page was left. A page still filling in (pictures, results) may not be tall enough yet,
// so this tries again each frame for a moment (at most 2.5 s), and stops as soon as the person scrolls or the page changes.
function restoreScroll(h, y, w = window) {
  const stop = new AbortController(), end = performance.now() + 2500, o = { passive: true, signal: stop.signal };
  for (const ev of ['wheel', 'touchstart', 'keydown', 'mousedown']) addEventListener(ev, () => stop.abort(), o);
  let sh = 0, still = 0, seen = null;   // done once the place is reached and the page has stopped growing for a moment (sections still arriving would move it)
  const tick = () => {
    if (stop.signal.aborted || (w === window ? current !== h : !(w.frameElement && w.frameElement.isConnected))) return;   // another page, or another article in the frame
    const h2 = w.document.scrollingElement.scrollHeight;
    if (seen !== null && w.scrollY !== seen && h2 === sh) return stop.abort();   // it moved while the page did not grow: the person scrolled (an article's own wheel and key events never arrive in the Mac app)
    if (Math.abs(w.scrollY - y) > 1) w.scrollTo(0, y);
    seen = w.scrollY; still = h2 === sh && Math.abs(seen - y) <= 1 ? still + 1 : 0; sh = h2;
    if (still < 12 && performance.now() < end) requestAnimationFrame(tick); else stop.abort();
  };
  requestAnimationFrame(tick);
}
// On Windows the toolbar's title starts where the page's column does, as in Fluent's reading apps. On the Mac it follows Back and Forward.
function alignTitle() {
  const t = $('.tb-title'); if (!t || MAC) return;
  t.style.marginLeft = '';
  if (!t.offsetWidth) return;
  const d = main.getBoundingClientRect().left + parseFloat(getComputedStyle(main).paddingLeft) - t.getBoundingClientRect().left;
  if (d > 0 && d < 240) t.style.marginLeft = parseFloat(getComputedStyle(t).marginLeft) + d + 'px';
}
addEventListener('resize', alignTitle);
// After a new page: a person moving through the sidebar stays there, as in Finder or Settings, and Tab goes on to the toolbar and the page.
// Otherwise the next Tab starts at the top of the window (skip link, sidebar, toolbar, page), as after a full load. The marker it starts from
// is not a control; it carries the page's name, which a screen reader reads when focus lands on it.
let focusAfterRoute = null;   // a control the page asks to keep focus on when it has settled (Read aloud's Stop, after a page turn)
function startHere(fromSide) {
  const keep = focusAfterRoute; focusAfterRoute = null;
  if (keep && keep.isConnected && !keep.hidden) { keep.focus({ preventScroll: true }); return }
  if (fromSide && !(MAC && !wide.matches) && document.activeElement && document.activeElement.closest('.side,.tabbar')) return;
  const h1 = $('h1', main);
  pageTop.textContent = (h1 && h1.textContent.trim()) || document.title;
  pageTop.focus({ preventScroll: true });
}
window.addEventListener('hashchange', route);
let searchLive = null;   // on the search page, where the pane's field is the page's own (Windows), typing there updates the results
$('#topSearch').addEventListener('submit', e => { e.preventDefault(); if (searchLive) { searchLive($('#topQ').value.trim(), true); $('#topQ').blur(); return } location.hash = '#/search?q=' + encodeURIComponent($('#topQ').value.trim()) });
$('#topQ').addEventListener('input', () => { if (searchLive) searchLive($('#topQ').value.trim(), false, true) });

/* --------------------------------------------------------- the window -- */
const html = document.documentElement, MAC = html.classList.contains('plat-mac');
const wide = matchMedia('(min-width:900px)');
// The toolbar names the page once its large title has scrolled up under the toolbar.
const h1seen = new IntersectionObserver(es => html.classList.toggle('h1-gone', !es[es.length - 1].isIntersecting), { rootMargin: `-${(parseInt(getComputedStyle(html).getPropertyValue('--top-h')) || 52) + (parseInt(getComputedStyle(html).getPropertyValue('--cap-h')) || 0)}px 0px 0px 0px` });
// Windows' folded pane shows icons only. Use the translated row names as tooltips.
function railTitles() { const icons = html.classList.contains('compact') && !html.classList.contains('side-open'); $$('.side a.row-s').forEach(a => icons ? a.title = $('span', a).textContent : a.removeAttribute('title')) }
addEventListener('resize', railTitles);
// The toolbar's field says only 'Search' when it is too narrow for the whole hint, as Windows' and the Mac's own narrow fields do
function searchPlaceholder() {
  const q = $('#topQ');
  if (!q.clientWidth) return;
  const short = q.clientWidth < 175;
  if (i18n) {
    q.dataset.i18nPlaceholder = short ? 'search.label' : 'search.library';
    i18n.apply(q);
  } else q.placeholder = short ? tr('search.label', null, 'Search') : tr('search.library', null, 'Search the library');
}
new ResizeObserver(searchPlaceholder).observe($('#topQ'));
let renderedLocale = globalThis.LastbookI18n?.locale || 'en';
function snapshotForLanguageChange() {
  const fields = $$('#main input,#main textarea,#main select').map((el, index) => ({
    index, id: el.id, tag: el.tagName, type: el.type, value: el.value,
    checked: 'checked' in el ? el.checked : undefined,
    start: typeof el.selectionStart === 'number' ? el.selectionStart : null,
    end: typeof el.selectionEnd === 'number' ? el.selectionEnd : null,
  }));
  const focusables = $$('#main a,#main button,#main input,#main textarea,#main select,[tabindex]');
  const active = document.activeElement;
  const media = $$('#main video,#main audio').map((el, index) => ({
    index, id: el.id, time: el.currentTime, paused: el.paused,
    rate: el.playbackRate, muted: el.muted, volume: el.volume,
  }));
  const scrollables = $$('#main [id]').filter(el => el.scrollTop || el.scrollLeft)
    .map(el => ({ id: el.id, top: el.scrollTop, left: el.scrollLeft }));
  return {
    href: here(), y: scrollY, topSearch: $('#topQ').value, fields, media, scrollables,
    focusId: active && active.id,
    focusIndex: focusables.indexOf(active),
  };
}
function restoreAfterLanguageChange(s) {
  if (here() !== s.href) return;
  $('#topQ').value = s.topSearch;
  const fields = $$('#main input,#main textarea,#main select');
  for (const saved of s.fields) {
    const el = (saved.id && document.getElementById(saved.id)) || fields[saved.index];
    if (!el || el.tagName !== saved.tag || el.type === 'file') continue;
    if (saved.checked !== undefined) el.checked = saved.checked;
    else if (el.value !== saved.value) {
      el.value = saved.value;
      if (el.matches('input[type="search"],input[type="text"],textarea')) el.dispatchEvent(new Event('input', { bubbles: true }));
    }
    if (saved.start !== null && el.setSelectionRange) {
      try { el.setSelectionRange(saved.start, saved.end) } catch { }
    }
  }
  for (const saved of s.scrollables) {
    const el = document.getElementById(saved.id);
    if (el) { el.scrollTop = saved.top; el.scrollLeft = saved.left }
  }
  for (const saved of s.media) {
    const el = (saved.id && document.getElementById(saved.id)) || $$('#main video,#main audio')[saved.index];
    if (!el) continue;
    const restore = () => {
      try { el.currentTime = saved.time } catch { }
      el.playbackRate = saved.rate; el.muted = saved.muted; el.volume = saved.volume;
      if (!saved.paused) el.play().catch(() => { });
    };
    if (el.readyState >= 1) restore(); else el.addEventListener('loadedmetadata', restore, { once: true });
  }
  const focusables = $$('#main a,#main button,#main input,#main textarea,#main select,[tabindex]');
  const focus = (s.focusId && document.getElementById(s.focusId)) || focusables[s.focusIndex];
  if (focus && focus.isConnected) focus.focus({ preventScroll: true });
  requestAnimationFrame(() => { if (here() === s.href) scrollTo(0, s.y) });
}
async function refreshCurrentLanguage() {
  if (!current) return;
  const state = snapshotForLanguageChange();
  if ((parse().parts[0] || 'videos') === 'map') {
    await MapView.refreshLanguage(main);
    translateRendered();
    restoreAfterLanguageChange(state);
  } else {
    await route();
    restoreAfterLanguageChange(state);
  }
}
document.addEventListener('lastbook:languagechange', () => {
  applyChromeLanguage();
  const locale = globalThis.LastbookI18n?.locale || 'en';
  if (locale === renderedLocale) return;
  renderedLocale = locale;
  void refreshCurrentLanguage();
});
// Apply a desktop language hint that i18n-app.js may have activated before this listener was registered.
applyChromeLanguage();
// At 900 and wider a page's .dock controls (view switch, Save, Ask) sit in the toolbar; narrower they stay in the page.
const docks = () => wide.matches || (!MAC && innerWidth >= 640);
function dock() {
  if (docks()) $$('.dock', main).forEach(el => { const mark = document.createElement('i'); mark.className = 'dock-home'; mark.hidden = true; el.before(mark); $('#tbActs').append(el) });
  else $$('#tbActs .dock').forEach(el => { const mark = $('.dock-home', main); if (mark) mark.replaceWith(el); else el.remove() });
}
wide.addEventListener('change', () => { html.classList.remove('side-open'); dock(); railTitles(); bandState() });
matchMedia('(min-width:640px)').addEventListener('change', () => { dock(); bandState() });   // an overlay sidebar left open does not come back open later
const pageBack = () => $('main a[data-back]');
function barState() { $('#tbBack').disabled = navAt < 1 && !pageBack(); $('#tbFwd').disabled = navAt >= navEnd }
function bandState() {
  if (MAC) return;
  const s = $('#topSearch'), searchInBand = html.classList.contains('compact') && getComputedStyle(s).visibility !== 'hidden' && getComputedStyle(s).display !== 'none';
  const was = html.classList.contains('no-bar'), now = !$('#tbActs').children.length && !searchInBand;
  html.classList.toggle('no-bar', now);
  if (was !== now && window.onresize) window.onresize();   // a page that measures itself (the map) measures again
}
addEventListener('resize', () => requestAnimationFrame(bandState));
$('#tbBack').onclick = () => { const a = pageBack(); if (navAt > 0) history.back(); else if (a) location.hash = a.getAttribute('href') };
$('#tbFwd').onclick = () => history.forward();
function toggleSide() {
  if (wide.matches) { html.classList.toggle('side-off'); try { localStorage.setItem('sg.side-off', html.classList.contains('side-off') ? '1' : '0') } catch { } window.LB_LAYOUT() }
  else html.classList.toggle('side-open');
  railTitles(); bandState();
}
$('#sideBtn').onclick = toggleSide;
if (!MAC) {
  $('#sideBtn').before($('#tbBack'));   // drawn first, top left, so reached first
  // the full pane holds its search field above the rows; the folded rail has it in the command bar
  const placeSearch = () => {
    const f = $('#topSearch'), side = $('#side'), inPane = innerWidth >= 640 && !html.classList.contains('compact');
    if (inPane && f.parentElement !== side) $('.side-nav', side).before(f);
    else if (!inPane && f.parentElement === side) $('.top-in').append(f);
  };
  placeSearch(); new MutationObserver(placeSearch).observe(html, { attributes: true, attributeFilter: ['class'] }); addEventListener('resize', placeSearch);
}
document.addEventListener('click', e => { if (html.classList.contains('side-open') && !e.target.closest('.side,#sideBtn')) { html.classList.remove('side-open'); railTitles() } });
function toggleInsp() { html.classList.toggle('insp-off'); const d = $('.about-src', main); if (d && !html.classList.contains('insp-off')) d.open = true; store.set('insp-off', html.classList.contains('insp-off')) }
if (store.get('insp-off', true)) html.classList.add('insp-off');   // off until asked for: the page keeps the width
document.addEventListener('click', e => { if (e.target.closest('[data-insp]')) toggleInsp() });
$('#side').addEventListener('keydown', e => {
  if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
  const rows = $$('.side a.row-s').filter(a => a.offsetParent), i = rows.indexOf(document.activeElement);
  if (i < 0) return;
  e.preventDefault(); rows[(i + (e.key === 'ArrowDown' ? 1 : rows.length - 1)) % rows.length].focus();
});
const SECTIONS = ['#/videos', '#/map', '#/ask'];
const findBox = () => [$('#bigQ'), $('#searchQ'), $('#topQ')].find(x => x && x.offsetParent) || $('#chatIn');
document.addEventListener('keydown', e => {
  const typing = /INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName), cmd = MAC ? e.metaKey && !e.ctrlKey : e.ctrlKey && !e.metaKey;
  const is = c => e.code === 'Key' + c || (!e.code && (e.key || '').toUpperCase() === c);   // some input (assistive and remote tools) sends no key code
  if (e.key === '/' && !typing) { e.preventDefault(); findBox().focus() }
  else if (cmd && !e.altKey && !e.shiftKey && /^[1-3]$/.test(e.key)) { e.preventDefault(); location.hash = SECTIONS[e.key - 1] }
  else if (cmd && !e.altKey && !e.shiftKey && (is('F') || (!MAC && is('E')))) { e.preventDefault(); const f = findBox(); f.focus(); if (f.select) f.select() }
  else if (MAC && e.metaKey && e.ctrlKey && is('S')) { e.preventDefault(); toggleSide() }   // Windows apps have no key for this: the ☰ button
  else if (MAC ? e.metaKey && e.altKey && is('I') : e.ctrlKey && e.shiftKey && is('I')) { e.preventDefault(); if ($('.about-src', main)) toggleInsp() }
  else if (e.key === 'Escape') {
    if (html.classList.contains('side-open')) { html.classList.remove('side-open'); railTitles() }
    else if (document.activeElement === $('#topQ')) { $('#topQ').value = ''; $('#topQ').blur() }
  }
});
function notFound() { setUiTitle('app.notFoundTitle', tr('app.notFoundTitle', null, 'Not found')); main.innerHTML = emptyState('search', tr('app.notFoundLead', null, 'That page isn’t here'), tr('app.notFoundHint', null, 'The link may be from an older version of the guide.')) }
const emptyState = (icon, title, text) => `<div class="empty"><span class="e-ico">${ico(icon)}</span><b>${esc(title)}</b><p>${esc(text)}</p><p class="e-act"><a class="btn plain" href="#/" data-i18n="nav.goToVideos">Go to Videos</a></p></div>`;
function searchBox(id, value, placeholder, buttonLabel) {
  const [key, button] = labelPair(buttonLabel, ['search.label', 'Search']);
  return `<form class="bigsearch" role="search" id="${id}F">${ico('search')}<label class="sr" for="${id}" data-i18n="search.label">Search</label><input id="${id}" type="search" autocomplete="off" value="${esc(value || '')}" placeholder="${esc(placeholder)}" enterkeyhint="search"><button${key ? ` data-i18n="${key}"` : ''}>${esc(button)}</button></form>`;
}

/* --------------------------------------------------------------- home -- */
async function home() {
  setTitle('');
  const tile = t => `<a class="need" href="#/t/${t.id}" ${tcStyle(t.id)}><span class="ico">${ico(t.id)}</span><b>${topicLabelHtml(t.id, 'title', t.title)}</b><small>${topicLabelHtml(t.id, 'short', t.short || '')}</small></a>`;
  const cont = await continueItems();
  const pins = (await libInfo()).pins !== false;
  const exampleChips = [[tr('search.ex.boilWater', null, 'boil water'), 'search.ex.boilWater'], [tr('search.ex.cutBleeding', null, 'cut won’t stop bleeding'), 'search.ex.cutBleeding'], [tr('search.ex.fridgePower', null, 'fridge after power cut'), 'search.ex.fridgePower'], [tr('search.ex.burn', null, 'burn'), 'search.ex.burn'], [tr('search.ex.toilet', null, 'toilet not working'), 'search.ex.toilet'], [tr('search.ex.smellGas', null, 'smell gas'), 'search.ex.smellGas']].map(([q, key]) => `<a class="chip" href="#/search?q=${encodeURIComponent(q)}" data-i18n="${key}">${esc(tr(key, null, q))}</a>`).join('');
  main.innerHTML = `
  <section class="hero">
    <h1 data-i18n="home.title">What do you need?</h1>
    <p class="lead" data-i18n="home.lead">Pick what’s happening, search in your own words, or ask the library a question.</p>
    ${searchBox('bigQ', '', tr(innerWidth < 500 ? 'home.searchShort' : 'home.searchLong', null, innerWidth < 500 ? 'e.g. boil water' : 'e.g. boil water, deep cut, no power'))}
    <div class="chips examples" aria-label="${esc(tr('home.examples', null, 'Example searches'))}" data-i18n-aria-label="home.examples">${exampleChips}</div>
  </section>
  ${secHead(`<span data-i18n="home.needHelpNow">Need help now</span>`)}
  <div class="needs">${nowTopics().map(tile).join('')}</div>
  <div class="banners"><a class="banner chatb" href="#/ask"><span class="ico">${ico('ask')}</span><span><b data-i18n="home.askLibrary">Ask the library</b><small data-i18n="home.askLibraryLead">Get an answer built from the manuals, with the exact pages and video moments it came from</small></span><span class="go">${ico('right')}</span></a>
  <a class="banner map" href="#/map"><span class="ico">${ico('pin')}</span><span>${pins ? '<b data-i18n="home.findHelp">Find help nearby</b><small data-i18n="home.findHelpLead">Hospitals, pharmacies, water taps and fire stations on an offline map</small>' : '<b data-i18n="home.findPlace">Find a place</b><small data-i18n="home.findPlaceLead">Main roads, towns and water on an offline map</small>'}</span><span class="go">${ico('right')}</span></a></div>
  ${cont.length ? secHead(`<span data-i18n="home.pickUp">Pick up where you left off</span>`) + rail(cont.join('')) : ''}
  <div id="homeVideos"></div>
  ${secHead(`<span data-i18n="home.learnSkill">Learn a skill</span>`, `<span data-i18n="home.learnLead">Step-by-step routes for the weeks and months ahead</span>`, `<a href="#/library" data-i18n="home.allSkills">All skills</a>`)}
  ${rail(learnTopics().map(t => `<a class="skill" href="#/t/${t.id}" ${tcStyle(t.id)}><span class="ico">${ico(t.id)}</span><b>${topicLabelHtml(t.id, 'title', t.title)}</b><small>${topicLabelHtml(t.id, 'short', t.short || '')}</small><span class="steps">${esc(tr('home.steps', { count: (t.route || []).length }, '{count} steps'))}</span></a>`).join(''), 'skills')}
  <a class="banner prep" href="#/prepare"><span class="ico">${ico('prep')}</span><span><b data-i18n="home.getReadyBanner">Get ready before it happens</b><small data-i18n="home.getReadyLead">Store water and food, plan for outages, pack kits</small></span><span class="go">${ico('right')}</span></a>`;
  $('#bigQF').addEventListener('submit', e => { e.preventDefault(); location.hash = '#/search?q=' + encodeURIComponent($('#bigQ').value.trim()) });
  const ex = $('.examples', main), exEnd = () => { ex.classList.toggle('at-end', ex.scrollLeft + ex.clientWidth >= ex.scrollWidth - 4); ex.classList.toggle('at-start', ex.scrollLeft < 4) };
  ex.addEventListener('scroll', exEnd, { passive: true }); exEnd(); window.onresize = exEnd;
  try {
    const rows = await api('/api/videos');
    const g = rows.find(r => r.id === 'guides');
    if (g && $('#homeVideos')) { $('#homeVideos').innerHTML = secHead(`<span data-i18n="home.watchHow">Watch how it’s done</span>`, `<span data-i18n="home.videosPicked">Videos picked for the guides</span>`, `<a href="#/videos" data-i18n="home.allVideos">All videos</a>`) + rail(g.items.slice(0, 14).map(v => vcard(v, { style: tcStyle(v.guide) })).join('')); translateRendered($('#homeVideos')); wireRails($('#homeVideos')) }
  } catch { }
}
async function continueItems() {
  const out = [], rec = await recents();
  (await resumable(12)).slice(0, 6)
    .forEach(([id, v]) => out.push(vcard({ id, title: v.title, thumb: v.thumb, duration: v.d }, { sub: tr('home.resumeAt', { time: clock(v.t) }, 'Resume at {time}') })));
  rec.filter(r => !r.key.startsWith('v:')).slice(0, 8).forEach(r => out.push(`<a class="mini" href="${esc(r.href)}"><small>${esc(r.sub || '')}</small><b>${esc(r.title)}</b></a>`));
  return out;
}

/* -------------------------------------------------------------- guide -- */
function topicVideos(t) {
  const all = [...(t.choices || []).flatMap(c => c.read || []), ...(t.route || []).flatMap(s => s.read || []), ...(t.learn || []), ...(t.prepare || [])];
  const seen = new Set();
  return all.filter(i => i.src && i.src.kind === 'video' && !seen.has(i.src.id) && seen.add(i.src.id)).map(i => i.src);
}
async function topicPage(id, open) {
  const t = topicById(id);
  if (!t) return notFound();
  setTitle(t.title);
  remember({ key: 't:' + id, title: t.title, href: '#/t/' + id, sub: t.mode === 'learn' ? tr('guide.learningRoute', null, 'Learning route') : tr('guide.topicKind', null, 'Guide') });
  const learn = t.mode === 'learn';
  const progress = store.get('progress', {});
  const sits = (t.choices || []).map(c => c.goto
    ? `<div class="sit"><a href="#/t/${esc(c.goto)}"><span class="dot"></span><span class="tx"><b>${esc(c.label)}</b>${c.hint ? `<span>${esc(c.hint)}</span>` : ''}</span><span class="chev">${ico('right')}</span></a></div>`
    : `<div class="sit${open === c.id ? ' open' : ''}" id="c-${esc(c.id)}">
      <button aria-expanded="${open === c.id}" aria-controls="cb-${esc(c.id)}" data-choice="${esc(c.id)}"><span class="dot"></span><span class="tx"><b>${esc(c.label)}</b>${c.hint ? `<span>${esc(c.hint)}</span>` : ''}</span><span class="chev">${ico('down')}</span></button>
      <div class="body" id="cb-${esc(c.id)}"><div class="rcards">${(c.read || []).map(rcard).join('') || `<p class="muted">${esc(tr('guide.nothingPicked', null, 'Nothing picked for this yet — try searching.'))}</p>`}</div></div></div>`).join('');
  const limLi = l => `<li>${esc(l.text)}${l.src ? ` <span class="lim-src">— <a href="${hrefFor(l)}">${esc(l.src.publisher || l.src.title)}${l.page ? ', p. ' + l.page : ''}</a></span>` : l.zim ? ` <span class="lim-src">— <a href="${hrefFor(l)}">encyclopedia</a></span>` : ''}</li>`;
  const LIM = 4, lims = t.limits || [];
  const limits = lims.length ? `<section class="limits" aria-labelledby="lim"><h2 id="lim">${ico('warn')}${esc(tr('guide.stopAndGetHelp', null, 'Stop and get help when…'))}</h2><ul>${lims.slice(0, LIM).map(limLi).join('')}</ul>${lims.length > LIM ? `<details><summary>${esc(tr('guide.showAllWarnings', { count: lims.length }, 'Show all {count} warnings'))}</summary><ul>${lims.slice(LIM).map(limLi).join('')}</ul></details>` : ''}</section>` : '';
  const disagree = (t.gaps?.disagree || []).length ? `<div class="disagree"><b>${esc(tr('guide.sourcesDisagree', null, 'Sources disagree'))}</b><ul>${t.gaps.disagree.map(x => `<li>${esc(x)}</li>`).join('')}</ul></div>` : '';
  const route = (t.route || []).length ? `<h2>${esc(tr('guide.yourRoute', null, 'Your learning route'))}</h2><p class="muted small">${esc(tr('guide.routeTicksNote', null, 'Ticks are your own notes on this device. Reading or watching is not the same as practising safely.'))}</p>
    <ol class="route">${t.route.map((s, i) => { const k = id + ':' + i, p = progress[k] || {}; return `<li class="step${p.practised ? ' done' : ''}"><h3>${esc(s.title.replace(/^Step \d+:\s*/i, ''))}</h3>${s.goal ? `<p class="goal">${esc(s.goal)}</p>` : ''}
      <div class="rcards">${(s.read || []).map(rcard).join('')}</div>
      <div class="mark"><label><input type="checkbox" data-prog="${k}" data-f="read" ${p.read ? 'checked' : ''}> ${tr('guide.readThis', null, 'I’ve read this')}</label><label><input type="checkbox" data-prog="${k}" data-f="practised" ${p.practised ? 'checked' : ''}> ${tr('guide.practisedWithSomeone', null, 'I’ve practised it with someone who knows')}</label></div></li>` }).join('')}</ol>` : '';
  const sec = (icon, title, items) => items && items.length ? `<details class="more"><summary>${ico(icon)}<span>${title} <span class="n">· ${items.length}</span></span></summary><div class="body"><ul class="list">${items.map(i => rowItem({ ...i, preview: true })).join('')}</ul></div></details>` : '';
  const vids = topicVideos(t);
  const related = (t.related || []).map(topicById).filter(Boolean);
  main.innerHTML = `<div class="ghero" ${tcStyle(id)}><div class="ghero-in">${crumbs([[tr('nav.guides', null, 'Guides'), '#/guides'], [learn ? tr('home.learnSkill', null, 'Learn a skill') : tr('home.needHelpNow', null, 'Need help now'), learn ? '#/library' : '#/guides'], [topicResult(id, 'title', t.title)]])}
      <div class="row1"><span class="ico">${ico(t.id)}</span><h1>${topicLabelHtml(id, 'title', t.title)}</h1></div><p class="lead">${esc(t.intro || '')}</p>
      <div class="vactions" style="margin-bottom:0">${askLink('topic:' + id, 'guide.askAboutThis', tr('guide.askAboutThis', null, 'Ask a question about this'))}</div></div></div>
    <div class="gcols" ${tcStyle(id)}><div>
      ${(t.choices || []).length ? `<p class="ask" id="askh">${learn ? tr('guide.whereStart', null, 'Where do you want to start?') : tr('guide.whatsHappening', null, 'What’s happening?')}</p><div class="situations" aria-labelledby="askh">${sits}</div>` : ''}
      <div class="gnarrow">${limits}${disagree}</div>
      ${route}
      ${vids.length ? secHead(tr('guide.videosForThis', null, 'Videos for this'), tr('guide.pickedVideos', { count: vids.length }, '{count} picked videos')) + rail(vids.map(v => vcard(v)).join('')) : ''}
      ${sec('prep', trLang('guide.getReady', null, 'Get ready before it happens'), t.prepare)}
      ${sec('book', tr('guide.goDeeper', null, 'Go deeper: full manuals & articles'), t.learn)}
      ${(t.gaps?.missing || []).length ? `<details class="more"><summary>${ico('warn')}<span>${tr('guide.notInLibrary', null, 'Not in this library')}</span></summary><div class="body"><p class="muted small" style="margin-top:0">${tr('guide.gapsNotFound', null, 'Looked for but not found when this guide was put together (October 2026):')}</p><ul>${t.gaps.missing.map(x => `<li>${esc(x)}</li>`).join('')}</ul></div></details>` : ''}
      ${related.length ? `<h2>${tr('guide.related', null, 'Related guides')}</h2><div class="related">${related.map(r => `<a class="chip" href="#/t/${r.id}" ${tcStyle(r.id)}><span style="color:var(--tc)">${ico(r.id)}</span>${topicLabelHtml(r.id, 'title', r.title)}</a>`).join('')}</div>` : ''}
    </div><aside class="gside" aria-label="${tr('guide.safety', null, "Safety")}"></aside></div>`;
  // On wide screens the safety box sits beside the choices so it stays visible.
  const side = $('.gside', main), nar = $('.gnarrow', main);
  const placeSide = () => { if (!side || !nar) return; if (innerWidth >= 1050) { if (!side.firstChild) side.append(...nar.childNodes) } else if (side.firstChild) nar.append(...side.childNodes) };
  placeSide(); window.onresize = placeSide;
  $$('[data-choice]', main).forEach(b => b.addEventListener('click', () => {
    const c = b.closest('.sit'), on = !c.classList.contains('open');
    $$('.sit.open', main).forEach(x => { x.classList.remove('open'); $('button', x).setAttribute('aria-expanded', 'false') });
    if (on) { c.classList.add('open'); b.setAttribute('aria-expanded', 'true') }
    history.replaceState(null, '', '#/t/' + id + (on ? '/' + b.dataset.choice : ''));
    if (on) setTimeout(() => c.scrollIntoView({ block: 'start', behavior: 'smooth' }), 30);
  }));
  $$('[data-prog]', main).forEach(cb => cb.addEventListener('change', () => {
    const p = store.get('progress', {}); p[cb.dataset.prog] = { ...(p[cb.dataset.prog] || {}), [cb.dataset.f]: cb.checked }; store.set('progress', p);
    cb.closest('.step').classList.toggle('done', !!p[cb.dataset.prog].practised);
  }));
  if (open) { const c = $('#c-' + CSS.escape(open)); if (c) setTimeout(() => c.scrollIntoView({ block: 'start' }), 0) }
}

/* ------------------------------------------------------------- videos -- */
async function videosHome() {
  setUiTitle('nav.videos', tr('nav.videos', null, 'Videos'));
  main.innerHTML = `<h1 data-i18n="videos.title">Videos</h1><p class="lead" data-i18n="videos.lead">Watch it done — practical how-tos first, then channels and courses.</p>
    <div class="vtools">${searchBox('vq', '', tr('videos.searchTitles', null, 'Search video titles'))}</div>
    <div class="chips" style="margin-top:8px">${[['short', 'videos.under10', 'Under 10 min'], ['medium', 'videos.10to30', '10–30 min'], ['long', 'videos.over30', 'Over 30 min']].map(([k, key, l]) => `<a class="chip" href="#/videos/all?len=${k}">${ico('clock')}<span data-i18n="${key}">${tr(key, null, l)}</span></a>`).join('')}</div>
    <div id="vrows"><p class="loading" data-i18n="videos.loading">Loading videos…</p></div>`;
  $('#vqF').addEventListener('submit', e => { e.preventDefault(); location.hash = '#/videos/all?q=' + encodeURIComponent($('#vq').value.trim()) });
  const rows = await api('/api/videos');
  const cont = (await resumable(20)).slice(0, 12);
  const GCOL = { health: 'hurt', water: 'water', food: 'food', power: 'power', outdoors: 'shelter', repair: 'repair', making: 'land' };
  $('#vrows').innerHTML =
    (cont.length ? secHead(`<span data-i18n="videos.continue">Continue watching</span>`) + rail(cont.map(([id, v]) => vcard({ id, title: v.title, thumb: v.thumb, duration: v.d }, { sub: tr('home.resumeAt', { time: clock(v.t) }, 'Resume at {time}') })).join('')) : '') +
    rows.map(r => secHead(esc(r.title), r.note ? esc(r.note) : '', `<a href="#/videos/${r.id}">${esc(tr('videos.seeAllCount', { count: r.count }, 'See all {count}'))}</a>`) +
      rail(r.items.map(v => vcard(v, { style: tcStyle(v.guide || GCOL[r.id]) })).join(''))).join('') +
    `<p class="small muted" style="margin-top:24px" data-i18n="videos.offlineNote">Only videos already downloaded are shown. Many have no captions, so the transcript search and the assistant can’t see what’s said in them.</p>`;
  wireRails();
}
async function videoRow(row, q) {
  const len = q.get('len') || '', sort = q.get('sort') || '', qq = q.get('q') || '';
  const base = `#/videos/${row}`;
  const qs = o => { const p = new URLSearchParams({ q: qq, len, sort, ...o }); for (const [k, v] of [...p]) if (!v) p.delete(k); const s = p.toString(); return base + (s ? '?' + s : '') };
  let off = 0;
  const first = await api(`/api/videos/${row}?q=${encodeURIComponent(qq)}&len=${len}&sort=${sort}&offset=0`);
  setTitle(first.title);
  main.innerHTML = `<div>${backButton('#/videos')}</div><h1 style="margin-top:12px">${esc(qq ? tr('videos.headingQuoted', { title: qq }, 'Videos: “{title}”') : first.title)}</h1>${first.note ? `<p class="lead">${esc(first.note)}</p>` : ''}
    <div class="vtools">${searchBox('vq', qq, tr('videos.searchThese', null, 'Search these videos'), ['search.go', 'Go'])}
      <label class="sr" for="vsort" data-i18n="videos.sort">Sort</label><select id="vsort">${[['', 'videos.mostUseful', 'Most useful first'], ['short', 'videos.shortestFirst', 'Shortest first'], ['new', 'videos.newestFirst', 'Newest first'], ['az', 'videos.az', 'A to Z']].map(([k, key, l]) => `<option value="${k}" ${k === sort ? 'selected' : ''} data-i18n="${key}">${tr(key, null, l)}</option>`).join('')}</select></div>
    <div class="chips" style="margin:8px 0 16px">${[['', tr('videos.anyLength', null, 'Any length')], ['short', tr('videos.under10', null, 'Under 10 min')], ['medium', tr('videos.10to30', null, '10–30 min')], ['long', tr('videos.over30', null, 'Over 30 min')]].map(([k, l]) => `<a class="chip ${k === len ? 'on' : ''}" href="${qs({ len: k })}">${l}</a>`).join('')}</div>
    <p class="muted small">${esc(tr('videos.videoCount', { count: first.total }, '{count} videos'))}</p>
    <div class="vgrid" id="vg"></div><p id="vmore"></p>`;
  $('#vqF').addEventListener('submit', e => { e.preventDefault(); location.hash = qs({ q: $('#vq').value.trim() }) });
  $('#vsort').addEventListener('change', e => { location.hash = qs({ sort: e.target.value }) });
  const add = d => {
    $('#vg').insertAdjacentHTML('beforeend', d.items.map(v => vcard(v)).join('') || (off ? '' : `<div class="empty" style="grid-column:1/-1">${esc(tr('videos.nothingMatches', null, 'No videos match. Try another word or length.'))}</div>`));
    $('#vmore').innerHTML = d.more ? `<button class="btn plain" id="vmb">${esc(tr('videos.showMore', null, 'Show more videos'))}</button>` : '';
    if (d.more) $('#vmb').onclick = async () => { off += 48; add(await api(`/api/videos/${row}?q=${encodeURIComponent(qq)}&len=${len}&sort=${sort}&offset=${off}`)) };
  };
  add(first);
}

// Video formats some computers can't play, by the code an MP4 file gives its video track: the name to show, and what to ask the player.
const UNPLAYABLE = { av01: ['AV1', 'video/mp4; codecs="av01.0.05M.08"'], vp09: ['VP9', 'video/mp4; codecs="vp09.00.10.08"'], hvc1: ['HEVC', 'video/mp4; codecs="hvc1.1.6.L93.B0"'], hev1: ['HEVC', 'video/mp4; codecs="hev1.1.6.L93.B0"'] };
// The format codes of an MP4 file's tracks ("av01", "mp4a"), read from the file's own index. [] when they can't be read (not an MP4, say).
// An MP4 is a row of boxes, each starting with its length and a four-letter name. This reads the start of each box until it finds
// the index ("moov"), then reads only that: never the pictures or the sound.
async function videoFormats(url) {
  let size = 0;
  const part = async (at, n) => {
    const r = await fetch(url, { headers: { Range: `bytes=${at}-${at + n - 1}` } });
    size = +(/\/(\d+)$/.exec(r.headers.get('Content-Range') || '') || [])[1] || 0;
    if (r.status !== 206 || !size) throw new Error('no byte range');
    return new DataView(await r.arrayBuffer());
  };
  const name = (v, at) => String.fromCharCode(v.getUint8(at), v.getUint8(at + 1), v.getUint8(at + 2), v.getUint8(at + 3));
  const found = [];
  const inside = (v, at, end) => {   // the boxes between at and end; a track's format is the first name in its "stsd" box
    while (at + 8 <= end) {
      let n = v.getUint32(at), head = 8;
      if (n === 1 && at + 16 <= end) { n = Number(v.getBigUint64(at + 8)); head = 16 } else if (n === 0) n = end - at;
      if (n < head || at + n > end) return;
      const type = name(v, at + 4);
      if (type === 'stsd' && n >= head + 16) found.push(name(v, at + head + 12));
      else if (['moov', 'trak', 'mdia', 'minf', 'stbl'].includes(type)) inside(v, at + head, at + n);
      at += n;
    }
  };
  for (let at = 0, i = 0; i < 64; i++) {
    const v = await part(at, 16);
    if (v.byteLength < 16) break;
    let n = v.getUint32(0);
    if (n === 1) n = Number(v.getBigUint64(8)); else if (n === 0) n = size - at;
    if (n < 8) break;
    if (name(v, 4) === 'moov') { if (n <= 32 * 1024 * 1024) { const m = await part(at, n); inside(m, 0, m.byteLength) } break }
    at += n;
    if (at + 16 > size) break;
  }
  return found;
}

async function watch(id, t, from) {
  const d = await api('/api/doc/' + encodeURIComponent(id));
  setTitle(d.title);
  const selfHref = `#/watch/${encodeURIComponent(id)}`;
  remember({ key: 'v:' + id, title: d.title, href: selfHref, sub: tr('common.video', null, 'Video') + ' · ' + fmtDur(d.duration) });
  const p = vprog()[id];
  const start = t !== null && Number.isFinite(+t) && +t >= 0 ? +t : null;
  const resumeAt = start === null && p && p.t > 15 && (!d.duration || p.t < d.duration - 20) ? p.t : 0;
  const watched = isWatched(id, p, d);
  main.innerHTML = `<div class="rtop">${backButton(from, ['nav.videos', tr('nav.videos', null, 'Videos')])}</div>
  <div class="watch">
    <div>
      <div class="player"><video id="vid" controls preload="metadata" playsinline src="${fileUrl(d.path)}${start !== null ? '#t=' + start : ''}"></video></div>
      <div class="video-speed"><label for="videoSpeed">${trLang('videos.speed', null, 'Playback speed')}</label><select id="videoSpeed"><option value="0.5">0.5×</option><option value="0.75">0.75×</option><option value="1" selected lang="${esc(trLocale('videos.speedNormal'))}">${tr('videos.speedNormal', null, 'Normal')}</option><option value="1.25">1.25×</option><option value="1.5">1.5×</option><option value="2">2×</option></select></div>
      ${d.remote ? `<p class="small muted" style="margin:6px 0 0">${esc(tr('videos.storedRemote', { name: d.remote }, 'Stored on the remote drive “{name}”. It plays only while that computer is reachable.'))}</p>` : ''}
      <h1 class="vtitle">${esc(d.title)}</h1>
      <div class="vmeta"><b>${esc(d.publisher || '')}</b><span>${fmtDur(d.duration)}</span>${d.upload_date ? `<span>${esc(d.upload_date.replace(/(\d{4})(\d\d)(\d\d)/, '$1-$2-$3'))}</span>` : ''}<span>${esc(d.trust)}</span></div>
      ${resumeAt ? `<div class="resume" id="resume"${watched ? ' hidden' : ''}>${esc(tr('videos.youStoppedAt', { time: clock(resumeAt) }, 'You stopped at {time}.'))} <button class="btn" id="resYes">${esc(tr('videos.resume', null, 'Resume'))}</button><button class="btn plain" id="resNo">${esc(tr('videos.startOver', null, 'Start over'))}</button></div>` : ''}
      <div class="vactions dock">${saveButton({ key: 'v:' + id, title: d.title, href: selfHref, sub: tr('common.video', null, 'Video') + ' · ' + fmtDur(d.duration) })}${watchedButton(id, d)}<a class="btn plain" title="${esc(tr('videos.askAbout', null, 'Ask about this video'))}" href="#/ask?about=${encodeURIComponent('video:' + id)}&${fromQ()}" id="askv">${ico('ask')}<span>${esc(tr('videos.askAbout', null, 'Ask about this video'))}</span></a></div>
      ${momentSection(true)}
      <div class="notice small">${esc(tr('videos.noticeHobby', null, 'A video shows how one person did something. Watching isn’t practice, and it may not match current safety guidance — check a manual for anything risky.'))}</div>
    </div>
    <section class="txpanel" id="tx" aria-label="${esc(tr('videos.transcript', null, 'Transcript'))}"><header><h2>${esc(tr('videos.transcript', null, 'Transcript'))}</h2><label class="sr" for="cueQ">${esc(tr('videos.findInTranscriptLabel', null, 'Find in transcript'))}</label><input id="cueQ" type="search" placeholder="${esc(tr('videos.findInTranscript', null, 'Find words in the transcript'))}"></header>
      <div class="cues" id="cues"><p class="muted" style="padding:12px 14px">${esc(tr('videos.loadingTranscript', null, 'Loading transcript…'))}</p></div><div class="txnote" id="txnote"></div></section>
  </div>
  <div id="morev"></div>
  <details class="about-src"><summary>${esc(tr('videos.aboutThis', null, 'About this video'))}</summary><div class="in"><dl><dt>${esc(tr('videos.channel', null, 'Channel'))}</dt><dd>${esc(d.publisher || '—')}</dd><dt>${esc(tr('reader.kind', null, 'Kind'))}</dt><dd>${esc(d.trust)}</dd><dt>${esc(tr('videos.length', null, 'Length'))}</dt><dd>${fmtDur(d.duration) || tr('common.unknown', null, 'unknown')}</dd>${d.notes ? `<dt>${esc(tr('videos.note', null, 'Note'))}</dt><dd>${esc(d.notes)}</dd>` : ''}${d.source_url ? `<dt>${esc(tr('videos.onlineOriginal', null, 'Online original'))}</dt><dd>${esc(hostOf(d.source_url))} <span class="muted">${esc(tr('videos.onlineNotNeeded', null, '(online; not needed here)'))}</span></dd>` : ''}</dl></div></details>`;
  const vid = $('#vid');
  wireMoments({ video: d, player: vid, start });
  const speed = $('#videoSpeed');
  speed.addEventListener('change', () => { vid.playbackRate = Number(speed.value) });
  // Native controls may also change the rate. Keep the visible control in sync.
  vid.addEventListener('ratechange', () => {
    const value = String(vid.playbackRate);
    if (![...speed.options].some(option => option.value === value)) speed.add(new Option(value + '×', value));
    speed.value = value;
  });
  if (d.thumb) vid.poster = fileUrl(d.thumb);
  vid.addEventListener('error', async () => {
    const say = why => vid.closest('.player')?.insertAdjacentHTML('afterend', `<div class="err">${why}</div>`);
    if (d.remote) return say(esc(tr('videos.remoteUnreachable', { name: d.remote }, 'This video is on the remote drive “{name}”, which isn’t reachable right now. The transcript below still works.')));
    // Say why when the reason is the format: some library videos are AV1, which a computer without an AV1 decoder (a Mac before the M3) can't play.
    const f = (await videoFormats(fileUrl(d.path)).catch(() => [])).map(x => UNPLAYABLE[x]).find(x => x && !vid.canPlayType(x[1]));
    if (!vid.isConnected) return;   // the person has gone to another page
    say(f ? tr('videos.unplayableFormat', { format: f[0], path: `<b style="overflow-wrap:anywhere">library-data/${esc(d.path)}</b>` }, 'This video is saved in the {format} format, which this computer can’t play in Lastbook. Try another video player that supports {format}, such as VLC: the file is in your Lastbook data folder, at {path}.')
      : `${esc(tr('videos.couldntPlay', null, 'This video file couldn’t be played here.'))} <a href="${fileUrl(d.path)}" target="_blank" rel="noopener">${esc(tr('videos.openFileDirectly', null, 'Open the file directly'))}</a>.`);
  }, { once: true });
  if (resumeAt) {
    $('#resYes').onclick = () => { vid.currentTime = resumeAt; vid.play().catch(() => { }); $('#resume')?.remove() };
    $('#resNo').onclick = () => { vid.currentTime = 0; vid.play().catch(() => { }); $('#resume')?.remove() };
    vid.addEventListener('play', () => { $('#resume')?.remove() });
  }
  const updateWatchedBtn = () => {
    const b = $('#markWatched');
    if (!b) return;
    const w = isWatched(id, null, d);
    if (b.getAttribute('aria-pressed') === String(w)) return;
    b.setAttribute('aria-pressed', w);
    const titleKey = w ? 'videos.markUnwatched' : 'videos.markWatched', labelKey = w ? 'videos.watched' : 'videos.markWatched';
    b.title = tr(titleKey, null, w ? 'Mark as unwatched' : 'Mark as watched');
    b.dataset.i18nTitle = titleKey;
    const sp = $('span', b); if (sp) { sp.dataset.i18n = labelKey; sp.textContent = tr(labelKey, null, w ? 'Watched' : 'Mark watched') }
    const res = $('#resume'); if (res) res.hidden = w;
  };
  const bWatched = $('#markWatched');
  if (bWatched) {
    bWatched.onclick = () => {
      const cur = isWatched(id, null, d);
      setWatched(id, !cur);
      updateWatchedBtn();
      toast(tr(!cur ? 'videos.toastMarkedWatched' : 'videos.toastMarkedUnwatched', null, !cur ? 'Marked as watched' : 'Marked as unwatched'));
    };
  }
  let lastSave = 0;
  let below90 = !((t || (resumeAt && !watched)) && (d.duration || vid.duration) && (t || (resumeAt && !watched)) >= (d.duration || vid.duration) * 0.9);
  const saveProg = () => {
    if (vid.currentTime > 3) {
      $('#resume')?.remove();
      setVprog(id, { t: vid.currentTime, d: d.duration || vid.duration, title: d.title, thumb: d.thumb });
    }
  };
  const onSeek = () => {
    const dur = d.duration || vid.duration;
    if (dur) below90 = vid.currentTime < dur * 0.9;
  };
  vid.addEventListener('seeking', onSeek);
  vid.addEventListener('seeked', onSeek);
  vid.addEventListener('loadedmetadata', () => {
    if (!d.duration && vid.duration) d.duration = vid.duration;
    const dur = d.duration || vid.duration;
    if (dur) {
      const pos = vid.currentTime || t || (resumeAt && $('#resume') && !$('#resume').hidden ? resumeAt : 0);
      below90 = pos < dur * 0.9;
    }
  });
  vid.addEventListener('timeupdate', () => {
    const dur = d.duration || vid.duration;
    if (dur) {
      if (vid.currentTime < dur * 0.9) {
        below90 = true;
      } else if (below90 && !vid.paused && !vid.seeking) {
        below90 = false;
        setWatched(id, true);
        updateWatchedBtn();
      }
    }
    if (Date.now() - lastSave > 4000) { lastSave = Date.now(); saveProg() }
  });
  vid.addEventListener('ended', () => {
    if (!isWatched(id, null, d)) {
      setWatched(id, true);
      updateWatchedBtn();
    }
  });
  vid.addEventListener('pause', saveProg);
  leaving = () => { saveProg(); vid.pause() };
  // keep tr('videos.askAbout', null, "Ask about this video") pointing at the current moment
  vid.addEventListener('pause', () => { const a = $('#askv'); if (a) a.href = `#/ask?about=${encodeURIComponent('video:' + id + ':' + Math.round(vid.currentTime))}&${fromQ()}` });
  let cues = [];
  try {
    const tx = await api('/api/transcript/' + encodeURIComponent(id)); cues = tx.cues || [];
    $('#txnote').textContent = cues.length ? tr('videos.captionsMayError', { kind: tx.source === 'authored' ? tr('videos.publisherCaptions', null, 'Captions written by the publisher') : /auto/.test(tx.source || '') ? tr('videos.automaticCaptions', null, 'Automatic captions') : tr('videos.captions', null, 'Captions') }, '{kind} — may contain errors.') : '';
  } catch { }
  const box = $('#cues');
  const draw = q => {
    const rx = q ? new RegExp(q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'ig') : null;
    const list = cues.filter(c => !rx || c.text.match(rx));
    box.innerHTML = list.length ? list.map(c => `<button class="cue" data-t="${c.t ?? ''}"><time>${c.t != null ? clock(c.t) : ''}</time><span>${rx ? esc(c.text).replace(rx, m => `<mark>${m}</mark>`) : esc(c.text)}</span></button>`).join('')
      : `<p class="muted" style="padding:12px 14px">${cues.length ? tr('videos.noMatch', null, 'No matching words.') : tr('videos.noTranscript', null, 'No transcript was saved for this video, so search and the assistant can’t see what’s said in it.')}</p>`;
  };
  draw('');
  $('#cueQ').addEventListener('input', e => draw(e.target.value.trim()));
  box.addEventListener('click', e => { const b = e.target.closest('.cue'); if (b && b.dataset.t !== '') { vid.currentTime = +b.dataset.t; vid.play().catch(() => { }); if (innerWidth < 1000) scrollTo({ top: 0, behavior: 'smooth' }) } });
  let lastOn = null;
  vid.addEventListener('timeupdate', () => {
    const now = vid.currentTime; let on = null;
    for (const b of box.children) { if (b.dataset && b.dataset.t !== '' && +b.dataset.t <= now) on = b; else if (on) break }
    if (on !== lastOn) { lastOn && lastOn.classList.remove('on'); on && on.classList.add('on'); lastOn = on; if (on && !$('#cueQ').value && innerWidth >= 1000) on.scrollIntoView({ block: 'nearest' }) }
  });
  try {
    const rel = await api('/api/videos/related/' + encodeURIComponent(id));
    if (rel.length && $('#morev')) { $('#morev').innerHTML = secHead(tr('videos.moreLikeThis', null, 'More like this')) + rail(rel.map(v => vcard(v)).join('')); translateRendered($('#morev')); wireRails($('#morev')) }
  } catch { }
}

/* ------------------------------------------------------- video moments -- */
function momentSection(watching = false) {
  return `<section class="moments" aria-labelledby="momentsTitle">
    <header class="moments-head"><h2 id="momentsTitle">${watching ? tr('moment.savedTitle', null, 'Saved moments') : tr('moment.pageTitle', null, 'Video moments')} <span id="momentCount" class="moment-count"></span></h2>
      ${watching ? `<button class="btn plain" id="saveMoment" disabled>${ico('save')}<span>${esc(tr('moment.saveThis', null, 'Save this moment'))}</span></button>` : ''}</header>
    <p class="moments-hint">${watching ? tr('moment.keepParts', null, 'Keep the parts you want to return to.') : tr('moment.savedPlaces', null, 'Your saved places in videos.')} ${esc(tr('moment.keptOnDevice', null, 'Kept on this device.'))}</p>
    <div id="momentEditor"></div><ul class="moment-list" id="momentList"></ul>
    <p id="momentStatus" class="moment-status" role="status"></p>
  </section>`;
}

function wireMoments({ video = null, player = null, available = null, start = null } = {}) {
  const root = $('.moments'), list = $('#momentList', root), editor = $('#momentEditor', root);
  const status = $('#momentStatus', root), add = $('#saveMoment', root);
  let editing = null;
  const say = (text, error = false) => { status.textContent = text; status.classList.toggle('is-error', error) };
  const focusRow = key => {
    const button = $$('[data-moment-edit]', root).find(b => b.dataset.momentEdit === key);
    if (button) button.focus(); else if (add) add.focus(); else $('#momentsTitle').focus();
  };
  $('#momentsTitle').tabIndex = -1;
  const read = () => VideoMoments.readSaved().filter(VideoMoments.isMoment);
  const draw = () => {
    let items;
    try { items = read() } catch (e) { say(e.message, true); return }
    if (video) items = items.filter(x => x.videoId === video.id).sort((a, b) => a.time - b.time);
    $('#momentCount', root).textContent = items.length || '';
    list.innerHTML = items.length ? items.map(x => {
      const missing = available && !available.has(x.videoId), title = esc(x.title), time = clock(x.time);
      const content = `<span class="moment-time">${time}</span><span class="moment-name"><b>${title}</b>${!video ? `<small>${esc(x.videoTitle)}${missing ? ' · ' + esc(tr('moment.notInLibrary', null, 'Not in this library')) : ''}</small>` : ''}</span>`;
      const open = video ? `<button class="moment-open" data-moment-play="${x.time}" aria-label="${esc(tr('moment.playAt', { title, time }, 'Play {title} at {time}'))}">${content}</button>`
        : missing ? `<span class="moment-open unavailable">${content}</span>`
          : `<a class="moment-open" href="${esc(VideoMoments.href(x))}" aria-label="${esc(tr('moment.openAt', { title, time }, 'Open {title} at {time}'))}">${content}</a>`;
      return `<li>${open}<div class="moment-actions"><button data-moment-edit="${esc(x.key)}" aria-label="${esc(tr('moment.renameNamed', { title }, 'Rename {title}'))}">${esc(tr('moment.rename', null, 'Rename'))}</button><button data-moment-remove="${esc(x.key)}" aria-label="${esc(tr('moment.removeNamed', { title }, 'Remove {title}'))}">${esc(tr('moment.remove', null, 'Remove'))}</button></div></li>`;
    }).join('') : `<li class="moment-empty">${video ? esc(tr('moment.pauseHint', null, 'Pause at a useful part, then choose Save this moment.')) : esc(tr('moment.noneSaved', null, 'No video moments saved.'))}</li>`;
  };
  const close = () => {
    const key = editing && editing.key;
    editing = null; editor.replaceChildren(); focusRow(key);
  };
  const edit = (item, seconds) => {
    if (player) player.pause();
    const time = item ? item.time : Math.floor(seconds);
    editing = { key: item ? item.key : null, time };
    editor.innerHTML = `<form class="moment-form"><p class="moment-form-title">${item ? tr('moment.renameTitle', null, 'Rename moment') : tr('moment.saveTitle', null, 'Save moment')} <span class="moment-time">${clock(time)}</span></p>
      <label for="momentName">${tr('moment.name', null, 'Name')} <span class="muted">${tr('moment.optional', null, '(optional)')}</span></label>
      <input id="momentName" type="text" maxlength="120" autocomplete="off" placeholder="${tr('moment.placeholder', null, "For example, tools needed")}" value="${esc(item ? item.title : '')}">
      <div class="moment-form-actions"><button class="btn" type="submit">${item ? tr('moment.saveChanges', null, 'Save changes') : tr('moment.saveTitle', null, 'Save moment')}</button><button class="btn plain" type="button" id="cancelMoment">${tr('common.cancel', null, 'Cancel')}</button></div></form>`;
    say('');
    $('#cancelMoment', editor).onclick = close;
    $('form', editor).onkeydown = e => { if (e.key === 'Escape') { e.preventDefault(); close() } };
    $('form', editor).onsubmit = e => {
      e.preventDefault();
      const title = $('#momentName', editor).value.trim() || 'Moment at ' + clock(editing.time);
      try {
        const item = editing.key ? VideoMoments.rename(editing.key, title) : VideoMoments.save(video, editing.time, title);
        editing = null; editor.replaceChildren(); draw(); savedCount(); focusRow(item.key);
        say(tr('moment.savedToast', null, 'Moment saved on this device.'));
      } catch (e) { say(e.message, true) }
    };
    $('#momentName', editor).focus();
  };
  if (player) {
    const ready = () => !player.error && player.readyState >= 1 && Number.isFinite(player.duration) && player.duration > 0;
    const update = () => { add.disabled = !ready() };
    player.addEventListener('loadedmetadata', update);
    player.addEventListener('durationchange', update);
    player.addEventListener('error', update);
    const checkStart = () => {
      if (ready() && start !== null && start >= player.duration)
        say(tr('moment.beyondEnd', null, 'This position is beyond the end of this video.'), true);
    };
    player.addEventListener('loadedmetadata', checkStart, { once: true });
    checkStart();
    update();
    add.onclick = () => {
      if (!ready()) return;
      const time = Math.floor(Math.min(player.currentTime, Math.max(0, player.duration - 0.001)));
      try { edit(read().find(x => x.videoId === video.id && x.time === time), time) }
      catch (e) { say(e.message, true) }
    };
  }
  list.onclick = e => {
    const play = e.target.closest('[data-moment-play]');
    if (play && player) {
      const time = +play.dataset.momentPlay;
      if (player.readyState < 1 || player.error) return say(tr('videos.notReady', null, 'This video is not ready to play.'), true);
      if (time >= player.duration) return say(tr('moment.beyondEndOpen', null, 'This moment is beyond the end of this video.'), true);
      player.currentTime = time; player.play().catch(() => { }); say(''); return;
    }
    const rename = e.target.closest('[data-moment-edit]'), remove = e.target.closest('[data-moment-remove]');
    try {
      if (rename) {
        const item = read().find(x => x.key === rename.dataset.momentEdit);
        if (!item) return say(tr('moment.gone', null, 'This moment is no longer saved.'), true);
        edit(item);
      }
      if (remove) {
        const key = remove.dataset.momentRemove;
        VideoMoments.remove(key);
        if (editing && editing.key === key) { editing = null; editor.replaceChildren() }
        draw(); savedCount();
        const next = $('[data-moment-edit]', root);
        if (next) next.focus(); else if (add) add.focus(); else $('#momentsTitle').focus();
        say(tr('moment.removed', null, 'Moment removed.'));
      }
    } catch (e) { say(e.message, true) }
  };
  draw();
}

/* ------------------------------------------------------------- reader -- */
async function reader(id, page, from, view) {
  const d = await api('/api/doc/' + encodeURIComponent(id));
  if (d.kind === 'video') { swap('#/watch/' + encodeURIComponent(id) + (from ? '?from=' + encodeURIComponent(from) : '')); return }
  if (d.kind === 'transcript' && d.videoId) { swap('#/watch/' + encodeURIComponent(d.videoId) + (from ? '?from=' + encodeURIComponent(from) : '')); return }
  setTitle(d.title, [d.publisher, d.year, d.trust].filter(Boolean).join(' · '));
  const isPdf = d.kind === 'pdf', total = d.pages || 1;
  const isWeb = d.kind === 'html' && /\.x?html?$/i.test(d.path);   // a plain text file, such as a lecture transcript, reads as text in the page itself
  page = Math.min(Math.max(page || 1, 1), total);
  view = isPdf ? view || 'page' : isWeb ? view || 'web' : 'text';
  const key = 'd:' + id + (isPdf ? ':' + page : '');
  const selfHref = `#/read/${encodeURIComponent(id)}?p=${page}`;
  remember({ key: 'd:' + id, title: d.title, href: selfHref, sub: (isPdf ? 'Page ' + page + ' · ' : '') + (d.publisher || '') });
  const go = (p, v = view) => `#/read/${encodeURIComponent(id)}?p=${p}&view=${v}${from ? '&from=' + encodeURIComponent(from) : ''}`;
  const views = isPdf ? [['page', tr('reader.pageView', null, 'Page')], ['text', tr('reader.textView', null, 'Text')], ['pdf', tr('reader.wholePdf', null, 'Whole PDF')]] : isWeb ? [['web', tr('reader.pageView', null, 'Page')], ['text', tr('reader.textOnly', null, 'Text only')]] : [];
  main.innerHTML = `
    <div class="rtop">${backButton(from)}</div>
    <h1 class="rtitle">${esc(d.title)}</h1>
    <div class="rsrc"><b>${esc(d.publisher || '')}</b>${d.year ? ' · ' + esc(d.year) : ''} · ${esc(d.trust)}</div>
    <div class="rmodes">${views.length ? `<div class="seg dock" role="group" aria-label="${tr('reader.howToShow', null, "How to show it")}">${views.map(([v, l]) => `<button data-view="${v}" aria-pressed="${v === view}">${l}</button>`).join('')}</div>` : ''}<span class="vactions dock">${askLink('doc:' + id + ':' + (isPdf ? page : 1), 'common.ask', 'Ask')}${saveButton({ key, title: d.title + (isPdf ? ' — page ' + page : ''), href: selfHref, sub: d.publisher || d.kindLabel })}<button class="tb-btn insp-btn" data-insp aria-label="${esc(tr('reader.toggleDetails', null, 'Show or hide the source details'))}" title="${esc(tr('common.details', null, 'Details'))}">${ico('insp')}</button></span></div>
    <div id="docbody"></div>
    ${d.imageOnly ? `<div class="notice">${esc(tr('reader.scanNoText', null, 'This is a scanned document without searchable text, so search and the assistant can’t read it. Use the Page view.'))}</div>` : ''}
    ${isPdf && view !== 'pdf' ? `<div class="rbar"><a class="btn plain nav" href="${go(page - 1)}" ${page <= 1 ? 'aria-disabled="true" style="opacity:.35;pointer-events:none"' : ''} aria-label="${esc(tr('nav.previousPage', null, 'Previous page'))}" data-i18n-aria-label="nav.previousPage" data-i18n-lang>${ico('back')}<span data-i18n="nav.previous">Previous</span></a>
      <span class="pnum"><label class="sr" for="pg">${esc(tr('reader.pageNumber', null, 'Page number'))}</label>${esc(tr('reader.pageView', null, 'Page'))} <input id="pg" inputmode="numeric" value="${page}"> ${esc(tr('common.of', null, 'of'))} ${total}</span>
      <a class="btn nav" href="${go(page + 1)}" ${page >= total ? 'aria-disabled="true" style="opacity:.35;pointer-events:none"' : ''} aria-label="${esc(tr('nav.nextPage', null, 'Next page'))}" data-i18n-aria-label="nav.nextPage" data-i18n-lang><span data-i18n="nav.next">Next</span>${ico('right')}</a></div>` : ''}
    <details class="about-src"><summary>${esc(tr('reader.aboutSource', null, 'About this source'))}</summary><div class="in"><p class="insp-h">${esc(d.title)}</p>
      <dl><dt>${esc(tr('reader.publisher', null, 'Publisher'))}</dt><dd>${esc(d.publisher || '—')}</dd><dt>${esc(tr('reader.kind', null, 'Kind'))}</dt><dd>${esc(d.trust)} · ${esc(d.kindLabel)}</dd>
      ${d.edition ? `<dt>${esc(tr('reader.edition', null, 'Edition'))}</dt><dd>${esc(d.edition)}</dd>` : ''}${d.year ? `<dt>${esc(tr('reader.year', null, 'Year'))}</dt><dd>${esc(d.year)}</dd>` : ''}
      <dt>${esc(tr('reader.savedOn', null, 'Saved'))}</dt><dd>${esc((d.retrieved_at || '').slice(0, 10) || tr('reader.unknownDate', null, 'unknown date'))} · ${esc(d.collection)}</dd>
      ${d.notes ? `<dt>${esc(tr('videos.note', null, 'Note'))}</dt><dd>${esc(d.notes)}</dd>` : ''}
      ${d.source_url ? `<dt>${esc(tr('videos.onlineOriginal', null, 'Online original'))}</dt><dd>${esc(hostOf(d.source_url))} <span class="muted">${esc(tr('reader.onlineNotNeededRead', null, '(online; not needed to read this copy)'))}</span></dd>` : ''}</dl>
      <p class="small muted">${esc(tr('reader.disclaimer', null, 'A reference copy, not advice checked for your situation. Check the date; older material can conflict with current guidance.'))}</p>
      ${isPdf || isWeb || !IN_WINDOW ? `<p><a class="btn ghost" href="${fileUrl(d.path)}${isPdf ? '#page=' + page : ''}" target="_blank" rel="noopener">${ico('ext')}${esc(tr('reader.openOriginal', null, 'Open the original file'))}</a></p>` : ''}</div></details>`;
  $$('[data-view]', main).forEach(b => b.addEventListener('click', () => swap(go(page, b.dataset.view))));
  // Read aloud (web/speak.js): this page's text, then on to the next page by itself, so a person whose hands are busy can keep listening.
  const sb = $('[data-speak]', main);
  if (sb) {
    let hadText = false;
    leaving = Speak.attach(sb, async () => {
      let t;
      try { t = await api(`/api/page/${encodeURIComponent(id)}/${isPdf ? page : 1}`) }
      catch { toast(tr('reader.speakFailed', null, 'This page could not be read aloud. Try again.')); return '' }   // shown, not only spoken: the sound may be off
      hadText = !!(t.text || '').trim();
      if (!hadText) toast(tr('reader.speakNoText', null, 'This page has no text that can be read aloud.'));
      return hadText ? (isPdf ? `${tr('reader.pageView', null, 'Page')} ${page}. ` : '') + t.text : tr('reader.speakNoText', null, 'This page has no text that can be read aloud.');
    }, isPdf && page < total ? () => { if (!hadText) return; try { sessionStorage.setItem('sg.speakOn', id) } catch { } location.hash = go(page + 1) } : null);
    let goingOn = null;
    try { goingOn = sessionStorage.getItem('sg.speakOn'); sessionStorage.removeItem('sg.speakOn') } catch { }
    // Reading went on to this page by itself: keyboard focus goes back to Stop when route() has finished and put it on the page's
    // start (startHere), so stopping is one key away, not a walk through the sidebar and toolbar while the voice goes on.
    if (goingOn === id) {
      focusAfterRoute = sb;
      Speak.ready().then(ok => {
        if (!ok || !sb.isConnected) return;
        sb.click();
        if (document.activeElement === $('#pageTop')) sb.focus({ preventScroll: true });   // the voices were listed after the page settled
      });
    }
  }
  if (innerWidth >= 1060 && !html.classList.contains('insp-off')) $('.about-src', main).open = true;
  const pg = $('#pg'); if (pg) pg.addEventListener('change', () => { const n = parseInt(pg.value, 10); if (n >= 1 && n <= total) location.hash = go(n) });
  const body = $('#docbody');
  if (view === 'page') {
    const w = Math.min(1600, Math.round(Math.min(innerWidth, 1000) * Math.min(2, devicePixelRatio || 1)));
    body.innerHTML = `<div class="pagewrap"><img class="pageimg" alt="${esc(tr('reader.pageOfTitle', { page, title: d.title }, 'Page {page} of {title}'))}" src="${pageImg(id, page, w)}"></div>`;
    const img = $('img', body);
    img.addEventListener('error', () => { body.innerHTML = `<div class="notice">${esc(tr('reader.imageFailed', null, 'This page image couldn’t be made.'))} <a href="${go(page, 'text')}">${esc(tr('reader.showTextInstead', null, 'Show the text instead'))}</a>.</div>` });
    if (page < total) { const n = new Image(); n.src = pageImg(id, page + 1, w) }
    let sx = null, sy = 0;
    const wrap = $('.pagewrap', body);
    wrap.addEventListener('touchstart', e => { if (e.touches.length === 1) { sx = e.touches[0].clientX; sy = e.touches[0].clientY } }, { passive: true });
    wrap.addEventListener('touchend', e => { if (sx == null) return; const dx = e.changedTouches[0].clientX - sx, dy = e.changedTouches[0].clientY - sy; sx = null; if (Math.abs(dx) > 70 && Math.abs(dx) > Math.abs(dy) * 1.5) { if (dx < 0 && page < total) location.hash = go(page + 1); if (dx > 0 && page > 1) location.hash = go(page - 1) } }, { passive: true });
  } else if (view === 'pdf') {
    body.innerHTML = `<iframe class="frame" title="${esc(d.title)}" src="${fileUrl(d.path)}#page=${page}"></iframe><p class="small muted">${esc(tr('reader.pdfPhoneHint', null, 'If the PDF doesn’t show here (some phones can’t), use Page view or open the original file.'))}</p>`;
  } else if (view === 'web') {
    const own = /(^|\/)documents\/lastbook\//.test(d.path);   // Lastbook's own pages (Sources and permissions) take the window's look from the server (engine/saved_pages.py, OWN_LOOK); an older server's stays a white sheet
    body.innerHTML = `<iframe class="frame${own ? ' own' : ''}" title="${esc(d.title)}" src="${fileUrl(d.path)}"></iframe>`;
  } else {
    body.innerHTML = `<p class="loading">${esc(tr('reader.loadingText', null, 'Loading text…'))}</p>`;
    try {
      const t = await api(`/api/page/${encodeURIComponent(id)}/${isPdf ? page : 1}`);
      const txt = (t.text || '').replace(/[ \t]{2,}/g, ' ').replace(/\n{3,}/g, '\n\n').trim();
      body.innerHTML = `${isPdf || isWeb ? `<div class="notice small">${esc(tr('reader.extractedNote', null, 'Text pulled out of the original automatically — tables, diagrams and warning boxes can be lost or out of order. Check the Page view for anything important.'))}</div>` : ''}<div class="pagetext">${esc(txt) || `<span class="muted">${esc(tr('reader.noText', null, 'No text on this page (it may be a picture or blank).'))}</span>`}</div>`;
    } catch (e) { body.innerHTML = errorBox(e, tr('reader.loadTextFailed', null, 'Couldn’t load the text.')) }
  }
  if (!isPdf) return;
  main.onkeydown = e => {
    if (e.target.tagName === 'INPUT' || e.altKey || e.metaKey || e.ctrlKey || e.shiftKey) return;   // Shift+Arrow selects text
    let next = page;
    if (e.key === 'ArrowRight') next++;
    if (e.key === 'ArrowLeft') next--;
    if (next === page || next < 1 || next > total) return;
    e.preventDefault();
    location.hash = go(next);
  };
  // The router puts focus on this marker before the first Tab.
  if (view !== 'pdf') pageTop.onkeydown = main.onkeydown;
}

/* --------------------------------------------------------------- wiki -- */
const zimLabel = name => {
  // Resolve translated names when used: a page restored from BFCache may see a
  // different language preference than the one active when this script loaded.
  const names = { mdwiki: tr('wiki.mdwiki', null, 'Medical encyclopedia (MDWiki)'), wikipedia: tr('wiki.wikipedia', null, 'Wikipedia (text only)'),
    wikibooks: tr('wiki.wikibooks', null, 'Wikibooks — how-to textbooks'), appropedia: tr('wiki.appropedia', null, 'Appropedia — appropriate technology') };
  for (const k in names) if (name.startsWith(k)) return names[k];
  return name;
};
async function wiki(path, from, y) {
  const tr = (k, p, f) => { const fill = (s) => (!p || s == null) ? s : String(s).replace(/\{([A-Za-z_][A-Za-z0-9_]*)\}/g, (m, n) => (p[n] != null ? p[n] : m)); return fill(typeof globalThis.lastbookTr === 'function' ? globalThis.lastbookTr(k, p, f) : f); };
  const [zim, ...rest] = path.split('/');
  const art = rest.join('/');
  const title = (art.split('/').pop() || '').replace(/_/g, ' ') || zimLabel(zim);   // parse() already decoded each component
  setTitle(title, '', zimLabel(zim));
  const src = '/zim/' + encodeURIComponent(zim) + '/' + art.split('/').map(encodeURIComponent).join('/');
  const selfHref = '#/wiki/' + path.split('/').map(encodeURIComponent).join('/');
  const mainPage = zimMain(zim);
  main.innerHTML = `<div class="rtop">${backButton(from || '#/encyclopedias')}<span id="wsave" class="dock">${saveButton({ key: 'w:' + path, title, href: selfHref, sub: zimLabel(zim) })}</span></div>
    <h1 class="rtitle" id="wtitle">${esc(title)}</h1><div class="rsrc"><span class="zn">${esc(zimLabel(zim))} · </span>${tr('wiki.communityWrittenReview', null, 'Community-written; check safety-critical steps against a manual')}${IN_WINDOW ? '' : ` · <a id="wopen" href="${src}" target="_blank" rel="noopener">${tr('wiki.openOnItsOwn', null, 'open on its own')}</a>`}</div>
    <iframe class="frame" id="wframe" title="${esc(title)}" src="${src}"></iframe>`;
  const f = $('#wframe');
  // The toolbar names the encyclopedia, and the article once the article's own title has scrolled up out of the frame, as a large title does
  const barName = () => { const n = f.lbName, b = $('#tbTitle'), t = n && f.contentWindow.scrollY > n.at - 4 ? n.nt : zimLabel(zim); if (b.textContent !== t) b.textContent = b.title = t };
  // One scroller: the frame fills the rest of the window, so the page around it never scrolls as well
  const fit = () => { if (!f.isConnected) return; f.style.height = Math.max(160, innerHeight - (f.getBoundingClientRect().top + scrollY) - parseFloat(getComputedStyle(document.body).paddingBottom || 0)) + 'px' };
  fit(); window.onresize = fit;
  // The frame's scrolling is read from here, every frame while it moves and ten times a second when it rests. The Mac app runs no script in
  // an article, and then no listener on it is ever called, its scroll events included. Once the text goes under the frame's top edge the
  // platform's separator shows there; the toolbar names the article; the reading place is kept for Back; a wide table fades at its edges.
  let lastY = -1, moved = 0;
  const watch = () => {
    if (!f.isConnected) return;
    const fw = f.contentWindow, t = f.lbTidy, now = performance.now();
    if (fw && fw.document.readyState === 'complete') {
      const y = fw.scrollY;
      if (y !== lastY) { lastY = y; moved = now; f.classList.toggle('scrolled', y > 2); scrolls[current] = y; barName() }
      if (t) for (const b of t.boxes) if (b.lbX !== b.scrollLeft) { b.lbX = b.scrollLeft; moved = now; t.edge(b) }
    }
    if (now - moved < 500) requestAnimationFrame(watch); else setTimeout(watch, 100);
  };
  watch();
  let shown = null;
  f.addEventListener('load', async () => {
    try {
      const fd = f.contentDocument;
      lookOf(fd);
      if (!fd.getElementById('lb-article') && !fd.getElementById('lb-host')) {   // an older server adds no look of its own: the window's colour shows through, as engine/saved_pages.py does it
        const st = fd.createElement('style'); st.id = 'lb-host';
        st.textContent = 'html{--background-color-base:transparent!important}html,body,.mw-page-container,.mw-page-container-inner{background:transparent!important}.hatnote,.dablink,.rellink{--background-color-interactive-subtle:transparent!important;background:none!important}';
        (fd.head || fd.documentElement).appendChild(st);
      }
      f.lbTidy = null; try { f.lbTidy = tidyArticle(fd) } catch { }   // the article still reads as it came if this fails
      const fw = f.contentWindow;
      f.lbName = null;
      if (y && shown === null) restoreScroll(current, y, fw);   // Back to this article: its place, once (a link followed inside the frame starts at its top)
      const loc = f.contentWindow.location.pathname, t = fd.title || '';
      const m = /^\/zim\/([^/]+)\/(.*)$/.exec(loc); if (!m) return;
      const p = decodeURIComponent(m[1]) + '/' + m[2].split('/').map(decodeURIComponent).join('/');
      const href = '#/wiki/' + p.split('/').map(encodeURIComponent).join('/');
      const own = fd.querySelector('#firstHeading, h1'), raw = (own && own.textContent.trim()) || t;
      if (!m[2] && !raw) return;   // the bare address, on its way to the front page
      const front = decodeURIComponent(loc) === await mainPage;   // the front page is named by its file, such as App/IntroPage: the encyclopedia's name says it instead
      if (f.contentDocument !== fd) return;
      if (front && own) own.style.setProperty('display', 'none', 'important');   // the skin sets its own display, which the hidden attribute does not beat
      main.classList.toggle('own-title', front);   // then the app's heading names it
      const nt = front ? zimLabel(zim) : raw || p.split('/').pop().replace(/_/g, ' '), sub = front ? tr('wiki.encyclopedia', null, 'Encyclopedia') : zimLabel(zim);
      $('#wtitle').textContent = nt; if ($('#wopen')) $('#wopen').href = loc; setTitle(nt, '', zimLabel(zim));
      f.lbName = !front && own ? { nt, at: own.getBoundingClientRect().bottom + fw.scrollY } : null; barName();
      $('#wsave').innerHTML = saveButton({ key: 'w:' + p, title: nt, href, sub });
      fit();
      if (p !== shown) { shown = p; history.replaceState(null, '', href + (from ? '?from=' + encodeURIComponent(from) : '')); remember({ key: 'w:' + p, title: nt, href, sub }) }
    } catch { }
  });
}
// The address an encyclopedia's bare address leads to (a redirect from the server, a refresh page in the Mac app), asked once
const ZMAIN = {};
const zimMain = zim => ZMAIN[zim] || (ZMAIN[zim] = fetch('/zim/' + encodeURIComponent(zim) + '/').then(async r => {
  let u = r.redirected ? r.url : '';
  if (!u) { const m = /http-equiv=["']?refresh["']?[^>]*url=([^"'>]+)/i.exec(await r.text()); if (m) u = new URL(m[1].replace(/&amp;/g, '&').trim(), r.url).href }
  return u ? decodeURIComponent(new URL(u).pathname) : '';
}).catch(() => ''));
// A table wider than the column scrolls sideways inside its own box (.lb-wide, styled by engine/saved_pages.py), so the article never does.
// The box goes around the table, which keeps its table layout: a table made a scrolling block itself turns its width into a fixed one.
// The box fades at an edge with more to scroll to. A list in a table cell is indented when its bullets would fall outside the cell's edge.
// Only with the server's article look, which carries the box's style; an older server's page stays as it came.
function tidyArticle(fd) {
  const fw = fd.defaultView, root = fd.querySelector('.mw-parser-output') || fd.body;
  if (!root || !fd.getElementById('lb-article') || fd.documentElement.dataset.lbTidy) return;
  fd.documentElement.dataset.lbTidy = '-';   // first, so the tables are measured as they will show (the look then undoes the skin's narrow-page blocks)
  const scrolls = e => { for (let a = e.parentElement; a && a !== root; a = a.parentElement) if (fw.getComputedStyle(a).overflowX !== 'visible') return true; return false };
  const boxes = [];
  // A box beside a float would shrink to the room left there (it scrolls, so nothing holds it open), where the table itself would go below
  // the float: the box is held at least as wide as the table can be made, up to the column. A float wider than the column would hang out on
  // the left, where a box cannot scroll to: in its box it is not floated.
  const wrap = (t, cs) => {
    const box = fd.createElement('div'); box.className = 'lb-wide';
    box.style.margin = `${cs.marginTop} 0 ${cs.marginBottom}`;   // the space above and below, which inside the box would no longer meet its neighbours'
    if (cs.clear !== 'none') box.style.clear = cs.clear;
    t.before(box); box.append(t);
    t.style.setProperty('margin-top', '0', 'important'); t.style.setProperty('margin-bottom', '0', 'important');
    if (cs.float !== 'none') { t.style.setProperty('float', 'none', 'important'); t.style.setProperty('margin-left', '0', 'important'); t.style.setProperty('margin-right', '0', 'important') }
    box.style.width = 'min-content'; const least = box.offsetWidth; box.style.width = '';
    box.style.minWidth = `min(100%, ${least}px)`;
    boxes.push(box); return box;
  };
  for (const t of root.querySelectorAll('table')) {
    if (t.parentElement.closest('table,.lb-wide') || scrolls(t)) continue;   // inside another table, or a box that scrolls already (a navbox)
    const cs = fw.getComputedStyle(t);
    if (cs.position === 'absolute' || cs.position === 'fixed' || (cs.float !== 'none' && t.offsetWidth <= root.clientWidth)) continue;   // a floated box that fits (an infobox) stays beside the text
    wrap(t, cs);
  }
  // Anything else still wider than the column (a bar chart, a box of fixed width, a group set inline) gets a box too, now and after a resize.
  const de = fd.documentElement;
  const rest = () => {
    if (de.scrollWidth <= de.clientWidth + 1) return;
    const cw = root.getBoundingClientRect(), out = e => { const r = e.getBoundingClientRect(); return r.width > 0 && (r.right > cw.right + 1 || r.left < cw.left - 1) };
    const found = [];
    for (const e of root.querySelectorAll('*')) {
      if (!out(e) || e.closest('.lb-wide') || found.some(f => f.contains(e))) continue;
      const p = e.parentElement; if (p !== root && out(p) && !scrolls(e)) continue;   // its parent is the one to box
      if (scrolls(e) || /^(TD|TH|TR|TBODY|THEAD|CAPTION|LI|SPAN|A|B|I|SUP|SUB)$/.test(e.tagName)) continue;
      const cs = fw.getComputedStyle(e); if (cs.position === 'absolute' || cs.position === 'fixed') continue;
      found.push(e);
    }
    found.forEach(e => { const b = wrap(e, fw.getComputedStyle(e)); edge(b); ro.observe(b) });
  };
  for (const li of root.querySelectorAll('table li')) {
    const s = fw.getComputedStyle(li), list = li.parentElement;
    if (s.display !== 'list-item' || s.listStyleType === 'none' || s.listStylePosition !== 'outside' || list.dataset.lbIn) continue;
    const r = li.getBoundingClientRect(), cell = li.closest('td,th'), c = cell ? cell.getBoundingClientRect() : r, m = parseFloat(s.fontSize) * 1.4;
    const rtl = s.direction === 'rtl', room = rtl ? c.right - r.right : r.left - c.left;
    if (room < m) { list.dataset.lbIn = 1; list.style.setProperty(rtl ? 'margin-right' : 'margin-left', `calc(${fw.getComputedStyle(list)[rtl ? 'marginRight' : 'marginLeft']} + ${Math.ceil(m - room)}px)`) }
  }
  const edge = b => {
    const more = b.scrollWidth - b.clientWidth, s = Math.abs(b.scrollLeft), rtl = fw.getComputedStyle(b).direction === 'rtl';
    b.classList.toggle(rtl ? 'lb-l' : 'lb-r', more > 1 && s < more - 1); b.classList.toggle(rtl ? 'lb-r' : 'lb-l', more > 1 && s > 1);
  };
  const ro = new fw.ResizeObserver(es => es.forEach(e => edge(e.target.closest('.lb-wide'))));
  boxes.forEach(b => { edge(b); ro.observe(b); ro.observe(b.firstElementChild) });   // as a box scrolls, wiki() calls edge (it reads the scroll, see there)
  // What is left of the web page's machinery, which reads as a broken page offline: editing links where the link itself was taken out
  // ('(edit it)', '[edit on Wikidata]'), a template's styles error, a chart's source where the chart would be, an empty paragraph
  // holding only a line break (a gap under the title), and a note's mark written out as its counter ('[lower-alpha 1]' for '[a]').
  const tw = fd.createTreeWalker(root, NodeFilter.SHOW_TEXT, { acceptNode: n => /edit|<graph|content model|-alpha|-roman/i.test(n.data) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP });
  const gone = [], ab = n => { let s = ''; for (n++; n > 0; n = Math.floor((n - 1) / 26)) s = String.fromCharCode(97 + (n - 1) % 26) + s; return s };
  for (let n; (n = tw.nextNode());) {
    const e = n.parentElement; if (!e || e === root) continue;
    const t = e.textContent.trim();
    if (/^[[(]\s*edit(\s+it|\s+on\s+wikidata)?\s*[\])]$/i.test(t) || (e.matches('.error') && /must have content model/.test(t))) gone.push(e);
    else if (/^<graph>[\s\S]*<\/graph>$/.test(t)) gone.push(e);
    else if (/<graph>[\s\S]*?<\/graph>/.test(n.data)) n.data = n.data.replace(/<graph>[\s\S]*?<\/graph>/g, '');
    else if (e.closest('sup.reference')) { const m = /^(lower|upper)-(alpha|roman) (\d+)$/.exec(n.data.trim()); if (m) { const k = +m[3], s = m[2] === 'alpha' ? ab(k - 1) : roman(k); n.data = m[1] === 'upper' ? s.toUpperCase() : s } }
  }
  for (const p of root.querySelectorAll('p')) if (!p.textContent.trim() && !p.querySelector('img,svg,video,audio,iframe,input,math,object')) gone.push(p);
  gone.forEach(e => e.style.setProperty('display', 'none', 'important'));
  rest(); let rt = 0; new fw.ResizeObserver(() => { clearTimeout(rt); rt = setTimeout(rest, 200) }).observe(root);
  fd.documentElement.dataset.lbTidy = boxes.length;
  return { boxes, edge };   // boxes: also those rest() adds later
}
const roman = n => { let s = ''; for (const [v, r] of [[1000, 'm'], [900, 'cm'], [500, 'd'], [400, 'cd'], [100, 'c'], [90, 'xc'], [50, 'l'], [40, 'xl'], [10, 'x'], [9, 'ix'], [5, 'v'], [4, 'iv'], [1, 'i']]) for (; n >= v; n -= v) s += r; return s };
// The article's stylesheet (engine/saved_pages.py) reads these: the window's text colours and its accent, which only this page knows
// (the system accent in the apps, Lastbook green in a browser).
function lookOf(fd) {
  const cs = getComputedStyle(html), r = fd.documentElement.style;
  const probe = document.createElement('i'); probe.style.color = 'var(--accent)'; probe.hidden = true; document.body.append(probe);
  r.setProperty('--lb-link', getComputedStyle(probe).color); probe.remove();
  for (const [k, v] of [['--lb-ink', '--ink'], ['--lb-ink2', '--ink2'], ['--lb-line', '--line2'], ['--lb-font', '--font'], ['--lb-display', '--display']]) { const x = cs.getPropertyValue(v).trim(); if (x) r.setProperty(k, x) }
}
const ZIMS = [
  ['mdwiki_en_all_maxi_2025-11.zim', () => tr('wiki.medical', null, 'Medical encyclopedia'), () => tr('wiki.mdwikiAbout', null, 'MDWiki: plain-language articles on conditions, medicines and first aid.'), 'health'],
  ['wikibooks_en_all_maxi_2026-04.zim', () => tr('wiki.wikibooks', null, 'Wikibooks — how-to textbooks'), () => tr('wiki.wikibooksAbout', null, 'Open textbooks and how-to manuals, from cooking to electronics.'), 'book'],
  ['appropedia_en_all_maxi_2026-02.zim', () => tr('wiki.appropedia', null, 'Appropedia — appropriate technology'), () => tr('wiki.appropediaAbout', null, 'Appropriate technology: water, sanitation, energy and building projects.'), 'repair'],
  ['wikipedia_en_all_nopic_2026-06.zim', () => tr('wiki.wikipedia', null, 'Wikipedia (text only)'), () => tr('wiki.wikipediaAbout', null, 'The full English encyclopedia, text only (no pictures).'), 'wiki'],
];
const zimTitle = z => z[1]();
const zimAbout = z => z[2]();
const zimsHere = async () => { const here = (await libInfo()).zims; return here ? ZIMS.filter(z => here.includes(z[0])) : ZIMS };
async function encyclopedias(q) {
  setUiTitle('wiki.title', tr('wiki.title', null, 'Encyclopedias'));
  const zims = await zimsHere();
  if (!zims.length) { main.innerHTML = `<h1>${tr('wiki.title', null, 'Encyclopedias')}</h1><p class="lead">${tr('wiki.noneHere', null, 'This download has no encyclopedias.')}</p>`; return }
  main.innerHTML = `<h1>${tr('wiki.title', null, 'Encyclopedias')}</h1><p class="lead">${['', tr('wiki.one', null, 'One complete encyclopedia'), tr('wiki.two', null, 'Two complete encyclopedias'), tr('wiki.three', null, 'Three complete encyclopedias'), tr('wiki.four', null, 'Four complete encyclopedias')][zims.length]}. ${tr('wiki.communitySafetyNotice', null, 'Community-written: good for background — use the guides’ manuals for safety-critical steps.')}</p>
  <div style="margin:16px 0">${searchBox('zq', q, 'e.g. tetanus, solar panel, sourdough')}</div><div id="zres"></div>
  ${secHead(tr('wiki.openOne', null, 'Open one'))}<div class="cards2">${zims.map(z => `<a class="card" href="#/wiki/${z[0]}/?from=${encodeURIComponent('#/encyclopedias')}"><span class="ico">${ico(z[3])}</span><b>${esc(zimTitle(z))}</b><small>${esc(zimAbout(z))}</small></a>`).join('')}</div>`;
  $('#zqF').addEventListener('submit', e => { e.preventDefault(); location.hash = '#/encyclopedias?q=' + encodeURIComponent($('#zq').value.trim()) });
  if (q) zimResults(q, $('#zres'), 40);
}
// heading: part of a wider search, shown under that heading only when something matched. Answers whether anything did.
async function zimResults(q, el, max = 8, heading = '') {
  el.innerHTML = heading ? '' : `<p class="loading">${esc(tr('search.encyclopediasLoading', null, 'Searching the encyclopedias…'))}</p>`;
  try {
    const hits = await api('/api/collection-search?q=' + encodeURIComponent(q));
    if (!hits.length) { el.innerHTML = heading ? '' : `<div class="empty"><span class="e-ico">${ico('wiki')}</span><b>${tr('wiki.noArticles', null, 'No articles found')}</b><p>${tr('wiki.tryAnother', null, 'Try another word for the same thing.')}</p></div>`; return false }
    const ord = ['mdwiki', 'wikibooks', 'appropedia', 'wikipedia'];
    hits.sort((a, b) => ord.findIndex(k => a.collection.startsWith(k)) - ord.findIndex(k => b.collection.startsWith(k)));
    el.innerHTML = `${heading ? `<h2>${heading}</h2>` : ''}<ul class="list">${hits.slice(0, max).map(h => `<li><a class="row" href="#/wiki/${esc(h.path.replace(/^zim\//, ''))}?${fromQ()}"><span class="k">${ico('wiki')}</span><span><b>${esc(h.title)}</b><small>${esc(zimLabel(h.collection))}</small></span></a></li>`).join('')}</ul>`;
    return true;
  } catch (e) { el.innerHTML = heading ? '' : `<p class="muted">${esc(tr('wiki.searchUnavailable', { error: e.message }, 'Encyclopedia search isn’t available right now ({error}).'))}</p>`; return false }
}

/* ------------------------------------------------------------- search -- */
// A guide word only has to start with a search word, so she, her and his would find shelter, here and hissing.
const QSTOP = new Set('a an and are can do does for from get got have how i if in is it its me my need no not of on or our so that the this to was we what when where which who why will with without you your won don can t s she her hers his him'.split(' '));
// Words are split, folded and matched by web/words.js (loaded first), so accents, Chinese and other scripts work.
const SEARCH_EXAMPLE_QUERIES = [
  ['search.ex.boilWater', 'boil water'],
  ['search.ex.cutBleeding', 'cut won’t stop bleeding'],
  ['search.ex.fridgePower', 'fridge after power cut'],
  ['search.ex.burn', 'burn'],
  ['search.ex.toilet', 'toilet not working'],
  ['search.ex.smellGas', 'smell gas'],
  ['search.ex.cleanWater', 'clean drinking water'],
  ['search.ex.brokenLeg', 'broken leg'],
  ['search.ex.carbonMonoxide', 'carbon monoxide'],
  ['search.ex.keepFoodCold', 'keep food cold'],
  ['search.ex.hamRadio', 'ham radio license'],
  ['search.ex.plantPotatoes', 'plant potatoes'],
  ['search.ex.sharpenKnife', 'sharpen a knife'],
  ['search.ex.diarrheaChild', 'diarrhea in a child'],
];
function searchContentQuery(q) {
  const normalized = String(q || '').normalize('NFC').trim().toLowerCase();
  const match = SEARCH_EXAMPLE_QUERIES.find(([key, english]) =>
    String(tr(key, null, english)).normalize('NFC').trim().toLowerCase() === normalized);
  return match ? match[1] : q;
}
function topicMatches(q) {
  return typeof SearchWords === 'undefined' ? [] : SearchWords.rankTopics(q, TOPICS, QSTOP);
}
let searchSeq = 0;
async function searchPage(q, kind) {
  setTitle(q ? tr('search.pageTitle', { query: q }, 'Search: {query}') : tr('search.label', null, 'Search'));
  const kinds = [['all', tr('search.everything', null, 'Everything')], ['read', tr('search.manuals', null, 'Manuals & pages')], ['video', tr('videos.title', null, 'Videos')], ['wiki', tr('wiki.title', null, 'Encyclopedias')]];
  main.innerHTML = `<h1>${q ? tr('search.resultsHeading', null, 'Results') : tr('search.label', null, 'Search')}</h1>
  ${searchBox('searchQ', q, tr('search.everyday', null, 'Describe it in everyday words'))}
  <div class="chips" role="group" aria-label="${tr('search.show', null, "Show")}" style="margin-top:12px" id="kinds">${kinds.map(([k, l]) => `<a class="chip ${k === kind ? 'on' : ''}" aria-pressed="${k === kind}" data-kind="${k}" href="#/search?q=${encodeURIComponent(q)}&kind=${k}">${l}</a>`).join('')}</div>
  <div id="sask"></div><div id="sout"></div>`;
  i18n?.apply(main);
  const input = $('#searchQ');
  $('#searchQF').addEventListener('submit', e => { e.preventDefault(); input.blur(); go(input.value.trim(), true) });
  let tmr;
  input.addEventListener('input', () => { clearTimeout(tmr); tmr = setTimeout(() => go(input.value.trim(), false), 350) });
  // as-you-type: update results and the address; a new search is one new history entry, not one per keystroke
  let fresh = true;   // the next change starts a new entry
  function go(nq, commit) {
    const h = '#/search?q=' + encodeURIComponent(nq) + (kind !== 'all' ? '&kind=' + kind : '');
    if (nq === q) { if (commit) fresh = true; return }
    if (fresh) pushHere(h); else history.replaceState(null, '', h);
    fresh = !!commit; q = nq; if (input.value !== nq) input.value = nq;
    $$('#kinds a').forEach(a => a.href = `#/search?q=${encodeURIComponent(nq)}&kind=${a.dataset.kind}`);
    askOffer(nq); results(nq, kind);
  }
  searchLive = (nq, commit, typing) => { clearTimeout(tmr); if (typing) tmr = setTimeout(() => go(nq, false), 350); else go(nq, commit) };
  setTimeout(() => { $('#topQ').value = q }, 0);   // after the router clears it: on Windows the pane's field is this page's field
  askOffer(q); results(q, kind);
  if (!q) setTimeout(() => findBox().focus(), 50);
}
function askOffer(q) {
  const el = $('#sask'); if (!el) return;
  el.innerHTML = q && q.split(/\s+/).length >= 2 ? `<a class="ghit" href="#/ask?q=${encodeURIComponent(q)}" style="--tc:var(--accent)"><span class="ico">${ico('ask')}</span><span><b>${esc(tr('search.askQuoted', { query: q }, 'Ask the library: “{query}”'))}</b><small>${esc(tr('search.askHint', null, 'Get a written answer with the exact pages it came from'))}</small></span></a>` : '';
}
async function results(q, kind) {
  const seq = ++searchSeq, out = $('#sout');
  const contentQuery = searchContentQuery(q);
  if (!q) {
    out.innerHTML = `<p class="muted" style="margin-top:18px">${trLang('search.friendWords', null, 'Use the words you’d use with a friend. For example:')}</p><div class="chips wrapchips">${[tr('search.ex.cleanWater', null, 'clean drinking water'), tr('search.ex.brokenLeg', null, 'broken leg'), tr('search.ex.carbonMonoxide', null, 'carbon monoxide'), tr('search.ex.keepFoodCold', null, 'keep food cold'), tr('search.ex.hamRadio', null, 'ham radio license'), tr('search.ex.plantPotatoes', null, 'plant potatoes'), tr('search.ex.sharpenKnife', null, 'sharpen a knife'), tr('search.ex.diarrheaChild', null, 'diarrhea in a child')].map(x => `<a class="chip" href="#/search?q=${encodeURIComponent(x)}">${esc(x)}</a>`).join('')}</div>`;
    return;
  }
  const g = kind === 'all' ? topicMatches(contentQuery) : [];
  out.innerHTML = `${g.length ? `<h2>${tr('search.startWithGuide', null, 'Start with a guide')}</h2>${g.map(({ t, c }) => `<a class="ghit" href="#/t/${t.id}${c ? '/' + c.id : ''}" ${tcStyle(t.id)}><span class="ico">${ico(t.id)}</span><span><b>${topicLabelHtml(t.id, 'title', t.title)}${c ? ' — ' + esc(c.label) : ''}</b><small>${tr('search.pickedPagesSafety', null, 'Picked pages with exact page numbers and safety limits')}</small></span></a>`).join('')}` : ''}
    <div id="spass"></div><div id="svid"></div><div id="sres"></div><div id="szim"></div>`;
  if (kind === 'wiki') return zimResults(contentQuery, $('#szim'), 40);
  // Each part answers whether it found anything; "nothing matched" shows once, only when none did.
  const parts = kind === 'all' || kind === 'read' ? [passages(contentQuery, seq)] : [];
  const reqs = [api('/api/find?q=' + encodeURIComponent(contentQuery) + '&kind=' + (kind === 'video' ? 'video' : 'read'))];
  if (kind === 'all') reqs.push(api('/api/find?q=' + encodeURIComponent(contentQuery) + '&kind=video').catch(() => null));
  $('#sres').innerHTML = `<p class="loading">${esc(tr('search.searching', null, 'Searching…'))}</p>`;
  const found = (async () => {
    try {
      const [d, vd] = await Promise.all(reqs);
      if (seq !== searchSeq) return true;
      const vids = (kind === 'video' ? d : vd)?.results || [];
      if (kind === 'video') { $('#sres').innerHTML = vids.length ? `<div class="vgrid" style="margin-top:14px">${vids.map(r => vcard(r)).join('')}</div>` : ''; return vids.length > 0 }
      if (vids.length) { $('#svid').innerHTML = secHead(tr('nav.videos', null, 'Videos'), '', `<a href="#/search?q=${encodeURIComponent(q)}&kind=video">${esc(tr('search.seeAll', null, 'See all'))}</a>`) + rail(vids.slice(0, 10).map(r => vcard(r)).join('')); translateRendered($('#svid')); wireRails($('#svid')) }
      $('#sres').innerHTML = d.results.length ? `<h2>${esc(tr('search.inManuals', null, 'In the manuals and saved pages'))}</h2>
        ${d.expanded.length ? `<p class="small muted">${esc(tr('search.alsoLookedFor', { terms: d.expanded.slice(0, 10).join(', ') }, 'Also looked for: {terms}'))}${d.mode === 'some words' ? ' · ' + esc(tr('search.someWords', null, 'showing pages with some of your words')) : ''}</p>` : ''}
        <div class="results">${d.results.map(resultCard).join('')}</div>` : '';
      return d.results.length + vids.length > 0;
    } catch (e) { if (seq === searchSeq) $('#sres').innerHTML = errorBox(e, tr('search.notResponding', null, 'Search isn’t responding.')) + `<p class="small muted">${esc(tr('search.indexBusy', null, 'The library may be busy rebuilding its index. Try again in a minute.'))}</p>`; return true }
  })();
  parts.push(found);
  if (kind === 'all') parts.push(found.then(() => seq === searchSeq && zimResults(contentQuery, $('#szim'), 6, tr('search.inEncyclopedias', null, 'In the encyclopedias'))));
  const any = (await Promise.all(parts)).some(Boolean);
  if (seq === searchSeq && !g.length && !any) { $('#sres').innerHTML = emptySearch(q); offerNote(q) }
}
// Most relevant pages from the shared keyword + meaning-based retriever (the same one the assistant uses).
async function passages(q, seq) {
  try {
    const d = await api('/api/retrieve?q=' + encodeURIComponent(q) + '&k=6&kind=manual');
    if (seq !== searchSeq || !d.results.length || !$('#spass')) return false;
    $('#spass').innerHTML = secHead(tr('search.mostRelevant', null, 'Most relevant pages'), d.semantic && !d.semantic.chunks ? tr('search.matchedWords', null, 'Matched by your words') : tr('search.matchedMeaning', null, 'Matched by meaning as well as by words')) + `<div class="rcards">${d.results.map(r => rcard({ src: { id: r.doc_id, kind: r.kind, title: r.title, publisher: r.publisher, year: r.year, pages: r.pages, trust: r.trust }, page: r.page, label: r.title, note: (r.excerpt || '').slice(0, 220) + '…' })).join('')}</div>`;
    return true;
  } catch { return false }
}
const emptySearch = q => `<div class="empty"><span class="e-ico">${ico('search')}</span><b>${esc(tr('search.noResults', { query: q }, 'No results for “{query}”'))}</b><p>${esc(tr('search.tryFewer', null, 'Try fewer words, or another word for the same thing.'))}</p><div id="noteOffer"></div></div>`;
/* Things I couldn't find (#116, engine/notes.py): when a search finds nothing, the person may keep a note of it, on this computer
   only. Nothing is kept unless they press the button. The engine answers only this computer, so elsewhere nothing is offered. */
let notesOpen = null;
const notesHere = () => notesOpen || (notesOpen = api('/api/not-found').then(() => true, () => { notesOpen = null; return false }));
function guideBefore() {   // the guide the person searched from, if any: the page before this run of searches
  for (let i = navAt - 1; i >= 0; i--) {
    const h = navStack[i] || '';
    if (h.startsWith('#/search')) continue;
    const m = h.match(/^#\/t\/([^/?]+)/);
    return m ? decodeURIComponent(m[1]) : null;
  }
  return null;
}
async function offerNote(q) {
  if (!(await notesHere())) return;
  const el = $('#noteOffer'); if (!el || !q) return;
  const guide = guideBefore(), t = guide && topicById(guide);
  const missLink = `<a href="#/not-found">${esc(tr('library.notFound', null, 'Things I couldn’t find'))}</a>`;
  el.innerHTML = `<p class="e-act"><button class="btn plain" id="keepNote">${esc(tr('search.keepNote', null, 'Keep a note of this'))}</button></p>
    <p class="small muted">${t
      ? tr('search.saveMissGuideWithLink', { query: esc(q), guide: esc(shortName(t.id) || t.title), link: missLink }, 'Saves “{query}” and the {guide} guide on this computer only, under Library → {link}. Nothing is sent anywhere.')
      : tr('search.saveMissWithLink', { query: esc(q), link: missLink }, 'Saves “{query}” on this computer only, under Library → {link}. Nothing is sent anywhere.')}</p>`;
  $('#keepNote').onclick = async () => {
    const b = $('#keepNote'); b.disabled = true;
    try {
      await api('/api/not-found', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ words: q, guide }) });
      el.innerHTML = `<p class="small" role="status">${tr('notes.keptInLibrary', { link: missLink }, 'Kept. It’s in Library → {link}, where you can delete it.')}</p>`;
    } catch (e) { b.disabled = false; el.insertAdjacentHTML('beforeend', `<p class="small" role="alert">${esc(e.message)}</p>`) }
  };
}
function resultCard(r) {
  const base = { src: r };
  let language = '';
  for (const candidate of [r.language, r.lang]) {
    if (typeof candidate !== 'string') continue;
    try { language = Intl.getCanonicalLocales(candidate)[0] || ''; } catch { language = ''; }
    if (language) break;
  }
  return `<article class="result"${language ? ` lang="${esc(language)}"` : ''}><h3><a href="${hrefFor({ ...base, page: r.hits[0] && r.hits[0].page })}">${esc(r.title)}</a></h3>
    <div class="rsrc">${srcText(r)} · ${esc(r.trust)}</div>
    ${r.hits.slice(0, 2).map(h => `<a class="hit" href="${hrefFor({ ...base, page: h.page })}">${h.page ? `<b>${esc(tr('reader.pagePrefix', { page: h.page }, 'Page {page}'))}:</b> ` : ''}${h.snippet}</a>`).join('')}</article>`;
}

/* ------------------------------------------------------------ library -- */
async function library() {
  setUiTitle('library.title', tr('library.title', null, 'Library'));
  const saved = store.get('saved', []).length, chats = (window.Chat ? Chat.count() : 0);
  const zims = await zimsHere();
  main.innerHTML = `<h1 data-i18n="library.title">Library</h1><p class="lead" data-i18n="library.lead">Your saved things, learning routes, encyclopedias and every manual in the collection.</p>
  <div class="cards2 three" style="margin-top:16px">
    <a class="card" href="#/saved"><span class="ico">${ico('save')}</span><b data-i18n="nav.saved">Saved</b><small>${saved ? esc(tr('library.savedCount', { count: saved }, '{count} saved items on this device')) : tr('library.savedEmpty', null, 'Pages, videos and answers you keep on this device')}</small></a>
    <a class="card" href="#/ask"><span class="ico">${ico('ask')}</span><b data-i18n="library.chats">Chats</b><small>${chats ? esc(tr('library.chatsCount', { count: chats }, '{count} saved conversations')) : tr('library.chatsEmpty', null, 'Ask the library a question')}</small></a>
    <a class="card" href="#/prepare"><span class="ico">${ico('prep')}</span><b data-i18n="library.prepare">Prepare your household</b><small data-i18n="library.prepareCard">Getting-ready readings from every guide</small></a>
    <a class="card" href="#/not-found" id="nfCard" hidden><span class="ico">${ico('search')}</span><b data-i18n="library.notFound">Things I couldn’t find</b><small id="nfCount" data-i18n="library.notFoundEmpty">Notes you kept when a search found nothing</small></a>
  </div>
  ${secHead(`<span data-i18n="home.learnSkill">Learn a skill</span>`, `<span data-i18n="library.learnLead">Step-by-step routes that start simple</span>`)}
  <div class="needs">${learnTopics().map(t => `<a class="need" href="#/t/${t.id}" ${tcStyle(t.id)}><span class="ico">${ico(t.id)}</span><b>${topicLabelHtml(t.id, 'title', t.title)}</b><small>${topicLabelHtml(t.id, 'short', t.short || '')} · ${tr('guide.stepCount', { count: (t.route || []).length }, '{count} steps')}</small></a>`).join('')}</div>
  ${zims.length ? secHead(`<span data-i18n="wiki.title">Encyclopedias</span>`, `<span data-i18n="library.encyclopediasLead">Complete offline copies</span>`, `<a href="#/encyclopedias" data-i18n="library.searchThem">Search them</a>`) + `<div class="cards2">${zims.map(z => `<a class="card" href="#/wiki/${z[0]}/?from=${encodeURIComponent('#/library')}"><span class="ico">${ico(z[3])}</span><b>${esc(zimTitle(z))}</b><small>${esc(zimAbout(z))}</small></a>`).join('')}</div>` : ''}
  ${secHead(`<span data-i18n="library.browseSubject">Browse by subject</span>`, `<span data-i18n="library.browseLead">Every manual, saved web page and video</span>`)}<div id="shelves"><p class="loading" data-i18n="common.loading">Loading…</p></div>
  <p style="margin-top:20px"><a href="#/about" data-i18n="library.aboutLink">About this library and its sources</a>${IN_WINDOW ? ' · <a href="/ui/setup.html#manage">Library and local AI</a>' : ''}</p>`;
  if (await notesHere()) api('/api/not-found').then(d => {
    const c = $('#nfCard'); if (!c) return;
    c.hidden = false;
    if (d.notes.length) $('#nfCount').innerHTML = trLang('notes.countOnDevice', { count: d.notes.length }, '{count} notes on this computer');
  }).catch(() => { });
  try {
    const sh = await api('/api/shelves');
    $('#shelves').innerHTML = sh.filter(s => s.read + s.video).map(s => `<a class="shelfrow" href="#/shelf/${s.id}"><span><b>${esc(s.title)}</b><small>${s.read ? s.read.toLocaleString() + ' to read' : ''}${s.read && s.video ? ' · ' : ''}${s.video ? s.video.toLocaleString() + ' videos' : ''}</small></span>${ico('right')}</a>`).join('');
  } catch (e) { $('#shelves').innerHTML = errorBox(e) }
}
async function prepareHub() {
  setUiTitle('library.prepare', tr('library.prepare', null, 'Prepare your household'));
  const list = nowTopics().filter(t => (t.prepare || []).length);
  main.innerHTML = `<h1 data-i18n="library.prepare">Prepare your household</h1>
  <p class="lead" data-i18n="library.prepareLead">Readings for getting ready before water, power or services stop — gathered from each guide. One area at a time.</p>
  <div class="notice" data-i18n="library.prepareNotice">A shopping list or cart isn’t the same as supplies you own, and reading isn’t the same as a practised plan.</div>
  ${list.map(t => `<details class="more" ${tcStyle(t.id)}><summary><span class="prep-ico">${ico(t.id)}</span><span>${topicLabelHtml(t.id, 'title', t.title)} <span class="n">· ${t.prepare.length}</span></span></summary><div class="body"><ul class="list">${t.prepare.map(i => rowItem({ ...i, preview: true })).join('')}</ul><p><a href="#/t/${t.id}">${esc(tr('library.openFullGuide', null, 'Open the full guide'))}</a></p></div></details>`).join('')}`;
}
async function shelfPage(id, kind, q) {
  const sh = (await api('/api/shelves')).find(s => s.id === id);
  if (!sh) return notFound();
  setTitle(sh.title);
  main.innerHTML = `${backButton('#/library')}${crumbs([[tr('nav.library', null, 'Library'), '#/library'], [sh.title]])}<h1>${esc(sh.title)}</h1>
  <div style="margin:14px 0 10px">${searchBox('shq', q, tr('library.filterShelf', null, 'Filter by title or publisher'), ['search.filter', tr('search.filter', null, 'Filter')])}</div>
  <div class="chips">${[['all', tr('library.everything', null, 'Everything')], ['read', tr('library.toReadFilter', null, 'To read')], ['video', tr('nav.videos', null, 'Videos')]].map(([k, l]) => `<a class="chip ${k === kind ? 'on' : ''}" href="#/shelf/${id}?kind=${k}&q=${encodeURIComponent(q)}">${l}</a>`).join('')}</div><div id="shres"><p class="loading" data-i18n="common.loading">Loading…</p></div>`;
  $('#shqF').addEventListener('submit', e => { e.preventDefault(); location.hash = `#/shelf/${id}?kind=${kind}&q=` + encodeURIComponent($('#shq').value.trim()) });
  let off = 0;
  const load = async () => {
    const d = await api(`/api/shelf/${id}?kind=${kind}&q=${encodeURIComponent(q)}&offset=${off}`);
    const html = d.collections.map(c => `<section class="collection"><h3>${esc(c.collection)}</h3><div class="small muted">${esc(c.trust)} · ${tr('library.itemCount', { count: c.count }, '{count} items')}</div><ul class="list">${c.items.map(r => rowItem({ src: r })).join('')}</ul>${c.count > c.items.length ? `<a class="btn ghost" href="#/collection?name=${encodeURIComponent(c.collection)}&${fromQ()}">${tr('library.seeAllCount', { count: c.count }, 'See all {count}')}</a>` : ''}</section>`).join('');
    if (!off) $('#shres').innerHTML = d.collections.length ? '' : `<div class="empty">${esc(tr('library.nothingMatches', null, 'Nothing here matches. Try another word.'))}</div>`;
    $('#shres').insertAdjacentHTML('beforeend', html);
    $('#moreb')?.remove();
    if (d.more) { $('#shres').insertAdjacentHTML('beforeend', `<p><button class="btn plain" id="moreb">${esc(tr('common.showMore', null, 'Show more'))}</button></p>`); $('#moreb').onclick = () => { off += 40; load() } }
  };
  await load();
}
async function collectionPage(name, from) {
  setTitle(name);
  main.innerHTML = `<div>${backButton(from, ['nav.library', tr('nav.library', null, 'Library')])}</div><h1 style="margin-top:12px">${esc(name)}</h1><ul class="list collection" id="cl"></ul><div id="cm"></div>`;
  let off = 0;
  const load = async () => {
    const d = await api('/api/collection?name=' + encodeURIComponent(name) + '&offset=' + off);
    $('#cl').insertAdjacentHTML('beforeend', d.items.map(r => rowItem({ src: r })).join(''));
    $('#cm').innerHTML = d.more ? `<button class="btn plain" id="cmb">${esc(tr('common.showMore', null, 'Show more'))}</button>` : '';
    if (d.more) $('#cmb').onclick = () => { off += 60; load() };
  };
  await load();
}

/* -------------------------------------------------------------- saved -- */
async function savedPage() {
  const tr = (k, p, f) => { const fill = (s) => (!p || s == null) ? s : String(s).replace(/\{([A-Za-z_][A-Za-z0-9_]*)\}/g, (m, n) => (p[n] != null ? p[n] : m)); return fill(typeof globalThis.lastbookTr === 'function' ? globalThis.lastbookTr(k, p, f) : f); };
  if (typeof setUiTitle === 'function') setUiTitle('nav.saved', tr('nav.saved', null, 'Saved')); else setTitle(tr('nav.saved', null, 'Saved'));
  let all = [], savedError = '';
  try { all = VideoMoments.readSaved() } catch (e) { savedError = e.message }
  const moments = all.filter(VideoMoments.isMoment);
  const s = all.filter(x => x && x.kind !== 'video-moment'), r = await recents();
  const li = x => `<li><a class="row" href="${esc(x.href)}"><span class="k">${ico(x.key[0] === 'v' ? 'video' : x.key[0] === 'w' ? 'wiki' : x.key[0] === 't' ? 'book' : x.key[0] === 'a' ? 'ask' : 'page')}</span><span><b>${esc(x.title)}</b><small>${esc(rowSub(x))}</small></span></a></li>`;
  const cont = await resumable();
  const available = new Set(await held([...new Set(moments.map(x => x.videoId))]));
  main.innerHTML = `<h1 data-i18n="nav.saved">${esc(tr('nav.saved', null, 'Saved'))}</h1><p class="lead" data-i18n="saved.keptOnDevice">${esc(tr('saved.keptOnDevice', null, 'Kept on this device only.'))}</p>
  ${savedError ? `<div class="err" role="alert">${esc(savedError)}</div>` : moments.length ? momentSection() : ''}
  ${s.length ? `<div class="collection" style="margin-top:18px"><ul class="list">${s.map(li).join('')}</ul></div>` : !moments.length && !savedError ? `<div class="empty"><span class="e-ico">${ico('save')}</span><b>${tr('saved.nothingYet', null, 'Nothing saved yet')}</b><p>${tr('saved.chooseSaveHint', null, 'Choose Save on any page, video, article or answer to keep it here.')}</p></div>` : ''}
  ${cont.length ? secHead(`<span data-i18n="videos.continue">Continue watching</span>`) + rail(cont.map(([id, v]) => vcard({ id, title: v.title, thumb: v.thumb, duration: v.d }, { sub: tr('home.resumeAt', { time: clock(v.t) }, 'Resume at {time}') })).join('')) : ''}
  ${secHead(tr('library.recentlyOpened', null, 'Recently opened'))}${r.length ? `<div class="collection"><ul class="list">${r.map(li).join('')}</ul></div><p><button class="btn plain" id="clr">${tr('saved.clearRecent', null, 'Clear recent list')}</button></p>` : `<div class="empty"><p>${tr('saved.recentEmpty', null, 'Pages you open will appear here.')}</p></div>`}`;
  if (moments.length) wireMoments({ available });
  const c = $('#clr'); if (c) c.onclick = () => { store.set('recent', []); savedPage() };
}

// Library → Things I couldn't find: the person's own notes, each with Delete, and Delete all (asked first)
async function notFoundPage(confirmAll) {
  setUiTitle('library.notFound', tr('library.notFound', null, 'Things I couldn’t find'));
  let notes;
  try { notes = (await api('/api/not-found')).notes } catch (e) {
    main.innerHTML = `<h1>${esc(tr('library.notFound', null, 'Things I couldn’t find'))}</h1>${errorBox(e)}`; return }
  const day = s => { const d = new Date(s + 'T12:00:00'); return isNaN(d) ? s : (i18n?.date?.(d, { day: 'numeric', month: 'long', year: 'numeric' }) ?? d.toLocaleDateString(undefined, { day: 'numeric', month: 'long', year: 'numeric' })) };
  const li = n => { const t = n.guide && topicById(n.guide);
    return `<li class="row nf"><span class="k">${ico('search')}</span><span><b>“${esc(n.words)}”</b><small>${t ? esc(tr('notes.fromGuide', { guide: shortName(t.id) || t.title }, 'From the {guide} guide')) + ' · ' : ''}${esc(day(n.at))}</small></span><button class="btn plain" data-del="${esc(n.id)}" aria-label="${esc(tr('notes.deleteNamed', { words: n.words }, 'Delete the note “{words}”'))}">${esc(tr('notes.delete', null, 'Delete'))}</button></li>` };
  main.innerHTML = `<h1>${esc(tr('library.notFound', null, 'Things I couldn’t find'))}</h1><p class="lead">${esc(tr('notes.lead', null, 'Notes you chose to keep when a search found nothing. They stay on this computer, and nothing is sent anywhere.'))}</p>
    ${notes.length ? `<div class="collection" style="margin-top:18px"><ul class="list">${notes.slice().reverse().map(li).join('')}</ul></div>
      <p>${confirmAll ? `<span>${notes.length === 1 ? tr('notes.deleteOne', null, 'Delete this note?') : tr('notes.deleteAllCount', { count: notes.length }, 'Delete all {count} notes?')}</span> <button class="btn danger" id="nfYes">${esc(tr('notes.deleteAll', null, 'Delete all'))}</button> <button class="btn plain" id="nfNo">${esc(tr('notes.keepThem', null, 'Keep them'))}</button>` : `<button class="btn plain" id="nfAll">${esc(tr('notes.deleteAll', null, 'Delete all'))}</button>`}</p>`
      : `<div class="empty"><span class="e-ico">${ico('search')}</span><b>${esc(tr('notes.noneTitle', null, 'No notes'))}</b><p>${esc(tr('notes.noneHint', null, 'When a search finds nothing, you can keep a note of it here, to remember what the library was missing.'))}</p></div>`}`;
  $$('[data-del]', main).forEach(b => b.onclick = async () => {
    b.disabled = true;
    try { await api('/api/not-found/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: b.dataset.del }) }) } catch { }
    await notFoundPage(); const f = $('[data-del]', main) || $('h1', main); if (f) f.focus();
  });
  if ($('#nfAll')) $('#nfAll').onclick = async () => { await notFoundPage(true); $('#nfNo').focus() };
  if ($('#nfNo')) $('#nfNo').onclick = async () => { await notFoundPage(); $('#nfAll').focus() };
  if ($('#nfYes')) $('#nfYes').onclick = async () => {
    try { await api('/api/not-found/delete-all', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' }) } catch { }
    await notFoundPage();
  };
}

/* -------------------------------------------------------------- about -- */
// What the assistant cannot read, as a sentence: counts of none are left out, and one is one
const many = (n, one, more) => `${n.toLocaleString()} ${n === 1 ? one : more}`;
function blind(c) {
  if (!c) return '';
  const nv = c.videos - c.videos_with_text, parts = [];
  if (nv) parts.push(tr(nv === 1 ? 'about.blind.noCaptionsOne' : 'about.blind.noCaptions', { count: nv.toLocaleString(), total: many(c.videos, tr('common.video', null, 'video'), tr('nav.videos', null, 'Videos').toLowerCase()) }, nv === 1 ? '{count} of {total} video has no captions or transcript' : '{count} of {total} videos have no captions or transcript'));
  if (c.pdfs_image_only) parts.push(tr('about.blind.scanWithoutText', { what: many(c.pdfs_image_only, tr('reader.pdfIsScan', null, 'PDF is a scan'), tr('reader.pdfsAreScans', null, 'PDFs are scans')) }, '{what} without text'));
  if (c.docs_without_text) parts.push(tr(c.docs_without_text === 1 ? 'about.blind.noReadableTextOne' : 'about.blind.noReadableText', { count: c.docs_without_text.toLocaleString() }, c.docs_without_text === 1 ? '{count} document gave no readable text when indexed' : '{count} documents gave no readable text when indexed'));
  if (!parts.length) return '';
  const t = parts.length > 1 ? parts.slice(0, -1).join(', ') + ' ' + tr('common.and', null, 'and') + ' ' + parts[parts.length - 1] : parts[0];
  return t[0].toUpperCase() + t.slice(1) + '. ';
}
// The optional local AI in the desktop app: what it is, where it runs, and its controls. '' in the server version.
function localAbout(st) {
  const l = st.local; if (!l) return '';
  const gb = n => (n / 1e9).toFixed(1) + ' GB';
  const where = (l.placement || []).filter(p => p.bytes > 2e8).map(p => tr('about.gbOnDevice', { size: gb(p.bytes), device: esc(p.device) }, '{size} on {device}')).join(', ');
  const line = { ready: tr('about.localRunning', null, 'running now'), stopped: tr('about.localAvailable', null, 'available; your first question loads it and may take a while; it stops after 15 minutes unused'), loading: tr('about.localStarting', null, 'starting') }[l.state];
  const btn = (a, t) => `<button class="btn plain" onclick="localAI('${a}')">${t}</button>`;
  return line ? `${esc(tr('about.localAiNamed', { name: l.name, status: line }, 'Local AI: {name}, {status}.'))}${where ? ' ' + esc(tr('about.localUses', { where }, 'It uses {where}.')) : ''} ${esc(tr('about.readsTextOnly', null, 'It reads text only.'))}
      <span class="row">${l.state === 'ready' ? btn('stop', tr('about.stopNow', null, 'Stop it now')) : ''}${btn('off', tr('about.turnOff', null, 'Turn off'))}</span>`
    : l.state === 'off' ? `${esc(tr('chat.aiTurnedOff', null, 'The local AI is turned off.'))} ${btn('on', tr('about.turnOn', null, 'Turn on'))}`
    : `${esc(tr('about.localAiNamed', { name: l.message || { absent: tr('about.addAi', null, 'not added. Add it in Library and local AI (about 17 GB).'), checking: tr('about.checkingFile', null, 'checking the file…'), measuring: tr('about.checkingMemory', null, 'checking this computer’s memory…') }[l.state] || l.state, status: '' }, 'Local AI: {name}, {status}.').replace(/,?\s*$/, '.'))} ${l.state === 'absent' ? `<a class="btn plain" href="/ui/setup.html#manage">${esc(tr('about.addTheLocalAi', null, 'Add the local AI'))}</a>` : ''}${btn('rescan', tr('about.lookAgain', null, 'Look again'))}`;
}
async function localAI(action) {
  try { await fetch('/api/assistant/local', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action }) }) } catch { }
  setTimeout(() => { if (location.hash.startsWith('#/about')) route() }, 400);
}
function contributePage() {
  setTitle(tr('contribute.title', null, 'Contribute to Lastbook'));
  main.innerHTML = `<section class="contribute">
    <h1 data-i18n="contribute.title">Contribute to Lastbook</h1>
    <p class="lead" data-i18n="contribute.welcome">We’re building Lastbook together. We need you.</p>
    <p class="contribute-help" data-i18n="contribute.help">Describe one idea and copy the prompt into your AI. You can review the change before it opens a pull request.</p>
    <div class="card contribute-card">
      <label for="contrib-idea"><span data-i18n="contribute.idea">Your idea</span> <span class="muted" data-i18n="contribute.optional">(optional)</span></label>
      <input id="contrib-idea" type="text" maxlength="300" placeholder="Example: Make offline map labels easier to read" data-i18n-placeholder="contribute.example">
      <label for="contrib-prompt" data-i18n="contribute.prompt">Prompt for your AI</label>
      <textarea id="contrib-prompt" rows="6" spellcheck="false"></textarea>
      <div class="contribute-actions">
        <button class="btn" id="copy-contrib" type="button" data-i18n="contribute.copy">Copy prompt</button>
        <a class="contribute-link" id="github-contrib" href="/contribute/github" target="_blank" rel="noopener"><span data-i18n="contribute.github">Open GitHub</span> <span aria-hidden="true">↗</span></a>
      </div>
      <p class="small muted contribute-note" data-i18n="contribute.local">Your idea stays on this device until you share it.</p>
      <p role="status" class="small" id="contrib-status"></p>
    </div>
  </section>`;
  const idea = $('#contrib-idea'), prompt = $('#contrib-prompt'), status = $('#contrib-status');
  const sync = () => {
    const ideaLine = idea.value.trim()
      ? tr('contribute.promptIdea', { idea: idea.value.trim() }, 'Make one focused change in a fork: {idea}')
      : tr('contribute.promptDefault', null, 'Help me choose a small improvement and make one focused change in a fork.');
    prompt.value = tr('contribute.promptBody', { ideaLine }, 'Read CONTRIBUTING.md in github.com/Immortal-Protocols/lastbook.\n\n{ideaLine}\n\nRun the relevant tests and prepare a pull request. Explain what changed and what you tested. Wait for my approval before opening the PR.');
  };
  sync();
  idea.addEventListener('input', sync);
  $('#copy-contrib').addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(prompt.value);
      status.dataset.i18n = 'contribute.copiedMessage';
      status.textContent = tr('contribute.copiedMessage', null, 'Prompt copied.');
      $('#copy-contrib').dataset.i18n = 'contribute.copied';
      $('#copy-contrib').textContent = tr('contribute.copied', null, 'Copied');
      translateRendered();
    } catch {
      prompt.focus();
      prompt.select();
      status.dataset.i18n = 'contribute.copyFallback';
      status.textContent = tr('contribute.copyFallback', null, 'Prompt selected. Press your copy shortcut.');
      translateRendered(status);
    }
  });
}

async function about(showUpdate = false) {
  setUiTitle('about.title', tr('about.title', null, 'About this library'));
  let dl = {}, st = {};
  LIB = null;   // About shows the counts as they are now
  const s = await libInfo();
  const oldServer = s.zims === undefined;   // it still serves the reports; this code does not
  try { dl = await api('/api/download-status') } catch { }
  try { st = await fetch('/api/assistant/status').then(r => r.json()) } catch { }   // not api(): this answer names an error when no model is running, and still holds what is wanted
  const ch = dl.channels && dl.channels.counts, ix = st.index || {};
  const contents = tr('about.contents', { pdfs: (s.pdfs || 0).toLocaleString(), pages: (s.pdf_pages || 0).toLocaleString(), web: (s.web_pages || 0).toLocaleString(), videos: (s.videos || 0).toLocaleString(), collections: s.collections || 0 }, '{pdfs} PDF manuals ({pages} pages), {web} saved web pages, {videos} downloaded videos and {collections} complete encyclopedias.');
  const pendingIx = ix.pending ? tr('about.stillToIndex', { count: ix.pending.toLocaleString() }, '{count} still to index') : '';
  const indexLine = ix.chunks ? ' ' + tr('about.meaningIndex', { chunks: ix.chunks.toLocaleString(), docs: ix.docs.toLocaleString() }, 'Meaning-based index: {chunks} passages from {docs} documents.') + (pendingIx ? ' ' + pendingIx + '.' : '') : '';
  const cantSee = st.vision === false ? tr('about.cantSeeRest', null, 'It also can’t see pictures in videos or raw map data. It reads text and says when it finds nothing.') : tr('about.cantSeeRestVision', null, 'It also can’t see pictures in videos or raw map data. It reads text (and page images when it asks to) and says when it finds nothing.');
  const remote = st.coverage && st.coverage.remote_videos ? ' ' + tr('about.remoteVideos', { count: st.coverage.remote_videos }, '{count} videos are stored on a remote drive and play only when that computer is reachable.') : '';
  main.innerHTML = `<h1 data-i18n="about.title">${esc(tr('about.title', null, 'About this library'))}</h1>
  <p class="lead" data-i18n="about.lead">${esc(tr('about.lead', null, 'Public manuals, health guides, courses, videos and encyclopedias kept on this computer, so it works when the internet and phones don’t.'))}</p>
  <div class="cards2" style="margin-top:16px">
   ${showUpdate && IN_WINDOW && window.LBUpdate ? LBUpdate.card() : ''}
   <div class="card"><b data-i18n="about.whatsInIt">${esc(tr('about.whatsInIt', null, 'What’s in it'))}</b><small>${esc(contents)}</small></div>
   ${ch ? `<div class="card"><b data-i18n="about.stillArriving">${esc(tr('about.stillArriving', null, 'Still arriving'))}</b><small>${esc(tr('about.queuedVideos', { pending: ch.pending.toLocaleString(), downloading: ch.downloading }, '{pending} more videos are queued and {downloading} downloading. Queued videos are not in the library yet — they appear only once downloaded.'))}</small></div>` : ''}
   <div class="card"><b data-i18n="about.assistant">${esc(tr('about.assistant', null, 'Assistant'))}</b><small>${localAbout(st) || (st.online ? esc(tr('about.localModelAvailable', { model: st.model }, 'Local model {model} — available.')) : esc(tr('about.localAiOff', null, 'No local model is running, so Chat can’t write answers right now. Guides, search, videos and the map all work without one.')))}${esc(indexLine)}</small></div>
   <div class="card"><b data-i18n="about.cantSee">${esc(tr('about.cantSee', null, 'What the assistant can’t see'))}</b><small>${blind(st.coverage)}${esc(cantSee)}${esc(remote)}</small></div>
   ${!showUpdate && IN_WINDOW && window.LBUpdate ? LBUpdate.card() : ''}
  </div>
  <h2 data-i18n="about.howLabelled">${esc(tr('about.howLabelled', null, 'How sources are labelled'))}</h2><ul>
   <li><b data-i18n="about.label.health">${esc(tr('about.label.health', null, 'International health & humanitarian guidance'))}</b> — ${esc(tr('about.label.healthDetail', null, 'WHO, Red Cross / Red Crescent, MSF, UNICEF, Sphere, St John Ambulance.'))}</li>
   <li><b data-i18n="about.label.hesperian">${esc(tr('about.label.hesperian', null, 'Hesperian community health guide'))}</b> — ${esc(tr('about.label.hesperianDetail', null, '“Where There Is No Doctor” and related books.'))}</li>
   <li><b data-i18n="about.label.gov">${esc(tr('about.label.gov', null, 'Government guidance'))}</b> — ${esc(tr('about.label.govDetail', null, 'FEMA, CDC, EPA, USDA, NOAA, National Park Service and similar.'))}</li>
   <li><b data-i18n="about.label.uni">${esc(tr('about.label.uni', null, 'University / extension service'))}</b> — ${esc(tr('about.label.uniDetail', null, 'e.g. National Center for Home Food Preservation, UC extension.'))}</li>
   <li><b data-i18n="about.label.manual">${esc(tr('about.label.manual', null, 'Manufacturer manual'))}</b> — ${esc(tr('about.label.manualDetail', null, 'only for the exact model named.'))}</li>
   <li><b data-i18n="about.label.community">${esc(tr('about.label.community', null, 'Community-written encyclopedia'))}</b> ${esc(tr('common.and', null, 'and'))} <b data-i18n="about.label.hobbyist">${esc(tr('about.label.hobbyist', null, 'hobbyist video'))}</b> — ${esc(tr('about.label.communityDetail', null, 'background; check anything risky against a manual.'))}</li></ul>
  <h2 data-i18n="about.doesNot">${esc(tr('about.doesNot', null, 'What this guide does not do'))}</h2><ul>
   <li data-i18n="about.doesNot.1">${esc(tr('about.doesNot.1', null, 'It points to original pages; the guides don’t write their own medical, chemical or electrical instructions. The assistant’s answers mark which sentences come from a cited page and which are its own wording.'))}</li>
   <li data-i18n="about.doesNot.2">${esc(tr('about.doesNot.2', null, 'Nothing here replaces trained help. Each guide shows the sources’ own limits.'))}</li>
   <li data-i18n="about.doesNot.3">${esc(tr('about.doesNot.3', null, 'Reading and watching are not the same as practising. Your ticks stay on this device.'))}</li>
   ${s.pack ? '' : `<li data-i18n="about.doesNot.4">${esc(tr('about.doesNot.4', null, 'Shopping lists and carts in older reports are plans, not proof of supplies you own.'))}</li>`}</ul>
  ${s.sources ? `<h2 data-i18n="about.sourcesCredits">${esc(tr('about.sourcesCredits', null, 'Sources and credits'))}</h2><p><a href="#/read/${encodeURIComponent(s.sources)}?${fromQ()}">${esc(tr('about.sourcesLink', null, 'Sources and permissions'))}</a>: ${esc(tr('about.sourcesDetail', null, 'every publisher in this library, where it came from, and how to ask for something to be removed.'))}</p>` : ''}
  ${IN_WINDOW ? '' : `<h2 data-i18n="about.usingPhone">${esc(tr('about.usingPhone', null, 'Using it on a phone'))}</h2><p>${esc(tr('about.usingPhoneDetail', { command: 'server.py --lan' }, 'Phones on the same Wi-Fi (no internet needed) can use the guide when this computer starts it with {command}. Phones need the access link shown in the terminal the first time.')).replace('server.py --lan', '<code>server.py --lan</code>')}</p>`}
  ${oldServer ? `<h2 data-i18n="about.otherWays">${esc(tr('about.otherWays', null, 'Other ways in'))}</h2><p><a href="/reports/gap-closure-status.html" target="_blank">${esc(tr('about.gapReport', null, 'Gap closure report'))}</a> · <a href="/reports/learning-pathways.html" target="_blank">${esc(tr('about.pathwaysReport', null, 'Learning pathways report'))}</a> · <a href="/reports/survival-tools-cart.html" target="_blank">${esc(tr('about.suppliesPlanning', null, 'Supplies planning'))}</a></p>` : ''}`;
  if (IN_WINDOW && window.LBUpdate) LBUpdate.mount(main);   // Check for updates (web/update.js): only when the person asks
}

route();
if ('serviceWorker' in navigator && /^(127\.0\.0\.1|localhost)$/.test(location.hostname)) navigator.serviceWorker.register('/sw.js').catch(() => { });
