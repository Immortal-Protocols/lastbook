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

  // Another form of the same English word: "tourniquets" and "tourniquet", "fainting" and "fainted", "choked" and
  // "choking". forms(w) is the word itself, then what is left when one common ending comes off: a plural -s, -es
  // (boxes, stitches) or -ies (batteries), and -ed or -ing, also with the dropped e put back (choking: choke) or a
  // doubled letter undone (stopped: stop). Two words are forms of each other when their lists share an entry.
  // Irregular forms (stung, frozen) are not covered.
  function forms(w) {
    const out = [w], add = (f, min) => { if (f.length >= min && !out.includes(f)) out.push(f) };
    const cut = end => w.endsWith(end) ? w.slice(0, -end.length) : null;
    let f;
    if ((f = cut('ies')) !== null) add(f + 'y', 4);
    else if ((f = cut('es')) !== null && /(?:s|x|z|ch|sh)$/.test(f)) add(f, 3);
    else if ((f = cut('s')) !== null && !f.endsWith('s')) add(f, 3);
    for (const end of ['ed', 'ing']) {
      if ((f = cut(end)) === null) continue;
      add(f, 4); add(f + 'e', 4);
      if (/([^aeiou])\1$/.test(f)) add(f.slice(0, -1), 4);
    }
    return out;
  }
  // A test for one piece of text: is a query word another form of one of its words? A form that is a stop word
  // doesn't count ("cans" is not "can"). Scripts without spaces have no such endings.
  function formMatcher(text) {
    const have = new Set(splitWords(text).flatMap(forms));
    return (w, stop) => !NO_SPACES.test(w) && forms(w).some(f => have.has(f) && !(stop && stop.has(f)));
  }

  // Topic search, scored as before: a word found in a topic's title, short line or keywords counts 1,
  // a word found in one of its choices counts 1.5; topics within 60% of the best score, top 3.
  // A choice's "urgent" phrases ("not breathing") pick that choice for its topic whenever the search names one,
  // even if another choice matches more words ("fractured neck and not breathing"). They don't change the score.
  // Only a search that finds nothing at all ("tourniquets", "he is fainting") is tried again by word form, scored
  // the same way. A search that finds any guide gives exactly what it gave before.
  const cache = new WeakMap();   // topics are replaced, never edited in place
  function topicMatchers(t) {
    let m = cache.get(t);
    if (!m) {
      const shown = (t.choices || []).filter(c => !c.goto);
      const hay = [t.title, t.short, ...(t.keywords || [])].join(' '), text = c => c.label + ' ' + (c.hint || '');
      m = { hay: matcher(hay), hayForm: formMatcher(hay),
            choices: shown.map(c => ({ c, has: matcher(text(c)), hasForm: formMatcher(text(c)) })),
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
    const all = splitWords(q);
    const score = byForm => {
      const out = [];
      for (const t of topics) {
        const m = topicMatchers(t), hay = byForm ? w => m.hayForm(w, stop) : m.hay;
        const s = words.filter(hay).length;
        let best = null, bs = 0;
        for (const { c, has, hasForm } of m.choices) {
          const n = words.filter(byForm ? w => hasForm(w, stop) : has).length;
          if (n > bs) { bs = n; best = c }
        }
        const u = m.urgent.find(x => x.phrases.some(p => names(all, p)));
        if (u) best = u.c;
        if (s || bs) out.push({ t, c: best, s: s + bs * 1.5, u: !!u });
      }
      return out;
    };
    let out = score(false);
    if (!out.length) out = score(true);
    out.sort((a, b) => b.s - a.s);
    const shown = out.filter(o => o.s >= out[0]?.s * 0.6);
    // A guide whose urgent phrase the search names comes first, even below the cut ("unconscious in the flood water").
    // Without one, the list is exactly as before.
    const urgent = out.filter(o => o.u);
    return [...urgent, ...shown.filter(o => !o.u)].slice(0, 3).map(({ t, c, s }) => ({ t, c, s }));
  }

  root.SearchWords = Object.freeze({ fold, splitWords, queryWords, matcher, rankTopics, hasSegmenter: () => !!segmenter() });
})(globalThis);
