'use strict';
/* Small tools inside a guide's situations (content/SCHEMA.md, "tools"). They only do arithmetic on figures their cited pages give,
   or keep a time, and they show the figure and the page every result comes from. No advice of their own.
     dose   amount = the page's rate × how much water, for each source side by side (sources may disagree: none is picked)
     clock  the time something happened and how long ago it was, kept on this device until cleared */
const Tools = (() => {
  const GAL = 3.785411784;     // liters in a US gallon
  const UNIT = { L: ['liter', 'liters'], gal: ['gallon', 'gallons'] };
  const unitName = (u, n) => UNIT[u][n === 1 ? 0 : 1];
  const num = n => n.toLocaleString(undefined, { maximumFractionDigits: 1 });
  const defaultUnit = () => store.get('toolUnit', /^en-us$/i.test(navigator.language || '') ? 'gal' : 'L');
  const cite = s => `<span class="src">From <a href="${hrefFor(s)}">${s.src ? '“' + esc(s.src.title) + '”' : 'the source'}</a> · ${srcText(s.src, s.page)}</span>`;

  // One result line per condition a source names ("Clear water", "Cloudy or dirty water"), or one line when it names none.
  function doseLines(source, amount, unit) {
    const groups = new Map();
    for (const r of source.rates || []) {
      const k = r.when || '';
      if (!groups.has(k) || r.per === unit) groups.set(k, r);   // the page's own rate for this unit when it gives one
    }
    return [...groups.entries()].map(([when, r]) => {
      const rate = r.per === unit ? r.amount : r.per === 'gal' ? r.amount / GAL : r.amount * GAL;
      const exact = rate * amount, whole = Math.abs(exact - Math.round(exact)) < 1e-9;   // 0.3 × 10 is 3.0000000000000004, still 3
      const drops = whole ? Math.round(exact) : Math.ceil(exact);
      const how = `${num(rate)} drop${rate === 1 ? '' : 's'} per ${unitName(unit, 1)} × ${num(amount)} ${unitName(unit, amount)}`
        + (r.per === unit ? '' : ` (the page gives ${num(r.amount)} per ${unitName(r.per, 1)}; 1 gallon is ${GAL.toLocaleString(undefined, { maximumFractionDigits: 3 })} liters)`)
        + (whole ? '' : ', rounded up to a whole drop');
      return `<li>${when ? `<span class="when">${esc(when)}:</span> ` : ''}<b class="amt">${drops.toLocaleString()} drop${drops === 1 ? '' : 's'}</b><small>${how}</small></li>`;
    }).join('');
  }

  function doseHtml(t) {
    const u = defaultUnit();
    return `<section class="tool" data-tool="dose" data-id="${esc(t.id)}" aria-labelledby="tool-${esc(t.id)}">
      <h2 id="tool-${esc(t.id)}">${ico('water')}${esc(t.title)}</h2>
      ${t.note ? `<p class="tnote">${esc(t.note)}</p>` : ''}
      <div class="tin"><label>How much water? <input type="number" inputmode="decimal" min="0" max="100000" step="any" value="1" data-amount></label>
        <span class="seg" role="group" aria-label="Unit">${Object.keys(UNIT).map(k => `<button type="button" class="chip" data-unit="${k}" aria-pressed="${k === u}">${unitName(k, 2)}</button>`).join('')}</span></div>
      <p class="tmsg" data-msg hidden></p>
      <ol class="tout" aria-live="polite">${(t.sources || []).map((s, i) => `<li data-src="${i}"><p class="strength">${esc(s.strength || '')}</p><ul class="lines"></ul>${s.note ? `<p class="small">${esc(s.note)}</p>` : ''}${cite(s)}</li>`).join('')}</ol>
    </section>`;
  }

  // An amount that can be worked out, or the one sentence that says why not (shown once, not once per source).
  const amountProblem = v => !(v > 0) ? 'Type how much water you have.' : v > 100000 ? 'Type an amount up to 100,000.' : '';
  function wireDose(el, t) {
    const input = $('[data-amount]', el), msg = $('[data-msg]', el);
    let wait = 0;
    const update = () => {
      clearTimeout(wait);
      const unit = $('[data-unit][aria-pressed=true]', el).dataset.unit, amount = parseFloat(input.value), why = amountProblem(amount);
      msg.hidden = !why; msg.textContent = why;
      (t.sources || []).forEach((s, i) => {
        const ul = $(`[data-src="${i}"] .lines`, el), html = why ? '' : doseLines(s, amount, unit);
        if (ul.innerHTML !== html) ul.innerHTML = html;      // the results are a live region: rewrite only what changed
      });
    };
    // Typing "12" would otherwise be read out for 1 and then for 12: the results follow once typing pauses. Units change at once.
    const later = () => { clearTimeout(wait); wait = setTimeout(update, 500) };
    $$('[data-unit]', el).forEach(b => b.addEventListener('click', () => {
      $$('[data-unit]', el).forEach(x => x.setAttribute('aria-pressed', x === b));
      store.set('toolUnit', b.dataset.unit);
      update();
    }));
    input.addEventListener('input', later);
    input.addEventListener('change', update);
    update();
  }

  const hm = d => d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
  function ago(ms) {   // words, not "h": some screen readers say the letter
    const m = Math.max(0, Math.floor(ms / 60000)), h = Math.floor(m / 60);
    return h ? `${h} hour${h === 1 ? '' : 's'} ${m % 60} min` : `${m} min`;
  }

  function clockHtml(t) {
    return `<section class="tool" data-tool="clock" data-id="${esc(t.id)}" aria-labelledby="tool-${esc(t.id)}">
      <h2 id="tool-${esc(t.id)}">${ico('clock')}${esc(t.title)}</h2>
      <p class="tclock" data-show></p>
      <p class="sr" role="status" data-said></p>
      <div class="tin"><button type="button" class="btn" data-now>${esc(t.now || 'It went on now')}</button>
        <label>${esc(t.at || 'or it went on at')} <input type="time" data-at></label>
        <button type="button" class="btn plain" data-clear hidden>Clear</button></div>
      <ul class="tout">${(t.sources || []).map(s => `<li>${s.note ? `<p class="small">${esc(s.note)}</p>` : ''}${cite(s)}</li>`).join('')}</ul>
      <p class="small muted">Kept on this device only, until you clear it.</p>
    </section>`;
  }

  // The ticking line is not a live region (it would be read out every minute): setting and clearing are said once, in [data-said].
  // While a time is kept, the "now" button is hidden, so a second tap with shaking hands cannot replace it; Clear brings it back.
  function wireClock(el, t) {
    const key = 'tool.' + t.id, show = $('[data-show]', el), at = $('[data-at]', el), clear = $('[data-clear]', el), now = $('[data-now]', el), said = $('[data-said]', el);
    const paint = () => {
      const v = store.get(key, null);
      clear.hidden = !v; now.hidden = !!v;
      const html = v ? `<b>On at ${esc(hm(new Date(v.at)))}</b> · ${ago(Date.now() - v.at)} ago` : 'Not started.';
      if (show.innerHTML !== html) show.innerHTML = html;
    };
    const set = ms => {
      const from = document.activeElement;
      store.set(key, { at: ms });
      if (from === now) clear.hidden = false, clear.focus();   // the button pressed is about to hide: focus goes to Clear first
      paint();
      said.textContent = `Kept: on at ${hm(new Date(ms))}.`;
    };
    now.addEventListener('click', () => set(Date.now()));
    let typed = 0;
    const commit = () => {   // a typed time is kept when typing pauses or the field is left, not at each arrow-key step
      clearTimeout(typed);
      const [h, m] = (at.value || '').split(':').map(Number);
      if (!Number.isFinite(h) || !Number.isFinite(m)) return;
      const d = new Date(); d.setHours(h, m, 0, 0);
      if (d.getTime() > Date.now() + 60000) d.setDate(d.getDate() - 1);   // a time later than now was yesterday
      const v = store.get(key, null);
      if (!v || v.at !== d.getTime()) set(d.getTime());
    };
    at.addEventListener('change', () => { clearTimeout(typed); typed = setTimeout(commit, 1200) });
    at.addEventListener('blur', commit);
    at.addEventListener('keydown', e => { if (e.key === 'Enter') commit() });
    clear.addEventListener('click', () => {
      store.set(key, null); at.value = '';
      now.hidden = false; now.focus();                           // before Clear hides itself, so focus is not lost
      paint();
      said.textContent = 'Cleared.';
    });
    paint();
    const timer = setInterval(() => { if (!el.isConnected) clearInterval(timer); else paint() }, 20000);
  }

  const KINDS = { dose: [doseHtml, wireDose], clock: [clockHtml, wireClock] };
  return {
    html: t => KINDS[t.kind] ? KINDS[t.kind][0](t) : '',
    wire(root, tools) {   // tools: the same objects html() was given, by id
      $$('section.tool', root).forEach(el => {
        const t = tools.find(x => x.id === el.dataset.id);
        if (t && KINDS[t.kind]) KINDS[t.kind][1](el, t);
      });
    },
    _doseLines: doseLines, _ago: ago, _amountProblem: amountProblem, _html: { dose: doseHtml, clock: clockHtml },   // for app/tests/test_tools.py
  };
})();
