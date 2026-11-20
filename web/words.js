/* Word handling for topic search: split, fold and match words in any script, not just a-z.
   Loaded before app.js. No DOM, no network: app/tests/test_topic_search.py runs these same functions in Node. */
(function (root) {
  'use strict';

  // Scripts written without spaces between words. A word in one of these matches anywhere in the text, at any length.
  const NO_SPACES = /[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Hangul}\p{Script=Thai}\p{Script=Lao}\p{Script=Khmer}\p{Script=Myanmar}]/u;
  // Accent marks on Latin letters, once a word is decomposed. Only Latin, the same as the library's FTS5 index (unicode61).
  const LATIN_MARKS = /(\p{Script=Latin})\p{M}+/gu;
  // Anything that isn't a letter, mark or digit separates words, as [^a-z0-9] did for a-z.
  const NOT_WORD = /[^\p{L}\p{M}\p{N}]+/u;

  // The key two texts are compared by. Display text is never changed.
  // Order: lower-case, decompose (NFKD), then remove marks. Decomposing before removing marks is the part that
  // matters: NFC "İ" is one character with no mark to remove, and lower-casing it afterwards gives "i" plus a
  // combining dot (U+0307), so "İstanbul" would miss "istanbul". NFKD also splits é into e + accent.
  // Final ς folds to σ and ß stays, as in FTS5. One deliberate difference: NFKD also folds full-width Latin
  // ("ｗａｔｅｒ", typed on Chinese and Japanese keyboards) to "water", which FTS5 keeps apart.
  function fold(s) {
    return String(s).toLowerCase().normalize('NFKD').replace(LATIN_MARKS, '$1').normalize('NFC').replace(/ς/g, 'σ');
  }

  // Intl.Segmenter is in WebView2, WKWebView (macOS 14+) and WebKitGTK; the fallback below covers older engines
  // and any engine whose constructor throws.
  let seg;   // made once; null where Intl.Segmenter is missing or unusable
  function segmenter() {
    if (seg === undefined) {
      try { seg = typeof Intl !== 'undefined' && Intl.Segmenter ? new Intl.Segmenter(undefined, { granularity: 'word' }) : null }
      catch (e) { seg = null }
    }
    return seg;
  }

  // Words of a text, folded. Segment first, then split each segment wherever there's no letter, mark or digit:
  // the segmenter keeps "water's", "first_aid" and "e.coli" whole, but here they split as they always have
  // (water + s, first + aid, e + coli), and ZWJ, ZWNJ and soft hyphens separate words, as in FTS5.
  // Folding comes after segmenting, so the segmenter sees the text as typed. Every segment is kept and that
  // split drops the spaces and punctuation, rather than trusting isWordLike: JavaScriptCore marks numbers
  // such as 112 as not word-like, V8 does not.
  // Without Intl.Segmenter that split is all there is: every script that uses spaces works, but a run of
  // Chinese or Thai stays one word.
  function splitWords(text) {
    const t = String(text), s = segmenter();
    const raw = s ? Array.from(s.segment(t), x => x.segment) : [t];
    const out = [];
    for (const w of raw) for (const part of w.split(NOT_WORD)) { const f = fold(part); if (f) out.push(f) }
    return out;
  }

  // Words worth searching for, counted in characters rather than UTF-16 units: words in scripts without spaces at
  // any length (水, 净化); two-letter words in scripts without case (आग, אש, دم); otherwise three or more, as before.
  function keep(w) {
    const n = Array.from(w).length;
    return NO_SPACES.test(w) || n > 2 || (n === 2 && /\p{L}/u.test(w) && !/\p{Ll}/u.test(w));
  }
  function queryWords(q, stop) {
    return splitWords(q).filter(w => keep(w) && !(stop && stop.has(w)));
  }

  // A test for one piece of text: does a query word start one of its words? For scripts without spaces,
  // is the word anywhere in it? No RegExp is built from what was typed.
  function matcher(text) {
    const words = splitWords(text), whole = fold(text);
    return w => NO_SPACES.test(w) ? whole.includes(w) : words.some(h => h.startsWith(w));
  }

  // Topic search, scored as before: a word found in a topic's title, short line or keywords counts 1,
  // a word found in one of its choices counts 1.5; topics within 60% of the best score, top 3.
  // A choice's "urgent" phrases ("not breathing") pick that choice for its topic whenever the search names one,
  // even if another choice matches more words ("fractured neck and not breathing"). They don't change the score.
  const cache = new WeakMap();   // topics are replaced, never edited in place
  function topicMatchers(t) {
    let m = cache.get(t);
    if (!m) {
      const shown = (t.choices || []).filter(c => !c.goto);
      m = { hay: matcher([t.title, t.short, ...(t.keywords || [])].join(' ')),
            choices: shown.map(c => ({ c, has: matcher(c.label + ' ' + (c.hint || '')) })),
            urgent: shown.filter(c => c.urgent).map(c => ({ c, phrases: c.urgent.map(splitWords).filter(p => p.length) })) };
      cache.set(t, m);
    }
    return m;
  }
  // Does a phrase's words appear in order, as whole words, among all the search's words (stop words included)?
  function names(all, p) {
    return all.some((_, i) => p.every((w, j) => all[i + j] === w));
  }
  function rankTopics(q, topics, stop) {
    const words = queryWords(q, stop);
    if (!words.length || !topics) return [];
    const all = splitWords(q), out = [];
    for (const t of topics) {
      const m = topicMatchers(t);
      const s = words.filter(m.hay).length;
      let best = null, bs = 0;
      for (const { c, has } of m.choices) { const n = words.filter(has).length; if (n > bs) { bs = n; best = c } }
      const u = m.urgent.find(x => x.phrases.some(p => names(all, p)));
      if (u) best = u.c;
      if (s || bs) out.push({ t, c: best, s: s + bs * 1.5, u: !!u });
    }
    out.sort((a, b) => b.s - a.s);
    const shown = out.filter(o => o.s >= out[0]?.s * 0.6);
    // A guide whose urgent phrase the search names comes first, even below the cut ("unconscious in the flood water").
    // Without one, the list is exactly as before.
    const urgent = out.filter(o => o.u);
    return [...urgent, ...shown.filter(o => !o.u)].slice(0, 3).map(({ t, c, s }) => ({ t, c, s }));
  }

  // A prototype for docs/COUNTRY-SEARCH.md, not yet used by app.js. A number the table lists is answered by the
  // table, never by a guide's keywords. With a country the person chose, its meaning there comes first. Without one,
  // a number that means different services in different places gets one row per country, by country name, and no
  // guide is picked for it. The rest of the search is ranked as before, without the number.
  // table: { services: { service: [guide id, choice id] }, countries: { code: { name, numbers: { number: service } } } }
  function numberRows(q, topics, stop, table, country) {
    const all = splitWords(q), found = all.filter(w => /^\p{Nd}+$/u.test(w) && meanings(table, w).length);
    if (!found.length) return rankTopics(q, topics, stop);
    const rows = [];
    for (const n of found) {
      const here = country && table.countries[country], own = here && here.numbers[n];
      const list = own ? [{ code: country, service: own }] : meanings(table, n);
      const one = new Set(list.map(m => m.service)).size === 1;
      for (const m of list) {
        const [g, c] = table.services[m.service] || [];
        const t = g ? (topics || []).find(x => x.id === g) : null;
        rows.push({ t, c: t && c ? t.choices.find(x => x.id === c) || null : null, s: 0, number: n, service: m.service,
                    country: own || !one ? m.code : null });
        if (one) break;   // every country listed agrees: one row, as a global keyword would give
      }
    }
    // A guide the other words also found keeps the choice they picked ("118 bleeding" in Italy: bleeding).
    const rest = rankTopics(all.filter(w => !found.includes(w)).join(' '), topics, stop);
    for (const r of rows) { const o = r.t && !r.c && rest.find(x => x.t === r.t); if (o) r.c = o.c }
    return [...rows, ...rest.filter(r => !rows.some(x => x.t && x.t === r.t))];
  }
  function meanings(table, n) {
    if (!table) return [];
    return Object.entries(table.countries).filter(([, c]) => c.numbers[n])
      .sort((a, b) => a[1].name.localeCompare(b[1].name, 'en'))
      .map(([code, c]) => ({ code, service: c.numbers[n] }));
  }

  root.SearchWords = Object.freeze({ fold, splitWords, queryWords, matcher, rankTopics, numberRows, hasSegmenter: () => !!segmenter() });
})(globalThis);
